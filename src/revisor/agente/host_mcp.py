"""
Host MCP: arranca los servidores por stdio, descubre sus herramientas y las llama.

Por qué un proceso de servidor por ejecución:
    El estado "una revisión por HU y ejecución" vive en el proceso del servidor, y el
    borrador se marca con el run_id. Así cada ejecución empieza limpia y es independiente de
    la anterior, que es lo que exige repetir cada configuración 3 veces.

Por qué el entorno de los servidores NO hereda el del host:
    `StdioServerParameters(env=None)` les da solo un entorno mínimo seguro del SDK. La clave
    de la API nunca llega a un servidor que no la necesita.
"""

from __future__ import annotations

import sys
from contextlib import AsyncExitStack
from pathlib import Path
from typing import TextIO

from mcp import ClientSession, StdioServerParameters, stdio_client

SEPARADOR = "__"  # servidor__herramienta, como el kit: evita choques de nombres


class ErrorHost(Exception):
    pass


def expandir_comando(comando: list[str], valores: dict[str, str | list[str]]) -> list[str]:
    """
    Reemplaza marcadores como {run_id} o {catalogo}. Un argumento que es EXACTAMENTE un
    marcador de lista (por ejemplo {historias}) se expande en varios argumentos.
    "python" se reemplaza por el intérprete actual, para usar siempre el del entorno virtual.
    """
    salida: list[str] = []
    for i, arg in enumerate(comando):
        if i == 0 and arg == "python":
            salida.append(sys.executable)
            continue
        clave = arg[1:-1] if arg.startswith("{") and arg.endswith("}") else None
        if clave in valores and isinstance(valores[clave], list):
            salida.extend(str(v) for v in valores[clave])
            continue
        for k, v in valores.items():
            if not isinstance(v, list):
                arg = arg.replace("{" + k + "}", str(v))
        salida.append(arg)
    return salida


class HostMCP:
    def __init__(self, servidores: list[dict], valores: dict, raiz: Path, errlog: TextIO):
        self._servidores = servidores
        self._valores = valores
        self._raiz = raiz
        self._errlog = errlog
        self._pila = AsyncExitStack()
        self.sesiones: dict[str, ClientSession] = {}
        self.herramientas: list[dict] = []  # {name, description, input_schema}

    async def __aenter__(self) -> "HostMCP":
        try:
            for srv in self._servidores:
                comando = expandir_comando(srv["comando"], self._valores)
                params = StdioServerParameters(command=comando[0], args=comando[1:], cwd=str(self._raiz))
                lectura, escritura = await self._pila.enter_async_context(stdio_client(params, errlog=self._errlog))
                sesion = await self._pila.enter_async_context(ClientSession(lectura, escritura))
                await sesion.initialize()
                self.sesiones[srv["nombre"]] = sesion
                for h in (await sesion.list_tools()).tools:
                    self.herramientas.append({
                        "name": f"{srv['nombre']}{SEPARADOR}{h.name}",
                        "description": h.description or "",
                        "input_schema": h.input_schema,
                    })
        except Exception as e:
            await self._pila.aclose()
            raise ErrorHost(f"no se pudo iniciar el servidor MCP '{srv['nombre']}': {e}. "
                            f"Revisa el registro de servidores.") from e
        return self

    async def __aexit__(self, *exc) -> None:
        await self._pila.aclose()

    async def llamar(self, nombre: str, argumentos: dict) -> tuple[str, bool]:
        """Devuelve (texto, es_error). Un fallo de transporte también vuelve como error legible."""
        servidor, _, herramienta = nombre.partition(SEPARADOR)
        sesion = self.sesiones.get(servidor)
        if sesion is None:
            return f"servidor desconocido: {servidor}", True
        try:
            r = await sesion.call_tool(herramienta, argumentos)
        except Exception as e:  # el modelo debe ver un error, no tumbar la ejecución
            return f"Error al llamar a {nombre}: {e}", True
        texto = "\n".join(c.text for c in r.content if getattr(c, "text", None))
        return texto, bool(r.is_error)
