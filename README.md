# RevisorHU — Agente revisor de historias de usuario

Proyecto final de la Maestría en IA (curso IA Distribuida, CENFOTEC).

El agente recibe una historia de usuario (HU) y hace lo siguiente:
- la **clasifica** por tipo;
- **busca** duplicados, conflictos e historias de referencia;
- la **estima** en story points (Fibonacci);
- la **refina** (redacción y criterios de aceptación como reglas o lista de verificación; el formato es configurable);
- **recomienda** una de tres decisiones: `aceptar`, `devolver` (con recomendaciones accionables) o `dividir`.

**El agente nunca aprueba.** La aprobación para la fábrica de software la da una persona.

**Pregunta de investigación:** ¿mejora una Skill procedimental basada en la *Definition of Ready* la exactitud de la decisión frente a instrucciones genéricas, y a qué costo en tokens? El detalle está en [docs/propuesta.md](docs/propuesta.md).

## Estado por fases

| Fase | Contenido | Estado |
|---|---|---|
| F0 | Andamiaje: estructura, reglas, documentación, puerto de backlog | ✅ |
| F1 | Backlog: `BacklogLocal` y `servidor_backlog` con su validación | ✅ |
| F2 | Catálogo de criterios, `servidor_conocimiento` y `servidor_estimacion` | ✅ |
| F3 | Agente: bucle con el SDK, política, trazas, modo simulado y CLI `revisar` | ✅ |
| F4 | `SKILL.md` y línea base | ✅ |
| F5 | Conjunto de evaluación, ataques, etiquetado y kappa | código ✅; falta el etiquetado (persona); ver "Conjunto de evaluación" abajo |
| F6 | Experimento, métricas y comando de reproducción | pendiente |
| F7 | Conector de Azure DevOps y poller (spec de Kiro, código de Kiro y Claude Code) | ✅ pruebas en verde; ver "Azure DevOps" abajo |

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

## Revisar una historia

Desde la raíz del repositorio, con el entorno virtual activo:

```powershell
# Sin clave ni costo: un guion reemplaza al modelo (muestra el bucle, la política y la traza)
revisar --caso HU-002 --config base --simulado

# Modelo real (claude-opus-5-5): cuesta dinero, alrededor de US$0,15–0,35 por HU
revisar --caso HU-002 --config base
```

- `--config skill` usa `skills/revisor-hu/SKILL.md`; `--config base` usa `config/instrucciones_base.md`. Es lo único que cambia entre las dos.
- La clave se lee de `ANTHROPIC_API_KEY` (entorno o `.env`) y nunca se escribe en la traza.
- Cada ejecución deja una traza JSONL en `trazas/desarrollo/` (no se versiona). Para un resumen, usa el lector del kit: `python ../kit-clase3/agente/leer_traza.py trazas/desarrollo/*.jsonl`.
- El código de salida es 0 solo si el agente terminó por sí mismo y registró una revisión.
- El modelo, el `effort`, los límites, la política y los archivos de datos están en `config/config.json`.

## Conjunto de evaluación (F5)

40 HU reales de 4 proyectos de Dalpiaz (2018), 19 de ellas difíciles, más 200 HU de contexto para que existan duplicados y conflictos. A 12 se les agregaron criterios de aceptación y 8 combinan varias HU (D-033). Los ataques de inyección (6 tipos) van aparte en `datos/ataques/`.

```powershell
python datos/descargar.py              # baja Dalpiaz y TAWOS a datos/crudos/ (no se versiona)
python datos/construir_casos.py        # regenera casos.jsonl y backlog_contexto.jsonl
python datos/etiquetar.py --anotador A --piloto   # etiquetado: lo hace una persona (guía en datos/guia_etiquetado.md)
python datos/etiquetar.py --anotador A
python experimentos/acuerdo.py         # etiquetas finales (y kappa si hay dos anotadores)
```

Los archivos generados ya están versionados: `descargar.py` solo hace falta para regenerarlos. Licencias y cambios declarados en `datos/LICENCIAS.md`.

**Conjunto bancario complementario (D-034):** 18 HU sintéticas de Banca Móvil en español, donde sí se aplican los criterios BM. Se reporta aparte del principal.

```powershell
python datos/construir_casos.py --conjunto banca
python datos/etiquetar.py --anotador A --conjunto banca
python experimentos/acuerdo.py --conjunto banca
```

## Azure DevOps (F7)

El poller busca User Stories nuevas (sin la etiqueta `ia-revisada`, creadas en los últimos 7 días) y ejecuta al agente sobre cada una. El agente deja **un comentario** con su recomendación (aceptar, devolver o dividir), los defectos, la historia refinada, los criterios propuestos y los story points sugeridos, y agrega las etiquetas `ia-revisada` e `ia-<decisión>`. **Nunca** aprueba, cambia el estado, asigna personas ni escribe el campo Story Points: la decisión es de una persona.

Configuración (la organización de prueba se crea con `docs/GUIA_AZURE_DEVOPS.md`):

| Variable en `.env` | Valor |
|---|---|
| `AZDO_ORG_URL` | `https://dev.azure.com/<organización>` |
| `AZDO_PROJECT` | nombre del proyecto, por ejemplo `RevisorHU-Pruebas` |
| `AZDO_PAT` | PAT con el alcance mínimo **Work Items: Read & write**. Nunca se pega en chats ni capturas. |
| `ANTHROPIC_API_KEY` | solo para `--real` |

```powershell
# Simulado: un guion reemplaza al modelo (sin costo), pero lee y ESCRIBE de verdad en Azure DevOps
python -m revisor.integracion.poller_azure --una-vez

# Real: cuesta dinero, alrededor de US$0,15–0,25 por HU; --max-hu limita cuántas HU revisa
python -m revisor.integracion.poller_azure --una-vez --real --max-hu 1

# Sin --una-vez queda corriendo y revisa cada 15 minutos; se detiene con Ctrl+C
python -m revisor.integracion.poller_azure --real

# Demo en clase: revisa cada 20 segundos y una HU por ciclo
python -m revisor.integracion.poller_azure --real --intervalo-segundos 20 --max-hu 1
```

- El resto de la configuración (mapeo Area Path → sistema, etiquetas, intervalo, máximo de HU por ciclo) está en `config/azure_devops.json`, sin secretos.
- `estado/azure_procesados.json` recuerda qué HU ya se revisaron. Una HU que falla se reintenta una sola vez.
- Las trazas quedan en `trazas/azure/`.

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

> Los tres servidores funcionan desde la raíz del repositorio con el backlog y las referencias **sintéticas** de `datos/ejemplo/`. Si el catálogo `conocimiento/criterios.yaml` es inválido, `backlog` y `conocimiento` no arrancan, a propósito: el error dice qué criterio y qué campo corregir.

## Documentación
- [docs/propuesta.md](docs/propuesta.md): propuesta aprobada (H1). Es el contrato del proyecto.
- [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md): diagrama y responsabilidades.
- [docs/DECISIONES.md](docs/DECISIONES.md): registro de decisiones.
- [docs/USO_IA.md](docs/USO_IA.md): bitácora de uso de IA.
- [docs/GUIA_AZURE_DEVOPS.md](docs/GUIA_AZURE_DEVOPS.md): organización de prueba, PAT, HU sintéticas y cómo trabajar la F7 con Kiro.
- [docs/kiro/PROMPT_F7_AZURE_DEVOPS.md](docs/kiro/PROMPT_F7_AZURE_DEVOPS.md): prompt del spec de Kiro para el conector.
- [CLAUDE.md](CLAUDE.md) y [.kiro/steering/](.kiro/steering/): reglas del proyecto para Claude Code y Kiro.

## Datos y seguridad
- Ninguna HU real del banco entra a este repositorio ni se envía a la API.
- Los secretos van en `.env`, que no se versiona.
- `datos/crudos/` no se versiona; las licencias se documentan en `datos/LICENCIAS.md` (F5).
