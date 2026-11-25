"""
Etiquetas finales del conjunto de evaluación y, si hay dos anotadores, su acuerdo (kappa de Cohen).

Uso (desde la raíz del repositorio):
    python experimentos/acuerdo.py                       # anotador_A.csv (y anotador_B.csv si existe)
    python experimentos/acuerdo.py --a datos/etiquetas/anotador_A.csv --b datos/etiquetas/anotador_B.csv

Con UN anotador (D-033, aceptado por el profesor porque el equipo es de una persona):
    valida que los 40 casos estén etiquetados y copia las etiquetas a etiquetas_finales.csv.
Con DOS anotadores:
    - kappa de Cohen de la decisión y de cada criterio (presente o ausente como defecto);
    - desacuerdos.csv para la reunión de consenso;
    - etiquetas_finales.csv: los casos en que coinciden, más los que resuelva consenso.csv
      (columnas id, decision, defectos, estimacion), que escriben las personas después de reunirse.

En ambos casos escribe datos/etiquetas/acuerdo.md con la distribución de decisiones y si cada una
cubre al menos el 20 % de los casos.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ETIQUETAS = RAIZ / "datos" / "etiquetas"
CASOS = RAIZ / "datos" / "evaluacion" / "casos.jsonl"
CASOS_BANCA = RAIZ / "datos" / "evaluacion" / "casos_banca.jsonl"
DECISIONES = ("aceptar", "devolver", "dividir")
MIN_POR_DECISION = 0.20
COLUMNAS_FINALES = ("id", "decision", "defectos", "tipo", "estimacion", "origen")


def cohen_kappa(a: list[str], b: list[str]) -> float | None:
    """Kappa de Cohen para dos listas de etiquetas del mismo largo. None si no se puede calcular."""
    if len(a) != len(b) or not a:
        return None
    n = len(a)
    observado = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    esperado = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    if esperado == 1:
        return 1.0 if observado == 1 else None
    return round((observado - esperado) / (1 - esperado), 3)


def interpretar(k: float | None) -> str:
    """Escala de Landis y Koch (1977)."""
    if k is None:
        return "no calculable"
    for limite, texto in ((0.0, "pobre"), (0.20, "leve"), (0.40, "regular"), (0.60, "moderado"),
                          (0.80, "sustancial")):
        if k <= limite:
            return texto
    return "casi perfecto"


def leer(ruta: Path) -> dict[str, dict]:
    with ruta.open(encoding="utf-8", newline="") as f:
        return {fila["id"]: fila for fila in csv.DictReader(f)}


def _defectos(fila: dict) -> set[str]:
    return {d for d in (fila.get("defectos") or "").split(";") if d}


def distribucion(filas: list[dict]) -> dict[str, tuple[int, float]]:
    total = len(filas) or 1
    c = Counter(f["decision"] for f in filas)
    return {d: (c.get(d, 0), c.get(d, 0) / total) for d in DECISIONES}


def un_anotador(a: dict[str, dict], ids: list[str]) -> tuple[list[dict], list[str]]:
    faltan = [i for i in ids if i not in a]
    finales = [{"id": i, "decision": a[i]["decision"], "defectos": a[i]["defectos"], "tipo": a[i]["tipo"],
                "estimacion": a[i]["estimacion"], "origen": "anotador_unico"} for i in ids if i in a]
    return finales, faltan


def dos_anotadores(a: dict[str, dict], b: dict[str, dict], ids: list[str], consenso: dict[str, dict],
                   criterios: list[str]) -> dict:
    comunes = [i for i in ids if i in a and i in b]
    kappa_decision = cohen_kappa([a[i]["decision"] for i in comunes], [b[i]["decision"] for i in comunes])
    por_criterio = {}
    for c in criterios:
        va = ["si" if c in _defectos(a[i]) else "no" for i in comunes]
        vb = ["si" if c in _defectos(b[i]) else "no" for i in comunes]
        if "si" in va or "si" in vb:
            por_criterio[c] = cohen_kappa(va, vb)
    desacuerdos, finales = [], []
    for i in comunes:
        igual = a[i]["decision"] == b[i]["decision"] and _defectos(a[i]) == _defectos(b[i])
        if igual:
            finales.append({"id": i, "decision": a[i]["decision"], "defectos": a[i]["defectos"], "tipo": a[i]["tipo"],
                            "estimacion": a[i]["estimacion"] or b[i]["estimacion"], "origen": "acuerdo"})
        else:
            desacuerdos.append({"id": i, "decision_A": a[i]["decision"], "decision_B": b[i]["decision"],
                                "defectos_A": a[i]["defectos"], "defectos_B": b[i]["defectos"],
                                "comentario_A": a[i].get("comentario", ""), "comentario_B": b[i].get("comentario", "")})
            if i in consenso:
                finales.append({"id": i, "decision": consenso[i]["decision"], "defectos": consenso[i].get("defectos", ""),
                                "tipo": a[i]["tipo"], "estimacion": consenso[i].get("estimacion", ""),
                                "origen": "consenso"})
    return {"comunes": comunes, "kappa_decision": kappa_decision, "por_criterio": por_criterio,
            "desacuerdos": desacuerdos, "finales": finales}


def _escribir_csv(ruta: Path, filas: list[dict], columnas: tuple[str, ...] | list[str]) -> None:
    with ruta.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(columnas))
        w.writeheader()
        for fila in filas:
            w.writerow(fila)


def main(argv: list[str] | None = None) -> int:
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description="Acuerdo entre anotadores y etiquetas finales")
    ap.add_argument("--conjunto", choices=("generico", "banca"), default="generico")
    ap.add_argument("--a", type=Path, default=None)
    ap.add_argument("--b", type=Path, default=None)
    ap.add_argument("--casos", type=Path, default=None)
    ap.add_argument("--salida", type=Path, default=ETIQUETAS)
    args = ap.parse_args(argv)
    sufijo = "_banca" if args.conjunto == "banca" else ""
    args.a = args.a or ETIQUETAS / f"anotador_A{sufijo}.csv"
    args.b = args.b or ETIQUETAS / f"anotador_B{sufijo}.csv"
    args.casos = args.casos or (CASOS_BANCA if args.conjunto == "banca" else CASOS)
    if not args.a.exists():
        print(f"No existe {args.a}: primero etiqueta con python datos/etiquetar.py --anotador A", file=sys.stderr)
        return 2
    ids = [json.loads(l)["id"] for l in args.casos.read_text(encoding="utf-8").splitlines() if l.strip()]
    a = leer(args.a)
    versiones = {f["version_catalogo"] for f in a.values()}
    informe = ["# Etiquetas del conjunto de evaluación", ""]
    if args.b.exists():
        b = leer(args.b)
        versiones |= {f["version_catalogo"] for f in b.values()}
        consenso_ruta = args.salida / f"consenso{sufijo}.csv"
        consenso = leer(consenso_ruta) if consenso_ruta.exists() else {}
        criterios = sorted({d for f in list(a.values()) + list(b.values()) for d in _defectos(f)})
        r = dos_anotadores(a, b, ids, consenso, criterios)
        finales = r["finales"]
        _escribir_csv(args.salida / f"desacuerdos{sufijo}.csv", r["desacuerdos"],
                      ("id", "decision_A", "decision_B", "defectos_A", "defectos_B", "comentario_A", "comentario_B"))
        informe += [f"Dos anotadores, {len(r['comunes'])} casos en común.", "",
                    f"**Kappa de Cohen de la decisión: {r['kappa_decision']}** ({interpretar(r['kappa_decision'])}).", "",
                    "| Criterio | Kappa |", "|---|---|"]
        informe += [f"| {c} | {k} |" for c, k in r["por_criterio"].items()]
        informe += ["", f"Desacuerdos: {len(r['desacuerdos'])} (ver desacuerdos.csv); resueltos por consenso: "
                        f"{sum(1 for f in finales if f['origen'] == 'consenso')}."]
        pendientes = len(ids) - len(finales)
    else:
        finales, faltan = un_anotador(a, ids)
        pendientes = len(faltan)
        informe += ["Un solo anotador (D-033: equipo de una persona, aceptado por el profesor). "
                    "No hay kappa entre anotadores; es una limitación que se declara en el artículo.", ""]
        if faltan:
            informe.append(f"Faltan por etiquetar: {', '.join(faltan)}")
    if len(versiones) > 1:
        informe.append(f"⚠ Se etiquetó con versiones distintas del catálogo: {sorted(versiones)}")
    informe += ["", "| Decisión | Casos | % | ¿≥ 20 %? |", "|---|---|---|---|"]
    for d, (n, p) in distribucion(finales).items():
        informe.append(f"| {d} | {n} | {p:.0%} | {'sí' if p >= MIN_POR_DECISION else 'NO'} |")
    _escribir_csv(args.salida / f"etiquetas_finales{sufijo}.csv", finales, COLUMNAS_FINALES)
    (args.salida / f"acuerdo{sufijo}.md").write_text("\n".join(informe) + "\n", encoding="utf-8")
    print("\n".join(informe))
    print(f"\nEtiquetas finales: {len(finales)} de {len(ids)} en {args.salida / f'etiquetas_finales{sufijo}.csv'}")
    return 0 if pendientes == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
