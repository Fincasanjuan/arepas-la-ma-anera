# Publicar Arepas La Mañanera en Render

Proyecto nuevo, independiente. Destino solicitado: cuenta GitHub `Fincasanjuan`.
Repositorio propuesto: `arepas-la-mananera`. Preferir repositorio privado.

## 1. Subir el código a GitHub

Crear un repositorio vacío en https://github.com/new con propietario Fincasanjuan,
nombre arepas-la-mananera y visibilidad Private. No incluir README de plantilla.
Si ya existe ese nombre, revisar primero su contenido; no reemplazar otro proyecto.

Para subir desde el navegador, descomprimir el ZIP preparado y entrar en la carpeta
`arepas-la-mananera-nueva`. En el repositorio, elegir «uploading an existing file»
o «Add file → Upload files». Arrastrar los archivos y las carpetas de DENTRO de la
carpeta del proyecto, conservando `public/` y `tests/`. `server.py`, `requirements.txt`
y `render.yaml` deben quedar directamente en la raíz del repositorio.

No subir `.git/`, `data/`, bases SQLite, respaldos, `.env` real, contraseñas ni claves.
`.env.example` contiene solo instrucciones. El ZIP de entrega no incluye datos.
Finalizar con «Commit changes» y comprobar que aparece `server.py` en la raíz.

Si hay acceso GitHub autorizado desde Codex, se puede crear el repositorio y subir
el commit directamente, sin pedir ni compartir contraseñas o tokens en el chat.
No considerar esa subida realizada hasta verificar el repositorio remoto.

## 2. Revisar el costo

Esta versión guarda cuentas y archivos en SQLite. Necesita un disco persistente.
El servidor gratuito de Render no ofrece ese disco y no es una entrega adecuada
para guardar los datos reales de la fábrica. `render.yaml` propone Starter con
disco de 1 GB. Servicio y disco pueden generar cargos. Comprobar el precio vigente
en Render y decidir si se acepta ANTES de crear el servicio o confirmar un Blueprint.
No se ha contratado ni pagado nada al preparar estos archivos.

## 3. Conectar Render

En Render elegir «New → Web Service», conectar GitHub y autorizar el acceso al
repositorio Fincasanjuan/arepas-la-mananera. Seleccionar la rama main.

- Nombre: arepas-la-mananera.
- Runtime: Python 3.
- Root Directory: vacío, si server.py está en la raíz.
- Build Command: `pip install -r requirements.txt`.
- Start Command: `python server.py`.
- Health Check Path: `/healthz`.
- Instancias: una. SQLite usa un disco local, no compartido entre instancias.
- Elegir un plan compatible con discos solo después de revisar y aceptar su costo.
- Añadir disco: ruta `/var/data`, tamaño inicial 1 GB.

Variables en Environment:

| Nombre | Valor |
| --- | --- |
| PYTHON_VERSION | 3.12.8 |
| AREPAS_HOST | 0.0.0.0 |
| AREPAS_DATA_DIR | /var/data/arepas |
| AREPAS_ADMIN_NAME | Dujardy |
| AREPAS_ADMIN_PASSWORD | Una contraseña NUEVA, privada, de mínimo 12 caracteres |

Render proporciona PORT y RENDER_EXTERNAL_URL; no copiar valores inventados.
La dirección HTTPS proporcionada determina el origen permitido y cookies Secure.
Al usar dominio propio, configurar AREPAS_PUBLIC_ORIGIN con su dirección HTTPS
exacta, sin rutas. No modificar los controles de origen para superar un error.

Alternativa: usar «New → Blueprint» con render.yaml, revisando su plan y disco antes
de confirmar. No seleccionar Blueprint si aún no se aceptó su costo.

## 4. Primer ingreso y comprobación

El servidor crea una sola cuenta de Administración desde el secreto inicial.
Ingresar con celular `admin` y la contraseña configurada. No aparece un registro
público para crear otra Administración. Cambiar el secreto después no reemplaza la
contraseña guardada; no borrar la base para cambiarla. Una vez comprobado el primer
ingreso, puede retirarse AREPAS_ADMIN_PASSWORD del entorno sin borrar la cuenta.

Comprobar «Live», abrir el enlace HTTPS de Render, ingresar, cargar el logo oficial,
registrar un movimiento de prueba y verificar su PDF. Reiniciar el servicio y
comprobar que el registro y el logo siguen disponibles. Mantener respaldos fuera
del servidor. No anunciar publicación exitosa únicamente por ver una pantalla
de configuración, un build completado o una dirección todavía sin verificar.

## 5. Gemini e instalación móvil

Gemini es opcional. Configurar GEMINI_API_KEY solo en Render y comprobar límites,
modelo, condiciones y costos. No subir su clave a GitHub ni enviarla al chat.
El resto de la aplicación funciona sin Gemini.

Con la publicación HTTPS comprobada, abrir el enlace en el celular: Chrome →
«Instalar aplicación» o «Añadir a pantalla de inicio». En iPhone: Safari → Compartir
→ «Añadir a pantalla de inicio». Las llamadas aún necesitan pruebas reales entre
celulares y configuración STUN/TURN cuando las redes lo requieran.
