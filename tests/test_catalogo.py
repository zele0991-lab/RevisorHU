"""
Pruebas del catálogo de criterios (sección 4.1 del prompt).

1. El catálogo real es válido.
2. Cada error de validación se detecta con un catálogo de prueba roto, y el mensaje dice qué
   criterio y qué campo fallan.
3. Criterio de "hecho" de la F2: un criterio nuevo agregado SOLO en el YAML aparece en
   listar_criterios y registrar_revision lo acepta, sin cambiar código.
4. Ningún id de criterio está escrito fuera del YAML (código, configuración, Skill, guías).
"""

import copy
import hashlib
import re

import pytest
import yaml

from conftest import BACKLOG_EJEMPLO, RAIZ, llamar
from revisor.conocimiento.catalogo import CatalogoInvalido, cargar_catalogo

RUTA_REAL = RAIZ / "conocimiento" / "criterios.yaml"


@pytest.fixture(scope="module")
def real():
    return cargar_catalogo(RUTA_REAL)


# ===================================================================== 1. catálogo real
def test_el_catalogo_real_es_valido(real):
    assert re.fullmatch(r"\d+\.\d+\.\d+", real.version)
    assert real.ids_activos(), "debe haber criterios activos"


def test_el_catalogo_real_cubre_todas_sus_categorias(real):
    for categoria in real.categorias:
        assert any(c.categoria == categoria and c.activo for c in real.criterios), categoria


def test_el_catalogo_real_tiene_el_paquete_de_banca_movil(real):
    generales = {c.id for c in real.aplicables("todos")}
    banca = {c.id for c in real.aplicables("banca_movil")}
    core = {c.id for c in real.aplicables("core")}
    assert generales < banca, "banca_movil = generales + propios"
    assert core == generales, "core todavía no tiene criterios propios"


def test_los_tipos_de_hu_salen_del_catalogo(real):
    assert real.tipos_hu() == ["funcional"]


def test_el_formato_de_criterios_sale_del_catalogo(real):
    """D-027: hoy reglas o lista de verificación; pasar a Gherkin es editar el YAML."""
    assert real.formato_criterios_aceptacion() == "lista"


def test_hash_sha256_de_los_bytes_del_archivo(real, tmp_path):
    assert real.hash_sha256 == hashlib.sha256(RUTA_REAL.read_bytes()).hexdigest()
    copia = tmp_path / "c.yaml"
    copia.write_bytes(RUTA_REAL.read_bytes() + b"\n# cambio\n")
    assert cargar_catalogo(copia).hash_sha256 != real.hash_sha256


# ===================================================================== 2. catálogos rotos
def _criterio(id, **cambios):
    base = {
        "id": id, "categoria": "dor", "nombre": "Nombre", "descripcion": "Descripción",
        "como_verificar": "Cómo verificar", "ejemplo_cumple": "Sí", "ejemplo_no_cumple": "No",
        "severidad": "mayor", "aplica_a": ["todos"], "estado": "activo",
    }
    return {**base, **cambios}


BASE = {
    "version": "1.0.0", "fecha": "2026-11-09", "categorias": ["dor", "banca_movil"],
    "sistemas": ["banca_movil", "core"], "tipos_hu": ["funcional"], "formato_criterios_aceptacion": "lista",
    "criterios": [_criterio("DOR-001"), _criterio("BM-001", categoria="banca_movil", aplica_a=["banca_movil"])],
}


def _escribir(tmp_path, datos):
    ruta = tmp_path / "criterios.yaml"
    ruta.write_text(yaml.safe_dump(datos, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return ruta


def test_el_catalogo_base_de_las_pruebas_es_valido(tmp_path):
    assert cargar_catalogo(_escribir(tmp_path, BASE)).version == "1.0.0"


def _con(cambio):
    def aplicar():
        d = copy.deepcopy(BASE)
        cambio(d)
        return d
    return aplicar


def _c(d, i=0):
    return d["criterios"][i]


ROTOS = {
    "falta un campo": (_con(lambda d: _c(d).pop("severidad")), "criterio DOR-001, campo 'severidad': falta"),
    "campo vacío": (_con(lambda d: _c(d).update(nombre="  ")), "criterio DOR-001, campo 'nombre': debe ser un texto no vacío"),
    "campo desconocido": (_con(lambda d: _c(d).update(severida="mayor")), "criterio DOR-001: campos desconocidos: severida"),
    "id duplicado": (_con(lambda d: d["criterios"].append(_criterio("DOR-001"))), "criterio DOR-001, campo 'id': id duplicado"),
    "formato de id": (_con(lambda d: _c(d).update(id="dor-1")), "criterio dor-1, campo 'id': 'dor-1' no tiene el formato correcto"),
    "sin id": (_con(lambda d: _c(d).pop("id")), "criterio #1 (sin id), campo 'id': falta"),
    "categoría inválida": (_con(lambda d: _c(d).update(categoria="seguridad")), "criterio DOR-001, campo 'categoria': 'seguridad' no está en 'categorias'"),
    "severidad inválida": (_con(lambda d: _c(d).update(severidad="alta")), "criterio DOR-001, campo 'severidad': 'alta' no es válida"),
    "estado inválido": (_con(lambda d: _c(d).update(estado="retirado")), "criterio DOR-001, campo 'estado': 'retirado' no es válido"),
    "obsoleto sin reemplazo": (_con(lambda d: _c(d).update(estado="obsoleto")), "criterio DOR-001, campo 'reemplazado_por': falta"),
    "reemplazo inexistente": (
        _con(lambda d: _c(d).update(estado="obsoleto", reemplazado_por="DOR-999")),
        "criterio DOR-001, campo 'reemplazado_por': 'DOR-999' no existe"),
    "activo con reemplazo": (
        _con(lambda d: _c(d).update(reemplazado_por="BM-001")), "campo 'reemplazado_por': solo se usa en criterios obsoletos"),
    "ciclo de reemplazos": (
        _con(lambda d: (_c(d).update(estado="obsoleto", reemplazado_por="DOR-002"),
                        d["criterios"].append(_criterio("DOR-002", estado="obsoleto", reemplazado_por="DOR-001")))),
        "la cadena de reemplazos no termina en un criterio activo"),
    "sin criterios activos": (
        _con(lambda d: d.update(criterios=[_criterio("DOR-001", estado="obsoleto", reemplazado_por="DOR-002"),
                                           _criterio("DOR-002", estado="obsoleto", reemplazado_por="DOR-001")])),
        "el catálogo no tiene ningún criterio activo"),
    "sistema desconocido en aplica_a": (
        _con(lambda d: _c(d, 1).update(aplica_a=["banca_movl"])), "criterio BM-001, campo 'aplica_a': banca_movl no está en 'sistemas'"),
    "todos combinado": (
        _con(lambda d: _c(d).update(aplica_a=["todos", "core"])), "campo 'aplica_a': 'todos' va solo"),
    "aplica_a vacío": (_con(lambda d: _c(d).update(aplica_a=[])), "campo 'aplica_a': debe ser una lista no vacía"),
    "criterio que no es objeto": (_con(lambda d: d["criterios"].append("texto suelto")), "criterio #3: debe ser un objeto"),
    "sin versión": (_con(lambda d: d.pop("version")), "cabecera: falta el campo obligatorio 'version'"),
    "versión sin comillas (float)": (_con(lambda d: d.update(version=1.0)), "campo 'version': '1.0' no es válida"),
    "fecha inválida": (_con(lambda d: d.update(fecha="9 de noviembre")), "campo 'fecha': '9 de noviembre' no es una fecha válida"),
    "todos como sistema": (_con(lambda d: d["sistemas"].append("todos")), "'todos' es reservado"),
    "sin tipos de HU": (_con(lambda d: d.update(tipos_hu=[])), "campo 'tipos_hu': debe ser una lista no vacía"),
    "lista de criterios vacía": (_con(lambda d: d.update(criterios=[])), "campo 'criterios': debe ser una lista no vacía"),
    "formato de criterios inválido": (
        _con(lambda d: d.update(formato_criterios_aceptacion="bdd")),
        "campo 'formato_criterios_aceptacion': 'bdd' no es válido"),
    "sin formato de criterios": (
        _con(lambda d: d.pop("formato_criterios_aceptacion")),
        "cabecera: falta el campo obligatorio 'formato_criterios_aceptacion'"),
    "campo de cabecera desconocido": (_con(lambda d: d.update(autor="x")), "cabecera: campos desconocidos: autor"),
}


@pytest.mark.parametrize("construir, esperado", ROTOS.values(), ids=ROTOS.keys())
def test_detecta_cada_error_con_mensaje_claro(tmp_path, construir, esperado):
    with pytest.raises(CatalogoInvalido) as e:
        cargar_catalogo(_escribir(tmp_path, construir()))
    assert any(esperado in err for err in e.value.errores), e.value.errores
    assert "no arranca" in str(e.value) and "criterios.yaml" in str(e.value)


def test_reporta_todos_los_errores_juntos(tmp_path):
    d = copy.deepcopy(BASE)
    _c(d).update(severidad="alta")
    _c(d, 1).update(estado="retirado")
    with pytest.raises(CatalogoInvalido) as e:
        cargar_catalogo(_escribir(tmp_path, d))
    assert len(e.value.errores) == 2


def test_yaml_con_error_de_sintaxis_y_archivo_inexistente(tmp_path):
    malo = tmp_path / "malo.yaml"
    malo.write_text("version: '1.0.0'\ncriterios: [\n", encoding="utf-8")
    with pytest.raises(CatalogoInvalido, match="no es YAML válido"):
        cargar_catalogo(malo)
    with pytest.raises(CatalogoInvalido, match="no existe el archivo"):
        cargar_catalogo(tmp_path / "no_existe.yaml")


def test_un_obsoleto_se_resuelve_a_su_vigente(tmp_path):
    d = copy.deepcopy(BASE)
    d["criterios"] += [_criterio("DOR-002", estado="obsoleto", reemplazado_por="DOR-003"),
                       _criterio("DOR-003", estado="obsoleto", reemplazado_por="DOR-001")]
    cat = cargar_catalogo(_escribir(tmp_path, d))
    assert cat.vigente("DOR-002").id == "DOR-001"
    assert "DOR-002" not in cat.ids_defectos_aplicables("core"), "un obsoleto nunca es un defecto válido"
    assert cat.obtener("DOR-002") is not None, "los ids antiguos siguen resolviéndose"


# ===================================================================== 3. criterio de "hecho" de la F2
NUEVO = """
  - id: BM-099
    categoria: banca_movil
    nombre: Criterio agregado solo en el YAML
    descripcion: Prueba de que las reglas son datos.
    como_verificar: Ver que aparezca sin tocar código.
    ejemplo_cumple: Aparece.
    ejemplo_no_cumple: No aparece.
    severidad: menor
    aplica_a: [banca_movil]
    estado: activo
"""


def test_criterio_nuevo_solo_en_el_yaml_funciona_sin_cambiar_codigo(tmp_path):
    """Se usa la misma ruta de arranque que en producción (`construir` con --catalogo)."""
    from revisor.servidores import servidor_backlog, servidor_conocimiento

    catalogo = tmp_path / "criterios.yaml"
    catalogo.write_text(RUTA_REAL.read_text(encoding="utf-8") + NUEVO, encoding="utf-8")

    conocimiento = servidor_conocimiento.construir(
        ["--catalogo", str(catalogo), "--guias", str(RAIZ / "conocimiento")])
    listado = llamar(conocimiento, "listar_criterios", {"sistema": "banca_movil"}).json
    assert "BM-099" in [c["id"] for c in listado["criterios"]]
    assert llamar(conocimiento, "obtener_criterio", {"id": "BM-099"}).json["criterio"]["severidad"] == "menor"

    backlog = servidor_backlog.construir(
        ["--catalogo", str(catalogo), "--historias", str(BACKLOG_EJEMPLO), "--estado", str(tmp_path / "estado")])
    r = llamar(backlog, "registrar_revision", {
        "id": "HU-002", "decision": "devolver", "tipo": "funcional", "estimacion": 3,
        "defectos": ["BM-099"], "recomendaciones": [{"defecto": "BM-099", "texto": "Corregir."}],
        "historia_refinada": "", "criterios_aceptacion": [],
    })
    assert not r.es_error, r.texto


def test_sin_el_criterio_nuevo_el_mismo_defecto_se_rechaza(tmp_path):
    """Contraprueba: lo que acepta el servidor depende del YAML, no de otra cosa."""
    from revisor.servidores import servidor_backlog

    backlog = servidor_backlog.construir(
        ["--catalogo", str(RUTA_REAL), "--historias", str(BACKLOG_EJEMPLO), "--estado", str(tmp_path / "e")])
    r = llamar(backlog, "registrar_revision", {
        "id": "HU-002", "decision": "devolver", "tipo": "funcional", "estimacion": 3,
        "defectos": ["BM-099"], "recomendaciones": [{"defecto": "BM-099", "texto": "Corregir."}],
        "historia_refinada": "", "criterios_aceptacion": [],
    })
    assert r.es_error and "'BM-099' no son criterios activos" in r.texto


# ===================================================================== 4. ningún id fuera del YAML
def _archivos_que_no_deben_tener_ids():
    patrones = ["src/**/*.py", "config/**/*", "skills/**/*", "conocimiento/*.md"]
    for patron in patrones:
        for ruta in RAIZ.glob(patron):
            if ruta.is_file():
                yield ruta


def test_ningun_id_de_criterio_esta_escrito_fuera_del_catalogo(real):
    """Si un id aparece en el código, la Skill, la política o las guías, cambiar el YAML ya no bastaría."""
    ids = [c.id for c in real.criterios]
    patron = re.compile(r"\b(" + "|".join(map(re.escape, ids)) + r")\b")
    encontrados = {}
    for ruta in _archivos_que_no_deben_tener_ids():
        hallados = set(patron.findall(ruta.read_text(encoding="utf-8", errors="ignore")))
        if hallados:
            encontrados[str(ruta.relative_to(RAIZ))] = sorted(hallados)
    assert not encontrados, f"ids de criterios fuera de criterios.yaml: {encontrados}"
