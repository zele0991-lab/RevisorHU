# Bitácora de uso de IA

El curso exige declarar para qué se usó IA y cómo se verificó el resultado. No declararlo
cuenta como falta de integridad académica. Cada fase agrega al menos una entrada.

| Fecha | Fase | Herramienta y modelo | Qué hizo | Cómo se verificó | Revisó |
|---|---|---|---|---|---|
| 2026-11-09 | F0 · Andamiaje | Claude Code (Claude Opus 5.5) | Leyó el enunciado, la propuesta H1 y el kit de la clase 3. Propuso un plan que fue aprobado. Detectó tres diferencias entre el prompt y la propuesta y las consultó (D-011, D-012, D-013). Creó la estructura de carpetas, `pyproject.toml`, `.gitignore`, `.gitattributes`, `.env.example`, `CLAUDE.md`, `.kiro/steering/*`, `.mcp.json`, `.kiro/settings/mcp.json`, el puerto de backlog (solo la interfaz), los documentos de `docs/` y `tests/test_andamiaje.py`. | `pytest` en verde (pruebas de importación, del contrato del puerto, de la configuración MCP, de `.env.example` y de `.gitignore`). `git status` confirma que no se versionan `.venv` ni `.env`. Revisión manual del plan antes de ejecutarlo. | Leonardo Zeledón (aprobado) |
| 2026-11-09 | F1 · Backlog | Claude Code (Claude Opus 5.5) | Revisó la API instalada de `mcp` 2.3.0 con scripts de prueba antes de escribir código: FastMCP pasó a llamarse `MCPServer` y el SDK aceptaba argumentos desconocidos sin avisar, lo que se corrigió con `endurecer_esquemas`. Consultó dos decisiones (D-015 y D-016). Implementó `BacklogLocal`, la búsqueda TF-IDF, `servidor_backlog` con sus 5 herramientas y validación (`validacion.py`), un backlog de ejemplo sintético y las pruebas. | 116 pruebas de `pytest` en verde y sin red, con una prueba por cada rechazo del servidor, usando el protocolo MCP real con un cliente en memoria. Prueba manual del transporte stdio en Windows, incluida la codificación UTF-8. Las pruebas detectaron dos fallos del detector de datos personales (tarjeta y +506 tomados por teléfono o cuenta), que se corrigieron. | Leonardo Zeledón (pendiente de visto bueno) |

## Reglas para las entradas
- Nombrar la herramienta **y** el modelo (por ejemplo, Claude Code con Claude Opus 5.5, o Kiro).
- Decir qué produjo la IA y qué hizo o corrigió una persona.
- La verificación tiene que ser concreta: qué pruebas, qué revisión manual, qué comparación.
- Las etiquetas del conjunto de evaluación **nunca** las produce una IA.
- Toda referencia bibliográfica sugerida por una IA se abre y se lee antes de citarla.
