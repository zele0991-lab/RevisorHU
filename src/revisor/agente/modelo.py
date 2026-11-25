"""
Modelos: el real (SDK `anthropic`) y el simulado (guion JSON, sin clave ni costo).

Los dos devuelven una `Respuesta` normalizada, así el bucle no sabe con cuál habla.

Decisiones del modelo real (verificadas con la skill claude-api y el SDK 2.7 instalado):
    - Endpoint beta `client.beta.messages.create`: lo exige `fallbacks`.
    - `thinking: adaptive` y `output_config.effort` EXPLÍCITO: en Opus 5.5 el pensamiento no
      se puede apagar; el effort es el control, y su valor por defecto (`medium`) no se deja
      implícito para que la traza diga exactamente con qué se corrió.
    - `display: "summarized"`: el pensamiento se factura igual con cualquier `display`; el
      resumen sirve para el análisis de errores del artículo.
    - Sin `temperature` ni `tool_choice` forzado (Opus 5.5 los rechaza): `tool_choice: auto` y
      `strict: true` en cada herramienta.
    - Caché: un punto explícito al final del prompt de sistema (cubre herramientas + sistema,
      que es lo compartido entre casos) y caché automática para la conversación que crece.
    - `fallbacks: "default"` con la cabecera `server-side-fallback-2026-07-01`. El modelo que
      respondió se lee de `response.model` y de `usage.iterations` (`fallback_message`). Una
      ejecución servida por otro modelo se marca y se repite (no contamina el experimento).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

BETA_FALLBACK = "server-side-fallback-2026-07-01"


@dataclass
class Respuesta:
    contenido: list                 # bloques tal cual, para devolverlos al historial sin cambios
    stop_reason: str
    uso: dict
    modelo: str                     # modelo que produjo la respuesta
    fallback: bool = False          # True si la sirvió un modelo de respaldo
    detalle_rechazo: dict | None = None
    texto: str = ""
    pensamiento: str = ""
    usos_herramienta: list[dict] = field(default_factory=list)  # {id, name, input}


def _tipo(bloque) -> str:
    return bloque["type"] if isinstance(bloque, dict) else bloque.type


def _campo(bloque, nombre, defecto=None):
    return bloque.get(nombre, defecto) if isinstance(bloque, dict) else getattr(bloque, nombre, defecto)


def resumir_bloques(contenido: list) -> tuple[str, str, list[dict]]:
    """Separa texto, pensamiento (resúmenes) y llamadas a herramientas, leyendo por `type`."""
    textos, pensamientos, usos = [], [], []
    for b in contenido:
        t = _tipo(b)
        if t == "text" and (_campo(b, "text") or "").strip():
            textos.append(_campo(b, "text").strip())
        elif t == "thinking" and (_campo(b, "thinking") or "").strip():
            pensamientos.append(_campo(b, "thinking").strip())
        elif t == "tool_use":
            usos.append({"id": _campo(b, "id"), "name": _campo(b, "name"), "input": _campo(b, "input") or {}})
    return "\n".join(textos), "\n".join(pensamientos), usos


# ===================================================================== modelo real
class ModeloClaude:
    def __init__(self, modelo: str, effort: str, max_tokens: int, fallbacks: str | None = "default",
                 cliente=None):
        """`cliente` se inyecta en las pruebas (un falso); en uso real se crea el del SDK."""
        if cliente is None:
            import anthropic

            if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
                raise RuntimeError("Falta ANTHROPIC_API_KEY (en .env o en el entorno). Sin clave, usa --simulado.")
            cliente = anthropic.AsyncAnthropic()
        self.cliente = cliente
        self.modelo = modelo
        self.effort = effort
        self.max_tokens = max_tokens
        self.fallbacks = fallbacks

    @staticmethod
    def herramientas_api(catalogo: list[dict]) -> list[dict]:
        """Del catálogo MCP al formato de la API: `strict: true` en todas."""
        return [{"name": h["name"], "description": h["description"], "input_schema": h["input_schema"],
                 "strict": True} for h in catalogo]

    def parametros(self, sistema: str, mensajes: list, herramientas: list[dict]) -> dict:
        params = {
            "model": self.modelo,
            "max_tokens": self.max_tokens,
            "system": [{"type": "text", "text": sistema, "cache_control": {"type": "ephemeral"}}],
            "messages": mensajes,
            "tools": self.herramientas_api(herramientas),
            "tool_choice": {"type": "auto"},
            "thinking": {"type": "adaptive", "display": "summarized"},
            "output_config": {"effort": self.effort},
            "cache_control": {"type": "ephemeral"},
        }
        if self.fallbacks:
            params["fallbacks"] = self.fallbacks
            params["betas"] = [BETA_FALLBACK]
        return params

    async def cerrar(self) -> None:
        """Cierra el cliente del SDK. Sin esto, al terminar asyncio.run aparece 'Event loop is closed'."""
        cerrar = getattr(self.cliente, "close", None)
        if cerrar is not None:
            try:
                await cerrar()
            except Exception:  # cerrar nunca debe hacer fallar una ejecución que ya terminó
                pass

    async def responder(self, sistema: str, mensajes: list, herramientas: list[dict]) -> Respuesta:
        r = await self.cliente.beta.messages.create(**self.parametros(sistema, mensajes, herramientas))
        u = r.usage
        iteraciones = getattr(u, "iterations", None) or []
        fallback = any(getattr(it, "type", None) == "fallback_message" for it in iteraciones)
        texto, pensamiento, usos = resumir_bloques(r.content)
        rechazo = None
        if r.stop_reason == "refusal" and getattr(r, "stop_details", None):
            rechazo = {"categoria": getattr(r.stop_details, "category", None),
                       "explicacion": getattr(r.stop_details, "explanation", None)}
        return Respuesta(
            contenido=list(r.content),
            stop_reason=r.stop_reason,
            uso={
                "input_tokens": u.input_tokens or 0,
                "output_tokens": u.output_tokens or 0,
                "cache_read_input_tokens": u.cache_read_input_tokens or 0,
                "cache_creation_input_tokens": u.cache_creation_input_tokens or 0,
            },
            modelo=r.model,
            fallback=fallback or r.model != self.modelo,
            detalle_rechazo=rechazo,
            texto=texto, pensamiento=pensamiento, usos_herramienta=usos,
        )


# ===================================================================== modelo simulado
class ModeloSimulado:
    """
    Reproduce un guion de turnos con la misma forma de respuesta que la API.

    Sirve para ver el bucle, la política y la traza sin clave ni costo, y para las pruebas.
    No razona: si el guion llama a una herramienta que no existe, se verá el bloqueo.
    El texto "{caso}" en los argumentos se reemplaza por el id de la HU de la ejecución.
    """

    NOMBRE = "simulado"

    def __init__(self, ruta_guion: Path | str, caso: str):
        self.turnos = json.loads(Path(ruta_guion).read_text(encoding="utf-8"))["turnos"]
        self.caso = caso
        self.i = 0

    def _sustituir(self, valor):
        if isinstance(valor, str):
            return valor.replace("{caso}", self.caso)
        if isinstance(valor, dict):
            return {k: self._sustituir(v) for k, v in valor.items()}
        if isinstance(valor, list):
            return [self._sustituir(v) for v in valor]
        return valor

    async def responder(self, sistema: str, mensajes: list, herramientas: list[dict]) -> Respuesta:
        turno = self.turnos[self.i] if self.i < len(self.turnos) else {"texto": "Guion terminado."}
        self.i += 1
        contenido = []
        if turno.get("texto"):
            contenido.append({"type": "text", "text": turno["texto"]})
        for j, h in enumerate(turno.get("herramientas", [])):
            contenido.append({"type": "tool_use", "id": f"sim_{self.i}_{j}", "name": h["name"],
                              "input": self._sustituir(h.get("input", {}))})
        texto, pensamiento, usos = resumir_bloques(contenido)
        entrada = (len(sistema) + len(json.dumps(mensajes, ensure_ascii=False, default=str))) // 4
        return Respuesta(
            contenido=contenido,
            stop_reason="tool_use" if usos else "end_turn",
            uso={"input_tokens": entrada, "output_tokens": 60,
                 "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
            modelo=self.NOMBRE, texto=texto, pensamiento=pensamiento, usos_herramienta=usos,
        )
