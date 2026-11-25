# Métricas del experimento · conjunto `generico`

Generado por `experimentos/metricas.py` a partir de las trazas. Media ± desviación estándar entre repeticiones.

- Trazas leídas: 10 (0 no válidas y reemplazadas o contadas sin decisión).
- Modelo pedido: claude-haiku-5-5. Commits: cdc2743.
- Versiones distintas de la Skill: 1; del catálogo: 1; de los datos: 1.
- Trazas con cambios sin commit en el repositorio: 10 (las del piloto cuentan su propia traza; ver D-037).
- Casos evaluados: 5.
- Referencia trivial "siempre devolver": exactitud 60.0%.

| Métrica | skill | base |
|---|---|---|
| Exactitud de la decisión | 80.0% ± 0.0% | 80.0% ± 0.0% |
| Falsos aceptar | 0.0% ± 0.0% | 0.0% ± 0.0% |
| Defectos: micro-F1 | 0.56 ± 0.00 | 0.57 ± 0.00 |
| Defectos: precisión | 0.45 ± 0.00 | 0.50 ± 0.00 |
| Defectos: exhaustividad | 0.75 ± 0.00 | 0.67 ± 0.00 |
| Tipo de HU | 100.0% ± 0.0% | 100.0% ± 0.0% |
| Estimación: error absoluto medio (vs anotador) | 2.00 ± 0.00 | 2.00 ± 0.00 |
| Estimación: a un paso o menos (vs anotador) | 100.0% ± 0.0% | 100.0% ± 0.0% |
| Tokens por HU | 78,199 ± 0.00 | 42,552 ± 0.00 |
| Costo por HU (USD estimado) | 0.0046 ± 0.0000 | 0.0030 ± 0.0000 |
| Duración por HU (s) | 26.68 ± 0.00 | 22.45 ± 0.00 |
| Pasos por HU | 5.60 ± 0.00 | 5.40 ± 0.00 |
| Ejecuciones sin decisión (por repetición) | 0.00 ± 0.00 | 0.00 ± 0.00 |

## Exactitud por repetición

| Config | r1 |
|---|---|
| skill | 80% |
| base | 80% |

## Matriz de confusión (etiqueta → agente, todas las repeticiones)

**skill:** aceptar->aceptar: 1, aceptar->devolver: 1, devolver->devolver: 3

**base:** aceptar->aceptar: 1, aceptar->devolver: 1, devolver->devolver: 3

## Umbral de éxito (fijado en la propuesta, §6)

- Diferencia de exactitud (skill − base): +0.0 puntos.
- Aumento de tokens de la Skill: +83.8%.
- exactitud_+10_puntos: NO
- tokens_+30%_o_menos: NO
- falsos_aceptar_no_aumentan: sí
- **¿Cumple el umbral? No.**
