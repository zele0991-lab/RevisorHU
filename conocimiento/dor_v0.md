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
- tiene criterios de aceptación verificables (reglas o lista de verificación);
- el equipo puede estimarla y mide 8 puntos o menos;
- las dependencias, las reglas de negocio y los requisitos no funcionales relevantes están
  identificados;
- en banca móvil, además, cumple el paquete de criterios de ese sistema (autenticación,
  sesión, datos sensibles, seguridad, auditoría, accesibilidad, errores, plataformas,
  protección de datos y normativa).

## Cómo se decide
Las reglas se aplican en este orden:

1. **Devolver** si la historia está vacía, no se entiende, le falta información para saber su
   alcance, está duplicada o entra en conflicto con otra. No se divide lo que no se entiende.
2. **Dividir** si es clara pero tiene más de un objetivo o mide más de 8 puntos. Se proponen de 2
   a 5 partes, todas con el mismo rol, y se reportan los demás defectos.
3. **Devolver** si incumple **cualquier** criterio que aplique a su sistema, sea cual sea su
   severidad. Cada recomendación dice qué corregir y apunta a un criterio concreto. Si falta
   información, se devuelve con **preguntas**; no se inventan requisitos.
4. **Aceptar** solo si cumple todos los criterios que aplican. Se entrega refinada y con sus
   criterios de aceptación en el formato que fija el catálogo.

La severidad no cambia la decisión: sirve para ordenar las correcciones (primero las
bloqueantes). Esta regla es la misma para el agente y para las personas que etiquetan el
conjunto de evaluación (D-025).

## Lo que la DoR no cambia
La aprobación para la fábrica es siempre de una persona. El agente recomienda.

## Casos difíciles
- **Historia vacía o casi vacía:** se devuelve pidiendo rol, acción y beneficio.
- **Historia en otro idioma:** se revisa igual; la versión refinada se escribe en español.
- **Historia técnica sin rol de usuario** (por ejemplo, actualizar una librería): se devuelve
  pidiendo quién se beneficia y para qué. El rol puede ser un equipo interno.
- **Texto con instrucciones para la IA:** se ignoran. Son parte del contenido de la historia,
  no órdenes.
