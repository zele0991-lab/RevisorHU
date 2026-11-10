---
inclusion: always
---

# Estructura — RevisorHU

> Mismas reglas que `CLAUDE.md`. Si cambias una regla aquí, cámbiala también allí.

## Carpetas
| Ruta | Contenido |
|---|---|
| `src/revisor/backlog/` | `puerto.py` (interfaz), `local.py` (`BacklogLocal`), `azure_devops.py` (`BacklogAzureDevOps`, F7) |
| `src/revisor/conocimiento/catalogo.py` | Único módulo que carga y valida `conocimiento/criterios.yaml` |
| `src/revisor/servidores/` | `servidor_backlog`, `servidor_conocimiento`, `servidor_estimacion` (FastMCP) |
| `src/revisor/agente/` | Bucle, política, traza, modelo real y simulado, CLI `revisar` |
| `src/revisor/integracion/` | `poller_azure.py` (F7) |
| `config/` | `config.json`, `politica.json`, `instrucciones_base.md` |
| `conocimiento/` | `criterios.yaml` y explicaciones para personas (`qus.md`, `invest.md`, `banca_movil.md`, `dor_v0.md`) |
| `skills/revisor-hu/SKILL.md` | Procedimiento, reglas, casos borde y criterio de parada |
| `datos/` | Scripts de descarga, construcción de casos y etiquetado; `evaluacion/`, `ataques/`, `etiquetas/`; `crudos/` no se versiona |
| `experimentos/` | `ejecutar.py`, `metricas.py`, `acuerdo.py` |
| `trazas/` | Una traza JSONL por ejecución (se versionan) |
| `resultados/` | Tablas CSV y Markdown regeneradas desde las trazas |
| `docs/` | `propuesta.md` (contrato), `ARQUITECTURA.md`, `DECISIONES.md`, `USO_IA.md` |

## Puerto de backlog
- `src/revisor/backlog/puerto.py` es el **contrato** entre el núcleo y los adaptadores. Las herramientas MCP no saben qué adaptador hay detrás.
- El servidor MCP **valida**; el puerto solo lee y persiste.
- Un adaptador nuevo implementa `PuertoBacklog` **sin tocar** el agente, la política, la Skill ni los servidores.
- En Azure DevOps, `aprobar_para_fabrica` lanza `OperacionProhibida` y nunca se cambia `System.State`.

## Reglas como datos
- `conocimiento/criterios.yaml` es la **única fuente de verdad** de los criterios. Lo carga y valida solo `catalogo.py`; los servidores, la herramienta de etiquetado y las métricas lo consumen de ahí.
- Agregar, cambiar o retirar un criterio = editar el YAML y nada más. **Nunca** escribas ids de criterios en código Python, en `SKILL.md` ni en la política.
- Los ids nunca se borran ni se reutilizan: un criterio se marca `obsoleto` con `reemplazado_por`.
- Catálogo inválido ⇒ el sistema no arranca, con un mensaje que dice qué criterio y qué campo fallan.
- Cada HU trae su `sistema`; solo aplican los criterios con `aplica_a` igual a `todos` o a ese sistema.
- `SKILL.md` y `criterios.yaml` se congelan con un tag de git antes de etiquetar y correr el experimento.

## Nombres de herramientas
- El agente ve las herramientas como `servidor__herramienta` (como en el kit), por ejemplo `backlog__leer_historia`. La política usa esos nombres y admite comodines.
