# Hotel Paradise · Sistema de Reservación de Hotel

PIA de Django. Proyecto individual de **Ruben Lemus Morales** (matrícula 2114932), FACPYA, UANL.

Aplicación web para que el personal del hotel administre habitaciones, clientes y reservaciones, consulte disponibilidad y genere reportes. Valida automáticamente que una habitación no se reserve dos veces en las mismas fechas.

## Cómo ejecutarlo

Requisitos: Python 3.10 o superior.

```bash
# 1. Crear y activar un entorno virtual
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # macOS / Linux

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Crear la base de datos (si no usas la db.sqlite3 incluida)
python manage.py migrate
python manage.py seed_demo     # usuarios, 14 habitaciones con foto, 30 clientes y reservaciones de ejemplo

# 4. Levantar el servidor
python manage.py runserver
```

Abre http://127.0.0.1:8000 e inicia sesión.

| Usuario     | Contraseña      | Rol           | Puede hacer |
|-------------|-----------------|---------------|-------------|
| `admin`     | `Paradise2026!` | Administrador | Todo: habitaciones, reportes, usuarios y panel Django (`/admin`) |
| `recepcion` | `Paradise2026!` | Recepcionista | Clientes, reservaciones, disponibilidad, mapa y dashboard |

> Las reservaciones de demo se generan alrededor de la fecha en que corres `seed_demo`. Para volver a generarlas desde cero: `python manage.py seed_demo --reset`.

## Funcionalidades

- **Login / logout** y control de usuarios por rol (grupos *Administrador* y *Recepcionista*). Todas las páginas requieren sesión.
- **Dashboard**: total de clientes, habitaciones, reservaciones, habitaciones disponibles hoy e ingresos generados; llegadas y salidas del día, gráfica de ingresos de 6 meses y mapa de ocupación de 14 días.
- **CRUD Habitaciones** con fotografía, tipos (Individual, Doble, Suite, Presidencial), estado “fuera de servicio” y búsqueda por número, tipo y estado.
- **CRUD Clientes** con validación de correo único y teléfono, búsqueda por nombre, apellidos, correo o teléfono, e historial de estancias.
- **CRUD Reservaciones** (crear, consultar, modificar, cancelar) con cálculo automático del total y **cotización en vivo** mientras llenas el formulario.
- **Consulta de disponibilidad** por fechas, huéspedes y tipo de habitación.
- **Mapa de ocupación** (habitaciones × días): clic en un hueco libre para reservar.
- **Reportes** por rango de fechas: ingresos, noches vendidas, tarifa promedio, ocupación, ingresos por tipo y por mes, mejores clientes y habitaciones, exportación a CSV e impresión.
- **Panel administrativo de Django** personalizado (miniaturas, filtros, acciones, reservaciones en línea).

## Reglas de negocio y dónde están

| Regla | Implementación |
|-------|----------------|
| 1. Una habitación no se reserva dos veces en las mismas fechas | `Reservacion.clean()` + `ReservacionQuerySet.traslapes()` en `reservaciones/models.py`; se revalida dentro de una transacción al guardar (`reservaciones/views.py`). El día de salida queda libre para un nuevo check-in. |
| 2. La salida debe ser mayor que la entrada | `Reservacion.clean()` y `CheckConstraint` en la base de datos |
| 3. Números de habitación no repetidos | `Habitacion.numero` con `unique=True` |
| 4. Correo del cliente único | `Cliente.correo` con `unique=True`, restricción sin distinguir mayúsculas y validación en `ClienteForm` |
| 5. No eliminar habitación con reservaciones activas | `Habitacion.delete()` lanza `ValidationError`; la vista y el admin muestran el mensaje |

Validaciones extra: no se reserva en fechas pasadas, ni más huéspedes que la capacidad, ni habitaciones fuera de servicio.

## Pruebas

```bash
python manage.py test
```

26 pruebas cubren las cinco reglas de negocio, los permisos por rol, las vistas y la exportación CSV.

## Estructura

```
config/           settings y URLs del proyecto
core/             dashboard, reportes, usuarios, permisos, comando seed_demo
habitaciones/     modelo Habitacion, CRUD, admin
clientes/         modelo Cliente, CRUD, búsquedas
reservaciones/    modelo Reservacion, CRUD, disponibilidad, mapa, cotizador, pruebas
templates/        plantillas (Bootstrap 5)
static/           CSS y JS propios
media/            fotografías de habitaciones
```

Flujo de Django aplicado: **Usuario → URL → Vista → Formulario → Modelo → Base de datos → Template → Navegador**.


## Tecnologías

Django 5.1, SQLite, Bootstrap 5.3, Bootstrap Icons, Chart.js y Pillow.
