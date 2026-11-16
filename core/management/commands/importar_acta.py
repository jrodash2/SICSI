from datetime import date
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from core.actas_crypto import cifrar_bytes, cifrar_json
from core.actas_parser import interpretar_fecha, leer_acta
from core.models import ActaEntrega, ElementoActa, Servicio
from core.services import auditar

class Command(BaseCommand):
    help = "Importa un acta DOCX privada completa, sin publicar ni descartar accesos o datos originales."
    def add_arguments(self, parser):
        parser.add_argument("archivo", type=Path)
        parser.add_argument("--aplicar", action="store_true", help="Confirma la carga; sin esta opción solo revisa y no escribe.")
    def handle(self, *args, **options):
        path = options["archivo"]
        if path.suffix.lower() != ".docx":
            raise CommandError("Seleccione un archivo .docx.")
        try:
            if path.stat().st_size > 15 * 1024 * 1024:
                raise ValueError("El DOCX supera 15 MB.")
            data = path.read_bytes()
            parsed = leer_acta(data)
        except (OSError, ValueError) as exc:
            raise CommandError(f"No se pudo leer el acta: {type(exc).__name__}. Compruebe el archivo DOCX y sus tablas.") from exc
        summary = parsed["resumen"]
        self.stdout.write("Revisión: " + ", ".join(f"{key}={value}" for key, value in summary.items()))
        self.stdout.write("Fechas: tabla de servicios=" + str(parsed["formato_servicios"]) + "; catálogo=" + str(parsed["formato_catalogo"]) + ". Las ambigüedades y contradicciones se marcan para validar.")
        if ActaEntrega.objects.filter(sha256=parsed["sha256"]).exists():
            self.stdout.write("Este documento exacto ya fue importado. No se duplicó ni sobrescribió información.")
            return
        if not options["aplicar"]:
            self.stdout.write("Solo revisión: no se guardaron datos, claves ni archivos. Agregue --aplicar para confirmar.")
            return
        try:
            with transaction.atomic():
                acta = ActaEntrega.objects.create(nombre_archivo=path.name[:255], sha256=parsed["sha256"], fecha_documento=parsed["fecha_documento"], resumen=summary, archivo_cifrado=cifrar_bytes(data), contenido_cifrado=cifrar_json(parsed))
                for index, item in enumerate(parsed["servicios"], start=1):
                    service = Servicio(acta_origen=acta, codigo=f"ACTA-{parsed['sha256'][:10]}-{index:02d}", nombre=item["nombre"], capacidad=item["capacidad"], fecha_vencimiento=date.fromisoformat(item["fecha_vencimiento"]) if item["fecha_vencimiento"] else None, proveedor=item["proveedor"], contacto_nombre=item["contacto_nombre"], contacto_telefono=item["contacto_telefono"], periodicidad=item["periodicidad"], requiere_validacion=item["requiere_validacion"], motivo_validacion=item["motivo_validacion"], observaciones=f"Fila original: {item['numero']}. Vencimiento literal: {item['fecha_texto']}. Código interno generado por SICSI; no consta en la fuente.")
                    service.full_clean()
                    service.save()
                    auditar("IMPORTAR_DESDE_ACTA", "Servicio", service.pk, {"acta_id": acta.pk, "fila": index})
                for tipo, key in [(ElementoActa.Tipo.CATALOGO, "catalogo"), (ElementoActa.Tipo.ACCESO, "accesos")]:
                    for orden, row in enumerate(parsed[key], start=1):
                        if len(row) != 3:
                            raise CommandError("Hay una fila de catálogo o accesos con columnas inesperadas. No se cargó información parcial.")
                        fecha, motivo = interpretar_fecha(row[2], parsed["formato_catalogo"]) if tipo == ElementoActa.Tipo.CATALOGO else (None, "")
                        ElementoActa.objects.create(acta=acta, tipo=tipo, orden=orden, nombre=row[0].strip()[:255], fecha_texto=row[2].strip()[:255] if tipo == ElementoActa.Tipo.CATALOGO else "", fecha_referencia=fecha, requiere_validacion=bool(motivo), motivo_validacion=motivo, contenido_cifrado=cifrar_json({"celdas_originales": row}))
                auditar("IMPORTAR_ACTA", "ActaEntrega", acta.pk, summary)
        except IntegrityError as exc:
            if ActaEntrega.objects.filter(sha256=parsed["sha256"]).exists():
                self.stdout.write("El documento ya fue importado por otra ejecución. No se duplicó información.")
                return
            raise CommandError("La base rechazó un registro. Se revirtió la carga completa; revise códigos existentes.") from exc
        self.stdout.write(self.style.SUCCESS("Carga completa. Original y contenido íntegro cifrados; servicios y catálogo disponibles en Actas de entrega. No se enviaron correos."))
