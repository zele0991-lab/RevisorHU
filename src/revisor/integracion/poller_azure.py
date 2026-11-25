"""
Poller de Azure DevOps: busca User Stories nuevas y lanza al agente revisor sobre cada una.

Uso (desde la raíz del repositorio):
    python -m revisor.integracion.poller_azure --una-vez            # simulado: sin costo
    python -m revisor.integracion.poller_azure --una-vez --real     # modelo real: cuesta dinero
    python -m revisor.integracion.poller_azure --una-vez --real --max-hu 1

Por qué polling y no webhooks (D-005): la organización de prueba no expone un endpoint
público y el polling se puede detener, repetir y probar sin red.

Qué hace cada ciclo:
    1. Pide al adaptador las HU pendientes (sin la etiqueta `ia-revisada`), sin pasar por MCP.
    2. Descarta las ya completadas o fallidas dos veces según `estado/azure_procesados.json`.
    3. Por cada HU, ejecuta el bucle del agente con `config/config_azure.json` y el aprobador
       desatendido. El agente deja un comentario y etiquetas; nunca aprueba ni cambia el estado.

Modo por defecto: SIMULADO (D-028). Solo con `--real` se llama al modelo.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Callable

from revisor.agente.bucle import CONFIGURACIONES, Opciones, Resultado, ejecutar
from revisor.backlog.puerto import ErrorBacklog, Historia, PuertoBacklog

RAZON_DESATENDIDA = "aprobada por la lista desatendida (config/azure_devops.json)"


class AprobadorDesatendido:
    """
    Sustituye a la persona que confirma las escrituras cuando el poller corre solo.

    La política del perfil `azure` pide confirmación para escribir. Esta clase aprueba solo
    las herramientas de `escrituras_desatendidas` y la traza lo registra con esa razón
    (D-029). `aprobar_para_fabrica` se deniega siempre, aunque alguien la agregue a la lista.
    """

    BLOQUEADAS = frozenset({"backlog__aprobar_para_fabrica"})

    def __init__(self, escrituras_desatendidas: list[str], caso: str | None = None):
        """
        `caso` es el id del work item que se está revisando. Si se indica, solo se aprueban
        escrituras sobre ese id: una instrucción inyectada no puede hacer que el agente
        comente o etiquete OTRA historia.
        """
        self._permitidas = frozenset(escrituras_desatendidas)
        self._caso = caso

    def __call__(self, nombre: str, argumentos: dict) -> tuple[bool, str]:
        if nombre in self.BLOQUEADAS:
            return False, f"'{nombre}' está bloqueada para el poller, sin importar la lista"
        if nombre not in self._permitidas:
            return False, f"'{nombre}' no está en escrituras_desatendidas"
        if self._caso is not None and str(argumentos.get("id", "")).strip() != self._caso:
            return False, f"el poller solo puede escribir en el work item {self._caso}, el que se está revisando"
        return True, RAZON_DESATENDIDA


# ================================================================= registro
class RegistroProcesados:
    """
    Recuerda qué HU ya se procesaron, para no revisarlas dos veces aunque el poller se reinicie.

    Valores por id: un `run_id` (completada), `{"fallos": 1, "motivo": ...}` (se reintenta una
    vez) o `{"fallido": true, "motivo": ...}` (no se vuelve a intentar).
    """

    def __init__(self, ruta: Path):
        self.ruta = ruta
        self.datos: dict = {}
        if ruta.exists():
            try:
                self.datos = json.loads(ruta.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                raise ErrorBacklog(f"{ruta} está dañado ({e.msg}); revísalo o bórralo para empezar de nuevo.") from None

    def omitir(self, id: str) -> bool:
        valor = self.datos.get(id)
        return isinstance(valor, str) or (isinstance(valor, dict) and valor.get("fallido") is True)

    def completada(self, id: str, run_id: str) -> None:
        self.datos[id] = run_id
        self._guardar()

    def fallo(self, id: str, motivo: str) -> None:
        anterior = self.datos.get(id)
        if isinstance(anterior, dict) and anterior.get("fallos", 0) >= 1:
            self.datos[id] = {"fallido": True, "motivo": motivo}
        else:
            self.datos[id] = {"fallos": 1, "motivo": motivo}
        self._guardar()

    def _guardar(self) -> None:
        """Escritura atómica: un corte a mitad de camino no deja el registro a medias."""
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        temporal = self.ruta.with_suffix(self.ruta.suffix + ".tmp")
        temporal.write_text(json.dumps(self.datos, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporal, self.ruta)


# ================================================================= ciclo
def ciclo(
    backlog: PuertoBacklog,
    registro: RegistroProcesados,
    max_hu: int,
    revisar: Callable[[Historia], Resultado],
    salida: Callable[[str], None] = print,
) -> list[tuple[str, str]]:
    """
    Un ciclo del poller. Devuelve [(id, resultado)] con resultado 'completada' o 'fallo'.

    Pide algunas HU de más porque las que el registro omite (por ejemplo, una que falló dos
    veces y sigue sin etiqueta) no deben ocupar el cupo de las nuevas.
    """
    omitibles = sum(1 for v in registro.datos.values() if isinstance(v, str) or
                    (isinstance(v, dict) and v.get("fallido") is True))
    candidatas = [h for h in backlog.listar_pendientes(min(max_hu + omitibles, 200)) if not registro.omitir(h.id)]
    elegidas = candidatas[:max_hu]
    if not elegidas:
        salida("Sin HU pendientes.")
        return []
    salida(f"HU a revisar en este ciclo: {', '.join(h.id for h in elegidas)}")
    hechas: list[tuple[str, str]] = []
    for h in elegidas:
        salida(f"\n=== Work item {h.id}: {h.titulo}")
        try:
            r = revisar(h)
        except Exception as e:  # una HU que falla no detiene a las demás
            motivo = f"{type(e).__name__}: {e}"
            registro.fallo(h.id, motivo)
            print(f"poller: el work item {h.id} falló ({motivo})", file=sys.stderr)
            hechas.append((h.id, "fallo"))
            continue
        if r.motivo_cierre == "end_turn" and r.decision:
            registro.completada(h.id, r.run_id)
            hechas.append((h.id, "completada"))
        else:
            motivo = f"motivo_cierre={r.motivo_cierre}" + (f" ({r.error})" if r.error else "") \
                     + ("" if r.decision else ", sin revisión registrada")
            registro.fallo(h.id, motivo)
            print(f"poller: el work item {h.id} no terminó bien ({motivo})", file=sys.stderr)
            hechas.append((h.id, "fallo"))
    return hechas


# ================================================================= CLI
def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="poller_azure", description="Revisa User Stories nuevas de Azure DevOps")
    ap.add_argument("--una-vez", action="store_true", help="hace un solo ciclo y termina (pruebas y demo)")
    ap.add_argument("--real", action="store_true", help="llama al modelo real (cuesta dinero); sin esto, simulado")
    ap.add_argument("--config", choices=CONFIGURACIONES, default="skill", help="skill (por defecto) o base")
    ap.add_argument("--max-hu", type=int, default=None,
                    help="máximo de HU por ciclo (por defecto, poller.max_hu_por_ciclo de la configuración)")
    ap.add_argument("--intervalo-segundos", type=int, default=None,
                    help="segundos entre ciclos (por defecto, poller.intervalo_minutos; mínimo 10). "
                         "Para la demo, por ejemplo 20")
    ap.add_argument("--config-azure", type=Path, default=Path("config/azure_devops.json"))
    ap.add_argument("--archivo-config", type=Path, default=Path("config/config_azure.json"))
    return ap.parse_args(argv)


def main(argv: list[str] | None = None, dormir: Callable[[float], None] = time.sleep) -> int:
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(errors="replace")
    args = _argumentos(argv)

    from dotenv import load_dotenv

    load_dotenv(Path(".env"))  # AZDO_* y, con --real, ANTHROPIC_API_KEY; nunca se imprimen

    from revisor.backlog.azure_devops import BacklogAzureDevOps

    try:
        config_azure = json.loads(args.config_azure.read_text(encoding="utf-8"))
        config = json.loads(args.archivo_config.read_text(encoding="utf-8"))
        backlog = BacklogAzureDevOps.desde_configuracion(args.config_azure)
        registro = RegistroProcesados(Path(config_azure["poller"]["registro_procesados"]))
    except (ErrorBacklog, OSError, json.JSONDecodeError, KeyError) as e:
        print(f"poller_azure no arranca: {e}", file=sys.stderr)
        return 2

    max_hu = args.max_hu if args.max_hu is not None else int(config_azure["poller"]["max_hu_por_ciclo"])
    if max_hu < 1:
        print("poller_azure: --max-hu debe ser al menos 1.", file=sys.stderr)
        return 2
    if args.intervalo_segundos is not None and args.intervalo_segundos < 10:
        # Un piso razonable: no saturar la API de Azure DevOps con consultas WIQL.
        print("poller_azure: --intervalo-segundos debe ser al menos 10.", file=sys.stderr)
        return 2
    intervalo_s = float(args.intervalo_segundos if args.intervalo_segundos is not None
                        else float(config_azure["poller"]["intervalo_minutos"]) * 60)
    intervalo_txt = f"{intervalo_s:g} s" if intervalo_s < 120 else f"{intervalo_s / 60:g} min"
    escrituras = config_azure.get("escrituras_desatendidas", [])

    if args.real:
        if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
            print("poller_azure: --real necesita ANTHROPIC_API_KEY en el entorno o en .env.", file=sys.stderr)
            return 2
        # El costo no se muestra en pantalla (pedido del responsable para la demo); queda en
        # cada traza como `costo_usd_estimado` y en docs/DECISIONES.md (D-032).
        print(f"MODO REAL: hasta {max_hu} HU por ciclo con {config['modelo']}.")
    else:
        print("MODO SIMULADO: el guion reemplaza al modelo (sin costo). "
              "Lee y escribe de verdad en Azure DevOps.")

    def revisar(h: Historia) -> Resultado:
        r = asyncio.run(ejecutar(Opciones(caso=h.id, config=args.config, simulado=not args.real,
                                          archivo_config=args.archivo_config,
                                          aprobador=AprobadorDesatendido(escrituras, caso=h.id))))
        print(f"   resultado: {r.decision or 'sin revisión'} · {r.motivo_cierre} · traza {r.ruta_traza}")
        return r

    try:
        while True:
            try:
                ciclo(backlog, registro, max_hu, revisar)
            except ErrorBacklog as e:
                print(f"poller_azure: el ciclo falló: {e}", file=sys.stderr)
                if args.una_vez:
                    return 1
            if args.una_vez:
                return 0
            print(f"\n[{time.strftime('%H:%M:%S')}] Próximo ciclo en {intervalo_txt} (Ctrl+C para salir).",
                  flush=True)
            dormir(intervalo_s)
    except KeyboardInterrupt:
        print("\nPoller detenido.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
