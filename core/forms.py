from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group, User

from .permisos import GRUPO_ADMIN, GRUPO_RECEPCION, rol_de

ROLES = [(GRUPO_RECEPCION, "Recepcionista"), (GRUPO_ADMIN, "Administrador")]


def _asignar_rol(user, rol):
    user.groups.clear()
    grupo, _ = Group.objects.get_or_create(name=rol)
    user.groups.add(grupo)
    user.is_staff = rol == GRUPO_ADMIN  # los administradores pueden entrar a /admin
    user.save(update_fields=["is_staff"])


class UsuarioCrearForm(UserCreationForm):
    rol = forms.ChoiceField(choices=ROLES)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["username", "first_name", "last_name", "email"]

    def save(self, commit=True):
        user = super().save(commit=True)
        _asignar_rol(user, self.cleaned_data["rol"])
        return user


class UsuarioEditarForm(forms.ModelForm):
    rol = forms.ChoiceField(choices=ROLES)

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "is_active"]
        labels = {"is_active": "Cuenta activa"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["rol"].initial = rol_de(self.instance)
        if self.instance.is_superuser:
            self.fields["rol"].disabled = True
            self.fields["rol"].help_text = "El superusuario siempre tiene acceso total."

    def save(self, commit=True):
        user = super().save(commit=True)
        if not user.is_superuser:
            _asignar_rol(user, self.cleaned_data["rol"])
        return user
