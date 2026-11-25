"""
Traza JSONL: un archivo por ejecución, un evento por línea.

Por qué tan detallada:
    Toda cifra del artículo tiene que regenerarse desde las trazas (condición no negociable
    del curso). Por eso el evento `inicio` fija TODO lo que define el experimento (modelo,
    effort, hashes del prompt, del catálogo y de los datos, commit) y el evento `fin` todo lo
    que se mide (decisión, tokens, duración, modelo que respondió realmente).

Compatibilidad con el kit:
    Usa los mismos campos que `leer_traza.py` (t, tipo, paso, nombre, argumentos, decision,
    razon, es_error, salida, uso; y en `fin`: motivo, pasos, tokens_entrada, tokens_salida,
    duracion_s), así que el lector del kit también la entiende.

Secretos:
    Antes de escribir, se reemplaza cualquier aparición de los valores de las variables de
    entorno secretas (clave de la API, PAT de Azure DevOps) por "***". Ninguna clave puede
    terminar en una traza versionada.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

VARIABLES_SECRETAS = ("ANTHROPIC_API_KEY", "AZDO_PAT")
MAX_SALIDA = 4000


def _secretos() -> list[str]:
    # Solo valores de longitud razonable: enmascarar "" o "a" rompería todo el texto.
    return [v for k in VARIABLES_SECRETAS if len(v := os.environ.get(k, "")) >= 8]


def enmascarar(valor, secretos: list[str] | None = None):
    """Recorre el valor (dict, lista o texto) y reemplaza los secretos por '***'."""
    secretos = _secretos() if secretos is None else secretos
    if not secretos:
        return valor
    if isinstance(valor, str):
        for s in secretos:
            valor = valor.replace(s, "***")
        return valor
    if isinstance(valor, dict):
        return {k: enmascarar(v, secretos) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [enmascarar(v, secretos) for v in valor]
    return valor


def sha256_archivos(*rutas: Path | str) -> str | None:
    """Hash conjunto de uno o más archivos (en bytes, ver D-014). None si alguno no existe."""
    h = hashlib.sha256()
    for ruta in rutas:
        ruta = Path(ruta)
        if not ruta.exists():
            return None
        h.update(ruta.name.encode("utf-8") + b"\0")
        h.update(ruta.read_bytes())
    return h.hexdigest()


def sha256_texto(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def estado_git(raiz: Path | str = ".") -> dict:
    """
    Commit actual y si hay cambios sin confirmar: una ejecución con cambios no es reproducible.

    No cuenta lo que está bajo `trazas/`: son salidas, no entradas. Si contaran, la propia traza
    recién creada haría que toda ejecución pareciera hecha con cambios (D-037).
    """
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=raiz, capture_output=True,
                                text=True, timeout=10).stdout.strip() or None
        cambios = subprocess.run(["git", "status", "--porcelain"], cwd=raiz, capture_output=True,
                                 text=True, timeout=10).stdout
        entradas = [l for l in cambios.splitlines() if l.strip() and not l[3:].strip('"').startswith("trazas/")]
        return {"commit": commit, "cambios_sin_confirmar": bool(entradas)}
    except (OSError, subprocess.SubprocessError):
        return {"commit": None, "cambios_sin_confirmar": None}


class Traza:
    def __init__(self, carpeta: Path | str, run_id: str):
        carpeta = Path(carpeta)
        carpeta.mkdir(parents=True, exist_ok=True)
        self.ruta = carpeta / f"{run_id}.jsonl"
        self._fh = self.ruta.open("w", encoding="utf-8", newline="\n")
        self._secretos = _secretos()

    def evento(self, tipo: str, **datos) -> None:
        registro = {"t": datetime.now().isoformat(timespec="milliseconds"), "tipo": tipo, **datos}
        linea = json.dumps(enmascarar(registro, self._secretos), ensure_ascii=False, default=str)
        self._fh.write(linea + "\n")
        self._fh.flush()

    def cerrar(self) -> None:
        if not self._fh.closed:
            self._fh.close()

    def __enter__(self) -> "Traza":
        return self

    def __exit__(self, *exc) -> None:
        self.cerrar()


def leer_eventos(ruta: Path | str) -> list[dict]:
    return [json.loads(l) for l in Path(ruta).read_text(encoding="utf-8").splitlines() if l.strip()]
