"""
La configuración de Azure DevOps solo puede diferir de la del experimento en lo que exige el
backend. Si alguien cambia el modelo, el effort o los límites en una sola de las dos, el agente
que corre en Azure DevOps dejaría de ser el que se evaluó.
"""

import json
import sys
import types

import pytest

from conftest import BACKLOG_EJEMPLO, RAIZ, llamar

CONFIG = json.loads((RAIZ / "config" / "config.json").read_text(encoding="utf-8"))
AZURE = json.loads((RAIZ / "config" / "config_azure.json").read_text(encoding="utf-8"))
DIFERENCIAS_PERMITIDAS = {"_lectura", "backend", "historias", "carpeta_trazas", "servidores"}


def test_azure_solo_cambia_lo_que_exige_el_backend():
    distintas = {k for k in CONFIG.keys() | AZURE.keys() if CONFIG.get(k) != AZURE.get(k)}
    assert distintas <= DIFERENCIAS_PERMITIDAS, distintas - DIFERENCIAS_PERMITIDAS
    assert AZURE["backend"] == "azure" and AZURE["historias"] == []


def test_los_servidores_de_conocimiento_y_estimacion_son_los_mismos():
    otros = lambda c: [s for s in c["servidores"] if s["nombre"] != "backlog"]
    assert otros(CONFIG) == otros(AZURE)
    backlog = next(s for s in AZURE["servidores"] if s["nombre"] == "backlog")["comando"]
    assert backlog[backlog.index("--backend") + 1] == "azure"


def test_la_configuracion_del_conector_no_tiene_secretos():
    texto = (RAIZ / "config" / "azure_devops.json").read_text(encoding="utf-8").lower()
    for prohibido in ("pat\":", "token", "password", "dev.azure.com/"):
        assert prohibido not in texto, prohibido


def test_las_escrituras_desatendidas_son_solo_borradores():
    """Nunca la aprobación: la lista desatendida no puede incluir la herramienta oculta."""
    datos = json.loads((RAIZ / "config" / "azure_devops.json").read_text(encoding="utf-8"))
    assert set(datos["escrituras_desatendidas"]) <= {"backlog__registrar_revision", "backlog__proponer_division"}


# ===================================================================== selección del adaptador
def test_backend_local_exige_historias(tmp_path):
    from revisor.backlog import ErrorBacklog
    from revisor.servidores.servidor_backlog import construir

    with pytest.raises(ErrorBacklog, match="--historias"):
        construir(["--backend", "local", "--estado", str(tmp_path)])


def test_backend_azure_sin_conector_da_un_mensaje_claro(tmp_path, monkeypatch):
    from revisor.backlog import ErrorBacklog
    from revisor.servidores.servidor_backlog import construir

    monkeypatch.setitem(sys.modules, "revisor.backlog.azure_devops", None)  # simula que no existe
    with pytest.raises((ErrorBacklog, ModuleNotFoundError, ImportError)) as e:
        construir(["--backend", "azure", "--estado", str(tmp_path)])
    if isinstance(e.value, ErrorBacklog):
        assert "F7" in str(e.value)


def test_backend_azure_usa_el_contrato_desde_configuracion(tmp_path, monkeypatch):
    """Contrato con Kiro: BacklogAzureDevOps.desde_configuracion(ruta, marca)."""
    from revisor.backlog.local import BacklogLocal
    from revisor.servidores.servidor_backlog import construir

    recibido = {}

    class BacklogAzureDevOps:
        @classmethod
        def desde_configuracion(cls, ruta, marca):
            recibido.update(ruta=ruta, marca=marca)
            return BacklogLocal([BACKLOG_EJEMPLO], tmp_path, marca=marca)

    falso = types.ModuleType("revisor.backlog.azure_devops")
    falso.BacklogAzureDevOps = BacklogAzureDevOps
    monkeypatch.setitem(sys.modules, "revisor.backlog.azure_devops", falso)
    srv = construir(["--backend", "azure", "--config-azure", "config/azure_devops.json",
                     "--estado", str(tmp_path), "--marca", "run1"])
    assert recibido["ruta"].as_posix() == "config/azure_devops.json" and recibido["marca"] == "run1"
    assert not llamar(srv, "leer_historia", {"id": "HU-001"}).es_error


# ===================================================================== entorno de los servidores
def test_solo_el_backlog_de_azure_recibe_variables_azdo():
    for c in (CONFIG, AZURE):
        for s in c["servidores"]:
            esperado = ["AZDO_ORG_URL", "AZDO_PROJECT", "AZDO_PAT"] if (c is AZURE and s["nombre"] == "backlog") else []
            assert s.get("entorno", []) == esperado, s["nombre"]


def test_entorno_servidor_pasa_solo_lo_pedido_y_nunca_la_clave(monkeypatch):
    from revisor.agente.host_mcp import ErrorHost, entorno_servidor

    monkeypatch.setenv("AZDO_PAT", "pat-de-prueba-123")
    monkeypatch.setenv("AZDO_ORG_URL", "https://ejemplo.invalid/org")
    monkeypatch.delenv("AZDO_PROJECT", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-no-debe-pasar")
    srv = {"nombre": "backlog", "entorno": ["AZDO_ORG_URL", "AZDO_PROJECT", "AZDO_PAT"]}
    assert entorno_servidor(srv) == {"AZDO_ORG_URL": "https://ejemplo.invalid/org", "AZDO_PAT": "pat-de-prueba-123"}
    assert entorno_servidor({"nombre": "conocimiento"}) is None
    with pytest.raises(ErrorHost, match="ANTHROPIC_API_KEY"):
        entorno_servidor({"nombre": "x", "entorno": ["ANTHROPIC_API_KEY"]})
