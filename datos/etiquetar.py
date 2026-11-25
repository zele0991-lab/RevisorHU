"""
Herramienta de etiquetado del conjunto de evaluación (F5). La usa una PERSONA, nunca Claude.

Uso (desde la raíz del repositorio):
    python datos/etiquetar.py --anotador A --piloto     # ronda piloto: 10 casos
    python datos/etiquetar.py --anotador A              # los 40 casos (retoma donde quedó)

Para cada HU muestra el texto y los criterios de aceptación, y pide:
    - la decisión: aceptar, devolver o dividir;
    - los defectos: SOLO criterios activos del catálogo que aplican al sistema de la HU;
    - el tipo de HU (del catálogo) y una estimación en la escala Fibonacci (opcional);
    - un comentario libre (opcional).
Con la tecla `b` busca HU parecidas en el backlog de contexto (para ver duplicados y conflictos).

Reglas que la herramienta hace cumplir:
    - escribe solo en datos/etiquetas/anotador_<X>.csv y nunca abre el archivo de otro anotador;
    - cada fila guarda la versión y el hash del catálogo con que se etiquetó;
    - el orden de los casos se baraja de forma fija por anotador (sin ver el orden del otro);
    - aceptar no lleva defectos; devolver lleva al menos uno (la misma regla que valida el servidor).

Las etiquetas definen la respuesta correcta del experimento: por eso Claude no etiqueta (D-033).
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Callable

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from revisor.backlog.similitud import IndiceSimilitud  # noqa: E402
from revisor.conocimiento.catalogo import cargar_catalogo  # noqa: E402

CASOS = RAIZ / "datos" / "evaluacion" / "casos.jsonl"
CONTEXTO = RAIZ / "datos" / "evaluacion" / "backlog_contexto.jsonl"
CASOS_BANCA = RAIZ / "datos" / "evaluacion" / "casos_banca.jsonl"
# conjunto -> (casos, backlog donde buscar parecidas, sufijo del archivo de etiquetas)
CONJUNTOS = {"generico": (CASOS, CONTEXTO, ""), "banca": (CASOS_BANCA, CASOS_BANCA, "_banca")}
CARPETA = RAIZ / "datos" / "etiquetas"
CATALOGO = RAIZ / "conocimiento" / "criterios.yaml"
TAMANO_PILOTO = 10
ESCALA = (1, 2, 3, 5, 8, 13)
DECISIONES = {"a": "aceptar", "d": "devolver", "v": "dividir"}
COLUMNAS = ("id", "decision", "defectos", "tipo", "estimacion", "comentario", "anotador",
            "version_catalogo", "hash_catalogo", "fecha")


class EtiquetaInvalida(ValueError):
    pass


def leer_jsonl(ruta: Path) -> list[dict]:
    return [json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()]


def ruta_anotador(anotador: str, carpeta: Path = CARPETA, sufijo: str = "") -> Path:
    if not anotador.isalnum() or len(anotador) > 10:
        raise EtiquetaInvalida("El anotador se identifica con letras o números, por ejemplo A o B.")
    return carpeta / f"anotador_{anotador}{sufijo}.csv"


def orden_para(anotador: str, ids: list[str]) -> list[str]:
    """Orden fijo por anotador: reproducible, y distinto entre anotadores."""
    orden = sorted(ids)
    random.Random(f"orden-etiquetado-{anotador}").shuffle(orden)
    return orden


def ya_etiquetados(ruta: Path) -> dict[str, dict]:
    if not ruta.exists():
        return {}
    with ruta.open(encoding="utf-8", newline="") as f:
        return {fila["id"]: fila for fila in csv.DictReader(f)}


def validar(decision: str, defectos: list[str], tipo: str, estimacion: int | None,
            permitidos: set[str], tipos: list[str]) -> None:
    """Las mismas reglas de forma que aplica el servidor al agente, para que ambos se comparen igual."""
    if decision not in DECISIONES.values():
        raise EtiquetaInvalida(f"Decisión inválida: {decision}")
    desconocidos = [d for d in defectos if d not in permitidos]
    if desconocidos:
        raise EtiquetaInvalida(f"No aplican a esta HU o no existen en el catálogo: {', '.join(desconocidos)}")
    if len(set(defectos)) != len(defectos):
        raise EtiquetaInvalida("Hay defectos repetidos.")
    if decision == "aceptar" and defectos:
        raise EtiquetaInvalida("Si aceptas, no puede haber defectos.")
    if decision == "devolver" and not defectos:
        raise EtiquetaInvalida("Si devuelves, indica al menos un defecto.")
    if tipo not in tipos:
        raise EtiquetaInvalida(f"Tipo inválido: {tipo}. Opciones: {', '.join(tipos)}")
    if estimacion is not None and estimacion not in ESCALA:
        raise EtiquetaInvalida(f"La estimación debe ser de la escala {ESCALA}.")


def guardar(ruta: Path, fila: dict) -> None:
    nuevo = not ruta.exists()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS)
        if nuevo:
            w.writeheader()
        w.writerow({c: fila.get(c, "") for c in COLUMNAS})


# ================================================================= interfaz de consola
def _mostrar_caso(caso: dict, n: int, total: int, salida: Callable[[str], None]) -> None:
    ancho = 92
    salida("\n" + "=" * ancho)
    salida(f"Caso {n} de {total} · {caso['id']} · proyecto {caso['proyecto']} · sistema {caso['sistema']}")
    salida("-" * ancho)
    salida(textwrap.fill(caso["texto"], ancho))
    if caso.get("criterios_aceptacion"):
        salida("\nCriterios de aceptación:")
        salida(caso["criterios_aceptacion"])
    else:
        salida("\n(Sin criterios de aceptación)")


def _pedir_defectos(criterios: list, entrada: Callable[[str], str], salida: Callable[[str], None]) -> list[str]:
    numerados = {str(i): c.id for i, c in enumerate(criterios, start=1)}
    for i, c in enumerate(criterios, start=1):
        salida(f"  {i:>2}. {c.id:<8} {c.nombre}")
    bruto = entrada("Defectos (números o ids separados por coma; vacío = ninguno): ").strip()
    if not bruto:
        return []
    return [numerados.get(p.strip(), p.strip().upper()) for p in bruto.split(",") if p.strip()]


def etiquetar(anotador: str, piloto: bool, entrada: Callable[[str], str] = input,
              salida: Callable[[str], None] = print, casos_ruta: Path | None = None,
              contexto_ruta: Path | None = None, carpeta: Path = CARPETA, catalogo_ruta: Path = CATALOGO,
              conjunto: str = "generico") -> int:
    if conjunto not in CONJUNTOS:
        raise EtiquetaInvalida(f"Conjunto desconocido: {conjunto}. Opciones: {', '.join(CONJUNTOS)}")
    por_defecto_casos, por_defecto_contexto, sufijo = CONJUNTOS[conjunto]
    casos_ruta, contexto_ruta = casos_ruta or por_defecto_casos, contexto_ruta or por_defecto_contexto
    catalogo = cargar_catalogo(catalogo_ruta)
    casos = {c["id"]: c for c in leer_jsonl(casos_ruta)}
    contexto = leer_jsonl(contexto_ruta) if contexto_ruta.exists() else []
    indice = IndiceSimilitud({h["id"]: h["texto"] for h in contexto}) if contexto else None
    textos_contexto = {h["id"]: h["texto"] for h in contexto}
    ruta = ruta_anotador(anotador, carpeta, sufijo)
    hechos = ya_etiquetados(ruta)
    orden = orden_para(anotador, list(casos))
    if piloto:
        orden = orden[:TAMANO_PILOTO]
    pendientes = [i for i in orden if i not in hechos]
    tipos = catalogo.tipos_hu()
    salida(f"Anotador {anotador} · catálogo {catalogo.version} · {len(orden) - len(pendientes)} de {len(orden)} hechos"
           f"{' (piloto)' if piloto else ''}. Escribe 'salir' en cualquier pregunta para terminar.")
    for n, cid in enumerate(pendientes, start=len(orden) - len(pendientes) + 1):
        caso = casos[cid]
        criterios = catalogo.aplicables(caso["sistema"])
        permitidos = {c.id for c in criterios}
        while True:
            _mostrar_caso(caso, n, len(orden), salida)
            letra = entrada("Decisión [a]ceptar / [d]evolver / di[v]idir · [b]uscar parecidas: ").strip().lower()
            if letra == "salir":
                salida(f"Guardado en {ruta}. Puedes retomar cuando quieras.")
                return 0
            if letra == "b":
                if indice is None:
                    salida("No hay backlog de contexto.")
                else:
                    parecidas = [(h, s) for h, s in indice.buscar(caso["texto"], 6) if h != cid][:5]
                    for hid, s in parecidas:
                        salida(f"  {hid} ({s:.2f}): {textos_contexto[hid][:150]}")
                continue
            if letra not in DECISIONES:
                salida("Responde a, d o v.")
                continue
            decision = DECISIONES[letra]
            defectos = [] if decision == "aceptar" else _pedir_defectos(criterios, entrada, salida)
            if "SALIR" in defectos:
                return 0
            tipo = tipos[0] if len(tipos) == 1 else entrada(f"Tipo ({', '.join(tipos)}): ").strip()
            bruto = entrada(f"Estimación {ESCALA} (vacío = sin estimar): ").strip()
            try:
                estimacion = int(bruto) if bruto else None
                validar(decision, defectos, tipo, estimacion, permitidos, tipos)
            except (ValueError, EtiquetaInvalida) as e:
                salida(f"  ⚠ {e} Vuelve a etiquetar este caso.")
                continue
            comentario = entrada("Comentario (opcional): ").strip()
            guardar(ruta, {"id": cid, "decision": decision, "defectos": ";".join(defectos), "tipo": tipo,
                           "estimacion": estimacion or "", "comentario": comentario, "anotador": anotador,
                           "version_catalogo": catalogo.version, "hash_catalogo": catalogo.hash_sha256,
                           "fecha": datetime.now().isoformat(timespec="seconds")})
            break
    salida(f"\nListo: {len(orden)} casos etiquetados en {ruta}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description="Etiquetado del conjunto de evaluación (lo hace una persona)")
    ap.add_argument("--anotador", required=True, help="A o B (cada persona usa su letra)")
    ap.add_argument("--piloto", action="store_true", help=f"solo los primeros {TAMANO_PILOTO} casos de su orden")
    ap.add_argument("--conjunto", choices=tuple(CONJUNTOS), default="generico",
                    help="generico: los 40 casos de Dalpiaz; banca: el conjunto bancario complementario")
    args = ap.parse_args(argv)
    try:
        return etiquetar(args.anotador, args.piloto, conjunto=args.conjunto)
    except EtiquetaInvalida as e:
        print(e, file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nInterrumpido; lo etiquetado quedó guardado.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
