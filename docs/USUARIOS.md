# Usuarios, responsables y auditoría

## Actualizar una instalación existente

Respalda tu base PostgreSQL y los documentos privados antes de actualizar. Detén runserver y, con el entorno virtual activo, ejecuta:

```powershell
git pull origin main
python manage.py migrate
python manage.py runserver
```

No copies otra vez settings_example.py encima de tu configuración. Se conservan la conexión, SMTP, SECRET_KEY, actas y claves privadas. No es necesario crear de nuevo el administrador ni importar otra vez el Word.

La migración retira la restricción antigua de una sola cuenta, conserva el id y contraseña del administrador existente, le asigna el perfil Administrador y prepara la secuencia para cuentas nuevas. Se comprobó que el siguiente usuario recibe otro id. No borra los datos de servicios ni modifica sus fechas.

La reversión al esquema de usuario único deja de ser compatible después de crear otras cuentas. Para volver a una instalación anterior usa un respaldo consistente; no borres usuarios o migraciones para forzar un downgrade.

## Crear cuentas de personal

Inicia sesión con tu administrador actual y abre **Usuarios → Crear usuario**. Completa nombre de usuario, nombres, apellidos, correo, perfil, estado y contraseña inicial de al menos 14 caracteres. No hay registro público.

Los perfiles se verifican en el servidor, no solo ocultando botones:

| Operación | Administrador | Gestor | Consulta |
|---|---|---|---|
| Consultar servicios, gestiones, alertas y reportes | Sí | Sí | Sí |
| Descargar documentos de servicios y exportar reportes | Sí | Sí | Sí |
| Crear/editar servicios, registrar gestiones y renovar | Sí | Sí | No |
| Adjuntar documentos y solicitar avisos de urgencia | Sí | Sí | No |
| Eliminar un servicio sin historial | Sí | Sí | No |
| Actas completas, accesos y credenciales del acta | Sí | No | No |
| Destinatarios y pruebas de correo | Sí | No | No |
| Auditoría completa y administración de usuarios | Sí | No | No |
| Cambiar la propia contraseña | Sí | Sí | Sí |

Las cuentas de personal son distintas de los destinatarios de correo. Crear un Gestor o Consulta no lo agrega automáticamente a las notificaciones. Los administradores activos reciben avisos; los contactos adicionales siguen configurándose en Destinatarios y se deduplican.

## Activar, desactivar y cambiar perfiles

Desde Usuarios puedes editar los datos y el perfil. Los permisos se consultan en cada solicitud. No puedes desactivar tu propia cuenta ni quitarte el perfil de administrador. Debe permanecer al menos un administrador activo; el control se realiza con bloqueo de base de datos para evitar pérdidas de acceso por cambios simultáneos.

Se desactivan cuentas en lugar de borrarlas. El usuario inactivo pierde acceso en su siguiente solicitud y se conservan sus servicios, documentos y acciones históricas.

**Restablecer clave** define una contraseña nueva para otro usuario sin mostrar la anterior. Sus sesiones existentes dejan de ser válidas. Para tu propia cuenta usa Seguridad, que solicita la contraseña actual y mantiene tu sesión después de cambiarla. Las claves y hashes no se guardan en auditoría.

## Quién realizó cada acción

Los nuevos registros guardan el usuario autenticado automáticamente. Los formularios no aceptan un autor enviado por el cliente.

- Servicios muestra quién registró el servicio; el detalle añade quién hizo la última modificación y su fecha.
- Las gestiones, renovaciones y documentos muestran quién los registró o confirmó.
- El detalle de servicio incluye un historial de acciones con fecha, usuario, operación y registro.
- Actas muestra quién realizó la importación; los accesos siguen restringidos a administradores.
- Alertas distingue solicitudes humanas de tareas automáticas.
- Auditoría identifica usuario, origen y cambios; incluye accesos, exportaciones, descargas, destinatarios, usuarios y operaciones denegadas por permisos.

La identidad del responsable se conserva también como texto de referencia. Si luego cambia su nombre o se desactiva la cuenta, la acción sigue mostrando la identidad registrada en ese momento. Las solicitudes simultáneas usan contextos separados; no se comparte el usuario entre peticiones.

**Los registros anteriores no se atribuyen a nadie por suposición.** Se muestran como Autor no registrado / registro anterior. Los procesos automáticos muestran Sistema; no se hacen pasar por una persona.

## Operaciones desde consola

Para declarar el responsable de una importación local:

```powershell
python manage.py importar_acta "C:/RUTA_PRIVADA/acta.docx" --usuario TU_USUARIO --aplicar
python manage.py importar_servicios "C:/RUTA_PRIVADA/servicios.csv" --usuario TU_USUARIO --aplicar
python manage.py respaldar_bd --usuario TU_USUARIO
python manage.py configurar_gmail --correo TU_CUENTA --usuario TU_USUARIO
```

El usuario debe existir, estar activo y tener el perfil correspondiente: el CSV permite Gestor y Administrador; actas, respaldos y configuración requieren Administrador. Sin --usuario se registra Consola / sin usuario indicado. La opción declara al operador local, no equivale a autenticación web: una persona con control del terminal sigue siendo un operador de confianza.

El Cron sin --usuario aparece como Sistema / tarea automática. Para una ejecución manual atribuida puedes usar `python manage.py enviar_alertas --usuario TU_USUARIO`. Los intentos o avisos anteriores ya reservados no se vuelven a enviar.

Para una instalación nueva puedes usar `python manage.py crear_administrador`, equivalente al asistente habitual de Django pero con registro de origen en consola. La recuperación local auditada se realiza con `python manage.py restablecer_clave NOMBRE_USUARIO --usuario TU_USUARIO`. La primera cuenta no tiene un usuario web previo que pueda autorizarla y se identifica como creada desde consola.

La traza cubre las operaciones implementadas en SICSI y estos comandos. No atribuye operaciones SQL ejecutadas directamente fuera de la aplicación ni pretende ser un registro externo inalterable. El acceso directo al servidor y a la base debe limitarse al personal responsable.

## Presentación institucional

La interfaz utiliza Arial/Helvetica, colores azul institucional, blanco y gris, tablas con mayor contraste y bordes discretos. Se retiraron el saludo personal y las tarjetas de estilo promocional. El formulario de servicio se organiza por identificación, proveedor, contratación/vigencia y trámite/validación. El menú y las acciones visibles corresponden al perfil real de cada cuenta.
