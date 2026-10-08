# Arepas La Mañanera — proyecto nuevo

Código nuevo e independiente. No importa código, datos, usuarios ni configuraciones del proyecto anterior.

## Estado real

Implementación local con servidor Python y SQLite. No está publicada ni instalada en ningún celular. El entorno no permitió las conexiones necesarias para publicar; la solicitud de acceso de red se interrumpió. No se ha borrado la aplicación anterior.

Actualización 7: archivos preparados para publicar en Render desde la cuenta GitHub Fincasanjuan. Incluye `render.yaml`, instrucciones en [PUBLICAR_RENDER.md](PUBLICAR_RENDER.md), puerto PORT, origen HTTPS de Render, comprobación `/healthz` y creación inicial de Administración mediante un secreto del servidor. Usa un disco persistente y una sola instancia. La configuración propone un servicio de pago: revisar y aceptar el precio en Render antes de crear el servicio. No se ha creado repositorio remoto ni contratado alojamiento. El acceso GitHub del entorno no está autenticado correctamente.

La actualización 6 prepara una integración opcional con Gemini para Administración: generar un resumen con datos agregados, revisarlo y pulsar «Guardar y generar PDF». Guarda el texto y la copia de los datos usados; no modifica cuentas ni inventario. Las vistas previas están firmadas por el servidor, vencen en una hora y no pueden alterarse antes de guardarlas. Guardar la misma vista previa dos veces conserva un solo informe. El PDF incluye el logo configurado y los totales usados como referencia. No hay clave configurada ni prueba contra el servicio real de Google: la integración aún no está activada.

Se conserva el PDF automático después de guardar un movimiento con sesión iniciada: pedidos, entradas, producción, despachos confirmados, cierres, fiados, abonos, entregas de saldos y gastos. Permite descargar o compartir el archivo mediante el menú del celular si el navegador lo admite. El PDF incorpora el logo configurado en cada página; si falta, se informa que el archivo sale sin logo. Si falla la descarga, el registro permanece guardado y el botón de reintento consulta únicamente el PDF, sin crear otro movimiento. Los pedidos públicos sin sesión conservan su confirmación en pantalla y no reciben acceso al PDF privado. El autoguardado de borradores no genera documentos definitivos.

Se conserva la revisión del despacho con cantidades, precios, subtotales, total y precios de devoluciones malas. Consulta los datos actuales del servidor y señala faltantes de inventario. La confirmación desde esta pantalla comprueba que las cantidades y los precios revisados siguen vigentes; si cambiaron, exige abrir nuevamente la revisión. La revisión no mueve inventario. Los faltantes se vuelven a verificar de forma transaccional al confirmar, aunque otro despacho haya consumido producto mientras se revisaba.

Se conservan autoguardado de borradores, control de versiones al editar, recuperación de reintentos con respuesta perdida y resumen del cierre antes de enviarlo. Las anulaciones y revisiones muestran el detalle, exigen motivo y confirmación y conservan el historial. Para corregir un movimiento se anula y se registra uno nuevo; no hay reemplazo automático.

Se conservan chat con archivos, stickers, audio, llamadas WebRTC, PDF nativo y respaldo recuperable. Hay 42 pruebas Python aprobadas, diez pantallas comprobadas con DOM simulado y verificaciones JavaScript de revisión del despacho, cierre, PDF y reintento del autoguardado. Esto no confirma funcionamiento en teléfonos ni conectividad de audio/video entre redes distintas.

## Activar Gemini en el servidor

Configurar `GEMINI_API_KEY` mediante las variables privadas del servidor; nunca incluirla en JavaScript, Git, ZIP, capturas o mensajes del chat. `GEMINI_MODEL` permite elegir el modelo autorizado para la cuenta; el valor inicial es `gemini-2.5-flash`, cuya disponibilidad debe comprobarse al conectar la cuenta. La clave configurada activa el botón, pero no certifica que Google la acepte. Reiniciar el servidor si cambia su entorno y comprobar una generación real antes de anunciar disponibilidad.

Solo Administración puede generar y guardar estos informes. Cada consulta requiere confirmar el envío de la pregunta y totales agregados a Google. No se envían automáticamente nombres, celulares, chats o archivos; el usuario debe evitar introducir información privada en su consulta. Los resultados son recomendaciones, no nuevas reglas contables. No se asegura gratuidad: revisar condiciones, cuota y facturación de la cuenta Gemini antes de habilitarla. Las llamadas usan HTTPS con un tiempo máximo de conexión de 25 segundos y no siguen redirecciones. No se realizaron llamadas reales en esta entrega.

En Despachos, elige primero el repartidor. Los cambios se guardan automáticamente con conexión; «Guardar borrador» permite reintentar y actualizar la lista. Si falla el guardado, las cantidades permanecen en el formulario y se impide cambiar de sección hasta resolverlo o descartarlas expresamente. No cierres la aplicación sin guardar: el navegador no conserva una copia comercial de respaldo. Confirmar exige revisar nuevamente si otro dispositivo cambió el borrador. Las cantidades en cero pueden conservarse como borrador, pero no confirmarse.

## Ejecutar

Requiere Python 3.12 o posterior. Los módulos de PDF e imágenes necesitan ReportLab y Pillow:

```sh
python -m pip install -r requirements.txt
python server.py
```

Abrir http://127.0.0.1:8787. La primera pantalla permite crear la cuenta de Administración. Los datos se guardan en `data/arepas.sqlite3`, nunca en el almacenamiento del navegador.

El servidor escucha únicamente en el equipo local por defecto. No exponerlo directamente a Internet. Una publicación para celulares necesita HTTPS, almacenamiento persistente respaldado y configuración de un servidor de producción. La instalación PWA requiere HTTPS (localhost sirve para desarrollo).

## Continuidad

Conservar este directorio o su ZIP. Contiene todo el código, pruebas y esquema de base de datos. En una conversación futura, adjuntar el ZIP permite continuar sin depender de la memoria del asistente. El asistente no puede prometer conservar archivos eternamente ni atender exclusivamente todas las conversaciones.

## Reglas

- Hora y fechas de Colombia.
- Pedidos sin código; consultas privadas y despachos con código personal.
- Movimientos atómicos y claves únicas para evitar duplicados.
- Despachos confirmados inmutables, anulaciones administrativas con motivo e historial.
- Precios por repartidor, cantidades por referencia y separación de sobrantes buenos y devoluciones malas.
- Fiados y abonos conservan movimientos. El abono no descuenta inventario.
- No se incluyen precios, rendimientos ni registros inventados.
- El logo oficial no se obtuvo; Administración puede cargar la imagen correcta para la app y los comprobantes.
- PDF nativo de despacho, cierre, abono, estado de cuenta e informe, con subtotales y saldos separados. La misma imagen configurada se repite sin recortar ni estirar en todas las páginas.
- Compartir PDF mediante el selector del celular cuando el navegador lo permite; descargar y adjuntar manualmente como alternativa.
- Conversaciones privadas y grupales con mensajes, archivos y stickers; nunca crean movimientos comerciales.
- Grabación de audio de hasta 60 segundos, archivos de hasta 12 MB y cámara mediante el selector del dispositivo.
- Llamadas de audio/video de 2 a 8 participantes, con aceptación explícita, estado real de conexión y controles para apagar micrófono/cámara.

## Conexión de llamadas

Las llamadas requieren HTTPS y permisos de micrófono/cámara. Entre teléfonos o redes distintas suele ser necesario configurar un servidor STUN/TURN. No se incluye ni se afirma disponible un proveedor de TURN.

- `AREPAS_ICE_SERVERS`: arreglo JSON de servidores ICE con sus `urls`.
- `AREPAS_TURN_URLS`: arreglo JSON de direcciones del servidor TURN configurado por el responsable del alojamiento.
- `AREPAS_TURN_SECRET`: secreto compartido de un servidor coturn que acepte credenciales temporales. No escribirlo en Git ni en el ZIP. El servidor emite credenciales de una hora y mantiene el secreto fuera del navegador.

La señalización y los permisos de invitación están probados localmente; el audio/video real aún debe comprobarse entre celulares.

## Respaldo y recuperación

Administración descarga un ZIP completo desde «Descargar respaldo». Incluye una instantánea consistente de SQLite, usuarios, cuentas, historial, mensajes y archivos originales del chat, con hashes para detectar daños. Las sesiones de acceso se excluyen y deben iniciarse de nuevo tras recuperar.

Detener el servidor y recuperar en un directorio vacío:

```sh
python backup.py respaldo.zip --destino /ruta/vacia/datos-recuperados
```

Iniciar el servidor con `AREPAS_DATA_DIR` apuntando a ese directorio. La recuperación rechaza destinos con datos y respaldos alterados. El respaldo contiene información privada; guardarlo fuera del código fuente.

## Comprobaciones

```sh
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
node tests/render.mjs
```

Antes de uso real faltan alojamiento compatible con el servidor y persistencia, publicación HTTPS, pruebas reales en teléfonos, logo oficial y configuración/verificación del servicio TURN cuando sea necesario. También falta retirar y borrar los datos de la aplicación anterior. Las pruebas locales no son una publicación.

La implementación Python/SQLite no se puede subir directamente como un Worker de Sites. Si se continúa con Sites, hay que adaptar el servidor a su ejecución y persistencia compatibles, conservando las reglas y pruebas de este proyecto. No publicar solo las pantallas con un servidor ausente. Un alojamiento Python sería una alternativa a decidir con el usuario, no un cambio ya realizado.

## Seguridad

Los códigos personales se almacenan como hashes scrypt. Sesiones en cookies HttpOnly y comprobación de origen en escrituras. La creación inicial de Administración solo está disponible en localhost. Para ejecutar detrás de un servidor HTTPS, definir `AREPAS_PUBLIC_ORIGIN` y `AREPAS_HOST`; configurar límites, respaldos, certificados y arranque supervisado. No incluir `data/` en el código fuente ni en el ZIP del proyecto.
