# INVEST

> Guía para personas. Explica el acrónimo; **no define criterios**. Los criterios que se
> evalúan están solo en `criterios.yaml`.

Bill Wake (2003) propuso INVEST como lista de verificación de una buena historia de usuario:
**I**ndependiente, **N**egociable, **V**aliosa, **E**stimable, pequeña (**S**mall) y
verificable (**T**estable).

## Independiente
La historia se puede desarrollar y entregar sin esperar a otra que no esté lista. Las
dependencias no siempre se pueden eliminar, pero deben estar identificadas.

## Negociable
Una historia no es un contrato: es la invitación a una conversación. Por eso no debe imponer
la solución técnica. En este proyecto se revisa con el criterio "orientada al problema".

## Valiosa
El beneficio es explícito y tiene valor para alguien distinto del equipo de desarrollo. La
parte "para…" de la plantilla es donde se ve.

## Estimable
El equipo puede asignar story points sin hacer preguntas de alcance. Si faltan reglas de
negocio, montos, integraciones o límites, la historia no es estimable y se devuelve con
preguntas concretas. **No se inventan requisitos para poder estimar.**

## Pequeña: cuándo dividir
La historia cabe en un sprint. En este proyecto, la escala es 1, 2, 3, 5, 8, 13 y **más de 8
puntos se divide**. También se divide una historia con más de un objetivo, aunque sea pequeña.

Formas habituales de dividir:
- por operación (consultar, crear, modificar, eliminar);
- por regla de negocio o variante (un tipo de cuenta primero, los demás después);
- por camino feliz primero y casos de error después;
- por canal o plataforma, solo si el comportamiento realmente difiere.

Todas las partes conservan el rol de la historia original.

## Verificable
Hay criterios de aceptación que permiten saber, sin interpretación, si la historia está
terminada. En este proyecto se escriben en Gherkin: "Dado … cuando … entonces …".

## Referencia
Wake, B. (2003). *INVEST in Good Stories, and SMART Tasks*. XP123.
https://xp123.com/articles/invest-in-good-stories-and-smart-tasks/
