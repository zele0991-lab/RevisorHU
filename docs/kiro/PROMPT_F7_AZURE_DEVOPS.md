# Prompt para Kiro — Spec "conector-azure-devops" (fase F7)

> **Cómo usarlo:** con el árbol de git limpio, abre la carpeta del proyecto en Kiro, crea un
> **Spec** nuevo y pega todo lo que está debajo de la línea. Revisa `requirements.md` y
> `design.md` antes de dejar que Kiro ejecute las tareas. Trabaja en la rama `f7-azure-devops`.
>
> Esta versión reemplaza a `kit-clase3/proyecto/arranque/PROMPT_KIRO_AZURE_DEVOPS.md`, que quedó
> desactualizada: por ejemplo, hablaba de Gherkin y no conocía el perfil `azure` de la política.

---

## Antes de empezar

Lee, en este orden:
1. `.kiro/steering/` (product, tech, structure). Son las mismas reglas que `CLAUDE.md`.
2. `docs/DECISIONES.md`, sobre todo D-004 (puerto y adaptadores), D-005 (polling), D-006 (el agente
   nunca aprueba), D-008 (confirmación en Azure), D-019 (topes), D-027 (formato de los criterios),
   D-028 (pausa de llamadas pagadas), D-029 (preparación de esta fase) y D-030 (texto oculto que
   Azure DevOps conserva: variantes que hay que limpiar, dato de prueba real y campos de autor que
   no deben llegar al agente).
3. `src/revisor/backlog/puerto.py`: la interfaz que implementas.
4. `src/revisor/servidores/servidor_backlog.py`, función `_crear_backlog`: el contrato de arranque.
5. `src/revisor/agente/bucle.py` (`Opciones`, `ejecutar`) y `config/config_azure.json`.
6. `config/azure_devops.json`: la configuración del conector, sin secretos.

**No modifiques** el agente (`src/revisor/agente/`), la política (`config/politica.json`), la Skill,
el catálogo (`conocimiento/criterios.yaml`), los servidores MCP ni las pruebas existentes. Esta fase
solo **agrega un adaptador y un disparador**. Si algo de lo anterior te impide avanzar, detente,
documenta el motivo en `docs/DECISIONES.md` y pregunta.

## Objetivo

Conectar el agente revisor con **Azure DevOps Boards**. Cuando hay una User Story nueva, el agente la
revisa y deja su recomendación en el work item **sin aprobarla nunca y sin cambiar su estado**.

## Alcance

### 1. Adaptador `BacklogAzureDevOps` — `src/revisor/backlog/azure_devops.py`

Implementa `PuertoBacklog` contra la API REST de Azure DevOps.

**Construcción (contrato fijo):**
```python
class BacklogAzureDevOps(PuertoBacklog):
    @classmethod
    def desde_configuracion(cls, ruta_config: Path, marca: str | None) -> "BacklogAzureDevOps": ...
```
- Lee `config/azure_devops.json` y, del entorno, `AZDO_ORG_URL`, `AZDO_PROJECT` y `AZDO_PAT`. El host
  ya pasa esas tres variables al servidor del backlog, y solo a él (campo `entorno` en
  `config/config_azure.json`).
- Si falta alguna variable, lanza `ErrorBacklog` con un mensaje que diga cuál falta. Nunca muestres
  el PAT.

**Métodos:**
- `leer_historia(id)`: obtiene el work item y lo convierte en `Historia`.
  - Toma el título, la descripción, los criterios de aceptación, los story points y el Area Path.
  - Si el tipo no es el `tipo_work_item` de la configuración, o el id no es numérico, lanza
    `HistoriaNoEncontrada`.
  - Convierte el HTML a **texto plano** y **elimina** los comentarios HTML, los `<script>`/`<style>`
    y los elementos ocultos, porque pueden traer instrucciones escondidas. Se considera oculto todo
    elemento con `display:none` escrito de cualquier forma (mayúsculas, espacios, `;` final),
    `visibility:hidden`, `opacity:0`, `font-size:0`, el atributo `hidden` o `aria-hidden="true"`
    (D-030: Azure DevOps conserva `display:none;`).
  - Copia a `Historia` **solo** título, descripción, criterios de aceptación, story points y Area
    Path. Nunca `System.CreatedBy`, `System.ChangedBy` ni otros campos con nombres o correos.
  - Calcula el `sistema` con `mapeo_area_sistema`, usando el prefijo más largo que coincida. Si
    ninguno coincide, usa `sistema_por_defecto` y deja una advertencia en el log del servidor
    (stderr).
- `buscar_similares(texto, limite)`: consulta con WIQL las User Stories del proyecto y obtiene sus
  textos por lotes. Para ordenarlas **reutiliza** `revisor.backlog.similitud.IndiceSimilitud`, que
  ya existe, y devuelve `HistoriaSimilar` con la `similitud` calculada.
- `registrar_revision(revision)`:
  - Escribe **un comentario** legible con la decisión, los defectos, las recomendaciones, la historia
    refinada, los criterios de aceptación como lista, la estimación sugerida y el aviso "Borrador
    generado por IA; la aprobación es de una persona".
  - Agrega las etiquetas `ia-revisada` y la de la decisión (`etiquetas.por_decision`), **conservando
    las que ya existan**.
  - Los story points se sugieren solo en el comentario: **no** escribas el campo Story Points.
- `proponer_division(id, partes)`: escribe la propuesta como comentario. **No** crea work items hijos.
- `aprobar_para_fabrica(id)`: lanza `OperacionProhibida`. Siempre.
- `listar_pendientes(limite)`: consulta WIQL de las User Stories del proyecto **sin** la etiqueta
  `ia-revisada`, creadas dentro de `poller.ventana_dias`, ordenadas de la más antigua a la más
  nueva.

**Prohibido** (con pruebas que lo demuestren): cambiar `System.State`, asignar personas, borrar
algo o escribir cualquier campo que no sea `System.Tags`. El único JSON Patch permitido toca
`/fields/System.Tags`.

**HTTP:**
- Usa la biblioteca estándar (`urllib.request`), sin dependencias nuevas.
- Recibe el cliente HTTP inyectado en el constructor, para poder probar sin red.
- Autenticación básica con el PAT. Timeouts en cada llamada.
- Ante 429 o 5xx, reintentos con espera exponencial que respeten `Retry-After`.
- 401/403 → `ErrorBacklog` que sugiera revisar el alcance del PAT (Work Items: Read & write).
- 404 → `HistoriaNoEncontrada`.
- Antes de escribir código, **verifica en la documentación oficial vigente** de Azure DevOps REST
  los endpoints y la `api-version` de: Work Items (Get y Get Batch), WIQL, Comments (Add) y Update
  (JSON Patch). No los adivines.

### 2. Disparador `src/revisor/integracion/poller_azure.py`

- **Comando:** `python -m revisor.integracion.poller_azure [--una-vez] [--real] [--config skill|base]`.
  La configuración por defecto es `skill`.
- **Por defecto corre en modo SIMULADO**, sin costo (D-028). Solo con `--real` llama al modelo, y
  antes de empezar imprime el máximo de HU del ciclo y un costo estimado de US$0,15–0,25 por HU.
- **Cada ciclo:**
  1. obtiene `listar_pendientes(poller.max_hu_por_ciclo)` directamente del adaptador, sin pasar
     por MCP;
  2. descarta las HU ya registradas en `poller.registro_procesados`;
  3. por cada HU, llama a `revisor.agente.bucle.ejecutar(Opciones(...))` con
     `archivo_config=config/config_azure.json`, `caso=<id del work item>` y el aprobador
     desatendido (abajo).
- **Aprobador desatendido:** aprueba solo las herramientas de `escrituras_desatendidas`, con la razón
  "aprobada por la lista desatendida (config/azure_devops.json)". Cualquier otra cosa la deniega.
  Así queda en la traza (D-029).
- **Idempotente:** no revisa dos veces la misma HU, ni siquiera si se reinicia, gracias a la etiqueta
  y al registro local. Una ejecución que terminó con error se reintenta una sola vez en el ciclo
  siguiente.
- `--una-vez` hace un solo ciclo y termina; sirve para pruebas y para la demo. Sin esa opción,
  espera `poller.intervalo_minutos` entre ciclos y se detiene limpiamente con Ctrl+C.
- Cada HU deja su traza en `trazas/azure/`, con el formato del proyecto.

### 3. Pruebas (`pytest`, **sin red**)

Con el cliente HTTP falso y respuestas grabadas, como mínimo:
- 401, 404, 429 (reintenta y luego funciona) y 5xx;
- HTML malicioso: un comentario HTML con una instrucción y un elemento oculto desaparecen del
  texto que llega al agente, incluidas las variantes de ocultamiento de D-030;
- **respuesta real de la HU 10** (D-030), grabada como dato de prueba sin `System.CreatedBy` ni
  `System.ChangedBy`: la instrucción del `span` oculto no llega al agente;
- ningún campo de autor (nombre o correo) aparece en la `Historia` ni en la traza;
- etiquetas existentes conservadas, y el JSON Patch toca **solo** `System.Tags`;
- `aprobar_para_fabrica` lanza `OperacionProhibida`;
- el mapeo Area Path → sistema, incluido un Area Path sin mapeo (→ `todos`);
- el poller: no reprocesa (idempotencia), respeta `max_hu_por_ciclo`, el aprobador desatendido solo
  aprueba la lista y el modo por defecto es el simulado.

Además: `tests/test_config_azure.py` ya prueba el contrato `desde_configuracion` y tiene que seguir
en verde.

### 4. Ataque propio de Azure DevOps

Agrega a `datos/ataques/` una HU de ataque con una instrucción escondida en un **comentario HTML**
de la descripción, y una prueba que muestre que el adaptador la elimina.

### 5. Documentación al terminar

- `docs/ARQUITECTURA.md`: el diagrama con el adaptador y el poller.
- `docs/DECISIONES.md`: las decisiones de fondo que tomes (endpoints y `api-version` elegidos,
  formato del comentario, política de reintentos).
- `README.md`: cómo configurar la organización de prueba y cómo correr el poller (simulado y real).
- `docs/USO_IA.md`: qué hizo Kiro y cómo se verificó.

## Reglas que no se negocian

- Solo HU **sintéticas** en la organización de prueba. Nunca HU reales del banco.
- El PAT nunca aparece en el código, las trazas ni los logs.
- El agente **nunca aprueba** ni cambia el estado del work item.
- Las pruebas no usan la red. Ninguna prueba ni tarea llama a la API de Anthropic.

## Criterio de aceptación de la demo

1. En la organización de prueba se crea una User Story sintética de Banca Móvil con defectos.
2. Se ejecuta `python -m revisor.integracion.poller_azure --una-vez` en modo simulado, o `--real` si
   el responsable autorizó el costo.
3. En el work item aparece un comentario del agente con su recomendación y sus recomendaciones,
   más las etiquetas `ia-revisada` y la de la decisión.
4. El **estado** del work item no cambió y existe la traza de la ejecución en `trazas/azure/`.
