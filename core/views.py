import csv
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.dateparse import parse_date
from django.views.generic import CreateView, ListView, TemplateView, UpdateView

from clientes.models import Cliente
from habitaciones.models import Habitacion
from reservaciones.models import Reservacion
from reservaciones.servicios import ids_ocupadas_en, mapa_ocupacion

from .forms import UsuarioCrearForm, UsuarioEditarForm
from .permisos import AdminRequeridoMixin, rol_de

MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def _meses_atras(hoy, n):
    """Lista de primeros de mes, de hace n-1 meses hasta el actual."""
    meses = []
    y, m = hoy.year, hoy.month
    for _ in range(n):
        meses.append(date(y, m, 1))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(meses))


def ingresos_por_mes(qs, meses):
    datos = {
        row["mes"].date() if hasattr(row["mes"], "date") else row["mes"]: row["total"]
        for row in qs.annotate(mes=TruncMonth("fecha_entrada")).values("mes").annotate(total=Sum("total"))
    }
    return {
        "etiquetas": [f"{MESES[m.month - 1]} {str(m.year)[2:]}" for m in meses],
        "valores": [float(datos.get(m, 0) or 0) for m in meses],
    }


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "core/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        hoy = date.today()
        ocupadas = ids_ocupadas_en(hoy)
        en_servicio = Habitacion.objects.filter(disponible=True)
        total_hab = Habitacion.objects.count()
        con_ingreso = Reservacion.objects.que_generan_ingreso()

        ctx.update(
            hoy=hoy,
            total_clientes=Cliente.objects.count(),
            total_habitaciones=total_hab,
            total_reservaciones=Reservacion.objects.count(),
            reservaciones_activas=Reservacion.objects.activas().filter(fecha_salida__gt=hoy).count(),
            habitaciones_disponibles=en_servicio.exclude(pk__in=ocupadas).count(),
            habitaciones_ocupadas=len(ocupadas),
            fuera_servicio=total_hab - en_servicio.count(),
            en_servicio_n=en_servicio.count(),
            ingresos=con_ingreso.aggregate(t=Sum("total"))["t"] or Decimal("0"),
            ingresos_mes=con_ingreso.filter(
                fecha_entrada__year=hoy.year, fecha_entrada__month=hoy.month
            ).aggregate(t=Sum("total"))["t"] or Decimal("0"),
            ocupacion_pct=round(len(ocupadas) * 100 / en_servicio.count()) if en_servicio.exists() else 0,
            llegadas=Reservacion.objects.activas().filter(fecha_entrada=hoy).select_related("cliente", "habitacion"),
            salidas=Reservacion.objects.activas().filter(fecha_salida=hoy).select_related("cliente", "habitacion"),
            proximas=Reservacion.objects.activas()
            .filter(fecha_entrada__gt=hoy, fecha_entrada__lte=hoy + timedelta(days=7))
            .select_related("cliente", "habitacion")
            .order_by("fecha_entrada")[:6],
            mapa=mapa_ocupacion(hoy, 14),
            grafica=ingresos_por_mes(con_ingreso, _meses_atras(hoy, 6)),
        )
        return ctx


class ReportesView(AdminRequeridoMixin, TemplateView):
    template_name = "core/reportes.html"

    def periodo(self):
        hoy = date.today()
        desde = parse_date(self.request.GET.get("desde", "") or "") or (hoy - timedelta(days=90))
        hasta = parse_date(self.request.GET.get("hasta", "") or "") or (hoy + timedelta(days=30))
        if hasta < desde:
            desde, hasta = hasta, desde
        return desde, hasta

    def reservas_periodo(self, desde, hasta):
        return Reservacion.objects.filter(fecha_entrada__gte=desde, fecha_entrada__lte=hasta)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        desde, hasta = self.periodo()
        reservas = self.reservas_periodo(desde, hasta).select_related("habitacion", "cliente")
        con_ingreso = reservas.filter(estado__in=Reservacion.ESTADOS_CON_INGRESO)

        ingresos = con_ingreso.aggregate(t=Sum("total"))["t"] or Decimal("0")
        noches = sum(r.noches for r in con_ingreso)

        # Ocupación real: noches ocupadas dentro del rango / noches disponibles.
        dias = (hasta - desde).days + 1
        fin_excl = hasta + timedelta(days=1)
        ocupadas = 0
        for r in Reservacion.objects.filter(
            estado__in=Reservacion.ESTADOS_CON_INGRESO + [Reservacion.Estado.PENDIENTE],
            fecha_entrada__lt=fin_excl, fecha_salida__gt=desde,
        ):
            ocupadas += (min(r.fecha_salida, fin_excl) - max(r.fecha_entrada, desde)).days
        capacidad = Habitacion.objects.filter(disponible=True).count() * dias

        etiquetas = dict(Habitacion.Tipo.choices)
        por_tipo = []
        for t in con_ingreso.values("habitacion__tipo").annotate(n=Count("id"), total=Sum("total")).order_by("-total"):
            n_noches = sum(r.noches for r in con_ingreso if r.habitacion.tipo == t["habitacion__tipo"])
            por_tipo.append({"tipo": etiquetas.get(t["habitacion__tipo"]), "n": t["n"],
                             "total": t["total"], "noches": n_noches})

        estados = dict(Reservacion.Estado.choices)
        por_estado = [
            {"estado": e["estado"], "etiqueta": estados[e["estado"]], "n": e["n"]}
            for e in reservas.values("estado").annotate(n=Count("id")).order_by("-n")
        ]

        top_clientes = (
            Cliente.objects.filter(reservaciones__in=con_ingreso)
            .annotate(total=Sum("reservaciones__total", filter=Q(reservaciones__in=con_ingreso)),
                      n=Count("reservaciones", filter=Q(reservaciones__in=con_ingreso)))
            .order_by("-total")[:5]
        )

        top_habitaciones = (
            Habitacion.objects.annotate(
                total=Sum("reservaciones__total", filter=Q(reservaciones__in=con_ingreso)),
                n=Count("reservaciones", filter=Q(reservaciones__in=con_ingreso)),
            ).filter(n__gt=0).order_by("-total")[:5]
        )

        meses = []
        m = date(desde.year, desde.month, 1)
        while m <= hasta and len(meses) < 24:
            meses.append(m)
            m = date(m.year + (m.month // 12), m.month % 12 + 1, 1)

        ctx.update(
            desde=desde, hasta=hasta, dias=dias,
            n_reservas=reservas.count(),
            n_canceladas=reservas.filter(estado=Reservacion.Estado.CANCELADA).count(),
            ingresos=ingresos, noches=noches,
            tarifa_promedio=(ingresos / noches) if noches else Decimal("0"),
            ocupacion=round(ocupadas * 100 / capacidad) if capacidad else 0,
            por_tipo=por_tipo, por_estado=por_estado,
            top_clientes=top_clientes, top_habitaciones=top_habitaciones,
            grafica=ingresos_por_mes(con_ingreso, meses),
            nuevos_clientes=Cliente.objects.filter(
                fecha_registro__date__gte=desde, fecha_registro__date__lte=hasta).count(),
        )
        return ctx

    def render_to_response(self, context, **kwargs):
        if self.request.GET.get("formato") == "csv":
            return self.exportar_csv(context["desde"], context["hasta"])
        return super().render_to_response(context, **kwargs)

    def exportar_csv(self, desde, hasta):
        resp = HttpResponse(content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="reservaciones_{desde}_{hasta}.csv"'
        resp.write("﻿")  # BOM para que Excel respete los acentos
        w = csv.writer(resp)
        w.writerow(["Folio", "Cliente", "Correo", "Habitación", "Tipo", "Entrada", "Salida",
                    "Noches", "Huéspedes", "Total", "Estado"])
        for r in self.reservas_periodo(desde, hasta).select_related("cliente", "habitacion").order_by("fecha_entrada"):
            w.writerow([r.folio, r.cliente.nombre_completo, r.cliente.correo, r.habitacion.numero,
                        r.habitacion.get_tipo_display(), r.fecha_entrada.isoformat(), r.fecha_salida.isoformat(),
                        r.noches, r.huespedes, f"{r.total:.2f}", r.get_estado_display()])
        return resp


class UsuarioListView(AdminRequeridoMixin, ListView):
    template_name = "core/usuarios.html"
    context_object_name = "usuarios"

    def get_queryset(self):
        usuarios = list(User.objects.prefetch_related("groups").order_by("-is_active", "username"))
        for u in usuarios:
            u.rol = rol_de(u)
        return usuarios


class UsuarioCreateView(AdminRequeridoMixin, CreateView):
    form_class = UsuarioCrearForm
    template_name = "core/usuario_form.html"
    success_url = reverse_lazy("core:usuarios")

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, f"Usuario {self.object.username} creado como {form.cleaned_data['rol']}.")
        return resp


class UsuarioUpdateView(AdminRequeridoMixin, UpdateView):
    model = User
    form_class = UsuarioEditarForm
    template_name = "core/usuario_form.html"
    success_url = reverse_lazy("core:usuarios")

    def form_valid(self, form):
        if form.instance == self.request.user and not form.cleaned_data["is_active"]:
            messages.error(self.request, "No puedes desactivar tu propia cuenta.")
            return redirect("core:usuarios")
        messages.success(self.request, f"Usuario {form.instance.username} actualizado.")
        return super().form_valid(form)
