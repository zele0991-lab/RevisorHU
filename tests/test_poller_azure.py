"""
Pruebas del poller de Azure DevOps, sin red y sin modelo.

El backlog es un falso en memoria y `revisar` es un stub: así se prueba la lógica del ciclo
(idempotencia, cupo, reintento único, registro atómico) sin Azure DevOps ni la API de Anthropic.
La CLI se prueba con `ejecutar` y el adaptador reemplazados.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import pytest

from revisor.agente.bucle import Resultado
from revisor.backlog.puerto import Historia
from revisor.integracion import poller_azure
from revisor.integracion.poller_azure import AprobadorDesatendido, RegistroProcesados, ciclo

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def bloquear_urlopen(monkeypatch):
    def _no_permitido(*args, **kwargs):
        raise AssertionError("Las pruebas del poller no deben usar la red.")

    monkeypatch.setattr(urllib.request, "urlopen", _no_permitido)


def _h(id: str) -> Historia:
    return Historia(id=id, texto="Como cliente, quiero algo, para algo.", sistema="banca_movil",
                    proyecto="RevisorHU-Pruebas", titulo=f"HU {id}")


class BacklogFalso:
    def __init__(self, ids: list[str]):
        self.historias = [_h(i) for i in ids]
        self.limites_pedidos: list[int] = []

    def listar_pendientes(self, limite: int) -> list[Historia]:
        self.limites_pedidos.append(limite)
        return self.historias[:limite]


def _resultado(id: str, *, decision: str | None = "devolver", motivo: str = "end_turn") -> Resultado:
    return Resultado(run_id=f"run_{id}", ruta_traza=Path(f"trazas/azure/run_{id}.jsonl"), motivo_cierre=motivo,
                     pasos=5, decision=decision, tokens={"totales": 0}, duracion_s=0.1,
                     modelo_respondio=["simulado"], contaminada=False)


def _sin_salida(_texto: str) -> None:
    pass


# ============================================================ Propiedad 12: aprobador

@pytest.mark.parametrize("nombre, lista, aprobada", [
    ("backlog__registrar_revision", ["backlog__registrar_revision"], True),
    ("backlog__proponer_division", ["backlog__registrar_revision", "backlog__proponer_division"], True),
    ("backlog__leer_historia", ["backlog__registrar_revision"], False),
    ("backlog__aprobar_para_fabrica", ["backlog__registrar_revision"], False),
    ("backlog__aprobar_para_fabrica", ["backlog__aprobar_para_fabrica"], False),  # configuración errónea
])
def test_aprobador_desatendido(nombre, lista, aprobada):
    ok, razon = AprobadorDesatendido(lista)(nombre, {"id": "10"})
    assert ok is aprobada
    if ok:
        assert razon == "aprobada por la lista desatendida (config/azure_devops.json)"


@pytest.mark.parametrize("id_pedido, aprobada", [("10", True), (" 10 ", True), ("3", False), ("", False)])
def test_aprobador_solo_escribe_en_el_caso_revisado(id_pedido, aprobada):
    """Una inyección no puede hacer que el agente comente o etiquete otra HU."""
    aprobador = AprobadorDesatendido(["backlog__registrar_revision"], caso="10")
    ok, razon = aprobador("backlog__registrar_revision", {"id": id_pedido})
    assert ok is aprobada
    if not ok:
        assert "work item 10" in razon


def test_aprobador_usa_la_lista_real_de_la_configuracion():
    config = json.loads((RAIZ / "config" / "azure_devops.json").read_text(encoding="utf-8"))
    aprobador = AprobadorDesatendido(config["escrituras_desatendidas"])
    assert aprobador("backlog__registrar_revision", {})[0]
    assert not aprobador("backlog__aprobar_para_fabrica", {})[0]


# ============================================================ Propiedad 11: idempotencia

@pytest.mark.parametrize("valor_previo, se_revisa", [
    ("run_anterior", False),                                   # completada
    ({"fallido": True, "motivo": "x"}, False),                 # fallida dos veces
    ({"fallos": 1, "motivo": "x"}, True),                      # primer fallo: se reintenta
    (None, True),                                              # nueva
])
def test_idempotencia_segun_registro(tmp_path, valor_previo, se_revisa):
    registro = RegistroProcesados(tmp_path / "procesados.json")
    if valor_previo is not None:
        registro.datos["10"] = valor_previo
    revisadas: list[str] = []
    ciclo(BacklogFalso(["10"]), registro, 3, lambda h: revisadas.append(h.id) or _resultado(h.id), _sin_salida)
    assert (revisadas == ["10"]) is se_revisa


def test_respeta_max_hu_por_ciclo(tmp_path):
    revisadas: list[str] = []
    ciclo(BacklogFalso(["1", "2", "3", "4", "5"]), RegistroProcesados(tmp_path / "p.json"), 2,
          lambda h: revisadas.append(h.id) or _resultado(h.id), _sin_salida)
    assert revisadas == ["1", "2"]


def test_las_omitidas_no_ocupan_el_cupo(tmp_path):
    registro = RegistroProcesados(tmp_path / "p.json")
    registro.datos.update({"1": "run_1", "2": {"fallido": True, "motivo": "x"}})
    backlog = BacklogFalso(["1", "2", "3", "4"])
    revisadas: list[str] = []
    ciclo(backlog, registro, 2, lambda h: revisadas.append(h.id) or _resultado(h.id), _sin_salida)
    assert revisadas == ["3", "4"]
    assert backlog.limites_pedidos == [4]


def test_registro_exito_primer_fallo_y_segundo_fallo(tmp_path):
    ruta = tmp_path / "estado" / "procesados.json"
    registro = RegistroProcesados(ruta)
    ciclo(BacklogFalso(["1"]), registro, 3, lambda h: _resultado(h.id), _sin_salida)
    ciclo(BacklogFalso(["2"]), registro, 3, lambda h: _resultado(h.id, decision=None), _sin_salida)
    assert json.loads(ruta.read_text(encoding="utf-8"))["2"]["fallos"] == 1

    def explota(h):
        raise RuntimeError("se cayó el servidor MCP")

    ciclo(BacklogFalso(["2"]), registro, 3, explota, _sin_salida)
    guardado = json.loads(ruta.read_text(encoding="utf-8"))
    assert guardado["1"] == "run_1"
    assert guardado["2"]["fallido"] is True and "se cayó" in guardado["2"]["motivo"]
    assert not list(ruta.parent.glob("*.tmp"))       # escritura atómica: no quedan temporales
    # Tercer ciclo: la fallida definitiva ya no se intenta.
    revisadas: list[str] = []
    ciclo(BacklogFalso(["2"]), RegistroProcesados(ruta), 3, lambda h: revisadas.append(h.id) or _resultado(h.id),
          _sin_salida)
    assert revisadas == []


def test_motivo_distinto_de_end_turn_es_fallo(tmp_path):
    registro = RegistroProcesados(tmp_path / "p.json")
    res = ciclo(BacklogFalso(["7"]), registro, 3, lambda h: _resultado(h.id, motivo="limite_pasos"), _sin_salida)
    assert res == [("7", "fallo")]
    assert registro.datos["7"]["fallos"] == 1


def test_un_fallo_no_detiene_a_las_demas(tmp_path):
    def revisar(h):
        if h.id == "1":
            raise RuntimeError("falla")
        return _resultado(h.id)

    res = ciclo(BacklogFalso(["1", "2"]), RegistroProcesados(tmp_path / "p.json"), 3, revisar, _sin_salida)
    assert res == [("1", "fallo"), ("2", "completada")]


def test_registro_danado_da_error_claro(tmp_path):
    ruta = tmp_path / "p.json"
    ruta.write_text("{roto", encoding="utf-8")
    with pytest.raises(Exception, match="dañado"):
        RegistroProcesados(ruta)


# ============================================================ CLI

@pytest.fixture
def cli(monkeypatch, tmp_path):
    """Arranca la CLI con el adaptador y `ejecutar` reemplazados; devuelve las opciones recibidas."""
    config_azure = json.loads((RAIZ / "config" / "azure_devops.json").read_text(encoding="utf-8"))
    config_azure["poller"]["registro_procesados"] = str(tmp_path / "procesados.json")
    ruta_config = tmp_path / "azure_devops.json"
    ruta_config.write_text(json.dumps(config_azure), encoding="utf-8")

    backlog = BacklogFalso(["10", "11", "12", "13"])
    from revisor.backlog import azure_devops

    monkeypatch.setattr(azure_devops.BacklogAzureDevOps, "desde_configuracion",
                        classmethod(lambda cls, ruta, marca=None: backlog))
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
    recibidas: list = []

    async def ejecutar_falso(op):
        recibidas.append(op)
        return _resultado(op.caso)

    monkeypatch.setattr(poller_azure, "ejecutar", ejecutar_falso)
    monkeypatch.chdir(RAIZ)

    def correr(*extra: str) -> int:
        return poller_azure.main(["--una-vez", "--config-azure", str(ruta_config), *extra])

    correr.ruta_config = ruta_config
    return correr, recibidas


def test_cli_por_defecto_simulado_y_un_ciclo(cli, monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    correr, recibidas = cli
    assert correr() == 0
    assert [op.caso for op in recibidas] == ["10", "11", "12"]          # max_hu_por_ciclo = 3
    assert all(op.simulado for op in recibidas)
    assert all(op.config == "skill" for op in recibidas)
    assert all(op.archivo_config == Path("config/config_azure.json") for op in recibidas)
    assert all(isinstance(op.aprobador, AprobadorDesatendido) for op in recibidas)
    assert recibidas[0].aprobador("backlog__registrar_revision", {"id": "10"})[0]
    assert not recibidas[0].aprobador("backlog__registrar_revision", {"id": "11"})[0]
    assert "MODO SIMULADO" in capsys.readouterr().out


def test_cli_real_sin_clave_no_arranca(cli, monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    correr, recibidas = cli
    assert correr("--real") == 2
    assert recibidas == []
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err


def test_cli_real_avisa_costo_antes_y_respeta_max_hu(cli, monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "clave-falsa-de-prueba")
    correr, recibidas = cli
    assert correr("--real", "--max-hu", "1") == 0
    salida = capsys.readouterr().out
    assert "MODO REAL" in salida and "0,15–0,25" in salida and "hasta 1 HU" in salida
    assert salida.index("MODO REAL") < salida.index("Work item 10")
    assert [op.caso for op in recibidas] == ["10"] and not recibidas[0].simulado
    assert "clave-falsa-de-prueba" not in salida


def test_cli_max_hu_invalido(cli):
    correr, _ = cli
    assert correr("--max-hu", "0") == 2


def test_cli_intervalo_en_segundos_para_la_demo(cli, monkeypatch, capsys):
    """Sin --una-vez el poller repite ciclos; --intervalo-segundos acorta la espera."""
    correr, recibidas = cli
    esperas: list[float] = []

    def dormir(segundos):
        esperas.append(segundos)
        if len(esperas) == 2:
            raise KeyboardInterrupt  # Ctrl+C en la segunda espera

    codigo = poller_azure.main(["--intervalo-segundos", "20", "--config-azure", str(correr.ruta_config)],
                               dormir=dormir)
    assert codigo == 0
    assert esperas == [20.0, 20.0]
    assert "Próximo ciclo en 20 s" in capsys.readouterr().out
    # Primer ciclo: 10, 11, 12. Segundo ciclo: queda la 13 (las demás ya están en el registro).
    assert [op.caso for op in recibidas] == ["10", "11", "12", "13"]


def test_cli_intervalo_menor_a_10_no_arranca(cli):
    correr, _ = cli
    assert correr("--intervalo-segundos", "5") == 2
