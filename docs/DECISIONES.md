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

## D-003 · Servidores MCP con el SDK oficial `mcp` (FastMCP) por stdio
- **Fecha:** 2026-11-09
- **Contexto:** el kit habla MCP a mano. Queremos conectar los mismos servidores a Claude Code y a Kiro para probarlos.
- **Decisión:** FastMCP para los servidores y el cliente stdio del SDK en el host. Los servidores se registran en `.mcp.json` y en `.kiro/settings/mcp.json`.
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
