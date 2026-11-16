from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from .models import DestinatarioAlerta, Documento, Gestion, Servicio, Usuario

class EstiloFormulario:
    def estilizar(self):
        for field in self.fields.values():
            css = "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-select" if isinstance(field.widget, forms.Select) else "form-control"
            field.widget.attrs["class"] = css
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs["rows"] = 3
            if isinstance(field, forms.DateField):
                field.widget = forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": css})
                field.input_formats = ["%Y-%m-%d"]

class AccesoForm(EstiloFormulario, AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Nombre de usuario"
        self.estilizar()

class ServicioForm(EstiloFormulario, forms.ModelForm):
    version = forms.IntegerField(widget=forms.HiddenInput, required=False)
    class Meta:
        model = Servicio
        fields = ["codigo", "nombre", "categoria", "descripcion", "proveedor", "contacto_nombre", "contacto_telefono", "contacto_correo", "capacidad", "contrato", "fecha_inicio", "fecha_vencimiento", "periodicidad", "monto", "moneda", "estado", "tramite", "observaciones", "requiere_validacion", "motivo_validacion"]
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial["version"] = self.instance.version
        self.estilizar()

    @property
    def secciones(self):
        grupos = [
            ("1. Identificación del servicio", "Registre el código, nombre y clasificación que utilizará en el inventario.", ["codigo", "nombre", "categoria", "descripcion", "estado"]),
            ("2. Proveedor y contacto", "Datos para realizar consultas y dar seguimiento al proveedor.", ["proveedor", "contacto_nombre", "contacto_telefono", "contacto_correo"]),
            ("3. Contratación y vigencia", "Deje vacíos los datos que no estén confirmados en la documentación.", ["capacidad", "contrato", "fecha_inicio", "fecha_vencimiento", "periodicidad", "monto", "moneda"]),
            ("4. Trámite y validación", "El cambio de estado se registra con su usuario. Marque las fechas que deban revisarse.", ["tramite", "observaciones", "requiere_validacion", "motivo_validacion"]),
        ]
        return [{"titulo": titulo, "descripcion": descripcion, "campos": [self[name] for name in names]} for titulo, descripcion, names in grupos]

class GestionForm(EstiloFormulario, forms.ModelForm):
    class Meta:
        model = Gestion
        fields = ["fecha", "tipo", "descripcion", "tramite", "expediente", "proximo_seguimiento", "observaciones"]
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.estilizar()

class RenovacionForm(EstiloFormulario, forms.Form):
    nuevo_inicio = forms.DateField(label="Nueva fecha de inicio", required=False)
    nuevo_vencimiento = forms.DateField(label="Nueva fecha de vencimiento")
    observaciones = forms.CharField(widget=forms.Textarea, required=False, max_length=10000)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.estilizar()
    def clean(self):
        data = super().clean()
        if data.get("nuevo_inicio") and data.get("nuevo_vencimiento") and data["nuevo_inicio"] > data["nuevo_vencimiento"]:
            raise ValidationError("El nuevo vencimiento no puede ser anterior al nuevo inicio.")
        return data

class DocumentoForm(EstiloFormulario, forms.ModelForm):
    class Meta:
        model = Documento
        fields = ["archivo", "gestion"]
    def __init__(self, *args, servicio, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["archivo"].label = f"Documento PDF (máximo {settings.UPLOAD_MAX_MB} MB)"
        self.fields["archivo"].widget.attrs["accept"] = ".pdf,application/pdf"
        self.fields["gestion"].queryset = servicio.gestiones.all()
        self.fields["gestion"].label = "Asociar a gestión (opcional)"
        self.estilizar()
    def clean_archivo(self):
        file = self.cleaned_data["archivo"]
        if file.size > settings.UPLOAD_MAX_MB * 1024 * 1024:
            raise ValidationError("El PDF supera el tamaño permitido.")
        if not file.name.lower().endswith(".pdf") or file.content_type != "application/pdf":
            raise ValidationError("Solo se permiten documentos PDF.")
        header = file.read(5)
        file.seek(max(0, file.size - 2048))
        tail = file.read(2048)
        file.seek(0)
        if header != b"%PDF-" or b"%%EOF" not in tail:
            raise ValidationError("El archivo no tiene una estructura PDF reconocible.")
        return file

class FiltrosForm(EstiloFormulario, forms.Form):
    servicio = forms.CharField(label="Servicio o código", required=False, max_length=255)
    proveedor = forms.CharField(required=False, max_length=255)
    categoria = forms.CharField(label="Categoría", required=False, max_length=255)
    estado = forms.ChoiceField(required=False, choices=[("", "Todos"), *Servicio.Estado.choices])
    tramite = forms.ChoiceField(label="Situación del trámite", required=False, choices=[("", "Todos"), *Servicio._meta.get_field("tramite").choices])
    desde = forms.DateField(label="Vence desde", required=False)
    hasta = forms.DateField(label="Vence hasta", required=False)
    tipo = forms.ChoiceField(label="Reporte", required=False, choices=[("", "Todos los servicios"), ("proximas", "Renovaciones en 45 días"), ("pendientes", "Gestiones pendientes")])
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.estilizar()
    def clean(self):
        data = super().clean()
        if data.get("desde") and data.get("hasta") and data["desde"] > data["hasta"]:
            raise ValidationError("La fecha inicial debe ser anterior o igual a la final.")
        return data


class DestinatarioForm(EstiloFormulario, forms.ModelForm):
    class Meta:
        model = DestinatarioAlerta
        fields = ["nombre", "correo", "activo"]
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.estilizar()
    def clean_correo(self):
        correo = self.cleaned_data["correo"].strip().casefold()
        qs = DestinatarioAlerta.objects.filter(correo__iexact=correo)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("Este correo ya está registrado. Edítelo o actívelo desde la lista.")
        return correo


class UsuarioForm(EstiloFormulario, forms.ModelForm):
    password1 = forms.CharField(label="Contraseña inicial", widget=forms.PasswordInput, required=False, max_length=128)
    password2 = forms.CharField(label="Confirmar contraseña inicial", widget=forms.PasswordInput, required=False, max_length=128)
    class Meta:
        model = Usuario
        fields = ["username", "first_name", "last_name", "email", "rol", "is_active"]
        labels = {"username": "Nombre de usuario", "first_name": "Nombres", "last_name": "Apellidos", "email": "Correo institucional", "rol": "Perfil de acceso", "is_active": "Usuario activo"}
        help_texts = {"username": "Se utiliza para iniciar sesión.", "rol": "Administrador: todos los módulos. Gestor: operación del inventario. Consulta: solo lectura."}
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields.pop("password1")
            self.fields.pop("password2")
        else:
            self.fields["password1"].required = True
            self.fields["password2"].required = True
            self.fields["password1"].help_text = "Mínimo 14 caracteres. Se guardará protegida con Argon2."
        self.estilizar()
    def clean_username(self):
        value = self.cleaned_data["username"].strip()
        if Usuario.objects.filter(username__iexact=value).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Ese nombre de usuario ya existe.")
        return value
    def clean_email(self):
        value = self.cleaned_data["email"].strip().casefold()
        if Usuario.objects.filter(email__iexact=value).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Ese correo ya está registrado.")
        return value
    def clean(self):
        data = super().clean()
        if not self.instance.pk:
            if data.get("password1") != data.get("password2"):
                self.add_error("password2", "Las contraseñas no coinciden.")
            if data.get("password1"):
                from django.contrib.auth.password_validation import validate_password
                candidate = Usuario(username=data.get("username", ""), email=data.get("email", ""), first_name=data.get("first_name", ""), last_name=data.get("last_name", ""))
                try:
                    validate_password(data["password1"], candidate)
                except ValidationError as exc:
                    self.add_error("password1", exc)
        return data
    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.is_superuser = usuario.rol == Usuario.Rol.ADMINISTRADOR
        usuario.is_staff = usuario.is_superuser
        if self.cleaned_data.get("password1"):
            usuario.set_password(self.cleaned_data["password1"])
        if commit:
            usuario.save()
        return usuario
