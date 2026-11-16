# Verificación

Entorno de desarrollo: Python 3.12, Django 5.2 y PostgreSQL 16 temporal. No se usan datos del acta ni cuentas institucionales.

## Pruebas automatizadas

Resultado de la entrega: **58 pruebas aprobadas** con PostgreSQL 16. `check` sin incidencias, migraciones al día y dependencias sin incompatibilidades (`pip check`). `check --deploy` únicamente informa las dos decisiones documentadas de HSTS (subdominios y preload).

La suite verifica umbrales exactos, exclusiones, urgencia inicial, día de Guatemala, año bisiesto, fechas contradictorias, importación sin escrituras parciales, reservas únicas, fallos SMTP sin reintentos ambiguos y renovación con fechas anteriores.

También prueba acceso, cierre por POST, CSRF, administrador único en ORM y base, límite persistente de intentos, todas las pantallas, protección contra XSS, formularios desactualizados, PDF privados, estado histórico, exportaciones y texto de Excel sin fórmulas ejecutables. La concurrencia se comprueba con dos conexiones reales a PostgreSQL. Las pruebas de correo verifican destinatarios activos/inactivos, deduplicación, resultados parciales sin reenvíos, conservación del historial al eliminar contactos, pruebas SMTP solo mediante POST, ocultación de secretos en errores y configuración de Gmail sin cambiar la base ni imprimir claves. Las nuevas pantallas y gráficos se renderizan con datos de prueba reales en PostgreSQL. Las pruebas de actas verifican reserva del original, cifrado sin secretos en auditoría, claves perdidas sin sustitución, descarga privada, filas repetidas, fechas ambiguas, rollback y reimportación idempotente, usando únicamente documentos sintéticos. Un servidor SMTP local de prueba verifica la captura de la respuesta DATA sin enviar mensajes fuera del entorno.

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

Las pruebas crean una base temporal y requieren permiso CREATEDB para la cuenta de desarrollo. El flujo GitHub Actions genera su propio settings.py privado desde la plantilla y ejecuta la suite con PostgreSQL efímero y credenciales exclusivamente de CI.

## Límites

La publicación en GitHub entrega código, no despliega la aplicación. El importador DOCX completo se verificó con el documento suministrado en una base temporal: recuentos íntegros, reimportación sin duplicados y recuperación byte por byte del original cifrado. No se ha escrito en la base del PC del usuario, enviado correo institucional ni programado el Cron real. No se dispone del alojamiento. Se entregó la configuración para Gmail; la autenticación y recepción con la cuenta institucional deben probarse desde la PC o servidor del usuario, mediante el botón de prueba. Los datos reales de esa verificación no se incluyen en el repositorio. La revisión visual en navegador no pudo ejecutarse por falta del control de navegador requerido en este entorno; las plantillas sí se renderizan en pruebas HTTP.

El despliegue requiere confirmar Python y PostgreSQL con el proveedor. Antes de producción, valida HTTPS, límites y descargas en el navegador, conexión SMTP, una ejecución programada real y restauración de respaldo en un destino aislado. No se promete compatibilidad de PostgreSQL con un plan compartido específico sin confirmación.
