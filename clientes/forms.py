from django import forms

from .models import Cliente


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ["nombre", "apellidos", "correo", "telefono"]
        widgets = {
            "nombre": forms.TextInput(attrs={"autocomplete": "given-name"}),
            "apellidos": forms.TextInput(attrs={"autocomplete": "family-name"}),
            "correo": forms.EmailInput(attrs={"placeholder": "nombre@correo.com", "autocomplete": "email"}),
            "telefono": forms.TextInput(attrs={"placeholder": "81 1234 5678", "autocomplete": "tel"}),
        }

    def clean_nombre(self):
        return self.cleaned_data["nombre"].strip().title()

    def clean_apellidos(self):
        return self.cleaned_data["apellidos"].strip().title()

    def clean_correo(self):
        # Regla 4 sin importar mayúsculas: "Ana@Mail.com" y "ana@mail.com" son el mismo correo.
        correo = self.cleaned_data["correo"].strip().lower()
        qs = Cliente.objects.filter(correo__iexact=correo)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Ya hay un cliente registrado con este correo.")
        return correo

    def clean_telefono(self):
        tel = self.cleaned_data["telefono"].strip()
        digitos = sum(c.isdigit() for c in tel)
        if digitos < 10:
            raise forms.ValidationError("El teléfono debe tener al menos 10 dígitos.")
        return tel
