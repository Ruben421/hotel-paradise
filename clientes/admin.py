from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from .models import Cliente


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("nombre", "apellidos", "correo", "telefono", "fecha_registro")
    search_fields = ("nombre", "apellidos", "correo", "telefono")
    list_filter = ("fecha_registro",)
    readonly_fields = ("fecha_registro",)
    date_hierarchy = "fecha_registro"

    def delete_model(self, request, obj):
        try:
            obj.delete()
        except ValidationError as e:
            self.message_user(request, e.messages[0], level=messages.ERROR)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            self.delete_model(request, obj)
