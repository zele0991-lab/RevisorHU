# Bitácora de uso de IA

El curso exige declarar para qué se usó IA y cómo se verificó el resultado. No declararlo
cuenta como falta de integridad académica. Cada fase agrega al menos una entrada.

| Fecha | Fase | Herramienta y modelo | Qué hizo | Cómo se verificó | Revisó |
|---|---|---|---|---|---|
| 2026-11-09 | F0 · Andamiaje | Claude Code (Claude Opus 5.5) | Leyó el enunciado, la propuesta H1 y el kit de la clase 3. Propuso un plan que fue aprobado. Detectó tres diferencias entre el prompt y la propuesta y las consultó (D-011, D-012, D-013). Creó la estructura de carpetas, `pyproject.toml`, `.gitignore`, `.gitattributes`, `.env.example`, `CLAUDE.md`, `.kiro/steering/*`, `.mcp.json`, `.kiro/settings/mcp.json`, el puerto de backlog (solo la interfaz), los documentos de `docs/` y `tests/test_andamiaje.py`. | `pytest` en verde (pruebas de importación, del contrato del puerto, de la configuración MCP, de `.env.example` y de `.gitignore`). `git status` confirma que no se versionan `.venv` ni `.env`. Revisión manual del plan antes de ejecutarlo. | Leonardo Zeledón (plan aprobado; resultado pendiente de visto bueno) |

## Reglas para las entradas
- Nombrar la herramienta **y** el modelo (por ejemplo, Claude Code con Claude Opus 5.5, o Kiro).
- Decir qué produjo la IA y qué hizo o corrigió una persona.
- La verificación tiene que ser concreta: qué pruebas, qué revisión manual, qué comparación.
- Las etiquetas del conjunto de evaluación **nunca** las produce una IA.
- Toda referencia bibliográfica sugerida por una IA se abre y se lee antes de citarla.
