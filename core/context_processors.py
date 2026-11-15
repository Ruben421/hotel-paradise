from django.conf import settings

from .permisos import es_admin, rol_de


def proyecto(request):
    return {
        "PROYECTO": settings.PROYECTO,
        "es_admin": es_admin(request.user),
        "rol_usuario": rol_de(request.user),
    }
