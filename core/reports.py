from io import BytesIO
from xml.sax.saxutils import escape
from django.http import HttpResponse
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

CABECERAS = ["Código", "Servicio", "Categoría", "Proveedor", "Vencimiento", "Días", "Estado", "Trámite", "Validar fechas", "Última gestión", "Expediente", "Próximo seguimiento", "Registrado por", "Última modificación por"]

def filas(servicios):
    for s in servicios:
        gestiones = list(s.gestiones.all())
        ultima = gestiones[0] if gestiones else None
        yield [s.codigo, s.nombre, s.categoria, s.proveedor, s.fecha_vencimiento.isoformat() if s.fecha_vencimiento else "", s.dias if s.dias is not None else "", s.estado, s.tramite, "Sí" if s.requiere_validacion else "No", ultima.descripcion if ultima else "", ultima.expediente if ultima else "", ultima.proximo_seguimiento.isoformat() if ultima and ultima.proximo_seguimiento else "", s.autor_creacion, s.autor_actualizacion]

def generar_reporte(servicios, formato):
    buffer = BytesIO()
    if formato == "xlsx":
        libro = Workbook()
        hoja = libro.active
        hoja.title = "Servicios"
        hoja.append(CABECERAS)
        for fila in filas(servicios):
            hoja.append(fila)
        # Evitar que texto ingresado por el usuario se interprete como fórmula.
        for row in hoja.iter_rows(min_row=2):
            for cell in row:
                if isinstance(cell.value, str):
                    cell.data_type = "s"
        for cell in hoja[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="164D85")
        for col in hoja.columns:
            hoja.column_dimensions[col[0].column_letter].width = 25
        hoja.freeze_panes = "A2"
        hoja.auto_filter.ref = hoja.dimensions
        libro.save(buffer)
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=32, leftMargin=32, topMargin=32, bottomMargin=32, title="SICSI · Servicios")
        estilos = getSampleStyleSheet()
        texto = [Paragraph("SICSI · Sección de Informática – UPCV", estilos["Title"]), Paragraph(f"Reporte al {timezone.localdate().isoformat()} · {len(servicios)} servicios", estilos["Normal"]), Spacer(1, 18)]
        for fila in filas(servicios):
            texto.append(Paragraph(escape(f"{fila[0]} · {fila[1]}"), estilos["Heading3"]))
            for label, valor in zip(CABECERAS[2:], fila[2:]):
                texto.append(Paragraph(f"<b>{escape(label)}:</b> {escape(str(valor) if valor != '' else 'No registrado')}", estilos["Normal"]))
            texto.append(Spacer(1, 14))
        doc.build(texto)
        mime = "application/pdf"
    response = HttpResponse(buffer.getvalue(), content_type=mime)
    response["Content-Disposition"] = f'attachment; filename="SICSI-servicios.{formato}"'
    return response
