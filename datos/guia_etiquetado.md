# Guía de etiquetado

Esta guía es para la persona que etiqueta el conjunto de evaluación. Las etiquetas son la
**respuesta correcta** con la que se mide al agente, así que se ponen con el mismo criterio con
que un líder técnico revisaría la historia.

## Antes de empezar

- **No abras** `datos/evaluacion/diseno_casos.yaml` ni las trazas del agente. El diseño muestra
  con qué intención se armó cada caso, y eso sesgaría tu etiqueta.
- Ten a mano el catálogo (`conocimiento/criterios.yaml`). La herramienta muestra el nombre de cada
  criterio; si dudas, lee su descripción y "cómo verificar".
- Las HU vienen de proyectos reales y públicos (Dalpiaz, 2018) y están en inglés. No son del banco,
  así que aplican solo los **17 criterios generales** (QUS, INVEST y DoR), no los de Banca Móvil.
- Etiqueta sin apuro. Si un caso te genera dudas, escríbelas en el comentario.

## Cómo se usa la herramienta

```bash
python datos/etiquetar.py --anotador A --piloto
```

```bash
python datos/etiquetar.py --anotador A
```

1. Primero la **ronda piloto** (10 casos). Al terminarla, revisa si la guía te alcanzó y anota
   cualquier regla que hayas tenido que inventar.
2. Después, los **40 casos**. La herramienta retoma donde quedaste; escribe `salir` para pausar.
3. Con la tecla `b` ves las 5 HU más parecidas del backlog del proyecto: úsala siempre que sospeches
   un duplicado o un conflicto.
4. Al final, ejecuta:

```bash
python experimentos/acuerdo.py
```

## Las tres decisiones

Se aplican **en este orden**, el mismo que usa el agente:

1. **Devolver si no se entiende o no puede seguir.** La HU no se entiende, falta información para
   saber el alcance, es un duplicado de otra HU del backlog o la contradice. No se divide lo que no
   se entiende, aunque sea grande.
2. **Dividir si es clara pero demasiado grande.** Se entiende, pero tiene más de un objetivo que se
   podría entregar por separado, o estimas más de 8 puntos. Marca también los demás defectos que
   veas (al menos QUS-002 o INV-004, que son los que justifican dividir).
3. **Devolver si tiene cualquier defecto**, de cualquier severidad.
4. **Aceptar** solo si todos los criterios se cumplen o no aplican. Si aceptas, no hay defectos.

## Criterios: cuándo NO se cumplen

| Criterio | No se cumple si… |
|---|---|
| QUS-001 Bien formada | falta el rol o la acción. |
| QUS-002 Atómica | une con "y", "también" o listas objetivos que se entregarían por separado. |
| QUS-003 Mínima | trae notas, soluciones o detalles dentro del enunciado. |
| QUS-004 Conceptualmente sólida | el "para…" describe otra funcionalidad o repite la acción, en vez de un propósito. |
| QUS-005 Orientada al problema | impone una solución técnica (tabla, librería, herramienta concreta). |
| QUS-006 No ambigua | usa términos vagos sin medida ("rápido", "mejor", "some", "functioning"). |
| QUS-007 Sin conflictos | contradice otra HU del backlog (búscala con `b`). |
| QUS-008 Única | otra HU del backlog dice lo mismo (búscala con `b`). |
| QUS-009 Uniforme | no sigue la plantilla del resto del backlog del proyecto. |
| INV-001 Independiente | depende de algo que no existe o no está planificado. |
| INV-002 Valiosa | no tiene "para…" o el beneficio es solo para el equipo de desarrollo. |
| INV-003 Estimable | un equipo no podría estimarla sin preguntar por alcance o reglas. |
| INV-004 Pequeña | estimas más de 8 puntos. |
| INV-005 Verificable | no tiene criterios de aceptación, o alguno no se puede comprobar sin interpretar. |
| DOR-001 Dependencias | necesita otro sistema o proveedor evidente y no lo nombra. |
| DOR-002 Reglas de negocio | faltan límites, validaciones o casos de error relevantes. |
| DOR-003 No funcionales | es crítica o de alto volumen y no declara ninguna medida (tiempo, tamaño, disponibilidad). |

Notas para estos proyectos:

- Una HU **sin criterios de aceptación** incumple INV-005, y eso basta para devolverla.
- **No inventes requisitos**: si para aceptarla tendrías que suponer una regla que la HU no dice,
  no cumple DOR-002 o INV-003.
- DOR-001 y DOR-003 se marcan solo cuando la dependencia o la necesidad no funcional es evidente.
- El idioma inglés no es un defecto: todo el backlog de cada proyecto está en inglés.

## Tipo y estimación

- **Tipo de HU:** el catálogo define hoy un solo tipo (`funcional`), y la herramienta lo pone sola.
- **Estimación (opcional):** usa la escala 1, 2, 3, 5, 8 y 13, y compara con tu experiencia. Si
  devuelves por falta de información, puedes dejarla vacía.

## Cuánto toma

Unos 3 a 4 minutos por caso: alrededor de 30 minutos el piloto y 2 a 3 horas los 40 casos.

## Conjunto bancario complementario

Son 18 HU sintéticas de Banca Móvil, en español, que se etiquetan aparte:

```bash
python datos/etiquetar.py --anotador A --conjunto banca
```

```bash
python experimentos/acuerdo.py --conjunto banca
```

- Aquí **sí aplican los 10 criterios de Banca Móvil** (BM-001 a BM-010), además de los 17 generales.
  La herramienta los muestra solos según el sistema de cada HU; una HU es del sistema `core` y no
  los lleva.
- Los duplicados y conflictos están **entre las mismas 18 HU**: la tecla `b` busca dentro del conjunto.
- Para aceptar una HU bancaria, sus criterios de aceptación tienen que cubrir lo que aplique:
  autenticación, enmascarado, sesión, errores y falta de conexión, auditoría, accesibilidad,
  plataformas y la Ley 8968 o la normativa SUGEF cuando corresponda. Lo que no aplica a esa HU no
  cuenta como defecto.
- No abras `diseno_casos_banca.yaml` antes de etiquetar.
