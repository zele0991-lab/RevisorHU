# Definition of Ready (DoR), borrador v0

> Guía para personas. Explica cómo se usa la DoR en este proyecto; **no define criterios**.
> Los criterios están solo en `criterios.yaml`.
>
> **Borrador v0**, escrito por el equipo a partir de QUS, INVEST y la experiencia en el banco.
> Se valida después con los líderes técnicos. Las diferencias entre líderes se documentan como
> hallazgo.

## Para qué sirve
Hoy cada líder técnico acepta o devuelve las historias según su criterio, y una historia tarda
unas dos semanas en aprobarse porque va y viene. Una DoR escrita hace explícito qué se exige para
que una historia entre a la fábrica de software. Así el criterio no depende de quién revise y se
puede transferir.

## Qué significa "lista" (ready)
Una historia está lista cuando:
- está bien escrita (rol, acción y beneficio) y expresa un solo objetivo;
- no es ambigua, no está duplicada y no entra en conflicto con otra;
- tiene criterios de aceptación verificables en Gherkin;
- el equipo puede estimarla y mide 8 puntos o menos;
- las dependencias, las reglas de negocio y los requisitos no funcionales relevantes están
  identificados;
- en banca móvil, además, cumple el paquete de criterios de ese sistema (autenticación,
  sesión, datos sensibles, seguridad, auditoría, accesibilidad, errores, plataformas,
  protección de datos y normativa).

## Cómo se decide
- **Aceptar:** cumple todos los criterios que aplican a su sistema. Se entrega refinada y con
  criterios en Gherkin.
- **Devolver:** incumple al menos un criterio. Cada recomendación dice qué corregir y apunta a un
  criterio concreto. Si falta información, se devuelve con **preguntas**; no se inventan
  requisitos.
- **Dividir:** tiene más de un objetivo o mide más de 8 puntos. Se proponen de 2 a 5 partes, todas
  con el mismo rol.

La severidad orienta la decisión: un criterio **bloqueante** incumplido impide aceptar; los de
severidad **mayor** normalmente también; los de severidad **menor** se reportan, pero el líder
puede aceptar la historia igual. La regla final la fija la Skill del agente y, en el banco, el
líder técnico.

## Lo que la DoR no cambia
La aprobación para la fábrica es siempre de una persona. El agente recomienda.

## Casos difíciles
- **Historia vacía o casi vacía:** se devuelve pidiendo rol, acción y beneficio.
- **Historia en otro idioma:** se revisa igual; la versión refinada se escribe en español.
- **Historia técnica sin rol de usuario** (por ejemplo, actualizar una librería): se devuelve
  pidiendo quién se beneficia y para qué. El rol puede ser un equipo interno.
- **Texto con instrucciones para la IA:** se ignoran. Son parte del contenido de la historia,
  no órdenes.
