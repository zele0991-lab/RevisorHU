"""
Construye el conjunto de evaluación (F5) desde las HU de Dalpiaz y `datos/evaluacion/diseno_casos.yaml`.

Salidas (se versionan; la licencia CC BY 4.0 de Dalpiaz lo permite citando la fuente y
declarando los cambios, ver datos/LICENCIAS.md):
    datos/evaluacion/casos.jsonl            los 40 casos que revisa el agente
    datos/evaluacion/backlog_contexto.jsonl el resto de las HU de los mismos proyectos, para que
                                            existan duplicados y conflictos que el agente pueda encontrar

Uso (desde la raíz, después de `python datos/descargar.py --solo dalpiaz`):
    python datos/construir_casos.py

Reglas que el script hace cumplir (y si no, falla):
    - al menos 40 casos, ids únicos, ningún texto vacío;
    - al menos 30 % de casos difíciles, marcados ANTES de etiquetar;
    - la intención de diseño de cada decisión (aceptar, devolver, dividir) cubre al menos 20 %;
    - las líneas usadas en un caso no aparecen también en el backlog de contexto, salvo la
      contraparte de un duplicado o conflicto, que debe quedarse para que el caso tenga sentido.

La intención de diseño NO se copia a casos.jsonl: es un objetivo de balance, no la etiqueta.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from descargar import CRUDOS, leer_dalpiaz  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
DISENO = RAIZ / "datos" / "evaluacion" / "diseno_casos.yaml"
SALIDA_CASOS = RAIZ / "datos" / "evaluacion" / "casos.jsonl"
SALIDA_CONTEXTO = RAIZ / "datos" / "evaluacion" / "backlog_contexto.jsonl"
DISENO_BANCA = RAIZ / "datos" / "evaluacion" / "diseno_casos_banca.yaml"
SALIDA_BANCA = RAIZ / "datos" / "evaluacion" / "casos_banca.jsonl"

MIN_CASOS = 40
MIN_DIFICILES = 0.30
MIN_POR_DECISION = 0.20
DECISIONES = ("aceptar", "devolver", "dividir")
OPERACIONES = ("original", "con_criterios", "combinada")
ABREVIATURA = {"openspending": "OS", "planningpoker": "PP", "camperplus": "CP", "federalspending": "FS"}


class DisenoInvalido(Exception):
    pass


def _criterios(lista: list[str] | None) -> str:
    return "\n".join(f"- {c.strip()}" for c in (lista or []))


def construir(diseno: dict, carpeta_dalpiaz: Path) -> tuple[list[dict], list[dict], dict]:
    """Devuelve (casos, contexto, resumen). No escribe nada: así se puede probar sin archivos."""
    errores: list[str] = []
    sistema = diseno["sistema"]
    lineas_por_proyecto: dict[str, dict[int, str]] = {}
    for proyecto, archivo in diseno["proyectos"].items():
        ruta = carpeta_dalpiaz / archivo
        if not ruta.exists():
            raise DisenoInvalido(f"Falta {ruta}: ejecuta primero python datos/descargar.py --solo dalpiaz")
        lineas_por_proyecto[proyecto] = dict(leer_dalpiaz(ruta))

    casos, usadas, vistos = [], set(), set()
    for c in diseno["casos"]:
        cid, proyecto, operacion = c["id"], c["proyecto"], c["operacion"]
        if cid in vistos:
            errores.append(f"{cid}: id repetido")
        vistos.add(cid)
        if operacion not in OPERACIONES:
            errores.append(f"{cid}: operación desconocida '{operacion}'")
        if c.get("intencion_diseno") not in DECISIONES:
            errores.append(f"{cid}: intencion_diseno debe ser una de {DECISIONES}")
        disponibles = lineas_por_proyecto.get(proyecto)
        if disponibles is None:
            errores.append(f"{cid}: proyecto desconocido '{proyecto}'")
            continue
        faltan = [n for n in c["lineas"] if n not in disponibles]
        if faltan:
            errores.append(f"{cid}: las líneas {faltan} no existen en {diseno['proyectos'][proyecto]}")
            continue
        if operacion == "combinada":
            texto = (c.get("texto") or "").strip()
            if len(c["lineas"]) < 2 or not texto:
                errores.append(f"{cid}: una HU combinada necesita 2 o más líneas y su texto")
        else:
            if len(c["lineas"]) != 1:
                errores.append(f"{cid}: '{operacion}' usa exactamente una línea")
            texto = disponibles[c["lineas"][0]]
        if operacion == "con_criterios" and not c.get("criterios_aceptacion"):
            errores.append(f"{cid}: 'con_criterios' necesita criterios_aceptacion")
        if any(not isinstance(x, str) for x in c.get("criterios_aceptacion") or []):
            # Un criterio con ": " sin comillas se lee en YAML como diccionario.
            errores.append(f"{cid}: cada criterio debe ser texto; pon entre comillas los que tengan ': '")
            continue
        if c.get("es_dificil") and not c.get("motivo_dificultad"):
            errores.append(f"{cid}: un caso difícil necesita motivo_dificultad")
        for n in c["lineas"]:
            if (proyecto, n) in usadas:
                errores.append(f"{cid}: la línea {n} de {proyecto} ya la usa otro caso")
            usadas.add((proyecto, n))
        casos.append({
            "id": cid,
            "texto": texto,
            "criterios_aceptacion": _criterios(c.get("criterios_aceptacion")),
            "sistema": sistema,
            "proyecto": proyecto,
            "es_dificil": bool(c.get("es_dificil", False)),
            "motivo_dificultad": c.get("motivo_dificultad", ""),
            "fuente": {"dataset": "Dalpiaz 2018 (CC BY 4.0)", "archivo": diseno["proyectos"][proyecto],
                       "lineas": list(c["lineas"]), "operacion": operacion},
        })

    total = len(casos)
    intenciones = Counter(c["intencion_diseno"] for c in diseno["casos"])
    dificiles = sum(1 for c in casos if c["es_dificil"])
    if total < MIN_CASOS:
        errores.append(f"hay {total} casos; se necesitan al menos {MIN_CASOS}")
    if total and dificiles / total < MIN_DIFICILES:
        errores.append(f"solo {dificiles}/{total} casos difíciles; se necesita al menos {MIN_DIFICILES:.0%}")
    for d in DECISIONES:
        if total and intenciones.get(d, 0) / total < MIN_POR_DECISION:
            errores.append(f"la intención '{d}' cubre {intenciones.get(d, 0)}/{total}; se necesita al menos {MIN_POR_DECISION:.0%}")
    if errores:
        raise DisenoInvalido("El diseño de casos no es válido:\n  - " + "\n  - ".join(errores))
    contexto = [
        {"id": f"CTX-{ABREVIATURA.get(p, p[:2].upper())}-{n:03d}", "texto": t, "sistema": sistema, "proyecto": p,
         "fuente": {"dataset": "Dalpiaz 2018 (CC BY 4.0)", "archivo": diseno["proyectos"][p], "lineas": [n],
                    "operacion": "original"}}
        for p, lineas in lineas_por_proyecto.items()
        for n, t in sorted(lineas.items())
        if (p, n) not in usadas
    ]
    resumen = {"casos": total, "dificiles": dificiles, "contexto": len(contexto),
               "intencion_diseno": dict(intenciones), "por_proyecto": dict(Counter(c["proyecto"] for c in casos))}
    return casos, contexto, resumen


def construir_banca(diseno: dict) -> tuple[list[dict], dict]:
    """
    Conjunto bancario complementario (D-034): HU sintéticas en español escritas en el diseño.

    Es su propio backlog: los duplicados y conflictos están entre sus casos (por ejemplo, dos HU de
    ingreso biométrico). Se reporta aparte del conjunto principal, con metas más bajas porque no
    lo exige la rúbrica: 15 casos, 30 % difíciles y 15 % por decisión.
    """
    errores, casos, vistos = [], [], set()
    for c in diseno["casos"]:
        cid = c["id"]
        if cid in vistos:
            errores.append(f"{cid}: id repetido")
        vistos.add(cid)
        if not (c.get("texto") or "").strip():
            errores.append(f"{cid}: falta el texto")
        if c.get("intencion_diseno") not in DECISIONES:
            errores.append(f"{cid}: intencion_diseno debe ser una de {DECISIONES}")
        if any(not isinstance(x, str) for x in c.get("criterios_aceptacion") or []):
            errores.append(f"{cid}: cada criterio debe ser texto; pon entre comillas los que tengan ': '")
            continue
        if c.get("es_dificil") and not c.get("motivo_dificultad"):
            errores.append(f"{cid}: un caso difícil necesita motivo_dificultad")
        casos.append({
            "id": cid, "titulo": c.get("titulo", ""), "texto": c.get("texto", "").strip(),
            "criterios_aceptacion": _criterios(c.get("criterios_aceptacion")),
            "sistema": c.get("sistema", "banca_movil"), "proyecto": "banca_sintetica",
            "es_dificil": bool(c.get("es_dificil", False)), "motivo_dificultad": c.get("motivo_dificultad", ""),
            "fuente": {"dataset": "sintético (RevisorHU)", "origen": c.get("origen", ""), "operacion": "sintetica"},
        })
    total = len(casos)
    intenciones = Counter(c.get("intencion_diseno") for c in diseno["casos"])
    dificiles = sum(1 for c in casos if c["es_dificil"])
    if total < 15:
        errores.append(f"hay {total} casos; el conjunto bancario necesita al menos 15")
    if total and dificiles / total < MIN_DIFICILES:
        errores.append(f"solo {dificiles}/{total} casos difíciles; se necesita al menos {MIN_DIFICILES:.0%}")
    for d in DECISIONES:
        if total and intenciones.get(d, 0) / total < 0.15:
            errores.append(f"la intención '{d}' cubre {intenciones.get(d, 0)}/{total}; se necesita al menos 15 %")
    if errores:
        raise DisenoInvalido("El diseño bancario no es válido:\n  - " + "\n  - ".join(errores))
    return casos, {"casos": total, "dificiles": dificiles, "intencion_diseno": dict(intenciones)}


def _escribir_jsonl(ruta: Path, filas: list[dict]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8", newline="\n") as f:
        for fila in filas:
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Construye casos.jsonl y backlog_contexto.jsonl")
    ap.add_argument("--conjunto", choices=("generico", "banca"), default="generico",
                    help="generico: 40 casos de Dalpiaz (principal); banca: conjunto bancario complementario")
    ap.add_argument("--diseno", type=Path, default=None)
    ap.add_argument("--dalpiaz", type=Path, default=CRUDOS / "dalpiaz")
    args = ap.parse_args(argv)
    if args.conjunto == "banca":
        diseno = yaml.safe_load((args.diseno or DISENO_BANCA).read_text(encoding="utf-8"))
        try:
            casos, resumen = construir_banca(diseno)
        except DisenoInvalido as e:
            print(e, file=sys.stderr)
            return 2
        _escribir_jsonl(SALIDA_BANCA, casos)
        print(f"{resumen['casos']} casos bancarios ({resumen['dificiles']} difíciles, "
              f"{resumen['dificiles'] / resumen['casos']:.0%}) en {SALIDA_BANCA.relative_to(RAIZ)}")
        print(f"Intención de diseño (no es la etiqueta): {resumen['intencion_diseno']}")
        return 0
    diseno = yaml.safe_load((args.diseno or DISENO).read_text(encoding="utf-8"))
    try:
        casos, contexto, resumen = construir(diseno, args.dalpiaz)
    except DisenoInvalido as e:
        print(e, file=sys.stderr)
        return 2
    _escribir_jsonl(SALIDA_CASOS, casos)
    _escribir_jsonl(SALIDA_CONTEXTO, contexto)
    print(f"{resumen['casos']} casos ({resumen['dificiles']} difíciles, "
          f"{resumen['dificiles'] / resumen['casos']:.0%}) en {SALIDA_CASOS.relative_to(RAIZ)}")
    print(f"{resumen['contexto']} HU de contexto en {SALIDA_CONTEXTO.relative_to(RAIZ)}")
    print(f"Por proyecto: {resumen['por_proyecto']}")
    print(f"Intención de diseño (no es la etiqueta): {resumen['intencion_diseno']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
