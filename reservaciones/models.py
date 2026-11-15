from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.urls import reverse

from clientes.models import Cliente
from habitaciones.models import Habitacion


class ReservacionQuerySet(models.QuerySet):
    def activas(self):
        return self.filter(estado__in=Reservacion.ESTADOS_ACTIVOS)

    def que_generan_ingreso(self):
        return self.filter(estado__in=Reservacion.ESTADOS_CON_INGRESO)

    def traslapes(self, habitacion, entrada, salida):
        """Reservaciones activas de la habitación que se cruzan con [entrada, salida).

        Dos rangos se traslapan si cada uno empieza antes de que el otro termine.
        El día de salida queda libre para un nuevo check-in.
        """
        return self.activas().filter(
            habitacion=habitacion,
            fecha_entrada__lt=salida,
            fecha_salida__gt=entrada,
        )

    def en_fecha(self, dia):
        return self.activas().filter(fecha_entrada__lte=dia, fecha_salida__gt=dia)


class Reservacion(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        CONFIRMADA = "confirmada", "Confirmada"
        FINALIZADA = "finalizada", "Finalizada"
        CANCELADA = "cancelada", "Cancelada"

    ESTADOS_ACTIVOS = [Estado.PENDIENTE, Estado.CONFIRMADA]
    ESTADOS_CON_INGRESO = [Estado.CONFIRMADA, Estado.FINALIZADA]

    cliente = models.ForeignKey(
        Cliente, on_delete=models.CASCADE, related_name="reservaciones"
    )
    habitacion = models.ForeignKey(
        Habitacion,
        on_delete=models.CASCADE,
        related_name="reservaciones",
        verbose_name="habitación",
    )
    fecha_entrada = models.DateField("fecha de entrada")
    fecha_salida = models.DateField("fecha de salida")
    huespedes = models.PositiveSmallIntegerField(
        "huéspedes", default=1, validators=[MinValueValidator(1)]
    )
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), editable=False)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.CONFIRMADA)
    notas = models.TextField(blank=True)
    creada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservaciones_creadas",
    )
    creada = models.DateTimeField(auto_now_add=True)
    actualizada = models.DateTimeField(auto_now=True)

    objects = ReservacionQuerySet.as_manager()

    class Meta:
        ordering = ["-fecha_entrada", "-pk"]
        verbose_name = "reservación"
        verbose_name_plural = "reservaciones"
        constraints = [
            # Regla 2 también a nivel base de datos.
            models.CheckConstraint(
                condition=Q(fecha_salida__gt=F("fecha_entrada")),
                name="reservacion_salida_mayor_entrada",
            ),
        ]
        indexes = [models.Index(fields=["habitacion", "fecha_entrada", "fecha_salida"])]

    def __str__(self):
        return f"{self.folio} · {self.cliente} · {self.habitacion}"

    def get_absolute_url(self):
        return reverse("reservaciones:detalle", args=[self.pk])

    @property
    def folio(self):
        return f"HP-{self.pk:05d}" if self.pk else "HP-nueva"

    @property
    def noches(self):
        if self.fecha_entrada and self.fecha_salida:
            return max((self.fecha_salida - self.fecha_entrada).days, 0)
        return 0

    @property
    def es_activa(self):
        return self.estado in self.ESTADOS_ACTIVOS

    @property
    def puede_cancelarse(self):
        return self.es_activa and self.fecha_salida > date.today()

    def calcular_total(self):
        if not self.habitacion_id:
            return Decimal("0.00")
        return (self.habitacion.precio_noche * self.noches).quantize(Decimal("0.01"))

    def clean(self):
        errores = {}

        # Regla 2: la fecha de salida debe ser mayor que la de entrada.
        if self.fecha_entrada and self.fecha_salida and self.fecha_salida <= self.fecha_entrada:
            errores["fecha_salida"] = "La fecha de salida debe ser posterior a la fecha de entrada."

        es_nueva = self.pk is None
        if es_nueva and self.fecha_entrada and self.fecha_entrada < date.today():
            errores["fecha_entrada"] = "No se pueden crear reservaciones con fecha de entrada en el pasado."

        if self.habitacion_id and self.es_activa:
            hab = self.habitacion
            if self.huespedes and self.huespedes > hab.capacidad:
                errores["huespedes"] = (
                    f"La habitación {hab.numero} admite máximo {hab.capacidad} huésped(es)."
                )
            if es_nueva and not hab.disponible:
                errores["habitacion"] = (
                    f"La habitación {hab.numero} está fuera de servicio y no acepta reservaciones."
                )
            # Regla 1: una habitación no puede reservarse dos veces en las mismas fechas.
            if self.fecha_entrada and self.fecha_salida and "fecha_salida" not in errores:
                choque = (
                    Reservacion.objects.traslapes(hab, self.fecha_entrada, self.fecha_salida)
                    .exclude(pk=self.pk)
                    .select_related("cliente")
                    .first()
                )
                if choque:
                    errores["habitacion"] = (
                        f"La habitación {hab.numero} ya está reservada del "
                        f"{choque.fecha_entrada:%d/%m/%Y} al {choque.fecha_salida:%d/%m/%Y} "
                        f"(folio {choque.folio}). Elige otras fechas u otra habitación."
                    )

        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        # Las reservaciones cerradas conservan el total con el que se cobraron,
        # aunque después cambie el precio de la habitación.
        if self.pk is None or self.es_activa:
            self.total = self.calcular_total()
        super().save(*args, **kwargs)
