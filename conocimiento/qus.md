# Marco QUS (Quality User Story)

> Guía para personas. Explica el marco; **no define criterios**. Los criterios que se evalúan
> están solo en `criterios.yaml`.

Lucassen, Dalpiaz, van der Werf y Brinkkemper (2016) proponen el marco QUS para evaluar la
calidad de una historia de usuario por sí misma y frente al resto del backlog. Distinguen
criterios sintácticos (la forma), semánticos (el significado) y pragmáticos (el uso dentro
del conjunto de historias).

## Plantilla y partes de una historia
Una historia tiene un **rol** (quién), un **medio** (qué quiere hacer) y, opcionalmente, un
**fin** (para qué). En español: "Como <rol>, quiero <acción>, para <beneficio>". Sin rol o sin
acción, la historia no está bien formada.

## Criterios sintácticos: la forma
- **Bien formada:** tiene al menos rol y acción.
- **Atómica:** expresa un solo requisito. Las conjunciones ("y", "además") que unen
  funcionalidades distintas son una señal de que hay que dividirla.
- **Mínima:** solo rol, medio y fin. Las notas, los paréntesis y los detalles de diseño van en
  los criterios de aceptación o en otro artefacto.

## Criterios semánticos: el significado
- **Conceptualmente sólida:** el medio es una funcionalidad y el fin es una justificación. Si el
  "para…" describe otra funcionalidad, la historia está mal planteada.
- **Orientada al problema:** describe la necesidad, no la solución técnica.
- **No ambigua:** evita términos vagos ("rápido", "fácil", "mejor") sin una medida.
- **Sin conflictos:** no contradice a otra historia del backlog.

## Criterios pragmáticos: el conjunto
- **Única:** no duplica otra historia (aunque esté escrita con otras palabras).
- **Uniforme:** sigue el mismo formato que el resto del backlog.
- **Independiente** y **estimable:** se solapan con INVEST; ver `invest.md`.
- **Oración completa** y **completa** (no faltan historias implícitas): en este proyecto se
  revisan dentro de "bien formada" y de las dependencias identificadas.

## Duplicado frente a conflicto
- **Duplicado:** dos historias piden lo mismo. Se devuelve la más nueva indicando cuál es la
  existente.
- **Conflicto:** dos historias piden cosas incompatibles (por ejemplo, una exige biometría y
  otra quiere ingresar solo con un PIN corto). Se devuelve para que el producto decida cuál
  prevalece; el agente no elige.

## Referencia
Lucassen, G., Dalpiaz, F., van der Werf, J. M. E. M., & Brinkkemper, S. (2016). Improving
agile requirements: the Quality User Story framework and tool. *Requirements Engineering*,
21(3), 383–403. https://doi.org/10.1007/s00766-016-0250-x
