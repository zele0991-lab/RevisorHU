"""
Pruebas de la F0: comprueban que el andamiaje cumple lo que otras fases y Kiro dan por hecho.

No usan la red. Si alguna falla, es porque se rompió un contrato del proyecto
(el puerto de backlog, la configuración MCP compartida o la protección de secretos).
"""

import inspect
import json
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]


def test_el_paquete_se_importa():
    import revisor

    assert revisor.__version__


def test_el_puerto_es_abstracto_y_tiene_el_contrato_completo():
    """Kiro implementa BacklogAzureDevOps contra esta interfaz: no puede cambiar en silencio."""
    from revisor.backlog import PuertoBacklog

    with pytest.raises(TypeError):
        PuertoBacklog()  # type: ignore[abstract]

    esperados = {
        "leer_historia",
        "buscar_similares",
        "registrar_revision",
        "proponer_division",
        "aprobar_para_fabrica",
        "listar_pendientes",
    }
    assert set(PuertoBacklog.__abstractmethods__) == esperados


def test_la_historia_exige_sistema():
    """Sin sistema no se sabe qué criterios del catálogo aplican."""
    from revisor.backlog import Historia

    parametros = inspect.signature(Historia).parameters
    assert "sistema" in parametros
    assert parametros["sistema"].default is inspect.Parameter.empty


def test_operacion_prohibida_es_un_error_del_backlog():
    from revisor.backlog import ErrorBacklog, OperacionProhibida

    assert issubclass(OperacionProhibida, ErrorBacklog)


@pytest.mark.parametrize("ruta", [".mcp.json", ".kiro/settings/mcp.json"])
def test_configuracion_mcp_tiene_los_tres_servidores(ruta):
    datos = json.loads((RAIZ / ruta).read_text(encoding="utf-8"))
    assert set(datos["mcpServers"]) == {"backlog", "conocimiento", "estimacion"}


def test_claude_code_y_kiro_usan_los_mismos_servidores():
    """Los dos IDE prueban los mismos servidores: si difieren, las pruebas a mano no son comparables."""
    claude = json.loads((RAIZ / ".mcp.json").read_text(encoding="utf-8"))
    kiro = json.loads((RAIZ / ".kiro/settings/mcp.json").read_text(encoding="utf-8"))
    assert claude["mcpServers"] == kiro["mcpServers"]


def test_env_example_tiene_las_claves_y_ningun_valor():
    """La plantilla se versiona: un valor aquí sería un secreto publicado."""
    claves = {}
    for linea in (RAIZ / ".env.example").read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#"):
            nombre, _, valor = linea.partition("=")
            claves[nombre.strip()] = valor.strip()

    assert set(claves) == {"ANTHROPIC_API_KEY", "AZDO_ORG_URL", "AZDO_PROJECT", "AZDO_PAT"}
    assert all(valor == "" for valor in claves.values())


def test_gitignore_protege_secretos_datos_crudos_y_entorno():
    lineas = {l.strip() for l in (RAIZ / ".gitignore").read_text(encoding="utf-8").splitlines()}
    assert {".env", "datos/crudos/", ".venv/"} <= lineas


def test_la_propuesta_esta_copiada_como_contrato():
    assert "Propuesta de proyecto" in (RAIZ / "docs/propuesta.md").read_text(encoding="utf-8")
