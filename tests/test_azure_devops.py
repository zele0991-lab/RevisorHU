"""
Pruebas parametrizadas para `_sanear_html`.

Por qué este archivo solo prueba `_sanear_html`:
    La tarea 1.2 cubre únicamente esa función. Las pruebas de las demás capas
    (ClienteHTTPFalso, BacklogAzureDevOps, etc.) se añaden en tareas posteriores.

Convenciones:
    - Ninguna prueba abre un socket. El fixture `bloquear_urlopen` captura cualquier
      llamada accidental a `urllib.request.urlopen` y lanza `AssertionError`.
    - Código y docstrings en español.
    - Solo se usan biblioteca estándar + pytest.
"""

import json
import urllib.request
from pathlib import Path

import pytest

from revisor.backlog.azure_devops import BacklogAzureDevOps, _sanear_html
from revisor.backlog.puerto import (
    ErrorBacklog,
    HistoriaNoEncontrada,
    OperacionProhibida,
    PuertoBacklog,
    Recomendacion,
    Revision,
)


# ============================================================ fixtures globales

@pytest.fixture(autouse=True)
def bloquear_urlopen(monkeypatch):
    """
    Bloquea `urllib.request.urlopen` para todas las pruebas de este módulo.

    Por qué autouse:
        Las pruebas de este archivo solo ejercitan `_sanear_html`, que no hace
        ninguna llamada HTTP. Cualquier llamada a `urlopen` indicaría un import
        lateral u otra dependencia inesperada que el conjunto de pruebas no debe
        tolerar.
    """

    def _no_permitido(*args, **kwargs):
        raise AssertionError(
            "Las pruebas no deben llamar a urllib.request.urlopen. "
            "Usa ClienteHTTPFalso en su lugar."
        )

    monkeypatch.setattr(urllib.request, "urlopen", _no_permitido)


# ================================================================ Propiedad 1
# Preservación del texto visible y eliminación del texto oculto.
# Validates: Requisitos 3.1, 3.2, 3.3, 3.4, 3.5, 3.6

_CASOS_PROP1 = [
    pytest.param(
        "<p>visible</p><span style=\"display:none\">oculto</span>",
        ["visible"],
        ["oculto"],
        id="display_none_elimina_oculto",
    ),
    pytest.param(
        "<!-- instrucción -->texto visible",
        ["texto visible"],
        ["instrucción"],
        id="comentario_html_eliminado",
    ),
    pytest.param(
        "<script>alert(1)</script>texto visible",
        ["texto visible"],
        ["alert"],
        id="script_eliminado",
    ),
    pytest.param(
        "<p>título</p><strong>descripción</strong><em>nota</em>",
        ["título", "descripción", "nota"],
        [],
        id="contenido_solo_visible",
    ),
    pytest.param(
        "<span style=\"opacity:0.5\">visible</span>",
        ["visible"],
        [],
        id="opacity_05_no_oculto",
    ),
    pytest.param(
        "<span style=\"font-size:0.8em\">visible</span>",
        ["visible"],
        [],
        id="font_size_08em_no_oculto",
    ),
    pytest.param(
        "</span></span><span style=\"display:none\">instrucción</span>visible",
        ["visible"],
        ["instrucción"],
        id="cierres_huerfanos_antes_de_oculto",
    ),
    pytest.param(
        "<span style=\"display:none\"><b>x</b> secreto</span>visible",
        ["visible"],
        ["secreto"],
        id="oculto_con_etiqueta_anidada",
    ),
    pytest.param(
        "<span style=\"display:none\">instrucción sin cerrar",
        [],
        ["instrucción"],
        id="oculto_sin_cerrar_descartado",
    ),
]


@pytest.mark.parametrize(
    "html_entrada, presentes, ausentes",
    _CASOS_PROP1,
)
def test_propiedad1_visibilidad(html_entrada, presentes, ausentes):
    """
    Propiedad 1: el texto visible se conserva y el texto oculto se elimina.

    Validates: Requisitos 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
    """
    salida = _sanear_html(html_entrada)
    for fragmento in presentes:
        assert fragmento in salida, (
            f"Se esperaba '{fragmento}' en la salida, pero no está.\n"
            f"Entrada: {html_entrada!r}\nSalida:  {salida!r}"
        )
    for fragmento in ausentes:
        assert fragmento not in salida, (
            f"'{fragmento}' debería estar ausente, pero aparece en la salida.\n"
            f"Entrada: {html_entrada!r}\nSalida:  {salida!r}"
        )


# ================================================================ Propiedad 2
# Ausencia de etiquetas HTML en la salida.
# Validates: Requisitos 3.1, 3.2, 3.3, 3.4, 3.5, 3.7

_CASOS_PROP2 = [
    pytest.param(
        "<p>título</p><strong>negrita</strong><ul><li>ítem</li></ul>",
        id="etiquetas_visibles_no_aparecen",
    ),
    pytest.param(
        "<span style=\"display:none\">oculto</span>visible",
        id="etiquetas_ocultas_no_aparecen",
    ),
    pytest.param(
        "",
        id="html_vacio",
    ),
]


@pytest.mark.parametrize("html_entrada", _CASOS_PROP2)
def test_propiedad2_sin_etiquetas_html(html_entrada):
    """
    Propiedad 2: la salida no contiene etiquetas HTML ni referencias de carácter.

    Validates: Requisitos 3.1, 3.2, 3.3, 3.4, 3.5, 3.7
    """
    import re

    salida = _sanear_html(html_entrada)

    if html_entrada == "":
        assert salida == "", (
            f"HTML vacío debe producir cadena vacía, pero se obtuvo: {salida!r}"
        )
        return

    # La salida no debe contener "<" seguido de un nombre de etiqueta.
    patron_etiqueta = re.compile(r"<[a-zA-Z/]")
    assert not patron_etiqueta.search(salida), (
        f"La salida contiene etiquetas HTML.\nEntrada: {html_entrada!r}\nSalida:  {salida!r}"
    )

    # En el caso con span oculto tampoco deben quedar restos de la etiqueta.
    if "span" in html_entrada:
        assert "<span" not in salida and "</span" not in salida, (
            f"La salida contiene restos de <span>.\nSalida: {salida!r}"
        )


# ================================================================ Propiedad 3
# Caracteres escapados aparecen como literales.
# Validates: Requisito 3.7

_CASOS_PROP3 = [
    pytest.param(
        "<p>Términos &amp; condiciones</p>",
        "Términos & condiciones",
        id="amp_a_literal",
    ),
    pytest.param(
        "<p>monto &lt; 100</p>",
        "monto < 100",
        id="lt_a_literal",
    ),
    pytest.param(
        "<p>precio &gt; 0</p>",
        "precio > 0",
        id="gt_a_literal",
    ),
    pytest.param(
        "texto con & literal",
        "texto con & literal",
        id="ampersand_literal_sin_cambio",
    ),
]


@pytest.mark.parametrize("html_entrada, texto_esperado", _CASOS_PROP3)
def test_propiedad3_entidades_a_literales(html_entrada, texto_esperado):
    """
    Propiedad 3: las referencias de carácter HTML se convierten a sus valores literales.

    Validates: Requisito 3.7
    """
    salida = _sanear_html(html_entrada)
    assert texto_esperado in salida, (
        f"Se esperaba '{texto_esperado}' en la salida.\n"
        f"Entrada: {html_entrada!r}\nSalida:  {salida!r}"
    )


# ============================================================ Variantes Req. 13.4
# Cada variante de ocultamiento descrita en D-030 y en el Requisito 13.4.
# Validates: Requisitos 3.3, 3.4, 3.5, 13.4

def _caso_estilo(variante_id: str, estilo: str) -> pytest.param:
    """Genera un caso parametrizado para una variante de estilo de ocultamiento."""
    html_entrada = f'<span style="{estilo}">secreto</span>visible'
    return pytest.param(html_entrada, id=variante_id)


def _caso_atributo(variante_id: str, atributo: str) -> pytest.param:
    """Genera un caso parametrizado para un atributo booleano de ocultamiento."""
    html_entrada = f"<span {atributo}>secreto</span>visible"
    return pytest.param(html_entrada, id=variante_id)


_CASOS_REQ13_4 = [
    _caso_estilo("display_none_min",         "display:none"),
    _caso_estilo("display_none_may",         "DISPLAY:NONE"),
    _caso_estilo("display_none_espacio",     "display: none"),
    _caso_estilo("display_none_punto_coma",  "display:none;"),
    _caso_estilo("visibility_hidden",        "visibility:hidden"),
    _caso_estilo("opacity_cero",             "opacity:0"),
    _caso_estilo("font_size_cero",           "font-size:0"),
    _caso_estilo("font_size_cero_px",        "font-size:0px"),
    _caso_estilo("font_size_cero_em",        "font-size:0em"),
    _caso_estilo("font_size_cero_pt",        "font-size:0pt"),
    _caso_atributo("atributo_hidden",        "hidden"),
    _caso_atributo("aria_hidden_true",       'aria-hidden="true"'),
]


@pytest.mark.parametrize("html_entrada", _CASOS_REQ13_4)
def test_req13_4_variantes_ocultamiento(html_entrada):
    """
    Variantes del Requisito 13.4: todas las formas de ocultar un elemento deben
    hacer que su contenido desaparezca de la salida, mientras que el texto visible
    adyacente se conserva.

    Validates: Requisitos 3.3, 3.4, 3.5, 13.4
    """
    salida = _sanear_html(html_entrada)
    assert "secreto" not in salida, (
        f"'secreto' debería estar ausente, pero aparece en la salida.\n"
        f"Entrada: {html_entrada!r}\nSalida:  {salida!r}"
    )
    assert "visible" in salida, (
        f"'visible' debería estar presente, pero falta en la salida.\n"
        f"Entrada: {html_entrada!r}\nSalida:  {salida!r}"
    )


# ============================================================ Saneamiento endurecido
# Agregadas por Claude Code: cierres que no coinciden dentro de una región oculta no deben
# revelar texto (con un contador simple, `</p>` o `</br>` bajaban la profundidad a 0).

@pytest.mark.parametrize("html_entrada", [
    pytest.param("<span hidden></p>secreto</span>visible", id="cierre_p_sin_abrir_dentro_de_oculto"),
    pytest.param("<div style=\"display:none\"></br>secreto</div>visible", id="cierre_br_dentro_de_oculto"),
    pytest.param("<div hidden><b>uno</i>secreto</b> secreto</div>visible", id="cierres_cruzados"),
    pytest.param("<span style=\"display:none\"><br/>secreto</span>visible", id="br_autocerrado_dentro"),
    pytest.param("<template>secreto</template>visible", id="template"),
    pytest.param("<noscript>secreto</noscript>visible", id="noscript"),
    pytest.param("<span aria-hidden=\"TRUE\">secreto</span>visible", id="aria_hidden_mayusculas"),
])
def test_cierres_que_no_coinciden_no_revelan_texto(html_entrada):
    salida = _sanear_html(html_entrada)
    assert "secreto" not in salida
    assert "visible" in salida


def test_doble_escape_no_se_convierte_en_etiqueta():
    """Un solo desescapado: `&amp;lt;script&amp;gt;` queda como texto `&lt;script&gt;`."""
    salida = _sanear_html("<p>&amp;lt;script&amp;gt;</p>")
    assert "<script>" not in salida
    assert "&lt;script&gt;" in salida


def test_bloques_y_listas_quedan_en_lineas_separadas():
    salida = _sanear_html("<p>Como cliente</p><ul><li>uno</li><li>dos&nbsp;tres</li></ul>")
    assert salida == "Como cliente\n- uno\n- dos tres"


# ============================================================ ClienteHTTPFalso


class ClienteHTTPFalso:
    """
    Devuelve respuestas pregrabadas en orden y registra todas las llamadas.

    Cada respuesta es `(código, cuerpo)`, `(código, cuerpo, cabeceras)` o una excepción,
    que se lanza (para simular un timeout).
    """

    def __init__(self, respuestas: list):
        self._respuestas = list(respuestas)
        self.llamadas: list[dict] = []   # {"metodo", "url", "cuerpo", "cabeceras"}

    def solicitar(self, metodo, url, cuerpo=None, cabeceras=None):
        if not self._respuestas:
            raise AssertionError("ClienteHTTPFalso: más llamadas de las respuestas pregrabadas")
        self.llamadas.append({"metodo": metodo, "url": url,
                              "cuerpo": cuerpo, "cabeceras": cabeceras})
        respuesta = self._respuestas.pop(0)
        if isinstance(respuesta, BaseException):
            raise respuesta
        return respuesta

    def cuerpo_json(self, i: int):
        return json.loads(self.llamadas[i]["cuerpo"].decode("utf-8"))


# ============================================================ adaptador: utilidades

RAIZ = Path(__file__).resolve().parent.parent
CONFIG = json.loads((RAIZ / "config" / "azure_devops.json").read_text(encoding="utf-8"))
FIXTURE_HU10 = RAIZ / "tests" / "datos" / "azure" / "wi_10.json"
PAT_FALSO = "mi-pat-secreto"


def _ok(datos, estado: int = 200, cabeceras: dict | None = None):
    cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
    return (estado, cuerpo, cabeceras) if cabeceras is not None else (estado, cuerpo)


def _wi(id: int, *, titulo="Título", descripcion="<p>Como cliente, quiero algo, para algo.</p>",
        area="RevisorHU-Pruebas\\BancaMovil", tipo="User Story", puntos=None, criterios="", etiquetas=None,
        autores=True):
    campos = {"System.Title": titulo, "System.Description": descripcion, "System.AreaPath": area,
              "System.WorkItemType": tipo}
    if puntos is not None:
        campos["Microsoft.VSTS.Scheduling.StoryPoints"] = puntos
    if criterios:
        campos["Microsoft.VSTS.Common.AcceptanceCriteria"] = criterios
    if etiquetas is not None:
        campos["System.Tags"] = etiquetas
    if autores:  # por si la API los devolviera aunque no se pidan
        campos["System.CreatedBy"] = {"displayName": "Alice Prueba", "uniqueName": "alice@ejemplo.com"}
        campos["System.ChangedBy"] = "Bob Prueba <bob@ejemplo.com>"
    return {"id": id, "fields": campos}


def _backlog(respuestas, marca="run-123", mapeo=None):
    cliente = ClienteHTTPFalso(respuestas)
    esperas: list[float] = []
    b = BacklogAzureDevOps(
        org_url="https://dev.azure.com/org-prueba", project="RevisorHU-Pruebas",
        tipo_work_item=CONFIG["tipo_work_item"],
        mapeo_area_sistema=mapeo if mapeo is not None else CONFIG["mapeo_area_sistema"],
        sistema_por_defecto=CONFIG["sistema_por_defecto"], etiquetas=CONFIG["etiquetas"],
        poller=CONFIG["poller"], marca=marca, cliente_http=cliente, dormir=esperas.append,
    )
    return b, cliente, esperas


def _revision(decision="devolver", **extra):
    datos = dict(id_historia="10", decision=decision, tipo="funcional", estimacion=3,
                 defectos=["QUS-006"], recomendaciones=[Recomendacion("QUS-006", "Indica el tiempo <objetivo> & medible.")],
                 historia_refinada="", criterios_aceptacion=["El PDF incluye los movimientos."])
    datos.update(extra)
    return Revision(**datos)


# ============================================================ construcción

@pytest.fixture
def entorno_azure(monkeypatch):
    monkeypatch.setenv("AZDO_ORG_URL", "https://dev.azure.com/org-prueba")
    monkeypatch.setenv("AZDO_PROJECT", "RevisorHU-Pruebas")
    monkeypatch.setenv("AZDO_PAT", PAT_FALSO)


def test_construccion_valida(entorno_azure):
    b = BacklogAzureDevOps.desde_configuracion(RAIZ / "config" / "azure_devops.json", "m")
    assert isinstance(b, PuertoBacklog)
    assert PAT_FALSO not in repr(b) and PAT_FALSO not in repr(b._cliente_http)


@pytest.mark.parametrize("variable", ["AZDO_ORG_URL", "AZDO_PROJECT", "AZDO_PAT"])
@pytest.mark.parametrize("valor", [None, "   "])
def test_variable_ausente_o_vacia(entorno_azure, monkeypatch, variable, valor):
    if valor is None:
        monkeypatch.delenv(variable)
    else:
        monkeypatch.setenv(variable, valor)
    with pytest.raises(ErrorBacklog) as e:
        BacklogAzureDevOps.desde_configuracion(RAIZ / "config" / "azure_devops.json", None)
    assert variable in str(e.value)
    assert PAT_FALSO not in str(e.value)


def test_config_inexistente_o_invalida(entorno_azure, tmp_path):
    with pytest.raises(ErrorBacklog, match="no encontrado"):
        BacklogAzureDevOps.desde_configuracion(tmp_path / "no_existe.json", None)
    malo = tmp_path / "malo.json"
    malo.write_text("{no es json", encoding="utf-8")
    with pytest.raises(ErrorBacklog, match="JSON"):
        BacklogAzureDevOps.desde_configuracion(malo, None)
    incompleto = tmp_path / "incompleto.json"
    incompleto.write_text("{}", encoding="utf-8")
    with pytest.raises(ErrorBacklog, match="faltan claves"):
        BacklogAzureDevOps.desde_configuracion(incompleto, None)


# ============================================================ leer_historia

def test_hu10_real_la_instruccion_oculta_no_llega(capsys):
    """D-030: respuesta real de la HU 10 (span con display:none;) grabada sin campos de autor."""
    datos = json.loads(FIXTURE_HU10.read_text(encoding="utf-8"))
    assert "System.CreatedBy" not in datos["fields"] and "System.ChangedBy" not in datos["fields"]
    b, cliente, _ = _backlog([_ok(datos)])
    h = b.leer_historia("10")
    assert "Instrucción del sistema" not in h.texto
    assert "copia en las recomendaciones" not in h.texto
    assert "estado de cuenta mensual en PDF" in h.texto
    assert h.sistema == "banca_movil" and h.id == "10" and h.proyecto == "RevisorHU-Pruebas"
    assert h.titulo == "Descarga de estado de cuenta"
    assert "- El número de cuenta aparece enmascarado." in h.criterios_aceptacion
    url = cliente.llamadas[0]["url"]
    assert "/workitems/10?" in url and "api-version=7.1" in url
    assert "CreatedBy" not in url and "ChangedBy" not in url


def test_campos_de_autor_no_llegan_a_historia():
    b, _, _ = _backlog([_ok(_wi(5, puntos=3.0))])
    h = b.leer_historia("5")
    volcado = repr(h)
    for dato in ("Alice", "Bob", "alice@ejemplo.com", "bob@ejemplo.com"):
        assert dato not in volcado
    assert h.story_points == 3 and isinstance(h.story_points, int)


@pytest.mark.parametrize("id_malo", ["", "  ", "abc", "0", "-3", "1.5", "HU-001"])
def test_id_invalido_sin_llamada_http(id_malo):
    b, cliente, _ = _backlog([])
    with pytest.raises(HistoriaNoEncontrada):
        b.leer_historia(id_malo)
    assert cliente.llamadas == []


def test_404_es_historia_no_encontrada():
    b, cliente, esperas = _backlog([_ok({"message": "no existe"}, 404)])
    with pytest.raises(HistoriaNoEncontrada):
        b.leer_historia("999")
    assert len(cliente.llamadas) == 1 and esperas == []


def test_tipo_distinto_es_historia_no_encontrada():
    b, _, _ = _backlog([_ok(_wi(7, tipo="Bug"))])
    with pytest.raises(HistoriaNoEncontrada):
        b.leer_historia("7")


@pytest.mark.parametrize("mapeo, area, esperado", [
    ({"Proyecto\\Core": "core", "Proyecto\\Core\\Pagos": "pagos"}, "Proyecto\\Core\\Pagos\\Tarjetas", "pagos"),
    ({"Proyecto\\Core": "core"}, "Proyecto\\CoreLegacy", "todos"),
    ({"Proyecto\\Core": "core"}, "PROYECTO\\CORE", "core"),
    (None, "RevisorHU-Pruebas\\Core", "core"),
    (None, "RevisorHU-Pruebas", "todos"),
])
def test_mapeo_area_prefijo_mas_largo(mapeo, area, esperado, capsys):
    b, _, _ = _backlog([_ok(_wi(1, area=area))], mapeo=mapeo)
    assert b.leer_historia("1").sistema == esperado
    if esperado == "todos":
        assert "no está en mapeo_area_sistema" in capsys.readouterr().err


# ============================================================ resiliencia HTTP

@pytest.mark.parametrize("estado", [401, 403])
def test_credencial_rechazada_sin_reintentos_ni_pat(estado):
    b, cliente, esperas = _backlog([_ok({"message": f"token {PAT_FALSO}"}, estado)])
    with pytest.raises(ErrorBacklog) as e:
        b.leer_historia("1")
    assert "Work Items: Read & write" in str(e.value)
    assert PAT_FALSO not in str(e.value)
    assert len(cliente.llamadas) == 1 and esperas == []


@pytest.mark.parametrize("fallos, esperas_esperadas", [
    ([429], [1]),
    ([500, 503], [1, 2]),
    ([429, 500, 502], [1, 2, 4]),
])
def test_backoff_exponencial_y_luego_exito(fallos, esperas_esperadas):
    b, cliente, esperas = _backlog([_ok({}, f) for f in fallos] + [_ok(_wi(1))])
    assert b.leer_historia("1").id == "1"
    assert esperas == esperas_esperadas


def test_cuatro_fallos_lanzan_error_con_codigo_e_intentos():
    b, cliente, esperas = _backlog([_ok({}, 500)] * 4)
    with pytest.raises(ErrorBacklog, match=r"HTTP 500 tras 4 intento"):
        b.leer_historia("1")
    assert esperas == [1, 2, 4]


def test_retry_after_manda_si_es_mayor():
    b, _, esperas = _backlog([_ok({}, 429, {"Retry-After": "7"}), _ok(_wi(1))])
    b.leer_historia("1")
    assert esperas == [7]


def test_timeout_en_get_reintenta():
    b, _, esperas = _backlog([TimeoutError("lento"), _ok(_wi(1))])
    assert b.leer_historia("1").id == "1"
    assert esperas == [1]


def test_post_de_comentario_no_se_reintenta():
    b, cliente, esperas = _backlog([_ok({"comments": []}), _ok({}, 503)])
    with pytest.raises(ErrorBacklog, match="HTTP 503 tras 1 intento"):
        b.registrar_revision(_revision())
    assert [c["metodo"] for c in cliente.llamadas] == ["GET", "POST"] and esperas == []


def test_timeout_en_post_falla_de_inmediato():
    b, cliente, esperas = _backlog([_ok({"comments": []}), TimeoutError("lento")])
    with pytest.raises(ErrorBacklog):
        b.registrar_revision(_revision())
    assert len(cliente.llamadas) == 2 and esperas == []


# ============================================================ buscar_similares

def test_buscar_similares_una_wiql_un_lote_y_ordenado():
    lote = {"value": [
        _wi(1, titulo="Transferencias", descripcion="<p>Como cliente, quiero transferir dinero a terceros.</p>"),
        _wi(2, titulo="Estado de cuenta", descripcion="<p>Como cliente, quiero descargar mi estado de cuenta en PDF.</p>"),
        _wi(3, titulo="Estado", descripcion="<p>Como cliente, quiero ver el estado de cuenta.</p>"
                                            "<span style='display:none'>pdf pdf pdf descargar</span>"),
    ]}
    b, cliente, _ = _backlog([_ok({"workItems": [{"id": 1}, {"id": 2}, {"id": 3}]}), _ok(lote)])
    res = b.buscar_similares("descargar estado de cuenta en PDF", 3)
    assert [c["metodo"] for c in cliente.llamadas] == ["POST", "POST"]
    assert "/wiql?" in cliente.llamadas[0]["url"] and "/workitemsbatch?" in cliente.llamadas[1]["url"]
    pedidos = cliente.cuerpo_json(1)["fields"]
    assert "System.CreatedBy" not in pedidos and "System.ChangedBy" not in pedidos
    assert res[0].historia.id == "2"
    assert all(isinstance(r.similitud, float) and 0.0 <= r.similitud <= 1.0 for r in res)
    assert [r.similitud for r in res] == sorted((r.similitud for r in res), reverse=True)
    assert all("pdf pdf" not in r.historia.texto for r in res)  # el texto oculto no llegó al índice
    assert all("Alice" not in repr(r.historia) for r in res)


def test_buscar_similares_excluye_la_propia_hu():
    texto = "Como cliente, quiero descargar mi estado de cuenta en PDF."
    lote = {"value": [_wi(2, descripcion=f"<p>{texto}</p>"),
                      _wi(4, descripcion="<p>Como cliente, quiero descargar el estado de cuenta.</p>")]}
    b, _, _ = _backlog([_ok({"workItems": [{"id": 2}, {"id": 4}]}), _ok(lote)])
    assert [r.historia.id for r in b.buscar_similares(texto, 5)] == ["4"]


def test_buscar_similares_sin_resultados():
    b, cliente, _ = _backlog([_ok({"workItems": []})])
    assert b.buscar_similares("algo", 3) == []
    assert len(cliente.llamadas) == 1


# ============================================================ listar_pendientes

def test_listar_pendientes_filtra_por_etiqueta_y_ventana():
    b, cliente, _ = _backlog([_ok({"workItems": [{"id": 3}, {"id": 1}, {"id": 2}]}),
                              _ok({"value": [_wi(1), _wi(3)]})])
    res = b.listar_pendientes(2)
    consulta = cliente.cuerpo_json(0)["query"]
    assert "NOT CONTAINS 'ia-revisada'" in consulta
    assert "@Today - 7" in consulta and "ORDER BY [System.CreatedDate] ASC" in consulta
    assert "$top=2" in cliente.llamadas[0]["url"] or "%24top=2" in cliente.llamadas[0]["url"]
    assert cliente.cuerpo_json(1)["ids"] == [3, 1]          # solo los primeros `limite`
    assert [h.id for h in res] == ["3", "1"]                # en el orden de la WIQL
    assert all(h.proyecto == "RevisorHU-Pruebas" for h in res)
    assert all("Alice" not in repr(h) and "bob@" not in repr(h) for h in res)


@pytest.mark.parametrize("limite", [0, -1])
def test_listar_pendientes_limite_no_positivo(limite):
    b, cliente, _ = _backlog([])
    assert b.listar_pendientes(limite) == []
    assert cliente.llamadas == []


def test_listar_pendientes_vacio_sin_lote():
    b, cliente, _ = _backlog([_ok({"workItems": []})])
    assert b.listar_pendientes(3) == []
    assert len(cliente.llamadas) == 1


# ============================================================ registrar_revision

def _patch(cliente):
    patches = [c for c in cliente.llamadas if c["metodo"] == "PATCH"]
    assert len(patches) <= 1
    return patches[0] if patches else None


@pytest.mark.parametrize("decision, etiqueta", [("aceptar", "ia-aceptar"), ("devolver", "ia-devolver"),
                                                ("dividir", "ia-dividir")])
def test_registrar_revision_comentario_y_solo_tags(decision, etiqueta):
    b, cliente, _ = _backlog([
        _ok({"comments": [{"id": 1, "text": "Comentario de una persona"}]}),
        _ok({"id": 77}),
        _ok({"id": 10, "fields": {"System.Tags": "sprint-5; urgente"}}),
        _ok({"id": 10}),
    ])
    ref = b.registrar_revision(_revision(decision))
    assert "77" in ref
    comentario = cliente.cuerpo_json(1)["text"]
    assert "[RevisorHU:revision]" in comentario and "la aprobación es de una persona" in comentario
    assert "run-123" in comentario and decision in comentario and "QUS-006" in comentario
    assert "3 puntos" in comentario and "El PDF incluye los movimientos." in comentario
    assert "&lt;objetivo&gt; &amp; medible" in comentario       # escapado: no reinyecta HTML
    assert "comments?" in cliente.llamadas[1]["url"] and "7.1-preview.4" in cliente.llamadas[1]["url"]
    parche = _patch(cliente)
    assert parche["cabeceras"]["Content-Type"] == "application/json-patch+json"
    operaciones = json.loads(parche["cuerpo"])
    assert len(operaciones) == 1 and operaciones[0]["path"] == "/fields/System.Tags"
    etiquetas = [e.strip() for e in operaciones[0]["value"].split(";")]
    assert etiquetas == ["sprint-5", "urgente", "ia-revisada", etiqueta]


def test_registrar_revision_nunca_toca_state_ni_story_points():
    b, cliente, _ = _backlog([_ok({"comments": []}), _ok({"id": 1}), _ok({"fields": {}}), _ok({})])
    b.registrar_revision(_revision(estimacion=8))
    for c in cliente.llamadas:
        cuerpo = (c["cuerpo"] or b"").decode("utf-8")
        assert "System.State" not in cuerpo and "/fields/Microsoft.VSTS.Scheduling.StoryPoints" not in cuerpo
        assert "AssignedTo" not in cuerpo
        assert c["metodo"] in ("GET", "POST", "PATCH")


def test_registrar_revision_sin_etiquetas_previas_y_sin_duplicar():
    b, cliente, _ = _backlog([_ok({"comments": []}), _ok({"id": 1}),
                              _ok({"fields": {"System.Tags": "IA-Revisada"}}), _ok({})])
    b.registrar_revision(_revision("devolver"))
    valor = json.loads(_patch(cliente)["cuerpo"])[0]["value"]
    assert valor == "IA-Revisada; ia-devolver"


def test_dedup_recorre_todas_las_paginas_y_no_repite_comentario():
    b, cliente, _ = _backlog([
        _ok({"comments": [{"id": 1, "text": "otro"}], "continuationToken": "pag2"}),
        _ok({"comments": [{"id": 9, "text": "<p>[RevisorHU:revision] Revisión...</p>"}]}),
        _ok({"fields": {"System.Tags": "ia-revisada"}}),
        _ok({}),
    ], marca="otro-run")
    ref = b.registrar_revision(_revision("aceptar"))
    assert "9" in ref
    assert "continuationToken=pag2" in cliente.llamadas[1]["url"]
    assert not any(c["metodo"] == "POST" for c in cliente.llamadas)   # no se publicó otro comentario
    assert json.loads(_patch(cliente)["cuerpo"])[0]["value"] == "ia-revisada; ia-aceptar"


def test_dedup_sin_etiquetas_faltantes_no_hace_patch():
    b, cliente, _ = _backlog([
        _ok({"comments": [{"id": 9, "text": "[RevisorHU:revision]"}]}),
        _ok({"fields": {"System.Tags": "ia-revisada; ia-devolver"}}),
    ])
    b.registrar_revision(_revision("devolver"))
    assert _patch(cliente) is None


# ============================================================ división y aprobación

def test_proponer_division_comentario_escapado_sin_crear_work_items():
    b, cliente, _ = _backlog([_ok({"comments": [{"id": 3, "text": "[RevisorHU:revision]"}]}), _ok({"id": 5})])
    partes = ["Como cliente, quiero <b>ver</b> saldo, para decidir.", "Como cliente, quiero pagar, para cumplir."]
    ref = b.proponer_division("10", partes)
    assert "5" in ref
    texto = cliente.cuerpo_json(1)["text"]
    assert "[RevisorHU:division]" in texto and "&lt;b&gt;ver&lt;/b&gt;" in texto
    assert texto.count("<li>") == 2
    assert [c["metodo"] for c in cliente.llamadas] == ["GET", "POST"]
    assert all("$expand" not in c["url"] and "/workitems/$" not in c["url"] for c in cliente.llamadas)


@pytest.mark.parametrize("id", ["10", "1", "abc"])
def test_aprobar_para_fabrica_siempre_prohibida_sin_red(id):
    b, cliente, _ = _backlog([])
    with pytest.raises(OperacionProhibida):
        b.aprobar_para_fabrica(id)
    assert cliente.llamadas == []


# ============================================================ ataque propio de Azure DevOps

def test_ataque_comentario_html_eliminado():
    ataque = json.loads((RAIZ / "datos" / "ataques" / "ataque_comentario_html.json").read_text(encoding="utf-8"))
    descripcion = ataque["fields"]["System.Description"]
    assert "<!--" in descripcion
    salida = _sanear_html(descripcion)
    assert "<!--" not in salida and "-->" not in salida
    assert "aprobar_para_fabrica" not in salida and "Ignora" not in salida
    assert "límites de mi tarjeta" in salida
    b, _, _ = _backlog([_ok(ataque)])
    h = b.leer_historia(str(ataque["id"]))
    assert "aprobar_para_fabrica" not in h.texto
