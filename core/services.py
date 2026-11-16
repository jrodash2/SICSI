from datetime import timedelta
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.forms.models import model_to_dict
from django.utils import timezone
from .mail import entregar, respuesta_segura
from .actor import nombre_usuario, origen_actual, usuario_actual
from .models import Alerta, Auditoria, DestinatarioAlerta, EnvioAlerta, Gestion, Renovacion, Servicio, Tramite, Usuario

def auditar(accion, entidad, registro_id=None, detalle=None, usuario=None):
    actor = usuario if usuario is not None else usuario_actual()
    return Auditoria.objects.create(accion=accion, entidad=entidad, registro_id=registro_id, detalle=detalle or {}, usuario=actor, usuario_nombre=nombre_usuario(actor), origen=origen_actual())

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

def destinatarios_actuales(administrador):
    # El administrador siempre recibe avisos; los contactos son adicionales.
    contactos = {}
    for admin in Usuario.objects.filter(is_active=True, is_superuser=True).order_by("pk"):
        correo = admin.email.strip().casefold()
        contactos[correo] = {"correo": correo, "nombre": admin.get_full_name() or admin.username}
    for contacto in DestinatarioAlerta.objects.filter(activo=True):
        correo = contacto.correo.strip().casefold()
        if correo not in contactos:
            contactos[correo] = {"correo": correo, "nombre": contacto.nombre}
    return list(contactos.values())

def enviar_alerta(servicio_id, tipo, hoy=None):
    hoy = hoy or timezone.localdate()
    with transaction.atomic():
        servicio = Servicio.objects.select_for_update().get(pk=servicio_id)
        dias = servicio.dias_al_vencimiento(hoy)
        valido = dias is not None and (dias < 45 if tipo == Alerta.Tipo.URGENTE else tipo in {"45", "30", "15"} and dias == int(tipo))
        if not valido:
            return "omitida"
        administrador = Usuario.objects.filter(is_active=True, is_superuser=True).order_by("pk").first()
        if administrador is None:
            raise ValidationError("No hay administradores activos para recibir las alertas.")
        alerta, creada = Alerta.objects.get_or_create(servicio=servicio, ciclo=servicio.ciclo, tipo=tipo, defaults={"fecha": hoy, "destinatario": administrador.email})
        if not creada:
            return "omitida"
        envios = [EnvioAlerta.objects.create(alerta=alerta, **destinatario) for destinatario in destinatarios_actuales(administrador)]
        datos = {"nombre": servicio.nombre, "codigo": servicio.codigo, "vencimiento": servicio.fecha_vencimiento, "tramite": servicio.tramite, "ciclo": servicio.ciclo}
    # Todas las reservas se confirman antes de SMTP, incluso en ejecuciones paralelas.
    alerta.estado = Alerta.Estado.ENVIANDO
    alerta.intentada = timezone.now()
    alerta.save(update_fields=["estado", "intentada"])
    etiqueta = "atención urgente" if tipo == Alerta.Tipo.URGENTE else f"{tipo} días para vencer"
    asunto = f"SICSI: {etiqueta} — {datos['codigo']}"
    texto = f"Sección de Informática – UPCV\nServicio: {datos['nombre']} ({datos['codigo']})\nVencimiento: {datos['vencimiento']}\nTrámite: {datos['tramite']}\nCiclo: {datos['ciclo']}\nFecha del aviso: {hoy} (America/Guatemala)\n{settings.APP_URL}"
    for envio in envios:
        envio.estado = Alerta.Estado.ENVIANDO
        envio.intentada = timezone.now()
        envio.save(update_fields=["estado", "intentada"])
        try:
            estado, respuesta = entregar(asunto, texto, envio.correo)
            envio.estado = estado
            envio.respuesta = respuesta[:4000]
            envio.enviada = timezone.now() if estado == Alerta.Estado.ENVIADA else None
        except Exception as exc:
            envio.estado = Alerta.Estado.INCIERTA
            envio.respuesta = respuesta_segura(exc)
        # Si guardar un resultado falla, no se reenvía: queda una reserva para revisión.
        envio.save(update_fields=["estado", "respuesta", "enviada"])
    fallidos = sum(e.estado == Alerta.Estado.INCIERTA for e in envios)
    if fallidos:
        alerta.estado = Alerta.Estado.PARCIAL if fallidos < len(envios) else Alerta.Estado.INCIERTA
    else:
        alerta.estado = Alerta.Estado.SIMULADA if all(e.estado == Alerta.Estado.SIMULADA for e in envios) else Alerta.Estado.ENVIADA
    alerta.respuesta = envios[0].respuesta if len(envios) == 1 else "\n".join(f"{e.correo}: {e.estado} · {e.respuesta}" for e in envios)[:4000]
    alerta.enviada = timezone.now() if alerta.estado == Alerta.Estado.ENVIADA else None
    alerta.save(update_fields=["estado", "respuesta", "enviada"])
    auditar("PROCESAR_ALERTA", "Alerta", alerta.pk, {"estado": alerta.estado, "destinatarios": len(envios)})
    return {Alerta.Estado.ENVIADA: "enviada", Alerta.Estado.SIMULADA: "simulada", Alerta.Estado.PARCIAL: "parcial", Alerta.Estado.INCIERTA: "fallida"}[alerta.estado]

def procesar_alertas(hoy=None):
    hoy = hoy or timezone.localdate()
    resultados = {"enviada": 0, "simulada": 0, "omitida": 0, "fallida": 0, "parcial": 0}
    for dias in (45, 30, 15):
        ids = Servicio.objects.filter(fecha_vencimiento=hoy + timedelta(days=dias), requiere_validacion=False).exclude(periodicidad=Servicio.Periodicidad.PERMANENTE).exclude(estado=Servicio.Estado.CANCELADO).values_list("pk", flat=True)
        for pk in ids:
            resultados[enviar_alerta(pk, str(dias), hoy)] += 1
    return resultados
