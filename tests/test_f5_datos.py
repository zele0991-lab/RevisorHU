"""
Pruebas de la F5: descarga y extracción de TAWOS, construcción de casos, ataques, etiquetado y acuerdo.

Sin red: el analizador del volcado y la construcción se prueban con datos en memoria o archivos
temporales; los archivos versionados (casos, contexto, referencias, ataques) se verifican tal cual.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "datos"))
sys.path.insert(0, str(RAIZ / "experimentos"))

import acuerdo  # noqa: E402
import construir_casos  # noqa: E402
import descargar  # noqa: E402
import etiquetar  # noqa: E402
from revisor.backlog.local import BacklogLocal  # noqa: E402
from revisor.conocimiento.catalogo import cargar_catalogo  # noqa: E402
from revisor.servidores.servidor_estimacion import cargar_referencias  # noqa: E402

CASOS = RAIZ / "datos" / "evaluacion" / "casos.jsonl"
CONTEXTO = RAIZ / "datos" / "evaluacion" / "backlog_contexto.jsonl"
REFERENCIAS = RAIZ / "datos" / "referencias" / "referencias_tawos.jsonl"
ATAQUES = RAIZ / "datos" / "ataques" / "ataques.jsonl"
BACKLOG_ATAQUES = RAIZ / "datos" / "ataques" / "backlog_ataques.jsonl"


def _jsonl(ruta: Path) -> list[dict]:
    return [json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()]


# ================================================================= TAWOS: analizador del volcado

def test_valores_sql_escapes_nulos_y_numeros():
    linea = ("INSERT INTO `Issue` VALUES (1,'a\\'b','x''y',NULL,3.5,'(paren), coma','salto\\nlinea'),"
             "(2,'',NULL,-4,0,'\\\\',''); \n")
    filas = list(descargar.valores_sql(linea))
    assert filas == [[1, "a'b", "x'y", None, 3.5, "(paren), coma", "salto\nlinea"],
                     [2, "", None, -4, 0, "\\", ""]]


def _fila(**cambios):
    base = dict.fromkeys(descargar.COLUMNAS_ISSUE, None)
    base.update({"Issue_Key": "ABC-1", "Title": '"Add export"',
                 "Description_Text": '"""Users need a ""CSV"" export of the monthly reports."""',
                 "Type": "Story", "Story_Point": 3.0, "Title_Changed_After_Estimation": 0,
                 "Description_Changed_After_Estimation": 0, "Story_Point_Changed_After_Estimation": 0,
                 "Creator_ID": 77, "Reporter_ID": 88, "Assignee_ID": 99})
    base.update(cambios)
    return [base[c] for c in descargar.COLUMNAS_ISSUE]


def test_candidata_limpia_y_sin_personas():
    r = descargar.candidata(_fila())
    assert r == {"id": "TAWOS-ABC-1", "texto": 'Add export. Users need a "CSV" export of the monthly reports.',
                 "story_points": 3, "proyecto": "ABC", "fuente": "TAWOS"}
    assert not any(str(v) in json.dumps(r) for v in (77, 88, 99))


@pytest.mark.parametrize("cambio", [
    {"Type": "Bug"}, {"Story_Point": 4.0}, {"Story_Point": None},
    {"Story_Point_Changed_After_Estimation": 1}, {"Description_Text": "Mail me at someone@example.com please, thanks a lot"},
    {"Title": "x", "Description_Text": ""},
])
def test_candidata_descarta(cambio):
    assert descargar.candidata(_fila(**cambio)) is None


def test_muestra_estable_determinista_y_variada():
    cands = [{"id": f"TAWOS-{p}-{i}", "texto": "t", "story_points": sp, "proyecto": p, "fuente": "TAWOS"}
             for sp in descargar.ESCALA for p in ("GRANDE", "B", "C") for i in range(40 if p == "GRANDE" else 3)]
    m1 = descargar.muestra_estable(cands, por_puntaje=10, max_por_proyecto=4)
    m2 = descargar.muestra_estable(list(reversed(cands)), por_puntaje=10, max_por_proyecto=4)
    assert m1 == m2
    assert len(m1) == 60
    # 4 del proyecto grande + 3 + 3 de los pequeños, y se completa con el grande hasta 10.
    assert sum(1 for c in m1 if c["story_points"] == 1 and c["proyecto"] != "GRANDE") == 6


def test_referencias_tawos_versionadas():
    refs = _jsonl(REFERENCIAS)
    assert len(refs) == 150
    assert {r["story_points"] for r in refs} == set(descargar.ESCALA)
    assert all("@" not in r["texto"] and "://" not in r["texto"] for r in refs)   # sin correos ni URL
    assert all('""' not in r["texto"] for r in refs)
    assert len({r["proyecto"] for r in refs}) >= 10
    assert len(cargar_referencias(REFERENCIAS)) == 150      # el servidor de estimación las acepta


# ================================================================= construcción de casos

def _dalpiaz_temporal(tmp_path: Path) -> Path:
    carpeta = tmp_path / "dalpiaz"
    carpeta.mkdir()
    lineas = [f"As a user, I want feature {i}, so that I get value {i}." for i in range(1, 21)]
    (carpeta / "p1.txt").write_bytes("\n".join(lineas).encode("cp1252"))
    return carpeta


def _diseno(n: int = 10) -> dict:
    casos = []
    for i in range(1, n + 1):
        intencion = ("aceptar", "devolver", "dividir", "devolver", "aceptar")[i % 5]
        c = {"id": f"T-{i:02d}", "proyecto": "p1", "lineas": [i], "operacion": "original", "intencion_diseno": intencion}
        if intencion == "aceptar":
            c.update(operacion="con_criterios", criterios_aceptacion=["Shows X.", "Rejects Y."])
        if i % 2 == 0:
            c.update(es_dificil=True, motivo_dificultad="m")
        casos.append(c)
    return {"sistema": "todos", "proyectos": {"p1": "p1.txt"}, "casos": casos}


def test_construir_valido(tmp_path, monkeypatch):
    monkeypatch.setattr(construir_casos, "MIN_CASOS", 10)
    casos, contexto, resumen = construir_casos.construir(_diseno(), _dalpiaz_temporal(tmp_path))
    assert len(casos) == 10 and len(contexto) == 10
    assert all("intencion_diseno" not in c for c in casos)
    assert casos[0]["criterios_aceptacion"] == "" or casos[0]["criterios_aceptacion"].startswith("- ")
    assert {c["id"] for c in contexto}.isdisjoint({c["id"] for c in casos})
    usadas = {n for c in casos for n in c["fuente"]["lineas"]}
    assert all(c["fuente"]["lineas"][0] not in usadas for c in contexto)


@pytest.mark.parametrize("romper, mensaje", [
    (lambda d: d["casos"][1].update(lineas=[1]), "ya la usa otro caso"),
    (lambda d: d["casos"][4].update(criterios_aceptacion=[{"a": "b"}]), "comillas"),
    (lambda d: d["casos"][2].update(operacion="combinada"), "combinada"),
    (lambda d: d["casos"][3].update(es_dificil=True, motivo_dificultad=""), "motivo_dificultad"),
    (lambda d: d["casos"][0].update(lineas=[99]), "no existen"),
    (lambda d: [c.update(es_dificil=False) for c in d["casos"]], "difíciles"),
])
def test_construir_rechaza_disenos_invalidos(tmp_path, monkeypatch, romper, mensaje):
    monkeypatch.setattr(construir_casos, "MIN_CASOS", 10)
    d = _diseno()
    romper(d)
    with pytest.raises(construir_casos.DisenoInvalido, match=mensaje):
        construir_casos.construir(d, _dalpiaz_temporal(tmp_path))


def test_casos_versionados_cumplen_la_rubrica():
    casos = _jsonl(CASOS)
    assert len(casos) >= 40
    assert len({c["id"] for c in casos}) == len(casos)
    assert sum(c["es_dificil"] for c in casos) / len(casos) >= 0.30
    assert all(c["texto"].strip() and c["sistema"] == "todos" for c in casos)
    assert all("intencion_diseno" not in c for c in casos)
    assert all(c["motivo_dificultad"] for c in casos if c["es_dificil"])


def test_casos_y_contexto_cargan_en_el_backlog_sin_metadatos(tmp_path):
    backlog = BacklogLocal([CASOS, CONTEXTO], tmp_path)
    h = backlog.leer_historia("EV-04")
    assert not hasattr(h, "es_dificil") and "dificultad" not in repr(h)
    # Las contrapartes de duplicados y conflictos están en el contexto y se encuentran buscando.
    for caso, contraparte in (("EV-26", "CTX-CP-049"), ("EV-35", "CTX-FS-020"), ("EV-16", "CTX-PP-034")):
        texto = backlog.leer_historia(caso).texto
        assert contraparte in [r.historia.id for r in backlog.buscar_similares(texto, 3)]


# ================================================================= ataques

def test_ataques_cinco_tipos_o_mas_y_canario_solo_en_contexto(tmp_path):
    ataques = _jsonl(ATAQUES)
    assert len({a["tipo_ataque"] for a in ataques}) >= 5
    assert all(a["exito_si"] and a["proposito"] for a in ataques)
    assert not any("CANARIO" in a["texto"] for a in ataques)
    assert any("CANARIO-ATQ-7Q2X" in h["texto"] for h in _jsonl(BACKLOG_ATAQUES))
    backlog = BacklogLocal([ATAQUES, BACKLOG_ATAQUES], tmp_path)
    exfiltracion = next(a for a in ataques if a["tipo_ataque"] == "exfiltracion")
    similares = backlog.buscar_similares(backlog.leer_historia(exfiltracion["id"]).texto, 3)
    assert "CTX-ATQ-01" in [r.historia.id for r in similares]   # el canario está al alcance del agente


# ================================================================= etiquetado

def test_validar_reglas_de_forma():
    permitidos, tipos = {"QUS-001", "INV-005"}, ["funcional"]
    etiquetar.validar("devolver", ["INV-005"], "funcional", 3, permitidos, tipos)
    for args in (("aceptar", ["INV-005"], "funcional", None), ("devolver", [], "funcional", None),
                 ("devolver", ["BM-001"], "funcional", None), ("devolver", ["INV-005"], "funcional", 4),
                 ("aprobar", [], "funcional", None), ("devolver", ["INV-005", "INV-005"], "funcional", None)):
        with pytest.raises(etiquetar.EtiquetaInvalida):
            etiquetar.validar(*args, permitidos, tipos)


def test_orden_fijo_y_distinto_por_anotador():
    ids = [f"EV-{i:02d}" for i in range(1, 41)]
    assert etiquetar.orden_para("A", ids) == etiquetar.orden_para("A", list(reversed(ids)))
    assert etiquetar.orden_para("A", ids) != etiquetar.orden_para("B", ids)


def test_etiquetar_piloto_guarda_version_y_retoma(tmp_path):
    respuestas = iter(["b", "x", "d", "INV-005, 1", "", "estaba vago", "salir"])
    salida: list[str] = []
    (tmp_path / "anotador_B.csv").write_text("no se debe leer", encoding="utf-8")
    etiquetar.etiquetar("A", piloto=True, entrada=lambda _: next(respuestas), salida=salida.append,
                        casos_ruta=CASOS, contexto_ruta=CONTEXTO, carpeta=tmp_path)
    filas = list(csv.DictReader((tmp_path / "anotador_A.csv").open(encoding="utf-8")))
    assert len(filas) == 1
    catalogo = cargar_catalogo(RAIZ / "conocimiento" / "criterios.yaml")
    primero = etiquetar.orden_para("A", [c["id"] for c in _jsonl(CASOS)])[0]
    assert filas[0]["id"] == primero and filas[0]["decision"] == "devolver"
    assert filas[0]["defectos"] == f"INV-005;{catalogo.aplicables('todos')[0].id}"
    assert filas[0]["version_catalogo"] == catalogo.version and filas[0]["hash_catalogo"] == catalogo.hash_sha256
    assert any("CTX-" in s for s in salida)                      # la búsqueda mostró HU del contexto
    # Al retomar, el caso ya etiquetado no se vuelve a pedir.
    vistos: list[str] = []
    etiquetar.etiquetar("A", piloto=True, entrada=lambda _: "salir", salida=vistos.append,
                        casos_ruta=CASOS, contexto_ruta=CONTEXTO, carpeta=tmp_path)
    assert any("1 de 10 hechos" in s for s in vistos)


def test_etiquetar_rechaza_aceptar_con_defectos_y_vuelve_a_preguntar(tmp_path):
    respuestas = iter(["v", "QUS-002", "13", "", "salir"])
    etiquetar.etiquetar("A", piloto=True, entrada=lambda _: next(respuestas), salida=lambda _: None,
                        casos_ruta=CASOS, contexto_ruta=CONTEXTO, carpeta=tmp_path)
    fila = next(csv.DictReader((tmp_path / "anotador_A.csv").open(encoding="utf-8")))
    assert (fila["decision"], fila["defectos"], fila["estimacion"]) == ("dividir", "QUS-002", "13")


def test_traducciones_cubren_casos_y_contexto_y_conservan_criterios():
    traducciones = etiquetar.leer_traducciones()
    casos, contexto = _jsonl(CASOS), _jsonl(CONTEXTO)
    assert {c["id"] for c in casos} | {h["id"] for h in contexto} == set(traducciones)
    for c in casos:   # si el original tiene criterios, la traducción también; si no, tampoco
        assert bool(c["criterios_aceptacion"]) == bool(traducciones[c["id"]].get("criterios")), c["id"]
        assert c["criterios_aceptacion"].count("\n") == traducciones[c["id"]].get("criterios", "").count("\n")


def test_etiquetar_muestra_original_y_traduccion(tmp_path):
    salida: list[str] = []
    etiquetar.etiquetar("A", piloto=True, entrada=lambda _: "salir", salida=salida.append,
                        casos_ruta=CASOS, contexto_ruta=CONTEXTO, carpeta=tmp_path)
    primero = {c["id"]: c for c in _jsonl(CASOS)}[etiquetar.orden_para("A", [c["id"] for c in _jsonl(CASOS)])[0]]
    texto = "\n".join(salida)
    assert primero["texto"][:40] in texto.replace("\n", " ")
    assert "Traducción de apoyo" in texto
    assert texto.index(primero["texto"][:20]) < texto.index("Traducción de apoyo")   # el original va primero


def test_texto_en_la_estimacion_solo_repite_la_estimacion(tmp_path):
    respuestas = iter(["d", "INV-005", "es vaga", "4", "", "es vaga", "salir"])
    salida: list[str] = []
    etiquetar.etiquetar("A", piloto=True, entrada=lambda _: next(respuestas), salida=salida.append,
                        casos_ruta=CASOS, contexto_ruta=CONTEXTO, carpeta=tmp_path)
    fila = next(csv.DictReader((tmp_path / "anotador_A.csv").open(encoding="utf-8")))
    assert (fila["decision"], fila["defectos"], fila["estimacion"], fila["comentario"]) == \
        ("devolver", "INV-005", "", "es vaga")
    assert sum("Comentario" in s and "⚠" in s for s in salida) == 2


def test_anotador_invalido():
    with pytest.raises(etiquetar.EtiquetaInvalida):
        etiquetar.ruta_anotador("../B")


# ================================================================= acuerdo

def test_kappa_valores_conocidos():
    assert acuerdo.cohen_kappa(["a", "b", "a"], ["a", "b", "a"]) == 1.0
    # Ejemplo clásico: 20 casos, 70 % de acuerdo observado, 50 % esperado -> 0,4.
    a = ["si"] * 10 + ["no"] * 10
    b = ["si"] * 7 + ["no"] * 3 + ["si"] * 3 + ["no"] * 7
    assert acuerdo.cohen_kappa(a, b) == 0.4
    assert acuerdo.cohen_kappa([], []) is None
    assert acuerdo.interpretar(0.4) == "regular" and acuerdo.interpretar(0.85) == "casi perfecto"


def _etiquetas(ruta: Path, filas: list[tuple[str, str, str]]):
    with ruta.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=etiquetar.COLUMNAS)
        w.writeheader()
        for i, d, defs in filas:
            w.writerow({"id": i, "decision": d, "defectos": defs, "tipo": "funcional", "estimacion": "",
                        "anotador": ruta.stem[-1], "version_catalogo": "0.2.0"})


def test_acuerdo_un_anotador_y_dos_con_consenso(tmp_path):
    casos = tmp_path / "casos.jsonl"
    casos.write_text("\n".join(json.dumps({"id": i}) for i in ("C1", "C2", "C3")), encoding="utf-8")
    _etiquetas(tmp_path / "anotador_A.csv", [("C1", "aceptar", ""), ("C2", "devolver", "INV-005"),
                                             ("C3", "dividir", "QUS-002")])
    args = ["--a", str(tmp_path / "anotador_A.csv"), "--b", str(tmp_path / "anotador_B.csv"),
            "--casos", str(casos), "--salida", str(tmp_path)]
    assert acuerdo.main(args) == 0
    finales = list(csv.DictReader((tmp_path / "etiquetas_finales.csv").open(encoding="utf-8")))
    assert [f["origen"] for f in finales] == ["anotador_unico"] * 3
    assert "Un solo anotador" in (tmp_path / "acuerdo.md").read_text(encoding="utf-8")

    _etiquetas(tmp_path / "anotador_B.csv", [("C1", "aceptar", ""), ("C2", "devolver", "INV-005;DOR-002"),
                                             ("C3", "devolver", "QUS-006")])
    assert acuerdo.main(args) == 1                                  # dos desacuerdos sin resolver
    assert len(list(csv.DictReader((tmp_path / "desacuerdos.csv").open(encoding="utf-8")))) == 2
    (tmp_path / "consenso.csv").write_text("id,decision,defectos,estimacion\nC2,devolver,INV-005,\nC3,dividir,QUS-002,8\n",
                                           encoding="utf-8")
    assert acuerdo.main(args) == 0
    informe = (tmp_path / "acuerdo.md").read_text(encoding="utf-8")
    assert "Kappa de Cohen de la decisión" in informe


# ================================================================= conjunto bancario complementario (D-034)

CASOS_BANCA = RAIZ / "datos" / "evaluacion" / "casos_banca.jsonl"


def test_conjunto_bancario_versionado(tmp_path):
    casos = _jsonl(CASOS_BANCA)
    assert len(casos) >= 15 and len({c["id"] for c in casos}) == len(casos)
    assert all(c["id"].startswith("BAN-") for c in casos)            # no se confunde con los criterios BM-0xx
    assert sum(c["es_dificil"] for c in casos) / len(casos) >= 0.30
    assert {c["sistema"] for c in casos} <= {"banca_movil", "core"}
    assert all("intencion_diseno" not in c for c in casos)
    # Sin las instrucciones de ataque de las HU 5, 9 y 10 de Azure: esas van al análisis de seguridad.
    assert not any(p in c["texto"] for c in casos for p in ("ASISTENTE", "asistente de IA", "Instrucción del sistema"))
    backlog = BacklogLocal([CASOS_BANCA], tmp_path)
    similares = [r.historia.id for r in backlog.buscar_similares(backlog.leer_historia("BAN-01").texto, 3)]
    assert "BAN-03" in similares                                     # el duplicado está en el mismo backlog


def test_construir_banca_rechaza_disenos_invalidos():
    base = {"casos": [{"id": f"B-{i}", "texto": "Como cliente, quiero algo, para algo.",
                       "intencion_diseno": ("aceptar", "devolver", "dividir")[i % 3],
                       "es_dificil": i % 2 == 0, "motivo_dificultad": "m"} for i in range(15)]}
    casos, resumen = construir_casos.construir_banca(base)
    assert resumen["casos"] == 15 and casos[0]["sistema"] == "banca_movil"
    base["casos"][1]["texto"] = ""
    with pytest.raises(construir_casos.DisenoInvalido, match="falta el texto"):
        construir_casos.construir_banca(base)


def test_etiquetar_conjunto_banca_usa_criterios_bm_y_su_propio_archivo(tmp_path):
    respuestas = iter(["d", "BM-003", "", "", "salir"])
    salida: list[str] = []
    etiquetar.etiquetar("A", piloto=True, entrada=lambda _: next(respuestas), salida=salida.append,
                        carpeta=tmp_path, conjunto="banca")
    primero = etiquetar.orden_para("A", [c["id"] for c in _jsonl(CASOS_BANCA)])[0]
    sistema = next(c["sistema"] for c in _jsonl(CASOS_BANCA) if c["id"] == primero)
    archivo = tmp_path / "anotador_A_banca.csv"
    if sistema == "banca_movil":
        fila = next(csv.DictReader(archivo.open(encoding="utf-8")))
        assert (fila["id"], fila["defectos"]) == (primero, "BM-003")
    else:  # un caso de core no admite criterios de Banca Móvil
        assert any("No aplican" in s for s in salida)
    assert not (tmp_path / "anotador_A.csv").exists()


def test_acuerdo_conjunto_banca_escribe_archivos_con_sufijo(tmp_path):
    _etiquetas(tmp_path / "anotador_A_banca.csv", [(c["id"], "devolver", "INV-005") for c in _jsonl(CASOS_BANCA)])
    assert acuerdo.main(["--conjunto", "banca", "--a", str(tmp_path / "anotador_A_banca.csv"),
                         "--salida", str(tmp_path)]) == 0
    assert (tmp_path / "etiquetas_finales_banca.csv").exists() and (tmp_path / "acuerdo_banca.md").exists()
