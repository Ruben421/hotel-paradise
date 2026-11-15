from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.utils.html import format_html

from reservaciones.models import Reservacion

from .models import Habitacion


class ReservacionInline(admin.TabularInline):
    model = Reservacion
    extra = 0
    fields = ("cliente", "fecha_entrada", "fecha_salida", "estado", "total")
    readonly_fields = ("total",)
    show_change_link = True
    ordering = ("-fecha_entrada",)


@admin.register(Habitacion)
class HabitacionAdmin(admin.ModelAdmin):
    list_display = ("numero", "miniatura", "tipo", "precio_noche", "capacidad", "disponible")
    list_display_links = ("numero", "miniatura")
    list_editable = ("precio_noche", "disponible")
    list_filter = ("tipo", "disponible", "capacidad")
    search_fields = ("numero", "descripcion")
    readonly_fields = ("vista_previa", "creada", "actualizada")
    inlines = [ReservacionInline]
    actions = ["sacar_de_servicio", "poner_en_servicio"]
    fieldsets = (
        (None, {"fields": ("numero", "tipo", "precio_noche", "capacidad", "disponible")}),
        ("Fotografía y descripción", {"fields": ("imagen", "vista_previa", "descripcion")}),
        ("Registro", {"fields": ("creada", "actualizada"), "classes": ("collapse",)}),
    )

    @admin.display(description="Foto")
    def miniatura(self, obj):
        if obj.imagen:
            return format_html('<img src="{}" style="height:36px;border-radius:6px">', obj.imagen.url)
        return "—"

    @admin.display(description="Vista previa")
    def vista_previa(self, obj):
        if obj.imagen:
            return format_html('<img src="{}" style="max-width:320px;border-radius:8px">', obj.imagen.url)
        return "Sin fotografía"

    @admin.action(description="Sacar de servicio")
    def sacar_de_servicio(self, request, queryset):
        n = queryset.update(disponible=False)
        self.message_user(request, f"{n} habitación(es) fuera de servicio.")

    @admin.action(description="Poner en servicio")
    def poner_en_servicio(self, request, queryset):
        n = queryset.update(disponible=True)
        self.message_user(request, f"{n} habitación(es) en servicio.")

    def delete_model(self, request, obj):
        try:
            obj.delete()
        except ValidationError as e:
            self.message_user(request, e.messages[0], level=messages.ERROR)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            self.delete_model(request, obj)
