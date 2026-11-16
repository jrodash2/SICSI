from django.shortcuts import render
from .actor import contexto_usuario

class PrivateResponseMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    def __call__(self, request):
        actor = request.user if request.user.is_authenticated else None
        with contexto_usuario(actor, "web"):
            response = self.get_response(request)
        response["Cache-Control"] = "no-store, private"
        response["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        return response
    def process_view(self, request, view_func, view_args, view_kwargs):
        if not request.user.is_authenticated or request.resolver_match is None:
            return None
        nombre = request.resolver_match.url_name or ""
        administracion = {"actas", "acta_detalle", "acta_descargar", "auditoria", "destinatarios", "destinatario_crear", "destinatario_editar", "destinatario_estado", "destinatario_eliminar", "correo_prueba", "correo_prueba_admin", "usuarios", "usuario_crear", "usuario_editar", "usuario_estado", "usuario_password"}
        gestion = {"servicio_crear", "servicio_editar", "servicio_eliminar", "gestion_crear", "servicio_renovar", "documento_crear", "alerta_urgente"}
        permitido = (nombre not in administracion or request.user.es_administrador) and (nombre not in gestion or request.user.puede_editar)
        if not permitido:
            from .services import auditar
            auditar("ACCESO_DENEGADO", "Ruta", detalle={"ruta": request.path, "metodo": request.method})
            return render(request, "core/permiso_denegado.html", status=403)
        return None
