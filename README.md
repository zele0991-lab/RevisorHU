# RevisorHU — Agente revisor de historias de usuario

Proyecto final de la Maestría en IA (curso IA Distribuida, CENFOTEC).

El agente recibe una historia de usuario (HU) y hace lo siguiente:
- la **clasifica** por tipo;
- **busca** duplicados, conflictos e historias de referencia;
- la **estima** en story points (Fibonacci);
- la **refina** (redacción y criterios en Gherkin);
- **recomienda** una de tres decisiones: `aceptar`, `devolver` (con recomendaciones accionables) o `dividir`.

**El agente nunca aprueba.** La aprobación para la fábrica de software la da una persona.

**Pregunta de investigación:** ¿mejora una Skill procedimental basada en la *Definition of Ready* la exactitud de la decisión frente a instrucciones genéricas, y a qué costo en tokens? El detalle está en [docs/propuesta.md](docs/propuesta.md).

## Estado por fases

| Fase | Contenido | Estado |
|---|---|---|
| F0 | Andamiaje: estructura, reglas, documentación, puerto de backlog | ✅ |
| F1 | Backlog: `BacklogLocal` y `servidor_backlog` con su validación | ✅ |
| F2 | Catálogo de criterios, `servidor_conocimiento` y `servidor_estimacion` | pendiente |
| F3 | Agente: bucle con el SDK, política, trazas, modo simulado y CLI `revisar` | pendiente |
| F4 | `SKILL.md` y línea base | pendiente |
| F5 | Conjunto de evaluación, ataques, etiquetado y kappa | pendiente |
| F6 | Experimento, métricas y comando de reproducción | pendiente |
| F7 | Conector de Azure DevOps y poller (Kiro) | pendiente |

## Instalación (Windows, PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
copy .env.example .env    # completa ANTHROPIC_API_KEY solo si vas a usar el modelo real
```

Requisitos: Python 3.11 o superior y git.

## Pruebas

```powershell
python -m pytest
```

Las pruebas no usan la red ni la API.

## Estructura

```
config/          configuración del agente, política e instrucciones de la línea base
conocimiento/    criterios.yaml (única fuente de reglas) y guías para personas
skills/          SKILL.md del revisor
src/revisor/     paquete Python: backlog (puerto y adaptadores), conocimiento, servidores MCP, agente, integración
datos/           scripts de descarga, construcción de casos y etiquetado; conjuntos de evaluación y ataques
experimentos/    ejecución, métricas y acuerdo entre anotadores
trazas/          una traza JSONL por ejecución (se versionan)
resultados/      tablas regeneradas desde las trazas
docs/            propuesta, arquitectura, decisiones y bitácora de uso de IA
```

## Servidores MCP en Claude Code y Kiro

Los tres servidores (`backlog`, `conocimiento` y `estimacion`) están registrados en `.mcp.json` (Claude Code) y en `.kiro/settings/mcp.json` (Kiro). Los dos usan el intérprete de `.venv`.

> `servidor_backlog` está implementado (F1), pero solo arranca cuando exista el catálogo de criterios (F2): sin catálogo no hay lista de defectos válidos y, por diseño, el servidor no arranca con reglas a medias. `servidor_conocimiento` y `servidor_estimacion` llegan en F2.

## Documentación
- [docs/propuesta.md](docs/propuesta.md): propuesta aprobada (H1). Es el contrato del proyecto.
- [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md): diagrama y responsabilidades.
- [docs/DECISIONES.md](docs/DECISIONES.md): registro de decisiones.
- [docs/USO_IA.md](docs/USO_IA.md): bitácora de uso de IA.
- [CLAUDE.md](CLAUDE.md) y [.kiro/steering/](.kiro/steering/): reglas del proyecto para Claude Code y Kiro.

## Datos y seguridad
- Ninguna HU real del banco entra a este repositorio ni se envía a la API.
- Los secretos van en `.env`, que no se versiona.
- `datos/crudos/` no se versiona; las licencias se documentan en `datos/LICENCIAS.md` (F5).
