from datetime import date, timedelta

from django import forms

from clientes.models import Cliente
from habitaciones.models import Habitacion

from .models import Reservacion

DATE = {"type": "date"}


class ReservacionForm(forms.ModelForm):
    class Meta:
        model = Reservacion
        fields = ["cliente", "habitacion", "fecha_entrada", "fecha_salida", "huespedes", "notas"]
        widgets = {
            "fecha_entrada": forms.DateInput(attrs=DATE, format="%Y-%m-%d"),
            "fecha_salida": forms.DateInput(attrs=DATE, format="%Y-%m-%d"),
            "huespedes": forms.NumberInput(attrs={"min": 1}),
            "notas": forms.Textarea(attrs={"rows": 2, "placeholder": "Peticiones especiales, hora de llegada…"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cliente"].queryset = Cliente.objects.order_by("apellidos", "nombre")
        self.fields["cliente"].empty_label = "Selecciona un cliente"
        habs = Habitacion.objects.order_by("numero")
        if not self.instance.pk:
            habs = habs.filter(disponible=True)
        self.fields["habitacion"].queryset = habs
        self.fields["habitacion"].empty_label = "Selecciona una habitación"
        self.fields["habitacion"].label_from_instance = (
            lambda h: f"{h.numero} · {h.get_tipo_display()} · {h.capacidad} pers. · ${h.precio_noche:,.2f}/noche"
        )
        if not self.instance.pk:
            self.fields["fecha_entrada"].widget.attrs["min"] = date.today().isoformat()


class ReservacionEditarForm(ReservacionForm):
    class Meta(ReservacionForm.Meta):
        fields = ReservacionForm.Meta.fields + ["estado"]


class DisponibilidadForm(forms.Form):
    entrada = forms.DateField(label="Llegada", widget=forms.DateInput(attrs=DATE))
    salida = forms.DateField(label="Salida", widget=forms.DateInput(attrs=DATE))
    huespedes = forms.IntegerField(label="Huéspedes", min_value=1, max_value=12, initial=1)
    tipo = forms.ChoiceField(
        label="Tipo", required=False, choices=[("", "Cualquier tipo")] + list(Habitacion.Tipo.choices)
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        hoy = date.today()
        self.fields["entrada"].initial = hoy
        self.fields["salida"].initial = hoy + timedelta(days=1)
        self.fields["entrada"].widget.attrs["min"] = hoy.isoformat()

    def clean(self):
        datos = super().clean()
        entrada, salida = datos.get("entrada"), datos.get("salida")
        if entrada and salida and salida <= entrada:
            self.add_error("salida", "La salida debe ser posterior a la llegada.")
        if entrada and entrada < date.today():
            self.add_error("entrada", "Elige una fecha de hoy en adelante.")
        return datos


class FiltroReservacionForm(forms.Form):
    q = forms.CharField(required=False, label="Buscar",
                        widget=forms.TextInput(attrs={"placeholder": "Cliente, correo, folio o habitación"}))
    estado = forms.ChoiceField(required=False, choices=[("", "Todos los estados")] + list(Reservacion.Estado.choices))
    tipo = forms.ChoiceField(required=False, choices=[("", "Todos los tipos")] + list(Habitacion.Tipo.choices))
    desde = forms.DateField(required=False, widget=forms.DateInput(attrs=DATE))
    hasta = forms.DateField(required=False, widget=forms.DateInput(attrs=DATE))
