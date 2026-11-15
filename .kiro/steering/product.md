---
inclusion: always
---

# Producto — RevisorHU

> Mismas reglas que `CLAUDE.md`. Si cambias una regla aquí, cámbiala también allí.
> Contrato del proyecto: `docs/propuesta.md`. Decisiones: `docs/DECISIONES.md`.

## Usuario y problema
- En un banco, cada sistema (por ejemplo, la **App de Banca Móvil**) tiene un líder técnico que acepta o devuelve las historias de usuario (HU) según su criterio individual. No hay una *Definition of Ready* (DoR) documentada, y una HU tarda unas 2 semanas en aprobarse.

## Qué hace el agente
- **Clasifica** el tipo de HU, **busca** duplicados, conflictos y referencias, **estima** en story points (1, 2, 3, 5, 8, 13), **refina** (redacción "Como…, quiero…, para…" y criterios de aceptación en el formato del catálogo: hoy reglas o lista de verificación, D-027) y **recomienda** `aceptar`, `devolver` (con recomendaciones accionables) o `dividir`.
- **El agente nunca aprueba.** La aprobación para la fábrica la da una persona (segregación de funciones). `aprobar_para_fabrica` está oculta al modelo.
- En Azure DevOps el agente solo comenta, etiqueta (`ia-revisada` y una de `ia-aceptar`, `ia-devolver`, `ia-dividir`) y sugiere story points. **Nunca cambia el estado del work item.**
- **Regla de decisión** (la misma para la Skill y para la guía de etiquetado, D-025), en este orden: devolver si no se entiende, falta información, es duplicado o hay conflicto; dividir si es clara pero tiene más de un objetivo o más de 8 puntos; devolver ante **cualquier** defecto, sin importar la severidad; aceptar solo sin defectos.
- `SKILL.md` describe cómo trabajar, no qué criterios existen: no contiene ids de criterios ni nombra herramientas ocultas (lo verifica `tests/test_skill.py`).

## Pregunta de investigación
- ¿La Skill procedimental (`skills/revisor-hu/SKILL.md`) mejora la exactitud de la decisión frente a un párrafo genérico (`config/instrucciones_base.md`), y a qué costo en tokens?
- **Solo cambia el prompt de sistema**: el modelo, las herramientas, la política y el `effort` son los mismos. Cada configuración se ejecuta 3 veces.

## Datos y ética
- **Ninguna HU real del banco** entra al repositorio ni se envía a la API. Solo HU genéricas (Dalpiaz, TAWOS) y sintéticas.
- Las etiquetas del conjunto de evaluación son de **dos personas del equipo**. Ninguna IA etiqueta casos.
