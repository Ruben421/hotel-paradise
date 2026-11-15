from decimal import Decimal, InvalidOperation

from django import forms, template

register = template.Library()


@register.filter
def campo(field, extra=""):
    """Renderiza un widget con las clases de Bootstrap correctas."""
    widget = field.field.widget
    if isinstance(widget, forms.CheckboxInput):
        css = "form-check-input"
    elif isinstance(widget, forms.Select):
        css = "form-select"
    else:
        css = "form-control"
    if field.errors:
        css += " is-invalid"
    if extra:
        css += f" {extra}"
    attrs = {"class": css}
    if field.errors:
        attrs["aria-describedby"] = f"{field.auto_id}_error"
    return field.as_widget(attrs=attrs)


@register.filter
def es_checkbox(field):
    return isinstance(field.field.widget, forms.CheckboxInput)


@register.filter
def moneda(valor):
    try:
        valor = Decimal(valor or 0)
    except (InvalidOperation, TypeError):
        return valor
    return f"${valor:,.2f}"


@register.filter
def porcentaje(valor, total):
    try:
        return round(float(valor) * 100 / float(total)) if total else 0
    except (TypeError, ValueError):
        return 0


@register.simple_tag(takes_context=True)
def qs(context, **kwargs):
    """Conserva los filtros GET al cambiar de página: ?{% qs page=2 %}"""
    params = context["request"].GET.copy()
    for k, v in kwargs.items():
        if v in (None, ""):
            params.pop(k, None)
        else:
            params[k] = v
    return params.urlencode()


ESTADO_CLASES = {
    "pendiente": "estado-pendiente",
    "confirmada": "estado-confirmada",
    "finalizada": "estado-finalizada",
    "cancelada": "estado-cancelada",
}


@register.filter
def estado_clase(estado):
    return ESTADO_CLASES.get(estado, "")
