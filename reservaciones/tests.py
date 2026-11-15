"""Pruebas funcionales de las reglas de negocio del PIA.

Ejecutar con:  python manage.py test
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from clientes.forms import ClienteForm
from clientes.models import Cliente
from core.permisos import GRUPO_ADMIN, GRUPO_RECEPCION
from habitaciones.models import Habitacion
from reservaciones.models import Reservacion
from reservaciones.servicios import habitaciones_libres

HOY = date.today()


def d(n):
    return HOY + timedelta(days=n)


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hab = Habitacion.objects.create(numero=101, tipo="doble", precio_noche=Decimal("1500"), capacidad=2)
        cls.hab2 = Habitacion.objects.create(numero=102, tipo="suite", precio_noche=Decimal("2500"), capacidad=4)
        cls.cliente = Cliente.objects.create(nombre="Ana", apellidos="García", correo="ana@correo.mx", telefono="8112345678")
        cls.otro = Cliente.objects.create(nombre="Luis", apellidos="Pérez", correo="luis@correo.mx", telefono="8187654321")

    def reservar(self, entrada, salida, hab=None, cliente=None, **extra):
        r = Reservacion(cliente=cliente or self.cliente, habitacion=hab or self.hab,
                        fecha_entrada=entrada, fecha_salida=salida, **extra)
        r.full_clean()
        r.save()
        return r


class Regla1Traslapes(Base):
    def test_no_permite_mismas_fechas(self):
        self.reservar(d(1), d(4))
        with self.assertRaises(ValidationError) as ctx:
            self.reservar(d(2), d(3), cliente=self.otro)
        self.assertIn("habitacion", ctx.exception.message_dict)

    def test_traslape_parcial(self):
        self.reservar(d(1), d(4))
        with self.assertRaises(ValidationError):
            self.reservar(d(3), d(6), cliente=self.otro)

    def test_salida_igual_a_entrada_siguiente_es_valida(self):
        self.reservar(d(1), d(4))
        self.reservar(d(4), d(6), cliente=self.otro)  # check-in el día del check-out
        self.assertEqual(Reservacion.objects.count(), 2)

    def test_otra_habitacion_mismas_fechas_es_valida(self):
        self.reservar(d(1), d(4))
        self.reservar(d(1), d(4), hab=self.hab2, cliente=self.otro)

    def test_cancelada_libera_las_fechas(self):
        r = self.reservar(d(1), d(4))
        r.estado = Reservacion.Estado.CANCELADA
        r.save()
        self.reservar(d(1), d(4), cliente=self.otro)

    def test_editar_misma_reservacion_no_choca_consigo(self):
        r = self.reservar(d(1), d(4))
        r.fecha_salida = d(5)
        r.full_clean()
        r.save()
        self.assertEqual(r.noches, 4)


class Regla2Fechas(Base):
    def test_salida_debe_ser_mayor(self):
        with self.assertRaises(ValidationError) as ctx:
            self.reservar(d(3), d(3))
        self.assertIn("fecha_salida", ctx.exception.message_dict)

    def test_salida_anterior(self):
        with self.assertRaises(ValidationError):
            self.reservar(d(5), d(2))

    def test_restriccion_en_base_de_datos(self):
        with self.assertRaises(IntegrityError):
            Reservacion.objects.create(cliente=self.cliente, habitacion=self.hab, fecha_entrada=d(5), fecha_salida=d(5))

    def test_no_permite_entrada_en_pasado(self):
        with self.assertRaises(ValidationError):
            self.reservar(d(-2), d(1))


class Regla3NumeroUnico(Base):
    def test_numero_repetido(self):
        h = Habitacion(numero=101, tipo="suite", precio_noche=1, capacidad=1)
        with self.assertRaises(ValidationError) as ctx:
            h.full_clean()
        self.assertIn("numero", ctx.exception.message_dict)


class Regla4CorreoUnico(Base):
    def test_correo_repetido_en_formulario(self):
        f = ClienteForm(data={"nombre": "X", "apellidos": "Y", "correo": "ANA@correo.mx", "telefono": "8100000000"})
        self.assertFalse(f.is_valid())
        self.assertIn("correo", f.errors)

    def test_correo_unico_en_base_de_datos(self):
        with self.assertRaises(IntegrityError):
            Cliente.objects.create(nombre="X", apellidos="Y", correo="ana@correo.mx", telefono="8100000000")


class Regla5EliminarHabitacion(Base):
    def test_no_elimina_con_reservaciones_activas(self):
        self.reservar(d(1), d(3))
        with self.assertRaises(ValidationError):
            self.hab.delete()
        self.assertTrue(Habitacion.objects.filter(pk=self.hab.pk).exists())

    def test_elimina_sin_reservaciones_activas(self):
        r = self.reservar(d(1), d(3))
        r.estado = Reservacion.Estado.CANCELADA
        r.save()
        self.hab.delete()
        self.assertFalse(Habitacion.objects.filter(numero=101).exists())


class OtrasValidaciones(Base):
    def test_total_se_calcula(self):
        r = self.reservar(d(1), d(4))
        self.assertEqual(r.total, Decimal("4500.00"))

    def test_capacidad(self):
        with self.assertRaises(ValidationError) as ctx:
            self.reservar(d(1), d(2), huespedes=3)
        self.assertIn("huespedes", ctx.exception.message_dict)

    def test_fuera_de_servicio(self):
        self.hab.disponible = False
        self.hab.save()
        with self.assertRaises(ValidationError):
            self.reservar(d(1), d(2))

    def test_consulta_disponibilidad(self):
        self.reservar(d(1), d(4))
        libres = list(habitaciones_libres(d(2), d(3)))
        self.assertEqual(libres, [self.hab2])


class Vistas(Base):
    def setUp(self):
        self.admin = User.objects.create_user("jefe", password="x-Clave-123")
        self.admin.groups.add(Group.objects.create(name=GRUPO_ADMIN))
        self.recep = User.objects.create_user("recep", password="x-Clave-123")
        self.recep.groups.add(Group.objects.create(name=GRUPO_RECEPCION))

    def test_login_requerido(self):
        for nombre in ["core:dashboard", "habitaciones:lista", "clientes:lista", "reservaciones:lista"]:
            r = self.client.get(reverse(nombre))
            self.assertEqual(r.status_code, 302, nombre)
            self.assertIn(reverse("login"), r.url)

    def test_paginas_cargan(self):
        self.reservar(d(0), d(2))
        self.client.force_login(self.admin)
        for url in [reverse("core:dashboard"), reverse("core:reportes"), reverse("core:usuarios"),
                    reverse("habitaciones:lista"), reverse("habitaciones:detalle", args=[self.hab.pk]),
                    reverse("clientes:lista") + "?q=ana", reverse("clientes:detalle", args=[self.cliente.pk]),
                    reverse("reservaciones:lista") + "?q=101", reverse("reservaciones:ocupacion"),
                    reverse("reservaciones:disponibilidad") + f"?entrada={d(1)}&salida={d(3)}&huespedes=1",
                    reverse("reservaciones:crear"), reverse("reservaciones:cotizar") + f"?habitacion={self.hab.pk}&entrada={d(1)}&salida={d(2)}"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_recepcionista_no_entra_a_reportes(self):
        self.client.force_login(self.recep)
        self.assertEqual(self.client.get(reverse("core:reportes")).status_code, 403)
        self.assertEqual(self.client.get(reverse("habitaciones:crear")).status_code, 403)

    def test_crear_reservacion_por_formulario(self):
        self.client.force_login(self.recep)
        datos = {"cliente": self.cliente.pk, "habitacion": self.hab.pk, "fecha_entrada": d(1),
                 "fecha_salida": d(3), "huespedes": 2, "notas": ""}
        r = self.client.post(reverse("reservaciones:crear"), datos)
        self.assertEqual(r.status_code, 302)
        # El mismo formulario otra vez debe rechazarse por traslape
        r = self.client.post(reverse("reservaciones:crear"), {**datos, "cliente": self.otro.pk})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "ya está reservada")
        self.assertEqual(Reservacion.objects.count(), 1)

    def test_cancelar(self):
        res = self.reservar(d(1), d(3))
        self.client.force_login(self.recep)
        self.client.post(reverse("reservaciones:cancelar", args=[res.pk]))
        res.refresh_from_db()
        self.assertEqual(res.estado, Reservacion.Estado.CANCELADA)

    def test_eliminar_habitacion_bloqueado_en_vista(self):
        self.reservar(d(1), d(3))
        self.client.force_login(self.admin)
        self.client.post(reverse("habitaciones:eliminar", args=[self.hab.pk]))
        self.assertTrue(Habitacion.objects.filter(pk=self.hab.pk).exists())

    def test_exportar_csv(self):
        self.reservar(d(1), d(3))
        self.client.force_login(self.admin)
        r = self.client.get(reverse("core:reportes") + "?formato=csv")
        self.assertEqual(r["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("Folio", r.content.decode("utf-8-sig"))
