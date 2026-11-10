"""
Utilidades comunes de las pruebas. Nada aquí usa la red.

`ReglasFalsas` sustituye al catálogo (que llega en F2). Sus ids (PRB-…) son inventados a
propósito para las pruebas: no son criterios del catálogo real.
"""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

import pytest

from mcp import Client

RAIZ = Path(__file__).resolve().parents[1]
BACKLOG_EJEMPLO = RAIZ / "datos" / "ejemplo" / "backlog_ejemplo.json"


class ReglasFalsas:
    """Fuente de reglas en memoria, editable desde cada prueba."""

    def __init__(self):
        self.tipos = ["funcional"]
        self.por_sistema = {
            "todos": {"PRB-001", "PRB-002", "PRB-003"},
            "banca_movil": {"PRB-BM-001"},
            "core": {"PRB-CORE-001"},
        }

    def tipos_hu(self) -> list[str]:
        return list(self.tipos)

    def ids_defectos_aplicables(self, sistema: str) -> set[str]:
        return self.por_sistema["todos"] | self.por_sistema.get(sistema, set())


@pytest.fixture
def reglas() -> ReglasFalsas:
    return ReglasFalsas()


@pytest.fixture
def backlog(tmp_path):
    from revisor.backlog.local import BacklogLocal

    copia = tmp_path / "backlog.json"
    shutil.copy(BACKLOG_EJEMPLO, copia)
    return BacklogLocal([copia], tmp_path / "estado", marca="prueba")


@pytest.fixture
def servidor(backlog, reglas):
    from revisor.servidores.servidor_backlog import crear_servidor

    return crear_servidor(backlog, reglas)


class Resultado:
    def __init__(self, crudo):
        self.es_error = crudo.is_error
        self.texto = "\n".join(c.text for c in crudo.content if getattr(c, "text", None))

    @property
    def json(self) -> dict:
        return json.loads(self.texto)


def llamar(servidor, herramienta: str, argumentos: dict) -> Resultado:
    """Llama a una herramienta por el protocolo MCP real (cliente en memoria)."""

    async def _llamar():
        async with Client(servidor) as cliente:
            return await cliente.call_tool(herramienta, argumentos)

    return Resultado(asyncio.run(_llamar()))


def listar(servidor) -> list:
    async def _listar():
        async with Client(servidor) as cliente:
            return (await cliente.list_tools()).tools

    return asyncio.run(_listar())
