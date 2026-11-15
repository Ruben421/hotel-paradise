from django.contrib import admin

from .models import Reservacion


@admin.register(Reservacion)
class ReservacionAdmin(admin.ModelAdmin):
    list_display = ("folio", "cliente", "habitacion", "fecha_entrada", "fecha_salida", "noches", "total", "estado")
    list_filter = ("estado", "habitacion__tipo", "fecha_entrada")
    search_fields = ("cliente__nombre", "cliente__apellidos", "cliente__correo", "habitacion__numero")
    autocomplete_fields = ("cliente",)
    readonly_fields = ("total", "creada_por", "creada", "actualizada")
    date_hierarchy = "fecha_entrada"
    list_select_related = ("cliente", "habitacion")
    actions = ["cancelar"]

    @admin.display(description="Folio", ordering="pk")
    def folio(self, obj):
        return obj.folio

    @admin.display(description="Noches")
    def noches(self, obj):
        return obj.noches

    @admin.action(description="Cancelar reservaciones seleccionadas")
    def cancelar(self, request, queryset):
        n = queryset.filter(estado__in=Reservacion.ESTADOS_ACTIVOS).update(estado=Reservacion.Estado.CANCELADA)
        self.message_user(request, f"{n} reservación(es) cancelada(s).")

    def save_model(self, request, obj, form, change):
        if not obj.creada_por_id:
            obj.creada_por = request.user
        super().save_model(request, obj, form, change)
