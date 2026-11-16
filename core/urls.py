from django.urls import path
from . import views
urlpatterns = [
    path("acceso/", views.AccesoView.as_view(), name="login"),
    path("salir/", views.SalirView.as_view(), name="logout"),
    path("seguridad/", views.ContrasenaView.as_view(), name="password_change"),
    path("", views.dashboard, name="dashboard"),
    path("servicios/", views.lista_servicios, name="servicios"),
    path("servicios/nuevo/", views.crear_servicio, name="servicio_crear"),
    path("servicios/<int:pk>/", views.detalle_servicio, name="servicio_detalle"),
    path("servicios/<int:pk>/editar/", views.editar_servicio, name="servicio_editar"),
    path("servicios/<int:pk>/eliminar/", views.eliminar_servicio, name="servicio_eliminar"),
    path("servicios/<int:pk>/gestion/", views.crear_gestion, name="gestion_crear"),
    path("servicios/<int:pk>/renovar/", views.confirmar_renovacion, name="servicio_renovar"),
    path("servicios/<int:pk>/adjuntar/", views.adjuntar_documento, name="documento_crear"),
    path("servicios/<int:pk>/urgencia/", views.alerta_urgente, name="alerta_urgente"),
    path("documentos/<int:pk>/", views.descargar_documento, name="documento_descargar"),
    path("gestiones/", views.lista_gestiones, name="gestiones"),
    path("alertas/", views.lista_alertas, name="alertas"),
    path("auditoria/", views.lista_auditoria, name="auditoria"),
    path("reportes/", views.reportes, name="reportes"),
    path("reportes/<str:formato>/", views.exportar, name="exportar"),
]
