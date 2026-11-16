from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from .models import Documento, Gestion, Servicio

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
        self.fields["username"].label = "Usuario administrador"
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
