from datetime import timedelta
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.forms.models import model_to_dict
from django.utils import timezone
from .mail import entregar
from .models import Alerta, Auditoria, Gestion, Renovacion, Servicio, Tramite, Usuario

def auditar(accion, entidad, registro_id=None, detalle=None):
    return Auditoria.objects.create(accion=accion, entidad=entidad, registro_id=registro_id, detalle=detalle or {})

def instantanea(servicio):
    return model_to_dict(servicio)

def registrar_gestion(servicio_id, datos):
    with transaction.atomic():
        servicio = Servicio.objects.select_for_update().get(pk=servicio_id)
        gestion = Gestion.objects.create(servicio=servicio, **datos)
        servicio.tramite = gestion.tramite
        servicio.version += 1
        servicio.save(update_fields=["tramite", "version", "actualizado"])
        auditar("REGISTRAR_GESTION", "Gestion", gestion.pk, datos)
        return gestion

def renovar(servicio_id, datos):
    with transaction.atomic():
        servicio = Servicio.objects.select_for_update().get(pk=servicio_id)
        if servicio.fecha_vencimiento and datos["nuevo_vencimiento"] <= servicio.fecha_vencimiento:
            raise ValidationError("La nueva fecha debe ser posterior al vencimiento actual.")
        if datos.get("nuevo_inicio") and datos["nuevo_inicio"] > datos["nuevo_vencimiento"]:
            raise ValidationError("El nuevo inicio no puede ser posterior al vencimiento.")
        Renovacion.objects.create(servicio=servicio, ciclo=servicio.ciclo, inicio_anterior=servicio.fecha_inicio, vencimiento_anterior=servicio.fecha_vencimiento, **datos)
        servicio.fecha_inicio = datos.get("nuevo_inicio")
        servicio.fecha_vencimiento = datos["nuevo_vencimiento"]
        servicio.ciclo += 1
        servicio.version += 1
        servicio.tramite = Tramite.RENOVADO
        servicio.requiere_validacion = False
        servicio.motivo_validacion = ""
        servicio.save()
        Gestion.objects.create(servicio=servicio, tipo="Renovación confirmada", descripcion=f"Nuevo vencimiento: {servicio.fecha_vencimiento.isoformat()}", tramite=Tramite.RENOVADO, observaciones=datos.get("observaciones", ""))
        auditar("RENOVAR", "Servicio", servicio.pk, datos)
        return servicio

def enviar_alerta(servicio_id, tipo, hoy=None):
    hoy = hoy or timezone.localdate()
    with transaction.atomic():
        servicio = Servicio.objects.select_for_update().get(pk=servicio_id)
        dias = servicio.dias_al_vencimiento(hoy)
        valido = dias is not None and (dias < 45 if tipo == Alerta.Tipo.URGENTE else tipo in {"45", "30", "15"} and dias == int(tipo))
        if not valido:
            return "omitida"
        administrador = Usuario.objects.get(pk=1, is_active=True)
        alerta, creada = Alerta.objects.get_or_create(servicio=servicio, ciclo=servicio.ciclo, tipo=tipo, defaults={"fecha": hoy, "destinatario": administrador.email})
        if not creada:
            return "omitida"
        # Reserva confirmada antes de SMTP: otra ejecución no puede volver a enviar.
        datos = {"nombre": servicio.nombre, "codigo": servicio.codigo, "vencimiento": servicio.fecha_vencimiento, "tramite": servicio.tramite, "ciclo": servicio.ciclo}
    alerta.estado = Alerta.Estado.ENVIANDO
    alerta.intentada = timezone.now()
    alerta.save(update_fields=["estado", "intentada"])
    etiqueta = "atención urgente" if tipo == Alerta.Tipo.URGENTE else f"{tipo} días para vencer"
    try:
        estado, respuesta = entregar(f"SICSI: {etiqueta} — {datos['codigo']}", f"Sección de Informática – UPCV\nServicio: {datos['nombre']} ({datos['codigo']})\nVencimiento: {datos['vencimiento']}\nTrámite: {datos['tramite']}\nCiclo: {datos['ciclo']}\nFecha del aviso: {hoy} (America/Guatemala)\n{settings.APP_URL}", alerta.destinatario)
        alerta.estado = estado
        alerta.respuesta = respuesta[:4000]
        alerta.enviada = timezone.now() if estado == Alerta.Estado.ENVIADA else None
        alerta.save(update_fields=["estado", "respuesta", "enviada"])
        return "enviada" if estado == Alerta.Estado.ENVIADA else "simulada"
    except Exception as exc:
        respuesta = f"{type(exc).__name__}: {exc}"
        for secreto in [settings.EMAIL_HOST_PASSWORD, settings.DATABASES["default"].get("PASSWORD", ""), settings.SECRET_KEY]:
            if secreto:
                respuesta = respuesta.replace(secreto, "[oculto]")
        Alerta.objects.filter(pk=alerta.pk).update(estado=Alerta.Estado.INCIERTA, respuesta=respuesta[:4000])
        return "fallida"

def procesar_alertas(hoy=None):
    hoy = hoy or timezone.localdate()
    resultados = {"enviada": 0, "simulada": 0, "omitida": 0, "fallida": 0}
    for dias in (45, 30, 15):
        ids = Servicio.objects.filter(fecha_vencimiento=hoy + timedelta(days=dias), requiere_validacion=False).exclude(periodicidad=Servicio.Periodicidad.PERMANENTE).exclude(estado=Servicio.Estado.CANCELADO).values_list("pk", flat=True)
        for pk in ids:
            resultados[enviar_alerta(pk, str(dias), hoy)] += 1
    return resultados
