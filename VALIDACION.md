# Validación de la base nueva

Fecha: 7 de octubre de 2026.

42 pruebas de reglas, comunicación, documentos y recuperación aprobadas:

- Pedido sin código, persistencia al reabrir y prevención de envíos duplicados.
- Fechas antes/después del mediodía y medianoche en Colombia.
- Borradores persistentes y editables.
- Confirmación inmutable e inventario sin duplicación.
- Cierre con sobrantes buenos, malas y reposiciones; redistribución posterior.
- Rechazo por inventario insuficiente con reversión completa.
- Fiados, abonos, límite de saldo y anulaciones auditadas.
- Anulación de cierre/despacho con reversión de inventario.
- Precios por repartidor y consumo de 400 g de químico por bulto.
- Entregas posteriores de saldos de ruta separadas de los fiados.
- Permisos y consultas privadas por repartidor.
- Cantidades y fechas inválidas.
- Rechazo de escrituras desde otro origen, sesión HttpOnly y bloqueo de creación de otra Administración.

Pruebas agregadas en la actualización 2:

- Chat autenticado, persistencia y reintentos sin duplicados ni movimientos comerciales.
- Conversaciones privadas con control de pertenencia y reutilización del mismo grupo.
- Archivos originales, permisos privados y rechazo de imágenes inválidas.
- Stickers y consulta de historial paginado.
- Invitación y aceptación de llamadas, señalización privada y salida de participantes.
- Llamada grupal y expiración de llamadas sin actividad.
- Credenciales temporales TURN sin exponer el secreto compartido.
- PDF nativo multipágina: saldo correcto y misma imagen del logo en cada página, comprobando dimensiones y píxeles.
- Permisos de descarga de recibos desde el límite HTTP.
- Recuperación de respaldo con usuarios, cuentas, mensajes y archivos, sin sesiones activas.
- Rechazo de respaldos alterados sin reemplazar datos.

Actualización 3: rechazo de edición con versión antigua sin sobrescribir cantidades ni generar movimientos; guardado de borradores vacíos con confirmación prohibida; rechazo de confirmación después de cambiar el borrador, conservando inventario. Verificaciones JavaScript de resumen del cierre, devoluciones excesivas, efectivo excesivo, deudor incompleto y cantidades fraccionarias. Reintento simulado de autoguardado con respuesta perdida después de confirmar: conserva la misma clave, recupera la versión y luego guarda los cambios posteriores.

Actualización 4: revisión con total y precios de devoluciones sin movimientos de inventario; confirmación con los importes revisados; rechazo de confirmación cuando cambian los precios, sin descontar existencias; reporte de faltantes y protección de la revisión frente a usuarios anónimos u otros repartidores. En JavaScript se verifica la pantalla de revisión y la ausencia del formulario de confirmación cuando hay faltantes.

Actualización 5: `node tests/pdf-client.mjs` verifica apertura del PDF guardado, descarga, opción de compartir el archivo PDF, advertencia de logo faltante y reintento tras perder conexión usando solo consultas al PDF, sin escrituras comerciales. Las pruebas Python existentes siguen comprobando la imagen exacta del logo en cada página y los permisos HTTP de los comprobantes.

Actualización 6: siete pruebas nuevas verifican informes sin cambios contables, guardado idempotente y duplicados con distinta clave, rechazo de texto alterado/revisión vencida/otros perfiles, totales con abonos descontados y sin nombres/celulares de clientes, PDF con respuesta y logo exacto en cada página, consentimiento y permisos de la ruta HTTP, falta de clave explícita y ausencia de secretos en el estado, solicitud al proveedor con clave en encabezado y rechazo de respuesta incompleta. El proveedor se simula: no se probó conexión real, disponibilidad del modelo, cuotas ni costos. Se comprueba también que el texto de Gemini se escape antes de mostrarlo en HTML.

Además: renderizado de diez pantallas, incluido el chat y el asistente, con un entorno DOM simulado, cálculo de requerimiento de producción y validación de sintaxis JavaScript. Estas comprobaciones no sustituyen una prueba visual o funcional en un navegador real.

Actualización 7: cinco pruebas adicionales de despliegue verifican creación inicial del administrador por secreto sin registrar su contraseña, persistencia de la cuenta sin cambios al reiniciar, rechazo de contraseña ausente o corta en un servidor Render vacío, inicio de sesión HTTPS con cookie Secure y rechazo de origen distinto, dominio propio y rechazo de direcciones con rutas, healthcheck sin datos privados. `render.yaml` se analizó con PyYAML: Python, una instancia y disco en /var/data. No se probó build en Render ni repositorio remoto: la autenticación GitHub del entorno está inválida.

No se realizaron pruebas en teléfonos ni de instalación, de la interfaz de compartir PDF ni de audio/video real. El entorno bloqueó sockets del servidor de prueba y el arranque de Chromium. Las solicitudes de red no se ejecutaron con permisos adicionales: la solicitud de acceso se interrumpió. No existe una publicación nueva verificada ni borrado verificado de la aplicación anterior.

No se importaron datos ni código del proyecto anterior. Las pruebas utilizan bases temporales separadas; el proyecto entregado no contiene una base real, sesiones, códigos personales ni registros ficticios.
