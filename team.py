"""Team communication. No business records or inventory changes happen here."""
import base64
import hashlib
import hmac
import io
import json
import os
import secrets
import time
from pathlib import Path

MAX_FILE_BYTES = 12 * 1024 * 1024
STICKERS = ['👍', '✅', '👋', '🙏', '💪', '😊', '❤️', '🚚']


class TeamError(ValueError):
    pass


def initialize(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS chat_rooms(id TEXT PRIMARY KEY, title TEXT NOT NULL,
      fingerprint TEXT UNIQUE NOT NULL, created TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS chat_members(room_id TEXT REFERENCES chat_rooms(id),
      user_id TEXT REFERENCES users(id), PRIMARY KEY(room_id,user_id));
    CREATE TABLE IF NOT EXISTS chat_files(id TEXT PRIMARY KEY, room_id TEXT REFERENCES chat_rooms(id),
      uploader TEXT REFERENCES users(id), name TEXT NOT NULL, mime TEXT NOT NULL, path TEXT NOT NULL,
      size INTEGER NOT NULL, created TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS chat_messages(seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE,
      room_id TEXT REFERENCES chat_rooms(id), sender TEXT REFERENCES users(id), content TEXT NOT NULL,
      sticker TEXT, file_id TEXT REFERENCES chat_files(id), created TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS idx_chat_messages_room_seq ON chat_messages(room_id,seq);
    CREATE TABLE IF NOT EXISTS team_calls(id TEXT PRIMARY KEY, room_id TEXT REFERENCES chat_rooms(id),
      caller TEXT REFERENCES users(id), kind TEXT NOT NULL, status TEXT NOT NULL, created TEXT NOT NULL, expires INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS call_members(call_id TEXT REFERENCES team_calls(id), user_id TEXT REFERENCES users(id),
      status TEXT NOT NULL, seen INTEGER NOT NULL, PRIMARY KEY(call_id,user_id));
    CREATE TABLE IF NOT EXISTS call_signals(seq INTEGER PRIMARY KEY AUTOINCREMENT, call_id TEXT REFERENCES team_calls(id),
      sender TEXT REFERENCES users(id), receiver TEXT REFERENCES users(id), kind TEXT NOT NULL, payload TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS idx_call_signals_receiver ON call_signals(call_id,receiver,seq);
    ''')
    db.execute("INSERT OR IGNORE INTO chat_rooms VALUES('team','Equipo La Mañanera','team','')")
    join_team(db)


def join_team(db):
    db.execute("INSERT OR IGNORE INTO chat_members SELECT 'team',id FROM users")


def require_member(db, user, room_id):
    if not user or not db.execute('SELECT 1 FROM chat_members WHERE room_id=? AND user_id=?',
                                  (room_id, user['id'])).fetchone():
        raise TeamError('Ingresa con tu código para acceder a esta conversación.')


def clean_calls(db):
    current = int(time.time())
    db.execute("UPDATE call_members SET status='left' WHERE status='joined' AND seen<?", (current-90,))
    db.execute("UPDATE team_calls SET status='ended' WHERE status!='ended' AND (expires<? "
               "OR NOT EXISTS (SELECT 1 FROM call_members m WHERE m.call_id=team_calls.id AND m.status='joined'))", (current,))
    # SDP and ICE candidates are ephemeral. Expired signals must not grow indefinitely.
    db.execute("DELETE FROM call_signals WHERE call_id IN (SELECT id FROM team_calls WHERE status='ended')")


def ice_servers(user):
    # Optional coturn shared-secret credentials expire after an hour; the secret stays server-side.
    servers = json.loads(os.environ.get('AREPAS_ICE_SERVERS', '[]'))
    if not isinstance(servers, list):
        raise TeamError('La configuración de llamadas no es válida.')
    urls = json.loads(os.environ.get('AREPAS_TURN_URLS', '[]'))
    secret = os.environ.get('AREPAS_TURN_SECRET')
    if urls and secret:
        username = str(int(time.time())+3600)+':'+user['id']
        credential = base64.b64encode(hmac.new(secret.encode(), username.encode(), hashlib.sha1).digest()).decode()
        servers.append({'urls': urls, 'username': username, 'credential': credential})
    return servers


def team_state(db, user, room_id='team', after=0, call_after=0, call_id=None, before=0):
    if not user:
        raise TeamError('Ingresa para abrir el chat del equipo.')
    join_team(db)
    require_member(db, user, room_id)
    clean_calls(db)
    rooms = [dict(r) for r in db.execute(
        'SELECT r.* FROM chat_rooms r JOIN chat_members m ON r.id=m.room_id WHERE m.user_id=? ORDER BY r.created,r.id', (user['id'],))]
    for room in rooms:
        room['members'] = [dict(r) for r in db.execute(
            'SELECT u.id,u.name FROM users u JOIN chat_members m ON m.user_id=u.id WHERE m.room_id=? ORDER BY u.name', (room['id'],))]
    if before:
        message_rows=list(reversed(list(db.execute('SELECT * FROM chat_messages WHERE room_id=? AND seq<? ORDER BY seq DESC LIMIT 100',(room_id,before)))))
    elif after:
        message_rows = list(db.execute('SELECT * FROM chat_messages WHERE room_id=? AND seq>? ORDER BY seq LIMIT 100', (room_id, after)))
    else:
        message_rows = list(reversed(list(db.execute('SELECT * FROM chat_messages WHERE room_id=? ORDER BY seq DESC LIMIT 100', (room_id,)))))
    messages = []
    names = {r['id']:r['name'] for r in db.execute('SELECT id,name FROM users')}
    for row in message_rows:
        msg = dict(row)
        msg['name'] = names.get(row['sender'], 'Miembro del equipo')
        msg['file'] = dict(db.execute('SELECT id,name,mime,size FROM chat_files WHERE id=?', (row['file_id'],)).fetchone()) if row['file_id'] else None
        messages.append(msg)
    calls = [dict(r) for r in db.execute(
        "SELECT c.* FROM team_calls c JOIN call_members m ON m.call_id=c.id WHERE m.user_id=? AND c.status!='ended' ORDER BY c.created", (user['id'],))]
    for call in calls:
        call['callerName'] = names.get(call['caller'], 'Miembro del equipo')
        call['members'] = [{**dict(r), 'name':names.get(r['user_id'], 'Miembro del equipo')} for r in db.execute(
            'SELECT user_id,status FROM call_members WHERE call_id=?', (call['id'],))]
    signals = []
    if call_id:
        if not db.execute('SELECT 1 FROM call_members WHERE call_id=? AND user_id=?', (call_id,user['id'])).fetchone():
            raise TeamError('No perteneces a esta llamada.')
        signals = [{**dict(r), 'payload':json.loads(r['payload'])} for r in db.execute(
            'SELECT * FROM call_signals WHERE call_id=? AND receiver=? AND seq>? ORDER BY seq LIMIT 200', (call_id,user['id'],call_after))]
    return {'rooms':rooms, 'messages':messages, 'calls':calls, 'signals':signals,
            'people':[{'id':uid,'name':name} for uid,name in names.items()], 'stickers':STICKERS,
            'iceServers':ice_servers(user)}


def check_file(mime, raw):
    extensions = {'image/jpeg':'.jpg','image/png':'.png','image/webp':'.webp',
                  'audio/mpeg':'.mp3','audio/wav':'.wav','audio/ogg':'.ogg','audio/webm':'.webm',
                  'video/webm':'.webm','video/mp4':'.mp4','audio/mp4':'.m4a'}
    if mime not in extensions or not raw or len(raw)>MAX_FILE_BYTES:
        raise TeamError('Usa una foto, audio o video de hasta 12 MB.')
    if mime.startswith('image/'):
        from PIL import Image
        try:
            image = Image.open(io.BytesIO(raw))
            expected = {'image/jpeg':'JPEG','image/png':'PNG','image/webp':'WEBP'}[mime]
            if image.format != expected or image.width*image.height>20_000_000:
                raise ValueError()
            image.verify()
        except Exception:
            raise TeamError('La imagen no es válida o es demasiado grande.')
    elif mime.endswith('/webm'):
        if not raw.startswith(b'\x1aE\xdf\xa3'):
            raise TeamError('Archivo WebM inválido.')
    elif mime.endswith('/mp4'):
        if len(raw)<12 or raw[4:8]!=b'ftyp':
            raise TeamError('Archivo MP4 inválido.')
    elif mime=='audio/ogg':
        if not raw.startswith(b'OggS'):
            raise TeamError('Archivo OGG inválido.')
    elif mime=='audio/wav':
        if not raw.startswith(b'RIFF') or raw[8:12]!=b'WAVE':
            raise TeamError('Archivo WAV inválido.')
    elif mime=='audio/mpeg':
        if not raw.startswith(b'ID3') and not (len(raw)>=2 and raw[0]==255 and raw[1]&224==224):
            raise TeamError('Archivo MP3 inválido.')
    return extensions[mime]


def action(db, user, name, payload, stamp, data_dir):
    if not user:
        raise TeamError('Ingresa para comunicarte con el equipo.')
    join_team(db)
    if not isinstance(payload, dict):
        raise TeamError('Solicitud inválida.')
    room_id = payload.get('room', 'team')
    require_member(db, user, room_id)
    clean_calls(db)
    result = {}
    if name=='team-room':
        selected = payload.get('members', [])
        if not isinstance(selected,list) or not selected or len(selected)>63 or any(not isinstance(v,str) for v in selected):
            raise TeamError('Selecciona las personas de la conversación.')
        members = sorted(set(selected+[user['id']]))
        if any(not db.execute('SELECT 1 FROM users WHERE id=?', (uid,)).fetchone() for uid in members):
            raise TeamError('Una de las personas no está registrada.')
        if len(members)<2:
            raise TeamError('Selecciona al menos otra persona.')
        fingerprint = hashlib.sha256(json.dumps(members).encode()).hexdigest()
        prior = db.execute('SELECT id FROM chat_rooms WHERE fingerprint=?',(fingerprint,)).fetchone()
        if prior:
            return {'id':prior['id'],'message':'Conversación abierta.'}
        title = str(payload.get('title','')).strip()[:100]
        if not title:
            title = ', '.join(db.execute('SELECT name FROM users WHERE id=?',(uid,)).fetchone()['name'] for uid in members)[:100]
        rid = secrets.token_hex(12)
        db.execute('INSERT INTO chat_rooms VALUES(?,?,?,?)', (rid,title,fingerprint,stamp))
        db.executemany('INSERT INTO chat_members VALUES(?,?)', [(rid,uid) for uid in members])
    elif name=='team-file':
        mime = str(payload.get('mime','')).split(';')[0].lower()
        try:
            encoded = payload.get('data','')
            if not isinstance(encoded,str) or len(encoded)>MAX_FILE_BYTES*4//3+10:
                raise ValueError()
            raw = base64.b64decode(encoded,validate=True)
        except (ValueError,TypeError):
            raise TeamError('El archivo no se pudo leer.')
        extension = check_file(mime,raw)
        rid = secrets.token_hex(16)
        filename = Path(str(payload.get('name','archivo'))).name[:150].replace('\r','').replace('\n','') or 'archivo'+extension
        directory = Path(data_dir)/'attachments'
        directory.mkdir(parents=True,exist_ok=True)
        (directory/(rid+extension)).write_bytes(raw)
        db.execute('INSERT INTO chat_files VALUES(?,?,?,?,?,?,?,?)', (rid,room_id,user['id'],filename,mime,rid+extension,len(raw),stamp))
        result = {'file':{'id':rid,'name':filename,'mime':mime,'size':len(raw)}}
    elif name=='team-message':
        content, sticker, fid = payload.get('text',''),payload.get('sticker'),payload.get('file')
        if not isinstance(content,str) or len(content)>4000 or sticker and sticker not in STICKERS:
            raise TeamError('El mensaje es demasiado largo o el sticker no es válido.')
        if fid and not db.execute('SELECT 1 FROM chat_files WHERE id=? AND room_id=? AND uploader=?', (fid,room_id,user['id'])).fetchone():
            raise TeamError('El archivo no pertenece a este mensaje.')
        content = content.strip()
        if not content and not sticker and not fid:
            raise TeamError('Escribe un mensaje o adjunta un archivo.')
        rid = secrets.token_hex(12)
        db.execute('INSERT INTO chat_messages(id,room_id,sender,content,sticker,file_id,created) VALUES(?,?,?,?,?,?,?)', (rid,room_id,user['id'],content,sticker,fid,stamp))
    elif name=='team-call':
        kind=payload.get('kind')
        if kind not in ('audio','video'):
            raise TeamError('Tipo de llamada inválido.')
        members=[r['user_id'] for r in db.execute('SELECT user_id FROM chat_members WHERE room_id=?',(room_id,))]
        if not 2<=len(members)<=8:
            raise TeamError('Las llamadas permiten entre 2 y 8 personas. Crea una conversación con ese grupo.')
        if db.execute("SELECT 1 FROM team_calls WHERE room_id=? AND status!='ended'",(room_id,)).fetchone():
            raise TeamError('Esta conversación ya tiene una llamada. Puedes unirte a ella.')
        if db.execute("SELECT 1 FROM call_members m JOIN team_calls c ON c.id=m.call_id WHERE m.user_id=? AND m.status='joined' AND c.status!='ended'",(user['id'],)).fetchone():
            raise TeamError('Primero termina tu llamada actual.')
        rid=secrets.token_hex(12)
        current=int(time.time())
        db.execute('INSERT INTO team_calls VALUES(?,?,?,?,?,?,?)',(rid,room_id,user['id'],kind,'ringing',stamp,current+90))
        db.executemany('INSERT INTO call_members VALUES(?,?,?,?)',[(rid,uid,'joined' if uid==user['id'] else 'invited',current) for uid in members])
    elif name in ('team-join','team-leave','team-reject','team-heartbeat','team-signal'):
        rid=payload.get('id')
        call=db.execute("SELECT * FROM team_calls WHERE id=? AND status!='ended'",(rid,)).fetchone()
        membership=db.execute('SELECT * FROM call_members WHERE call_id=? AND user_id=?',(rid,user['id'])).fetchone()
        if not call or not membership:
            raise TeamError('La llamada ya terminó o no tienes acceso.')
        require_member(db,user,call['room_id'])
        current=int(time.time())
        if name=='team-join':
            if membership['status'] not in ('invited','joined'):
                raise TeamError('La invitación ya fue cerrada.')
            if db.execute("SELECT 1 FROM call_members m JOIN team_calls c ON c.id=m.call_id WHERE m.user_id=? AND m.call_id!=? AND m.status='joined' AND c.status!='ended'",(user['id'],rid)).fetchone():
                raise TeamError('Primero termina tu llamada actual.')
            db.execute("UPDATE call_members SET status='joined',seen=? WHERE call_id=? AND user_id=?",(current,rid,user['id']))
            db.execute("UPDATE team_calls SET status='active',expires=? WHERE id=?",(current+90,rid))
        elif name in ('team-leave','team-reject'):
            status='left' if name=='team-leave' else 'rejected'
            db.execute('UPDATE call_members SET status=? WHERE call_id=? AND user_id=?',(status,rid,user['id']))
            clean_calls(db)
        else:
            if membership['status']!='joined':
                raise TeamError('Únete a la llamada antes de enviar datos.')
            db.execute('UPDATE call_members SET seen=? WHERE call_id=? AND user_id=?',(current,rid,user['id']))
            db.execute('UPDATE team_calls SET expires=? WHERE id=?',(current+90,rid))
            if name=='team-signal':
                receiver=payload.get('to')
                target=db.execute("SELECT 1 FROM call_members WHERE call_id=? AND user_id=? AND status='joined'",(rid,receiver)).fetchone()
                if not target or receiver==user['id']:
                    raise TeamError('La otra persona no está en la llamada.')
                kind=payload.get('kind');signal=payload.get('signal')
                if kind not in ('offer','answer','ice') or not isinstance(signal,dict) or len(json.dumps(signal))>40000:
                    raise TeamError('Datos de llamada inválidos.')
                db.execute('INSERT INTO call_signals(call_id,sender,receiver,kind,payload) VALUES(?,?,?,?,?)',(rid,user['id'],receiver,kind,json.dumps(signal)))
    else:
        raise TeamError('Acción de comunicación desconocida.')
    return {'id':rid,'message':'Enviado correctamente.',**result}


def file_access(db,user,fid,data_dir):
    row=db.execute('SELECT * FROM chat_files WHERE id=?',(fid,)).fetchone()
    if not row:
        raise TeamError('Archivo no encontrado.')
    require_member(db,user,row['room_id'])
    path=Path(data_dir)/'attachments'/row['path']
    if not path.is_file():
        raise TeamError('El archivo no está disponible. Revisa el respaldo del servidor.')
    return dict(row),path.read_bytes()
