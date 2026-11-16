# Implementation Plan: conector-azure-devops

## Overview

Implementar `BacklogAzureDevOps` (adaptador del puerto para Azure DevOps Boards) y `poller_azure.py` (proceso de polling) siguiendo el patrón puerto/adaptador existente. Los archivos modificados son `src/revisor/backlog/azure_devops.py`, `src/revisor/integracion/poller_azure.py`, los archivos de prueba nuevos y las actualizaciones de documentación. No se modifica ningún archivo existente del agente, la política, la Skill, el catálogo ni los servidores MCP.

## Tasks

- [x] 1. Implementar `_sanear_html` y sus pruebas parametrizadas
  - [x] 1.1 Crear `src/revisor/backlog/azure_devops.py` con la función `_sanear_html`
    - Crear el archivo con la subclase interna de `html.parser.HTMLParser` con `convert_charrefs=True`
    - Implementar la pila `_profundidad_oculta: int` para rastrear profundidad de ocultamiento
    - Implementar `handle_starttag`: incrementar profundidad si la etiqueta es `script` o `style`, si tiene atributo `hidden` booleano, si tiene `aria-hidden="true"`, o si el atributo `style` coincide con `_RE_OCULTO`. Dentro de una región oculta (`_profundidad_oculta > 0`), toda etiqueta de apertura que no sea void element incrementa la profundidad en 1, aunque no sea oculta por sí misma.
    - Implementar `handle_endtag`: decrementar profundidad cuando corresponda; la profundidad nunca baja de 0: si `handle_endtag` se invoca con `_profundidad_oculta == 0`, se ignora sin modificar la profundidad.
    - Implementar verificación de void elements en `handle_starttag` **y** en `handle_startendtag`: si la etiqueta está en la lista de void elements (`br`, `img`, `hr`, `input`, `meta`, `link`, `wbr`, `area`, `base`, `col`, `embed`, `source`, `track`), no se modifica la profundidad en ninguno de los dos callbacks. Esto cubre `<br>` escrito sin barra de cierre, que `html.parser` puede enrutar a `handle_starttag` en lugar de `handle_startendtag`.
    - Implementar `handle_comment`: descartar todo sin acumular
    - Implementar `handle_data`: acumular texto solo cuando `_profundidad_oculta == 0`
    - Definir la constante `_RE_OCULTO` exactamente como especifica el diseño
    - _Requisitos: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [x] 1.2 Escribir pruebas parametrizadas de `_sanear_html` en `tests/test_azure_devops.py`
    - Crear `tests/test_azure_devops.py` con monkeypatch que bloquea `urllib.request.urlopen` (lanza `AssertionError` si se llama)
    - **Propiedad 1 (Property 1): Preservación del texto visible y eliminación del texto oculto**
      - `<p>visible</p><span style="display:none">oculto</span>` → "visible" presente, "oculto" ausente
      - `<!-- instrucción -->texto visible` → "texto visible" presente, "instrucción" ausente
      - `<script>alert(1)</script>texto visible` → "texto visible" presente, "alert" ausente
      - HTML solo con contenido visible → todo el texto presente
      - `<span style="opacity:0.5">visible</span>` → "visible" presente (caso negativo)
      - `<span style="font-size:0.8em">visible</span>` → "visible" presente (caso negativo)
      - `"</span></span><span style=\"display:none\">instrucción</span>visible"` → `"instrucción"` ausente, `"visible"` presente.
      - `"<span style=\"display:none\"><b>x</b> secreto</span>visible"` → `"secreto"` ausente, `"visible"` presente.
      - `"<span style=\"display:none\">instrucción sin cerrar"` → la salida está vacía o no contiene `"instrucción"` (elemento oculto sin cierre: el campo termina con profundidad > 0 y el texto oculto fue descartado en tiempo real).
      - **Validates: Requisitos 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**
    - **Propiedad 2 (Property 2): Ausencia de etiquetas HTML en la salida**
      - HTML con `<p>`, `<strong>`, `<ul><li>` visibles → salida no contiene `<` seguido de nombre de etiqueta
      - HTML con etiquetas ocultas eliminadas → salida no contiene `<span` ni `</span`
      - HTML vacío `""` → salida es `""`
      - **Validates: Requisitos 3.1, 3.2, 3.3, 3.4, 3.5, 3.7**
    - **Propiedad 3 (Property 3): Caracteres escapados aparecen como literales**
      - `<p>Términos &amp; condiciones</p>` → contiene `Términos & condiciones`
      - `<p>monto &lt; 100</p>` → contiene `monto < 100`
      - `<p>precio &gt; 0</p>` → contiene `precio > 0`
      - Texto plano con `&` literal → texto sin modificar
      - **Validates: Requisito 3.7**
    - Cubrir variantes del Requisito 13.4: `display:none`, `DISPLAY:NONE`, `display: none`, `display:none;`, `visibility:hidden`, `opacity:0`, `font-size:0`, atributo booleano `hidden`, `aria-hidden="true"`, `font-size:0px`, `font-size:0em`, `font-size:0pt`
    - _Requisitos: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 13.4_

- [x] 2. Implementar protocolo `ClienteHTTP` y `_ClienteHTTPReal`
  - [x] 2.1 Añadir en `azure_devops.py` el protocolo `ClienteHTTP` y la implementación real
    - Definir el protocolo duck-typing `ClienteHTTP` con método `solicitar(metodo, url, cuerpo, cabeceras) -> tuple[int, bytes]`
    - Implementar `_ClienteHTTPReal`: usa `urllib.request.Request` + `urlopen` con `timeout=30`
    - Construir el encabezado `Authorization: Basic <base64(:<PAT>)>` dentro del cuerpo de `solicitar`, sin almacenarlo en ningún atributo de instancia ni en `__repr__`
    - _Requisitos: 1.5, 9.6, 16.2_

  - [-] 2.2 Crear `ClienteHTTPFalso` en `tests/test_azure_devops.py`
    - Implementar `ClienteHTTPFalso` con lista de respuestas pregrabadas `list[tuple[int, bytes]]`
    - El simulacro registra todas las llamadas en `self.llamadas: list[dict]` con `{metodo, url, cuerpo, cabeceras}`
    - Lanza `AssertionError` si se agotan las respuestas pregrabadas
    - _Requisitos: 13.1_

- [x] 3. Implementar construcción del adaptador (`desde_configuracion`)
  - [x] 3.1 Implementar `BacklogAzureDevOps` y su método de clase `desde_configuracion`
    - Implementar la clase `BacklogAzureDevOps(PuertoBacklog)` con sus atributos de configuración
    - Leer `tipo_work_item`, `mapeo_area_sistema`, `sistema_por_defecto`, `etiquetas` y `poller` del archivo JSON en `ruta_config`
    - Leer `AZDO_ORG_URL`, `AZDO_PROJECT` y `AZDO_PAT` del entorno; lanzar `ErrorBacklog` con el nombre exacto de la variable si alguna está ausente o vacía (sin incluir el valor del PAT en el mensaje)
    - Si el archivo no existe o el JSON es inválido, lanzar `ErrorBacklog` con la ruta y el motivo
    - Aceptar `cliente_http` y `dormir` como argumentos opcionales para inyección en pruebas
    - _Requisitos: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [~] 3.2 Escribir pruebas de construcción del adaptador
    - Prueba: construcción exitosa con archivo JSON válido y variables de entorno presentes
    - Prueba: `ErrorBacklog` con nombre exacto de la variable cuando `AZDO_ORG_URL` está ausente
    - Prueba: `ErrorBacklog` cuando `AZDO_PROJECT` está vacía tras eliminar espacios
    - Prueba: `ErrorBacklog` cuando `AZDO_PAT` está ausente; verificar que el mensaje no contiene el valor del PAT
    - Prueba: `ErrorBacklog` cuando el archivo JSON no existe (incluye ruta en el mensaje)
    - Prueba: `ErrorBacklog` cuando el archivo contiene JSON inválido
    - Prueba: `BacklogAzureDevOps` implementa todos los métodos abstractos de `PuertoBacklog`
    - _Requisitos: 1.1, 1.2, 1.3, 1.4, 1.6, 16.2_

- [x] 4. Implementar `leer_historia` con saneamiento y mapeo de Area Path
  - [~] 4.1 Implementar `leer_historia` en `BacklogAzureDevOps`
    - Validar que `id` es un entero positivo; lanzar `HistoriaNoEncontrada` sin llamada HTTP si no lo es
    - Construir la URL del endpoint `GET /{org}/{project}/_apis/wit/workitems/{id}?api-version=7.1`
    - Verificar que `System.WorkItemType` coincide con `tipo_work_item`; lanzar `HistoriaNoEncontrada` si no coincide
    - Aplicar `_sanear_html` a `System.Description` y `Microsoft.VSTS.Common.AcceptanceCriteria`
    - Implementar el mapeo de `System.AreaPath` a `Historia.sistema` con el prefijo más largo (segmentos separados por `\`, insensible a mayúsculas); usar `sistema_por_defecto` y escribir advertencia en stderr si no hay coincidencia
    - Mapear solo los campos de `Historia` listados en el diseño; no copiar `System.CreatedBy`, `System.ChangedBy` ni ningún otro campo
    - Establecer `Historia.id` como cadena del id numérico y `Historia.proyecto` con el valor de `AZDO_PROJECT`
    - _Requisitos: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 16.1, 16.3_

  - [~] 4.2 Escribir pruebas de `leer_historia` y de la Propiedad 4 (filtrado de campos de autor)
    - Preparar fixture con respuesta grabada del work item 10 (D-030) con `System.CreatedBy` y `System.ChangedBy` eliminados del fixture real; afirmar que `Historia.texto` no contiene `"Instrucción del sistema"` ni ninguna subcadena del `<span>` oculto
    - **Propiedad 4 (Property 4): Historia no contiene campos de autor**
      - Fixture `tests/datos/azure/wi_10.json`: este archivo es la respuesta real de la API del work item 10 de la organización de prueba (D-030), con `System.CreatedBy` y `System.ChangedBy` eliminados. **No generarlo ni llamar a la API**: el archivo ya existirá creado por el equipo antes de ejecutar las pruebas. La prueba lo carga y verifica que `Historia.texto` no contiene `"Instrucción del sistema"` ni ninguna subcadena del `<span>` oculto.
      - Fixture sintético: respuesta de API fabricada con `System.CreatedBy = "Alice"` y `System.ChangedBy = "Bob"` como valores literales falsos, para verificar que esos campos no llegan a ningún atributo de `Historia`.
      - Respuesta de `listar_pendientes` con dos work items que tienen campos de autor: ningún objeto `Historia` contiene valores de esos campos.
      - **Validates: Requisitos 2.2, 16.2**
    - **Propiedad 5 (Property 5): Mapeo con prefijo más largo**
      - `mapeo = {"Proyecto\Core": "core", "Proyecto\Core\Pagos": "pagos"}`, Area Path `"Proyecto\Core\Pagos\Tarjetas"`: resultado `"pagos"`
      - `mapeo = {"Proyecto\Core": "core"}`, Area Path `"Proyecto\CoreLegacy"`: resultado `sistema_por_defecto`
      - Area Path en mayúsculas con mapeo en minúsculas: coincide (insensible a mayúsculas)
      - **Validates: Requisito 2.6**
    - Prueba: `HistoriaNoEncontrada` cuando id es cadena vacía, no numérico o entero no positivo (sin llamada HTTP)
    - Prueba: `HistoriaNoEncontrada` cuando la API devuelve HTTP 404
    - Prueba: `HistoriaNoEncontrada` cuando `System.WorkItemType` no coincide con `tipo_work_item`
    - Prueba: advertencia en stderr cuando Area Path no coincide con ningún prefijo
    - Prueba: `Historia.id` y `Historia.proyecto` se establecen correctamente
    - _Requisitos: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 13.2, 13.7, 16.3_

- [x] 5. Implementar resiliencia HTTP (reintentos, backoff, códigos de error)
  - [~] 5.1 Implementar política de reintentos en `_ClienteHTTPReal` y en el adaptador
    - Añadir método interno `_solicitar_con_reintentos` para peticiones idempotentes (GET, WIQL): backoff exponencial 0 s → 1 s → 2 s → 4 s entre intentos (hasta 4 intentos)
    - Si la respuesta incluye `Retry-After: N`, esperar `max(backoff_calculado, N)` segundos antes del siguiente intento
    - Tras el cuarto intento fallido, lanzar `ErrorBacklog` con el código HTTP y el número de intentos
    - 401/403: `ErrorBacklog` inmediato (sin reintentos) con el código HTTP y sugerencia de verificar alcance del PAT; sin ninguna subcadena del PAT en el mensaje
    - 404: `HistoriaNoEncontrada` inmediato (sin reintentos)
    - Timeout de 30 s: si la petición idempotente supera el timeout, reintentar; si no es idempotente, `ErrorBacklog` inmediato
    - POST de comentarios: no reintentar por timeout ni por 5xx
    - Usar la función `dormir` inyectable en lugar de `time.sleep`
    - _Requisitos: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.8, 16.1_

  - [~] 5.2 Escribir pruebas de resiliencia HTTP y Propiedad 6 (PAT ausente en errores)
    - **Propiedad 6 (Property 6): PAT ausente en mensajes de error**
      - Error HTTP 401 con PAT `"mi-pat-secreto"`: el mensaje de `ErrorBacklog` no contiene `"mi-pat-secreto"`
      - Error HTTP 403: mismo comportamiento
      - Variable `AZDO_PAT` ausente: mensaje menciona `"AZDO_PAT"` pero no contiene ningún valor de PAT
      - **Validates: Requisitos 9.3, 16.2**
    - **Propiedad 10 (Property 10): Backoff exponencial en reintentos idempotentes**
      - 1 fallo 429 + éxito: `dormir` llamado una vez con `1`
      - 2 fallos 500 + éxito: `dormir` llamado con `1` y luego con `2`
      - 3 fallos 429 + éxito: `dormir` llamado con `1`, `2` y `4`
      - 4 fallos consecutivos: se lanza `ErrorBacklog` tras el cuarto intento
      - **Validates: Requisito 9.1**
    - Prueba: HTTP 429 reintenta y tiene éxito en el segundo intento devolviendo `Historia` válida
    - Prueba: HTTP 500 reintenta hasta 3 veces antes de lanzar `ErrorBacklog`
    - Prueba: `Retry-After` anula backoff calculado cuando es mayor
    - Prueba: timeout en petición idempotente → reintento; timeout en POST → `ErrorBacklog` inmediato
    - _Requisitos: 9.1, 9.2, 9.3, 9.4, 9.5, 9.8, 13.3_

- [x] 6. Implementar `buscar_similares` (WIQL, batch, TF-IDF)
  - [~] 6.1 Implementar `buscar_similares` en `BacklogAzureDevOps`
    - Construir y ejecutar exactamente una consulta WIQL sobre `POST /{org}/{project}/_apis/wit/wiql?api-version=7.1` para obtener las 200 User Stories más recientes del proyecto (ordenadas por `System.CreatedDate` descendente)
    - Obtener el contenido completo en lotes usando el endpoint de lote `POST /_apis/wit/workitemsbatch?api-version=7.1` con los campos necesarios
    - Aplicar `_sanear_html` a la descripción de cada work item antes de pasarlo al índice
    - Instanciar `revisor.backlog.similitud.IndiceSimilitud` y llamar a `buscar(texto, limite)` para las puntuaciones; no implementar un algoritmo de clasificación separado
    - Excluir de los resultados la HU cuyo texto saneado sea idéntico al texto buscado (reconocimiento de la propia HU)
    - Devolver `list[HistoriaSimilar]` con `similitud` como `float` en [0.0, 1.0], nunca `None`
    - Devolver lista vacía si la WIQL devuelve cero resultados
    - _Requisitos: 4.1, 4.2, 4.3, 4.4, 4.5, 16.4_

  - [~] 6.2 Escribir pruebas de `buscar_similares`
    - Prueba: se ejecuta exactamente una WIQL y el batch obtiene los campos requeridos
    - Prueba: `similitud` de cada `HistoriaSimilar` es `float` en [0.0, 1.0], no `None`
    - Prueba: lista ordenada de mayor a menor similitud
    - Prueba: saneamiento HTML aplicado antes de pasar texto al índice (texto oculto no llega al índice)
    - Prueba: lista vacía cuando WIQL devuelve cero work items (sin error, sin llamadas adicionales)
    - Prueba: la HU cuyo texto es idéntico al buscado se excluye de los resultados
    - Prueba: ningún objeto `Historia` en los resultados contiene valores de `System.CreatedBy` o `System.ChangedBy`
    - _Requisitos: 4.1, 4.2, 4.3, 4.4, 4.5, 13.7, 16.4_

- [x] 7. Implementar `listar_pendientes` (WIQL con filtro de etiqueta y ventana de días)
  - [~] 7.1 Implementar `listar_pendientes` en `BacklogAzureDevOps`
    - Construir y ejecutar una WIQL que seleccione solo User Stories de tipo `tipo_work_item` sin la etiqueta `etiquetas.revisada`, con `System.CreatedDate` dentro de los últimos `poller.ventana_dias` días (inclusive del día actual), ordenadas por `System.CreatedDate` ascendente
    - Devolver lista vacía si `limite <= 0` sin ninguna llamada HTTP
    - Si la WIQL devuelve cero resultados, devolver lista vacía sin llamadas adicionales
    - Obtener solo los primeros `limite` resultados de la WIQL antes de hacer el lote batch
    - Establecer `Historia.id` como cadena del id y `Historia.proyecto` con el valor de `AZDO_PROJECT` para cada `Historia` construida
    - _Requisitos: 8.1, 8.2, 8.3, 8.4, 16.3_

  - [~] 7.2 Escribir pruebas de `listar_pendientes`
    - Prueba: WIQL incluye filtro de etiqueta ausente y ventana de días en la consulta
    - Prueba: se devuelven como máximo `limite` elementos aunque la WIQL retorne más
    - Prueba: lista vacía cuando WIQL devuelve cero resultados (sin llamadas adicionales)
    - Prueba: lista vacía cuando `limite` es cero o negativo (sin ninguna llamada HTTP)
    - Prueba: `Historia.id` y `Historia.proyecto` se establecen correctamente en cada elemento
    - Prueba: ningún objeto `Historia` contiene valores de `System.CreatedBy` o `System.ChangedBy`
    - _Requisitos: 8.1, 8.2, 8.3, 8.4, 13.7, 16.3_

- [x] 8. Implementar `registrar_revision` (deduplicación paginada, comentario HTML, PATCH etiquetas)
  - [~] 8.1 Implementar `registrar_revision` en `BacklogAzureDevOps`
    - Implementar deduplicación paginada: obtener todos los comentarios del work item siguiendo `continuationToken` hasta que no haya más páginas usando `GET /_apis/wit/workItems/{id}/comments?api-version=7.1-preview.4`
    - Si algún comentario contiene `[RevisorHU]`: actualizar solo etiquetas faltantes en `System.Tags` y devolver la referencia del comentario existente
    - Construir el cuerpo del comentario HTML siguiendo exactamente el formato del diseño; escapar con `html.escape()` todos los valores dinámicos (decisión, defectos, recomendaciones, historia refinada, criterios de aceptación)
    - Incluir la cadena literal `[RevisorHU]` y la `marca` de ejecución en el cuerpo del comentario
    - Publicar el comentario con `POST /_apis/wit/workItems/{id}/comments?api-version=7.1-preview.4`
    - Leer las etiquetas actuales del work item, añadir `etiquetas.revisada` y `etiquetas.por_decision[revision.decision]`, y enviar JSON Patch con exactamente una operación sobre `/fields/System.Tags` usando `PATCH /_apis/wit/workitems/{id}?api-version=7.1`
    - No escribir `revision.estimacion` en `Microsoft.VSTS.Scheduling.StoryPoints`; solo incluirlo en el texto del comentario
    - Devolver cadena no vacía con la URL o id numérico del comentario creado
    - _Requisitos: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 9.7_

  - [~] 8.2 Escribir pruebas de `registrar_revision` y Propiedades 7, 8 y 9
    - **Propiedad 7 (Property 7): JSON Patch contiene exactamente una operación en `/fields/System.Tags`**
      - `Revision` con decisión `"aceptar"`: el Patch capturado tiene exactamente 1 elemento, `path == "/fields/System.Tags"`
      - `Revision` con decisión `"devolver"` y varios defectos: mismo comportamiento
      - `Revision` con decisión `"dividir"`: mismo comportamiento
      - **Validates: Requisitos 5.3, 5.4**
    - **Propiedad 8 (Property 8): Preservación de etiquetas existentes**
      - Work item sin etiquetas previas, decisión `"devolver"`: tags resultantes contienen `"ia-revisada"` e `"ia-devolver"`
      - Work item con etiquetas previas `"sprint-5; urgente"`, decisión `"aceptar"`: contienen `"sprint-5"`, `"urgente"`, `"ia-revisada"` e `"ia-aceptar"`
      - Work item con `"ia-revisada"` ya presente: no se duplica
      - **Validates: Requisito 5.2**
    - **Propiedad 9 (Property 9): Deduplicación de comentarios**
      - Primera llamada: lista vacía → se publica el comentario
      - Segunda llamada (reintento): lista con `[RevisorHU]` existente → no se publica segundo comentario; solo se actualizan etiquetas faltantes
      - Segunda llamada con `run_id` distinto: mismo comportamiento (deduplicación no depende del `run_id`)
      - **Validates: Requisito 9.7**
    - Prueba: el cuerpo del comentario capturado contiene todos los campos de `Revision` (decisión, defectos, recomendaciones, historia refinada, criterios de aceptación, estimación, descargo)
    - Prueba: JSON Patch capturado no contiene operaciones sobre `System.State`, `StoryPoints` ni ningún otro campo
    - _Requisitos: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 9.7, 13.5_

- [x] 9. Implementar `proponer_division` y `aprobar_para_fabrica`
  - [~] 9.1 Implementar `proponer_division` en `BacklogAzureDevOps`
    - Implementar deduplicación paginada con la misma lógica de `registrar_revision` (seguir `continuationToken`)
    - Construir el cuerpo del comentario HTML con el formato del diseño (sección "Propuesta de división"); escapar cada cadena de `partes` con `html.escape()`
    - Incluir `[RevisorHU]` y la `marca` en el cuerpo
    - No crear work items hijos, subtareas ni work items vinculados
    - Devolver cadena no vacía con la URL o id numérico del comentario
    - _Requisitos: 6.1, 6.2, 6.3, 6.4_

  - [~] 9.2 Implementar `aprobar_para_fabrica` en `BacklogAzureDevOps`
    - Lanzar `OperacionProhibida` como primera acción, antes de cualquier otro código en el cuerpo del método
    - _Requisitos: 7.1, 7.2, 7.3_

  - [~] 9.3 Escribir pruebas de `proponer_division` y `aprobar_para_fabrica`
    - Prueba: el comentario de `proponer_division` lista cada parte, incluye `[RevisorHU]` y está escapado con HTML
    - Prueba: `proponer_division` no realiza peticiones que creen work items (ninguna llamada a endpoint de work items para crear)
    - Prueba de humo: `aprobar_para_fabrica` lanza `OperacionProhibida` y el `ClienteHTTPFalso` registra cero llamadas
    - Prueba: `aprobar_para_fabrica` lanza `OperacionProhibida` incluso cuando se pasa un id válido
    - _Requisitos: 6.1, 6.2, 6.3, 6.4, 7.1, 7.2, 13.6_

- [x] 10. Crear muestra de ataque y su prueba
  - [~] 10.1 Crear `datos/ataques/ataque_comentario_html.json`
    - Crear el archivo con una Historia sintética cuyo campo `System.Description` incluya una instrucción oculta en un comentario HTML con la forma `<!-- [texto de instrucción] -->`
    - El archivo debe representar una respuesta de la API de Azure DevOps (formato de work item) para que la prueba pueda pasarlo directamente por `_sanear_html`
    - _Requisitos: 14.1_

  - [~] 10.2 Escribir prueba de la muestra de ataque
    - Cargar `datos/ataques/ataque_comentario_html.json`, pasar el valor de `System.Description` por `_sanear_html`
    - Afirmar que la salida no contiene el texto de instrucción del comentario HTML
    - Afirmar que la salida no contiene las subcadenas `<!--` ni `-->`
    - _Requisitos: 14.2, 14.3_

- [~] 11. Checkpoint — Pruebas del adaptador en verde
  - Ejecutar `pytest tests/test_azure_devops.py -v` y confirmar que todas las pruebas pasan sin red.
  - Asegurarse de que `pytest tests/test_config_azure.py` pasa sin modificaciones.
  - Verificar que el monkeypatch que bloquea `urlopen` real no lanza `AssertionError` en ninguna prueba.

- [x] 12. Implementar `AprobadorDesatendido` y crear `src/revisor/integracion/__init__.py`
  - [~] 12.1 Implementar `AprobadorDesatendido` en `src/revisor/integracion/poller_azure.py`
    - Crear `src/revisor/integracion/__init__.py` vacío (marca el paquete Python)
    - Crear `src/revisor/integracion/poller_azure.py` con la clase `AprobadorDesatendido`
    - Definir `BLOQUEADAS = frozenset({"backlog__aprobar_para_fabrica"})` como atributo de clase
    - Implementar `__init__(self, escrituras_desatendidas: list[str])`: almacenar como `frozenset`
    - Implementar `__call__(self, nombre, argumentos) -> tuple[bool, str]`:
      - Si `nombre in BLOQUEADAS`: devolver `(False, "'{nombre}' está bloqueada por AprobadorDesatendido sin importar la lista")`
      - Si `nombre in self._permitidas`: devolver `(True, "aprobada por la lista desatendida (config/azure_devops.json)")`
      - Si no: devolver `(False, "'{nombre}' no está en escrituras_desatendidas")`
    - _Requisitos: 12.1, 12.2, 12.3_

  - [~] 12.2 Escribir pruebas de `AprobadorDesatendido` en `tests/test_poller_azure.py`
    - Crear `tests/test_poller_azure.py` con monkeypatch que bloquea `urlopen` real y stubs de `bucle.ejecutar`
    - **Propiedad 12 (Property 12): Aprobador desatendido**
      - `h = "backlog__registrar_revision"` en `escrituras_desatendidas`: devuelve `(True, ...)`
      - `h = "backlog__leer_historia"` fuera de la lista: devuelve `(False, ...)`
      - `h = "backlog__aprobar_para_fabrica"` fuera de la lista: devuelve `(False, ...)`
      - `h = "backlog__aprobar_para_fabrica"` dentro de la lista (configuración errónea): devuelve `(False, ...)` de todas formas
      - **Validates: Requisitos 12.1, 12.2, 12.3**
    - _Requisitos: 12.1, 12.2, 12.3_

- [x] 13. Implementar el ciclo del Poller
  - [~] 13.1 Implementar el ciclo principal del Poller en `poller_azure.py`
    - Añadir punto de entrada `python -m revisor.integracion.poller_azure` con `argparse`; aceptar `--una-vez`, `--real` y `--config skill|base` (por defecto `skill`)
    - Cargar `.env` con `load_dotenv(Path(".env"))` antes de construir `BacklogAzureDevOps`
    - Si `--real`: imprimir en stdout el valor de `poller.max_hu_por_ciclo` y el aviso `"US$0.15–0.25 por historia"` antes de cualquier llamada al modelo
    - Llamar a `BacklogAzureDevOps.listar_pendientes(poller.max_hu_por_ciclo)` directamente (no a través del servidor MCP) para obtener las historias candidatas de cada ciclo
    - Para cada HU: llamar a `asyncio.run(bucle.ejecutar(Opciones(...)))` con un event loop nuevo por HU; pasar `caso`, `config`, `simulado=not args.real`, `archivo_config=Path("config/config_azure.json")`, `aprobador=AprobadorDesatendido(escrituras_desatendidas)`
    - Si `--una-vez`: ejecutar exactamente un ciclo y salir con código 0
    - Sin `--una-vez`: dormir `poller.intervalo_minutos` minutos entre ciclos; capturar SIGINT para salir con código 0 después de completar la HU en curso
    - Escribir cada traza en `trazas/azure/` (el campo `carpeta_trazas` de `config_azure.json`)
    - _Requisitos: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8_

  - [~] 13.2 Implementar gestión del `Registro_Procesados` en el Poller
    - Leer el archivo JSON del `Registro_Procesados` al inicio de cada ciclo (crear si no existe)
    - Omitir ids cuya entrada sea una cadena (completado) o un objeto con `"fallido": true` (fallido definitivo)
    - Reintentar ids cuya entrada sea `{"fallos": 1, "motivo": "..."}` (primer fallo)
    - Al terminar una HU con éxito (`motivo_cierre == "end_turn"` y `decision != None`): escribir `{id: run_id}` en el registro
    - Al primer fallo (excepción, `motivo_cierre != "end_turn"` o `decision == None`): escribir `{"fallos": 1, "motivo": motivo}` y registrar en stderr con id del work item y motivo
    - Al segundo fallo consecutivo: escribir `{"fallido": true, "motivo": motivo}` en el registro
    - Escribir el archivo JSON de forma atómica (write-then-rename) para evitar corrupción
    - _Requisitos: 11.2, 11.3, 11.4_

  - [~] 13.3 Escribir pruebas del Poller y Propiedades 11 y 12
    - **Propiedad 11 (Property 11): Idempotencia del Poller**
      - Id presente como cadena (completado): `ejecutar` no se llama
      - Id presente con `{"fallido": true, ...}` (fallido definitivo): `ejecutar` no se llama
      - Id presente con `{"fallos": 1, ...}` (primer fallo): `ejecutar` sí se llama (reintento)
      - Id ausente del registro (nuevo): `ejecutar` sí se llama
      - **Validates: Requisitos 11.1, 11.2**
    - Prueba: `--una-vez` ejecuta exactamente un ciclo y sale con código 0
    - Prueba: en modo simulado (`sin --real`), `ANTHROPIC_API_KEY` no se pasa y no se llama a la API de Anthropic
    - Prueba: en modo `--real`, se imprime el aviso de costo antes de llamar al modelo
    - Prueba: el Registro_Procesados escribe la entrada correcta tras éxito, primer fallo y segundo fallo
    - Prueba: el Registro_Procesados se escribe de forma atómica (el archivo temporal no queda huérfano)
    - _Requisitos: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 11.1, 11.2, 11.3, 11.4_

- [~] 14. Checkpoint — Todas las pruebas en verde
  - Ejecutar `pytest tests/test_azure_devops.py tests/test_poller_azure.py tests/test_config_azure.py -v` y confirmar que todas pasan.
  - Confirmar que las pruebas existentes no se rompieron: `pytest --ignore=tests/test_azure_devops.py --ignore=tests/test_poller_azure.py -v`.

- [x] 15. Actualizar documentación
  - [~] 15.1 Actualizar `docs/ARQUITECTURA.md`
    - Actualizar el diagrama Mermaid existente para incluir `BacklogAzureDevOps` y `Poller` como nodos distintos
    - Añadir flechas etiquetadas que indiquen la dirección de cada llamada: `Poller → BacklogAzureDevOps (listar_pendientes)`, `Poller → bucle.ejecutar (asyncio.run)`, `servidor_backlog MCP → BacklogAzureDevOps (PuertoBacklog)`
    - _Requisitos: 15.1_

  - [~] 15.2 Actualizar `docs/DECISIONES.md`
    - Añadir entradas D-AZ-01 a D-AZ-08 tomadas del diseño (`design.md` sección "Decisiones de diseño")
    - Incluir los endpoints de la API REST de Azure DevOps y las cadenas `api-version` elegidas
    - Incluir la política de reintentos (máximo de intentos, fórmula de backoff y manejo de `Retry-After`)
    - _Requisitos: 15.2_

  - [~] 15.3 Actualizar `README.md` con la sección "Azure DevOps"
    - Añadir sección con los nombres y valores esperados de `AZDO_ORG_URL`, `AZDO_PROJECT` y `AZDO_PAT`
    - Incluir el alcance mínimo requerido del PAT: "Work Items: Read & write"
    - Incluir los comandos exactos: `python -m revisor.integracion.poller_azure --una-vez` (simulado) y `python -m revisor.integracion.poller_azure --una-vez --real` (real)
    - _Requisitos: 15.3_

  - [~] 15.4 Actualizar `docs/USO_IA.md`
    - Añadir nueva entrada para esta funcionalidad con: archivos creados o modificados por Kiro, pruebas ejecutadas para verificar la corrección y resultado de esas pruebas (recuentos pase/fallo o salida del comando de prueba)
    - _Requisitos: 15.4_

## Notes

- Cada tarea hace referencia a los requisitos específicos para trazabilidad.
- Las pruebas nunca abren sockets: todas usan `ClienteHTTPFalso` y el monkeypatch que bloquea `urllib.request.urlopen` real.
- El código, los docstrings y los comentarios van en español.
- No se modifica ningún archivo existente del agente, la política, la Skill, el catálogo ni los servidores MCP.
- No se añaden dependencias nuevas: solo biblioteca estándar Python 3.11 + `python-dotenv` (ya declarada).
- Las pruebas de propiedad usan `@pytest.mark.parametrize`, no Hypothesis.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "2.1"] },
    { "id": 2, "tasks": ["2.2", "3.1"] },
    { "id": 3, "tasks": ["3.2", "4.1"] },
    { "id": 4, "tasks": ["4.2", "5.1"] },
    { "id": 5, "tasks": ["5.2", "6.1"] },
    { "id": 6, "tasks": ["6.2", "7.1"] },
    { "id": 7, "tasks": ["7.2", "8.1"] },
    { "id": 8, "tasks": ["8.2", "9.1", "9.2", "10.1"] },
    { "id": 9, "tasks": ["9.3", "10.2"] },
    { "id": 10, "tasks": ["12.1"] },
    { "id": 11, "tasks": ["12.2", "13.1"] },
    { "id": 12, "tasks": ["13.2"] },
    { "id": 13, "tasks": ["13.3"] },
    { "id": 14, "tasks": ["15.1", "15.2", "15.3", "15.4"] }
  ]
}
```
