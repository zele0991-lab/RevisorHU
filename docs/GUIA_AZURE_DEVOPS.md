# Guía: Azure DevOps de prueba y la fase F7 con Kiro

Esta guía es para la persona del equipo que prepara Azure DevOps y trabaja con Kiro. Todo se hace en
una **organización de prueba**, con historias **sintéticas**. Nunca con HU reales del banco.

> Los nombres de los menús de Azure DevOps cambian con el tiempo. Si un paso no coincide con lo que
> ves, busca la opción por su nombre en la documentación oficial de Azure DevOps.

## Qué hace cada parte

| Parte | Quién | Estado |
|---|---|---|
| Agente, servidores MCP, política, Skill y trazas | Claude Code (F0–F4) | listo |
| Punto de conexión del adaptador, `config/config_azure.json` y `config/azure_devops.json` | Claude Code | listo |
| Organización de prueba, proyecto, áreas, HU sintéticas y PAT | tú (pasos 1–5) | pendiente |
| Adaptador `BacklogAzureDevOps` y poller | Kiro (paso 6) | pendiente |
| Revisión del código de Kiro | Claude Code (paso 8) | pendiente |

## 1. Crear la organización (gratis)

1. Entra a `dev.azure.com` con tu cuenta de Microsoft.
2. Crea una organización nueva, por ejemplo `revisorhu-pruebas-<tus iniciales>`.

## 2. Crear el proyecto

1. Crea un proyecto llamado exactamente **`RevisorHU-Pruebas`**, privado.
2. En las opciones avanzadas, elige el proceso **Agile**. Es el que trae User Story, Acceptance
   Criteria y Story Points.

Si usas otro nombre de proyecto, cambia también las claves de `mapeo_area_sistema` en
`config/azure_devops.json` y la columna *Area Path* del CSV.

## 3. Crear las áreas (una por sistema)

En *Project settings → Boards → Project configuration → Areas*, crea dos áreas bajo el proyecto:
- `BancaMovil`
- `Core`

Así el Area Path de cada HU dice a qué sistema pertenece. El conector lo traduce al `sistema` del
catálogo con `mapeo_area_sistema` (`RevisorHU-Pruebas\BancaMovil` → `banca_movil`).

## 4. Cargar las HU sintéticas

El archivo [`datos/ejemplo/hu_sinteticas_azure.csv`](../datos/ejemplo/hu_sinteticas_azure.csv) trae
10 User Stories:
- las 8 del backlog de ejemplo: una bien escrita, una vaga, un duplicado, una que hay que dividir,
  una con inyección visible, una técnica sin rol, una de Core y una en conflicto;
- 2 **ataques propios de Azure DevOps**: una instrucción escondida en un comentario HTML y otra en
  un texto oculto (`display:none`). Sirven para probar que el conector las elimina.

Para importarlas: *Boards → Work items → Import work items*, elige el CSV y confirma. Todas llevan la
etiqueta `sintetica`.

Si la importación falla por un campo, revisa que el proyecto use el proceso Agile y que las áreas
del paso 3 existan.

## 5. Crear el PAT (token de acceso personal)

1. *User settings* (ícono de usuario) → *Personal access tokens* → *New token*.
2. Nombre: `revisorhu-f7`. Organización: la de prueba. Expiración: **corta** (por ejemplo, 30 días).
3. Alcance: *Custom defined* → **Work Items: Read & write**. Nada más.
4. Copia el token: se muestra **una sola vez**.

Crea un archivo `.env` en la raíz del proyecto (no se sube a git: está en `.gitignore`):

```
AZDO_ORG_URL=https://dev.azure.com/<tu-organizacion>
AZDO_PROJECT=RevisorHU-Pruebas
AZDO_PAT=<el token>
```

Comprueba que no aparezca en git: `git status` **no** debe listar `.env`.

## 6. Implementar el conector con Kiro

1. En Claude Code, confirma que el árbol está limpio (`git status` sin cambios).
2. Crea la rama de trabajo: `git switch -c f7-azure-devops`.
3. Abre la carpeta del proyecto en **Kiro**. Kiro lee solo `.kiro/steering/` (las reglas) y
   `.kiro/settings/mcp.json` (los tres servidores, para probarlos a mano).
4. Crea un **Spec** nuevo y pega el contenido de
   [`docs/kiro/PROMPT_F7_AZURE_DEVOPS.md`](kiro/PROMPT_F7_AZURE_DEVOPS.md), desde la línea `---` hacia
   abajo.
5. **Revisa `requirements.md` y `design.md` antes de ejecutar tareas.** Comprueba que:
   - no cambie el agente, la política, la Skill, el catálogo ni los servidores;
   - el único campo que escribe en Azure DevOps sea `System.Tags`, además de los comentarios;
   - el poller corra en modo **simulado** por defecto.
6. Ejecuta las tareas y, al final, `python -m pytest`: todo en verde y sin red.

## 7. Probar contra la organización de prueba (sin costo de API)

```powershell
python -m revisor.integracion.poller_azure --una-vez
```

- En modo simulado, el "modelo" es el guion de prueba: **no llama a la API de Anthropic**. Igual lee
  las HU de Azure DevOps y escribe en ellas el comentario y las etiquetas.
- Revisa en Azure DevOps que cada HU procesada tenga el comentario y las etiquetas `ia-revisada` y
  `ia-<decisión>`, y que su **estado no haya cambiado**.
- La traza queda en `trazas/azure/`.

El modo real (`--real`) llama al modelo y cuesta unos US$0,15–0,25 por HU. Está en pausa (D-028) hasta
que lo autorices.

## 8. Volver a Claude Code

Cuando Kiro termine:
1. vuelve a Claude Code en la rama `f7-azure-devops`;
2. pide una revisión del código de Kiro (`/code-review`) y de seguridad;
3. si todo está bien, se integra en `main` y se actualizan las bitácoras.

## Seguridad

- Usa siempre HU **sintéticas**. Una HU real del banco no puede entrar ni a esta organización ni a la
  API.
- Al terminar el curso, **revoca el PAT** desde *Personal access tokens*.
- Si alguna vez pegaste el PAT donde no debías (un chat, un commit, una captura), revócalo de
  inmediato y crea otro.
