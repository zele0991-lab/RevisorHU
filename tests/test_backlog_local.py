"""Pruebas de BacklogLocal: carga, validación de archivos, búsqueda y escrituras en borrador."""

import json

import pytest

from revisor.backlog import ErrorBacklog, HistoriaNoEncontrada, Recomendacion, Revision
from revisor.backlog.local import BacklogLocal


def _jsonl(ruta, registros):
    ruta.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in registros), encoding="utf-8")
    return ruta


def test_carga_el_backlog_de_ejemplo(backlog):
    assert backlog.ids[:3] == ["HU-001", "HU-002", "HU-003"]
    h = backlog.leer_historia("HU-007")
    assert h.sistema == "core" and h.story_points == 3


def test_carga_jsonl_y_descarta_metadatos_de_investigacion(tmp_path):
    """es_dificil y motivo_dificultad le darían pistas al modelo: no deben salir del backlog."""
    ruta = _jsonl(tmp_path / "casos.jsonl", [
        {"id": "C-1", "texto": "Como x, quiero y, para z", "sistema": "core", "proyecto": "p",
         "es_dificil": True, "motivo_dificultad": "duplicado"},
    ])
    h = BacklogLocal([ruta], tmp_path / "estado").leer_historia("C-1")
    assert h.titulo == "" and h.story_points is None
    assert not hasattr(h, "es_dificil") and "duplicado" not in repr(h)


def test_varios_archivos_se_combinan(tmp_path, backlog):
    extra = _jsonl(tmp_path / "contexto.jsonl", [{"id": "CTX-1", "texto": "t", "sistema": "core", "proyecto": "p"}])
    from conftest import BACKLOG_EJEMPLO
    b = BacklogLocal([BACKLOG_EJEMPLO, extra], tmp_path / "estado")
    assert "CTX-1" in b.ids and "HU-001" in b.ids


@pytest.mark.parametrize("registro, esperado", [
    ({"id": "X", "texto": "t", "proyecto": "p"}, "faltan campos obligatorios: sistema"),
    ({"id": "X", "texto": "  ", "sistema": "s", "proyecto": "p"}, "faltan campos obligatorios: texto"),
    ({"id": "X", "texto": "t", "sistema": "s", "proyecto": "p", "story_points": "5"}, "story_points debe ser un entero"),
    ("no es objeto", "cada historia debe ser un objeto"),
])
def test_rechaza_registros_invalidos_diciendo_donde(tmp_path, registro, esperado):
    ruta = _jsonl(tmp_path / "malo.jsonl", [registro])
    with pytest.raises(ErrorBacklog, match=esperado) as e:
        BacklogLocal([ruta], tmp_path / "estado")
    assert "malo.jsonl:1" in str(e.value)


def test_rechaza_ids_duplicados(tmp_path):
    r = {"id": "X", "texto": "t", "sistema": "s", "proyecto": "p"}
    with pytest.raises(ErrorBacklog, match="id duplicado 'X'"):
        BacklogLocal([_jsonl(tmp_path / "d.jsonl", [r, r])], tmp_path / "estado")


def test_rechaza_json_invalido_archivo_inexistente_y_backlog_vacio(tmp_path):
    malo = tmp_path / "malo.json"
    malo.write_text("{no json", encoding="utf-8")
    with pytest.raises(ErrorBacklog, match="JSON inválido"):
        BacklogLocal([malo], tmp_path / "estado")
    with pytest.raises(ErrorBacklog, match="No existe el archivo"):
        BacklogLocal([tmp_path / "no_existe.json"], tmp_path / "estado")
    vacio = tmp_path / "vacio.json"
    vacio.write_text("[]", encoding="utf-8")
    with pytest.raises(ErrorBacklog, match="vacío"):
        BacklogLocal([vacio], tmp_path / "estado")


def test_leer_historia_inexistente(backlog):
    with pytest.raises(HistoriaNoEncontrada):
        backlog.leer_historia("HU-999")


def test_buscar_similares_encuentra_el_duplicado(backlog):
    texto = backlog.leer_historia("HU-001").texto
    resultados = backlog.buscar_similares(texto, 3)
    # La propia HU no da 1.0 exacto porque el índice incluye también el título.
    assert [r.historia.id for r in resultados] == ["HU-001", "HU-003", "HU-008"]
    assert resultados[0].similitud > 0.9 > resultados[1].similitud > 0.3


def test_buscar_similares_es_determinista_y_respeta_el_limite(backlog):
    a = backlog.buscar_similares("cliente app contraseña", 4)
    b = backlog.buscar_similares("cliente app contraseña", 4)
    assert a == b and len(a) <= 4


def test_buscar_sin_coincidencias_devuelve_lista_vacia(backlog):
    assert backlog.buscar_similares("zzzz qqqq", 5) == []


def _revision(id="HU-001"):
    return Revision(id_historia=id, decision="devolver", tipo="funcional", estimacion=3,
                    defectos=["PRB-001"], recomendaciones=[Recomendacion("PRB-001", "Agregar criterios")])


def test_registrar_revision_escribe_borrador_y_saca_de_pendientes(backlog, tmp_path):
    assert "HU-001" in [h.id for h in backlog.listar_pendientes(100)]
    ref = backlog.registrar_revision(_revision())
    datos = json.loads((tmp_path / "estado" / "revisiones" / "HU-001__prueba.json").read_text(encoding="utf-8"))
    assert ref.endswith("HU-001__prueba.json")
    assert datos["estado"] == "borrador" and datos["recomendaciones"][0]["defecto"] == "PRB-001"
    assert "HU-001" not in [h.id for h in backlog.listar_pendientes(100)]


def test_listar_pendientes_respeta_el_limite(backlog):
    assert len(backlog.listar_pendientes(2)) == 2


def test_escrituras_de_division_y_aprobacion(backlog, tmp_path):
    backlog.proponer_division("HU-004", ["Como a, quiero b, para c", "Como a, quiero d, para e"])
    backlog.aprobar_para_fabrica("HU-005")
    assert (tmp_path / "estado" / "divisiones" / "HU-004__prueba.json").exists()
    assert (tmp_path / "estado" / "aprobaciones" / "HU-005__prueba.json").exists()


def test_escrituras_sobre_historia_inexistente_fallan(backlog):
    with pytest.raises(HistoriaNoEncontrada):
        backlog.registrar_revision(_revision("HU-999"))


def test_ids_peligrosos_no_escapan_de_la_carpeta_de_estado(tmp_path):
    ruta = _jsonl(tmp_path / "h.jsonl", [{"id": "../../fuera", "texto": "t", "sistema": "s", "proyecto": "p"}])
    b = BacklogLocal([ruta], tmp_path / "estado", marca="m")
    b.aprobar_para_fabrica("../../fuera")
    assert (tmp_path / "estado" / "aprobaciones" / "______fuera__m.json").exists()
