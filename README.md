# SICSI · Sección de Informática – UPCV

Sistema de Control de Servicios Informáticos en **Python, Django y PostgreSQL**. Interfaz en español con Bootstrap 5 local, sin herramientas Node.js ni compilación de frontend.

Permite inventariar servicios, controlar vencimientos, conservar renovaciones, seguir gestiones, adjuntar PDF privados y generar reportes. Uso exclusivo de un administrador.

## Empezar en tu PC (Windows y PowerShell)

Necesitas Git, Python 3.12 recomendado (versión utilizada en las pruebas) y PostgreSQL 16 o compatible con Django 5.2. No necesitas reinstalar PostgreSQL si ya lo tienes funcionando.

### 1. Descargar el código

```powershell
git clone https://github.com/jrodash2/SICSI.git
cd SICSI
```

Si ya clonaste la carpeta vacía antes de esta entrega, entra a ella y ejecuta `git pull origin main` en lugar de volver a clonarla.

### 2. Crear el entorno virtual e instalar

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
```

Se llama al Python del entorno directamente para evitar problemas con las políticas de activación de PowerShell. Si tu instalación usa `python` en lugar de `py`, crea el entorno con `python -m venv .venv`. Comprueba primero que sea una versión compatible.

`requirements.txt` describe los paquetes principales; `requirements-lock.txt` fija todas las versiones verificadas. Usa el segundo para reproducir la instalación.

### 3. Crear la base en PostgreSQL

Abre pgAdmin, conéctate con tu administrador de PostgreSQL y abre Query Tool en la base `postgres`.

Ejecuta primero esta instrucción, reemplazando la contraseña por una propia:

```sql
CREATE USER sicsi WITH PASSWORD 'REEMPLAZA_POR_UNA_CLAVE_PROPIA';
```

Luego ejecuta **por separado**, con autocommit habilitado:

```sql
CREATE DATABASE sicsi OWNER sicsi ENCODING 'UTF8';
```

No ejecutes CREATE DATABASE dentro de una transacción. Puedes usar otra base/usuario si ajustas `.env`; se recomienda una base exclusiva para SICSI. No utilices la cuenta `postgres` como cuenta de la aplicación.

### 4. Configurar `.env`

```powershell
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
notepad .env
```

Copia la clave aleatoria generada a SECRET_KEY. Completa los valores:

```dotenv
SECRET_KEY=PEGA_LA_CLAVE_ALEATORIA_GENERADA
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
DB_NAME=sicsi
DB_USER=sicsi
DB_PASSWORD=LA_CLAVE_QUE_ELEGISTE_EN_POSTGRESQL
DB_HOST=127.0.0.1
DB_PORT=5432
DB_SSLMODE=prefer
APP_URL=http://127.0.0.1:8000
EMAIL_MODE=console
```

Conserva también las otras variables de la plantilla. Si PostgreSQL usa otro puerto, cambia DB_PORT. No publiques `.env`, claves ni respaldos; `.gitignore` los excluye. Si una clave contiene `#` o espacios, usa el formato de comillas admitido por python-dotenv. No compartas capturas del archivo completo.

### 5. Crear las tablas y el administrador

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
```

El comando solicitará usuario, correo y contraseña. Usa un correo válido: allí llegarán las alertas cuando actives SMTP. La contraseña debe tener al menos 14 caracteres. No se muestra al escribirla. SICSI solo permite una cuenta; no existe registro público ni panel para crear usuarios adicionales.

### 6. Levantar la aplicación

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

Abre **http://127.0.0.1:8000/** e inicia sesión con el **usuario** y contraseña que acabas de crear. Mantén PowerShell abierto. Para detener el servidor presiona Ctrl+C.

La base comienza vacía. Registra tu primer servicio desde Servicios → Nuevo servicio. No se cargan datos ficticios automáticamente.

### 7. Usarla otro día

Comprueba que el servicio de PostgreSQL esté encendido. Desde la carpeta SICSI:

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

No repitas `createsuperuser`. Cuando incorpores actualizaciones, ejecuta `git pull`, instala las dependencias bloqueadas si cambiaron y aplica `manage.py migrate`. Respalda antes los datos importantes.

## Módulos incluidos

- Acceso, cierre por POST, CSRF, límites de intentos persistentes y cambio de contraseña.
- Dashboard con ocho indicadores y próximos vencimientos.
- CRUD de servicios con filtros y validación de fechas.
- Bitácora de gestiones y estados sin borrar hechos anteriores.
- Renovaciones con inicio/vencimiento anterior y nuevo ciclo de avisos.
- PDF privados asociados a servicio o gestión, validados por tamaño y estructura básica.
- Alertas exactas de 45/30/15 días, urgencia inicial, reserva y clave única contra duplicados.
- Reportes Excel/PDF, última gestión, expediente y siguiente seguimiento.
- Auditoría, importador CSV y comando de respaldo PostgreSQL.

## Comandos útiles

Ejemplos con el entorno activado; si no lo activas, sustituye `python` por ` .\.venv\Scripts\python.exe` en Windows.

```text
python manage.py check
python manage.py test
python manage.py enviar_alertas --solo-revisar
python manage.py enviar_alertas
python manage.py importar_servicios data/servicios_plantilla.csv
python manage.py respaldar_bd
```

Las pruebas usan una base temporal `test_sicsi`. El usuario local necesita permiso CREATEDB para crearlas; puedes otorgarlo **solo en desarrollo** desde pgAdmin con `ALTER ROLE sicsi CREATEDB;`. No lo concedas al usuario de producción.

## Documentación

- [Uso y reglas del sistema](docs/USO.md).
- [Importación de los servicios del acta](docs/IMPORTACION.md).
- [SMTP, tareas programadas y producción](docs/DESPLIEGUE.md).
- [Problemas comunes en tu PC](docs/SOLUCION_PROBLEMAS.md).
- [Pruebas y límites de verificación](docs/VERIFICACION.md).

## Datos pendientes

El acta del 11 de noviembre de 2026 no se proporcionó. Las plantillas están preparadas, pero los 12 servicios de páginas 5–6 y el catálogo de páginas 2–4 requieren transcripción y revisión. No inventes fechas, proveedores ni contactos. No importes el acta completa, contraseñas, credenciales administrativas ni números de identidad.

## Producción

`runserver` es únicamente para desarrollo local. El despliegue necesita alojamiento con Python/Django y acceso a PostgreSQL. **No se presupone que Namecheap Stellar Plus incluya PostgreSQL**: comprueba con el proveedor tanto soporte Python/Passenger como conectividad a una base PostgreSQL propia o administrada. La aplicación no está publicada y el enlace de GitHub no es una dirección de acceso al sistema.
