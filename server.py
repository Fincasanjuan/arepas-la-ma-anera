"""Independent Arepas application. Python stdlib, transactional SQLite persistence."""
import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
import io
import team
import ai_assistant
from datetime import datetime, timedelta
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit, parse_qs, quote

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('AREPAS_DATA_DIR', ROOT / 'data'))
PRODUCTS = ['Grandes', 'Normales', 'Media tela', 'Promo 15 La Mañanera',
            'Promo 20 Ricky', 'Promo 20 Norteña', 'Redonda x50', 'Rellenar']
INPUTS = ['Maíz blanco', 'Maíz amarillo', 'Harina', 'Sal', 'Químico', 'Bolsas']
COLOMBIA = ZoneInfo('America/Bogota')


class RuleError(Exception):
    pass


def now():
    return datetime.now(COLOMBIA).isoformat(timespec='seconds')


def delivery_day(stamp=None):
    stamp = stamp or datetime.now(COLOMBIA)
    return (stamp + timedelta(days=1 if stamp.hour >= 12 else 0)).date().isoformat()


def number(value, integer=False):
    if isinstance(value, bool):
        raise RuleError('Cantidad inválida.')
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise RuleError('Escribe un número válido.')
    if not 0 <= result <= 1_000_000_000 or integer and result != int(result):
        raise RuleError('La cantidad debe ser positiva y válida.')
    return int(result) if integer else result


def money(value):
    return number(value, True)


def text(value, required=True, limit=250):
    result = str(value or '').strip()
    if len(result) > limit or required and not result:
        raise RuleError('Completa los campos obligatorios.')
    return result


def quantities(value, allow_empty=False):
    if not isinstance(value, list) or len(value) != len(PRODUCTS):
        raise RuleError('Revisa las cantidades por referencia.')
    result = [number(v, True) for v in value]
    if not allow_empty and not sum(result):
        raise RuleError('Agrega al menos una cantidad.')
    return result


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    return salt + ':' + hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()


def password_valid(password, stored):
    return hmac.compare_digest(password_hash(password, stored.split(':')[0]), stored)


def connect():
    DATA.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATA / 'arepas.sqlite3', timeout=15, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA journal_mode=WAL')
    return db


def initialize():
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, name TEXT NOT NULL, phone TEXT UNIQUE,
          role TEXT NOT NULL CHECK(role IN ('admin','rider','dispatcher')), password TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id TEXT REFERENCES users(id), expires INTEGER);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY, kind TEXT NOT NULL, owner TEXT,
          date TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL, created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS movements(id INTEGER PRIMARY KEY, record_id TEXT REFERENCES records(id),
          item TEXT NOT NULL, qty REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, actor TEXT NOT NULL, action TEXT NOT NULL,
          record_id TEXT, detail TEXT NOT NULL, created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS requests(key TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, response TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS login_attempts(ip TEXT PRIMARY KEY, failures INTEGER NOT NULL, until INTEGER NOT NULL);
        ''')
        team.initialize(db)
        db.execute('INSERT OR IGNORE INTO settings VALUES(?,?)',('ai:signing',json.dumps(secrets.token_hex(32))))


def bootstrap_admin():
    """Create the first hosted admin from a server secret; never reset an existing one."""
    code = os.environ.get('AREPAS_ADMIN_PASSWORD', '')
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        try:
            if db.execute("SELECT id FROM users WHERE role='admin'").fetchone():
                db.execute('COMMIT')
                return
            if not code:
                if os.environ.get('RENDER_EXTERNAL_URL'):
                    raise RuleError('Configura AREPAS_ADMIN_PASSWORD en Render antes de iniciar.')
                db.execute('COMMIT')
                return
            if len(code) < 12:
                raise RuleError('AREPAS_ADMIN_PASSWORD necesita al menos 12 caracteres.')
            user = {'id': secrets.token_hex(12), 'name': text(os.environ.get('AREPAS_ADMIN_NAME', 'Dujardy'))}
            db.execute('INSERT INTO users VALUES(?,?,?,?,?)',
                       (user['id'], user['name'], 'admin', 'admin', password_hash(code)))
            team.join_team(db)
            audit(db, user, 'setup-server', user['id'], {'name': user['name']})
            db.execute('COMMIT')
        except Exception:
            db.execute('ROLLBACK')
            raise


def public_origin(headers):
    configured = os.environ.get('AREPAS_PUBLIC_ORIGIN') or os.environ.get('RENDER_EXTERNAL_URL')
    if configured:
        origin = configured.rstrip('/')
        parsed = urlsplit(origin)
        if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.path or parsed.query or parsed.fragment or parsed.username:
            raise RuleError('Revisa la dirección pública configurada en el servidor.')
        return origin
    return 'http://' + headers.get('Host', '')


def stock(db):
    return {r['item']: r['qty'] for r in db.execute(
        "SELECT m.item, SUM(m.qty) qty FROM movements m JOIN records r ON r.id=m.record_id "
        "WHERE r.status!='void' GROUP BY m.item")}


def setting(db, key, default=None):
    row = db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
    return json.loads(row['value']) if row else default


def audit(db, user, action, rid, detail):
    db.execute('INSERT INTO audit(actor,action,record_id,detail,created) VALUES(?,?,?,?,?)',
               (user['id'] if user else 'pedido público', action, rid, json.dumps(detail, ensure_ascii=False), now()))


def record(db, kind, owner, payload, status='confirmed', date=None, rid=None):
    rid = rid or secrets.token_hex(12)
    db.execute('INSERT INTO records VALUES(?,?,?,?,?,?,?)',
               (rid, kind, owner, date or now()[:10], json.dumps(payload, ensure_ascii=False), status, now()))
    return rid


def move(db, rid, item, qty):
    db.execute('INSERT INTO movements(record_id,item,qty) VALUES(?,?,?)', (rid, item, qty))


def ensure_inventory(db):
    negative = [item for item, qty in stock(db).items() if qty < -0.00001]
    if negative:
        raise RuleError('Inventario insuficiente: ' + ', '.join(negative))


def get_record(db, rid, kind=None):
    row = db.execute('SELECT * FROM records WHERE id=?', (rid,)).fetchone()
    if not row or row['status'] == 'void' or kind and row['kind'] != kind:
        raise RuleError('No se encontró un registro vigente.')
    return dict(row), json.loads(row['payload'])


def admin(user):
    if not user or user['role'] != 'admin':
        raise RuleError('Esta acción requiere Administración.')


def operational(user):
    if not user:
        raise RuleError('Ingresa con tu código personal.')


def owner_allowed(user, owner):
    operational(user)
    if user['role'] == 'rider' and user['id'] != owner:
        raise RuleError('Solo puedes consultar tus propios registros.')


def debt_balance(db, debt_id):
    _, payload = get_record(db, debt_id, 'debt')
    paid = sum(json.loads(r['payload'])['amount'] for r in db.execute(
        "SELECT payload FROM records WHERE kind='payment' AND status!='void'")
        if json.loads(r['payload'])['debt_id'] == debt_id)
    return payload['amount'] - paid


def route_balance(db, close_id):
    _, payload = get_record(db, close_id, 'close')
    paid = sum(json.loads(r['payload'])['amount'] for r in db.execute(
        "SELECT payload FROM records WHERE kind='routePayment' AND status!='void'")
        if json.loads(r['payload'])['close_id'] == close_id)
    return payload['balance'] - paid


def dispatch_quote(db, user, rid):
    operational(user)
    row, payload = get_record(db, rid, 'dispatch')
    owner_allowed(user, row['owner'])
    if row['status'] != 'draft':
        raise RuleError('Este despacho ya está confirmado.')
    qty = quantities(payload['qty'])
    config = setting(db, 'config:'+row['owner'], setting(db, 'config:default', {}))
    prices, returns = config.get('prices', [0]*8), config.get('returnPrices', [0]*8)
    if any(q and not prices[i] for i,q in enumerate(qty)):
        raise RuleError('Administración debe configurar los precios antes de confirmar.')
    signed = {'id': row['id'], 'version': payload.get('version', 0), 'qty': qty,
              'prices': prices, 'returnPrices': returns}
    token = hashlib.sha256(json.dumps(signed, sort_keys=True).encode()).hexdigest()
    inventory = stock(db)
    shortages = [{'item': PRODUCTS[i], 'missing': q-inventory.get(PRODUCTS[i], 0)}
                 for i,q in enumerate(qty) if q > inventory.get(PRODUCTS[i], 0)]
    return {**signed, 'owner': row['owner'], 'total': sum(q*prices[i] for i,q in enumerate(qty)),
            'token': token, 'shortages': shortages}


def apply_action(db, user, action, p):
    if action.startswith('team-'):
        return team.action(db, user, action, p, now(), DATA)
    if action == 'ai-save':
        admin(user)
        document=ai_assistant.verify(p.get('preview'),setting(db,'ai:signing'),user['id'])
        token=p['preview']['token']
        prior=db.execute("SELECT id,status,payload FROM records WHERE kind='aiReport' AND json_extract(payload,'$.token')=?",(token,)).fetchone()
        if prior:
            if prior['status']=='void':
                raise RuleError('Este informe fue anulado. Genera uno nuevo.')
            return {'id':prior['id'],'message':'El informe ya está guardado.','detail':json.loads(prior['payload'])}
        payload={**document,'token':token}
        rid=record(db,'aiReport',user['id'],payload)
        audit(db,user,'ai-save',rid,{'model':document['model'],'generatedAt':document['generatedAt']})
        return {'id':rid,'message':'Informe guardado.','detail':payload}
    if action == 'preview-dispatch':
        quote = dispatch_quote(db, user, p.get('id'))
        return {'id': p.get('id'), 'message': 'Revisa el despacho antes de confirmar.', 'detail': quote}
    if action == 'order':
        name, phone = text(p.get('name')), text(p.get('phone'), limit=25)
        if not phone.isdigit() or not 7 <= len(phone) <= 15:
            raise RuleError('Escribe el celular solo con números.')
        day = text(p.get('date'))
        try:
            if datetime.strptime(day, '%Y-%m-%d').date().isoformat() != day:
                raise ValueError()
        except ValueError:
            raise RuleError('Fecha de entrega inválida.')
        earliest = delivery_day()
        if day < earliest or day > (datetime.now(COLOMBIA) + timedelta(days=30)).date().isoformat():
            raise RuleError('Elige una fecha válida. Después de las 12, el pedido queda para mañana.')
        rider = db.execute("SELECT id FROM users WHERE phone=? AND role='rider'", (phone,)).fetchone()
        payload = {'name': name, 'phone': phone, 'qty': quantities(p.get('qty'))}
        rid = record(db, 'order', rider['id'] if rider else None, payload, date=day)
    elif action == 'user':
        admin(user)
        role = p.get('role')
        if role not in ('rider', 'dispatcher'):
            raise RuleError('Perfil inválido.')
        code = text(p.get('code'), limit=100)
        if len(code) < 8:
            raise RuleError('El código personal necesita al menos 8 caracteres.')
        rid = secrets.token_hex(12)
        phone = text(p.get('phone'), limit=25)
        if not phone.isdigit() or not 7 <= len(phone) <= 15:
            raise RuleError('Celular inválido.')
        db.execute('INSERT INTO users VALUES(?,?,?,?,?)',
                   (rid, text(p.get('name')), phone, role, password_hash(code)))
        db.execute("UPDATE records SET owner=? WHERE kind='order' AND owner IS NULL AND json_extract(payload,'$.phone')=?", (rid, phone))
        team.join_team(db)
        payload = {'name': p['name'], 'role': role}
    elif action == 'settings':
        admin(user)
        payload = {'prices': quantities(p.get('prices'), True), 'returnPrices': quantities(p.get('returnPrices'), True),
                   'yields': quantities(p.get('yields'), True), 'bags': quantities(p.get('bags'), True)}
        target = p.get('rider') or 'default'
        if target != 'default' and not db.execute("SELECT id FROM users WHERE id=? AND role='rider'", (target,)).fetchone():
            raise RuleError('Repartidor inválido.')
        rid = 'config:' + target
        db.execute('INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                   (rid, json.dumps(payload)))
    elif action == 'logo':
        admin(user)
        value = p.get('value', '')
        if not isinstance(value, str) or not value.startswith(('data:image/png;base64,', 'data:image/jpeg;base64,')) or len(value) > 2_000_000:
            raise RuleError('Carga el logo oficial en PNG o JPG, máximo 1 MB.')
        try:
            raw=base64.b64decode(value.split(',',1)[1],validate=True)
        except ValueError:
            raise RuleError('No se pudo leer el logo.')
        if len(raw)>1_000_000:
            raise RuleError('El logo debe pesar máximo 1 MB.')
        team.check_file(value.split(';',1)[0].removeprefix('data:'),raw)
        rid, payload = 'logo', {'updated': True}
        db.execute('INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', ('logo', json.dumps(value)))
    elif action == 'input':
        admin(user)
        item = p.get('item')
        if item not in INPUTS:
            raise RuleError('Insumo inválido.')
        payload = {'item': item, 'qty': number(p.get('qty')), 'cost': money(p.get('cost')), 'unit': text(p.get('unit'))}
        required_unit = 'bultos' if item in INPUTS[:2] else 'gramos' if item == 'Químico' else 'unidades' if item == 'Bolsas' else None
        if required_unit and payload['unit'] != required_unit:
            raise RuleError('Para ' + item + ' registra la cantidad en ' + required_unit + '.')
        if not required_unit:
            previous = db.execute("SELECT json_extract(payload,'$.unit') unit FROM records WHERE kind='input' AND status!='void' AND json_extract(payload,'$.item')=? LIMIT 1", (item,)).fetchone()
            if previous and previous['unit'] != payload['unit']:
                raise RuleError('Mantén la unidad registrada para este insumo: ' + previous['unit'])
        if not payload['qty']:
            raise RuleError('La entrada debe ser mayor que cero.')
        rid = record(db, 'input', user['id'], payload)
        move(db, rid, item, payload['qty'])
    elif action == 'production':
        admin(user)
        qty = quantities(p.get('qty'))
        config = setting(db, 'config:default', {})
        yields, bags = config.get('yields', [0]*8), config.get('bags', [0]*8)
        if any(q and not yields[i] for i, q in enumerate(qty)):
            raise RuleError('Configura el rendimiento por bulto de cada referencia.')
        bultos = sum(q / yields[i] for i, q in enumerate(qty) if q)
        corn = p.get('corn')
        if corn not in INPUTS[:2]:
            raise RuleError('Selecciona el tipo de maíz.')
        extras = p.get('extras', {})
        consumption = {corn: bultos, 'Químico': bultos * 400, 'Bolsas': sum(q*bags[i] for i,q in enumerate(qty))}
        for item in ['Harina', 'Sal']:
            consumption[item] = number(extras.get(item, 0))
        payload = {'qty': qty, 'bultos': bultos, 'chemicalGrams': bultos*400, 'consumption': consumption}
        rid = record(db, 'production', user['id'], payload)
        for i, q in enumerate(qty):
            if q:
                move(db, rid, PRODUCTS[i], q)
        for item, q in consumption.items():
            if q:
                move(db, rid, item, -q)
        ensure_inventory(db)
    elif action == 'draft':
        operational(user)
        owner = user['id'] if user['role'] == 'rider' else p.get('rider')
        if not db.execute("SELECT id FROM users WHERE id=? AND role='rider'", (owner,)).fetchone():
            raise RuleError('Selecciona un repartidor registrado.')
        payload = {'qty': quantities(p.get('qty'), True)}
        existing = db.execute("SELECT id,payload FROM records WHERE owner=? AND kind='dispatch' AND status='draft'", (owner,)).fetchone()
        version = json.loads(existing['payload']).get('version', 0) if existing else 0
        if p.get('expected', 0) != version:
            raise RuleError('Otro dispositivo cambió este borrador. Actualiza la pantalla antes de editarlo.')
        payload['version'] = version + 1
        if existing:
            rid = existing['id']
            db.execute('UPDATE records SET payload=? WHERE id=?', (json.dumps(payload), rid))
        else:
            rid = record(db, 'dispatch', owner, payload, 'draft')
    elif action == 'confirm':
        operational(user)
        row, payload = get_record(db, p.get('id'), 'dispatch')
        owner_allowed(user, row['owner'])
        if row['status'] != 'draft':
            raise RuleError('Este despacho ya está confirmado.')
        if 'expected' in p and p['expected'] != payload.get('version', 0):
            raise RuleError('El borrador cambió. Actualiza y revisa las cantidades antes de confirmar.')
        if 'quote' in p and p['quote'] != dispatch_quote(db, user, row['id'])['token']:
            raise RuleError('Las cantidades o los precios cambiaron. Abre de nuevo la revisión del despacho.')
        quantities(payload['qty'])
        config = setting(db, 'config:'+row['owner'], setting(db, 'config:default', {}))
        prices, returns = config.get('prices', [0]*8), config.get('returnPrices', [0]*8)
        if any(q and not prices[i] for i,q in enumerate(payload['qty'])):
            raise RuleError('Administración debe configurar los precios antes de confirmar.')
        payload.update(prices=prices, returnPrices=returns, total=sum(q*prices[i] for i,q in enumerate(payload['qty'])))
        rid = row['id']
        db.execute("UPDATE records SET status='confirmed',payload=?,date=? WHERE id=?", (json.dumps(payload), now()[:10], rid))
        for i,q in enumerate(payload['qty']):
            if q:
                move(db, rid, PRODUCTS[i], -q)
        ensure_inventory(db)
    elif action == 'close':
        operational(user)
        if user['role'] == 'dispatcher':
            raise RuleError('El despachador no tiene permiso para liquidar cuentas de ruta.')
        row, dispatch = get_record(db, p.get('id'), 'dispatch')
        owner_allowed(user, row['owner'])
        if row['status'] != 'confirmed':
            raise RuleError('El despacho debe estar confirmado y sin cierre previo.')
        good, bad, changes = [quantities(p.get(k), True) for k in ('good','bad','changes')]
        if any(good[i]+bad[i] > q for i,q in enumerate(dispatch['qty'])):
            raise RuleError('Las devoluciones superan las cantidades despachadas.')
        expense = money(p.get('expenses'))
        reason = text(p.get('expenseReason'), required=bool(expense))
        cash = money(p.get('cash'))
        credits = p.get('credits', [])
        if not isinstance(credits, list) or len(credits) > 50:
            raise RuleError('Lista de fiados inválida.')
        credit_rows = [{'debtor': text(c.get('debtor')), 'amount': money(c.get('amount'))} for c in credits]
        credit_total = sum(c['amount'] for c in credit_rows)
        net = dispatch['total'] - sum(good[i]*dispatch['prices'][i] + bad[i]*dispatch['returnPrices'][i] for i in range(8))
        if expense + credit_total > net:
            raise RuleError('Los fiados y gastos superan el valor de la ruta.')
        due = net - expense - credit_total
        if cash > due:
            raise RuleError('El efectivo supera lo que corresponde entregar.')
        payload = {'dispatchId': row['id'], 'good': good, 'bad': bad, 'changes': changes,
                   'expenses': expense, 'expenseReason': reason, 'cash': cash, 'credits': credit_rows,
                   'net': net, 'due': due, 'balance': due-cash, 'prices': dispatch['prices'], 'returnPrices': dispatch['returnPrices']}
        rid = record(db, 'close', row['owner'], payload, 'pending')
        for i in range(8):
            if good[i] or changes[i]:
                move(db, rid, PRODUCTS[i], good[i]-changes[i])
        ensure_inventory(db)
        for c in credit_rows:
            if c['amount']:
                record(db, 'debt', row['owner'], {**c, 'closeId': rid})
        db.execute("UPDATE records SET status='closed' WHERE id=?", (row['id'],))
    elif action == 'debt':
        admin(user)
        owner = p.get('rider')
        if not db.execute("SELECT id FROM users WHERE id=? AND role='rider'", (owner,)).fetchone():
            raise RuleError('Selecciona el repartidor responsable.')
        payload = {'debtor': text(p.get('debtor')), 'amount': money(p.get('amount')), 'note': text(p.get('note'), False)}
        if not payload['amount']:
            raise RuleError('El fiado debe ser mayor que cero.')
        rid = record(db, 'debt', owner, payload)
    elif action == 'payment':
        admin(user)
        row, debt = get_record(db, p.get('id'), 'debt')
        amount = money(p.get('amount'))
        balance = debt_balance(db, row['id'])
        if not amount or amount > balance:
            raise RuleError('El abono debe ser mayor que cero y no superar el saldo.')
        payload = {'debt_id': row['id'], 'debtor': debt['debtor'], 'amount': amount, 'balance': balance-amount}
        rid = record(db, 'payment', row['owner'], payload)
    elif action == 'expense':
        admin(user)
        payload = {'amount': money(p.get('amount')), 'reason': text(p.get('reason'))}
        if not payload['amount']:
            raise RuleError('El gasto debe ser mayor que cero.')
        rid = record(db, 'expense', user['id'], payload)
    elif action == 'routePayment':
        admin(user)
        row, closing = get_record(db, p.get('id'), 'close')
        amount = money(p.get('amount'))
        balance = route_balance(db, row['id'])
        if not amount or amount > balance:
            raise RuleError('La entrega debe ser mayor que cero y no superar el saldo de ruta.')
        payload = {'close_id': row['id'], 'amount': amount, 'balance': balance-amount}
        rid = record(db, 'routePayment', row['owner'], payload)
    elif action == 'settle':
        admin(user)
        row, payload = get_record(db, p.get('id'), 'close')
        if row['status'] != 'pending':
            raise RuleError('El cierre ya fue revisado.')
        rid = row['id']
        payload['reviewNote'] = text(p.get('reason'))
        db.execute("UPDATE records SET status='reviewed',payload=? WHERE id=?", (json.dumps(payload), rid))
    elif action == 'void':
        admin(user)
        row, original = get_record(db, p.get('id'))
        reason = text(p.get('reason'))
        rid = row['id']
        if row['kind'] == 'dispatch' and row['status'] == 'closed':
            raise RuleError('Primero anula el cierre asociado.')
        if row['kind'] == 'debt' and debt_balance(db, rid) != original['amount']:
            raise RuleError('Primero anula los abonos asociados.')
        if row['kind'] == 'close':
            if route_balance(db, rid) != original['balance']:
                raise RuleError('Primero anula las entregas posteriores del cierre.')
            children = list(db.execute("SELECT * FROM records WHERE kind='debt' AND status!='void' AND json_extract(payload,'$.closeId')=?", (rid,)))
            if any(debt_balance(db, r['id']) != json.loads(r['payload'])['amount'] for r in children):
                raise RuleError('Primero anula los abonos de los fiados del cierre.')
            for r in children:
                db.execute("UPDATE records SET status='void' WHERE id=?", (r['id'],))
                audit(db, user, 'void', r['id'], {'before': json.loads(r['payload']), 'reason': reason, 'closeId': rid})
            db.execute("UPDATE records SET status='confirmed' WHERE id=?", (original['dispatchId'],))
        db.execute("UPDATE records SET status='void' WHERE id=?", (rid,))
        ensure_inventory(db)
        payload = {'before': original, 'after': 'void', 'reason': reason}
    else:
        raise RuleError('Acción desconocida.')
    audit(db, user, action, rid, payload)
    return {'id': rid, 'message': 'Guardado correctamente.', 'detail': payload}


def transact(db, user, action, payload, key):
    text(key, limit=100)
    if not isinstance(payload, dict):
        raise RuleError('Formulario inválido.')
    fingerprint = hashlib.sha256(json.dumps([user['id'] if user else None, action, payload], sort_keys=True).encode()).hexdigest()
    db.execute('BEGIN IMMEDIATE')
    try:
        prior = db.execute('SELECT * FROM requests WHERE key=?', (key,)).fetchone()
        if prior:
            if prior['fingerprint'] != fingerprint:
                raise RuleError('Este envío ya se utilizó. Vuelve a abrir el formulario.')
            result = json.loads(prior['response'])
        else:
            result = apply_action(db, user, action, payload)
            db.execute('INSERT INTO requests VALUES(?,?,?)', (key, fingerprint, json.dumps(result)))
        db.execute('COMMIT')
        return result
    except Exception:
        db.execute('ROLLBACK')
        raise


def state(db, user):
    result = {'products': PRODUCTS, 'inputs': INPUTS, 'today': now()[:10], 'orderDay': delivery_day(),
              'logo': setting(db, 'logo'), 'needsSetup': not db.execute("SELECT id FROM users WHERE role='admin'").fetchone(),
              'user': {k: user[k] for k in ('id','name','role','phone')} if user else None}
    if not user:
        return result
    records = list(db.execute('SELECT * FROM records ORDER BY created DESC, rowid DESC'))
    if user['role'] == 'rider':
        records = [r for r in records if r['owner'] == user['id']]
    elif user['role'] == 'dispatcher':
        records = [r for r in records if r['kind'] in ('order','dispatch','production')]
    result['records'] = [{**dict(r), 'payload': json.loads(r['payload'])} for r in records]
    for r in result['records']:
        if r['kind'] == 'debt' and r['status'] != 'void':
            r['balance'] = debt_balance(db, r['id'])
        if r['kind'] == 'close' and r['status'] != 'void':
            r['balance'] = route_balance(db, r['id'])
    result['stock'] = stock(db) if user['role'] in ('admin','dispatcher') else {}
    result['users'] = [dict(r) for r in db.execute('SELECT id,name,phone,role FROM users')] if user['role'] in ('admin','dispatcher') else []
    result['config'] = setting(db, 'config:default', {}) if user['role'] == 'admin' else {}
    if user['role'] == 'admin':
        result['aiEnabled']=ai_assistant.enabled()
        result['audit'] = [dict(r) for r in db.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 200')]
        result['pricesByRider'] = {r['id']: setting(db, 'config:'+r['id'], {}) for r in result['users'] if r['role']=='rider'}
    return result


class Handler(BaseHTTPRequestHandler):
    server_version = 'ArepasNueva/1'

    def log_message(self, fmt, *args):
        # Never log payloads, cookies, passwords or access tokens.
        print(f'{now()} {self.command} {self.path.split("?")[0]}')

    def respond(self, status, data, cookie=None):
        payload = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(payload)

    def binary(self, content, mime, filename=None, inline=False, ranges=False):
        start, end, status = 0, len(content)-1, 200
        if ranges and self.headers.get('Range'):
            try:
                value=self.headers['Range']
                if not value.startswith('bytes=') or ',' in value:
                    raise ValueError()
                first,last=value[6:].split('-')
                if not first:
                    length=int(last)
                    if length<=0:
                        raise ValueError()
                    start=max(0,len(content)-length)
                else:
                    start=int(first)
                    end=min(int(last) if last else end,end)
                if start<0 or start>end or start>=len(content):
                    raise ValueError()
                status=206
            except (ValueError,TypeError):
                self.send_response(416)
                self.send_header('Content-Range','bytes */'+str(len(content)))
                self.send_header('Content-Length','0')
                self.end_headers()
                return
        self.send_response(status)
        self.send_header('Content-Type',mime)
        self.send_header('Content-Length',str(end-start+1))
        self.send_header('Cache-Control','private, no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        if filename:
            disposition='inline' if inline else 'attachment'
            self.send_header('Content-Disposition',disposition+"; filename*=UTF-8''"+quote(filename))
        if ranges:
            self.send_header('Accept-Ranges','bytes')
        if status==206:
            self.send_header('Content-Range',f'bytes {start}-{end}/{len(content)}')
        self.end_headers()
        self.wfile.write(content[start:end+1])

    def user(self, db):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', ''))
            token = cookie['session'].value if 'session' in cookie else ''
        except Exception:
            return None
        row = db.execute('SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires>?',
                         (hashlib.sha256(token.encode()).hexdigest(), int(time.time()))).fetchone()
        return dict(row) if row else None

    def do_GET(self):
        if self.path == '/healthz':
            try:
                with connect() as db:
                    db.execute('SELECT 1 FROM settings LIMIT 1').fetchone()
                return self.respond(200, {'status': 'ok'})
            except sqlite3.Error:
                return self.respond(503, {'status': 'unavailable'})
        url = urlsplit(self.path)
        path, params = url.path, parse_qs(url.query)
        if path.startswith('/api/'):
            db=None
            user=None
            try:
                db=connect()
                user=self.user(db)
                if path=='/api/state':
                    return self.respond(200,state(db,user))
                if path=='/api/team':
                    data=team.team_state(db,user,params.get('room',['team'])[0],int(params.get('after',[0])[0]),
                                         int(params.get('callAfter',[0])[0]),params.get('call',[None])[0],int(params.get('before',[0])[0]))
                    return self.respond(200,data)
                if path.startswith('/api/file/'):
                    meta,content=team.file_access(db,user,path.removeprefix('/api/file/'),DATA)
                    return self.binary(content,meta['mime'],meta['name'],inline=True,ranges=True)
                if path=='/api/backup':
                    admin(user)
                    from backup import create_archive
                    return self.binary(create_archive(db,DATA,now()),'application/zip','respaldo-mananera-'+now()[:10]+'.zip')
                if path.startswith('/api/pdf/'):
                    from pdf_export import record_pdf
                    rid=path.removeprefix('/api/pdf/')
                    row=db.execute('SELECT * FROM records WHERE id=?',(rid,)).fetchone()
                    if not row:
                        raise RuleError('Registro no encontrado.')
                    owner_allowed(user,row['owner'])
                    if user['role']=='dispatcher' and row['kind'] not in ('dispatch','order','production'):
                        raise RuleError('Este comprobante requiere permiso administrativo.')
                    return self.binary(record_pdf(state(db,user),rid),'application/pdf','mananera-'+rid+'.pdf')
                if path=='/api/report.pdf':
                    admin(user)
                    from pdf_export import report_pdf
                    return self.binary(report_pdf(state(db,user),params.get('date',[''])[0],params.get('rider',[''])[0]),
                                       'application/pdf','informe-mananera-'+now()[:10]+'.pdf')
                return self.respond(404,{'error':'No encontrado.'})
            except (RuleError,team.TeamError,ValueError) as exc:
                return self.respond(400 if user else 403,{'error':str(exc)})
            except ImportError:
                return self.respond(503,{'error':'El servidor necesita instalar los componentes para generar PDF y validar imágenes.'})
            except Exception as exc:
                print('Read failure:',type(exc).__name__)
                return self.respond(503,{'error':'No se pudo cargar. Intenta de nuevo.'})
            finally:
                if db:
                    db.close()
        allowed = {'/': 'index.html', '/index.html': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css',
                   '/manifest.webmanifest': 'manifest.webmanifest', '/sw.js': 'sw.js', '/icon.svg': 'icon.svg',
                   '/domain.js': 'domain.js', '/icon-192.png': 'icon-192.png', '/icon-512.png': 'icon-512.png',
                   '/team-client.js':'team-client.js', '/pdf-client.js':'pdf-client.js'}
        if path not in allowed:
            return self.respond(404, {'error':'No encontrado.'})
        file = ROOT / 'public' / allowed[path]
        if not file.exists():
            return self.respond(404, {'error':'No encontrado.'})
        suffix = file.suffix
        mime = {'.html':'text/html; charset=utf-8', '.js':'text/javascript; charset=utf-8', '.css':'text/css; charset=utf-8',
                '.webmanifest':'application/manifest+json', '.svg':'image/svg+xml', '.png':'image/png'}[suffix]
        content = file.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(content)))
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Cache-Control','no-cache')
        self.send_header('Permissions-Policy','camera=(self), microphone=(self)')
        self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; style-src 'self'; script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):
        db = None
        try:
            expected = public_origin(self.headers)
            if self.headers.get('Origin') != expected:
                return self.respond(403, {'error':'Origen de la solicitud no autorizado.'})
            length = int(self.headers.get('Content-Length', 0))
            limit=18*1024*1024 if self.path=='/api/action/team-file' else 2_100_000
            if length < 2 or length > limit:
                return self.respond(413, {'error':'El archivo o formulario es demasiado grande.'})
            p = json.loads(self.rfile.read(length))
            if not isinstance(p, dict):
                raise RuleError('Formulario inválido.')
            db = connect()
            user = self.user(db)
            if self.path == '/api/ai/preview':
                admin(user)
                if p.get('consent') is not True:
                    raise RuleError('Confirma que quieres enviar el resumen a Gemini.')
                question=text(p.get('question'),limit=1000)
                data=ai_assistant.snapshot(state(db,user))
                answer,model=ai_assistant.generate(question,data)
                document={'actor':user['id'],'question':question,'answer':answer,'model':model,
                          'snapshot':data,'generatedAt':time.time(),'generatedDate':now()[:10],
                          'nonce':secrets.token_hex(16)}
                return self.respond(200,{'document':document,'token':ai_assistant.seal(document,setting(db,'ai:signing'))})
            if self.path in ('/api/login', '/api/setup'):
                db.execute('BEGIN IMMEDIATE')
                ip = self.client_address[0]
                attempts = db.execute('SELECT * FROM login_attempts WHERE ip=?', (ip,)).fetchone()
                if attempts and attempts['failures'] >= 8 and attempts['until'] > time.time():
                    db.execute('ROLLBACK')
                    return self.respond(429, {'error':'Demasiados intentos. Espera 15 minutos.'})
                if self.path == '/api/setup':
                    if ip not in ('127.0.0.1', '::1') or db.execute("SELECT id FROM users WHERE role='admin'").fetchone():
                        raise RuleError('La cuenta inicial ya está creada o debes configurarla desde el equipo local.')
                    code = text(p.get('code'))
                    if len(code) < 12:
                        raise RuleError('Usa una contraseña de al menos 12 caracteres para Administración.')
                    uid = secrets.token_hex(12)
                    db.execute('INSERT INTO users VALUES(?,?,?,?,?)', (uid, text(p.get('name')), 'admin', 'admin', password_hash(code)))
                    team.join_team(db)
                    user = dict(db.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone())
                    audit(db, user, 'setup', uid, {'name': user['name']})
                else:
                    row = db.execute('SELECT * FROM users WHERE phone=?', (text(p.get('phone')),)).fetchone()
                    valid=password_valid(text(p.get('code')),row['password'] if row else password_hash('invalid-placeholder'))
                    if not row or not valid:
                        failures=attempts['failures']+1 if attempts and attempts['until']>time.time() else 1
                        db.execute('INSERT INTO login_attempts VALUES(?,?,?) ON CONFLICT(ip) DO UPDATE SET failures=excluded.failures,until=excluded.until', (ip,failures,int(time.time())+900))
                        db.execute('COMMIT')
                        return self.respond(401, {'error':'Celular o código incorrecto.'})
                    user = dict(row)
                db.execute('DELETE FROM login_attempts WHERE ip=?', (ip,))
                token = secrets.token_urlsafe(32)
                db.execute('DELETE FROM sessions WHERE expires<?', (int(time.time()),))
                db.execute('INSERT INTO sessions VALUES(?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), user['id'], int(time.time())+43200))
                db.execute('COMMIT')
                secure = '; Secure' if expected.startswith('https:') else ''
                return self.respond(200, {'message':'Sesión iniciada.'}, 'session='+token+'; Path=/; HttpOnly; SameSite=Strict; Max-Age=43200'+secure)
            if self.path == '/api/logout':
                if user:
                    db.execute('DELETE FROM sessions WHERE user_id=?', (user['id'],))
                return self.respond(200, {'message':'Sesión cerrada.'}, 'session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0')
            if not self.path.startswith('/api/action/'):
                return self.respond(404, {'error':'No encontrado.'})
            action = self.path.removeprefix('/api/action/')
            return self.respond(200, transact(db, user, action, p.get('payload', {}), p.get('key')))
        except (RuleError,team.TeamError,ai_assistant.AIError) as exc:
            if db and db.in_transaction:
                db.execute('ROLLBACK')
            self.respond(400, {'error':str(exc)})
        except (ValueError, TypeError, KeyError):
            if db and db.in_transaction:
                db.execute('ROLLBACK')
            self.respond(400, {'error':'Revisa los datos enviados.'})
        except sqlite3.IntegrityError:
            if db and db.in_transaction:
                db.execute('ROLLBACK')
            self.respond(409, {'error':'Este celular o envío ya está registrado.'})
        except Exception as exc:
            if db and db.in_transaction:
                db.execute('ROLLBACK')
            print('Server failure:', type(exc).__name__)
            self.respond(503, {'error':'No se pudo guardar. Tus datos del formulario siguen disponibles; intenta de nuevo.'})
        finally:
            if db:
                db.close()


if __name__ == '__main__':
    initialize()
    bootstrap_admin()
    host = os.environ.get('AREPAS_HOST', '0.0.0.0' if os.environ.get('RENDER_EXTERNAL_URL') else '127.0.0.1')
    port = int(os.environ.get('PORT') or os.environ.get('AREPAS_PORT', '8787'))
    print(f'Arepas La Mañanera nueva: http://{host}:{port}')
    ThreadingHTTPServer((host, port), Handler).serve_forever()
