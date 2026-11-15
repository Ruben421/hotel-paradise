from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Count, Max, Q, Sum
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from core.permisos import AdminRequeridoMixin
from reservaciones.models import Reservacion

from .forms import ClienteForm
from .models import Cliente


class ClienteListView(LoginRequiredMixin, ListView):
    model = Cliente
    template_name = "clientes/lista.html"
    context_object_name = "clientes"
    paginate_by = 15

    ORDENES = {
        "nombre": ("apellidos", "nombre"),
        "recientes": ("-fecha_registro",),
        "reservas": ("-n_reservas", "apellidos"),
    }

    def get_queryset(self):
        qs = Cliente.objects.annotate(
            n_reservas=Count("reservaciones"),
            gastado=Sum("reservaciones__total",
                        filter=Q(reservaciones__estado__in=Reservacion.ESTADOS_CON_INGRESO)),
            ultima=Max("reservaciones__fecha_entrada"),
        )
        self.q = self.request.GET.get("q", "").strip()
        if self.q:
            for palabra in self.q.split():
                qs = qs.filter(
                    Q(nombre__icontains=palabra)
                    | Q(apellidos__icontains=palabra)
                    | Q(correo__icontains=palabra)
                    | Q(telefono__icontains=palabra)
                )
        self.orden = self.request.GET.get("orden", "nombre")
        return qs.order_by(*self.ORDENES.get(self.orden, self.ORDENES["nombre"]))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = self.q
        ctx["orden"] = self.orden
        ctx["total_clientes"] = Cliente.objects.count()
        return ctx


class ClienteDetailView(LoginRequiredMixin, DetailView):
    model = Cliente
    template_name = "clientes/detalle.html"
    context_object_name = "cliente"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        reservas = self.object.reservaciones.select_related("habitacion").order_by("-fecha_entrada")
        ctx["reservaciones"] = reservas
        con_ingreso = reservas.filter(estado__in=Reservacion.ESTADOS_CON_INGRESO)
        ctx["gastado"] = con_ingreso.aggregate(t=Sum("total"))["t"] or 0
        ctx["noches"] = sum(r.noches for r in con_ingreso)
        return ctx


class ClienteCreateView(LoginRequiredMixin, CreateView):
    model = Cliente
    form_class = ClienteForm
    template_name = "clientes/form.html"

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, f"Cliente {self.object.nombre_completo} registrado.")
        siguiente = self.request.GET.get("next")
        if siguiente == "reservar":
            return redirect(f"{reverse_lazy('reservaciones:crear')}?cliente={self.object.pk}")
        return resp


class ClienteUpdateView(LoginRequiredMixin, UpdateView):
    model = Cliente
    form_class = ClienteForm
    template_name = "clientes/form.html"

    def form_valid(self, form):
        messages.success(self.request, "Datos del cliente actualizados.")
        return super().form_valid(form)


class ClienteDeleteView(AdminRequeridoMixin, View):
    def post(self, request, pk):
        cliente = get_object_or_404(Cliente, pk=pk)
        nombre = cliente.nombre_completo
        try:
            cliente.delete()
        except ValidationError as e:
            messages.error(request, e.messages[0])
            return redirect(cliente)
        messages.success(request, f"Cliente {nombre} eliminado.")
        return redirect("clientes:lista")
