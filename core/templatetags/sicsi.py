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
