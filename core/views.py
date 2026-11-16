from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import OuterRef, ProtectedError, Q, Subquery
from django.http import FileResponse, Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from . import auth
from .actor import contexto_usuario
from .forms import AccesoForm, DestinatarioForm, DocumentoForm, FiltrosForm, GestionForm, RenovacionForm, ServicioForm, UsuarioForm
from .models import Alerta, Auditoria, DestinatarioAlerta, Documento, Gestion, Renovacion, Servicio, Tramite, Usuario
from .services import auditar, enviar_alerta, instantanea, registrar_gestion, renovar

class AccesoView(LoginView):
    template_name = "registration/login.html"
    authentication_form = AccesoForm
    redirect_authenticated_user = True
    def post(self, request, *args, **kwargs):
        if auth.bloqueado(request):
            form = self.authentication_form(request=request, data={})
            form.add_error(None, "Demasiados intentos fallidos. Espere 15 minutos.")
            return self.render_to_response(self.get_context_data(form=form), status=429)
        return super().post(request, *args, **kwargs)
    def form_invalid(self, form):
        auth.fallo(self.request)
        auditar("ACCESO_FALLIDO", "Usuario")
        return super().form_invalid(form)
    def form_valid(self, form):
        auth.limpiar(self.request)
        with contexto_usuario(form.get_user(), "web"):
            auditar("INICIAR_SESION", "Usuario", form.get_user().pk, usuario=form.get_user())
            return super().form_valid(form)

class SalirView(LogoutView):
    def post(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            auditar("CERRAR_SESION", "Usuario", request.user.pk)
        return super().post(request, *args, **kwargs)

@method_decorator(login_required, name="dispatch")
class ContrasenaView(PasswordChangeView):
    template_name = "registration/password_change_form.html"
    success_url = reverse_lazy("password_change")
    def form_valid(self, form):
        response = super().form_valid(form)
        auditar("CAMBIAR_CONTRASENA", "Usuario", self.request.user.pk)
        messages.success(self.request, "Contraseña actualizada. Las demás sesiones dejaron de tener acceso.")
        return response

def render_form(request, form, titulo, servicio=None):
    return render(request, "core/form.html", {"form": form, "titulo": titulo, "servicio": servicio})

@login_required
def dashboard(request):
    todos = list(Servicio.objects.all())
    calculables = [(s, s.dias) for s in todos if s.dias is not None]
    pendientes = sum(s.tramite not in [Tramite.RENOVADO, Tramite.CANCELADO] for s in todos)
    metricas = [("Total de servicios", len(todos), "Inventario institucional", ""), ("Vencidos", sum(d < 0 for _, d in calculables), "Sin renovación del ciclo vigente", "danger"), ("Vencen en 0–15 días", sum(0 <= d <= 15 for _, d in calculables), "Atención prioritaria", "danger"), ("Vencen en 16–30 días", sum(16 <= d <= 30 for _, d in calculables), "Planifique la renovación", ""), ("Vencen en 31–45 días", sum(31 <= d <= 45 for _, d in calculables), "Seguimiento preventivo", ""), ("Sin fecha confirmada", sum(s.periodicidad != Servicio.Periodicidad.PERMANENTE and (not s.fecha_vencimiento or s.requiere_validacion) for s in todos), "Fechas pendientes de revisión", ""), ("Gestiones pendientes", pendientes, "Trámites de servicios sin cierre", ""), ("Renovaciones completadas", Renovacion.objects.count(), "Historial de ciclos renovados", "")]
    proximos = sorted((s for s, _ in calculables), key=lambda s: s.fecha_vencimiento)[:20]
    from django.db.models import Count
    from django.db.models.functions import TruncMonth
    etiquetas = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    hoy = timezone.localdate()
    serial = hoy.year * 12 + hoy.month - 1
    meses = [divmod(serial - i, 12) for i in range(5, -1, -1)]
    inicio = timezone.make_aware(datetime(meses[0][0], meses[0][1] + 1, 1))
    renovaciones_mes = {(item["mes"].year, item["mes"].month): item["total"] for item in Renovacion.objects.filter(creado__gte=inicio).annotate(mes=TruncMonth("creado")).values("mes").annotate(total=Count("id"))}
    maximo = max([renovaciones_mes.get((a, m + 1), 0) for a, m in meses] + [1])
    barras = [{"mes": etiquetas[m], "anio": a, "total": renovaciones_mes.get((a, m + 1), 0), "alto": round(renovaciones_mes.get((a, m + 1), 0) / maximo * 100)} for a, m in meses]
    grupos = [("Vencidos", sum(d < 0 for _, d in calculables), "#ef6479"), ("0–15 días", sum(0 <= d <= 15 for _, d in calculables), "#f6ad55"), ("16–30 días", sum(16 <= d <= 30 for _, d in calculables), "#5d8dee"), ("31–45 días", sum(31 <= d <= 45 for _, d in calculables), "#88c9dd"), ("Más de 45 días", sum(d > 45 for _, d in calculables), "#63ba9e")]
    segmentos = []
    acumulado = 0
    for nombre, cantidad, color in grupos:
        porcentaje = cantidad / len(calculables) * 100 if calculables else 0
        segmentos.append({"nombre": nombre, "cantidad": cantidad, "color": color, "porcentaje": round(porcentaje, 2), "offset": round(-acumulado, 2)})
        acumulado += porcentaje
    seguimientos = Gestion.objects.filter(pk=Subquery(Gestion.objects.filter(servicio=OuterRef("servicio_id")).order_by("-id").values("pk")[:1])).exclude(servicio__tramite__in=[Tramite.RENOVADO, Tramite.CANCELADO]).filter(proximo_seguimiento__isnull=False).select_related("servicio").order_by("proximo_seguimiento")[:4]
    return render(request, "core/dashboard.html", {"metricas": metricas, "servicios": proximos[:6], "segmentos": segmentos, "calculables": len(calculables), "barras": barras, "seguimientos": seguimientos, "actividad": Auditoria.objects.exclude(accion__in=["ACCESO_FALLIDO", "CONSULTAR_ACTA"])[:5], "pendientes": pendientes})

def servicios_filtrados(params):
    form = FiltrosForm(params or None)
    qs = Servicio.objects.order_by("fecha_vencimiento", "nombre")
    if not form.is_bound:
        return form, qs
    if not form.is_valid():
        return form, qs.none()
    f = form.cleaned_data
    if f.get("servicio"):
        qs = qs.filter(Q(codigo__icontains=f["servicio"]) | Q(nombre__icontains=f["servicio"]))
    for field in ["proveedor", "categoria", "estado", "tramite"]:
        if f.get(field):
            qs = qs.filter(**{field + "__iexact": f[field]})
    if f.get("desde"):
        qs = qs.filter(fecha_vencimiento__gte=f["desde"])
    if f.get("hasta"):
        qs = qs.filter(fecha_vencimiento__lte=f["hasta"])
    if f.get("tipo") == "proximas":
        hoy = timezone.localdate()
        qs = qs.filter(fecha_vencimiento__range=(hoy, hoy + timedelta(days=45)), requiere_validacion=False).exclude(periodicidad=Servicio.Periodicidad.PERMANENTE).exclude(estado=Servicio.Estado.CANCELADO)
    if f.get("tipo") == "pendientes":
        qs = qs.exclude(tramite__in=[Tramite.RENOVADO, Tramite.CANCELADO])
    return form, qs

@login_required
def lista_servicios(request):
    form, qs = servicios_filtrados(request.GET)
    return render(request, "core/lista.html", {"filtros": form, "pagina": Paginator(qs, 25).get_page(request.GET.get("page")), "consulta": urlencode({k: v for k, v in request.GET.items() if k != "page"})})

@login_required
def detalle_servicio(request, pk):
    servicio = get_object_or_404(Servicio, pk=pk)
    relacionados = Q(entidad="Servicio", registro_id=pk) | Q(entidad="Gestion", registro_id__in=servicio.gestiones.values("pk")) | Q(entidad="Documento", registro_id__in=servicio.documentos.values("pk")) | Q(entidad="Alerta", registro_id__in=servicio.alertas.values("pk"))
    historial = Paginator(Auditoria.objects.filter(relacionados), 25).get_page(request.GET.get("page"))
    return render(request, "core/detalle.html", {"historial_acciones": historial, "servicio": servicio, "gestiones": servicio.gestiones.all(), "renovaciones": servicio.renovaciones.all(), "documentos": servicio.documentos.all(), "alertas": servicio.alertas.prefetch_related("envios").all(), "urgencia_registrada": servicio.alertas.filter(ciclo=servicio.ciclo, tipo=Alerta.Tipo.URGENTE).exists()})

@login_required
def crear_servicio(request):
    form = ServicioForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            servicio = form.save()
            auditar("CREAR", "Servicio", servicio.pk, instantanea(servicio))
        messages.success(request, "Servicio registrado.")
        return redirect("servicio_detalle", pk=servicio.pk)
    return render_form(request, form, "Nuevo servicio")

@login_required
def editar_servicio(request, pk):
    servicio = get_object_or_404(Servicio, pk=pk)
    form = ServicioForm(request.POST or None, instance=servicio)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                actual = Servicio.objects.select_for_update().get(pk=pk)
                if form.cleaned_data.get("version") != actual.version:
                    raise ValidationError("El servicio cambió desde que abrió este formulario. Recargue antes de editar.")
                if actual.fecha_vencimiento != form.cleaned_data["fecha_vencimiento"] and actual.alertas.filter(ciclo=actual.ciclo).exists():
                    raise ValidationError("Este ciclo ya tiene alertas. Use Confirmar renovación para cambiar la fecha.")
                anterior = instantanea(actual)
                if actual.tramite != form.cleaned_data["tramite"]:
                    Gestion.objects.create(servicio=actual, tipo="Cambio de estado", descripcion=f"{actual.tramite} → {form.cleaned_data['tramite']}", tramite=form.cleaned_data["tramite"])
                for campo in form.Meta.fields:
                    setattr(actual, campo, form.cleaned_data[campo])
                actual.version += 1
                actual.save()
                auditar("EDITAR", "Servicio", pk, {"anterior": anterior, "nuevo": instantanea(actual)})
            messages.success(request, "Servicio actualizado.")
            return redirect("servicio_detalle", pk=pk)
        except ValidationError as exc:
            form.add_error(None, exc)
    return render_form(request, form, "Editar servicio", servicio)

@login_required
def eliminar_servicio(request, pk):
    servicio = get_object_or_404(Servicio, pk=pk)
    if request.method == "POST":
        try:
            with transaction.atomic():
                servicio = Servicio.objects.select_for_update().get(pk=pk)
                auditar("ELIMINAR", "Servicio", pk, instantanea(servicio))
                servicio.delete()
            messages.success(request, "Servicio eliminado.")
            return redirect("servicios")
        except ProtectedError:
            messages.error(request, "El servicio tiene historial o documentos. Cambie su estado a Cancelado para conservarlos.")
            return redirect("servicio_detalle", pk=pk)
    return render(request, "core/confirmar.html", {"servicio": servicio, "titulo": "Eliminar servicio", "texto": "Solo se eliminará si no tiene historial, alertas ni documentos. Para conservar sus registros, cambie el estado a Cancelado.", "boton": "Eliminar servicio"})

@login_required
def crear_gestion(request, pk):
    servicio = get_object_or_404(Servicio, pk=pk)
    form = GestionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        registrar_gestion(pk, form.cleaned_data)
        messages.success(request, "Gestión registrada en la bitácora.")
        return redirect("servicio_detalle", pk=pk)
    return render_form(request, form, "Registrar gestión", servicio)

@login_required
def confirmar_renovacion(request, pk):
    servicio = get_object_or_404(Servicio, pk=pk)
    form = RenovacionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            renovar(pk, form.cleaned_data)
            messages.success(request, "Renovación confirmada. Las fechas anteriores se conservaron en el historial.")
            return redirect("servicio_detalle", pk=pk)
        except ValidationError as exc:
            form.add_error(None, exc)
    return render_form(request, form, "Confirmar renovación", servicio)

@login_required
def adjuntar_documento(request, pk):
    servicio = get_object_or_404(Servicio, pk=pk)
    form = DocumentoForm(request.POST or None, request.FILES or None, servicio=servicio)
    if request.method == "POST" and form.is_valid():
        documento = form.save(commit=False)
        documento.servicio = servicio
        documento.nombre_original = Path(form.cleaned_data["archivo"].name).name[:255]
        documento.tamano = form.cleaned_data["archivo"].size
        try:
            with transaction.atomic():
                Servicio.objects.select_for_update().get(pk=pk)
                documento.save()
                auditar("ADJUNTAR_PDF", "Documento", documento.pk, {"servicio": pk, "nombre": documento.nombre_original})
        except Exception:
            if documento.archivo.name and getattr(documento.archivo, "_committed", False):
                documento.archivo.storage.delete(documento.archivo.name)
            raise
        messages.success(request, "Documento guardado de forma privada.")
        return redirect("servicio_detalle", pk=pk)
    return render_form(request, form, "Adjuntar PDF", servicio)

@login_required
def descargar_documento(request, pk):
    documento = get_object_or_404(Documento, pk=pk)
    try:
        archivo = documento.archivo.open("rb")
    except FileNotFoundError:
        raise Http404("Documento no disponible.")
    auditar("DESCARGAR_PDF", "Documento", documento.pk, {"servicio": documento.servicio_id})
    return FileResponse(archivo, as_attachment=True, filename=documento.nombre_original, content_type="application/pdf")

@login_required
@require_POST
def alerta_urgente(request, pk):
    get_object_or_404(Servicio, pk=pk)
    resultado = enviar_alerta(pk, Alerta.Tipo.URGENTE)
    auditar("ALERTA_URGENTE", "Servicio", pk, {"resultado": resultado})
    textos = {"enviada": "Aviso aceptado por el servidor SMTP.", "simulada": "Aviso simulado. EMAIL_MODE=console: no se envió correo real.", "omitida": "Ya existe un aviso de urgencia de este ciclo o el servicio no cumple las condiciones.", "fallida": "Envío fallido o incierto. Revise Alertas antes de intervenir.", "parcial": "Algunos destinatarios no recibieron confirmación. Revise el detalle de la alerta."}
    (messages.error if resultado in {"fallida", "parcial"} else messages.info)(request, textos[resultado])
    return redirect("servicio_detalle", pk=pk)

@login_required
def lista_gestiones(request):
    ultimo = Gestion.objects.filter(servicio=OuterRef("servicio_id")).order_by("-id").values("id")[:1]
    qs = Gestion.objects.filter(pk=Subquery(ultimo)).exclude(servicio__tramite__in=[Tramite.RENOVADO, Tramite.CANCELADO]).select_related("servicio").order_by("proximo_seguimiento", "-id")
    return render(request, "core/gestiones.html", {"pagina": Paginator(qs, 25).get_page(request.GET.get("page"))})

@login_required
def lista_alertas(request):
    return render(request, "core/alertas.html", {"pagina": Paginator(Alerta.objects.select_related("servicio").prefetch_related("envios"), 25).get_page(request.GET.get("page"))})

@login_required
def lista_auditoria(request):
    return render(request, "core/auditoria.html", {"pagina": Paginator(Auditoria.objects.select_related("usuario").all(), 25).get_page(request.GET.get("page"))})

@login_required
def reportes(request):
    form, qs = servicios_filtrados(request.GET)
    return render(request, "core/lista.html", {"es_reporte": True, "filtros": form, "pagina": Paginator(qs, 25).get_page(request.GET.get("page")), "consulta": urlencode({k: v for k, v in request.GET.items() if k != "page"})})

@login_required
def exportar(request, formato):
    form, qs = servicios_filtrados(request.GET)
    if form.is_bound and not form.is_valid():
        return HttpResponseBadRequest("Filtros inválidos. Revise las fechas y opciones del reporte.")
    if formato not in {"xlsx", "pdf"}:
        raise Http404
    from .reports import generar_reporte
    servicios = list(qs.prefetch_related("gestiones"))
    auditar("EXPORTAR", "Reporte", detalle={"formato": formato, "filtros": dict(request.GET.items()), "filas": len(servicios)})
    return generar_reporte(servicios, formato)


@login_required
def lista_actas(request):
    from .models import ActaEntrega
    return render(request, "core/actas.html", {"actas": ActaEntrega.objects.defer("archivo_cifrado", "contenido_cifrado")})

@login_required
def detalle_acta(request, pk):
    from .actas_crypto import descifrar_json
    from .models import ActaEntrega, ElementoActa
    acta = get_object_or_404(ActaEntrega, pk=pk)
    try:
        contenido = descifrar_json(acta.contenido_cifrado)
        catalogo = [{"registro": item, "celdas": descifrar_json(item.contenido_cifrado)["celdas_originales"]} for item in acta.elementos.filter(tipo=ElementoActa.Tipo.CATALOGO)]
    except ImproperlyConfigured:
        return render(request, "core/acta_error.html", status=503)
    auditar("CONSULTAR_ACTA", "ActaEntrega", acta.pk)
    return render(request, "core/acta_detalle.html", {"acta": acta, "contenido": contenido, "catalogo": catalogo, "servicios": acta.servicios.all()})

@login_required
def descargar_acta(request, pk):
    from hashlib import sha256
    from io import BytesIO
    from .actas_crypto import descifrar_bytes
    from .models import ActaEntrega
    acta = get_object_or_404(ActaEntrega, pk=pk)
    try:
        data = descifrar_bytes(acta.archivo_cifrado)
    except ImproperlyConfigured:
        return render(request, "core/acta_error.html", status=503)
    if sha256(data).hexdigest() != acta.sha256:
        return render(request, "core/acta_error.html", status=503)
    auditar("DESCARGAR_ACTA", "ActaEntrega", acta.pk)
    return FileResponse(BytesIO(data), as_attachment=True, filename=acta.nombre_archivo, content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


@login_required
def destinatarios(request):
    return render(request, "core/destinatarios.html", {"destinatarios": DestinatarioAlerta.objects.all(), "correo_administrador": request.user.email, "correos_administradores": ", ".join(Usuario.objects.filter(is_active=True, is_superuser=True).values_list("email", flat=True)), "cantidad_administradores": Usuario.objects.filter(is_active=True, is_superuser=True).count(), "correo_remitente": settings.DEFAULT_FROM_EMAIL, "smtp_host": settings.EMAIL_HOST, "smtp_port": settings.EMAIL_PORT, "smtp_real": settings.EMAIL_MODE == "smtp", "activos": DestinatarioAlerta.objects.filter(activo=True).count()})

@login_required
def destinatario_form(request, pk=None):
    item = get_object_or_404(DestinatarioAlerta, pk=pk) if pk is not None else None
    anterior = {"nombre": item.nombre, "correo": item.correo, "activo": item.activo} if item else {}
    form = DestinatarioForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                registro = form.save()
                auditar("EDITAR_DESTINATARIO" if pk else "CREAR_DESTINATARIO", "DestinatarioAlerta", registro.pk, {"anterior": anterior, "nuevo": {k: form.cleaned_data[k] for k in form.Meta.fields}})
            messages.success(request, "Destinatario guardado. Se aplicará a los próximos avisos.")
            return redirect("destinatarios")
        except IntegrityError:
            form.add_error("correo", "Este correo ya está registrado.")
    return render(request, "core/destinatario_form.html", {"form": form, "titulo": "Editar destinatario" if pk else "Añadir destinatario"})

@login_required
@require_POST
def destinatario_estado(request, pk):
    with transaction.atomic():
        item = get_object_or_404(DestinatarioAlerta.objects.select_for_update(), pk=pk)
        item.activo = not item.activo
        item.save(update_fields=["activo", "actualizado"])
        auditar("ESTADO_DESTINATARIO", "DestinatarioAlerta", item.pk, {"activo": item.activo})
    messages.success(request, "Estado actualizado para los próximos avisos.")
    return redirect("destinatarios")

@login_required
@require_POST
def destinatario_eliminar(request, pk):
    with transaction.atomic():
        item = get_object_or_404(DestinatarioAlerta, pk=pk)
        auditar("ELIMINAR_DESTINATARIO", "DestinatarioAlerta", item.pk, {"nombre": item.nombre, "correo": item.correo})
        item.delete()
    messages.success(request, "Destinatario eliminado. Se conserva el historial de envíos anteriores.")
    return redirect("destinatarios")

@login_required
@require_POST
def probar_correo(request, pk=None):
    from .mail import entregar, respuesta_segura
    item = get_object_or_404(DestinatarioAlerta, pk=pk, activo=True) if pk is not None else None
    correo = item.correo if item else request.user.email
    # Solo se envía cuando el administrador confirma el botón de prueba.
    try:
        estado, respuesta = entregar("SICSI · Prueba de notificaciones", "Este mensaje verifica el envío de correo de SICSI, Sección de Informática – UPCV. No corresponde a un vencimiento ni contiene datos del acta.", correo)
        auditar("PROBAR_CORREO", "DestinatarioAlerta", item.pk if item else None, {"correo": correo, "estado": estado, "respuesta": respuesta[:4000]})
        messages.success(request, "Correo de prueba aceptado por SMTP. Compruebe la bandeja del destinatario.") if estado == Alerta.Estado.ENVIADA else messages.warning(request, "Prueba simulada: EMAIL_MODE está en console y no se envió correo real.")
    except Exception as exc:
        auditar("PROBAR_CORREO", "DestinatarioAlerta", item.pk if item else None, {"correo": correo, "estado": "Fallido o incierto", "respuesta": respuesta_segura(exc)})
        messages.error(request, "No se confirmó el correo de prueba. Revise la configuración SMTP y el detalle en Auditoría.")
    return redirect("destinatarios")


def datos_usuario(usuario):
    return {"username": usuario.username, "nombres": usuario.first_name, "apellidos": usuario.last_name, "email": usuario.email, "rol": usuario.perfil, "activo": usuario.is_active}

@login_required
def usuarios(request):
    qs = Usuario.objects.all().order_by("username")
    buscar = request.GET.get("buscar", "").strip()[:150]
    if buscar:
        qs = qs.filter(Q(username__icontains=buscar) | Q(first_name__icontains=buscar) | Q(last_name__icontains=buscar) | Q(email__icontains=buscar))
    return render(request, "core/usuarios.html", {"pagina": Paginator(qs, 25).get_page(request.GET.get("page")), "buscar": buscar})

@login_required
def usuario_form(request, pk=None):
    objetivo = get_object_or_404(Usuario, pk=pk) if pk else None
    anterior = datos_usuario(objetivo) if objetivo else {}
    form = UsuarioForm(request.POST or None, instance=objetivo)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                administradores = list(Usuario.objects.select_for_update().filter(is_superuser=True, is_active=True).order_by("pk"))
                actual = Usuario.objects.select_for_update().get(pk=pk) if pk else None
                conserva_admin = form.cleaned_data["rol"] == Usuario.Rol.ADMINISTRADOR and form.cleaned_data["is_active"]
                if pk == request.user.pk and not conserva_admin:
                    raise ValidationError("No puedes desactivar tu propia cuenta ni quitarte el perfil de administrador.")
                if actual and actual.es_administrador and not conserva_admin and len(administradores) <= 1:
                    raise ValidationError("Debe permanecer al menos un administrador activo.")
                anterior = datos_usuario(actual) if actual else {}
                nuevo = form.save()
                auditar("EDITAR_USUARIO" if pk else "CREAR_USUARIO", "Usuario", nuevo.pk, {"anterior": anterior, "nuevo": datos_usuario(nuevo)})
            messages.success(request, "Usuario guardado. Los permisos se aplican en la siguiente solicitud.")
            return redirect("usuarios")
        except ValidationError as exc:
            form.add_error(None, exc)
        except IntegrityError:
            form.add_error(None, "El usuario o correo ya fue registrado. Revisa los datos.")
    return render(request, "core/usuario_form.html", {"form": form, "objetivo": objetivo, "titulo": "Editar usuario" if pk else "Crear usuario"})

@login_required
@require_POST
def usuario_estado(request, pk):
    try:
        with transaction.atomic():
            administradores = list(Usuario.objects.select_for_update().filter(is_superuser=True, is_active=True).order_by("pk"))
            objetivo = get_object_or_404(Usuario.objects.select_for_update(), pk=pk)
            if objetivo.pk == request.user.pk:
                raise ValidationError("No puedes desactivar tu propia cuenta.")
            if objetivo.es_administrador and len(administradores) <= 1:
                raise ValidationError("Debe permanecer al menos un administrador activo.")
            objetivo.is_active = not objetivo.is_active
            objetivo.save(update_fields=["is_active"])
            auditar("ESTADO_USUARIO", "Usuario", pk, {"activo": objetivo.is_active})
        messages.success(request, "Estado del usuario actualizado. Su historial se conserva.")
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    return redirect("usuarios")

@login_required
def usuario_password(request, pk):
    from django.contrib.auth.forms import SetPasswordForm
    objetivo = get_object_or_404(Usuario, pk=pk)
    if objetivo.pk == request.user.pk:
        return redirect("password_change")
    form = SetPasswordForm(objetivo, request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            form.save()
            auditar("RESTABLECER_CONTRASENA", "Usuario", pk, {"username": objetivo.username})
        messages.success(request, "Contraseña restablecida. Las sesiones anteriores de ese usuario dejaron de tener acceso.")
        return redirect("usuarios")
    return render(request, "core/usuario_form.html", {"form": form, "objetivo": objetivo, "titulo": "Restablecer contraseña"})
