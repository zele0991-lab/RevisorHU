# Registro de decisiones

Una entrada por decisión, con fecha, contexto, decisión y consecuencias. Las decisiones no se
borran: si una cambia, se agrega una entrada nueva que la reemplaza y se indica en la anterior.

---

## D-001 · Python 3.11 con `venv` + `pip`
- **Fecha:** 2026-11-09
- **Contexto:** el prompt pide usar `uv` si está instalado. En la máquina de desarrollo no lo está; Python 3.11.9 sí.
- **Decisión:** `.venv` creado con `python -m venv` y dependencias instaladas con `pip install -e .[dev]` desde `pyproject.toml`.
- **Consecuencias:** cualquier integrante reproduce el entorno sin instalar herramientas extra. Si más adelante se adopta `uv`, `pyproject.toml` sirve igual.

## D-002 · Bucle manual de tool use con el SDK `anthropic`
- **Fecha:** 2026-11-09
- **Contexto:** el Tool Runner del SDK ejecuta las herramientas por su cuenta.
- **Decisión:** bucle manual, como el `agente.py` del kit.
- **Consecuencias:** en cada llamada podemos aplicar la política, contar topes y escribir la traza. Cuesta algo más de código.

## D-003 · Servidores MCP con el SDK oficial `mcp` (MCPServer, antes FastMCP) por stdio
- **Fecha:** 2026-11-09
- **Contexto:** el kit habla MCP a mano. Queremos conectar los mismos servidores a Claude Code y a Kiro para probarlos.
- **Decisión:** `MCPServer` (en mcp 2.x, FastMCP pasó a llamarse así; actualizado en F1) para los servidores y el cliente stdio del SDK en el host. Los servidores se registran en `.mcp.json` y en `.kiro/settings/mcp.json`.
- **Consecuencias:** esquemas generados de forma estándar y servidores reutilizables fuera del agente.

## D-004 · Backlog detrás de un puerto con adaptadores
- **Fecha:** 2026-11-09
- **Contexto:** el experimento necesita un backlog local reproducible, y el banco usa Azure DevOps.
- **Decisión:** `src/revisor/backlog/puerto.py` define `PuertoBacklog`, con `BacklogLocal` (F1) y `BacklogAzureDevOps` (F7, Kiro). **El servidor MCP valida; el puerto solo persiste.** El puerto incluye `listar_pendientes` para el poller.
- **Consecuencias:** cambiar de backend no toca el agente, la política, la Skill ni los servidores. La validación es la misma para los dos backends.

## D-005 · Azure DevOps por polling WIQL, sin webhooks
- **Fecha:** 2026-11-09
- **Contexto:** un Service Hook necesita una URL pública, lo que en el banco implica abrir el firewall.
- **Decisión:** polling cada N minutos con una consulta WIQL sobre las HU sin la etiqueta `ia-revisada`.
- **Consecuencias:** solo hay conexiones salientes, pero la revisión no es instantánea. El webhook queda como mejora futura; el agente no cambia.

## D-006 · El agente nunca aprueba
- **Fecha:** 2026-11-09
- **Contexto:** en un banco, aprobar y revisar deben ser funciones separadas.
- **Decisión:**
  - `aprobar_para_fabrica` existe solo para probar la política y los ataques, y está **oculta** al modelo;
  - en Azure DevOps el adaptador lanza `OperacionProhibida` si se le pide aprobar, y nunca cambia `System.State`;
  - el agente solo comenta, etiqueta y sugiere story points.
- **Consecuencias:** un ataque exitoso puede, como mucho, sesgar una recomendación en borrador; no puede aprobar.

## D-007 · Las reglas son datos: `conocimiento/criterios.yaml`
- **Fecha:** 2026-11-09
- **Contexto:** la DoR todavía no existe y va a cambiar al validarla con los líderes técnicos.
- **Decisión:**
  - un único catálogo YAML con versión y fecha, cargado y validado solo por `catalogo.py`;
  - ningún id de criterio en el código, la Skill ni la política;
  - los ids son estables: un criterio retirado se marca obsoleto, no se borra;
  - la versión y el hash SHA-256 del catálogo se escriben en cada traza.
- **Consecuencias:** cambiar una regla no exige programar. Un catálogo inválido impide arrancar.

## D-008 · Borradores permitidos en el backlog local; con confirmación en Azure DevOps
- **Fecha:** 2026-11-09
- **Contexto:** el experimento corre sin una persona delante (80 casos × 2 configuraciones × 3 repeticiones = 480 ejecuciones). Una confirmación en cada escritura lo haría imposible y no aporta seguridad, porque el backlog local es desechable.
- **Decisión:** con `BacklogLocal`, `registrar_revision` y `proponer_division` van en **permitir**, con tope de 1 llamada por ejecución. Con Azure DevOps van en **confirmar**. `aprobar_para_fabrica` está oculta en los dos casos.
- **Consecuencias:** la política del experimento es la misma para las dos configuraciones. El modo desatendido de Azure DevOps (F7) tendrá su propia lista documentada.

## D-009 · Las trazas se versionan
- **Fecha:** 2026-11-09
- **Contexto:** la rúbrica H3 exige el repositorio con las trazas de todas las ejecuciones reportadas, y que toda cifra se regenere desde ellas.
- **Decisión:** `trazas/` se versiona. Las trazas no contienen secretos ni HU reales del banco.
- **Consecuencias:** el repositorio crece. Si llega a ser un problema, se evaluará comprimirlas.

## D-010 · Nombres `servidor__herramienta`
- **Fecha:** 2026-11-09
- **Contexto:** con tres servidores puede haber nombres repetidos, y `leer_traza.py` del kit usa este formato.
- **Decisión:** el host expone cada herramienta como `servidor__herramienta` (por ejemplo, `backlog__leer_historia`). La política usa esos nombres, con comodines.
- **Consecuencias:** compatibilidad con el kit y con su lector de trazas.

## D-011 · Sin HU reales del banco (prevalece el prompt sobre la propuesta)
- **Fecha:** 2026-11-09
- **Contexto:** la propuesta H1 admitía hasta 30 HU del banco, anonimizadas y con autorización escrita. El prompt de desarrollo prohíbe que una HU real del banco entre al repositorio o se envíe a la API.
- **Decisión (confirmada por Leonardo Zeledón):** prevalece el prompt. El experimento usa solo HU genéricas (Dalpiaz) y sintéticas. Es el plan B que la propuesta ya contemplaba ("El banco no autoriza usar historias reales").
- **Consecuencias:** el diseño experimental no cambia. Se puede revisar si el banco autoriza por escrito y el área de seguridad o cumplimiento aprueba a dónde va el texto; en ese caso, se agregaría una decisión nueva.

## D-012 · La estimación se mide sobre 30 HU de TAWOS aparte
- **Fecha:** 2026-11-09
- **Contexto:** el prompt no dice sobre qué casos se mide la estimación; la propuesta habla de 30 HU de TAWOS.
- **Decisión (confirmada por Leonardo Zeledón):** el error absoluto medio y la proporción de estimaciones a un paso de Fibonacci o menos se calculan sobre **30 HU de TAWOS con story points reales**, aparte del conjunto de exactitud. Los 80 casos de Dalpiaz miden la decisión, los defectos y el tipo.
- **Consecuencias:** F5 construye dos conjuntos. Las referencias que usa `servidor_estimacion` no pueden incluir esas 30 HU, para no filtrar la respuesta.

## D-013 · Herramientas adicionales respecto de la propuesta
- **Fecha:** 2026-11-09
- **Contexto:** la propuesta solo tenía `obtener_criterio(nombre)` en `servidor_conocimiento`. El prompt agrega `listar_criterios`, `buscar_guia`, `obtener_criterio(id)` y el servidor `servidor_estimacion`.
- **Decisión (confirmada por Leonardo Zeledón):** se tratan como una **ampliación** de la propuesta. `obtener_criterio` usa el id estable del catálogo en lugar del nombre.
- **Consecuencias:** la variable del experimento no cambia, porque las dos configuraciones tienen exactamente las mismas herramientas. En el artículo se describe la versión final.

## D-014 · Saltos de línea LF fijados con `.gitattributes`
- **Fecha:** 2026-11-09
- **Contexto:** git en Windows (`core.autocrlf=true`) convierte LF a CRLF al hacer checkout. Las trazas registran el hash SHA-256 de `SKILL.md`, `criterios.yaml` y el conjunto de datos.
- **Decisión:** `.gitattributes` con `* text=auto eol=lf`.
- **Consecuencias:** el mismo commit produce los mismos hashes en cualquier máquina. Además, los módulos que calculan hashes deben leer los archivos en modo binario.

## D-015 · Tipos de HU: por ahora solo `funcional`, definidos como datos
- **Fecha:** 2026-11-09
- **Contexto:** `registrar_revision` valida el `tipo` contra una lista cerrada. Esa misma lista la usan los anotadores y la métrica de exactitud del tipo.
- **Decisión (confirmada por Leonardo Zeledón):** "de momento" el único tipo es `funcional`. La lista **no** se escribe en el código: el servidor la obtiene de la fuente de reglas (`FuenteReglas.tipos_hu()`), que en F2 sale de `conocimiento/criterios.yaml`.
- **Consecuencias:** agregar un tipo es editar datos; hay una prueba que lo verifica. Mientras haya un solo tipo, la exactitud del tipo es trivial (100 %) y no aporta al artículo; se reportará solo si la lista crece antes de congelar el catálogo.

## D-016 · "Mismo rol" en una división = mismo rol entre las partes
- **Fecha:** 2026-11-09
- **Contexto:** las HU de Dalpiaz están en inglés ("As a user…") y las partes se redactan en español ("Como usuario…"). Comparar con el rol de la HU original fallaría por el idioma o por HU sin rol.
- **Decisión (confirmada por Leonardo Zeledón):** `proponer_division` exige que todas las partes compartan el mismo rol entre sí. La comparación ignora artículos, tildes y mayúsculas. La trazabilidad con la HU original queda registrada por su id en el borrador.
- **Consecuencias:** una división que cambia de persona usuaria (por ejemplo, cliente y cajero) se rechaza.

## D-017 · Reglas de validación de `registrar_revision` (interpretación del prompt)
- **Fecha:** 2026-11-09
- **Contexto:** el prompt fija las reglas generales; algunos detalles había que concretarlos.
- **Decisión:**
  - el servidor devuelve **todos** los errores juntos, para que el modelo corrija en un solo intento;
  - un rechazo **no consume** la única revisión permitida por HU y ejecución; solo una revisión registrada con éxito la consume;
  - `historia_refinada` es obligatoria al aceptar; al devolver o dividir puede ir vacía (por ejemplo, si falta información, para no inventar requisitos). Si viene, tiene que seguir el formato "Como…, quiero…, para…";
  - los criterios de aceptación, cuando vienen, siempre van en Gherkin en español (Dado … Cuando … Entonces …, en ese orden). Al aceptar se exige al menos uno;
  - al devolver se exige al menos un defecto y una recomendación. Con cualquier decisión, cada recomendación tiene que referenciar un defecto de la lista;
  - datos personales: correo; cédula (9 dígitos, con o sin guiones); teléfono de Costa Rica (+506 o dddd-dddd); IBAN CR; cuenta (10 o más dígitos); tarjeta (13 a 19 dígitos que pasan Luhn). Un número suelto de 8 dígitos **no** se toma como teléfono, para no rechazar montos. El mensaje de error enmascara el dato.
- **Consecuencias:** hay una prueba por cada regla en `tests/test_servidor_backlog.py`.

## D-018 · Búsqueda de similares por TF-IDF y cambios al puerto
- **Fecha:** 2026-11-09
- **Contexto:** las pruebas no usan la red y el experimento tiene que ser determinista.
- **Decisión:** `BacklogLocal` usa TF-IDF con coseno, en Python puro (`backlog/similitud.py`). El puerto cambia en dos puntos:
  - `buscar_similares` devuelve `HistoriaSimilar(historia, similitud | None)`, porque la similitud ayuda a reconocer duplicados (Azure DevOps puede devolver `None`);
  - `Historia.titulo` pasa a ser opcional, porque los casos de evaluación no traen título.
- **Consecuencias:** la propia HU aparece en sus resultados; la descripción de la herramienta le dice al modelo que la reconozca por su id. Los metadatos de investigación de los casos (`es_dificil`, `motivo_dificultad`) nunca salen del backlog.

## D-019 · El tope de la política cuenta solo las escrituras aceptadas (implementado en F3)
- **Fecha:** 2026-11-09
- **Contexto:** en el kit, `Politica.registrar` cuenta toda llamada permitida, aunque el servidor la rechace. Con un tope de 1 para `registrar_revision`, un primer intento rechazado por validación bloquearía la corrección, y el agente no podría registrar nada.
- **Decisión (implementada en F3, `Politica.registrar_aceptada`):** el contador de topes cuenta solo las llamadas que el servidor aceptó (`es_error = false`). Los intentos rechazados quedan en la traza y se reportan.
- **Consecuencias:** se mantiene "una revisión por ejecución", y el servidor la refuerza por su lado.

## D-020 · Diseño del catálogo de criterios (v0, versión 0.1.0)
- **Fecha:** 2026-11-09
- **Contexto:** la sección 4.1 del prompt pide un catálogo con validación estricta, en el que los sistemas y las categorías se validen contra lo que dice el catálogo, no contra el código.
- **Decisión:**
  - **Cabecera con listas declaradas:** `categorias`, `sistemas` y `tipos_hu` se declaran en el YAML. Así un error de escritura (`aplica_a: [banca_movl]`) se detecta al cargar, en vez de dejar sin efecto el criterio sin avisar. Agregar un sistema o una categoría es editar la cabecera.
  - **`todos` es un sistema válido en las consultas:** es el valor para una HU sin sistema mapeado (lo usará el conector de Azure DevOps en F7) y devuelve solo los criterios generales. No se puede declarar como sistema ni combinar con otros en `aplica_a`.
  - **Validaciones adicionales al prompt:** se rechazan los campos desconocidos (detectan errores de escritura); un criterio activo no puede tener `reemplazado_por`; la cadena de reemplazos tiene que terminar en un criterio activo (sin ciclos).
  - **Qué queda en el código:** solo la semántica fija del esquema: severidades (bloqueante, mayor, menor), estados (activo, obsoleto) y el formato del id (2 a 5 mayúsculas, guion, 3 dígitos).
  - **Versión `0.1.0` (borrador):** el prompt pide congelar en `1.0.0` con un tag de git antes de etiquetar (F5).
  - **Contenido v0:** 27 criterios. Son 17 generales (9 de QUS, 5 de INVEST, 3 de DoR) y 10 de banca móvil. No se solapan entre sí, para no confundir a los anotadores. `core` todavía no tiene criterios propios.
- **Consecuencias:** las descripciones de `listar_criterios` y `registrar_revision` incluyen los sistemas, las categorías y los tipos del catálogo; si el catálogo cambia, cambia el texto de las herramientas. Eso queda registrado por el hash del catálogo en cada traza.

## D-021 · Referencias de estimación sintéticas hasta F5
- **Fecha:** 2026-11-09
- **Contexto:** el subconjunto de TAWOS se descarga y construye en F5, pero `servidor_estimacion` se implementa en F2.
- **Decisión:** `datos/ejemplo/referencias_ejemplo.jsonl` (12 HU sintéticas, marcadas `"fuente": "sintetico"`) se usa en las pruebas y en `.mcp.json` mientras tanto. En F5 se genera el archivo de TAWOS **sin** las 30 HU reservadas para medir la estimación (D-012), y la configuración del experimento apunta a ese archivo.
- **Consecuencias:** ninguna corrida del experimento debe usar las referencias sintéticas. Se verificará en F6 con el hash del conjunto de datos de la traza.

## D-022 · Ningún id de criterio fuera del YAML, ni siquiera en las guías
- **Fecha:** 2026-11-09
- **Contexto:** el principio "agregar o cambiar un criterio = editar el YAML" se rompe si un id queda escrito en otro lugar.
- **Decisión:** una prueba (`test_catalogo.py`) busca cada id del catálogo en `src/`, `config/`, `skills/` y en las guías `conocimiento/*.md`, y falla si aparece. Las guías explican los marcos sin citar ids. Las pruebas pueden usar ids en catálogos de prueba; el catálogo real no se cita.
- **Consecuencias:** también cubre la regla del prompt sobre `SKILL.md` (F4), que se reforzará con su propia prueba.

## D-023 · Configuración del agente y del modelo (F3)
- **Fecha:** 2026-11-09
- **Contexto:** el prompt fija el modelo (`claude-opus-5-5`), el pensamiento adaptativo, un `effort` explícito, la caché, `strict: true`, `tool_choice: auto` y `fallbacks: "default"`, pero no los valores concretos. Las reglas de la API se verificaron con la skill `claude-api` y con el SDK `anthropic` 2.7.0 instalado.
- **Decisión:**
  - **`effort: medium`**, el valor por defecto de Opus 5.5, escrito explícitamente en `config.json` y en cada traza. Es igual para las dos configuraciones.
  - **`thinking: {type: adaptive, display: summarized}`.** En Opus 5.5 el pensamiento no se puede apagar. `display` no cambia lo que se factura; el resumen queda en la traza para el análisis de errores del artículo.
  - **Caché:** un punto explícito al final del prompt de sistema, que cubre herramientas + sistema (lo que comparten todos los casos), más caché automática para la conversación. Es la combinación que la documentación recomienda para bucles de agente.
  - **`max_tokens` de 16.000 por respuesta**, sin streaming. Las respuestas son cortas y el pensamiento cuenta dentro de ese límite.
  - **Fallbacks:** el modelo que respondió se lee de `response.model` y de las entradas `fallback_message` en `usage.iterations`. Si no es el pedido, la traza se marca `contaminada: true` y la ejecución se repite en F6.
  - **`por_defecto: denegar` en la política** (el kit usaba `confirmar`): una herramienta nueva sin clasificar no se ejecuta, porque en el experimento no hay persona que confirme.
  - **Presupuesto de 250.000 tokens por HU**, contando entrada, salida y caché, y **15 pasos como máximo**.
  - **Entorno de los servidores:** se arrancan con el entorno mínimo del SDK de MCP; la clave de la API no les llega. Su stderr va a `estado/logs/<run_id>.log`.
  - **Carpetas de trazas:** `trazas/desarrollo/` (pruebas manuales) no se versiona. Las trazas que respaldan algo reportado (la demostración de F3 y el experimento) sí se versionan.
  - **Tarea del usuario:** el mismo texto mínimo en las dos configuraciones ("Revisa la historia de usuario con id '…' del backlog.").
- **Consecuencias:** las dos ejecuciones reales de F3 costaron en total US$0,30 (HU-002: 0,17; HU-005: 0,13). La caché funcionó: menos de 20 tokens de entrada sin caché por ejecución.

## D-024 · `instrucciones_base.md` se adelantó a F3
- **Fecha:** 2026-11-09
- **Contexto:** para probar el agente con el modelo real hacía falta un prompt de sistema. `SKILL.md` es trabajo de F4.
- **Decisión:** se creó `config/instrucciones_base.md` con el párrafo exacto que fija el prompt del proyecto, y las demostraciones de F3 se corrieron con la configuración `base`.
- **Consecuencias:** F4 no cambia ese archivo. Si hubiera que ajustarlo, se registra aquí antes de congelar.
