from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac
from .models import IntentoAcceso

VENTANA = timedelta(minutes=15)

def claves(request):
    # REMOTE_ADDR es confiable; no se acepta X-Forwarded-For enviado por el cliente.
    ip = request.META.get("REMOTE_ADDR", "desconocida")
    return [(salted_hmac("sicsi.login.ip", ip, algorithm="sha256").hexdigest(), 5), (salted_hmac("sicsi.login.cuenta", str(request.POST.get("username", "")).strip().casefold()[:150], algorithm="sha256").hexdigest(), 15)]

def bloqueado(request):
    ahora = timezone.now()
    return any(IntentoAcceso.objects.filter(clave=key, ventana__gt=ahora - VENTANA, fallos__gte=limit).exists() for key, limit in claves(request))

def fallo(request):
    ahora = timezone.now()
    with transaction.atomic():
        # Orden fijo de bloqueos para evitar interbloqueos entre dos IP.
        for key, _ in sorted(claves(request)):
            item, _ = IntentoAcceso.objects.get_or_create(clave=key)
            item = IntentoAcceso.objects.select_for_update().get(pk=item.pk)
            if item.ventana <= ahora - VENTANA:
                item.ventana = ahora
                item.fallos = 0
            item.fallos += 1
            item.save()

def limpiar(request):
    IntentoAcceso.objects.filter(clave__in=[k for k, _ in claves(request)]).delete()
