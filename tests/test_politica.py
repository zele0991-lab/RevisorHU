"""Pruebas de la política: orden de evaluación, perfiles por backend, topes (D-019) y justificaciones."""

import json

import pytest

from conftest import RAIZ
from revisor.agente.politica import Politica, PoliticaInvalida

ARCHIVO = RAIZ / "config" / "politica.json"
DATOS = json.loads(ARCHIVO.read_text(encoding="utf-8"))


@pytest.fixture
def local():
    return Politica(DATOS, "local")


@pytest.fixture
def azure():
    return Politica(DATOS, "azure")


@pytest.mark.parametrize("nombre", [
    "backlog__leer_historia", "backlog__buscar_historias_similares",
    "conocimiento__listar_criterios", "conocimiento__obtener_criterio", "conocimiento__buscar_guia",
    "estimacion__historias_referencia", "estimacion__escala_estimacion",
])
def test_las_lecturas_se_permiten_en_los_dos_backends(local, azure, nombre):
    assert local.decidir(nombre)[0] == azure.decidir(nombre)[0] == "permitir"


def test_aprobar_esta_oculta_y_denegada_en_los_dos_backends(local, azure):
    for p in (local, azure):
        assert not p.visible("backlog__aprobar_para_fabrica")
        assert p.decidir("backlog__aprobar_para_fabrica") == ("denegar", "herramienta oculta por la política")


@pytest.mark.parametrize("nombre", ["backlog__registrar_revision", "backlog__proponer_division"])
def test_escrituras_permitidas_en_local_y_con_confirmacion_en_azure(local, azure, nombre):
    assert local.decidir(nombre)[0] == "permitir"
    assert azure.decidir(nombre)[0] == "confirmar"


def test_una_herramienta_sin_clasificar_se_deniega_por_defecto(local):
    assert local.decidir("backlog__borrar_todo") == ("denegar", "regla por defecto: denegar")


def test_una_herramienta_fuera_del_catalogo_visible_se_deniega(local):
    decision, razon = local.decidir("backlog__leer_historia", catalogo_visible={"otra"})
    assert decision == "denegar" and "desconocida" in razon


def test_el_tope_cuenta_solo_las_llamadas_aceptadas(local):
    """D-019: un rechazo de validación del servidor no consume la única revisión permitida."""
    nombre = "backlog__registrar_revision"
    assert local.decidir(nombre)[0] == "permitir"   # primer intento (el servidor lo rechaza: no se registra)
    assert local.decidir(nombre)[0] == "permitir"   # el agente puede corregir
    local.registrar_aceptada(nombre)                # el servidor aceptó
    decision, razon = local.decidir(nombre)
    assert decision == "denegar" and "máximo de 1" in razon


def test_el_orden_ocultar_gana_a_permitir():
    datos = {**DATOS, "permitir": [*DATOS["permitir"], "backlog__*"]}
    assert Politica(datos, "local").decidir("backlog__aprobar_para_fabrica")[0] == "denegar"


def test_denegar_gana_a_confirmar_y_permitir():
    datos = {**DATOS, "denegar": ["backlog__registrar_revision"]}
    assert Politica(datos, "azure").decidir("backlog__registrar_revision")[0] == "denegar"


def test_backend_sin_perfil_o_defecto_invalido():
    with pytest.raises(PoliticaInvalida, match="backend 'jira'"):
        Politica(DATOS, "jira")
    with pytest.raises(PoliticaInvalida, match="por_defecto"):
        Politica({**DATOS, "por_defecto": "quizas"}, "local")


def test_cada_regla_tiene_su_justificacion():
    """Requisito del prompt: cada regla lleva su justificación en _cambios."""
    claves = set(DATOS["_cambios"])
    faltan = [p for lista in ("permitir", "confirmar", "denegar", "ocultar") for p in DATOS[lista] if p not in claves]
    faltan += [f"tope {n}" for n in DATOS["max_llamadas_por_herramienta"]
               if not any(k.startswith(f"tope {n}=") for k in claves)]
    faltan += [b for b in DATOS["por_backend"] if not any(k.startswith(f"{b}:") for k in claves)]
    faltan += [] if any(k.startswith("por_defecto=") for k in claves) else ["por_defecto"]
    assert not faltan, f"reglas sin justificación en _cambios: {faltan}"
