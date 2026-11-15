from django.urls import path

from . import views

app_name = "reservaciones"

urlpatterns = [
    path("", views.ReservacionListView.as_view(), name="lista"),
    path("nueva/", views.ReservacionCreateView.as_view(), name="crear"),
    path("disponibilidad/", views.DisponibilidadView.as_view(), name="disponibilidad"),
    path("ocupacion/", views.OcupacionView.as_view(), name="ocupacion"),
    path("cotizar/", views.CotizarView.as_view(), name="cotizar"),
    path("<int:pk>/", views.ReservacionDetailView.as_view(), name="detalle"),
    path("<int:pk>/editar/", views.ReservacionUpdateView.as_view(), name="editar"),
    path("<int:pk>/cancelar/", views.ReservacionCancelarView.as_view(), name="cancelar"),
]
