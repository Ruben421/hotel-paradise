"""Control de usuarios: roles y mixins de acceso.

Roles del sistema (grupos de Django):
- Administrador: acceso total (habitaciones, reportes, usuarios).
- Recepcionista: clientes, reservaciones, disponibilidad y dashboard.
"""
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

GRUPO_ADMIN = "Administrador"
GRUPO_RECEPCION = "Recepcionista"


def es_admin(user):
    return user.is_authenticated and (
        user.is_superuser or user.groups.filter(name=GRUPO_ADMIN).exists()
    )


def rol_de(user):
    if not user.is_authenticated:
        return ""
    if es_admin(user):
        return GRUPO_ADMIN
    return GRUPO_RECEPCION


class AdminRequeridoMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Solo usuarios con rol Administrador (o superusuario)."""

    def test_func(self):
        return es_admin(self.request.user)
