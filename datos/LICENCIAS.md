# Licencias de los datos

| Datos | Fuente | Licencia | Qué se versiona |
|---|---|---|---|
| HU de 4 proyectos (OpenSpending, Planning Poker, CamperPlus, Federal Spending) | Dalpiaz, F. (2018). *Requirements data sets (user stories)*. Mendeley Data, v1. doi:10.17632/7zbk8zsd8y.1 | CC BY 4.0 | `datos/evaluacion/casos.jsonl` y `backlog_contexto.jsonl` |
| 150 historias con story points reales (19 proyectos) | Tawosi, V., Al-Subaihin, A., Moussa, R. y Sarro, F. (2022). *A Versatile Dataset of Agile Open Source Software Projects*. MSR 2022. doi:10.1145/3524842.3528029. Datos: doi:10.5522/04/21308124 | Apache 2.0 | `datos/referencias/referencias_tawos.jsonl` |
| HU sintéticas de Banca Móvil y ataques | Escritas para este proyecto | Del proyecto | `datos/ejemplo/`, `datos/ataques/` |

## Cambios declarados (exigencia de CC BY 4.0)

Las HU de Dalpiaz se usan **modificadas** en una parte de los casos, según
`datos/evaluacion/diseno_casos.yaml`:

- `con_criterios`: a la HU original se le agregaron criterios de aceptación redactados para este conjunto.
- `combinada`: dos o más HU originales del mismo proyecto se unieron en una sola.
- `original`: la HU sin cambios (solo se normalizaron apóstrofos y espacios).

Cada caso guarda en el campo `fuente` el archivo, las líneas de origen y la operación aplicada.

## TAWOS

Se usa con fines de investigación, según sus términos de uso. De cada issue solo se extraen la
clave, el título, la descripción en texto, los story points y el proyecto. **No** se extraen ids de
creador, informante ni responsable; se descartan las descripciones con correos y se reemplazan las
URL por `[URL]`. El volcado completo (637 MB) no se versiona: se descarga con
`python datos/descargar.py --solo tawos`.

## Datos que no se versionan

`datos/crudos/` (está en `.gitignore`): los archivos originales descargados. Se regeneran con
`python datos/descargar.py`.
