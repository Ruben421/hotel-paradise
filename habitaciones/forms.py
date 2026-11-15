from django import forms

from .models import Habitacion


class HabitacionForm(forms.ModelForm):
    class Meta:
        model = Habitacion
        fields = ["numero", "tipo", "precio_noche", "capacidad", "disponible", "imagen", "descripcion"]
        widgets = {
            "numero": forms.NumberInput(attrs={"placeholder": "Ej. 204", "min": 1}),
            "precio_noche": forms.NumberInput(attrs={"step": "0.01", "min": "0.01", "placeholder": "0.00"}),
            "capacidad": forms.NumberInput(attrs={"min": 1, "max": 12}),
            "descripcion": forms.Textarea(attrs={"rows": 3, "placeholder": "Vista, camas, amenidades…"}),
            "imagen": forms.ClearableFileInput(attrs={"accept": "image/*"}),
        }

    def clean_imagen(self):
        imagen = self.cleaned_data.get("imagen")
        if imagen and hasattr(imagen, "size") and imagen.size > 5 * 1024 * 1024:
            raise forms.ValidationError("La imagen no debe pesar más de 5 MB.")
        return imagen


class FiltroHabitacionForm(forms.Form):
    q = forms.CharField(required=False, label="Buscar",
                        widget=forms.TextInput(attrs={"placeholder": "Número o descripción"}))
    tipo = forms.ChoiceField(required=False, choices=[("", "Todos los tipos")] + list(Habitacion.Tipo.choices))
    estado = forms.ChoiceField(
        required=False,
        choices=[("", "Cualquier estado"), ("libre", "Libre hoy"), ("ocupada", "Ocupada hoy"),
                 ("fuera", "Fuera de servicio")],
    )
