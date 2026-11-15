from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.dateparse import parse_date
from django.views import View
from django.views.generic import CreateView, DetailView, FormView, ListView, TemplateView, UpdateView

from habitaciones.models import Habitacion

from .forms import DisponibilidadForm, FiltroReservacionForm, ReservacionEditarForm, ReservacionForm
from .models import Reservacion
from .servicios import habitaciones_libres, mapa_ocupacion


class ReservacionListView(LoginRequiredMixin, ListView):
    model = Reservacion
    template_name = "reservaciones/lista.html"
    context_object_name = "reservaciones"
    paginate_by = 15

    def get_queryset(self):
        qs = Reservacion.objects.select_related("cliente", "habitacion")
        self.filtro = FiltroReservacionForm(self.request.GET or None)
        if self.filtro.is_valid():
            d = self.filtro.cleaned_data
            q = d["q"].strip()
            if q:
                cond = Q()
                for palabra in q.split():
                    p = Q(cliente__nombre__icontains=palabra) | Q(cliente__apellidos__icontains=palabra) \
                        | Q(cliente__correo__icontains=palabra)
                    limpio = palabra.upper().replace("HP-", "")
                    if limpio.isdigit():
                        p |= Q(habitacion__numero=int(limpio)) | Q(pk=int(limpio))
                    cond &= p
                qs = qs.filter(cond)
            if d["estado"]:
                qs = qs.filter(estado=d["estado"])
            if d["tipo"]:
                qs = qs.filter(habitacion__tipo=d["tipo"])
            if d["desde"]:
                qs = qs.filter(fecha_salida__gt=d["desde"])
            if d["hasta"]:
                qs = qs.filter(fecha_entrada__lte=d["hasta"])
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["filtro"] = self.filtro
        ctx["hoy"] = date.today()
        return ctx


class ReservacionDetailView(LoginRequiredMixin, DetailView):
    model = Reservacion
    template_name = "reservaciones/detalle.html"
    context_object_name = "r"

    def get_queryset(self):
        return Reservacion.objects.select_related("cliente", "habitacion", "creada_por")


class _GuardadoSeguroMixin:
    """Vuelve a validar el traslape dentro de una transacción antes de guardar."""

    def form_valid(self, form):
        with transaction.atomic():
            r = form.instance
            if r.es_activa and Reservacion.objects.traslapes(
                r.habitacion, r.fecha_entrada, r.fecha_salida
            ).exclude(pk=r.pk).exists():
                form.add_error("habitacion", "Alguien acaba de reservar esta habitación en esas fechas.")
                return self.form_invalid(form)
            return super().form_valid(form)


class ReservacionCreateView(LoginRequiredMixin, _GuardadoSeguroMixin, CreateView):
    model = Reservacion
    form_class = ReservacionForm
    template_name = "reservaciones/form.html"

    def get_initial(self):
        ini = super().get_initial()
        for campo in ("cliente", "habitacion", "huespedes"):
            if self.request.GET.get(campo):
                ini[campo] = self.request.GET[campo]
        for campo, param in (("fecha_entrada", "entrada"), ("fecha_salida", "salida")):
            valor = parse_date(self.request.GET.get(param, "") or "")
            if valor:
                ini[campo] = valor
        ini.setdefault("fecha_entrada", date.today())
        if not ini.get("fecha_salida") or ini["fecha_salida"] <= ini["fecha_entrada"]:
            ini["fecha_salida"] = ini["fecha_entrada"] + timedelta(days=1)
        return ini

    def form_valid(self, form):
        form.instance.creada_por = self.request.user
        resp = super().form_valid(form)
        if self.object and self.object.pk:
            messages.success(
                self.request,
                f"Reservación {self.object.folio} confirmada: {self.object.noches} noche(s), "
                f"total ${self.object.total:,.2f}.",
            )
        return resp


class ReservacionUpdateView(LoginRequiredMixin, _GuardadoSeguroMixin, UpdateView):
    model = Reservacion
    form_class = ReservacionEditarForm
    template_name = "reservaciones/form.html"

    def form_valid(self, form):
        resp = super().form_valid(form)
        if self.object and self.object.pk:
            messages.success(self.request, f"Reservación {self.object.folio} actualizada.")
        return resp


class ReservacionCancelarView(LoginRequiredMixin, View):
    def post(self, request, pk):
        r = get_object_or_404(Reservacion, pk=pk)
        if not r.puede_cancelarse:
            messages.error(request, f"La reservación {r.folio} ya no se puede cancelar.")
        else:
            r.estado = Reservacion.Estado.CANCELADA
            r.save(update_fields=["estado", "actualizada"])
            messages.success(request, f"Reservación {r.folio} cancelada. La habitación quedó libre en esas fechas.")
        return redirect(r)


class DisponibilidadView(LoginRequiredMixin, FormView):
    """Consulta de disponibilidad: ¿qué habitaciones puedo vender en estas fechas?"""

    template_name = "reservaciones/disponibilidad.html"
    form_class = DisponibilidadForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if "entrada" in self.request.GET:
            kwargs["data"] = self.request.GET
        return kwargs

    def get(self, request, *args, **kwargs):
        form = self.get_form()
        ctx = {"form": form}
        if form.is_bound and form.is_valid():
            d = form.cleaned_data
            libres = list(habitaciones_libres(d["entrada"], d["salida"], d["huespedes"], d["tipo"] or None))
            noches = (d["salida"] - d["entrada"]).days
            for h in libres:
                h.total_estancia = h.precio_noche * noches
            ctx.update(libres=libres, noches=noches, consulta=d, buscado=True)
        return self.render_to_response(self.get_context_data(**ctx))


class OcupacionView(LoginRequiredMixin, TemplateView):
    """Mapa de ocupación: habitaciones × días."""

    template_name = "reservaciones/ocupacion.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        inicio = parse_date(self.request.GET.get("inicio", "") or "") or date.today()
        dias = 21
        tipo = self.request.GET.get("tipo", "")
        habs = Habitacion.objects.order_by("numero")
        if tipo in Habitacion.Tipo.values:
            habs = habs.filter(tipo=tipo)
        ctx["mapa"] = mapa_ocupacion(inicio, dias, habs)
        ctx["anterior"] = inicio - timedelta(days=7)
        ctx["siguiente"] = inicio + timedelta(days=7)
        ctx["hoy"] = date.today()
        ctx["tipo"] = tipo
        ctx["tipos"] = Habitacion.Tipo.choices
        return ctx


class CotizarView(LoginRequiredMixin, View):
    """Endpoint JSON que el formulario usa para mostrar total y disponibilidad en vivo."""

    def get(self, request):
        hab = Habitacion.objects.filter(pk=request.GET.get("habitacion") or 0).first()
        entrada = parse_date(request.GET.get("entrada", "") or "")
        salida = parse_date(request.GET.get("salida", "") or "")
        excluir = request.GET.get("excluir") or None
        if not (hab and entrada and salida):
            return JsonResponse({"ok": False, "mensaje": "Elige habitación y fechas para cotizar."})
        if salida <= entrada:
            return JsonResponse({"ok": False, "mensaje": "La salida debe ser posterior a la llegada."})
        noches = (salida - entrada).days
        libre = hab.esta_libre(entrada, salida, excluir_pk=excluir)
        return JsonResponse({
            "ok": True,
            "disponible": libre and hab.disponible,
            "noches": noches,
            "precio_noche": f"{hab.precio_noche:,.2f}",
            "total": f"{hab.precio_noche * noches:,.2f}",
            "capacidad": hab.capacidad,
            "mensaje": (
                "Disponible en esas fechas." if libre and hab.disponible
                else "Fuera de servicio." if not hab.disponible
                else "Ocupada en esas fechas. Prueba otras fechas u otra habitación."
            ),
        })
