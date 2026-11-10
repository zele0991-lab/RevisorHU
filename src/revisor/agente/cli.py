"""
CLI `revisar`: revisa una HU con el agente y deja su traza.

Uso (desde la raíz del repositorio):
    revisar --caso HU-002 --config base --simulado      # sin clave ni costo
    revisar --caso HU-002 --config skill                # modelo real: cuesta dinero

El código de salida es 0 solo si el agente terminó por sí mismo (end_turn) y registró una
revisión; así un script puede detectar ejecuciones fallidas.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from revisor.agente.bucle import CONFIGURACIONES, ErrorConfiguracion, Opciones, ejecutar


def main(argv: list[str] | None = None) -> int:
    # En Windows, una salida redirigida puede no ser UTF-8: mejor un carácter reemplazado que un fallo.
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(errors="replace")

    ap = argparse.ArgumentParser(prog="revisar", description="Agente revisor de historias de usuario")
    ap.add_argument("--caso", required=True, help="id de la HU a revisar")
    ap.add_argument("--config", required=True, choices=CONFIGURACIONES,
                    help="skill (SKILL.md) o base (instrucciones genéricas)")
    ap.add_argument("--simulado", action="store_true", help="usa el guion en vez de la API (sin costo)")
    ap.add_argument("--repeticion", type=int, default=1)
    ap.add_argument("--archivo-config", type=Path, default=Path("config/config.json"))
    ap.add_argument("--guion", type=Path, default=None, help="guion del modo simulado")
    ap.add_argument("--modelo", default=None, help="sobrescribe el modelo de config.json")
    ap.add_argument("--carpeta-trazas", type=Path, default=None)
    args = ap.parse_args(argv)

    from dotenv import load_dotenv

    load_dotenv(Path(".env"))  # la clave nunca se imprime ni se escribe en la traza

    op = Opciones(caso=args.caso, config=args.config, repeticion=args.repeticion, simulado=args.simulado,
                  archivo_config=args.archivo_config, guion=args.guion, modelo=args.modelo,
                  carpeta_trazas=args.carpeta_trazas)
    try:
        r = asyncio.run(ejecutar(op))
    except (ErrorConfiguracion, FileNotFoundError) as e:
        print(f"revisar: {e}", file=sys.stderr)
        return 2

    denegadas = sum(1 for c in r.llamadas if c["decision"] == "denegar")
    print("\n== Resultado")
    print(f"   motivo de cierre : {r.motivo_cierre}" + (f" ({r.error})" if r.error else ""))
    print(f"   decisión         : {r.decision or 'ninguna (no registró revisión)'}")
    print(f"   pasos            : {r.pasos} · {len(r.llamadas)} llamadas ({denegadas} denegadas por la política)")
    print(f"   tokens           : {r.tokens['totales']} (entrada {r.tokens['entrada']}, salida {r.tokens['salida']}, "
          f"caché lectura {r.tokens['cache_lectura']}, caché escritura {r.tokens['cache_escritura']})")
    print(f"   modelo respondió : {', '.join(r.modelo_respondio) or '-'}"
          + ("  ¡CONTAMINADA: repetir!" if r.contaminada else ""))
    print(f"   duración         : {r.duracion_s} s")
    print(f"   traza            : {r.ruta_traza}")
    return 0 if r.motivo_cierre == "end_turn" and r.decision else 1


if __name__ == "__main__":
    sys.exit(main())
