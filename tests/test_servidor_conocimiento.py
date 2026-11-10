"""Pruebas de servidor_conocimiento con el catálogo y las guías reales, por el protocolo MCP."""

import pytest
import yaml

from conftest import RAIZ, listar, llamar

GUIAS = RAIZ / "conocimiento"
CATALOGO = GUIAS / "criterios.yaml"


@pytest.fixture(scope="module")
def srv():
    from revisor.servidores.servidor_conocimiento import construir

    return construir(["--catalogo", str(CATALOGO), "--guias", str(GUIAS)])


@pytest.fixture(scope="module")
def catalogo():
    from revisor.conocimiento.catalogo import cargar_catalogo

    return cargar_catalogo(CATALOGO)


def test_tres_herramientas_con_esquema_estricto_y_cuando_usarlas(srv):
    herramientas = listar(srv)
    assert {t.name for t in herramientas} == {"listar_criterios", "obtener_criterio", "buscar_guia"}
    for t in herramientas:
        assert t.input_schema.get("additionalProperties") is False, t.name
        assert "Úsala" in t.description, t.name


def test_las_descripciones_muestran_los_valores_del_catalogo(srv):
    desc = next(t for t in listar(srv) if t.name == "listar_criterios").description
    assert "banca_movil" in desc and "core" in desc and "todos" in desc


# ===================================================================== listar_criterios
def test_listar_devuelve_generales_mas_los_del_sistema_y_solo_tres_campos(srv, catalogo):
    d = llamar(srv, "listar_criterios", {"sistema": "banca_movil"}).json
    ids = [c["id"] for c in d["criterios"]]
    assert ids == [c.id for c in catalogo.aplicables("banca_movil")]
    assert d["total"] == len(ids) and d["version_catalogo"] == catalogo.version
    assert all(set(c) == {"id", "nombre", "severidad"} for c in d["criterios"]), "costo controlado"


def test_listar_para_un_sistema_sin_criterios_propios_y_para_todos(srv, catalogo):
    core = [c["id"] for c in llamar(srv, "listar_criterios", {"sistema": "core"}).json["criterios"]]
    todos = [c["id"] for c in llamar(srv, "listar_criterios", {"sistema": "todos"}).json["criterios"]]
    assert core == todos == [c.id for c in catalogo.aplicables("todos")]


def test_listar_filtra_por_categoria(srv, catalogo):
    d = llamar(srv, "listar_criterios", {"sistema": "banca_movil", "categoria": "banca_movil"}).json
    assert {c["id"] for c in d["criterios"]} == {c.id for c in catalogo.aplicables("banca_movil", "banca_movil")}


def test_categoria_null_equivale_a_todas(srv):
    a = llamar(srv, "listar_criterios", {"sistema": "core", "categoria": None}).json
    b = llamar(srv, "listar_criterios", {"sistema": "core"}).json
    assert a["criterios"] == b["criterios"]


@pytest.mark.parametrize("args, mensaje", [
    ({"sistema": "banca"}, "sistema: 'banca' no existe en el catálogo; usa uno de: banca_movil, core, todos"),
    ({"sistema": "core", "categoria": "seguridad"}, "categoria: 'seguridad' no existe en el catálogo"),
    ({"sistema": "core", "extra": 1}, "Extra inputs are not permitted"),
])
def test_listar_rechaza_valores_que_no_estan_en_el_catalogo(srv, args, mensaje):
    r = llamar(srv, "listar_criterios", args)
    assert r.es_error and mensaje in r.texto, r.texto


def test_los_sistemas_validos_salen_del_yaml_no_del_codigo(tmp_path):
    from revisor.servidores.servidor_conocimiento import construir

    datos = yaml.safe_load(CATALOGO.read_text(encoding="utf-8"))
    datos["sistemas"].append("tarjetas")
    ruta = tmp_path / "c.yaml"
    ruta.write_text(yaml.safe_dump(datos, allow_unicode=True), encoding="utf-8")
    srv = construir(["--catalogo", str(ruta), "--guias", str(GUIAS)])
    assert not llamar(srv, "listar_criterios", {"sistema": "tarjetas"}).es_error


# ===================================================================== obtener_criterio
def test_obtener_devuelve_el_detalle_completo(srv, catalogo):
    c = catalogo.aplicables("banca_movil", "banca_movil")[0]
    d = llamar(srv, "obtener_criterio", {"id": c.id}).json["criterio"]
    assert d["como_verificar"] == c.como_verificar and d["ejemplo_no_cumple"] == c.ejemplo_no_cumple
    assert d["aplica_a"] == ["banca_movil"] and d["estado"] == "activo"


def test_obtener_un_id_inexistente_sugiere_los_cercanos(srv, catalogo):
    real = catalogo.ids_activos()[0]
    casi = real.lower()  # error típico: el id en minúsculas
    r = llamar(srv, "obtener_criterio", {"id": casi})
    assert r.es_error and f"No existe el criterio '{casi}'" in r.texto
    assert f"¿Quisiste decir: {real}" in r.texto, "el id correcto va primero"


def test_obtener_sin_parecidos_no_inventa_sugerencias(srv):
    r = llamar(srv, "obtener_criterio", {"id": "ZZZZZ-999"})
    assert r.es_error and "¿Quisiste decir" not in r.texto and "no los inventes" in r.texto


@pytest.mark.parametrize("id", ["", "X" * 21])
def test_obtener_rechaza_ids_de_largo_invalido(srv, id):
    r = llamar(srv, "obtener_criterio", {"id": id})
    assert r.es_error and "entre 1 y 20 caracteres" in r.texto


def test_obtener_un_obsoleto_indica_su_reemplazo(tmp_path):
    from revisor.servidores.servidor_conocimiento import construir

    datos = yaml.safe_load(CATALOGO.read_text(encoding="utf-8"))
    viejo, nuevo = datos["criterios"][0], datos["criterios"][1]
    viejo.update(estado="obsoleto", reemplazado_por=nuevo["id"])
    ruta = tmp_path / "c.yaml"
    ruta.write_text(yaml.safe_dump(datos, allow_unicode=True), encoding="utf-8")
    srv = construir(["--catalogo", str(ruta), "--guias", str(GUIAS)])

    d = llamar(srv, "obtener_criterio", {"id": viejo["id"]}).json
    assert d["criterio"]["estado"] == "obsoleto"
    assert d["vigente"]["id"] == nuevo["id"] and "OBSOLETO" in d["aviso"]
    listado = llamar(srv, "listar_criterios", {"sistema": "core"}).json["criterios"]
    assert viejo["id"] not in [c["id"] for c in listado], "un obsoleto no se lista"


# ===================================================================== buscar_guia
def test_buscar_guia_encuentra_la_seccion_relevante(srv):
    d = llamar(srv, "buscar_guia", {"texto": "cuándo dividir una historia grande", "limite": 3}).json
    assert d["resultados"] and d["resultados"][0]["fuente"] == "invest.md"
    assert "dividir" in d["resultados"][0]["seccion"].lower()


def test_buscar_guia_de_banca_movil(srv):
    d = llamar(srv, "buscar_guia", {"texto": "enmascarado número de cuenta notificaciones", "limite": 2}).json
    assert d["resultados"][0]["fuente"] == "banca_movil.md"


@pytest.mark.parametrize("args, mensaje", [
    ({"texto": " ", "limite": 2}, "texto: está vacío"),
    ({"texto": "dividir", "limite": 0}, "limite: 0 está fuera de rango; usa un entero entre 1 y 5"),
    ({"texto": "dividir", "limite": 6}, "limite: 6 está fuera de rango"),
    ({"texto": "x" * 1001, "limite": 2}, "el máximo es 1000"),
])
def test_buscar_guia_rechaza_entradas_invalidas(srv, args, mensaje):
    r = llamar(srv, "buscar_guia", args)
    assert r.es_error and mensaje in r.texto


# ===================================================================== arranque
def test_con_catalogo_invalido_no_arranca(tmp_path, capsys):
    from revisor.servidores.servidor_conocimiento import main

    malo = tmp_path / "c.yaml"
    malo.write_text("version: '1.0.0'\n", encoding="utf-8")
    assert main(["--catalogo", str(malo), "--guias", str(GUIAS)]) == 2
    err = capsys.readouterr().err
    assert "no arranca" in err and "'categorias'" in err


def test_sin_guias_no_arranca(tmp_path, capsys):
    from revisor.servidores.servidor_conocimiento import main

    assert main(["--catalogo", str(CATALOGO), "--guias", str(tmp_path)]) == 2
    assert "No hay guías" in capsys.readouterr().err
