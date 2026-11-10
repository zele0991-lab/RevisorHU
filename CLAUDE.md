# CLAUDE.md — Reglas del proyecto RevisorHU

> Estas reglas son las mismas que `.kiro/steering/` (product.md, tech.md, structure.md).
> **Si cambias una regla aquí, cámbiala también allí** (y al revés).
> Contrato del proyecto: `docs/propuesta.md`. Si algo la contradice, detente y pregunta.
> Decisiones de fondo: `docs/DECISIONES.md`.

## Producto
- Agente que revisa historias de usuario (HU): **clasifica** el tipo, **busca** duplicados, conflictos y referencias, **estima** en story points (1, 2, 3, 5, 8, 13), **refina** (redacción y criterios en Gherkin) y **recomienda** `aceptar`, `devolver` (con recomendaciones accionables) o `dividir`.
- **El agente nunca aprueba.** La aprobación para la fábrica la da una persona (segregación de funciones). `aprobar_para_fabrica` está oculta al modelo.
- Pregunta de investigación: ¿la Skill (`skills/revisor-hu/SKILL.md`) mejora la exactitud de la decisión frente a un párrafo genérico (`config/instrucciones_base.md`), y a qué costo en tokens? **Solo cambia el prompt de sistema**: el modelo, las herramientas, la política y el `effort` son los mismos.

## Reglas como datos
- `conocimiento/criterios.yaml` es la **única fuente de verdad** de los criterios y de la lista de tipos de HU (por ahora solo `funcional`). Lo carga y valida solo `src/revisor/conocimiento/catalogo.py`. Todo lo demás lo consume de ahí.
- Agregar, cambiar o retirar un criterio = editar el YAML y nada más. **Nunca** escribas ids de criterios (`DOR-001`…) en código Python, en `SKILL.md` ni en la política.
- Los ids nunca se borran ni se reutilizan: un criterio se marca `obsoleto` con `reemplazado_por`.
- Catálogo inválido ⇒ el sistema no arranca, con un mensaje que dice qué criterio y qué campo fallan. Las `categorias`, los `sistemas` y los `tipos_hu` se declaran en la cabecera del YAML; `todos` es reservado.
- Cada HU trae su `sistema`; solo aplican los criterios con `aplica_a` igual a `todos` o a ese sistema.
- `SKILL.md` y `criterios.yaml` se congelan con un tag de git antes de etiquetar y correr el experimento. Un cambio posterior crea una versión nueva y se registra en `docs/DECISIONES.md`.

## Tecnología
- Python 3.11+, `pyproject.toml`, `.venv` con `pip` (no hay `uv`). Pruebas con `pytest`. **Las pruebas no usan la red.**
- SDK `anthropic` con un **bucle manual** de tool use (no el Tool Runner): la política y la traza se aplican en cada llamada. **Antes de escribir código del SDK, consulta la skill `claude-api`.** No adivines firmas.
- Modelo en `config/config.json` (`claude-opus-5-5` por defecto). Pensamiento adaptativo y `effort` explícito, iguales en las dos configuraciones. Caché de prompts para el sistema y las herramientas. Sin `temperature` y sin `tool_choice` forzado (`auto`). `strict: true` en las herramientas. `fallbacks: "default"`, registrando el **modelo que respondió**; una ejecución que respondió otro modelo se marca y se repite.
- Modo simulado (guion JSON) para correr sin clave y en las pruebas.
- MCP: SDK oficial `mcp` 2.x (`MCPServer`, antes llamado FastMCP, en los servidores; cliente por stdio). Después de registrar las herramientas, llama a `endurecer_esquemas` (`src/revisor/servidores/comun.py`): sin eso, el SDK acepta argumentos desconocidos sin avisar. Herramientas con descripción de **cuándo** usarlas, esquema estricto (`additionalProperties: false`) y rechazos que dicen qué corregir.
- El agente ve las herramientas como `servidor__herramienta` (como en el kit), por ejemplo `backlog__leer_historia`; la política usa esos nombres y admite comodines.
- Backlog detrás de un puerto (`src/revisor/backlog/puerto.py`) con adaptadores `BacklogLocal` (experimento) y `BacklogAzureDevOps` (F7). El servidor MCP **valida**; el puerto solo lee y persiste. Un adaptador nuevo no toca el agente, la política, la Skill ni los servidores. Azure DevOps por **polling WIQL**, sin webhooks; ahí el agente solo comenta, etiqueta y sugiere puntos, y **nunca cambia el estado**.

## Política, límites y trazas
- `config/politica.json`: ocultar > denegar > confirmar > permitir > por defecto. Cada regla se justifica en `_cambios`.
- Lecturas: permitir. `registrar_revision` y `proponer_division`: confirmar con Azure DevOps y permitir con el backlog local (documentado). `aprobar_para_fabrica`: ocultar. Topes: 1 llamada por ejecución a cada escritura. Como máximo 15 pasos y un presupuesto de tokens configurable.
- Una traza JSONL por ejecución, compatible con el `leer_traza.py` del kit, con los eventos `inicio` (run_id, config, repetición, caso, modelo, effort, hashes de SKILL.md, criterios.yaml y datos, commit) y `fin` (decisión, modelo real, tokens, duración, motivo).
- Los resultados de herramientas se envuelven como datos no confiables en **las dos** configuraciones.

## Datos y seguridad
- **Ninguna HU real del banco** entra al repositorio ni se envía a la API. Solo HU genéricas (Dalpiaz, TAWOS) y sintéticas.
- Nunca escribas claves en código, trazas ni logs; el PAT se enmascara. Los secretos van en `.env`, que no se versiona.
- `datos/crudos/` no se versiona; las licencias se documentan en `datos/LICENCIAS.md`.
- **Claude no etiqueta casos.** Las etiquetas son de dos personas del equipo. Si te lo piden, niégate y recuérdalo.

## Forma de trabajo
- Una fase por vez (F0…F7, ver `README.md`). Al terminar cada fase: pruebas en verde, commit con mensaje claro y una entrada en `docs/USO_IA.md`. Después, esperar el visto bueno.
- Código y docstrings en español, legibles como el kit; los docstrings explican **por qué**.
- Si algo no está claro, pregunta; no lo inventes. Si hay conflicto con la propuesta o la rúbrica, detente y avisa.
- **No hagas llamadas pagadas a la API** sin avisar antes del costo estimado (tokens y dólares).
