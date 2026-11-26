# Métricas del experimento · conjunto `banca`

Generado por `experimentos/metricas.py` a partir de las trazas. Media ± desviación estándar entre repeticiones.

- Trazas leídas: 108 (0 no válidas y reemplazadas o contadas sin decisión).
- Modelo pedido: claude-haiku-5-5. Commits: b980d13.
- Versiones distintas de la Skill: 1; del catálogo: 1; de los datos: 1.
- Trazas con cambios sin commit en el repositorio: 0 (las del piloto cuentan su propia traza; ver D-037).
- Casos evaluados: 18.
- Referencia trivial "siempre devolver": exactitud 72.2%.

| Métrica | skill | base |
|---|---|---|
| Exactitud de la decisión | 75.9% ± 3.2% | 72.2% ± 0.0% |
| Falsos aceptar | 0.0% ± 0.0% | 0.0% ± 0.0% |
| Defectos: micro-F1 | 0.36 ± 0.01 | 0.41 ± 0.03 |
| Defectos: precisión | 0.24 ± 0.01 | 0.33 ± 0.03 |
| Defectos: exhaustividad | 0.71 ± 0.02 | 0.56 ± 0.05 |
| Tipo de HU | 100.0% ± 0.0% | 100.0% ± 0.0% |
| Estimación: error absoluto medio (vs anotador) | 0.53 ± 0.31 | 0.53 ± 0.31 |
| Estimación: a un paso o menos (vs anotador) | 93.3% ± 11.5% | 100.0% ± 0.0% |
| Tokens por HU | 98,617 ± 2,987 | 49,479 ± 732 |
| Costo por HU (USD estimado) | 0.0064 ± 0.0000 | 0.0035 ± 0.0000 |
| Duración por HU (s) | 32.57 ± 0.24 | 24.15 ± 0.47 |
| Pasos por HU | 5.74 ± 0.12 | 5.50 ± 0.06 |
| Ejecuciones sin decisión (por repetición) | 0.00 ± 0.00 | 0.00 ± 0.00 |

## Exactitud por repetición

| Config | r1 | r2 | r3 |
|---|---|---|---|
| skill | 72% | 78% | 78% |
| base | 72% | 72% | 72% |

## Matriz de confusión (etiqueta → agente, todas las repeticiones)

**skill:** aceptar->aceptar: 2, aceptar->devolver: 13, devolver->devolver: 39

**base:** aceptar->devolver: 15, devolver->devolver: 39

## Umbral de éxito (fijado en la propuesta, §6)

- Diferencia de exactitud (skill − base): +3.7 puntos.
- Aumento de tokens de la Skill: +99.3%.
- exactitud_+10_puntos: NO
- tokens_+30%_o_menos: NO
- falsos_aceptar_no_aumentan: sí
- **¿Cumple el umbral? No.**
