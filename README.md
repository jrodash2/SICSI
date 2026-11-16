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

No ejecutes CREATE DATABASE dentro de una transacción. Puedes usar otra base/usuario si ajustas `config/settings.py`; se recomienda una base exclusiva para SICSI. No utilices la cuenta `postgres` como cuenta de la aplicación.

### 4. Configurar `settings.py`

La configuración se escribe directamente en Python, como en un proyecto Django tradicional. No se utiliza `.env` ni se leen variables de entorno para la conexión.

La plantilla pública es `config/settings_example.py`. Tu configuración real se llama `config/settings.py` y está excluida de Git para proteger las contraseñas.

En la primera instalación:

```powershell
Copy-Item config\settings_example.py config\settings.py
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
notepad config\settings.py
```

Copia la clave aleatoria generada en `SECRET_KEY`, entre comillas. Completa `DATABASES` en el mismo archivo:

```python
SECRET_KEY = "PEGA_AQUI_LA_CLAVE_ALEATORIA_GENERADA"
DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "sicsi",
        "USER": "sicsi",
        "PASSWORD": "ESCRIBE_AQUI_TU_CONTRASEÑA_LOCAL",
        "HOST": "127.0.0.1",
        "PORT": "5432",
        "CONN_MAX_AGE": 60,
        "OPTIONS": {"sslmode": "prefer"},
    }
}
```

`NAME` es el nombre de la base. `USER` debe coincidir con el rol de PostgreSQL que creaste; no es el usuario administrador de SICSI. Si tu cuenta local tiene otro nombre, cambia USER. PASSWORD debe coincidir con la clave de ese rol. Una contraseña con `#` funciona dentro de una cadena entre comillas; no la dejes fuera de las comillas.

Conserva el resto de los ajustes de la plantilla. Si PostgreSQL usa otro puerto, cambia PORT. `EMAIL_MODE = "console"` permite probar sin SMTP. No publiques tu `settings.py`, claves ni respaldos; comprueba que no aparezca en `git status` después de la actualización. No añadas este archivo usando `git add -f`.

**Si venías de la versión con `.env`:** respalda primero cualquier cambio local de configuración y actualiza con `git pull origin main`. La nueva versión retira del seguimiento `config/settings.py`; vuelve a crearlo copiando la plantilla y completa la conexión y SECRET_KEY. Ya no necesita `.env`. Este cambio no elimina ni renombra tablas ni datos de PostgreSQL. En actualizaciones posteriores, tu settings.py privado permanece intacto: compara la plantilla si se anuncian ajustes nuevos, sin copiarla encima de tus secretos.

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
- Actas DOCX completas: original cifrado, catálogo, accesos y transcripción privada sin suprimir contenido.

## Comandos útiles

Ejemplos con el entorno activado; si no lo activas, sustituye `python` por ` .\.venv\Scripts\python.exe` en Windows.

```text
python manage.py check
python manage.py test
python manage.py enviar_alertas --solo-revisar
python manage.py enviar_alertas
python manage.py importar_servicios data/servicios_plantilla.csv
python manage.py importar_acta "C:/RUTA_PRIVADA/acta.docx"
python manage.py importar_acta "C:/RUTA_PRIVADA/acta.docx" --aplicar
python manage.py respaldar_bd
```

Las pruebas usan una base temporal `test_sicsi`. El usuario local necesita permiso CREATEDB para crearlas; puedes otorgarlo **solo en desarrollo** desde pgAdmin con `ALTER ROLE sicsi CREATEDB;`. No lo concedas al usuario de producción.

## Documentación

- [Uso y reglas del sistema](docs/USO.md).
- [Importación CSV de servicios](docs/IMPORTACION.md).
- [Cargar el DOCX completo con catálogo y accesos](docs/ACTAS.md).
- [SMTP, tareas programadas y producción](docs/DESPLIEGUE.md).
- [Problemas comunes en tu PC](docs/SOLUCION_PROBLEMAS.md).
- [Pruebas y límites de verificación](docs/VERIFICACION.md).

## Importar el documento completo

El comando `importar_acta` lee tu DOCX local, incorpora los servicios, conserva todas las filas de catálogo y accesos y archiva el documento original completo con cifrado. En la interfaz aparece **Actas de entrega** para consultar todo el contenido, incluidas las secciones privadas, y descargar el original sin cambios.

No se publican archivos reales, credenciales ni identidades en GitHub. No hay datos del acta dentro del código: debes ejecutar la carga en tu PC con tu documento. Consulta [la guía de actas](docs/ACTAS.md) antes de aplicar. La importación no envía correos y no sobrescribe servicios existentes.

## Producción

`runserver` es únicamente para desarrollo local. El despliegue necesita alojamiento con Python/Django y acceso a PostgreSQL. **No se presupone que Namecheap Stellar Plus incluya PostgreSQL**: comprueba con el proveedor tanto soporte Python/Passenger como conectividad a una base PostgreSQL propia o administrada. La aplicación no está publicada y el enlace de GitHub no es una dirección de acceso al sistema.
