# Acuerdo por criterio entre el agente y el anotador (exploratorio, D-038)

Conjuntos genérico y bancario juntos (58 HU), 3 repeticiones sumadas. "Anotador" = defectos que marcó el anotador; "marca" = promedio por repetición de los que señala el agente. Precisión: de lo que marca el agente, cuánto coincide con el anotador. Exhaustividad: de lo que marcó el anotador, cuánto encuentra el agente.

Análisis exploratorio: la pregunta surgió después de ver los resultados y no distingue omisiones del anotador de exceso de rigor del agente.

## Por categoría

| Categoría | Anotador | Skill marca | Skill prec. | Skill exh. | Skill F1 | Base marca | Base prec. | Base exh. | Base F1 |
|---|---|---|---|---|---|---|---|---|---|
| qus | 45 | 64.0 | 35 % | 50 % | 0.41 | 64.0 | 35 % | 50 % | 0.41 |
| invest | 88 | 96.0 | 72 % | 79 % | 0.75 | 78.7 | 72 % | 64 % | 0.68 |
| dor | 15 | 83.3 | 13 % | 73 % | 0.22 | 60.7 | 15 % | 60 % | 0.24 |
| banca_movil | 19 | 69.3 | 21 % | 75 % | 0.32 | 28.3 | 33 % | 49 % | 0.39 |

## Por criterio

| Criterio | Nombre | Anotador | Skill marca | Skill prec. | Skill exh. | Skill F1 | Base marca | Base prec. | Base exh. | Base F1 |
|---|---|---|---|---|---|---|---|---|---|---|
| QUS-001 | Bien formada | 15 | 1.0 | 100 % | 7 % | 0.12 | 1.3 | 100 % | 9 % | 0.16 |
| QUS-002 | Atómica | 5 | 11.0 | 36 % | 80 % | 0.50 | 12.0 | 33 % | 80 % | 0.47 |
| QUS-003 | Mínima | 1 | 1.0 | 0 % | 0 % | 0.00 | 0.0 | — | 0 % | 0.00 |
| QUS-004 | Conceptualmente sólida | 3 | 4.7 | 14 % | 22 % | 0.17 | 1.3 | 0 % | 0 % | 0.00 |
| QUS-005 | Orientada al problema | 1 | 4.0 | 0 % | 0 % | 0.00 | 0.0 | — | 0 % | 0.00 |
| QUS-006 | No ambigua | 18 | 33.7 | 50 % | 93 % | 0.65 | 44.7 | 38 % | 94 % | 0.54 |
| QUS-007 | Sin conflictos | 0 | 3.3 | 0 % | — | 0.00 | 0.7 | 0 % | — | 0.00 |
| QUS-008 | Única | 2 | 5.0 | 0 % | 0 % | 0.00 | 4.0 | 0 % | 0 % | 0.00 |
| QUS-009 | Uniforme | 0 | 0.3 | 0 % | — | 0.00 | 0.0 | — | — | — |
| INV-001 | Independiente | 6 | 0.3 | 0 % | 0 % | 0.00 | 0.3 | 0 % | 0 % | 0.00 |
| INV-002 | Valiosa | 1 | 11.0 | 6 % | 67 % | 0.11 | 10.0 | 3 % | 33 % | 0.06 |
| INV-003 | Estimable | 32 | 41.3 | 75 % | 97 % | 0.85 | 23.3 | 76 % | 55 % | 0.64 |
| INV-004 | Pequeña | 14 | 3.0 | 89 % | 19 % | 0.31 | 4.7 | 79 % | 26 % | 0.39 |
| INV-005 | Verificable | 35 | 40.3 | 87 % | 100 % | 0.93 | 40.3 | 87 % | 100 % | 0.93 |
| DOR-001 | Dependencias identificadas | 1 | 26.0 | 0 % | 0 % | 0.00 | 16.7 | 0 % | 0 % | 0.00 |
| DOR-002 | Reglas de negocio explícitas | 11 | 39.0 | 23 % | 82 % | 0.36 | 40.3 | 20 % | 73 % | 0.31 |
| DOR-003 | Requisitos no funcionales declarados | 3 | 18.3 | 11 % | 67 % | 0.19 | 3.7 | 27 % | 33 % | 0.30 |
| BM-001 | Autenticación y MFA | 6 | 8.0 | 75 % | 100 % | 0.86 | 7.0 | 81 % | 94 % | 0.87 |
| BM-002 | Manejo de sesión | 0 | 4.3 | 0 % | — | 0.00 | 1.0 | 0 % | — | 0.00 |
| BM-003 | Enmascarado de datos sensibles | 1 | 7.0 | 14 % | 100 % | 0.25 | 5.0 | 0 % | 0 % | 0.00 |
| BM-004 | Seguridad de la app móvil (OWASP MASVS) | 5 | 1.0 | 67 % | 13 % | 0.22 | 0.0 | — | 0 % | 0.00 |
| BM-005 | Trazabilidad y auditoría | 1 | 6.3 | 16 % | 100 % | 0.27 | 1.3 | 50 % | 67 % | 0.57 |
| BM-006 | Accesibilidad | 0 | 10.0 | 0 % | — | 0.00 | 0.3 | 0 % | — | 0.00 |
| BM-007 | Comportamiento sin conexión y errores | 3 | 10.7 | 28 % | 100 % | 0.44 | 4.0 | 50 % | 67 % | 0.57 |
| BM-008 | Plataformas iOS y Android | 2 | 6.3 | 26 % | 83 % | 0.40 | 1.0 | 0 % | 0 % | 0.00 |
| BM-009 | Protección de datos personales (Ley 8968) | 1 | 6.0 | 17 % | 100 % | 0.29 | 4.3 | 23 % | 100 % | 0.38 |
| BM-010 | Cumplimiento normativo SUGEF | 0 | 9.7 | 0 % | — | 0.00 | 4.3 | 0 % | — | 0.00 |
