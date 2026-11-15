"""Carga datos de demostración: usuarios, habitaciones con foto, clientes y reservaciones.

Uso:
    python manage.py seed_demo           # crea lo que falte
    python manage.py seed_demo --reset   # borra clientes/habitaciones/reservaciones y vuelve a cargar
"""
import random
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import Group, User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction

from clientes.models import Cliente
from core.permisos import GRUPO_ADMIN, GRUPO_RECEPCION
from habitaciones.models import Habitacion
from reservaciones.models import Reservacion

PASSWORD = "Paradise2026!"

HABITACIONES = [
    # numero, tipo, precio, capacidad, descripcion
    (101, "individual", "950", 1, "Cama matrimonial, escritorio de trabajo y vista al jardín."),
    (102, "individual", "950", 1, "Cama matrimonial y regadera de lluvia."),
    (103, "individual", "1050", 2, "Cama queen, balcón pequeño con vista a la alberca."),
    (104, "individual", "1050", 2, "Cama queen, ideal para viajes de negocio."),
    (201, "doble", "1450", 3, "Dos camas matrimoniales y sofá."),
    (202, "doble", "1450", 3, "Dos camas matrimoniales, vista a la ciudad."),
    (203, "doble", "1550", 4, "Dos camas queen. En remodelación de baño."),
    (204, "doble", "1650", 4, "Dos camas queen y balcón con vista al mar."),
    (205, "doble", "1650", 4, "Dos camas queen, conectada con la 204."),
    (301, "suite", "2650", 4, "Recámara king, sala independiente y tina."),
    (302, "suite", "2750", 4, "Recámara king, terraza con camastros."),
    (303, "suite", "2900", 5, "Suite familiar con sofá cama y cocineta."),
    (401, "presidencial", "5900", 6, "Dos recámaras, comedor para 8 y jacuzzi privado."),
    (402, "presidencial", "6500", 6, "Piso completo con terraza panorámica y mayordomo."),
]

NOMBRES = ["Ana Sofía", "Luis Fernando", "María José", "Carlos", "Daniela", "Jorge", "Valeria", "Ricardo",
           "Fernanda", "Alejandro", "Paola", "Miguel Ángel", "Andrea", "José Luis", "Mariana", "Eduardo",
           "Regina", "Héctor", "Ximena", "Roberto", "Camila", "Sergio", "Natalia", "Arturo", "Renata",
           "Diego", "Lucía", "Óscar", "Gabriela", "Emilio"]
APELLIDOS = ["García López", "Martínez Treviño", "Hernández Garza", "González Villarreal", "Rodríguez Salinas",
             "Pérez Cantú", "Sánchez Elizondo", "Ramírez Guerra", "Flores Leal", "Torres Cavazos",
             "Rivera Montemayor", "Gómez de la Garza", "Díaz Zambrano", "Cruz Benavides", "Morales Tamez",
             "Reyes Lozano", "Ortiz Chapa", "Gutiérrez Quiroga", "Chávez Sada", "Ruiz Garza"]

COLORES = {
    "individual": ((14, 110, 121), (120, 196, 190)),
    "doble": ((22, 74, 104), (98, 160, 196)),
    "suite": ((88, 62, 122), (196, 150, 196)),
    "presidencial": ((140, 92, 22), (242, 196, 92)),
}


def imagen_habitacion(numero, tipo):
    """Genera una ilustración simple de la habitación (sin descargar nada de internet)."""
    from PIL import Image, ImageDraw, ImageFont

    w, h = 800, 520
    c1, c2 = COLORES[tipo]
    img = Image.new("RGB", (w, h), c1)
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        d.line([(0, y), (w, y)], fill=tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3)))
    # ventana
    d.rounded_rectangle([520, 70, 730, 250], radius=10, fill=(235, 246, 246), outline=(255, 255, 255), width=6)
    d.line([(625, 70), (625, 250)], fill=(255, 255, 255), width=5)
    d.ellipse([560, 110, 610, 160], fill=(242, 181, 68))
    # cama
    d.rounded_rectangle([90, 300, 560, 430], radius=18, fill=(250, 250, 248))
    d.rounded_rectangle([90, 230, 140, 430], radius=10, fill=(60, 44, 36))
    d.rounded_rectangle([160, 270, 280, 310], radius=14, fill=(226, 236, 236))
    d.rounded_rectangle([300, 270, 420, 310], radius=14, fill=(226, 236, 236))
    d.rectangle([330, 300, 560, 430], fill=c1)
    d.rectangle([0, 430, w, h], fill=tuple(max(0, v - 30) for v in c1))
    # lámpara y planta para dar un poco de vida
    d.rectangle([600, 330, 690, 430], fill=(60, 44, 36))
    d.polygon([(615, 250), (675, 250), (690, 300), (600, 300)], fill=(250, 238, 210))
    d.line([(645, 300), (645, 330)], fill=(60, 44, 36), width=5)
    d.rounded_rectangle([40, 360, 72, 430], radius=6, fill=(196, 120, 80))
    for dx, dy in ((-14, -40), (8, -58), (24, -34), (-2, -70)):
        d.ellipse([56 + dx - 16, 360 + dy - 26, 56 + dx + 16, 360 + dy + 26], fill=(46, 120, 86))
    buf = BytesIO()
    img.save(buf, "JPEG", quality=85)
    return ContentFile(buf.getvalue(), name=f"hab_{numero}.jpg")


class Command(BaseCommand):
    help = "Carga usuarios, habitaciones, clientes y reservaciones de demostración."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Borra los datos existentes antes de cargar.")

    @transaction.atomic
    def handle(self, *args, **opts):
        random.seed(2114932)
        if opts["reset"]:
            Reservacion.objects.all().delete()
            Cliente.objects.all().delete()
            Habitacion.objects.all().delete()
            self.stdout.write("Datos anteriores eliminados.")

        g_admin, _ = Group.objects.get_or_create(name=GRUPO_ADMIN)
        g_recep, _ = Group.objects.get_or_create(name=GRUPO_RECEPCION)

        if not User.objects.filter(username="admin").exists():
            u = User.objects.create_superuser("admin", "", PASSWORD, first_name="Ruben", last_name="Lemus")
            u.groups.add(g_admin)
        if not User.objects.filter(username="recepcion").exists():
            u = User.objects.create_user("recepcion", "", PASSWORD, first_name="Laura", last_name="Recepción")
            u.groups.add(g_recep)

        for numero, tipo, precio, cap, desc in HABITACIONES:
            hab, creada = Habitacion.objects.get_or_create(
                numero=numero,
                defaults=dict(tipo=tipo, precio_noche=Decimal(precio), capacidad=cap,
                              descripcion=desc, disponible=numero != 203),
            )
            if creada or not hab.imagen:
                hab.imagen.save(f"hab_{numero}.jpg", imagen_habitacion(numero, tipo), save=True)

        if Cliente.objects.count() < 30:
            usados = set(Cliente.objects.values_list("correo", flat=True))
            for i, nombre in enumerate(NOMBRES):
                ap = APELLIDOS[i % len(APELLIDOS)]
                base = f"{nombre.split()[0]}.{ap.split()[0]}".lower()
                base = base.translate(str.maketrans("áéíóúñ", "aeioun"))
                correo = f"{base}{i}@correo.mx"
                if correo in usados:
                    continue
                Cliente.objects.create(nombre=nombre, apellidos=ap, correo=correo,
                                       telefono=f"81 {random.randint(1000, 9999)} {random.randint(1000, 9999)}")

        if not Reservacion.objects.exists():
            self._reservaciones()

        self.stdout.write(self.style.SUCCESS(
            f"Listo: {Habitacion.objects.count()} habitaciones, {Cliente.objects.count()} clientes, "
            f"{Reservacion.objects.count()} reservaciones.\n"
            f"Usuarios: admin / {PASSWORD}  (Administrador)   recepcion / {PASSWORD}  (Recepcionista)"
        ))

    def _reservaciones(self):
        hoy = date.today()
        clientes = list(Cliente.objects.all())
        admin = User.objects.get(username="admin")
        for hab in Habitacion.objects.all():
            dia = hoy - timedelta(days=180)
            limite = hoy + timedelta(days=45)
            while dia < limite:
                dia += timedelta(days=random.choice([0, 1, 2, 3, 4, 6, 9]))
                noches = random.choice([1, 2, 2, 3, 3, 4, 5, 7])
                salida = dia + timedelta(days=noches)
                if salida > limite:
                    break
                if not hab.disponible and salida > hoy - timedelta(days=20):
                    break
                if salida <= hoy:
                    estado = Reservacion.Estado.CANCELADA if random.random() < 0.1 else Reservacion.Estado.FINALIZADA
                elif dia > hoy + timedelta(days=10):
                    estado = random.choice([Reservacion.Estado.CONFIRMADA, Reservacion.Estado.PENDIENTE])
                else:
                    estado = Reservacion.Estado.CONFIRMADA
                Reservacion.objects.create(
                    cliente=random.choice(clientes), habitacion=hab,
                    fecha_entrada=dia, fecha_salida=salida,
                    huespedes=random.randint(1, hab.capacidad), estado=estado, creada_por=admin,
                )
                dia = salida
