"""
Acuerdo entre el agente y el anotador, por criterio y por categoría del catálogo (análisis
exploratorio, D-038).

Uso (desde la raíz del repositorio):
    python experimentos/por_criterio.py

Lee las mismas trazas y etiquetas que `metricas.py` (conjuntos genérico y bancario juntos) y
escribe `resultados/acuerdo_por_criterio.md` y `.json`.

Cálculo:
    - Una traza por (configuración, repetición, caso), la misma que elige `metricas.py`.
    - Por criterio se suman los pares (caso, criterio) de las 3 repeticiones: coincidencias (el
      agente y el anotador marcan el defecto), de más (solo el agente) y omitidos (solo el
      anotador). Con eso se calculan precisión, exhaustividad y F1 (micro).
    - "Marca" es el promedio por repetición de los defectos que señala el agente; "anotador" es
      cuántos marcó el anotador.
    - Las categorías son las del catálogo (qus, invest, dor, banca_movil).
    - Es exploratorio: la pregunta surgió después de ver los resultados de F6, así que no confirma
      ninguna hipótesis. No distingue omisiones del anotador de exceso de rigor del agente.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import metricas as m  # noqa: E402

RAIZ = m.RAIZ
CONJUNTOS = ("generico", "banca")
CATEGORIAS = ("qus", "invest", "dor", "banca_movil")
CONFIGS = ("skill", "base")


def leer_catalogo(ruta: Path) -> dict[str, dict]:
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    criterios: dict[str, dict] = {}

    def recorrer(o):
        if isinstance(o, dict):
            if "id" in o and "categoria" in o:
                criterios[o["id"]] = o
            for v in o.values():
                recorrer(v)
        elif isinstance(o, list):
            for v in o:
                recorrer(v)

    recorrer(datos)
    return criterios


def contar(elegidas: dict[tuple, dict], etiquetas: dict[str, dict], cuentas=None) -> dict:
    """cuentas[config][criterio] = {anotador, coinciden, de_mas, omitidos, repeticiones}."""
    cuentas = cuentas if cuentas is not None else defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for (cfg, rep, caso), t in elegidas.items():
        if caso not in etiquetas or not t["valida"]:
            continue
        gold, pred = etiquetas[caso]["defectos"], t["defectos"]
        for d in gold | pred:
            c = cuentas[cfg][d]
            c["anotador"] += d in gold
            c["coinciden"] += d in gold and d in pred
            c["de_mas"] += d in pred and d not in gold
            c["omitidos"] += d in gold and d not in pred
    return cuentas


def indicadores(coinciden: int, de_mas: int, omitidos: int, repeticiones: int) -> dict:
    p = coinciden / (coinciden + de_mas) if coinciden + de_mas else None
    r = coinciden / (coinciden + omitidos) if coinciden + omitidos else None
    f1 = 2 * p * r / (p + r) if p and r else (0.0 if coinciden + de_mas + omitidos else None)
    return {"anotador": (coinciden + omitidos) / repeticiones, "marca": (coinciden + de_mas) / repeticiones,
            "precision": p, "exhaustividad": r, "f1": f1}


def resumen(cuentas, catalogo: dict[str, dict], repeticiones: int) -> dict:
    por_criterio, por_categoria = {}, {}
    for cid in sorted(catalogo, key=lambda i: (CATEGORIAS.index(catalogo[i]["categoria"])
                                               if catalogo[i]["categoria"] in CATEGORIAS else 9, i)):
        fila = {"nombre": catalogo[cid]["nombre"], "categoria": catalogo[cid]["categoria"]}
        for cfg in CONFIGS:
            c = cuentas[cfg][cid]
            fila[cfg] = indicadores(c["coinciden"], c["de_mas"], c["omitidos"], repeticiones)
        por_criterio[cid] = fila
    for cat in CATEGORIAS:
        fila = {}
        for cfg in CONFIGS:
            tot = defaultdict(int)
            for cid, crit in catalogo.items():
                if crit["categoria"] == cat:
                    for k in ("coinciden", "de_mas", "omitidos"):
                        tot[k] += cuentas[cfg][cid][k]
            fila[cfg] = indicadores(tot["coinciden"], tot["de_mas"], tot["omitidos"], repeticiones)
        por_categoria[cat] = fila
    return {"por_categoria": por_categoria, "por_criterio": por_criterio}


def _p(v) -> str:
    return "—" if v is None else f"{v * 100:.0f} %"


def _f(v) -> str:
    return "—" if v is None else f"{v:.2f}"


def informe(res: dict, repeticiones: int) -> str:
    l = ["# Acuerdo por criterio entre el agente y el anotador (exploratorio, D-038)", "",
         f"Conjuntos genérico y bancario juntos (58 HU), {repeticiones} repeticiones sumadas. "
         "\"Anotador\" = defectos que marcó el anotador; \"marca\" = promedio por repetición de los que "
         "señala el agente. Precisión: de lo que marca el agente, cuánto coincide con el anotador. "
         "Exhaustividad: de lo que marcó el anotador, cuánto encuentra el agente.", "",
         "Análisis exploratorio: la pregunta surgió después de ver los resultados y no distingue "
         "omisiones del anotador de exceso de rigor del agente.", "",
         "## Por categoría", "",
         "| Categoría | Anotador | Skill marca | Skill prec. | Skill exh. | Skill F1 | Base marca | Base prec. | Base exh. | Base F1 |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for cat, f in res["por_categoria"].items():
        s, b = f["skill"], f["base"]
        l.append(f"| {cat} | {s['anotador']:.0f} | {s['marca']:.1f} | {_p(s['precision'])} | {_p(s['exhaustividad'])} | "
                 f"{_f(s['f1'])} | {b['marca']:.1f} | {_p(b['precision'])} | {_p(b['exhaustividad'])} | {_f(b['f1'])} |")
    l += ["", "## Por criterio", "",
          "| Criterio | Nombre | Anotador | Skill marca | Skill prec. | Skill exh. | Skill F1 | Base marca | Base prec. | Base exh. | Base F1 |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for cid, f in res["por_criterio"].items():
        s, b = f["skill"], f["base"]
        if not s["anotador"] and not s["marca"] and not b["marca"]:
            continue
        l.append(f"| {cid} | {f['nombre']} | {s['anotador']:.0f} | {s['marca']:.1f} | {_p(s['precision'])} | "
                 f"{_p(s['exhaustividad'])} | {_f(s['f1'])} | {b['marca']:.1f} | {_p(b['precision'])} | "
                 f"{_p(b['exhaustividad'])} | {_f(b['f1'])} |")
    return "\n".join(l) + "\n"


def main(argv: list[str] | None = None) -> int:
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(errors="replace")
    cfg = json.loads(m.CONFIG.read_text(encoding="utf-8"))
    catalogo = leer_catalogo(RAIZ / cfg["catalogo"])
    cuentas, reps = None, set()
    for nombre in CONJUNTOS:
        conj = cfg["conjuntos"][nombre]
        carpeta = RAIZ / conj["carpeta_trazas"]
        trazas = [t for t in (m.leer_traza(p) for p in sorted(carpeta.glob("*.jsonl"))) if t]
        if not trazas:
            print(f"No hay trazas en {carpeta}.", file=sys.stderr)
            return 1
        elegidas = m.seleccionar(trazas)
        reps |= {r for (_, r, _) in elegidas}
        cuentas = contar(elegidas, m.leer_etiquetas(RAIZ / conj["etiquetas"]), cuentas)
    res = resumen(cuentas, catalogo, len(reps))
    salida = RAIZ / "resultados"
    salida.mkdir(exist_ok=True)
    texto = informe(res, len(reps))
    (salida / "acuerdo_por_criterio.md").write_text(texto, encoding="utf-8")
    (salida / "acuerdo_por_criterio.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(texto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
