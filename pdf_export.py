"""Native PDF receipts, with the exact configured logo on every content page."""
import base64
import io
from decimal import Decimal
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

LABELS={'order':'Pedido','dispatch':'Comprobante de despacho','close':'Cierre y liquidación de ruta',
        'production':'Producción','input':'Entrada de insumos','debt':'Estado de cuenta',
        'payment':'Recibo de abono','expense':'Gasto','routePayment':'Recibo de entrega de saldo de ruta'}
STATUS={'draft':'BORRADOR','confirmed':'CONFIRMADO','closed':'RUTA CERRADA','pending':'PENDIENTE DE REVISIÓN','reviewed':'REVISADO','void':'ANULADO'}
RED=colors.HexColor('#a92323')


def pesos(n):
    return '$ '+format(int(n or 0),',').replace(',','.')


def decimal(n):
    return format(Decimal(str(n)).quantize(Decimal('.001')),'f').rstrip('0').rstrip('.') or '0'


def build_pdf(state,title,items):
    stream=io.BytesIO()
    width,height=A5
    styles=getSampleStyleSheet()
    normal=ParagraphStyle('BodyLarge',parent=styles['BodyText'],fontName='Helvetica',fontSize=12,leading=17,spaceAfter=9)
    heading=ParagraphStyle('SectionLarge',parent=normal,fontName='Helvetica-Bold',fontSize=14,leading=19,spaceBefore=14)
    small=ParagraphStyle('TableReadable',parent=normal,fontSize=11,leading=15,spaceAfter=0)
    right=ParagraphStyle('Amount',parent=small,alignment=TA_RIGHT)
    body=[]
    usable=width-48
    def paragraph(value,style=normal):
        return Paragraph(escape(str(value)).replace('\n','<br/>'),style)
    for item in items:
        kind=item[0]
        if kind=='heading':
            body.append(paragraph(item[1],heading))
        elif kind=='text':
            body.append(paragraph(item[1]))
        elif kind=='summary':
            table=Table([[paragraph(item[1],small),paragraph(item[2],right)]],colWidths=[usable*.58,usable*.42])
            table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#f3f5ef')),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10),('LINEBELOW',(0,0),(-1,-1),.5,colors.HexColor('#dde1dc'))]))
            body.extend([table,Spacer(1,8)])
        elif kind=='table':
            rows=item[1]
            ratios=item[2]
            table=Table([[paragraph(v,small) for v in row] for row in rows],colWidths=[usable*r for r in ratios],repeatRows=1,hAlign='LEFT')
            table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#ffe681')),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),('LINEBELOW',(0,0),(-1,-1),.5,colors.HexColor('#dde1dc'))]))
            body.extend([table,Spacer(1,12)])
    logo=None
    if state.get('logo'):
        logo=ImageReader(io.BytesIO(base64.b64decode(state['logo'].split(',',1)[1])))
    def page_header(canvas,doc):
        canvas.saveState()
        if logo:
            canvas.drawImage(logo,width-100,height-79,width=76,height=57,preserveAspectRatio=True,anchor='c',mask='auto')
        canvas.setFillColor(RED)
        canvas.setFont('Helvetica-Bold',14)
        canvas.drawString(24,height-32,'Arepas La Mañanera')
        canvas.setFillColor(colors.black)
        canvas.setFont('Helvetica',10)
        canvas.drawString(24,height-49,state['today']+' · Hora de Colombia')
        canvas.setStrokeColor(RED)
        canvas.line(24,height-88,width-24,height-88)
        canvas.setFont('Helvetica',10)
        canvas.setFillColor(colors.HexColor('#636a61'))
        canvas.drawString(24,18,'Arepas La Mañanera')
        canvas.drawRightString(width-24,18,'Página '+str(doc.page))
        canvas.restoreState()
    doc=SimpleDocTemplate(stream,pagesize=A5,rightMargin=24,leftMargin=24,topMargin=103,bottomMargin=37,
                          title=title,author='Arepas La Mañanera')
    doc.build([paragraph(title,heading),Spacer(1,10)]+body,onFirstPage=page_header,onLaterPages=page_header)
    return stream.getvalue()


def record_pdf(state,rid):
    row=next((r for r in state.get('records',[]) if r['id']==rid),None)
    if not row:
        raise ValueError('No tienes acceso a este comprobante.')
    p=row['payload']
    names={u['id']:u['name'] for u in state.get('users',[])}
    if state.get('user'):
        names[state['user']['id']]=state['user']['name']
    owner=p.get('name') or names.get(row['owner'],'Repartidor')
    title=LABELS.get(row['kind'],'Comprobante')
    items=[('text','Fecha: '+row['date']),('text','Responsable: '+owner),('text','Estado: '+STATUS[row['status']])]
    if row['kind']=='aiReport':
        title='Informe con Gemini'
        items.extend([('text','Generado: '+p['generatedDate']),('text','Modelo: '+p['model']),
                      ('text','Consulta: '+p['question']),('heading','Resumen para revisión')])
        items.extend(('text',line) for line in p['answer'].split('\n') if line.strip())
        items.extend([('heading','Datos del servidor usados para el informe'),
                      ('text','Período: '+p['snapshot']['periodo'])])
        for label in ('ventas_liquidadas','gastos_de_ruta','saldo_rutas_por_entregar','fiados_por_cobrar','otros_gastos'):
            items.append(('summary',label.replace('_',' ').capitalize(),pesos(p['snapshot'][label])))
        items.append(('text','Las recomendaciones de Gemini requieren revisión; no modifican cuentas ni inventario.'))
    if p.get('qty') and isinstance(p['qty'],list):
        rows=[['Referencia','Cantidad','Precio','Subtotal']] if p.get('prices') else [['Referencia','Cantidad']]
        for i,name in enumerate(state['products']):
            if p['qty'][i]:
                values=[name,str(p['qty'][i])]
                if p.get('prices'):
                    values.extend([pesos(p['prices'][i]),pesos(p['qty'][i]*p['prices'][i])])
                rows.append(values)
        items.append(('table',rows,[.4,.13,.23,.24] if p.get('prices') else [.73,.27]))
    if row['kind']=='close':
        items.append(('heading','Regreso de ruta'))
        rows=[['Referencia','Buenos','Malos','Cambios']]
        rows.extend([[name,str(p['good'][i]),str(p['bad'][i]),str(p['changes'][i])] for i,name in enumerate(state['products']) if p['good'][i] or p['bad'][i] or p['changes'][i]])
        items.append(('table',rows,[.46,.18,.18,.18]))
        good_credit=sum(p['good'][i]*p['prices'][i] for i in range(8))
        bad_credit=sum(p['bad'][i]*p['returnPrices'][i] for i in range(8))
        dispatch=next((r for r in state['records'] if r['id']==p['dispatchId']),None)
        if dispatch:
            items.append(('summary','Subtotal despachado',pesos(dispatch['payload']['total'])))
        items.extend([('summary','Sobrantes buenos',pesos(good_credit)),('summary','Devoluciones malas',pesos(bad_credit))])
        for credit in p['credits']:
            items.append(('text','Fiado de '+credit['debtor']+': '+pesos(credit['amount'])))
        items.append(('summary','Total fiado en ruta',pesos(sum(c['amount'] for c in p['credits']))))
    for key,label in [('total','Subtotal despachado'),('net','Venta liquidada'),('expenses','Gastos de ruta'),('cash','Efectivo entregado'),('due','Corresponde entregar'),('amount','Valor del movimiento'),('cost','Costo total')]:
        if key in p:
            items.append(('summary',label,pesos(p[key])))
    if row['kind']=='debt':
        items.append(('heading','Abonos registrados'))
        payments=[r for r in state['records'] if r['kind']=='payment' and r['status']!='void' and r['payload']['debt_id']==rid]
        rows=[['Fecha','Abono','Saldo tras abono']]+[[r['date'],pesos(r['payload']['amount']),pesos(r['payload']['balance'])] for r in reversed(payments)]
        items.append(('table',rows,[.35,.3,.35]))
        if row['status']!='void':
            items.append(('summary','Saldo pendiente actual',pesos(row['balance'])))
    elif row['kind']=='close' and row['status']!='void':
        items.append(('summary','Saldo al cerrar',pesos(p['balance'])))
        payments=[r for r in state['records'] if r['kind']=='routePayment' and r['status']!='void' and r['payload']['close_id']==rid]
        if payments:
            items.append(('heading','Entregas posteriores'))
            items.append(('table',[['Fecha','Entregado']]+[[r['date'],pesos(r['payload']['amount'])] for r in reversed(payments)],[.5,.5]))
        items.append(('summary','Saldo pendiente actual',pesos(row['balance'])))
    elif 'balance' in p:
        items.append(('summary','Saldo después del movimiento',pesos(p['balance'])))
    if row['kind']=='production':
        items.append(('text','Maíz utilizado: '+decimal(p['bultos'])+' bultos.'))
        items.append(('text','Químico: '+decimal(p['bultos'])+' × 400 g = '+decimal(p['chemicalGrams'])+' g.'))
        items.append(('table',[['Insumo','Consumido']]+[[name,decimal(value)] for name,value in p['consumption'].items()],[.6,.4]))
    if row['kind']=='input':
        items.append(('text',p['item']+': '+decimal(p['qty'])+' '+p['unit']))
    for key,label in [('debtor','Deudor'),('reason','Concepto'),('expenseReason','Gasto de ruta'),('note','Detalle'),('reviewNote','Revisión')]:
        if p.get(key):
            items.append(('text',label+': '+p[key]))
    items.extend([('text','Registro: '+rid),('text','Guardado: '+row['created'])])
    return build_pdf(state,title,items)


def report_pdf(state,date='',rider=''):
    records=[r for r in state['records'] if r['status']!='void' and (not date or r['date']==date) and (not rider or r['owner']==rider)]
    def rows(kind):return [r for r in records if r['kind']==kind]
    closures=rows('close')
    amounts=[('Valor despachado',sum(r['payload']['total'] for r in rows('dispatch') if r['status']!='draft')),
             ('Ventas de rutas cerradas',sum(r['payload']['net'] for r in closures)),
             ('Fiados de rutas cerradas',sum(sum(c['amount'] for c in r['payload']['credits']) for r in closures)),
             ('Gastos de ruta',sum(r['payload']['expenses'] for r in closures)),
             ('Efectivo al cerrar',sum(r['payload']['cash'] for r in closures)),
             ('Saldo actual de las rutas',sum(r['balance'] for r in closures)),
             ('Entregas posteriores de ruta',sum(r['payload']['amount'] for r in rows('routePayment'))),
             ('Abonos a fiados',sum(r['payload']['amount'] for r in rows('payment'))),
             ('Otros gastos',sum(r['payload']['amount'] for r in rows('expense')))]
    name=next((u['name'] for u in state.get('users',[]) if u['id']==rider),'Todos')
    items=[('text','Fecha: '+(date or 'Todas')),('text','Repartidor: '+name),
           ('text','El valor despachado incluye rutas abiertas. Las ventas se calculan al cerrar cada ruta.')]
    items.extend(('summary',label,pesos(value)) for label,value in amounts)
    items.append(('heading','Devoluciones e inventario'))
    inventory=[['Referencia','Buenos','Malos','Disponible']]
    inventory.extend([[name,str(sum(r['payload']['good'][i] for r in closures)),str(sum(r['payload']['bad'][i] for r in closures)),decimal(state['stock'].get(name,0))] for i,name in enumerate(state['products'])])
    items.append(('table',inventory,[.46,.18,.18,.18]))
    items.append(('text','Disponible corresponde al inventario actual de toda la fábrica; no es un inventario histórico del día filtrado.'))
    return build_pdf(state,'Informe de movimientos',items)
