import json
from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from core.models import Servicio
from core.services import procesar_alertas

class Command(BaseCommand):
    help = "Consulta los umbrales exactos de hoy y genera avisos sin depender de sesiones web."
    def add_arguments(self, parser):
        parser.add_argument("--solo-revisar", action="store_true", help="Muestra los candidatos sin reservar ni enviar avisos.")
    def handle(self, *args, **options):
        hoy = timezone.localdate()
        if options["solo_revisar"]:
            for dias in (45, 30, 15):
                servicios = Servicio.objects.filter(fecha_vencimiento=hoy + timedelta(days=dias), requiere_validacion=False).exclude(periodicidad="permanente").exclude(estado="Cancelado")
                for servicio in servicios:
                    self.stdout.write(f"{servicio.codigo}: {dias} días, ciclo {servicio.ciclo}")
            self.stdout.write("Solo revisión: no se reservaron ni enviaron avisos.")
            return
        resultado = procesar_alertas(hoy)
        self.stdout.write(json.dumps({"fecha": str(hoy), "zona": "America/Guatemala", **resultado}, ensure_ascii=False))
        if resultado["fallida"] or resultado["parcial"]:
            raise CommandError("Hay envíos fallidos o inciertos. Revise el registro de alertas; no se reintentan automáticamente.")
