from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse


class Habitacion(models.Model):
    class Tipo(models.TextChoices):
        INDIVIDUAL = "individual", "Individual"
        DOBLE = "doble", "Doble"
        SUITE = "suite", "Suite"
        PRESIDENCIAL = "presidencial", "Presidencial"

    # Regla 3: no se pueden registrar habitaciones con números repetidos.
    numero = models.PositiveIntegerField(
        "número",
        unique=True,
        validators=[MinValueValidator(1)],
        error_messages={"unique": "Ya existe una habitación con este número."},
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.DOBLE)
    precio_noche = models.DecimalField(
        "precio por noche",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    capacidad = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text="Número máximo de huéspedes.",
    )
    disponible = models.BooleanField(
        default=True,
        help_text="Desmárcala para sacar la habitación de servicio (mantenimiento, remodelación).",
    )
    imagen = models.ImageField(upload_to="habitaciones/", blank=True, null=True)
    descripcion = models.TextField("descripción", blank=True)
    creada = models.DateTimeField(auto_now_add=True)
    actualizada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["numero"]
        verbose_name = "habitación"
        verbose_name_plural = "habitaciones"

    def __str__(self):
        return f"Hab. {self.numero} · {self.get_tipo_display()}"

    def get_absolute_url(self):
        return reverse("habitaciones:detalle", args=[self.pk])

    @property
    def piso(self):
        return self.numero // 100 if self.numero >= 100 else 0

    def reservaciones_activas(self):
        """Reservaciones pendientes o confirmadas que aún no terminan."""
        from reservaciones.models import Reservacion

        return self.reservaciones.filter(
            estado__in=Reservacion.ESTADOS_ACTIVOS, fecha_salida__gt=date.today()
        )

    def esta_libre(self, entrada, salida, excluir_pk=None):
        """True si no hay otra reservación activa que se traslape con [entrada, salida)."""
        from reservaciones.models import Reservacion

        qs = Reservacion.objects.traslapes(self, entrada, salida)
        if excluir_pk:
            qs = qs.exclude(pk=excluir_pk)
        return not qs.exists()

    def ocupada_hoy(self):
        hoy = date.today()
        return not self.esta_libre(hoy, date.fromordinal(hoy.toordinal() + 1))

    def delete(self, *args, **kwargs):
        # Regla 5: no se puede eliminar una habitación con reservaciones activas.
        if self.reservaciones_activas().exists():
            raise ValidationError(
                "No se puede eliminar la habitación porque tiene reservaciones activas. "
                "Cancélalas o espera a que terminen."
            )
        return super().delete(*args, **kwargs)
