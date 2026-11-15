from datetime import date

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from core.permisos import AdminRequeridoMixin
from reservaciones.models import Reservacion
from reservaciones.servicios import ids_ocupadas_en

from .forms import FiltroHabitacionForm, HabitacionForm
from .models import Habitacion


class HabitacionListView(LoginRequiredMixin, ListView):
    model = Habitacion
    template_name = "habitaciones/lista.html"
    context_object_name = "habitaciones"
    paginate_by = 16

    def get_queryset(self):
        qs = Habitacion.objects.all()
        self.filtro = FiltroHabitacionForm(self.request.GET or None)
        self.ocupadas = ids_ocupadas_en(date.today())
        if self.filtro.is_valid():
            q = self.filtro.cleaned_data["q"].strip()
            tipo = self.filtro.cleaned_data["tipo"]
            estado = self.filtro.cleaned_data["estado"]
            if q:
                filtro_q = Q(descripcion__icontains=q)
                if q.isdigit():
                    filtro_q |= Q(numero=int(q))
                qs = qs.filter(filtro_q)
            if tipo:
                qs = qs.filter(tipo=tipo)
            if estado == "libre":
                qs = qs.filter(disponible=True).exclude(pk__in=self.ocupadas)
            elif estado == "ocupada":
                qs = qs.filter(pk__in=self.ocupadas)
            elif estado == "fuera":
                qs = qs.filter(disponible=False)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["filtro"] = self.filtro
        ctx["ocupadas"] = self.ocupadas
        ctx["resumen_tipos"] = (
            Habitacion.objects.values("tipo").annotate(n=Count("id")).order_by("tipo")
        )
        etiquetas = dict(Habitacion.Tipo.choices)
        for r in ctx["resumen_tipos"]:
            r["etiqueta"] = etiquetas.get(r["tipo"], r["tipo"])
        return ctx


class HabitacionDetailView(LoginRequiredMixin, DetailView):
    model = Habitacion
    template_name = "habitaciones/detalle.html"
    context_object_name = "habitacion"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        hab = self.object
        hoy = date.today()
        reservas = hab.reservaciones.select_related("cliente")
        ctx["proximas"] = reservas.filter(
            estado__in=Reservacion.ESTADOS_ACTIVOS, fecha_salida__gt=hoy
        ).order_by("fecha_entrada")
        ctx["historial"] = reservas.exclude(pk__in=ctx["proximas"]).order_by("-fecha_entrada")[:10]
        ingreso = reservas.filter(estado__in=Reservacion.ESTADOS_CON_INGRESO)
        ctx["ingresos"] = ingreso.aggregate(t=Sum("total"))["t"] or 0
        ctx["noches"] = sum(r.noches for r in ingreso)
        ctx["ocupada_hoy"] = hab.ocupada_hoy()
        return ctx


class HabitacionCreateView(AdminRequeridoMixin, CreateView):
    model = Habitacion
    form_class = HabitacionForm
    template_name = "habitaciones/form.html"

    def form_valid(self, form):
        messages.success(self.request, f"Habitación {form.instance.numero} registrada.")
        return super().form_valid(form)


class HabitacionUpdateView(AdminRequeridoMixin, UpdateView):
    model = Habitacion
    form_class = HabitacionForm
    template_name = "habitaciones/form.html"

    def form_valid(self, form):
        messages.success(self.request, f"Habitación {form.instance.numero} actualizada.")
        return super().form_valid(form)


class HabitacionDeleteView(AdminRequeridoMixin, View):
    """Elimina por POST. Regla 5: se bloquea si hay reservaciones activas."""

    success_url = reverse_lazy("habitaciones:lista")

    def post(self, request, pk):
        hab = get_object_or_404(Habitacion, pk=pk)
        numero = hab.numero
        try:
            hab.delete()
        except ValidationError as e:
            messages.error(request, e.messages[0])
            return redirect(hab)
        messages.success(request, f"Habitación {numero} eliminada.")
        return redirect(self.success_url)
