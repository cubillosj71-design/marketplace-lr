"""RF-D-USU-01.3: el enlace de recuperación llega al correo de la cuenta y la API no lo muestra ni revela si el
correo está registrado. Las pruebas usan el backend de correo en memoria (mailoutbox): no se envía nada de verdad."""

import re

import pytest

from apps.auditoria import services as auditoria
from apps.identidad import services

pytestmark = pytest.mark.django_db
RUTA = "/api/v1/identidad/recuperacion"


def _token(correo) -> str:
    return re.search(r"/#/restablecer/([\w-]+)", correo.body).group(1)


def test_el_correo_trae_un_enlace_valido_para_cambiar_la_contrasena(demo, cliente, mailoutbox):
    assert cliente.post(RUTA, {"correo": "Huesped@Correo.com "}, format="json").status_code == 202
    correo = mailoutbox[0]
    assert correo.to == ["huesped@correo.com"] and "contraseña" in correo.subject.lower()
    assert "20 minutos" in correo.body and correo.alternatives[0][1] == "text/html"
    token = _token(correo)
    assert services.consultar_estado_enlace(token) == "valido"
    assert cliente.post(f"{RUTA}/{token}", {"password": "NuevaClave2026"}, format="json").status_code == 200
    assert services.consultar_estado_enlace(token) == "usado"


def test_misma_respuesta_exista_o_no_la_cuenta(demo, cliente, mailoutbox):
    existe = cliente.post(RUTA, {"correo": "huesped@correo.com"}, format="json")
    no_existe = cliente.post(RUTA, {"correo": "nadie@correo.com"}, format="json")
    assert (existe.status_code, existe.json()) == (no_existe.status_code, no_existe.json())
    assert len(mailoutbox) == 1  # solo a la cuenta que existe


def test_si_el_correo_falla_el_usuario_ve_lo_mismo_y_queda_en_la_auditoria(demo, cliente, mailoutbox, monkeypatch):
    from django.core.mail import EmailMultiAlternatives

    def caida(self, fail_silently=False):
        raise ConnectionRefusedError("smtp.gmail.com no respondió")

    monkeypatch.setattr(EmailMultiAlternatives, "send", caida)
    r = cliente.post(RUTA, {"correo": "huesped@correo.com"}, format="json")
    assert r.status_code == 202 and "Revisa tu bandeja" in r.json()["detalle"]
    falla = auditoria.consultar_eventos(accion="CorreoRecuperacionNoEnviado").get()
    assert falla.exitoso is False and falla.detalle["error"] == "ConnectionRefusedError"


def test_el_nombre_del_usuario_se_escapa_en_el_html(demo, mailoutbox):
    from django.apps import apps

    apps.get_model("identidad", "Usuario").objects.filter(correo="huesped@correo.com").update(nombre_completo="<script>x</script>")
    services.solicitar_recuperacion("huesped@correo.com")
    html = mailoutbox[0].alternatives[0][0]
    assert "<script>" not in html and "&lt;script&gt;" in html
