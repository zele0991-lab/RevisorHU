# Arquitectura

> Estado: F0 (andamiaje). Este documento se actualiza al cerrar cada fase.

## Vista general

```mermaid
flowchart LR
    subgraph Entradas
        CLI["CLI revisar<br/>--caso ID --config skill|base"]
        EXP["experimentos/ejecutar.py<br/>3 repeticiones por config"]
        POLL["poller_azure.py (F7)<br/>WIQL cada N minutos"]
    end

    subgraph Host["Host del agente (src/revisor/agente)"]
        PROMPT["Prompt de sistema<br/>SKILL.md | instrucciones_base.md"]
        BUCLE["Bucle manual de tool use<br/>SDK anthropic"]
        POL["Política<br/>ocultar > denegar > confirmar > permitir"]
        TRAZA["Traza JSONL<br/>inicio · respuesta_modelo · herramienta · fin"]
    end

    API[("API de Claude<br/>o modelo simulado")]

    subgraph MCP["Servidores MCP propios (stdio, FastMCP)"]
        SB["servidor_backlog<br/>leer · buscar · registrar · dividir<br/>(aprobar: oculta)"]
        SC["servidor_conocimiento<br/>listar_criterios · obtener_criterio · buscar_guia"]
        SE["servidor_estimacion<br/>historias_referencia · escala_estimacion"]
    end

    PUERTO["PuertoBacklog<br/>backlog/puerto.py"]
    LOCAL[("BacklogLocal<br/>JSON")]
    AZDO[("BacklogAzureDevOps (F7)<br/>comentario + etiquetas")]
    CAT["catalogo.py<br/>carga y valida"]
    YAML[("conocimiento/criterios.yaml<br/>única fuente de reglas")]
    TAWOS[("Referencias TAWOS<br/>story points reales")]
    MET["experimentos/metricas.py"]
    RES[("resultados/<br/>CSV y Markdown")]

    CLI --> BUCLE
    EXP --> BUCLE
    POLL --> BUCLE
    PROMPT --> BUCLE
    BUCLE <--> API
    BUCLE --> POL
    POL -->|permitida| SB
    POL -->|permitida| SC
    POL -->|permitida| SE
    BUCLE --> TRAZA
    SB --> PUERTO
    PUERTO --> LOCAL
    PUERTO --> AZDO
    SB -->|ids de defectos válidos| CAT
    SC --> CAT
    CAT --> YAML
    SE --> TAWOS
    TRAZA --> MET
    MET --> RES
```

## Piezas y responsabilidades

| Pieza | Decide | No decide |
|---|---|---|
| **Skill** (`SKILL.md`) o **instrucciones base** | El orden de trabajo, cuándo devolver o dividir, cuándo parar. Es la **única** diferencia entre las dos configuraciones. | Qué criterios existen (los pide a `listar_criterios`). |
| **Modelo** | Qué herramienta llamar y con qué argumentos; la recomendación final. | Si una herramienta se ejecuta. |
| **Política** (host) | Si cada llamada se oculta, se deniega, se confirma o se permite; topes de llamadas, pasos y tokens. | El contenido de la revisión. |
| **Servidores MCP** | Si los argumentos son válidos (listas cerradas, ids del catálogo, Gherkin, datos personales, longitudes). Rechazan con un mensaje que dice qué corregir. | Si el agente tiene permiso. |
| **Puerto de backlog** | Dónde y cómo se persiste (JSON local o Azure DevOps). | Si una revisión es válida. |
| **Catálogo** (`catalogo.py`) | Qué criterios existen, a qué sistema aplican y si el archivo es válido. | Nada más: es datos. |
| **Persona** | La aprobación para la fábrica. | — |

## Herramientas

| Servidor | Herramienta | Tipo | Política (experimento) |
|---|---|---|---|
| backlog | `leer_historia(id)` | Lee (texto no confiable) | permitir |
| backlog | `buscar_historias_similares(texto, limite)` | Lee | permitir |
| backlog | `registrar_revision(...)` | Escribe (borrador) | permitir · tope 1 (confirmar con Azure DevOps) |
| backlog | `proponer_division(id, partes)` | Escribe (borrador) | permitir · tope 1 (confirmar con Azure DevOps) |
| backlog | `aprobar_para_fabrica(id)` | Escribe (definitiva) | **ocultar** |
| conocimiento | `listar_criterios(sistema, categoria)` | Lee | permitir |
| conocimiento | `obtener_criterio(id)` | Lee | permitir |
| conocimiento | `buscar_guia(texto, limite)` | Lee | permitir |
| estimacion | `historias_referencia(texto, limite)` | Lee | permitir |
| estimacion | `escala_estimacion()` | Lee | permitir |

## Defensas contra la inyección indirecta

1. **Política:** la herramienta de aprobación está oculta, así que el modelo ni siquiera la ve.
2. **Topes:** como máximo una escritura de cada tipo por ejecución.
3. **Servidor:** valida cada escritura y rechaza datos personales.
4. **Envoltura:** los resultados de herramientas (incluido el texto de la HU) llegan marcados como datos no confiables, en las dos configuraciones.
5. **Skill:** regla explícita de ignorar instrucciones incrustadas en la HU (solo en la configuración `skill`).
