# Problemas comunes en Windows

## No se reconoce py o python

Instala Python desde python.org con Add Python to PATH, o usa la ruta de tu instalación existente. Cierra y abre PowerShell. Comprueba `py --version`. Python 3.12 es la versión verificada para esta entrega.

## PowerShell bloquea Activate.ps1

No es necesario cambiar políticas. Usa directamente ` .\.venv\Scripts\python.exe manage.py runserver` desde la carpeta que contiene manage.py, sin el espacio inicial de este ejemplo. Los comandos del README usan ese método.

## No module named config.settings / Configure SECRET_KEY

En la primera instalación copia config/settings_example.py como config/settings.py. Abre settings.py, genera una clave aleatoria de al menos 40 caracteres y asígnala a SECRET_KEY entre comillas. Ese archivo es privado y no se descarga de Git porque está excluido para proteger tus secretos. No uses una clave publicada en un ejemplo. No hace falta crear .env.

## Connection refused / conexión rechazada

Comprueba que PostgreSQL esté iniciado en Servicios de Windows y que DATABASES["default"]["HOST"] y PORT coincidan con pgAdmin. No necesitas instalar PostgreSQL dentro de Python; psycopg es el conector, no el servidor.

## Password authentication failed

Revisa USER y PASSWORD dentro de DATABASES en config/settings.py. Es la clave del usuario PostgreSQL sicsi, no la contraseña para entrar a SICSI. Prueba la misma conexión desde pgAdmin. No envíes tu settings.py completo al pedir ayuda.

## Database does not exist / permission denied for schema public

Crea la base con OWNER sicsi como indica el README. Si la base ya existe con otro propietario, pide a tu administrador ajustar los permisos sobre la base y el esquema public. No concedas permisos globales a la aplicación.

## Relation does not exist

Ejecuta ` .\.venv\Scripts\python.exe manage.py migrate` desde el proyecto. No borres migraciones para resolver errores de instalación.

## Ya existe un administrador

No repitas el alta inicial. Las cuentas adicionales se crean desde Usuarios por un administrador. Inicia sesión con la cuenta creada. Para recuperación local autorizada puedes usar ` .\.venv\Scripts\python.exe manage.py restablecer_clave NOMBRE_USUARIO`; se solicita una contraseña nueva y se invalidan las sesiones anteriores. El comando de recuperación no registra la contraseña en auditoría.

## Error al ejecutar pruebas: permission denied to create database

Las pruebas crean y borran una base temporal. Otorga CREATEDB al usuario solo en desarrollo, o usa una cuenta de pruebas separada. Nunca ejecutes la suite con la conexión de producción.

## Puerto 8000 ocupado

Ejecuta ` .\.venv\Scripts\python.exe manage.py runserver 8001` y abre http://127.0.0.1:8001. Ajusta APP_URL si vas a probar enlaces de correo.

## No llegan correos

EMAIL_MODE = "console" es el valor local: el mensaje aparece en la terminal y se registra como Simulada. Para SMTP usa docs/DESPLIEGUE.md. El aviso normal solo corresponde en 45, 30 o 15 días exactos y un aviso ya reservado no se repite.

## pg_dump no se encuentra

Agrega la carpeta bin de PostgreSQL a PATH o configura PG_DUMP_BIN con la ruta completa a pg_dump.exe. Usa un cliente de la misma versión principal o más reciente que el servidor. No necesitas el respaldo para iniciar la aplicación, pero sí debes comprobarlo antes de usar datos reales importantes.
