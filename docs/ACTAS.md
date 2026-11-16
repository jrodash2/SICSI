# Cargar el acta DOCX completa en tu PC

El archivo original se procesa como datos, no como instrucciones para ejecutar. No necesitas transcribirlo a CSV ni subirlo a GitHub. La importación conserva el DOCX exacto, incluyendo imágenes y formato, más una transcripción completa de párrafos, tablas y partes adicionales con texto. Los accesos, claves e identificación presentes en la fuente no se suprimen de la copia privada.

## 1. Actualizar SICSI

Detén runserver con Ctrl+C. Desde la carpeta del proyecto y con el entorno virtual activo:

```powershell
git pull origin main
python -m pip install -r requirements-lock.txt
python manage.py migrate
```

Tu config/settings.py privado permanece en tu PC. No es necesario volver a copiar la plantilla ni cambiar la contraseña de PostgreSQL. La migración agrega actas y catálogo y un vínculo opcional con los servicios existentes; no los elimina.

## 2. Elegir el Word original

Conserva el DOCX fuera del repositorio, por ejemplo en una carpeta privada de tus documentos. Puedes seleccionar la ruta mediante PowerShell:

```powershell
$ruta = Read-Host "Pega la ruta completa al archivo DOCX, sin comillas adicionales"
python manage.py importar_acta "$ruta"
```

El comando revisa y muestra recuentos sin escribir datos ni generar claves. No imprime contraseñas, identidades ni textos de acceso. Comprueba los recuentos antes de continuar.

## 3. Aplicar

```powershell
python manage.py importar_acta "$ruta" --aplicar
python manage.py runserver
```

La carga es transaccional: si una fila no es válida, no quedan servicios o actas a medio cargar. Repetir el mismo archivo exacto no duplica registros ni sobrescribe ediciones locales, porque se verifica su SHA-256. Una copia modificada de Word puede tener otro hash aunque se vea igual: no la vuelvas a importar como si fuera el mismo archivo; revisa primero el inventario.

No se modifican cuentas administrativas, contraseñas de plataformas ni permisos externos. Las frases del acta que piden cambiar una clave se conservan como información, no se ejecutan. Tampoco se envían correos durante la importación.

## 4. Revisar desde la aplicación

- **Servicios:** registros de la tabla de vencimientos, con nombres, capacidades, proveedores y contactos disponibles. Los códigos ACTA-… son identificadores internos generados y se indica que no vienen de la fuente.
- **Actas de entrega:** catálogo completo, incluyendo filas repetidas; tabla de accesos; párrafos de entrega; datos de identificación; y todas las demás tablas, sin reemplazar textos originales.
- **Descargar DOCX original:** recupera exactamente los bytes del archivo importado. La descarga exige sesión y se registra en auditoría.
- **Contenido original completo:** permite leer los textos originales sin enmascararlos. Django escapa el contenido para que se muestre como texto y no como HTML ejecutable.

Los accesos no se mezclan en observaciones de servicios ni en exportaciones generales. Quedan dentro de las actas privadas. Los elementos del catálogo se conservan como catálogo, no se convierten automáticamente en servicios: pueden ser insumos, solicitudes o filas repetidas que requieren revisión antes de inventariarse como un contrato independiente.

## 5. Fechas y contradicciones

Se conserva el texto literal de cada fecha. Cada tabla se analiza por separado: por ejemplo, si hay fechas inequívocas como 11/30/2026 se detecta mes/día/año; si aparecen 30/11/2026 se detecta día/mes/año. Las fechas ambiguas se interpretan siguiendo el patrón de su propia tabla y quedan marcadas para validación. Si no puede identificarse un patrón, la fecha queda vacía y se conserva el texto.

Se comparan conceptos con nombre normalizado entre catálogo y servicios. Si los vencimientos no coinciden, se guardan ambas referencias y se marca el servicio. La comparación normalizada no garantiza identificar todos los sinónimos: revisa también el documento completo. No se corrigen fechas en silencio ni se inventa el año de un mes o de una frase incompleta.

Permanente queda excluido de vencimientos. Pago mensual conserva la periodicidad y no inventa una fecha. Los registros pendientes de validación no generan alertas hasta que el administrador confirme su fecha en Editar servicio.

## 6. Cifrado y respaldos

Al aplicar por primera vez se crea automáticamente **private_media/.acta.key** (o el equivalente bajo PRIVATE_MEDIA_ROOT). No tienes que poner claves de cifrado en settings.py ni en Git. El DOCX completo, su transcripción y los campos originales de accesos/catálogo se guardan cifrados en PostgreSQL con Fernet, autenticación de integridad y una clave separada de SECRET_KEY.

**Respalda la base y private_media/.acta.key por separado y de forma privada. Sin esa clave no se puede recuperar el original ni los accesos. No la regeneres para resolver un error de lectura.** Si configuraste ACTA_KEY_FILE manualmente, respalda esa ruta. No sustituyas la clave de una instalación por la de otra.

La clave y los DOCX están excluidos de Git. Evita forzar su inclusión. En Windows usa una carpeta con permisos NTFS limitados a tu cuenta. Copias del documento y respaldos deben seguir la política institucional. El original contiene información sensible y no debe incluirse como una fixture o migración de datos del repositorio público.

Este comando prepara la incorporación en tu PostgreSQL local; un archivo subido al chat no da acceso al servidor de tu PC. Para completar esa carga debes ejecutar --aplicar en tu máquina.
