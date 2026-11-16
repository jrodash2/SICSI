# Importación del acta

Los CSV de `data/` solo contienen encabezados. Este flujo importa únicamente campos del inventario. Para cargar el DOCX completo, incluidos catálogo, accesos y datos originales privados, usa [importar_acta](ACTAS.md); no hace falta transcribir el documento a CSV.

## Preparar los 12 servicios

Transcribe las páginas 5–6 del documento del 11 de noviembre de 2026 a una copia de `data/servicios_plantilla.csv`, CSV UTF-8 con comas. Revisa que Excel no cambie el separador ni las fechas. Solo código y nombre son obligatorios. Si asignas un código interno, identifícalo como tal.

- Fechas: YYYY-MM-DD. No selecciones una fecha por deducción.
- Si la fuente contiene dos fechas incompatibles y no puedes confirmar cuál corresponde, deja el vencimiento vacío, describe ambas en motivo_validacion y marca requiere_validacion=true.
- Si inicio supera vencimiento, el importador marca el registro para revisión automáticamente.
- Deja vacíos datos faltantes. Valores por defecto: periodicidad=por definir, estado=Activo, tramite=Pendiente.
- Periodicidad: anual, mensual, permanente, otra, por definir.
- Estado: Activo, Suspendido, Cancelado.
- Trámite: Pendiente, Cotización solicitada, En preparación, Trasladado a Compras, En trámite, En espera de aprobación, Aprobado, Renovado, Cancelado.
- Marca de validación: true, 1, sí o si; las demás entradas no marcan la casilla.
- Monto: no negativo, con punto decimal y sin símbolo. Moneda: tres letras mayúsculas o vacía.

Con el entorno virtual activo:

```bash
python manage.py importar_servicios /RUTA_PRIVADA/servicios.csv --inicial-12
python manage.py importar_servicios /RUTA_PRIVADA/servicios.csv --inicial-12 --usuario TU_USUARIO --aplicar
```

Primero simula, revisa y luego aplica. En --usuario indica la cuenta activa del Gestor o Administrador responsable para que conste en la auditoría. En Windows también puedes usar rutas entre comillas y llamar directamente al Python de `.venv`. --inicial-12 exige exactamente doce filas; omítelo para incorporaciones posteriores autorizadas.

Se valida todo antes de escribir. La carga aplica una transacción completa, genera auditoría y rechaza códigos existentes, repetidos y columnas no admitidas. No hay sobrescrituras ni importación de PDF desde CSV; adjúntalos después por la interfaz.

Revisa manualmente los campos de texto: una lista cerrada de columnas no puede identificar si una observación contiene una clave. No mezcles contraseñas, accesos, credenciales administrativas, números de identidad ni el acta completa en este CSV de servicios. El importador DOCX conserva esas secciones completas dentro de las actas privadas cifradas. Incluye únicamente los contactos de servicio pertinentes disponibles en la fuente.

## Catálogo adicional

`data/catalogo_adicional.csv` sirve para preparar licencias y solicitudes de páginas 2–4, con referencia de página y estado. No se importa automáticamente como servicio. Revisa cada elemento antes de crearlo en la interfaz o convertirlo al formato de servicios. No es una tabla de credenciales ni un módulo adicional de usuarios.
