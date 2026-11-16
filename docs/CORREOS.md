# Gmail, destinatarios y verificación de alertas

## Actualizar desde Windows

Detén runserver con Ctrl+C. Con el entorno virtual activo:

```powershell
git pull origin main
python -m pip install -r requirements-lock.txt
python manage.py migrate
```

La migración agrega destinatarios y resultados individuales de envío. No borra servicios, actas ni avisos previos. Tu config/settings.py sigue privado y no se reemplaza con git pull.

## Configurar Gmail en settings.py

Puedes hacerlo con el asistente local:

```powershell
python manage.py configurar_gmail --correo TU_CUENTA
```

Reemplaza TU_CUENTA por tu correo de Gmail o Google Workspace. Se solicitará la **contraseña de aplicación** de 16 caracteres de forma oculta. Puedes pegarla con sus grupos de espacios; se eliminan al guardarla. No se imprime ni se envía correo durante la configuración. El asistente modifica únicamente los ajustes de correo del config/settings.py privado y conserva la base, SECRET_KEY y las rutas de documentos.

También puedes editar el archivo manualmente:

```python
EMAIL_MODE = "smtp"
EMAIL_BACKEND = "core.email_backend.CustomEmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
EMAIL_HOST_USER = "TU_CUENTA"
EMAIL_HOST_PASSWORD = "TU_CLAVE_DE_APLICACION_SIN_ESPACIOS"
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
```

El backend correcto de este proyecto es **core.email_backend.CustomEmailBackend**. Un módulo llamado tickets_app pertenece a otra aplicación y no está instalado en SICSI. El backend de SICSI usa la conexión SMTP/TLS de Django y captura la respuesta DATA para el historial. Las instalaciones anteriores con el backend SMTP estándar mantienen compatibilidad.

Para activar la configuración reinicia:

```powershell
python manage.py runserver
```

La clave real no se incluye en la plantilla, documentación ni historial Git. Para revisar la configuración no compartas tu archivo privado completo.

## Agregar los destinatarios

En la barra lateral abre **Destinatarios** y selecciona **Añadir correo**. Registra nombre o área, correo y estado activo.

- Los administradores activos siguen incluidos en todos los avisos, con el correo de sus cuentas SICSI.
- Los contactos activos son destinatarios adicionales de todos los servicios y umbrales, incluida urgencia.
- Los contactos inactivos no se añaden. Si registras el mismo correo del administrador, desactivar ese contacto no elimina la notificación obligatoria del administrador.
- Un correo recibe un solo mensaje por aviso: se normaliza y no se duplica aunque coincida con el administrador o varíen sus mayúsculas.
- Puedes editar, activar, desactivar y eliminar contactos. Estas acciones exigen sesión, POST/CSRF para cambios y dejan auditoría.
- Los destinatarios son contactos, no cuentas de usuario: Las cuentas y perfiles se administran por separado en Usuarios.

El remitente SMTP y los destinatarios cumplen funciones diferentes. La cuenta de Gmail envía; los administradores y los contactos activos reciben. El remitente no se añade automáticamente como destinatario si no coincide con el administrador o con un contacto activo.

## Probar sin generar alertas

Desde Destinatarios usa **Probar con el administrador** o **Probar correo** en un contacto activo. Un modal solicita confirmar el envío al correo seleccionado. No se incluyen datos del acta y no se crean alertas de servicios ni se consumen claves de renovación.

Comprueba la bandeja del destinatario y, si no aparece, la carpeta de correo no deseado. En Auditoría verás el resultado de la prueba y la respuesta SMTP. Una aceptación 250 no confirma recepción final en la bandeja.

EMAIL_MODE = "console" solo simula el mensaje. La vista lo indica expresamente y nunca informa que hubo un envío real. Si Gmail rechaza la autenticación, comprueba la cuenta, la contraseña de aplicación, la habilitación necesaria en la cuenta y la salida al puerto 587 desde tu PC o servidor. El código no modifica políticas de Google ni verifica credenciales al guardarlas.

## Avisos diarios y resultados parciales

El Cron o Programador de tareas sigue ejecutando:

```powershell
python manage.py enviar_alertas
```

Los avisos se generan exactamente a los 45, 30 y 15 días de Guatemala; no se agregan envíos retroactivos al crear un contacto. Los servicios permanentes, cancelados, sin fecha o pendientes de validación se excluyen como antes.

Cada alerta mantiene su clave única por servicio, ciclo y tipo. Antes de conectar a SMTP se reserva la lista de destinatarios. Los mensajes se envían individualmente para no exponer la lista de otros contactos en los encabezados.

En **Alertas → Ver destinatarios y respuestas** puedes consultar el correo, estado y respuesta SMTP de cada envío. Si uno falla se continúa con los demás; el resultado global será **Parcial** si hubo confirmaciones y errores. El Cron devuelve un error ante fallos totales o parciales para facilitar monitoreo.

No se reintenta automáticamente un resultado ambiguo ni se vuelve a enviar a los contactos exitosos. Agregar contactos después de reservar una alerta no modifica ese envío ya iniciado. Los nuevos destinatarios aplican a avisos futuros. Las alertas de versiones anteriores conservan su registro original, sin inventar resultados individuales.

## Diseño

La interfaz usa un diseño propio inspirado en la organización de [NexLink](https://nexlink.layoutdrop.com/php/demo/index.php): navegación lateral clara, paneles de resumen y datos agrupados. Conserva la identidad azul/blanco/gris de SICSI. Los gráficos muestran datos reales de PostgreSQL: renovaciones por mes y distribución por vencimiento; no se incluyen porcentajes o tendencias ficticias. Bootstrap, iconos SVG y estilos se sirven localmente.
