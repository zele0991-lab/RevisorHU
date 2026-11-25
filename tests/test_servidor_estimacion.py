"""Pruebas de servidor_estimacion: referencias, escala y validación de entradas y del archivo."""

import json

import pytest

from conftest import RAIZ, listar, llamar

REFERENCIAS = RAIZ / "datos" / "ejemplo" / "referencias_ejemplo.jsonl"


@pytest.fixture(scope="module")
def srv():
    from revisor.servidores.servidor_estimacion import construir

    return construir(["--referencias", str(REFERENCIAS)])


def test_dos_herramientas_con_esquema_estricto_y_cuando_usarlas(srv):
    herramientas = listar(srv)
    assert {t.name for t in herramientas} == {"historias_referencia", "escala_estimacion"}
    for t in herramientas:
        assert t.input_schema.get("additionalProperties") is False, t.name
        assert "Úsala" in t.description, t.name


def test_referencias_parecidas_con_puntos_reales_y_equivalente(srv):
    d = llamar(srv, "historias_referencia", {"texto": "ingresar a la app con huella", "limite": 3}).json
    primero = d["resultados"][0]
    assert primero["id"] == "REF-003" and primero["story_points_reales"] == 5
    assert primero["equivalente_escala"] == 5
    assert primero["texto"].startswith("<contenido_no_confiable>")


def test_puntos_fuera_de_la_escala_se_aproximan(srv):
    d = llamar(srv, "historias_referencia", {"texto": "sección de inversiones fondos bonos simulador", "limite": 1}).json
    assert d["resultados"][0]["story_points_reales"] == 20
    assert d["resultados"][0]["equivalente_escala"] == 13


@pytest.mark.parametrize("puntos, esperado", [(1, 1), (4, 5), (6, 5), (7, 8), (10, 8), (11, 13), (40, 13)])
def test_a_escala(puntos, esperado):
    from revisor.servidores.servidor_estimacion import a_escala

    assert a_escala(puntos) == esperado


def test_sin_referencias_parecidas(srv):
    d = llamar(srv, "historias_referencia", {"texto": "zzzz qqqq", "limite": 3}).json
    assert d["resultados"] == [] and "escala_estimacion" in d["nota"]


@pytest.mark.parametrize("args, mensaje", [
    ({"texto": "", "limite": 3}, "texto: está vacío"),
    ({"texto": "huella", "limite": 0}, "limite: 0 está fuera de rango; usa un entero entre 1 y 10"),
    ({"texto": "huella", "limite": 11}, "limite: 11 está fuera de rango"),
    ({"texto": "huella", "limite": 3, "proyecto": "x"}, "Extra inputs are not permitted"),
])
def test_historias_referencia_rechaza_entradas_invalidas(srv, args, mensaje):
    r = llamar(srv, "historias_referencia", args)
    assert r.es_error and mensaje in r.texto, r.texto


def test_escala_y_regla_de_division(srv):
    d = llamar(srv, "escala_estimacion", {}).json
    assert d["escala"] == [1, 2, 3, 5, 8, 13] and d["umbral_division"] == 8
    regla = d["regla_division"].lower()
    assert "más de 8 puntos" in regla and "único problema" in regla and "'devolver'" in regla


def test_escala_no_acepta_argumentos(srv):
    r = llamar(srv, "escala_estimacion", {"limite": 3})
    assert r.es_error and "Extra inputs" in r.texto


# ===================================================================== archivo de referencias
def _jsonl(tmp_path, registros):
    ruta = tmp_path / "r.jsonl"
    ruta.write_text("\n".join(json.dumps(r) for r in registros), encoding="utf-8")
    return ruta


@pytest.mark.parametrize("registros, mensaje", [
    ([{"id": "A", "texto": "t"}], "r.jsonl:1: faltan campos: story_points"),
    ([{"id": "A", "texto": "t", "story_points": 0}], "story_points debe ser un entero positivo"),
    ([{"id": "A", "texto": "t", "story_points": "5"}], "story_points debe ser un entero positivo"),
    ([{"id": "A", "texto": "t", "story_points": True}], "story_points debe ser un entero positivo"),
    ([{"id": "A", "texto": "t", "story_points": 3}, {"id": "A", "texto": "u", "story_points": 5}], "r.jsonl:2: id duplicado 'A'"),
    ([], "no hay referencias"),
])
def test_referencias_invalidas_impiden_arrancar(tmp_path, registros, mensaje):
    from revisor.servidores.servidor_estimacion import ReferenciasInvalidas, cargar_referencias

    with pytest.raises(ReferenciasInvalidas, match=mensaje):
        cargar_referencias(_jsonl(tmp_path, registros))


def test_main_sin_archivo_no_arranca(tmp_path, capsys):
    from revisor.servidores.servidor_estimacion import main

    assert main(["--referencias", str(tmp_path / "no.jsonl")]) == 2
    assert "no arranca" in capsys.readouterr().err
