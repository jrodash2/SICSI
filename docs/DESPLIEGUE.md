# Producción, SMTP, tareas y respaldos

## Alojamiento

La aplicación exige Python/Django y PostgreSQL. Antes de contratar o usar un plan existente, confirma soporte Python/WSGI y disponibilidad o conexión saliente a PostgreSQL. No se afirma que Namecheap Stellar Plus ofrezca PostgreSQL. Si solo ofrece MariaDB, se necesita una base PostgreSQL externa autorizada o un alojamiento compatible. No se cambia automáticamente de motor.

En un servidor compatible usa un entorno virtual, instala requirements-lock.txt, configura secretos mediante variables del servicio o .env privado, ejecuta migrate y collectstatic, y publica config.wsgi:application mediante el servidor WSGI del proveedor. Un VPS puede usar Gunicorn como dependencia específica de despliegue, instalada y versionada según ese entorno. No uses runserver en producción.

## Variables esenciales

```dotenv
DEBUG=False
SECRET_KEY=CLAVE_ALEATORIA_PRIVADA_DE_AL_MENOS_40_CARACTERES
ALLOWED_HOSTS=sicsi.TU_DOMINIO
APP_URL=https://sicsi.TU_DOMINIO
CSRF_TRUSTED_ORIGINS=https://sicsi.TU_DOMINIO
DB_NAME=BASE_REAL
DB_USER=USUARIO_REAL
DB_PASSWORD=SECRETO_REAL
DB_HOST=HOST_POSTGRESQL
DB_PORT=5432
DB_SSLMODE=verify-full
PRIVATE_MEDIA_ROOT=/RUTA_PRIVADA/sicsi-documentos
BACKUP_DIR=/RUTA_PRIVADA/sicsi-respaldos
TRUST_PROXY_HTTPS=False
EMAIL_MODE=smtp
```

verify-full requiere certificados confiables y nombre de host correcto. Instala la CA de PostgreSQL según el proveedor (psycopg/libpq admite PGSSLROOTCERT). Para una base por loopback en el mismo servidor, la política puede permitir prefer; verifica la política institucional. No desactives verificación de TLS en conexiones remotas por conveniencia.

Activa TRUST_PROXY_HTTPS=True únicamente si un proxy confiable elimina/reemplaza X-Forwarded-Proto y es el único que puede acceder al proceso. DEBUG=False exige cookies seguras y redirige a HTTPS. Usa un certificado válido antes de habilitar acceso. SESSION_SECRET no existe en esta versión: Django utiliza SECRET_KEY y sesiones en PostgreSQL. Mantén estable esa clave y rótala con planificación.

Sirve solo STATIC_ROOT mediante el servidor web después de collectstatic. No sirvas MEDIA_ROOT, PRIVATE_MEDIA_ROOT, .env, respaldos ni el directorio completo del proyecto. Los PDF pasan por la vista autenticada de Django. Ajusta también el límite de carga del proxy.

```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy
```

El comando check --deploy puede advertir que HSTS no incluye subdominios ni preload: es deliberado y no debe ampliarse sin controlar todos los subdominios. Revisa los demás avisos y confirma HTTPS de extremo a extremo.

## SMTP

```dotenv
EMAIL_MODE=smtp
SMTP_HOST=HOST_SMTP
SMTP_PORT=587
SMTP_USER=CUENTA_SMTP
SMTP_PASSWORD=SECRETO_SMTP
SMTP_USE_TLS=True
SMTP_USE_SSL=False
SMTP_FROM=notificaciones@TU_DOMINIO
```

Para puerto 465 usa SMTP_USE_SSL=True y SMTP_USE_TLS=False. No actives los dos. TLS se verifica mediante los valores por defecto seguros de Python. Ajusta SPF/DKIM/DMARC con el proveedor.

Prueba con un servicio de prueba con menos de 45 días y Notificar urgencia. Comprueba bandeja y registros SMTP. La respuesta DATA queda registrada junto con fecha, tipo, destinatario, servicio y ciclo. Un 250 significa aceptación del proveedor, no entrega final.

En modo consola se generan registros Simulada y no se marcan como Enviada. Cambiar luego a SMTP no libera esas reservas. Para probar envío real usa un servicio de prueba distinto y evita contaminar el inventario real.

## Cron diario independiente de la web

Comando para Linux/cPanel con soporte Python y PostgreSQL (sustituye las rutas):

```cron
0 8 * * * cd /home/USUARIO/SICSI && /home/USUARIO/venv/sicsi/bin/python manage.py enviar_alertas >> /home/USUARIO/logs/sicsi-alertas.log 2>&1
```

La hora de Cron es la del servidor; ajusta la programación para que corresponda a las 08:00 de America/Guatemala. El código calcula siempre el calendario de Guatemala. No programes cerca de medianoche. No es necesario tener sesión web abierta ni mantener runserver ejecutándose.

Revisa la configuración sin enviar ni reservar:

```bash
python manage.py enviar_alertas --solo-revisar
```

Los umbrales son exactos: si Cron falta un día, no hay envío retroactivo. Monitoriza la ejecución. La reserva persistente y la clave única evitan duplicados aun si dos tareas corren al mismo tiempo. No existe garantía de exactamente una entrega en SMTP ante una caída después de la aceptación; por eso resultados inciertos no se reintentan solos.

Para probar la programación en Windows usa el Programador de tareas: programa `.venv\Scripts\python.exe`, argumentos `manage.py enviar_alertas` e Iniciar en = carpeta absoluta SICSI. La máquina y PostgreSQL deben estar encendidos. Si EMAIL_MODE=console, el mensaje es simulado; configura salida y monitoreo de la tarea.

Programa también limpieza de sesiones expiradas:

```cron
0 3 * * * cd /home/USUARIO/SICSI && /home/USUARIO/venv/sicsi/bin/python manage.py clearsessions
```

## Respaldo PostgreSQL

El cliente pg_dump debe estar instalado y ser de la misma versión principal o una más reciente que el servidor. Configura PG_DUMP_BIN si no está en PATH; Windows admite la ruta completa a pg_dump.exe.

```bash
python manage.py respaldar_bd
```

Crea un archivo .dump en formato personalizado, fuera de la web, con un archivo temporal privado de contraseña que se elimina al finalizar. La contraseña no se pasa en argumentos. El archivo parcial se elimina ante error y se renombra al terminar. En Windows configura permisos NTFS privados de la carpeta; chmod no sustituye las ACL.

```cron
30 2 * * * cd /home/USUARIO/SICSI && /home/USUARIO/venv/sicsi/bin/python manage.py respaldar_bd >> /home/USUARIO/logs/sicsi-respaldos.log 2>&1
```

Respalda además los PDF privados y la configuración secreta mediante un mecanismo institucional cifrado. Conserva una copia externa y aplica una política de retención; este comando no elimina copias automáticamente. El respaldo de BD contiene contactos y sesiones y debe protegerse.

Prueba restauración en una base aislada vacía:

```bash
pg_restore --host HOST --username USUARIO --dbname BASE_DE_RESTAURACION --no-owner --no-acl --password archivo.dump
```

El comando solicita la contraseña. Detén escrituras al preparar una restauración real. Restaura documentos y configuración del mismo punto de respaldo, elimina las sesiones restauradas y comprueba inventario, historial y descargas antes de abrir acceso.

## Actualizaciones

Respalda primero. Detén el servicio o usa el mecanismo de mantenimiento del proveedor; git pull, instalación del lock, migrate, collectstatic y check --deploy. Ejecuta pruebas en una base de desarrollo, nunca con credenciales de producción. Reinicia y verifica acceso, dashboard y un PDF. No edites migraciones ya aplicadas ni borres tablas para resolver conflictos.
