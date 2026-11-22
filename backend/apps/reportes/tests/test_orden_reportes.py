"""RF-D-ADM-05.2: todos los reportes salen de la fecha más antigua a la más reciente, con el código (id) para
desempatar, y con el mismo orden en PDF y en Excel. El encabezado dice el orden; en el Excel la fila de encabezado
queda inmovilizada y las columnas llevan autofiltro.

Se generan los cinco reportes en los dos formatos por la API, con los datos de la demo de 2026 y empates forzados
(dos usuarios y dos publicaciones con el mismo instante de registro o creación, y dos reservas creadas en el mismo
instante con el reloj fijo).
"""

import io
import re
from datetime import datetime

import pytest
from django.apps import apps
from django.utils import timezone
from openpyxl import load_workbook
from pypdf import PdfReader

from apps.reportes import archivos
from apps.reportes.models import PublicacionReporte, ReservaReporte, UsuarioReporte

pytestmark = pytest.mark.django_db

PERIODO = {"desde": "2026-01-01", "hasta": "2026-12-31"}
ORDEN = {
    "usuarios": "fecha de registro, ascendente; luego por código",
    "publicaciones": "fecha de creación, ascendente; luego por código",
    "reservas": "fecha de creación, ascendente; luego por código",
    "ingresos": "mes, ascendente",
    "demanda": "fecha, ascendente; luego por ciudad y por tipo",
}


@pytest.fixture
def datos_con_empates(demo, alojamiento_740, reservar, reloj):
    Usuario = apps.get_model("identidad", "Usuario")
    Publicacion = apps.get_model("catalogo", "Publicacion")
    instante = timezone.make_aware(datetime(2026, 6, 15, 10, 0))
    # Empates de usuarios y de publicaciones: el mismo instante; los desempata el código
    Usuario.objects.filter(correo__in=["pedro@correo.com", "sofia@correo.com"]).update(fecha_registro=instante)
    Publicacion.objects.filter(titulo__in=["Estudio Usaquén", "Cabaña del Lago"]).update(creada=instante)
    Publicacion.objects.filter(pk=alojamiento_740).update(creada=timezone.make_aware(datetime(2026, 9, 1, 8, 0)))
    # Empate de reservas: dos creadas con el reloj detenido en el mismo instante
    reloj("2026-10-15T11:00")
    reservar(alojamiento_740, "2026-12-26", "2026-12-28")
    reservar(alojamiento_740, "2026-12-28", "2026-12-30")


def _excel(admin, tipo):
    r = admin.get(f"/api/v1/admin/reportes/{tipo}", {**PERIODO, "formato": "xlsx"})
    assert r.status_code == 200, r.content
    return load_workbook(io.BytesIO(r.content))


def _texto_pdf(admin, tipo) -> str:
    r = admin.get(f"/api/v1/admin/reportes/{tipo}", {**PERIODO, "formato": "pdf"})
    assert r.status_code == 200, r.content
    return "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(r.content)).pages)


def _compacto(t) -> str:
    return re.sub(r"\s+", "", str(t))


def _clave_real(tipo, filas, col):
    """La clave por la que debe ir ordenado cada reporte, leída de las vistas (instante completo, no solo el día)."""
    if tipo == "usuarios":
        registro = dict(UsuarioReporte.objects.values_list("id", "fecha_registro"))
        return [(registro[f[col["Código"]]], f[col["Código"]]) for f in filas]
    if tipo == "publicaciones":
        creada = dict(PublicacionReporte.objects.values_list("id", "creada"))
        return [(creada[f[col["Código"]]], f[col["Código"]]) for f in filas]
    if tipo == "reservas":
        creada = dict(ReservaReporte.objects.values_list("id", "creada"))
        return [(creada[f[col["Código"]]], f[col["Código"]]) for f in filas]
    if tipo == "ingresos":
        return [f[col["Mes"]] for f in filas]
    return [(f[col["Fecha"]], f[col["Ciudad"]], f[col["Tipo de alojamiento"]]) for f in filas]


@pytest.mark.parametrize("tipo", ["usuarios", "publicaciones", "reservas", "ingresos", "demanda"])
def test_cada_reporte_sale_ordenado_igual_en_pdf_y_en_excel(datos_con_empates, entrar, tipo):
    admin = entrar("admin@inversioneslr.com")

    # ---- Excel: encabezado inmovilizado, autofiltro, "Ordenado por" y filas en orden ascendente
    hoja = _excel(admin, tipo)["Detalle"]
    cabecera = [c.value for c in hoja[archivos.FILA_CABECERA]]
    col = {nombre: i for i, nombre in enumerate(cabecera)}
    filas = [f for f in hoja.iter_rows(min_row=archivos.FILA_CABECERA + 1, values_only=True)]
    assert len(filas) >= 2, "el reporte necesita al menos dos filas para comprobar el orden"
    assert hoja.freeze_panes == f"A{archivos.FILA_CABECERA + 1}"
    assert hoja.auto_filter.ref.startswith(f"A{archivos.FILA_CABECERA}:")
    assert hoja.auto_filter.ref.endswith(str(archivos.FILA_CABECERA + len(filas)))
    assert f"Ordenado por: {ORDEN[tipo]}" in hoja["A2"].value
    clave = _clave_real(tipo, filas, col)
    assert clave == sorted(clave)

    # ---- PDF: el encabezado dice el orden y las filas aparecen en el mismo orden que en el Excel
    texto = _texto_pdf(admin, tipo)
    assert f"Ordenado por: {ORDEN[tipo]}" in " ".join(texto.split())
    compacto = _compacto(texto)
    pos = compacto.index(_compacto("".join(cabecera)))  # la tabla de detalle empieza en su encabezado
    for f in filas:
        firma = _compacto(f"{f[0]}{f[1]}")  # primera y segunda celda de la fila, tal como las escribe el PDF
        siguiente = compacto.find(firma, pos)
        assert siguiente > pos, f"la fila {f[:2]} no está después de la anterior en el PDF"
        pos = siguiente


def test_los_empates_se_resuelven_por_codigo(datos_con_empates, entrar):
    admin = entrar("admin@inversioneslr.com")
    usuarios = [f for f in _excel(admin, "usuarios")["Detalle"].iter_rows(min_row=archivos.FILA_CABECERA + 1, values_only=True)]
    empatados = [f[0] for f in usuarios if f[2] in ("pedro@correo.com", "sofia@correo.com")]
    assert empatados == sorted(empatados) and len(empatados) == 2
    reservas = [f for f in _excel(admin, "reservas")["Detalle"].iter_rows(min_row=archivos.FILA_CABECERA + 1, values_only=True)]
    mismo_dia = [f[0] for f in reservas if f[4] == "2026-10-15"]
    assert len(mismo_dia) == 2 and mismo_dia == sorted(mismo_dia)
