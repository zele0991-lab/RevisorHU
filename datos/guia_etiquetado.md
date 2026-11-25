# Guía de etiquetado

Esta guía es para la persona que etiqueta el conjunto de evaluación. Las etiquetas son la
**respuesta correcta** con la que se mide al agente, así que se ponen con el mismo criterio con
que un líder técnico revisaría la historia.

## Rutina rápida (2–3 minutos por historia)

Lee la HU una vez **en el original** y responde estas 6 preguntas en orden. Cada "no" es un defecto:

| # | Pregunta | Si es "no", marca |
|---|---|---|
| 1 | ¿Tiene criterios de aceptación comprobables? | INV-005 |
| 2 | ¿Tiene rol, acción y un "para…" que sea un beneficio real (no repite la acción)? | QUS-001 / QUS-004 / INV-002 |
| 3 | ¿Es un solo objetivo y cabe en 8 puntos o menos? | QUS-002 / INV-004 → candidata a **dividir** |
| 4 | ¿Se entiende sin palabras vagas ni soluciones técnicas impuestas? | QUS-006 / QUS-005 / QUS-003 |
| 5 | Con `b`: ¿no hay otra HU igual o que la contradiga? | QUS-008 / QUS-007 |
| 6 | ¿Un equipo podría estimarla sin preguntar reglas, límites o errores? | INV-003 / DOR-002 |

Decisión: si falla cualquier pregunta distinta de la 3, **devolver**; si solo falla la 3,
**dividir**; si no falla ninguna, **aceptar**. QUS-009, INV-001, DOR-001 y DOR-003 solo se marcan cuando saltan a
la vista. Marca **todos** los defectos que veas con claridad, no solo el primero.

**Traducción de apoyo.** Debajo de cada HU en inglés la herramienta muestra una traducción literal al
español (D-035). Úsala para entender, pero **decide sobre el original**: el agente recibe el texto en
inglés. La traducción conserva a propósito las palabras vagas (por ejemplo "some" → "algunos (some)")
y los errores del original; si la traducción y el original parecen decir cosas distintas, manda el
original y anótalo en el comentario.

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
2. **Devolver si tiene cualquier defecto que no sea de tamaño**, de cualquier severidad, aunque
   además sea grande. Marca todos los defectos, también QUS-002 o INV-004 si los ves.
3. **Dividir solo si el tamaño es su único problema.** Cumple todo lo demás, pero tiene más de un
   objetivo que se podría entregar por separado, o estimas más de 8 puntos. Sus defectos son solo
   QUS-002 o INV-004.
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
- **Criterio del anotador (D-036):** se **divide** solo si la HU cumple todo **excepto el tamaño**
  (sus únicos defectos son QUS-002 o INV-004). Si además es ambigua, no verificable o tiene cualquier
  otro defecto, se **devuelve**.
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
