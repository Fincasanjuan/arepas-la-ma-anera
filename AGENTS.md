# Proyecto nuevo de Arepas La Mañanera

La instrucción más reciente del usuario es empezar desde cero, sin reutilizar el código ni los registros de la aplicación anterior. No cambiar esta implementación por el proyecto anterior ni importar sus datos. El PDF es una guía funcional; las instrucciones recientes del usuario reemplazan su requisito de preservar el código anterior.

El usuario quiere mejoras futuras sobre este código y una aplicación instalable en celular. No prometer memoria permanente del asistente o atención exclusiva. Conservar una copia descargable del código y, cuando sea posible, guardarlo en un repositorio remoto propiedad del usuario.

Estado de entrega: actualización local 7, no publicada. SQLite persistente en el servidor, ningún registro de ejemplo en la base real. PDF automático después de guardar movimientos con sesión iniciada, descarga/compartir y reintento sin repetir el guardado. Aviso visible si falta logo. Revisión de despachos con cantidades, precios, total, faltantes y comprobación de precios vigentes. Autoguardado de borradores con versiones y reintentos, resumen de cierre y formularios de anulación/revisión con motivo están implementados. Las correcciones usan anulación y nuevo registro, no reemplazo automático. Se conservan chat con archivos, stickers y audio, llamadas WebRTC, PDF nativo y respaldo recuperable. Pasan 42 pruebas Python, verificaciones JavaScript del autoguardado/cierre y el renderizado simulado de 10 pantallas. Faltan logo oficial, pruebas reales en celulares, conectividad de llamadas y despliegue HTTPS con almacenamiento persistente. No confundir señalización probada con una llamada de audio/video comprobada.

La eliminación de registros y retirada del proyecto anterior fue autorizada, pero NO se ejecutó. El proyecto anterior identificado para retirar es `appgprj_6abdb5df31b48191afad9baf3677bcf0`. No eliminar otros proyectos del usuario. No crear ni publicar un proyecto con este identificador como si fuera el proyecto nuevo. Confirmar la limpieza con evidencia cuando exista acceso a sus datos; retirar una publicación no equivale a borrar registros.

Las conexiones probadas sin permisos de red fallan al intentar acceder al proxy; también se bloquean sockets locales y Chromium. Una solicitud de permisos adicionales de red se interrumpió, así que no hay verificación con acceso concedido. No afirmar que se diagnosticó un fallo del servidor remoto. No quitar el proxy ni evadir la política de red. No guardar credenciales en archivos. Los scripts locales de Sites tampoco están disponibles. No declarar una publicación exitosa sin respuesta verificada del servicio.

Este servidor Python/SQLite no es un Worker compatible con Sites. Para publicar con Sites debe adaptarse el servidor, autenticación, PDF y almacenamiento a su ejecución y persistencia; no crear una publicación estática que simule guardar datos sin un servidor. Conservar el proyecto independiente y la semántica transaccional. Otra plataforma de alojamiento debe decidirse con el usuario.

Ejecutar las pruebas relevantes tras cambios en movimientos, cuentas o permisos:

```
python -m unittest discover -s tests -v
node tests/render.mjs
node tests/pdf-client.mjs
node --check public/app.js
```

El servidor y la persistencia usan biblioteca estándar de Python; PDF e imágenes requieren ReportLab y Pillow. Las pruebas de PDF también usan pypdf. Toda acción comercial debe ser transaccional, tener clave de idempotencia, validar permisos en el servidor y conservar auditoría. Los borradores se guardan en SQLite. No usar almacenamiento del navegador como autoridad de datos comerciales. No cachear respuestas API en el service worker.

El módulo `team.py` no modifica `records`, `movements` ni cuentas. Los mensajes/archivos privados requieren pertenencia a la conversación. Cámara y micrófono solo se abren al grabar, llamar o aceptar una llamada. Las llamadas reales requieren HTTPS y un servicio STUN/TURN según la red; no afirmar disponibilidad de TURN si no se configuró y comprobó.

La base SQLite y archivos de clientes nunca se incluyen en Git ni en el ZIP del código.

Gemini: integración opcional preparada en ai_assistant.py, sin clave ni llamada real verificada. Solo Administración, consentimiento explícito, contexto agregado sin nombres/celulares/chats, sin herramientas ni escrituras comerciales. Generación fuera de la transacción SQLite. Revisión firmada con clave persistida en settings, expira en una hora; ai-save conserva una copia de los datos y evita duplicados. PDF con logo configurado, respuesta y totales de referencia. GEMINI_API_KEY solo en entorno del servidor; nunca en cliente, Git o ZIP. El modelo inicial es configurable y no se comprobó su disponibilidad. No prometer gratuidad ni conexión real por el mero hecho de tener la clave configurada.

Render autorizado por el usuario; GitHub solicitado: Fincasanjuan. Configuración preparada en render.yaml y PUBLICAR_RENDER.md, sin repositorio remoto creado ni despliegue verificado. Usa PORT, RENDER_EXTERNAL_URL para origen/cookie Secure, bootstrap_admin con AREPAS_ADMIN_PASSWORD de mínimo 12 caracteres solo para la primera cuenta; no reinicia contraseña existente. Disco /var/data con AREPAS_DATA_DIR=/var/data/arepas y una instancia. Starter y disco pueden tener costo: no contratar antes de revisar y aceptar el precio. El 7 de octubre gh auth status reportó GH_TOKEN inválido; no copiar tokens del chat ni inventar una URL de repositorio como si existiera. No reutilizar el sitio antiguo para esta publicación.
