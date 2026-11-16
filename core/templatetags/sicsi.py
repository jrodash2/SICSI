import json
from django import template
register = template.Library()

@register.filter
def campo(field):
    tipo = getattr(field.field.widget, "input_type", "")
    css = "form-check-input" if tipo == "checkbox" else "form-select" if field.field.widget.__class__.__name__ == "Select" else "form-control"
    return field.as_widget(attrs={"class": css})

@register.filter
def bonito(value):
    return json.dumps(value, ensure_ascii=False, indent=2)

@register.simple_tag(takes_context=True)
def activo(context, names):
    request = context["request"]
    return "active" if request.resolver_match and request.resolver_match.url_name in names.split(",") else ""


@register.simple_tag
def icono(nombre, size=20):
    from django.utils.html import format_html
    from django.utils.safestring import mark_safe
    paths = {
        "usuarios": '<circle cx="9" cy="8" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3M17 5a3 3 0 0 1 0 6M21 21v-3a6 6 0 0 0-4-5"/>',
        "dashboard": '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
        "servicios": '<rect x="3" y="3" width="18" height="7" rx="2"/><rect x="3" y="14" width="18" height="7" rx="2"/><path d="M7 6.5h.01M7 17.5h.01M12 6.5h5M12 17.5h5"/>',
        "reloj": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
        "alertas": '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>',
        "correo": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m4 6 8 7 8-7"/>',
        "reportes": '<path d="M4 3v18h17M9 16v-5M14 16V7M19 16v-8"/>',
        "documento": '<path d="M14 2H5a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V9zM14 2v7h7M7 13h10M7 17h7"/>',
        "auditoria": '<path d="M9 5H5a2 2 0 0 0-2 2v13h16V7a2 2 0 0 0-2-2h-4"/><rect x="8" y="2" width="6" height="6" rx="1"/><path d="m7 14 2 2 5-5"/>',
        "seguridad": '<path d="m12 2 8 4v6c0 5-8 10-8 10S4 17 4 12V6zM9 12l2 2 4-4"/>',
        "salir": '<path d="M9 4H4v16h5M14 8l4 4-4 4M8 12h10"/>',
        "buscar": '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
        "calendario": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 2v6M17 2v6M3 11h18M7 15h2M13 15h2"/>',
        "mas": '<path d="M12 5v14M5 12h14"/>',
        "flecha": '<path d="M4 12h16m-6-6 6 6-6 6"/>',
        "abajo": '<path d="m6 9 6 6 6-6"/>',
        "menu": '<path d="M4 6h16M4 12h16M4 18h16"/>',
        "check": '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
        "puntos": '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
        "editar": '<path d="m16 3 5 5-12 12H4v-5zM13 6l5 5"/>',
        "papelera": '<path d="M3 6h18M8 6V3h8v3M5 6l1 15h12l1-15M10 10v7M14 10v7"/>',
        "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
    }
    size = max(12, min(64, int(size)))
    return format_html('<svg class="icon" width="{}" height="{}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{}</svg>', size, size, mark_safe(paths.get(nombre, paths["dashboard"])))


@register.simple_tag
def modo_correo():
    from django.conf import settings
    return "SMTP" if settings.EMAIL_MODE == "smtp" else "Consola"
