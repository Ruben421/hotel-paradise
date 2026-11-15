"""Lógica de disponibilidad y ocupación, separada de las vistas para poder reutilizarla y probarla."""
from datetime import date, timedelta

from habitaciones.models import Habitacion

from .models import Reservacion


def habitaciones_libres(entrada, salida, huespedes=1, tipo=None):
    """Habitaciones en servicio, con capacidad suficiente y sin traslapes en [entrada, salida)."""
    ocupadas = (
        Reservacion.objects.activas()
        .filter(fecha_entrada__lt=salida, fecha_salida__gt=entrada)
        .values("habitacion_id")
    )
    qs = Habitacion.objects.filter(disponible=True, capacidad__gte=huespedes).exclude(pk__in=ocupadas)
    if tipo:
        qs = qs.filter(tipo=tipo)
    return qs.order_by("precio_noche", "numero")


def ids_ocupadas_en(dia):
    return set(Reservacion.objects.en_fecha(dia).values_list("habitacion_id", flat=True))


def mapa_ocupacion(inicio=None, dias=14, habitaciones=None):
    """Construye la cuadrícula habitación × día con segmentos agrupados por reservación.

    Cada fila tiene una lista de segmentos {tipo, span, reservacion} lista para
    renderizarse como celdas con colspan.
    """
    inicio = inicio or date.today()
    fin = inicio + timedelta(days=dias)
    dias_lista = [inicio + timedelta(days=i) for i in range(dias)]
    habitaciones = list(habitaciones if habitaciones is not None else Habitacion.objects.order_by("numero"))

    reservas = (
        Reservacion.objects.activas()
        .filter(fecha_entrada__lt=fin, fecha_salida__gt=inicio, habitacion__in=habitaciones)
        .select_related("cliente")
        .order_by("fecha_entrada")
    )
    por_hab = {}
    for r in reservas:
        por_hab.setdefault(r.habitacion_id, []).append(r)

    filas = []
    for hab in habitaciones:
        segmentos = []
        i = 0
        lista = por_hab.get(hab.pk, [])
        while i < dias:
            dia = dias_lista[i]
            r = next((x for x in lista if x.fecha_entrada <= dia < x.fecha_salida), None)
            if r:
                hasta = min(r.fecha_salida, fin)
                span = (hasta - dia).days
                segmentos.append({
                    "tipo": r.estado,
                    "span": span,
                    "reservacion": r,
                    "corta_inicio": r.fecha_entrada < inicio,
                })
                i += span
            else:
                segmentos.append({"tipo": "libre" if hab.disponible else "fuera", "span": 1, "dia": dia})
                i += 1
        filas.append({"habitacion": hab, "segmentos": segmentos})

    return {"dias": dias_lista, "filas": filas, "inicio": inicio, "fin": fin}
