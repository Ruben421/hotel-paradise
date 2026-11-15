from datetime import date

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.functions import Lower
from django.urls import reverse

telefono_validator = RegexValidator(
    regex=r"^\+?[\d\s\-()]{10,20}$",
    message="Escribe un teléfono válido de al menos 10 dígitos (ej. 81 1234 5678).",
)


class Cliente(models.Model):
    nombre = models.CharField(max_length=80)
    apellidos = models.CharField(max_length=120)
    # Regla 4: el correo del cliente debe ser único.
    correo = models.EmailField(
        unique=True,
        error_messages={"unique": "Ya hay un cliente registrado con este correo."},
    )
    telefono = models.CharField("teléfono", max_length=20, validators=[telefono_validator])
    fecha_registro = models.DateTimeField("fecha de registro", auto_now_add=True)

    class Meta:
        ordering = ["apellidos", "nombre"]
        constraints = [
            models.UniqueConstraint(Lower("correo"), name="cliente_correo_unico_ci"),
        ]

    def __str__(self):
        return self.nombre_completo

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellidos}"

    @property
    def iniciales(self):
        return (self.nombre[:1] + self.apellidos[:1]).upper()

    def get_absolute_url(self):
        return reverse("clientes:detalle", args=[self.pk])

    def save(self, *args, **kwargs):
        self.correo = self.correo.strip().lower()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        from reservaciones.models import Reservacion

        activas = self.reservaciones.filter(
            estado__in=Reservacion.ESTADOS_ACTIVOS, fecha_salida__gt=date.today()
        )
        if activas.exists():
            raise ValidationError(
                "No se puede eliminar el cliente porque tiene reservaciones activas."
            )
        return super().delete(*args, **kwargs)
