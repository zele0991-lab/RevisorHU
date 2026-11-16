# Requirements Document

## Introduction

Esta funcionalidad conecta el agente RevisorHU con Azure DevOps Boards para que las nuevas Historias de Usuario (HU) se revisen automáticamente. El agente lee cada work item, lo evalúa contra el catálogo de calidad y escribe su recomendación como comentario con etiquetas. Nunca aprueba un work item ni cambia su estado. El conector sigue el patrón puerto/adaptador existente: `BacklogAzureDevOps` implementa `PuertoBacklog` sin modificar el agente, la política, la Skill, el catálogo ni los servidores MCP. Un proceso de polling (`poller_azure.py`) conduce el ciclo, funcionando en modo simulado por defecto para evitar costos involuntarios de API.

## Glossary

- **Adaptador**: `BacklogAzureDevOps` — la clase que implementa `PuertoBacklog` contra la API REST de Azure DevOps.
- **Agente**: la función existente `revisor.agente.bucle.ejecutar` que ejecuta el modelo Claude con herramientas MCP.
- **Aprobador_Desatendido**: el aprobador desatendido utilizado por el Poller; aprueba automáticamente solo las herramientas listadas en `escrituras_desatendidas`.
- **BacklogAzureDevOps**: la clase adaptadora de Azure DevOps definida en `src/revisor/backlog/azure_devops.py`.
- **Cliente_HTTP**: el cliente HTTP inyectable utilizado por `BacklogAzureDevOps`; reemplazado por un simulacro en las pruebas.
- **Historia**: el dataclass `Historia` de `src/revisor/backlog/puerto.py`; contiene id del work item, proyecto (valor de `AZDO_PROJECT`), título, descripción, criterios de aceptación, story points y sistema.
- **Poller**: `src/revisor/integracion/poller_azure.py`; el proceso que consulta Azure DevOps en busca de Historias de Usuario sin revisar y ejecuta el agente en cada una.
- **Puerto**: la clase abstracta `PuertoBacklog` en `src/revisor/backlog/puerto.py`.
- **Registro_Procesados**: el archivo JSON local (ruta tomada de `poller.registro_procesados` en `config/azure_devops.json`) que registra los work items ya procesados entre reinicios.
- **Revision**: el dataclass `Revision` de `src/revisor/backlog/puerto.py`; el borrador de recomendación del agente.
- **Sistema**: la etiqueta de dominio (p. ej. `banca_movil`, `core`, `todos`) que determina qué criterios del catálogo aplican a una HU; se deriva del Area Path del work item mediante `mapeo_area_sistema`.
- **Work_Item**: un work item de Azure DevOps Boards de tipo User Story.

---

## Requirements

### Requisito 1: Construcción del adaptador desde la configuración

**Historia de usuario:** Como desarrollador que integra Azure DevOps, quiero que el adaptador se construya a partir de `config/azure_devops.json` y variables de entorno, para que ningún secreto aparezca en el código.

#### Criterios de aceptación

1. CUANDO se llama a `BacklogAzureDevOps.desde_configuracion(ruta_config, marca)` con un archivo JSON existente, `BacklogAzureDevOps` DEBE leer `tipo_work_item`, `mapeo_area_sistema`, `sistema_por_defecto`, `etiquetas` y `poller` del archivo JSON en `ruta_config` y almacenar cada valor en el atributo de instancia correspondiente antes de devolver el objeto construido.
2. CUANDO se llama a `BacklogAzureDevOps.desde_configuracion`, `BacklogAzureDevOps` DEBE leer `AZDO_ORG_URL`, `AZDO_PROJECT` y `AZDO_PAT` del entorno del proceso y almacenarlos de modo que cada llamada de API posterior utilice esos valores.
3. SI alguno de `AZDO_ORG_URL`, `AZDO_PROJECT` o `AZDO_PAT` está ausente del entorno o su valor es una cadena vacía tras eliminar los espacios en blanco, ENTONCES `BacklogAzureDevOps` DEBE lanzar `ErrorBacklog` con un mensaje que nombre la variable faltante por su nombre exacto y no contenga ninguna subcadena del valor del PAT.
4. CUANDO se llama a `BacklogAzureDevOps.desde_configuracion` con una ruta a un archivo que no existe o no puede analizarse como JSON válido, `BacklogAzureDevOps` DEBE lanzar `ErrorBacklog` con un mensaje que incluya la ruta del archivo y el motivo del fallo.
5. El constructor de `BacklogAzureDevOps` DEBE aceptar un argumento de palabra clave opcional `cliente_http`; cuando se proporciona, todas las llamadas HTTP DEBEN usar ese objeto en lugar de la implementación predeterminada de `urllib.request`, de modo que las pruebas puedan sustituir un simulacro sin acceso a la red.
6. `BacklogAzureDevOps` DEBE implementar los seis métodos abstractos de `PuertoBacklog` (`leer_historia`, `buscar_similares`, `registrar_revision`, `proponer_division`, `aprobar_para_fabrica`, `listar_pendientes`). Los archivos permitidos son: `src/revisor/backlog/azure_devops.py`, `src/revisor/integracion/poller_azure.py`, archivos nuevos en `tests/`, archivos nuevos en `datos/ataques/`, archivos nuevos en `.kiro/specs/` y las actualizaciones de `docs/ARQUITECTURA.md`, `docs/DECISIONES.md`, `docs/USO_IA.md` y `README.md`. Quedan prohibidas las modificaciones al agente (`src/revisor/agente/`), la política (`config/politica.json`), la Skill (`skills/`), el catálogo (`conocimiento/criterios.yaml`), los servidores MCP y las pruebas existentes.

---

### Requisito 2: Lectura de un work item

**Historia de usuario:** Como agente, quiero leer una Historia de Usuario de Azure DevOps para poder evaluarla contra el catálogo.

#### Criterios de aceptación

1. CUANDO se llama a `leer_historia(id)` con una cadena que representa un entero positivo y la API REST de Azure DevOps devuelve HTTP 200 para ese work item, `BacklogAzureDevOps` DEBE devolver una `Historia` cuyos campos se rellenan con los campos de respuesta de la API `System.Title`, `System.Description`, `Microsoft.VSTS.Common.AcceptanceCriteria`, `Microsoft.VSTS.Scheduling.StoryPoints` y `System.AreaPath`.
2. La `Historia` devuelta por `leer_historia` NO DEBE contener ningún valor derivado de `System.CreatedBy`, `System.ChangedBy` ni de ningún otro campo del work item no listado en el criterio 1; una prueba DEBE verificar esto para cada ruta de ejecución, incluyendo la ruta de éxito, la ruta de tipo incorrecto y la ruta sin coincidencia de Area Path.
3. CUANDO se llama a `leer_historia` y el campo `System.WorkItemType` del work item no es igual a `tipo_work_item` de la configuración (comparación sensible a mayúsculas), `BacklogAzureDevOps` DEBE lanzar `HistoriaNoEncontrada` sin realizar ninguna llamada de API adicional.
4. CUANDO se llama a `leer_historia` con una cadena vacía, que contiene caracteres no numéricos o que representa un entero no positivo (cero o negativo), `BacklogAzureDevOps` DEBE lanzar `HistoriaNoEncontrada` sin realizar ninguna llamada de API.
5. CUANDO se llama a `leer_historia` y la API devuelve HTTP 404, `BacklogAzureDevOps` DEBE lanzar `HistoriaNoEncontrada`.
6. CUANDO `leer_historia` recibe un work item cuyo `System.AreaPath` coincide con uno o más prefijos de `mapeo_area_sistema`, `BacklogAzureDevOps` DEBE asignar a `Historia.sistema` el valor mapeado al prefijo más largo; la comparación se realiza segmento a segmento (separador `\`) ignorando mayúsculas y minúsculas, de modo que `"RevisorHU-Pruebas\Core"` coincide con `"RevisorHU-Pruebas\Core\Pagos"` pero no con `"RevisorHU-Pruebas\CoreLegacy"`.
7. CUANDO se llama a `leer_historia` con un work item cuyo `System.AreaPath` no coincide con ningún prefijo de `mapeo_area_sistema`, `BacklogAzureDevOps` DEBE asignar a `Historia.sistema` el valor de `sistema_por_defecto` y escribir un mensaje de advertencia que contenga el valor del Area Path no coincidente en stderr.

---

### Requisito 3: Saneamiento HTML del contenido del work item

**Historia de usuario:** Como revisor de seguridad, quiero que todo el HTML oculto y malicioso sea eliminado antes de que llegue al agente, para prevenir la inyección de prompts mediante texto oculto.

#### Criterios de aceptación

1. CUANDO `leer_historia` procesa un valor de campo del work item que contiene un comentario HTML (`<!--...-->`), `BacklogAzureDevOps` DEBE eliminar el comentario y todo su contenido del texto almacenado en `Historia`.
2. CUANDO `leer_historia` procesa un valor de campo del work item que contiene un elemento `<script>` o `<style>` (etiqueta de apertura, contenido y etiqueta de cierre), `BacklogAzureDevOps` DEBE eliminar el elemento completo y su contenido.
3. CUANDO `leer_historia` procesa un valor de campo del work item que contiene un elemento cuyo atributo `style` contiene `display:none` en cualquier combinación de mayúsculas y minúsculas, con o sin espacios alrededor de los dos puntos y con o sin punto y coma final, `BacklogAzureDevOps` DEBE eliminar ese elemento, sus atributos y su contenido por completo.
4. CUANDO `leer_historia` procesa un valor de campo del work item que contiene un elemento cuyo atributo `style` contiene `visibility:hidden`, `opacity:0` o `font-size:0` (cada uno con cualquier espaciado y punto y coma final opcional), `BacklogAzureDevOps` DEBE eliminar ese elemento, sus atributos y su contenido por completo. El valor `opacity:0.5` y el valor `font-size:0.8em` **no** se consideran ocultamiento y el elemento no se elimina.
5. CUANDO `leer_historia` procesa un valor de campo del work item que contiene un elemento con el atributo booleano `hidden` o el atributo `aria-hidden="true"`, `BacklogAzureDevOps` DEBE eliminar ese elemento, sus atributos y su contenido por completo.
6. CUANDO `leer_historia` procesa un valor de campo del work item que contiene contenido visible y elementos ocultos en el mismo campo, `BacklogAzureDevOps` DEBE preservar todo el texto que no esté dentro de un elemento eliminado y DEBE eliminar únicamente los elementos ocultos identificados por los criterios 1–5.
7. `BacklogAzureDevOps` DEBE convertir el HTML saneado a texto plano antes de almacenarlo en `Historia.texto` y `Historia.criterios_aceptacion`; el texto plano NO DEBE contener etiquetas HTML ni referencias de carácter (p. ej. `&amp;`, `&lt;`).

---

### Requisito 4: Búsqueda de historias similares

**Historia de usuario:** Como agente, quiero encontrar work items similares a una historia dada para poder detectar duplicados, conflictos y referencias de story points.

#### Criterios de aceptación

1. CUANDO se llama a `buscar_similares(texto, limite)`, `BacklogAzureDevOps` DEBE ejecutar exactamente una consulta WIQL para obtener los ids de work items de tipo User Story del proyecto y luego obtener su contenido completo en lotes usando el endpoint de lote de Work Items de la API REST de Azure DevOps.
2. AL clasificar los resultados, `BacklogAzureDevOps` DEBE instanciar `revisor.backlog.similitud.IndiceSimilitud` con el contenido en texto plano saneado de los work items obtenidos y llamar a `IndiceSimilitud.buscar(texto, limite)` para obtener puntuaciones de similitud por coseno; NO DEBE implementar un algoritmo de clasificación separado.
3. `BacklogAzureDevOps` DEBE devolver una `list[HistoriaSimilar]` de como máximo `limite` elementos, ordenados de mayor a menor `similitud`; cada `HistoriaSimilar.similitud` DEBE ser un `float` en el intervalo cerrado [0.0, 1.0] y NO DEBE ser `None`.
4. `BacklogAzureDevOps` DEBE aplicar el mismo saneamiento HTML definido en el Requisito 3 a la descripción de cada work item obtenido antes de pasar su texto a `IndiceSimilitud`; el texto sin sanear NO DEBE llegar al índice de similitud.
5. CUANDO se llama a `buscar_similares` y la consulta WIQL devuelve cero work items, `BacklogAzureDevOps` DEBE devolver una lista vacía sin lanzar un error.

---

### Requisito 5: Registro de una revisión

**Historia de usuario:** Como agente, quiero registrar mi revisión como borrador en Azure DevOps para que una persona pueda inspeccionar la recomendación antes de actuar.

#### Criterios de aceptación

1. CUANDO se llama a `registrar_revision(revision)` y la API acepta la solicitud, `BacklogAzureDevOps` DEBE añadir exactamente un comentario al work item identificado por `revision.id_historia`; el cuerpo del comentario DEBE incluir: el valor de `revision.decision`, la lista de cadenas en `revision.defectos`, todos los valores `Recomendacion.texto` en `revision.recomendaciones`, el valor de `revision.historia_refinada`, la lista de cadenas en `revision.criterios_aceptacion`, el valor entero de `revision.estimacion` y el texto literal de descargo "Borrador generado por IA; la aprobación es de una persona".
2. CUANDO se llama a `registrar_revision(revision)`, `BacklogAzureDevOps` DEBE actualizar el campo `System.Tags` del work item para incluir el valor de etiqueta de `etiquetas.revisada` y el valor de etiqueta de `etiquetas.por_decision[revision.decision]`, añadiéndolos a las etiquetas que ya existen en el work item y preservando todas las cadenas de etiquetas preexistentes sin cambios.
3. `BacklogAzureDevOps` DEBE actualizar las etiquetas enviando un documento JSON Patch que contenga exactamente una operación dirigida a la ruta `/fields/System.Tags` y ninguna otra ruta; NO DEBE incluir operaciones para `System.State`, campos de asignado, `Microsoft.VSTS.Scheduling.StoryPoints` ni ningún otro campo.
4. `BacklogAzureDevOps` NO DEBE escribir el valor de `revision.estimacion` en el campo `Microsoft.VSTS.Scheduling.StoryPoints` del work item; el valor de story points DEBE aparecer únicamente dentro del texto del comentario descrito en el criterio 1.
5. CUANDO `registrar_revision` termina sin error, `BacklogAzureDevOps` DEBE devolver una cadena no vacía que contenga la URL del comentario creado o su id numérico, permitiendo que una persona localice el comentario en Azure DevOps.
6. ANTES de ensamblar el cuerpo del comentario, `BacklogAzureDevOps` DEBE escapar como HTML todos los valores de texto que provienen del agente (decisión, defectos, recomendaciones, historia refinada, criterios de aceptación), de modo que no se reinyecte HTML ni scripts en Azure DevOps.

---

### Requisito 6: Propuesta de división

**Historia de usuario:** Como agente, quiero proponer la división de una historia grande en partes para que el equipo decida si dividirla.

#### Criterios de aceptación

1. CUANDO se llama a `proponer_division(id, partes)` y la API acepta la solicitud, `BacklogAzureDevOps` DEBE añadir exactamente un comentario al work item identificado por `id`; el cuerpo del comentario DEBE listar cada cadena de `partes` como una historia propuesta separada en formato "Como…, quiero…, para…", con una historia propuesta por párrafo o elemento de lista.
2. `BacklogAzureDevOps` NO DEBE crear work items hijos, subtareas, work items vinculados ni ningún work item nuevo en Azure DevOps cuando se llama a `proponer_division`.
3. CUANDO `proponer_division` termina sin error, `BacklogAzureDevOps` DEBE devolver una cadena no vacía que contenga la URL del comentario creado o su id numérico.
4. ANTES de ensamblar el cuerpo del comentario, `BacklogAzureDevOps` DEBE escapar como HTML cada cadena de `partes`, de modo que no se reinyecte HTML ni scripts en Azure DevOps.

---

### Requisito 7: Bloqueo de la aprobación

**Historia de usuario:** Como auditor de seguridad, quiero que `aprobar_para_fabrica` siempre falle en el adaptador de Azure DevOps para que el agente no pueda aprobar un work item independientemente de cómo se haya invocado.

#### Criterios de aceptación

1. CUANDO se llama a `aprobar_para_fabrica(id)` en una instancia de `BacklogAzureDevOps`, `BacklogAzureDevOps` DEBE lanzar `OperacionProhibida` como primera acción, antes de que se ejecute cualquier otro código en el cuerpo del método.
2. `BacklogAzureDevOps` DEBE lanzar `OperacionProhibida` desde `aprobar_para_fabrica` incluso cuando `id` es un id de work item válido que existe en Azure DevOps y las credenciales configuradas tienen alcance de escritura; una prueba DEBE verificar esto afirmando que no se realiza ninguna llamada HTTP.
3. SI se modifica `escrituras_desatendidas` en `config/azure_devops.json` para incluir la cadena `"backlog__aprobar_para_fabrica"`, ENTONCES `Aprobador_Desatendido` DEBE seguir denegando la llamada; una prueba DEBE verificar que `aprobar_para_fabrica` lanza `OperacionProhibida` independientemente del contenido de `escrituras_desatendidas`.

---

### Requisito 8: Listado de historias pendientes

**Historia de usuario:** Como Poller, quiero obtener las Historias de Usuario sin revisar para que el agente procese cada historia nueva exactamente una vez.

#### Criterios de aceptación

1. CUANDO se llama a `listar_pendientes(limite)`, `BacklogAzureDevOps` DEBE ejecutar una consulta WIQL que seleccione únicamente User Stories de tipo `tipo_work_item` cuyas etiquetas no incluyan el valor de `etiquetas.revisada`, cuyo `System.CreatedDate` caiga dentro de los últimos `poller.ventana_dias` días calendario (inclusive del día actual), y que estén ordenadas por `System.CreatedDate` de forma ascendente (las más antiguas primero).
2. `BacklogAzureDevOps` DEBE devolver una `list[Historia]` de como máximo `limite` elementos construida a partir de los resultados WIQL; si el resultado WIQL contiene más de `limite` elementos, solo se obtienen y devuelven los primeros `limite`.
3. CUANDO la consulta WIQL devuelve cero resultados, `BacklogAzureDevOps` DEBE devolver una lista vacía sin lanzar un error y sin realizar llamadas de API adicionales.
4. CUANDO se llama a `listar_pendientes` con `limite` igual a cero o negativo, `BacklogAzureDevOps` DEBE devolver una lista vacía sin realizar ninguna llamada de API.

---

### Requisito 9: Resiliencia HTTP

**Historia de usuario:** Como operador del sistema, quiero que el adaptador gestione errores de API transitorios de forma elegante para que los fallos temporales no bloqueen permanentemente la revisión de historias.

#### Criterios de aceptación

1. CUANDO la API de Azure DevOps devuelve HTTP 429 o cualquier código 5xx en una petición idempotente (GET o WIQL), `BacklogAzureDevOps` DEBE reintentar la misma petición hasta 3 veces con retroceso exponencial de base 1 segundo (1 s, 2 s, 4 s); tras el tercer reintento fallido DEBE lanzar `ErrorBacklog` con un mensaje que incluya el código HTTP y el número de intentos realizados. Las peticiones no idempotentes (POST de comentarios) NO se reintentan por timeout ni por 5xx; el criterio 9.7 regula la deduplicación en su lugar.
2. CUANDO la respuesta de la API incluye un encabezado `Retry-After` con un valor numérico, `BacklogAzureDevOps` DEBE esperar al menos ese número de segundos enteros antes del siguiente intento de reintento, anulando el intervalo de retroceso exponencial si `Retry-After` es mayor.
3. CUANDO la API devuelve HTTP 401 o HTTP 403, `BacklogAzureDevOps` DEBE lanzar `ErrorBacklog` con un mensaje que indique el código HTTP, sugiera verificar que el PAT tiene el alcance "Work Items: Read & write" y no contenga ninguna subcadena del valor del PAT.
4. CUANDO la API devuelve HTTP 404, `BacklogAzureDevOps` DEBE lanzar `HistoriaNoEncontrada`; NO DEBE reintentar una respuesta 404.
5. `BacklogAzureDevOps` DEBE aplicar un timeout de 30 segundos a cada petición HTTP individual; si la petición no concluye en ese plazo, DEBE cancelarla y tratarla como fallo reintentable (igual que 5xx) solo si la petición es idempotente (GET o WIQL); si no es idempotente, DEBE lanzar `ErrorBacklog` sin reintentar.
6. `BacklogAzureDevOps` DEBE usar únicamente `urllib.request` de la biblioteca estándar de Python para todas las operaciones HTTP; no se DEBE importar ni usar ninguna biblioteca HTTP de terceros.
7. TODO comentario publicado por el adaptador DEBE incluir la marca fija `[RevisorHU]` en el cuerpo, además de la marca de la ejecución (`marca` recibida en `desde_configuracion`). CUANDO `registrar_revision` o `proponer_division` va a publicar un comentario en un work item, `BacklogAzureDevOps` DEBE primero obtener la lista completa de comentarios existentes del work item recorriendo todas las páginas disponibles mediante el campo `continuationToken` de la respuesta, y verificar si ya existe alguno cuyo cuerpo contenga la cadena `[RevisorHU]`; SI existe ese comentario, DEBE omitir la publicación, completar únicamente las etiquetas que falten en `System.Tags` y devolver la referencia del comentario encontrado, evitando así que un reintento del Poller (que llega con un `run_id` distinto) publique un segundo comentario. La lectura de comentarios para la deduplicación recorre todas las páginas disponibles siguiendo el campo `continuationToken` de la respuesta antes de decidir que no existe un comentario `[RevisorHU]`.
8. La función de espera entre reintentos (equivalente a `time.sleep`) DEBE ser inyectable en el constructor de `BacklogAzureDevOps`; cuando se inyecta una función alternativa en las pruebas, el adaptador DEBE usarla en lugar de `time.sleep`, de modo que los tests de reintentos no esperen tiempo real.

---

### Requisito 10: Operación del Poller

**Historia de usuario:** Como líder de equipo, quiero un poller automatizado que revise las nuevas Historias de Usuario sin intervención manual para que el equipo reciba retroalimentación oportuna.

#### Criterios de aceptación

1. El `Poller` DEBE poder ejecutarse como `python -m revisor.integracion.poller_azure` y DEBE aceptar los argumentos de línea de comandos `--una-vez` (indicador), `--real` (indicador) y `--config` con los valores `skill` o `base`; si se omite `--config`, el valor por defecto DEBE ser `skill`.
2. MIENTRAS no se proporcione `--real`, el `Poller` DEBE ejecutarse en modo simulado pasando `simulado=True` a `revisor.agente.bucle.ejecutar` y NO DEBE establecer la variable de entorno `ANTHROPIC_API_KEY` ni realizar ninguna conexión a la API de Anthropic.
3. CUANDO se proporciona `--real`, el `Poller` DEBE imprimir en stdout, antes de iniciar cualquier llamada al modelo, el valor de `poller.max_hu_por_ciclo` y un rango de costo estimado de "US$0.15–0.25 por historia", y DEBE esperar sin recibir ninguna entrada antes de continuar.
4. CUANDO comienza un ciclo de polling, el `Poller` DEBE llamar a `BacklogAzureDevOps.listar_pendientes(poller.max_hu_por_ciclo)` directamente en la instancia del adaptador (no a través del servidor MCP) para obtener la lista de historias candidatas para ese ciclo.
5. AL procesar cada HU candidata, el `Poller` DEBE llamar a `revisor.agente.bucle.ejecutar(Opciones(...))` con `asyncio` (ya que `ejecutar` es una corrutina), pasando: `config` con el valor de `--config` (por defecto `"skill"`), `simulado=True` salvo que se haya indicado `--real`, `archivo_config=Path("config/config_azure.json")`, `caso` con el id del work item como cadena de texto y `aprobador` con la instancia de `Aprobador_Desatendido`.
6. CUANDO se proporciona `--una-vez`, el `Poller` DEBE ejecutar exactamente un ciclo de polling y salir con código 0 después de que el ciclo se complete, independientemente de cuántas historias se procesaron.
7. MIENTRAS no se proporcione `--una-vez`, el `Poller` DEBE dormir exactamente `poller.intervalo_minutos` minutos entre el final de un ciclo y el inicio del siguiente; CUANDO se interrumpe por SIGINT (Ctrl+C), el `Poller` DEBE detenerse después de completar cualquier ejecución de historia en curso y salir con código 0.
8. El `Poller` DEBE escribir cada traza de ejecución por historia en el directorio `trazas/azure/` usando el mismo formato JSONL y la misma convención de nombres `run_id` que `revisor.agente.bucle.ejecutar`.

---

### Requisito 11: Idempotencia del Poller

**Historia de usuario:** Como operador del sistema, quiero que el poller nunca revise la misma historia dos veces para evitar comentarios duplicados y llamadas de API desperdiciadas.

#### Criterios de aceptación

1. CUANDO el work item de una historia candidata ya tiene la etiqueta `etiquetas.revisada` en Azure DevOps en el momento en que `listar_pendientes` retorna, el `Poller` NO DEBE incluir esa historia en la cola de procesamiento; `revisor.agente.bucle.ejecutar` NO DEBE llamarse para ella en ese ciclo.
2. CUANDO el id del work item de una historia candidata está presente como clave en `Registro_Procesados` al inicio de un ciclo de polling, el `Poller` DEBE omitir esa historia sin llamar a `ejecutar` para ella, incluso si la etiqueta `etiquetas.revisada` está ausente.
3. CUANDO `ejecutar` retorna para una HU y `Resultado.decision` no es `None` y `Resultado.motivo_cierre` es `"end_turn"`, el `Poller` DEBE escribir en `Registro_Procesados` una entrada cuya clave es el id del work item y cuyo valor es el `run_id` como cadena de texto (p. ej. `"42": "20261114_192848_060_skill_r1_42"`) antes de pasar a la siguiente HU del mismo ciclo.
4. CUANDO `ejecutar` lanza una excepción, o retorna un `Resultado` cuyo `motivo_cierre` es distinto de `"end_turn"`, o retorna un `Resultado` con `decision` igual a `None`, el `Poller` DEBE registrar el error en stderr incluyendo el id del work item y el motivo. En el primer fallo, el `Poller` DEBE escribir en `Registro_Procesados` una entrada con `{"fallos": 1, "motivo": "<motivo>"}` y DEBE permitir que la HU se reintente en el próximo ciclo. Tras un segundo fallo consecutivo, el `Poller` DEBE sobrescribir esa entrada con `{"fallido": true, "motivo": "<motivo>"}`, impidiendo nuevos reintentos. El `Poller` DEBE omitir en cada ciclo los ids cuya entrada en `Registro_Procesados` sea una cadena (completado) o un objeto con `"fallido": true` (fallido definitivo), exactamente igual que omite los ids completados.

---

### Requisito 12: Aprobador desatendido

**Historia de usuario:** Como auditor de seguridad, quiero que el aprobador desatendido solo apruebe las herramientas de escritura explícitamente listadas para que ninguna llamada de herramienta no intencionada se ejecute sin supervisión humana.

#### Criterios de aceptación

1. CUANDO se llama a `Aprobador_Desatendido` con un nombre de herramienta que aparece en la lista `escrituras_desatendidas` de `config/azure_devops.json`, `Aprobador_Desatendido` DEBE devolver `(True, "aprobada por la lista desatendida (config/azure_devops.json)")` para que el código que llama en `bucle.py` trate la llamada como permitida y el motivo de aprobación quede registrado en la traza.
2. CUANDO se llama a `Aprobador_Desatendido` con un nombre de herramienta que no aparece en `escrituras_desatendidas`, `Aprobador_Desatendido` DEBE devolver `(False, motivo)` donde `motivo` es una cadena no vacía que explica que la herramienta no está en la lista desatendida; el código que llama en `bucle.py` DEBE registrar esta denegación en la traza.
3. `Aprobador_Desatendido` DEBE devolver `(False, motivo)` cuando se llama con el nombre de herramienta `"backlog__aprobar_para_fabrica"` independientemente de si esa cadena aparece en `escrituras_desatendidas`; esta comprobación DEBE evaluarse antes de la búsqueda en la lista del criterio 1.

---

### Requisito 13: Pruebas sin red

**Historia de usuario:** Como desarrollador, quiero que todas las pruebas se ejecuten sin acceso a la red para que el conjunto de pruebas sea determinista y funcione en cualquier entorno.

#### Criterios de aceptación

1. El conjunto de pruebas DEBE usar un simulacro de `Cliente_HTTP` que devuelva objetos de respuesta pregrabados; ninguna prueba DEBE abrir un socket, resolver un nombre de host ni realizar ninguna conexión HTTP real; una prueba DEBE fallar si se llama al `urllib.request.urlopen` real durante la ejecución del conjunto.
2. El conjunto de pruebas DEBE incluir una prueba que use la respuesta de API pregrabada para el work item id 10 (de D-030, con los campos `System.CreatedBy` y `System.ChangedBy` eliminados antes de la grabación) y afirme que el `Historia.texto` resultante no contiene la cadena "Instrucción del sistema" ni ninguna subcadena de la instrucción oculta del `<span>`.
3. El conjunto de pruebas DEBE incluir una prueba por cada escenario de error HTTP: HTTP 401 lanza `ErrorBacklog`, HTTP 403 lanza `ErrorBacklog`, HTTP 404 lanza `HistoriaNoEncontrada`, HTTP 429 reintenta y tiene éxito en el segundo intento (devolviendo una `Historia` válida) y HTTP 500 reintenta hasta 3 veces antes de lanzar `ErrorBacklog`.
4. El conjunto de pruebas DEBE incluir una prueba por cada variante de contenido oculto de D-030: comentario HTML, `display:none` en minúsculas, `DISPLAY:NONE` en mayúsculas, `display: none` con espacio, `display:none;` con punto y coma, `visibility:hidden`, `opacity:0`, `font-size:0`, el atributo booleano `hidden` y `aria-hidden="true"`; cada prueba DEBE afirmar que el texto oculto está ausente de la `Historia` resultante. La prueba DEBE cubrir al menos una variante de `font-size:0` con unidad CSS (`font-size:0px`, `font-size:0em` o `font-size:0pt`).
5. El conjunto de pruebas DEBE incluir una prueba que capture el cuerpo JSON Patch enviado por `registrar_revision` al endpoint de actualización del work item y afirme que contiene exactamente una operación, que la `path` de la operación es `/fields/System.Tags` y que ningún otro valor de `path` aparece en el documento.
6. El conjunto de pruebas DEBE incluir una prueba que llame a `aprobar_para_fabrica` en una instancia de `BacklogAzureDevOps` y afirme que se lanza `OperacionProhibida` y que el simulacro de `Cliente_HTTP` registra cero llamadas.
7. El conjunto de pruebas DEBE incluir una prueba para cada ruta de ejecución en `leer_historia` y `buscar_similares` que afirme que los objetos `Historia` devueltos no contienen ningún valor derivado de `System.CreatedBy` o `System.ChangedBy`.
8. El conjunto de pruebas DEBE verificar que `tests/test_config_azure.py` pasa sin modificaciones después de implementar el adaptador.

---

### Requisito 14: Muestra de ataque

**Historia de usuario:** Como investigador de seguridad, quiero una muestra de ataque documentada en `datos/ataques/` para que las defensas del adaptador puedan validarse y demostrarse.

#### Criterios de aceptación

1. El directorio `datos/ataques/` DEBE contener al menos un archivo que represente una Historia de Usuario sintética cuyo valor del campo `System.Description` incluya una instrucción oculta incrustada en un comentario HTML con la forma `<!-- [texto de instrucción] -->`.
2. CUANDO el adaptador `BacklogAzureDevOps` procesa el archivo de muestra de ataque pasando su valor de `System.Description` a través de la lógica de saneamiento, el adaptador DEBE producir una cadena de texto plano en la que el comentario HTML y el texto de instrucción que contenía estén completamente ausentes.
3. El conjunto de pruebas DEBE incluir una prueba que cargue el archivo de muestra de ataque, pase su campo `System.Description` a través de la misma función de saneamiento usada por `leer_historia` y afirme que la cadena resultante no contiene ningún texto de instrucción del comentario HTML y no contiene las subcadenas `<!--` ni `-->`.

---

### Requisito 15: Actualizaciones de documentación

**Historia de usuario:** Como miembro del equipo, quiero que la documentación se actualice para reflejar el nuevo conector para que cualquiera pueda configurar y ejecutar la integración con Azure DevOps.

#### Criterios de aceptación

1. `docs/ARQUITECTURA.md` DEBE contener un diagrama (ASCII o imagen) que muestre `BacklogAzureDevOps`, `Poller`, el agente existente (`bucle.ejecutar`) y el `servidor_backlog` MCP como nodos distintos, con flechas etiquetadas que indiquen la dirección de cada llamada entre ellos.
2. `docs/DECISIONES.md` DEBE contener nuevas entradas que documenten: los endpoints de la API REST de Azure DevOps y la cadena `api-version` elegidos para Work Item Get, Work Item Batch, WIQL, Comments Add y Work Item Update; la estructura y los campos requeridos del comentario escrito por `registrar_revision`; y la política de reintentos (máximo de intentos, fórmula de retroceso y manejo de `Retry-After`) elegida para la resiliencia HTTP.
3. `README.md` DEBE contener una sección titulada "Azure DevOps" que incluya: los nombres y valores esperados de `AZDO_ORG_URL`, `AZDO_PROJECT` y `AZDO_PAT`; el alcance mínimo requerido del PAT ("Work Items: Read & write"); y los comandos exactos para ejecutar el poller en modo simulado (`python -m revisor.integracion.poller_azure --una-vez`) y en modo real (`python -m revisor.integracion.poller_azure --una-vez --real`).
4. `docs/USO_IA.md` DEBE contener una nueva entrada para esta funcionalidad que indique qué archivos creó o modificó Kiro, qué pruebas se ejecutaron para verificar la corrección y el resultado de esas pruebas (recuentos de pase/fallo o salida del comando de prueba).

---

### Requisito 16: Propiedades transversales del adaptador

**Historia de usuario:** Como operador del sistema, quiero que el adaptador gestione correctamente la codificación, los secretos, los identificadores y el alcance de la búsqueda, para que funcione de forma robusta y segura en cualquier entorno.

#### Criterios de aceptación

1. `BacklogAzureDevOps` DEBE decodificar todas las respuestas HTTP como UTF-8; si el cuerpo de la respuesta contiene bytes inválidos en UTF-8, DEBE lanzar `ErrorBacklog` indicando el endpoint que respondió y el problema de codificación.
2. El valor de `AZDO_PAT` NUNCA DEBE aparecer en logs, trazas, mensajes de excepción ni en la representación `__repr__` o `__str__` de ningún objeto, incluido el encabezado `Authorization`; una prueba DEBE verificar que, tras provocar un `ErrorBacklog`, el mensaje de excepción no contiene ninguna subcadena del PAT.
3. `Historia.id` DEBE contener el id del work item de Azure DevOps como cadena de texto (p. ej. `"42"`), y `Historia.proyecto` DEBE contener el valor de `AZDO_PROJECT` leído del entorno; ambos campos DEBEN establecerse en `leer_historia` y en cada `Historia` construida por `listar_pendientes`.
4. CUANDO `buscar_similares` ejecuta la consulta WIQL, DEBE limitar los resultados a las 200 User Stories más recientes del proyecto (ordenadas por `System.CreatedDate` descendente); como `buscar_similares` recibe texto y no un id, la "propia HU" se reconoce porque su texto saneado es idéntico al texto buscado; esa coincidencia exacta DEBE excluirse de los resultados antes de calcular la similitud y de devolver la lista.
5. El criterio de ocultamiento por `font-size` cero (Requisito 3.4) INCLUYE los valores con unidades CSS: `font-size:0px`, `font-size:0em` y `font-size:0pt` se consideran equivalentes a `font-size:0`; la prueba del Requisito 13.4 DEBE cubrir al menos una variante con unidad.
