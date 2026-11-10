"""Pruebas de las reglas puras del servidor: formato de HU, Gherkin y datos personales."""

import pytest

from revisor.servidores import validacion as v


@pytest.mark.parametrize("texto", [
    "Como cliente, quiero ver mi saldo, para planificar mis gastos.",
    "como Cliente quiero ver mi saldo para planificar",
    "Como cajero de sucursal,\nquiero consultar el saldo,\npara responder rápido.",
])
def test_formato_hu_valido(texto):
    assert v.es_formato_hu(texto)


@pytest.mark.parametrize("texto", [
    "Actualizar la librería de red a la versión 5.",
    "Como cliente, quiero ver mi saldo.",
    "Quiero ver mi saldo, para planificar, como cliente.",
    "",
])
def test_formato_hu_invalido(texto):
    assert not v.es_formato_hu(texto)


def test_rol_normalizado_ignora_articulos_tildes_y_mayusculas():
    assert v.rol_de("Como un Cliente de Banca Móvil, quiero a, para b") == "cliente de banca movil"
    assert v.rol_de("como cliente de banca movil quiero c para d") == "cliente de banca movil"
    assert v.rol_de("sin formato") is None


def test_gherkin():
    assert v.es_gherkin("Dado que tengo saldo, cuando transfiero, entonces veo el comprobante")
    assert v.es_gherkin("Escenario: x\n  Dado algo\n  Cuando pasa\n  Entonces resulta")
    assert not v.es_gherkin("El usuario puede transferir")
    assert not v.es_gherkin("Entonces veo el comprobante cuando transfiero dado que tengo saldo")
    assert not v.es_gherkin("Given I have funds, when I transfer, then I see the receipt")


@pytest.mark.parametrize("texto, tipo", [
    ("escribir a ana.perez@correo.com", "correo electrónico"),
    ("cédula 1-2345-6789", "número de cédula"),
    ("cédula 112345678", "número de cédula"),
    ("llamar al 8888-8888", "número de teléfono"),
    ("llamar al +506 88888888", "número de teléfono"),
    ("cuenta CR05 0152 0200 1026 2840 66", "número de cuenta (IBAN)"),
    ("tarjeta 4111 1111 1111 1111", "número de tarjeta"),
    ("cuenta 100200300400", "número de cuenta"),
])
def test_detecta_datos_personales(texto, tipo):
    assert tipo in [t for t, _ in v.buscar_datos_personales(texto)]


@pytest.mark.parametrize("texto", [
    "transferencias de hasta 25000000 colones",
    "monto máximo de 100.000 colones",
    "publicar el 2026-11-09",
    "responder en menos de 2 segundos con 3 reintentos",
    "escribir a [CORREO] o llamar a [TELEFONO]",
    "PIN de 4 dígitos y TLS 1.2",
])
def test_no_marca_textos_legitimos(texto):
    assert v.buscar_datos_personales(texto) == []


def test_el_mensaje_no_repite_el_dato_completo():
    errores = v.errores_datos_personales("historia_refinada", "correo ana.perez@correo.com")
    assert len(errores) == 1
    assert "ana.perez@correo.com" not in errores[0] and "an***" in errores[0]
