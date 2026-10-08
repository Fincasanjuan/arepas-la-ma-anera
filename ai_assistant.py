"""Optional Gemini summaries. No tools, commercial writes or credentials in responses."""
import hashlib
import hmac
import json
import os
import re
import time
from urllib import request, error


class AIError(Exception):
    pass


def enabled():
    return bool(os.environ.get('GEMINI_API_KEY', '').strip())


def snapshot(state):
    records=[r for r in state['records'] if r['status']!='void']
    closes=[r for r in records if r['kind']=='close']
    debts=[r for r in records if r['kind']=='debt']
    return {'fecha_colombia':state['today'], 'periodo':'Movimientos vigentes acumulados; saldos actuales',
            'inventario':state['stock'], 'cierres_de_ruta':len(closes),
            'ventas_liquidadas':sum(r['payload']['net'] for r in closes),
            'gastos_de_ruta':sum(r['payload']['expenses'] for r in closes),
            'saldo_rutas_por_entregar':sum(r['balance'] for r in closes),
            'fiados_por_cobrar':sum(r['balance'] for r in debts),
            'fiados_con_saldo':sum(r['balance']>0 for r in debts),
            'otros_gastos':sum(r['payload']['amount'] for r in records if r['kind']=='expense')}


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def generate(question, data):
    key=os.environ.get('GEMINI_API_KEY','').strip()
    if not key:
        raise AIError('Gemini aún no está conectado. Configura su clave en el servidor.')
    model=os.environ.get('GEMINI_MODEL','gemini-2.5-flash')
    if not re.fullmatch(r'[a-zA-Z0-9._-]{1,100}',model):
        raise AIError('Revisa el nombre del modelo Gemini configurado.')
    body={'systemInstruction':{'parts':[{'text':
          'Eres el asistente de Arepas La Mañanera. Responde en español sencillo. '
          'Usa solo los datos proporcionados; no inventes ventas, clientes ni pronósticos. '
          'Distingue saldo de ruta y fiados; no los cuentes como efectivo recibido. '
          'No tienes herramientas ni permiso para modificar cuentas o inventario. '
          'Los valores provienen del servidor. Si no hay datos suficientes, dilo. '
          'Da un resumen breve y recomendaciones para revisión humana.'}]},
          'contents':[{'role':'user','parts':[{'text':json.dumps({'consulta':question,'datos':data},ensure_ascii=False)}]}],
          'generationConfig':{'temperature':0.2,'maxOutputTokens':1600}}
    req=request.Request('https://generativelanguage.googleapis.com/v1beta/models/'+model+':generateContent',
                        data=json.dumps(body).encode(),headers={'Content-Type':'application/json','x-goog-api-key':key},method='POST')
    try:
        with request.build_opener(NoRedirect()).open(req,timeout=25) as response:
            raw=response.read(512001)
        if len(raw)>512000:
            raise AIError('La respuesta es demasiado larga. Intenta una consulta más breve.')
        result=json.loads(raw)
        candidate=result.get('candidates',[])[0]
        if candidate.get('finishReason') not in (None,'STOP'):
            raise AIError('Gemini no completó el informe. Intenta una consulta más breve.')
        answer='\n'.join(p['text'] for p in candidate.get('content',{}).get('parts',[]) if p.get('text') and not p.get('thought'))
        if not answer.strip() or len(answer)>16000:
            raise AIError('Gemini no entregó un informe válido. Intenta nuevamente.')
        return answer.strip(),model
    except error.HTTPError as exc:
        messages={429:'Gemini alcanzó su límite de uso. Intenta después; revisa la cuota de tu cuenta.',
                  401:'La clave de Gemini no es válida.',403:'Gemini rechazó el acceso. Revisa la clave y los permisos.',
                  404:'El modelo Gemini configurado no está disponible. Revisa GEMINI_MODEL.'}
        raise AIError(messages.get(exc.code,'Gemini no pudo generar el informe. Intenta después.')) from None
    except (error.URLError,TimeoutError,OSError):
        raise AIError('No se pudo conectar con Gemini. No se modificó ninguna cuenta ni inventario.') from None
    except (ValueError,IndexError,KeyError,TypeError):
        raise AIError('Gemini no entregó un informe válido. Intenta nuevamente.') from None


def seal(document, secret):
    return hmac.new(secret.encode(),json.dumps(document,sort_keys=True,ensure_ascii=False).encode(),hashlib.sha256).hexdigest()


def verify(preview, secret, actor):
    if not isinstance(preview,dict) or not isinstance(preview.get('document'),dict) or not isinstance(preview.get('token'),str):
        raise AIError('Informe inválido. Genera una nueva revisión.')
    document=preview['document']
    if not hmac.compare_digest(seal(document,secret),preview['token']) or document.get('actor')!=actor:
        raise AIError('El informe cambió. Genera una nueva revisión antes de guardar.')
    generated=document.get('generatedAt',0)
    if not isinstance(generated,(int,float)) or not 0<=time.time()-generated<=3600:
        raise AIError('La revisión del informe venció. Genera un informe actualizado.')
    return document
