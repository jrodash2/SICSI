import csv
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from core.forms import ServicioForm
from core.models import Servicio
from core.services import auditar

CAMPOS = list(ServicioForm.Meta.fields)

from core.management.actor_command import ComandoConUsuario

class Command(ComandoConUsuario):
    requiere_administrador = False
    help = "Valida un CSV de servicios. Solo escribe con --aplicar; nunca sobrescribe registros existentes."
    def add_arguments(self, parser):
        parser.add_argument("archivo", type=Path)
        parser.add_argument("--aplicar", action="store_true")
        parser.add_argument("--inicial-12", action="store_true", help="Exige exactamente 12 servicios revisados de las páginas 5 y 6.")
    def handle(self, *args, **options):
        try:
            with options["archivo"].open(encoding="utf-8-sig", newline="") as entrada:
                lector = csv.DictReader(entrada)
                headers = lector.fieldnames or []
                if len(headers) != len(set(headers)) or set(headers) - set(CAMPOS):
                    raise CommandError("Columnas repetidas o no admitidas. Use la plantilla y no incluya credenciales ni identidad personal.")
                if not {"codigo", "nombre"}.issubset(headers):
                    raise CommandError("El CSV necesita las columnas codigo y nombre.")
                filas = list(lector)
        except (OSError, UnicodeError, csv.Error) as exc:
            raise CommandError(f"No se pudo leer el CSV: {type(exc).__name__}.") from exc
        if options["inicial_12"] and len(filas) != 12:
            raise CommandError("La carga inicial exige exactamente 12 filas verificadas.")
        validados = []
        codigos = set()
        for numero, fila in enumerate(filas, start=2):
            if None in fila:
                raise CommandError(f"Fila {numero}: número incorrecto de columnas.")
            datos = {k: (v or "").strip() for k, v in fila.items()}
            datos["periodicidad"] = datos.get("periodicidad") or "por definir"
            datos["estado"] = datos.get("estado") or "Activo"
            datos["tramite"] = datos.get("tramite") or "Pendiente"
            datos["requiere_validacion"] = datos.get("requiere_validacion", "").lower() in {"true", "1", "sí", "si"}
            # Fechas ISO ordenan igual que el calendario; el formulario valida su formato real.
            if datos.get("fecha_inicio") and datos.get("fecha_vencimiento") and datos["fecha_inicio"] > datos["fecha_vencimiento"]:
                datos["requiere_validacion"] = True
                datos["motivo_validacion"] = datos.get("motivo_validacion") or "Fechas contradictorias en la fuente; revisar antes de confirmar."
            form = ServicioForm(datos)
            if not form.is_valid():
                raise CommandError(f"Fila {numero}: {form.errors.as_json(escape_html=False)}")
            codigo = form.cleaned_data["codigo"]
            if codigo in codigos:
                raise CommandError(f"Fila {numero}: código duplicado dentro del CSV.")
            codigos.add(codigo)
            validados.append(form)
        self.stdout.write(f"Validación correcta: {len(validados)} filas; {sum(f.cleaned_data['requiere_validacion'] for f in validados)} para revisión.")
        if not options["aplicar"]:
            self.stdout.write("Simulación: no se guardaron datos. Revise y agregue --aplicar para confirmar.")
            return
        with transaction.atomic():
            for form in validados:
                servicio = form.save()
                auditar("IMPORTAR", "Servicio", servicio.pk, {"codigo": servicio.codigo, "requiere_validacion": servicio.requiere_validacion})
        self.stdout.write(self.style.SUCCESS("Importación completa y auditada."))
