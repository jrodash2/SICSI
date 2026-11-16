import uuid
from django.contrib.auth.models import AbstractUser, UserManager
from django.core.serializers.json import DjangoJSONEncoder
from django.core.exceptions import ValidationError
from django.conf import settings
from .actor import etiqueta_autor, nombre_usuario, origen_actual, usuario_actual
from django.db import models
from django.db.models import Q
from django.utils import timezone

class RegistroConAutor(models.Model):
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="%(class)s_creados")
    actualizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="%(class)s_actualizados")
    creado_por_nombre = models.CharField(max_length=320, blank=True, editable=False)
    actualizado_por_nombre = models.CharField(max_length=320, blank=True, editable=False)
    origen_registro = models.CharField(max_length=15, default="historico", editable=False)
    origen_actualizacion = models.CharField(max_length=15, default="historico", editable=False)
    class Meta:
        abstract = True
    def save(self, *args, **kwargs):
        actor = usuario_actual()
        campos = set()
        if self._state.adding:
            self.origen_registro = origen_actual()
            campos.add("origen_registro")
            if actor:
                self.creado_por = actor
                self.creado_por_nombre = nombre_usuario(actor)
                campos.update(["creado_por", "creado_por_nombre"])
        self.actualizado_por = actor
        self.actualizado_por_nombre = nombre_usuario(actor)
        self.origen_actualizacion = origen_actual()
        campos.update(["actualizado_por", "actualizado_por_nombre", "origen_actualizacion"])
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | campos
        return super().save(*args, **kwargs)
    @property
    def autor_creacion(self):
        return etiqueta_autor(self.creado_por_nombre, self.origen_registro)
    @property
    def autor_actualizacion(self):
        return etiqueta_autor(self.actualizado_por_nombre, self.origen_actualizacion)

class AdministradorManager(UserManager):
    # El nombre de la clase se conserva para las migraciones iniciales.
    def _create_user(self, username, email, password, **extra_fields):
        if not email:
            raise ValueError("Cada usuario necesita correo electrónico.")
        if extra_fields.get("is_superuser"):
            extra_fields["rol"] = "administrador"
        return super()._create_user(username, self.normalize_email(email).casefold(), password, **extra_fields)
    def get_by_natural_key(self, username):
        return self.get(username__iexact=username)

class Usuario(RegistroConAutor, AbstractUser):
    class Rol(models.TextChoices):
        ADMINISTRADOR = "administrador", "Administrador"
        GESTOR = "gestor", "Gestor"
        CONSULTA = "consulta", "Consulta"
    id = models.BigAutoField(primary_key=True)
    email = models.EmailField("correo electrónico", unique=True)
    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.CONSULTA)
    objects = AdministradorManager()
    class Meta:
        verbose_name = "usuario"
        constraints = [models.UniqueConstraint(models.functions.Lower("username"), name="nombre_usuario_sin_duplicados"), models.UniqueConstraint(models.functions.Lower("email"), name="correo_usuario_sin_duplicados")]
    @property
    def es_administrador(self):
        return self.is_active and self.is_superuser
    @property
    def puede_editar(self):
        return self.is_active and (self.is_superuser or self.rol == self.Rol.GESTOR)
    @property
    def perfil(self):
        return "Administrador" if self.is_superuser else self.get_rol_display()

class Tramite(models.TextChoices):
    PENDIENTE = "Pendiente", "Pendiente"
    COTIZACION = "Cotización solicitada", "Cotización solicitada"
    PREPARACION = "En preparación", "En preparación"
    COMPRAS = "Trasladado a Compras", "Trasladado a Compras"
    EN_TRAMITE = "En trámite", "En trámite"
    ESPERA = "En espera de aprobación", "En espera de aprobación"
    APROBADO = "Aprobado", "Aprobado"
    RENOVADO = "Renovado", "Renovado"
    CANCELADO = "Cancelado", "Cancelado"

class Servicio(RegistroConAutor):
    class Periodicidad(models.TextChoices):
        ANUAL = "anual", "Anual"
        MENSUAL = "mensual", "Mensual"
        PERMANENTE = "permanente", "Permanente"
        OTRA = "otra", "Otra"
        POR_DEFINIR = "por definir", "Por definir"
    class Estado(models.TextChoices):
        ACTIVO = "Activo", "Activo"
        SUSPENDIDO = "Suspendido", "Suspendido"
        CANCELADO = "Cancelado", "Cancelado"
    acta_origen = models.ForeignKey("ActaEntrega", on_delete=models.PROTECT, related_name="servicios", null=True, blank=True, editable=False)
    codigo = models.CharField("código", max_length=60, unique=True)
    nombre = models.CharField("nombre del servicio", max_length=255)
    categoria = models.CharField("categoría", max_length=255, blank=True)
    descripcion = models.TextField("descripción", blank=True, max_length=10000)
    proveedor = models.CharField(max_length=255, blank=True)
    contacto_nombre = models.CharField("nombre del contacto", max_length=255, blank=True)
    contacto_telefono = models.CharField("teléfono", max_length=80, blank=True)
    contacto_correo = models.EmailField("correo del contacto", blank=True)
    capacidad = models.CharField("licencias o capacidad contratada", max_length=255, blank=True)
    contrato = models.CharField("número de contrato", max_length=255, blank=True)
    fecha_inicio = models.DateField("fecha de inicio", null=True, blank=True)
    fecha_vencimiento = models.DateField("fecha de vencimiento", null=True, blank=True, db_index=True)
    periodicidad = models.CharField(max_length=20, choices=Periodicidad.choices, default=Periodicidad.POR_DEFINIR)
    monto = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    moneda = models.CharField("moneda ISO (GTQ, USD…)", max_length=3, blank=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ACTIVO)
    tramite = models.CharField("estado del trámite", max_length=40, choices=Tramite.choices, default=Tramite.PENDIENTE)
    observaciones = models.TextField(blank=True, max_length=10000)
    requiere_validacion = models.BooleanField("requiere validación de fechas", default=False)
    motivo_validacion = models.TextField("motivo de validación", blank=True, max_length=10000)
    ciclo = models.PositiveIntegerField(default=1, editable=False)
    version = models.PositiveIntegerField(default=1, editable=False)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ["nombre"]
        constraints = [models.CheckConstraint(condition=Q(monto__isnull=True) | Q(monto__gte=0), name="monto_no_negativo"), models.CheckConstraint(condition=Q(ciclo__gte=1), name="ciclo_positivo")]
    def __str__(self):
        return f"{self.codigo} · {self.nombre}"
    def clean(self):
        errors = {}
        if self.fecha_inicio and self.fecha_vencimiento and self.fecha_inicio > self.fecha_vencimiento and not self.requiere_validacion:
            errors["fecha_vencimiento"] = "El vencimiento es anterior al inicio. Corrija o marque para validación."
        if self.requiere_validacion and not self.motivo_validacion.strip():
            errors["motivo_validacion"] = "Explique qué fechas deben validarse."
        if self.moneda and (len(self.moneda) != 3 or not self.moneda.isalpha() or not self.moneda.isascii() or not self.moneda.isupper()):
            errors["moneda"] = "Use tres letras mayúsculas, por ejemplo GTQ o USD."
        if errors:
            raise ValidationError(errors)
    def dias_al_vencimiento(self, hoy=None):
        if self.periodicidad == self.Periodicidad.PERMANENTE or not self.fecha_vencimiento or self.requiere_validacion or self.estado == self.Estado.CANCELADO:
            return None
        return (self.fecha_vencimiento - (hoy or timezone.localdate())).days
    @property
    def dias(self):
        return self.dias_al_vencimiento()
    @property
    def urgente(self):
        return self.dias is not None and self.dias < 45

class Gestion(RegistroConAutor):
    servicio = models.ForeignKey(Servicio, on_delete=models.PROTECT, related_name="gestiones")
    fecha = models.DateField("fecha de gestión", default=timezone.localdate)
    tipo = models.CharField("tipo de gestión", max_length=255)
    descripcion = models.TextField("descripción", max_length=10000)
    tramite = models.CharField("estado del trámite", max_length=40, choices=Tramite.choices)
    expediente = models.CharField("número de expediente", max_length=255, blank=True)
    proximo_seguimiento = models.DateField("próxima fecha de seguimiento", null=True, blank=True)
    observaciones = models.TextField(blank=True, max_length=10000)
    creado = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["-id"]

class Renovacion(RegistroConAutor):
    servicio = models.ForeignKey(Servicio, on_delete=models.PROTECT, related_name="renovaciones")
    ciclo = models.PositiveIntegerField()
    inicio_anterior = models.DateField(null=True, blank=True)
    vencimiento_anterior = models.DateField(null=True, blank=True)
    nuevo_inicio = models.DateField(null=True, blank=True)
    nuevo_vencimiento = models.DateField()
    observaciones = models.TextField(blank=True, max_length=10000)
    creado = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["-id"]
        constraints = [models.UniqueConstraint(fields=["servicio", "ciclo"], name="renovacion_por_ciclo")]

def documento_path(instance, filename):
    return f"servicios/{instance.servicio_id}/{uuid.uuid4().hex}.pdf"

class Documento(RegistroConAutor):
    servicio = models.ForeignKey(Servicio, on_delete=models.PROTECT, related_name="documentos")
    gestion = models.ForeignKey(Gestion, on_delete=models.PROTECT, null=True, blank=True, related_name="documentos")
    archivo = models.FileField(upload_to=documento_path, max_length=255)
    nombre_original = models.CharField(max_length=255)
    tamano = models.PositiveIntegerField()
    creado = models.DateTimeField(auto_now_add=True)

class Alerta(RegistroConAutor):
    class Tipo(models.TextChoices):
        D45 = "45", "45 días"
        D30 = "30", "30 días"
        D15 = "15", "15 días"
        URGENTE = "urgente", "Urgencia inicial"
    class Estado(models.TextChoices):
        RESERVADA = "Reservada", "Reservada"
        ENVIANDO = "Enviando", "Enviando"
        ENVIADA = "Enviada", "Enviada (aceptada por SMTP)"
        INCIERTA = "Fallida o incierta", "Fallida o incierta"
        SIMULADA = "Simulada", "Simulada (sin SMTP)"
        PARCIAL = "Parcial", "Parcial (revisar destinatarios)"
    servicio = models.ForeignKey(Servicio, on_delete=models.PROTECT, related_name="alertas")
    ciclo = models.PositiveIntegerField()
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    fecha = models.DateField(default=timezone.localdate)
    destinatario = models.EmailField()
    estado = models.CharField(max_length=25, choices=Estado.choices, default=Estado.RESERVADA)
    respuesta = models.TextField(blank=True)
    intentada = models.DateTimeField(null=True, blank=True)
    enviada = models.DateTimeField(null=True, blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["-id"]
        constraints = [models.UniqueConstraint(fields=["servicio", "ciclo", "tipo"], name="alerta_servicio_ciclo_tipo")]

class Auditoria(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="eventos_auditoria")
    usuario_nombre = models.CharField(max_length=320, blank=True)
    origen = models.CharField(max_length=15, default="historico")
    @property
    def autor(self):
        return etiqueta_autor(self.usuario_nombre, self.origen)
    @property
    def accion_legible(self):
        nombres = {"CREAR": "Registro de servicio", "EDITAR": "Edición de servicio", "ELIMINAR": "Eliminación de servicio", "REGISTRAR_GESTION": "Registro de gestión", "RENOVAR": "Confirmación de renovación", "ADJUNTAR_PDF": "Carga de documento", "DESCARGAR_PDF": "Descarga de documento", "INICIAR_SESION": "Inicio de sesión", "CERRAR_SESION": "Cierre de sesión", "CAMBIAR_CONTRASENA": "Cambio de contraseña", "ACCESO_FALLIDO": "Intento de acceso fallido", "ACCESO_DENEGADO": "Operación sin permisos", "PROCESAR_ALERTA": "Procesamiento de alerta", "ALERTA_URGENTE": "Notificación de urgencia", "EXPORTAR": "Exportación de reporte", "CREAR_USUARIO": "Creación de usuario", "EDITAR_USUARIO": "Edición de usuario", "ESTADO_USUARIO": "Cambio de estado de usuario", "RESTABLECER_CONTRASENA": "Restablecimiento de contraseña", "IMPORTAR_ACTA": "Importación de acta", "IMPORTAR_DESDE_ACTA": "Registro desde acta", "CONSULTAR_ACTA": "Consulta de acta privada", "DESCARGAR_ACTA": "Descarga de acta privada", "PROBAR_CORREO": "Prueba de correo"}
        return nombres.get(self.accion, self.accion.replace("_", " ").capitalize())
    @property
    def origen_legible(self):
        return {"web": "Interfaz web", "consola": "Consola local", "sistema": "Proceso automático", "historico": "Histórico sin autor"}.get(self.origen, self.origen)
    accion = models.CharField(max_length=60)
    entidad = models.CharField(max_length=60)
    registro_id = models.PositiveBigIntegerField(null=True, blank=True)
    detalle = models.JSONField(default=dict, encoder=DjangoJSONEncoder)
    creado = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["-id"]

class IntentoAcceso(models.Model):
    clave = models.CharField(max_length=64, unique=True)
    fallos = models.PositiveIntegerField(default=0)
    ventana = models.DateTimeField(default=timezone.now)


class ActaEntrega(RegistroConAutor):
    nombre_archivo = models.CharField(max_length=255)
    sha256 = models.CharField(max_length=64, unique=True)
    fecha_documento = models.DateField(null=True, blank=True)
    resumen = models.JSONField(default=dict)
    archivo_cifrado = models.BinaryField(editable=False)
    contenido_cifrado = models.BinaryField(editable=False)
    creado = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["-id"]
    def __str__(self):
        return self.nombre_archivo

class ElementoActa(RegistroConAutor):
    class Tipo(models.TextChoices):
        CATALOGO = "catalogo", "Compra o licencia"
        ACCESO = "acceso", "Acceso o plataforma"
    acta = models.ForeignKey(ActaEntrega, on_delete=models.PROTECT, related_name="elementos")
    tipo = models.CharField(max_length=15, choices=Tipo.choices)
    orden = models.PositiveIntegerField()
    nombre = models.CharField(max_length=255)
    fecha_texto = models.CharField(max_length=255, blank=True)
    fecha_referencia = models.DateField(null=True, blank=True)
    requiere_validacion = models.BooleanField(default=False)
    motivo_validacion = models.TextField(blank=True)
    contenido_cifrado = models.BinaryField(editable=False)
    class Meta:
        ordering = ["orden"]
        constraints = [models.UniqueConstraint(fields=["acta", "tipo", "orden"], name="elemento_acta_unico")]


class DestinatarioAlerta(RegistroConAutor):
    nombre = models.CharField("nombre o área", max_length=150, blank=True)
    correo = models.EmailField("correo electrónico")
    activo = models.BooleanField("recibir notificaciones", default=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ["-activo", "correo"]
        constraints = [models.UniqueConstraint(models.functions.Lower("correo"), name="correo_destinatario_unico")]
    def __str__(self):
        return self.nombre or self.correo

class EnvioAlerta(RegistroConAutor):
    alerta = models.ForeignKey(Alerta, on_delete=models.PROTECT, related_name="envios")
    correo = models.EmailField()
    nombre = models.CharField(max_length=150, blank=True)
    estado = models.CharField(max_length=25, choices=Alerta.Estado.choices, default=Alerta.Estado.RESERVADA)
    respuesta = models.TextField(blank=True)
    intentada = models.DateTimeField(null=True, blank=True)
    enviada = models.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ["id"]
        constraints = [models.UniqueConstraint(fields=["alerta", "correo"], name="envio_unico_por_destinatario")]
