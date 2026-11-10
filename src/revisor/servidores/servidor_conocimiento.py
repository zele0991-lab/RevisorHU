"""
servidor_conocimiento: la base de conocimiento que hoy está en la cabeza de los líderes técnicos.

Solo lectura. Herramientas:
    listar_criterios   criterios ACTIVOS que aplican al sistema (solo id, nombre y severidad)
    obtener_criterio   detalle de un criterio; si está obsoleto, indica cuál lo reemplaza
    buscar_guia        secciones de las guías para personas (QUS, INVEST, banca móvil, DoR)

Por qué `listar_criterios` devuelve tan poco:
    Para que el costo en tokens no crezca con el tamaño del catálogo. El agente pide el
    detalle (cómo verificar, ejemplos) solo de los criterios que está evaluando.

Uso (stdio, desde la raíz del repositorio):
    python -m revisor.servidores.servidor_conocimiento
"""

# Sin `from __future__ import annotations` (ver servidor_backlog): MCPServer evalúa las anotaciones.
import argparse
import json
import sys
from typing import Annotated

from pydantic import Field

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from revisor.conocimiento.catalogo import Catalogo
from revisor.conocimiento.guias import MAX_TEXTO_SECCION, IndiceGuias
from revisor.servidores.comun import endurecer_esquemas, errores_busqueda, rechazo

LIMITE_GUIA = (1, 5)


def _json(datos: dict) -> str:
    return json.dumps(datos, ensure_ascii=False)


def crear_servidor(catalogo: Catalogo, guias: IndiceGuias) -> MCPServer:
    servidor = MCPServer(
        "servidor_conocimiento",
        instructions="Catálogo de criterios para revisar historias de usuario y guías de apoyo. Solo lectura.",
    )
    sistemas = ", ".join(catalogo.sistemas_validos)
    categorias = ", ".join(catalogo.categorias)

    @servidor.tool(
        structured_output=False,
        description=(
            "Lista los criterios ACTIVOS que aplican a una HU según su sistema: los generales más los "
            "propios del sistema. Úsala después de leer la HU (leer_historia te da el 'sistema') para saber "
            "qué criterios evaluar; devuelve solo id, nombre y severidad. Para cómo verificar cada uno, "
            f"usa obtener_criterio. Sistemas válidos: {sistemas}. Categorías: {categorias}."
        ),
    )
    def listar_criterios(
        sistema: Annotated[str, Field(description=f"Sistema de la HU, tal como lo devuelve leer_historia. Uno de: {sistemas}.")],
        categoria: Annotated[
            str | None,
            Field(description=f"Opcional: filtra por categoría ({categorias}). Usa null para todas."),
        ] = None,
    ) -> str:
        errores = []
        if sistema not in catalogo.sistemas_validos:
            errores.append(f"sistema: '{sistema}' no existe en el catálogo; usa uno de: {sistemas}.")
        if categoria is not None and categoria not in catalogo.categorias:
            errores.append(f"categoria: '{categoria}' no existe en el catálogo; usa una de: {categorias}, o null.")
        if errores:
            raise rechazo("listar_criterios", errores)
        criterios = catalogo.aplicables(sistema, categoria)
        return _json({
            "version_catalogo": catalogo.version,
            "sistema": sistema,
            "categoria": categoria,
            "total": len(criterios),
            "criterios": [c.resumen() for c in criterios],
            "siguiente_paso": "Evalúa cada criterio; usa obtener_criterio(id) para ver cómo verificarlo.",
        })

    @servidor.tool(
        structured_output=False,
        description=(
            "Devuelve el detalle de un criterio: descripción, cómo verificarlo, un ejemplo que cumple y uno "
            "que no, severidad y a qué sistemas aplica. Úsala para cada criterio que vayas a evaluar, con el "
            "id que obtuviste de listar_criterios. Si el criterio está obsoleto, te dice cuál lo reemplaza."
        ),
    )
    def obtener_criterio(
        id: Annotated[str, Field(description="Id exacto del criterio, por ejemplo el que devolvió listar_criterios.")],
    ) -> str:
        if not id.strip() or len(id) > 20:
            raise ToolError("id: debe tener entre 1 y 20 caracteres.")
        criterio = catalogo.obtener(id)
        if criterio is None:
            sugerencias = catalogo.sugerir(id)
            pista = f" ¿Quisiste decir: {', '.join(sugerencias)}?" if sugerencias else ""
            raise ToolError(
                f"No existe el criterio '{id}'.{pista} Usa listar_criterios(sistema) para ver los ids válidos; no los inventes."
            )
        respuesta = {"version_catalogo": catalogo.version, "criterio": criterio.detalle()}
        if not criterio.activo:
            vigente = catalogo.vigente(id)
            respuesta["aviso"] = (
                f"El criterio {id} está OBSOLETO y no debe reportarse como defecto. Usa {vigente.id} en su lugar."
            )
            respuesta["vigente"] = vigente.detalle()
        return _json(respuesta)

    @servidor.tool(
        structured_output=False,
        description=(
            "Busca en las guías del equipo (marcos QUS e INVEST, guía de banca móvil y DoR en borrador) las "
            "secciones más relacionadas con un texto. Úsala cuando tengas una duda de interpretación sobre un "
            "criterio o un caso borde; no reemplaza a listar_criterios. 'limite' entre 1 y 5."
        ),
    )
    def buscar_guia(
        texto: Annotated[str, Field(description="Duda o tema a buscar, por ejemplo 'cuándo dividir una historia'.")],
        limite: Annotated[int, Field(description="Cuántas secciones devolver, entre 1 y 5.")],
    ) -> str:
        errores = errores_busqueda(texto, limite, LIMITE_GUIA, max_texto=1000)
        if errores:
            raise rechazo("buscar_guia", errores)
        resultados = guias.buscar(texto, limite)
        return _json({
            "resultados": [
                {"fuente": s.fuente, "seccion": s.titulo, "similitud": sim, "texto": s.texto[:MAX_TEXTO_SECCION]}
                for s, sim in resultados
            ],
            "nota": "Sin secciones relacionadas." if not resultados else
                    "Las guías explican; los criterios válidos son solo los del catálogo.",
        })

    endurecer_esquemas(servidor)
    return servidor


def construir(argv: list[str] | None = None) -> MCPServer:
    from revisor.conocimiento.catalogo import RUTA_POR_DEFECTO, cargar_catalogo

    ap = argparse.ArgumentParser(description="Servidor MCP de conocimiento (stdio)")
    ap.add_argument("--catalogo", default=str(RUTA_POR_DEFECTO), help="catálogo de criterios (YAML)")
    ap.add_argument("--guias", default="conocimiento", help="carpeta con las guías .md")
    args = ap.parse_args(argv)
    return crear_servidor(cargar_catalogo(args.catalogo), IndiceGuias(args.guias))


def main(argv: list[str] | None = None) -> int:
    from revisor.conocimiento.catalogo import CatalogoInvalido

    try:
        servidor = construir(argv)
    except (CatalogoInvalido, FileNotFoundError) as e:
        print(f"servidor_conocimiento no arranca: {e}", file=sys.stderr)
        return 2
    servidor.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
