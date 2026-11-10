"""
Pruebas del modelo real SIN red: un cliente falso captura los parámetros de la solicitud y
devuelve respuestas con la forma del SDK. Verifica lo que el prompt fija para Opus 5.5.
"""

import asyncio
from types import SimpleNamespace as NS

import pytest

from revisor.agente.modelo import BETA_FALLBACK, ModeloClaude, ModeloSimulado

HERRAMIENTAS = [{"name": "backlog__leer_historia", "description": "Lee una HU.",
                 "input_schema": {"type": "object", "properties": {"id": {"type": "string"}},
                                  "required": ["id"], "additionalProperties": False}}]


def _respuesta(modelo="claude-opus-5-5", stop="tool_use", iteraciones=None, stop_details=None):
    return NS(
        model=modelo, stop_reason=stop, stop_details=stop_details,
        content=[NS(type="thinking", thinking="Primero leo la HU."),
                 NS(type="text", text="Voy a leer la historia."),
                 NS(type="tool_use", id="tu_1", name="backlog__leer_historia", input={"id": "HU-001"})],
        usage=NS(input_tokens=120, output_tokens=80, cache_read_input_tokens=3000,
                 cache_creation_input_tokens=500, iterations=iteraciones),
    )


class ClienteFalso:
    def __init__(self, respuesta):
        self.parametros = None
        self._respuesta = respuesta
        self.beta = NS(messages=NS(create=self._crear))

    async def _crear(self, **parametros):
        self.parametros = parametros
        return self._respuesta


def _llamar(respuesta, **kwargs):
    cliente = ClienteFalso(respuesta)
    m = ModeloClaude("claude-opus-5-5", "medium", 16000, cliente=cliente, **kwargs)
    r = asyncio.run(m.responder("SISTEMA", [{"role": "user", "content": "x"}], HERRAMIENTAS))
    return cliente.parametros, r


def test_parametros_de_la_solicitud():
    p, _ = _llamar(_respuesta())
    assert p["model"] == "claude-opus-5-5" and p["max_tokens"] == 16000
    assert p["thinking"] == {"type": "adaptive", "display": "summarized"}
    assert p["output_config"] == {"effort": "medium"}, "effort explícito"
    assert p["tool_choice"] == {"type": "auto"}, "Opus 5.5 rechaza el tool_choice forzado"
    assert "temperature" not in p and "top_p" not in p
    assert all(h["strict"] is True for h in p["tools"])
    assert p["fallbacks"] == "default" and p["betas"] == [BETA_FALLBACK]


def test_cache_en_el_sistema_y_automatica_en_la_conversacion():
    p, _ = _llamar(_respuesta())
    assert p["system"] == [{"type": "text", "text": "SISTEMA", "cache_control": {"type": "ephemeral"}}]
    assert p["cache_control"] == {"type": "ephemeral"}


def test_sin_fallbacks_no_se_envia_la_cabecera_beta():
    p, _ = _llamar(_respuesta(), fallbacks=None)
    assert "fallbacks" not in p and "betas" not in p


def test_normaliza_la_respuesta_y_el_uso():
    _, r = _llamar(_respuesta())
    assert r.stop_reason == "tool_use" and r.modelo == "claude-opus-5-5" and not r.fallback
    assert r.texto == "Voy a leer la historia." and r.pensamiento == "Primero leo la HU."
    assert r.usos_herramienta == [{"id": "tu_1", "name": "backlog__leer_historia", "input": {"id": "HU-001"}}]
    assert r.uso == {"input_tokens": 120, "output_tokens": 80,
                     "cache_read_input_tokens": 3000, "cache_creation_input_tokens": 500}
    assert len(r.contenido) == 3, "los bloques (incluido el pensamiento) se devuelven al historial sin cambios"


def test_detecta_el_fallback_por_las_iteraciones():
    iteraciones = [NS(type="message"), NS(type="fallback_message")]
    _, r = _llamar(_respuesta(modelo="claude-opus-4-8", iteraciones=iteraciones))
    assert r.fallback and r.modelo == "claude-opus-4-8"


def test_un_modelo_distinto_al_pedido_tambien_cuenta_como_fallback():
    _, r = _llamar(_respuesta(modelo="claude-opus-4-8"))
    assert r.fallback


def test_rechazo_con_detalle():
    detalle = NS(category="cyber", explanation="x")
    _, r = _llamar(_respuesta(stop="refusal", stop_details=detalle))
    assert r.stop_reason == "refusal" and r.detalle_rechazo == {"categoria": "cyber", "explicacion": "x"}


def test_sin_clave_no_se_crea_el_cliente_real(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="--simulado"):
        ModeloClaude("claude-opus-5-5", "medium", 16000)


def test_el_simulado_sustituye_el_caso_y_termina(tmp_path):
    guion = tmp_path / "g.json"
    guion.write_text('{"turnos": [{"herramientas": [{"name": "a__b", "input": {"id": "{caso}"}}]}, {"texto": "fin"}]}',
                     encoding="utf-8")
    m = ModeloSimulado(guion, "HU-009")
    r1 = asyncio.run(m.responder("s", [], []))
    r2 = asyncio.run(m.responder("s", [], []))
    r3 = asyncio.run(m.responder("s", [], []))
    assert r1.stop_reason == "tool_use" and r1.usos_herramienta[0]["input"] == {"id": "HU-009"}
    assert r2.stop_reason == r3.stop_reason == "end_turn" and r3.texto == "Guion terminado."
