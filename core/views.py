from datetime import timedelta
from pathlib import Path
from urllib.parse import urlencode
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import OuterRef, ProtectedError, Q, Subquery
from django.http import FileResponse, Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from . import auth
from .forms import AccesoForm, DocumentoForm, FiltrosForm, GestionForm, RenovacionForm, ServicioForm
from .models import Alerta, Auditoria, Documento, Gestion, Renovacion, Servicio, Tramite
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
        auditar("ACCESO_FALLIDO", "Usuario", 1)
        return super().form_invalid(form)
    def form_valid(self, form):
        auth.limpiar(self.request)
        auditar("INICIAR_SESION", "Usuario", 1)
        return super().form_valid(form)

class SalirView(LogoutView):
    def post(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            auditar("CERRAR_SESION", "Usuario", 1)
        return super().post(request, *args, **kwargs)

@method_decorator(login_required, name="dispatch")
class ContrasenaView(PasswordChangeView):
    template_name = "registration/password_change_form.html"
    success_url = reverse_lazy("password_change")
    def form_valid(self, form):
        response = super().form_valid(form)
        auditar("CAMBIAR_CONTRASENA", "Usuario", 1)
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
    return render(request, "core/dashboard.html", {"metricas": metricas, "servicios": proximos})

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
    return render(request, "core/detalle.html", {"servicio": servicio, "gestiones": servicio.gestiones.all(), "renovaciones": servicio.renovaciones.all(), "documentos": servicio.documentos.all(), "alertas": servicio.alertas.all(), "urgencia_registrada": servicio.alertas.filter(ciclo=servicio.ciclo, tipo=Alerta.Tipo.URGENTE).exists()})

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
    return FileResponse(archivo, as_attachment=True, filename=documento.nombre_original, content_type="application/pdf")

@login_required
@require_POST
def alerta_urgente(request, pk):
    get_object_or_404(Servicio, pk=pk)
    resultado = enviar_alerta(pk, Alerta.Tipo.URGENTE)
    auditar("ALERTA_URGENTE", "Servicio", pk, {"resultado": resultado})
    textos = {"enviada": "Aviso aceptado por el servidor SMTP.", "simulada": "Aviso simulado. EMAIL_MODE=console: no se envió correo real.", "omitida": "Ya existe un aviso de urgencia de este ciclo o el servicio no cumple las condiciones.", "fallida": "Envío fallido o incierto. Revise Alertas antes de intervenir."}
    (messages.error if resultado == "fallida" else messages.info)(request, textos[resultado])
    return redirect("servicio_detalle", pk=pk)

@login_required
def lista_gestiones(request):
    ultimo = Gestion.objects.filter(servicio=OuterRef("servicio_id")).order_by("-id").values("id")[:1]
    qs = Gestion.objects.filter(pk=Subquery(ultimo)).exclude(servicio__tramite__in=[Tramite.RENOVADO, Tramite.CANCELADO]).select_related("servicio").order_by("proximo_seguimiento", "-id")
    return render(request, "core/gestiones.html", {"pagina": Paginator(qs, 25).get_page(request.GET.get("page"))})

@login_required
def lista_alertas(request):
    return render(request, "core/alertas.html", {"pagina": Paginator(Alerta.objects.select_related("servicio"), 25).get_page(request.GET.get("page"))})

@login_required
def lista_auditoria(request):
    return render(request, "core/auditoria.html", {"pagina": Paginator(Auditoria.objects.all(), 25).get_page(request.GET.get("page"))})

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
