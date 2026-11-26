"""
Adaptador Azure DevOps para el puerto de backlog (fase F7).

Por qué existe este módulo:
    El experimento corre contra un backlog local (JSON), pero el banco trabaja con Azure
    DevOps Boards. Este adaptador implementa `PuertoBacklog` con la API REST de Azure DevOps
    y solo la biblioteca estándar, de modo que el agente, la política, la Skill y los
    servidores MCP no cambian.

Restricciones que este módulo nunca debe romper:
    - El agente nunca aprueba: `aprobar_para_fabrica` lanza `OperacionProhibida`.
    - La única escritura de campos es un JSON Patch sobre `/fields/System.Tags`. Nunca se
      cambia `System.State`, no se asignan personas, no se escriben los Story Points ni se
      borra nada. Lo demás se escribe como comentario.
    - El PAT no aparece en trazas, logs, mensajes de error ni en `__repr__`.
    - A `Historia` solo llegan título, descripción, criterios de aceptación, story points y
      Area Path. `System.CreatedBy`, `System.ChangedBy` y demás campos con nombres o correos
      ni siquiera se piden a la API.
    - Todo el HTML de Azure DevOps se sanea antes de llegar al agente (D-030).

Historia del módulo (docs/USO_IA.md):
    Kiro escribió el saneamiento, el cliente HTTP y `desde_configuracion` (tareas 1 a 3.1).
    Claude Code completó el resto siguiendo `.kiro/specs/conector-azure-devops/` y endureció
    el saneamiento con una pila de etiquetas (cierres que no coinciden ya no revelan texto).
"""

from __future__ import annotations

import base64
import html
import html.parser
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

from revisor.backlog.puerto import (
    ErrorBacklog,
    Historia,
    HistoriaNoEncontrada,
    HistoriaSimilar,
    OperacionProhibida,
    PuertoBacklog,
    Revision,
)
from revisor.backlog.similitud import IndiceSimilitud

# ================================================================= constantes
# Detecta estilos CSS que ocultan un elemento. Se aplica al valor del atributo `style`.
#   - display:none y visibility:hidden, con cualquier espaciado, mayúsculas y `;` final;
#   - opacity:0 (también 0.0), pero no 0.5 ni 0.05;
#   - font-size:0 con unidad opcional, pero no 0.8em ni 0.5px.
_RE_OCULTO = re.compile(
    r"""
    (?:
        display\s*:\s*none
      | visibility\s*:\s*hidden
      | opacity\s*:\s*0(?:\.0+)?(?![\d.])
      | font-size\s*:\s*0(?:\.0+)?(?:px|em|pt|rem|%)?(?![\d.])
    )
    \s*;?
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Etiquetas sin cierre (void elements): nunca abren ni cierran una región oculta.
_VOID_ELEMENTS: frozenset[str] = frozenset(
    {"br", "img", "hr", "input", "meta", "link", "wbr", "area", "base", "col", "embed", "source", "track"}
)

# Etiquetas cuyo contenido nunca es texto visible para una persona.
_SIEMPRE_OCULTAS: frozenset[str] = frozenset({"script", "style", "template", "noscript"})

# Etiquetas de bloque: separan líneas en el texto plano, para que el agente no reciba
# "criterio unocriterio dos" pegados.
_BLOQUES: frozenset[str] = frozenset(
    {"p", "div", "br", "li", "ul", "ol", "tr", "table", "blockquote", "pre", "section",
     "h1", "h2", "h3", "h4", "h5", "h6"}
)

# Campos que se piden a la API. Lista blanca: lo que no está aquí no entra al proceso.
CAMPO_TITULO = "System.Title"
CAMPO_DESCRIPCION = "System.Description"
CAMPO_CRITERIOS = "Microsoft.VSTS.Common.AcceptanceCriteria"
CAMPO_PUNTOS = "Microsoft.VSTS.Scheduling.StoryPoints"
CAMPO_AREA = "System.AreaPath"
CAMPO_TIPO = "System.WorkItemType"
CAMPO_ETIQUETAS = "System.Tags"
CAMPOS_HISTORIA: tuple[str, ...] = (
    CAMPO_TITULO, CAMPO_DESCRIPCION, CAMPO_CRITERIOS, CAMPO_PUNTOS, CAMPO_AREA, CAMPO_TIPO,
)

API_VERSION = "7.1"
API_VERSION_COMENTARIOS = "7.1-preview.4"

# Marcas de deduplicación: texto ASCII visible en el comentario. Son distintas para la
# revisión y para la división porque una HU que se divide recibe los dos comentarios.
MARCA_REVISION = "[RevisorHU:revision]"
MARCA_DIVISION = "[RevisorHU:division]"
AVISO = "Borrador generado por IA; la aprobación es de una persona."

# Reintentos de peticiones idempotentes: 4 intentos, esperas 1, 2 y 4 s (Retry-After manda
# si es mayor, con un tope para que un servidor no deje colgado al poller).
MAX_INTENTOS = 4
TOPE_RETRY_AFTER_S = 60
MAX_IDS_POR_LOTE = 200
MAX_HISTORIAS_BUSQUEDA = 200


# ================================================================= saneamiento
def _sanear_html(html_texto: str) -> str:
    """
    Convierte el HTML de un campo de Azure DevOps en texto plano sin contenido oculto.

    Se elimina: comentarios HTML, `<script>`, `<style>`, `<template>`, `<noscript>` y todo
    elemento con `hidden`, `aria-hidden="true"` o un `style` que lo oculte (D-030).

    Por qué una pila de etiquetas y no solo un contador:
        Con un contador, un cierre que no corresponde (`<span hidden></p>secreto</span>`)
        bajaría la profundidad a 0 y "secreto" llegaría al agente. Con la pila, un cierre solo
        cuenta si coincide con una etiqueta abierta dentro de la región oculta; si no, se ignora.

    Comportamiento ante HTML malformado (siempre del lado seguro):
        - Cierres huérfanos fuera de una región oculta se ignoran.
        - Si el campo termina dentro de una región oculta, ese texto ya fue descartado.

    Un solo desescapado: `convert_charrefs=True` resuelve `&amp;`, `&lt;`, etc. No se aplica
    `html.unescape()` después, porque convertiría `&amp;lt;script&gt;` en `<script>`.
    """

    class _Extractor(html.parser.HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self._pila_oculta: list[str] = []  # etiquetas abiertas dentro de la región oculta
            self._partes: list[str] = []

        @staticmethod
        def _es_oculta(etiqueta: str, attrs: list[tuple[str, str | None]]) -> bool:
            if etiqueta in _SIEMPRE_OCULTAS:
                return True
            for nombre, valor in attrs:
                if nombre == "hidden":
                    return True
                if nombre == "aria-hidden" and (valor or "").strip().lower() == "true":
                    return True
                if nombre == "style" and valor and _RE_OCULTO.search(valor):
                    return True
            return False

        def _salto(self, etiqueta: str) -> None:
            if etiqueta == "li":
                self._partes.append("\n- ")
            elif etiqueta in _BLOQUES:
                self._partes.append("\n")

        def handle_starttag(self, etiqueta: str, attrs: list[tuple[str, str | None]]) -> None:
            if etiqueta in _VOID_ELEMENTS:
                if not self._pila_oculta and etiqueta in _BLOQUES:
                    self._partes.append("\n")
                return
            if self._pila_oculta or self._es_oculta(etiqueta, attrs):
                self._pila_oculta.append(etiqueta)
            else:
                self._salto(etiqueta)

        def handle_startendtag(self, etiqueta: str, attrs: list[tuple[str, str | None]]) -> None:
            # `<x/>` no deja nada abierto: no abre ni cierra regiones ocultas.
            if not self._pila_oculta and etiqueta in _BLOQUES:
                self._partes.append("\n")

        def handle_endtag(self, etiqueta: str) -> None:
            if etiqueta in _VOID_ELEMENTS:
                return  # `</br>` y similares no cierran nada
            if self._pila_oculta:
                if etiqueta in self._pila_oculta:
                    # Cierra hasta la etiqueta correspondiente (las intermedias quedaron sin cerrar).
                    while self._pila_oculta.pop() != etiqueta:
                        pass
                # Un cierre que no coincide con nada abierto dentro de la región se ignora.
                return
            if etiqueta in _BLOQUES:
                self._partes.append("\n")

        def handle_comment(self, data: str) -> None:
            """Los comentarios HTML son el vector de inyección indirecta más común: se descartan."""

        def handle_data(self, data: str) -> None:
            if not self._pila_oculta:
                self._partes.append(data)

        def texto(self) -> str:
            crudo = "".join(self._partes).replace("\xa0", " ")
            lineas = [re.sub(r"[ \t\r\f\v]+", " ", linea).strip() for linea in crudo.split("\n")]
            lineas = [linea for linea in lineas if linea and linea != "-"]
            return "\n".join(lineas)

    if not html_texto:
        return ""
    extractor = _Extractor()
    extractor.feed(html_texto)
    extractor.close()
    return extractor.texto()


# ================================================================= cliente HTTP
class ClienteHTTP:
    """
    Protocolo (duck typing) del cliente HTTP que usa el adaptador.

    `solicitar` devuelve `(código, cuerpo)` o `(código, cuerpo, cabeceras)`. Las cabeceras
    son opcionales para que un cliente falso de prueba pueda devolver solo dos valores; el
    adaptador las usa para `Retry-After`. Un fallo de red o de tiempo de espera se propaga
    como `OSError` (por ejemplo `TimeoutError` o `urllib.error.URLError`).
    """

    def solicitar(self, metodo: str, url: str, cuerpo: bytes | None = None,
                  cabeceras: dict[str, str] | None = None) -> tuple:
        ...


class _ClienteHTTPReal:
    """
    Implementación real con `urllib.request`. Timeout de 30 s por petición.

    La cabecera `Authorization` se arma en cada llamada; el PAT no aparece en `__repr__`.
    """

    _TIEMPO_ESPERA = 30

    def __init__(self, pat: str) -> None:
        self._pat = pat

    def __repr__(self) -> str:
        return "_ClienteHTTPReal()"

    __str__ = __repr__

    def solicitar(self, metodo: str, url: str, cuerpo: bytes | None = None,
                  cabeceras: dict[str, str] | None = None) -> tuple[int, bytes, dict[str, str]]:
        credencial = base64.b64encode(f":{self._pat}".encode()).decode()
        todas = {"Authorization": f"Basic {credencial}", "Accept": "application/json"}
        todas.update(cabeceras or {})
        peticion = urllib.request.Request(url=url, data=cuerpo, headers=todas, method=metodo)
        try:
            with urllib.request.urlopen(peticion, timeout=self._TIEMPO_ESPERA) as respuesta:
                return respuesta.status, respuesta.read(), dict(respuesta.headers.items())
        except urllib.error.HTTPError as exc:
            cuerpo_error = exc.read() if exc.fp is not None else b""
            return exc.code, cuerpo_error, dict(exc.headers.items()) if exc.headers else {}


# ================================================================= utilidades
def _id_numerico(id: object) -> int:
    """Valida el id de un work item. Lanza `HistoriaNoEncontrada` sin tocar la red."""
    texto = str(id).strip()
    if not texto.isdigit() or int(texto) <= 0:
        raise HistoriaNoEncontrada(f"'{texto}' no es un id de work item válido (debe ser un número positivo).")
    return int(texto)


def _separar_etiquetas(valor: str | None) -> list[str]:
    return [e.strip() for e in (valor or "").split(";") if e.strip()]


def _wiql_literal(valor: str) -> str:
    """Literal de texto para WIQL: comillas simples duplicadas."""
    return "'" + valor.replace("'", "''") + "'"


def _story_points(valor: object) -> int | None:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    return int(round(valor))


def _normalizar_espacios(texto: str) -> str:
    return " ".join(texto.split())


def _retry_after(cabeceras: dict[str, str]) -> float:
    for nombre, valor in cabeceras.items():
        if nombre.lower() == "retry-after":
            try:
                return min(float(valor), TOPE_RETRY_AFTER_S)
            except ValueError:
                return 0.0
    return 0.0


# ================================================================= adaptador
class BacklogAzureDevOps(PuertoBacklog):
    """
    `PuertoBacklog` sobre Azure DevOps Boards.

    En producción se construye siempre con `desde_configuracion`; las pruebas pueden usar
    `__init__` con valores ya validados y un cliente HTTP falso.
    """

    def __init__(
        self,
        *,
        org_url: str,
        project: str,
        tipo_work_item: str,
        mapeo_area_sistema: dict[str, str],
        sistema_por_defecto: str,
        etiquetas: dict,
        poller: dict,
        marca: str | None,
        cliente_http: ClienteHTTP,
        dormir: Callable[[float], None] = time.sleep,
    ) -> None:
        self._org_url = org_url.rstrip("/")
        self._project = project
        self.tipo_work_item = tipo_work_item
        self.mapeo_area_sistema = mapeo_area_sistema
        self.sistema_por_defecto = sistema_por_defecto
        self.etiquetas = etiquetas
        self.poller = poller
        self._marca = marca
        self._cliente_http = cliente_http
        self._dormir = dormir
        self._base = f"{self._org_url}/{urllib.parse.quote(project)}/_apis/wit"

    def __repr__(self) -> str:
        return f"BacklogAzureDevOps(project={self._project!r})"

    __str__ = __repr__

    @classmethod
    def desde_configuracion(
        cls,
        ruta_config: Path,
        marca: str | None = None,
        cliente_http: ClienteHTTP | None = None,
        dormir: Callable[[float], None] | None = None,
    ) -> "BacklogAzureDevOps":
        """
        Lee `config/azure_devops.json` (sin secretos) y, del entorno, `AZDO_ORG_URL`,
        `AZDO_PROJECT` y `AZDO_PAT`. Falla con `ErrorBacklog` antes de cualquier llamada HTTP
        si falta algo. Ningún mensaje incluye el PAT.
        """
        ruta_config = Path(ruta_config)
        try:
            config = json.loads(ruta_config.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise ErrorBacklog(f"Archivo de configuración no encontrado: {ruta_config}") from None
        except json.JSONDecodeError as exc:
            raise ErrorBacklog(f"El archivo de configuración {ruta_config} no es JSON válido: {exc}") from None
        except OSError as exc:
            raise ErrorBacklog(f"No se pudo leer el archivo de configuración {ruta_config}: {exc}") from None

        faltan = [c for c in ("tipo_work_item", "mapeo_area_sistema", "sistema_por_defecto", "etiquetas", "poller")
                  if c not in config]
        if faltan:
            raise ErrorBacklog(f"{ruta_config}: faltan claves obligatorias: {', '.join(faltan)}")

        for nombre_var in ("AZDO_ORG_URL", "AZDO_PROJECT", "AZDO_PAT"):
            if not os.environ.get(nombre_var, "").strip():
                raise ErrorBacklog(f"Variable de entorno obligatoria ausente o vacía: {nombre_var}")

        if cliente_http is None:
            cliente_http = _ClienteHTTPReal(os.environ["AZDO_PAT"].strip())
        return cls(
            org_url=os.environ["AZDO_ORG_URL"].strip(),
            project=os.environ["AZDO_PROJECT"].strip(),
            tipo_work_item=config["tipo_work_item"],
            mapeo_area_sistema=config["mapeo_area_sistema"],
            sistema_por_defecto=config["sistema_por_defecto"],
            etiquetas=config["etiquetas"],
            poller=config["poller"],
            marca=marca,
            cliente_http=cliente_http,
            dormir=dormir if dormir is not None else time.sleep,
        )

    # ---------------------------------------------------------------- HTTP
    def _pedir(self, metodo: str, url: str, cuerpo: object = None, *, idempotente: bool,
               tipo_contenido: str = "application/json") -> dict:
        """
        Hace una petición y devuelve el JSON de la respuesta.

        Idempotentes (GET, WIQL, lote): hasta 4 intentos ante 429, 5xx o fallo de red, con
        esperas de 1, 2 y 4 s o `Retry-After` si es mayor. No idempotentes (comentario,
        etiquetas): un solo intento; la deduplicación evita duplicados si el poller reintenta.
        """
        datos = json.dumps(cuerpo, ensure_ascii=False).encode("utf-8") if cuerpo is not None else None
        cabeceras = {"Content-Type": tipo_contenido} if datos is not None else {}
        intentos = MAX_INTENTOS if idempotente else 1
        for intento in range(1, intentos + 1):
            espera = float(2 ** (intento - 1))
            try:
                respuesta = self._cliente_http.solicitar(metodo, url, datos, cabeceras)
            except OSError as exc:
                if intento == intentos:
                    raise ErrorBacklog(
                        f"Azure DevOps no respondió ({type(exc).__name__}) tras {intento} intento(s)."
                    ) from None
                self._dormir(espera)
                continue
            estado, contenido = respuesta[0], respuesta[1]
            cabeceras_resp = respuesta[2] if len(respuesta) > 2 else {}
            if 200 <= estado < 300:
                if not contenido:
                    return {}
                try:
                    return json.loads(contenido.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    raise ErrorBacklog(f"Azure DevOps devolvió una respuesta que no es JSON (HTTP {estado}).") from None
            if estado in (401, 403):
                raise ErrorBacklog(
                    f"Azure DevOps rechazó la credencial (HTTP {estado}). Revisa que AZDO_PAT esté vigente "
                    "y tenga el alcance 'Work Items: Read & write'."
                )
            if estado == 404:
                raise HistoriaNoEncontrada(f"Azure DevOps no encontró el recurso (HTTP 404).")
            if (estado == 429 or estado >= 500) and intento < intentos:
                self._dormir(max(espera, _retry_after(cabeceras_resp)))
                continue
            raise ErrorBacklog(f"Azure DevOps respondió HTTP {estado} tras {intento} intento(s).{self._detalle(contenido)}")
        raise ErrorBacklog("Azure DevOps no respondió.")  # inalcanzable; deja contento al verificador de tipos

    @staticmethod
    def _detalle(contenido: bytes) -> str:
        """Mensaje de error de la API, corto. Sirve para diagnosticar un 400 (por ejemplo, WIQL inválida)."""
        try:
            mensaje = json.loads(contenido.decode("utf-8")).get("message", "")
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            return ""
        return f" Detalle: {str(mensaje)[:200]}" if mensaje else ""

    def _url(self, ruta: str, version: str = API_VERSION, **parametros: str) -> str:
        consulta = urllib.parse.urlencode({**parametros, "api-version": version})
        return f"{self._base}/{ruta}?{consulta}"

    def _wiql(self, consulta: str, top: int) -> list[int]:
        respuesta = self._pedir("POST", self._url("wiql", **{"$top": str(top)}), {"query": consulta}, idempotente=True)
        return [int(w["id"]) for w in respuesta.get("workItems", [])]

    def _lote(self, ids: list[int], campos: tuple[str, ...]) -> dict[int, dict]:
        """Lee work items en lotes de 200 y devuelve {id: fields}, sin perder el orden de `ids`."""
        resultado: dict[int, dict] = {}
        for i in range(0, len(ids), MAX_IDS_POR_LOTE):
            parte = ids[i:i + MAX_IDS_POR_LOTE]
            respuesta = self._pedir("POST", self._url("workitemsbatch"),
                                    {"ids": parte, "fields": list(campos), "errorPolicy": "omit"},
                                    idempotente=True)
            for wi in respuesta.get("value", []):
                if wi and "id" in wi:
                    resultado[int(wi["id"])] = wi.get("fields", {})
        return {i: resultado[i] for i in ids if i in resultado}

    # ---------------------------------------------------------------- conversión
    def _sistema(self, area: str) -> str:
        """Prefijo más largo de `mapeo_area_sistema`, por segmentos y sin distinguir mayúsculas."""
        area_n = area.strip().lower()
        mejor, largo = None, -1
        for prefijo, sistema in self.mapeo_area_sistema.items():
            p = prefijo.strip().lower()
            if (area_n == p or area_n.startswith(p + "\\")) and len(p) > largo:
                mejor, largo = sistema, len(p)
        if mejor is None:
            print(f"azure_devops: el Area Path '{area}' no está en mapeo_area_sistema; "
                  f"se usa '{self.sistema_por_defecto}'.", file=sys.stderr)
            return self.sistema_por_defecto
        return mejor

    def _a_historia(self, id: int, campos: dict) -> Historia:
        """Construye `Historia` campo por campo: nada fuera de la lista blanca llega al agente."""
        return Historia(
            id=str(id),
            texto=_sanear_html(str(campos.get(CAMPO_DESCRIPCION) or "")),
            sistema=self._sistema(str(campos.get(CAMPO_AREA) or "")),
            proyecto=self._project,
            titulo=str(campos.get(CAMPO_TITULO) or "").strip(),
            story_points=_story_points(campos.get(CAMPO_PUNTOS)),
            criterios_aceptacion=_sanear_html(str(campos.get(CAMPO_CRITERIOS) or "")),
        )

    # ---------------------------------------------------------------- lectura
    def leer_historia(self, id: str) -> Historia:
        numero = _id_numerico(id)
        respuesta = self._pedir("GET", self._url(f"workitems/{numero}", fields=",".join(CAMPOS_HISTORIA)),
                                idempotente=True)
        campos = respuesta.get("fields", {})
        if campos.get(CAMPO_TIPO) != self.tipo_work_item:
            raise HistoriaNoEncontrada(f"El work item {numero} no es de tipo '{self.tipo_work_item}'.")
        return self._a_historia(numero, campos)

    def buscar_similares(self, texto: str, limite: int) -> list[HistoriaSimilar]:
        if limite <= 0:
            return []
        consulta = (
            "SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = @project "
            f"AND [System.WorkItemType] = {_wiql_literal(self.tipo_work_item)} "
            "ORDER BY [System.CreatedDate] DESC"
        )
        ids = self._wiql(consulta, MAX_HISTORIAS_BUSQUEDA)
        if not ids:
            return []
        historias = {i: self._a_historia(i, c) for i, c in self._lote(ids, CAMPOS_HISTORIA).items()}
        buscado = _normalizar_espacios(texto)
        # La propia HU (texto saneado idéntico) no cuenta como similar a sí misma.
        candidatas = {str(i): h for i, h in historias.items() if _normalizar_espacios(h.texto) != buscado}
        indice = IndiceSimilitud({i: f"{h.titulo} {h.texto}" for i, h in candidatas.items()})
        return [HistoriaSimilar(candidatas[i], min(max(float(s), 0.0), 1.0)) for i, s in indice.buscar(texto, limite)]

    def listar_pendientes(self, limite: int) -> list[Historia]:
        if limite <= 0:
            return []
        dias = int(self.poller.get("ventana_dias", 7))
        # Etiqueta de entrada (D-039): con `requerir_etiqueta_para_revision`, el poller solo toma las
        # HU que el analista marcó como terminadas, para no revisar una HU que aún se está redactando.
        entrada = ""
        if self.poller.get("requerir_etiqueta_para_revision"):
            etiqueta = self.etiquetas.get("para_revision")
            if not etiqueta:
                raise ErrorBacklog("requerir_etiqueta_para_revision está activo, pero falta etiquetas.para_revision "
                                   "en config/azure_devops.json.")
            entrada = f"AND [System.Tags] CONTAINS {_wiql_literal(etiqueta)} "
        consulta = (
            "SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = @project "
            f"AND [System.WorkItemType] = {_wiql_literal(self.tipo_work_item)} "
            f"AND [System.Tags] NOT CONTAINS {_wiql_literal(self.etiquetas['revisada'])} "
            f"{entrada}"
            f"AND [System.CreatedDate] >= @Today - {dias} "
            "ORDER BY [System.CreatedDate] ASC"
        )
        ids = self._wiql(consulta, limite)[:limite]
        if not ids:
            return []
        return [self._a_historia(i, c) for i, c in self._lote(ids, CAMPOS_HISTORIA).items()]

    # ---------------------------------------------------------------- escritura
    def _comentarios(self, numero: int) -> list[dict]:
        """Todos los comentarios del work item, recorriendo las páginas (`continuationToken`)."""
        comentarios: list[dict] = []
        token: str | None = None
        for _ in range(100):  # tope de seguridad: 100 páginas de 200
            parametros = {"$top": "200"}
            if token:
                parametros["continuationToken"] = token
            respuesta = self._pedir("GET", self._url(f"workItems/{numero}/comments", API_VERSION_COMENTARIOS,
                                                     **parametros), idempotente=True)
            comentarios.extend(respuesta.get("comments", []))
            token = respuesta.get("continuationToken")
            if not token:
                break
        return comentarios

    def _publicar_una_vez(self, numero: int, marca_tipo: str, cuerpo_html: str) -> str:
        """Publica el comentario salvo que ya exista uno con la misma marca. Devuelve su id."""
        for c in self._comentarios(numero):
            if marca_tipo in str(c.get("text") or ""):
                return str(c.get("id", ""))
        respuesta = self._pedir("POST", self._url(f"workItems/{numero}/comments", API_VERSION_COMENTARIOS),
                                {"text": cuerpo_html}, idempotente=False)
        return str(respuesta.get("id", ""))

    def _agregar_etiquetas(self, numero: int, nuevas: list[str]) -> None:
        """Agrega etiquetas conservando las existentes. Única escritura de campos: System.Tags."""
        respuesta = self._pedir("GET", self._url(f"workitems/{numero}", fields=CAMPO_ETIQUETAS), idempotente=True)
        actuales = _separar_etiquetas(respuesta.get("fields", {}).get(CAMPO_ETIQUETAS))
        en_minusculas = {e.lower() for e in actuales}
        faltan = [e for e in nuevas if e.lower() not in en_minusculas]
        if not faltan:
            return
        parche = [{"op": "add", "path": f"/fields/{CAMPO_ETIQUETAS}", "value": "; ".join(actuales + faltan)}]
        self._pedir("PATCH", self._url(f"workitems/{numero}"), parche, idempotente=False,
                    tipo_contenido="application/json-patch+json")

    def _pie(self) -> str:
        return f"<p><em>Marca de ejecución: {html.escape(self._marca)}</em></p>" if self._marca else ""

    def _comentario_revision(self, r: Revision) -> str:
        e = html.escape

        def lista(items: list[str]) -> str:
            return "<ul>" + "".join(f"<li>{e(i)}</li>" for i in items) + "</ul>" if items else "<p>(ninguno)</p>"

        recomendaciones = "".join(f"<li><strong>{e(x.defecto)}:</strong> {e(x.texto)}</li>" for x in r.recomendaciones)
        return (
            f"<p>{MARCA_REVISION} <strong>Revisión del agente RevisorHU</strong> · <em>{e(AVISO)}</em></p>"
            f"<p><strong>Recomendación:</strong> {e(r.decision)}</p>"
            f"<p><strong>Tipo:</strong> {e(r.tipo)}</p>"
            f"<p><strong>Estimación sugerida:</strong> {e(str(r.estimacion))} puntos "
            "(sugerencia; el campo Story Points no se modifica)</p>"
            f"<p><strong>Defectos encontrados:</strong></p>{lista(r.defectos)}"
            "<p><strong>Recomendaciones:</strong></p>"
            + (f"<ul>{recomendaciones}</ul>" if recomendaciones else "<p>(ninguna)</p>")
            + "<p><strong>Historia refinada:</strong></p>"
            f"<p>{e(r.historia_refinada) if r.historia_refinada else '(sin historia refinada)'}</p>"
            f"<p><strong>Criterios de aceptación propuestos:</strong></p>{lista(r.criterios_aceptacion)}"
            + self._pie()
        )

    def registrar_revision(self, revision: Revision) -> str:
        """
        Un comentario con la revisión y las etiquetas `ia-revisada` + la de la decisión.
        Si ya hay un comentario de revisión (reintento), no lo repite: solo completa etiquetas.
        """
        numero = _id_numerico(revision.id_historia)
        por_decision = self.etiquetas.get("por_decision", {})
        if revision.decision not in por_decision:
            raise ErrorBacklog(f"Decisión sin etiqueta configurada: '{revision.decision}'.")
        id_comentario = self._publicar_una_vez(numero, MARCA_REVISION, self._comentario_revision(revision))
        self._agregar_etiquetas(numero, [self.etiquetas["revisada"], por_decision[revision.decision]])
        return f"work item {numero}, comentario {id_comentario}"

    def proponer_division(self, id: str, partes: list[str]) -> str:
        """La propuesta va como comentario. No crea work items hijos ni vínculos."""
        numero = _id_numerico(id)
        cuerpo = (
            f"<p>{MARCA_DIVISION} <strong>Propuesta de división del agente RevisorHU</strong> · "
            f"<em>{html.escape(AVISO)}</em></p>"
            "<p>Se propone dividir esta historia en:</p>"
            "<ol>" + "".join(f"<li>{html.escape(p)}</li>" for p in partes) + "</ol>"
            + self._pie()
        )
        id_comentario = self._publicar_una_vez(numero, MARCA_DIVISION, cuerpo)
        return f"work item {numero}, comentario {id_comentario}"

    def aprobar_para_fabrica(self, id: str) -> str:
        """Siempre prohibido, sin ninguna llamada HTTP: la aprobación es humana (D-006)."""
        raise OperacionProhibida(
            "aprobar_para_fabrica no está permitido en Azure DevOps; la aprobación es una decisión humana."
        )
