---
inclusion: always
---

# Tecnología — RevisorHU

> Mismas reglas que `CLAUDE.md`. Si cambias una regla aquí, cámbiala también allí.

## Stack
- Python 3.11+, `pyproject.toml`, `.venv` con `pip`. Pruebas con `pytest`. **Las pruebas no usan la red** (respuestas HTTP simuladas o grabadas).
- SDK `anthropic` con un **bucle manual** de tool use (no el Tool Runner): la política y la traza se aplican en cada llamada. No adivines firmas: consulta la documentación oficial.
- Modelo en `config/config.json` (`claude-opus-5-5` por defecto). Pensamiento adaptativo y `effort` explícito, iguales en las dos configuraciones. Caché de prompts para el sistema y las herramientas. Sin `temperature` y sin `tool_choice` forzado (`auto`). `strict: true` en las herramientas. `fallbacks: "default"`, registrando el **modelo que respondió**; una ejecución que respondió otro modelo se marca y se repite.
- Modo simulado (guion JSON) para correr sin clave y en las pruebas.
- MCP: SDK oficial `mcp` (FastMCP en los servidores, cliente por stdio). Herramientas con descripción de **cuándo** usarlas, esquema estricto (`additionalProperties: false`) y rechazos que dicen qué corregir.

## Política, límites y trazas
- `config/politica.json`: ocultar > denegar > confirmar > permitir > por defecto. Cada regla se justifica en `_cambios`.
- Lecturas: permitir. `registrar_revision` y `proponer_division`: confirmar con Azure DevOps y permitir con el backlog local (documentado). `aprobar_para_fabrica`: ocultar. Topes: 1 llamada por ejecución a cada escritura. Como máximo 15 pasos y un presupuesto de tokens configurable.
- Una traza JSONL por ejecución, compatible con el `leer_traza.py` del kit, con los eventos `inicio` (run_id, config, repetición, caso, modelo, effort, hashes de SKILL.md, criterios.yaml y datos, commit) y `fin` (decisión, modelo real, tokens, duración, motivo).
- Los resultados de herramientas se envuelven como datos no confiables en **las dos** configuraciones.

## Azure DevOps
- Integración por **polling** con una consulta WIQL cada N minutos sobre las HU sin la etiqueta `ia-revisada`. Sin webhooks, para no necesitar una URL pública.
- Verifica en la documentación oficial vigente los endpoints y la `api-version` antes de escribir código.

## Secretos
- Nunca escribas claves en código, trazas ni logs; el PAT se enmascara. Los secretos van en `.env`, que no se versiona (plantilla: `.env.example`).
- **No hagas llamadas pagadas a la API** sin avisar antes del costo estimado.

## Forma de trabajo
- Código y docstrings en español, legibles; los docstrings explican **por qué**.
- Cada fase termina con pruebas en verde, un commit con mensaje claro y una entrada en `docs/USO_IA.md` que dice qué hizo la herramienta de IA y cómo se verificó.
- Si algo no está claro, pregunta; no lo inventes. Si hay conflicto con la propuesta o la rúbrica, detente y avisa.
