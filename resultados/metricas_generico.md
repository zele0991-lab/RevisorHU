# Métricas del experimento · conjunto `generico`

Generado por `experimentos/metricas.py` a partir de las trazas. Media ± desviación estándar entre repeticiones.

- Trazas leídas: 240 (0 no válidas y reemplazadas o contadas sin decisión).
- Modelo pedido: claude-haiku-5-5. Commits: b980d13, cdc2743.
- Versiones distintas de la Skill: 1; del catálogo: 1; de los datos: 1.
- Trazas con cambios sin commit en el repositorio: 10 (las del piloto cuentan su propia traza; ver D-037).
- Casos evaluados: 40.
- Referencia trivial "siempre devolver": exactitud 70.0%.

| Métrica | skill | base |
|---|---|---|
| Exactitud de la decisión | 83.3% ± 2.9% | 75.0% ± 2.5% |
| Falsos aceptar | 0.0% ± 0.0% | 0.0% ± 0.0% |
| Defectos: micro-F1 | 0.58 ± 0.01 | 0.53 ± 0.01 |
| Defectos: precisión | 0.50 ± 0.01 | 0.47 ± 0.01 |
| Defectos: exhaustividad | 0.70 ± 0.01 | 0.59 ± 0.02 |
| Tipo de HU | 100.0% ± 0.0% | 100.0% ± 0.0% |
| Estimación: error absoluto medio (vs anotador) | 1.06 ± 0.10 | 1.19 ± 0.25 |
| Estimación: a un paso o menos (vs anotador) | 100.0% ± 0.0% | 94.4% ± 4.8% |
| Tokens por HU | 81,833 ± 471 | 42,290 ± 917 |
| Costo por HU (USD estimado) | 0.0046 ± 0.0000 | 0.0030 ± 0.0000 |
| Duración por HU (s) | 24.82 ± 0.03 | 22.10 ± 0.14 |
| Pasos por HU | 5.82 ± 0.04 | 5.32 ± 0.08 |
| Ejecuciones sin decisión (por repetición) | 0.00 ± 0.00 | 0.00 ± 0.00 |

## Exactitud por repetición

| Config | r1 | r2 | r3 |
|---|---|---|---|
| skill | 85% | 85% | 80% |
| base | 78% | 75% | 72% |

## Matriz de confusión (etiqueta → agente, todas las repeticiones)

**skill:** aceptar->aceptar: 16, aceptar->devolver: 20, devolver->devolver: 84

**base:** aceptar->aceptar: 6, aceptar->devolver: 30, devolver->devolver: 84

## Umbral de éxito (fijado en la propuesta, §6)

- Diferencia de exactitud (skill − base): +8.3 puntos.
- Aumento de tokens de la Skill: +93.5%.
- exactitud_+10_puntos: NO
- tokens_+30%_o_menos: NO
- falsos_aceptar_no_aumentan: sí
- **¿Cumple el umbral? No.**
