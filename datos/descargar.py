"""
Descarga los datos públicos del conjunto de evaluación (F5) a `datos/crudos/`, que no se versiona.

Fuentes (licencias en datos/LICENCIAS.md):
    - Dalpiaz, "Requirements data sets (user stories)", Mendeley Data, v1,
      doi:10.17632/7zbk8zsd8y.1, CC BY 4.0. 22 proyectos con HU reales en texto plano.
    - TAWOS (Tawosi et al., MSR 2022), doi:10.5522/04/21308124, Apache 2.0. Volcado MySQL de
      issues de Jira con story points reales. De aquí solo se extrae una muestra de historias
      para la estimación por analogía (`datos/referencias/referencias_tawos.jsonl`).

Uso (desde la raíz del repositorio):
    python datos/descargar.py                 # todo
    python datos/descargar.py --solo dalpiaz
    python datos/descargar.py --solo tawos    # descarga 637 MB si el zip no está

Por qué se lee el volcado de TAWOS línea por línea y no con MySQL:
    instalar un servidor de base de datos para leer una tabla haría el experimento difícil de
    reproducir. El volcado usa `INSERT INTO ... VALUES (...),(...);`, y un analizador pequeño
    basta. De cada issue se toman solo la clave, el título, la descripción en texto, el tipo, los
    story points y el proyecto: nunca los ids de creador, informante o responsable.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Iterator

RAIZ = Path(__file__).resolve().parent.parent
CRUDOS = RAIZ / "datos" / "crudos"
REFERENCIAS = RAIZ / "datos" / "referencias" / "referencias_tawos.jsonl"

DALPIAZ_API = "https://data.mendeley.com/public-api/datasets/7zbk8zsd8y/files?folder_id=root&version=1"
TAWOS_ZIP_URL = "https://ndownloader.figshare.com/files/37806375"
AGENTE = "RevisorHU-descarga/1.0 (investigacion academica)"

# Columnas de la tabla Issue en el orden del esquema oficial de TAWOS
# (TAWOS_Database_Schema_Creation_Script.sql). Solo se usan las marcadas abajo.
COLUMNAS_ISSUE = (
    "ID", "Jira_ID", "Issue_Key", "URL", "Title", "Description", "Description_Text",
    "Description_Code", "Type", "Priority", "Status", "Resolution", "Creation_Date",
    "Estimation_Date", "Resolution_Date", "Last_Updated", "Story_Point", "Timespent",
    "In_Progress_Minutes", "Total_Effort_Minutes", "Resolution_Time_Minutes",
    "Title_Changed_After_Estimation", "Description_Changed_After_Estimation",
    "Story_Point_Changed_After_Estimation", "Pull_Request_URL", "Creator_ID", "Reporter_ID",
    "Assignee_ID", "Project_ID", "Sprint_ID",
)
ESCALA = (1, 2, 3, 5, 8, 13)
POR_PUNTAJE = 25            # 25 historias por valor de la escala: 150 referencias
LARGO_TEXTO = (60, 700)     # descarta descripciones vacías o muy largas
_RE_CORREO = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_RE_URL = re.compile(r"https?://\S+")


# ================================================================= utilidades
def _bajar(url: str, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    peticion = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    temporal = destino.with_suffix(destino.suffix + ".parcial")
    with urllib.request.urlopen(peticion, timeout=120) as r, temporal.open("wb") as f:
        while bloque := r.read(1 << 20):
            f.write(bloque)
    temporal.replace(destino)


def _sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        while bloque := f.read(1 << 20):
            h.update(bloque)
    return h.hexdigest()


# ================================================================= Dalpiaz
def descargar_dalpiaz() -> Path:
    """Baja los 22 archivos .txt y escribe un manifiesto con su sha256."""
    carpeta = CRUDOS / "dalpiaz"
    peticion = urllib.request.Request(DALPIAZ_API, headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(peticion, timeout=60) as r:
        archivos = json.loads(r.read().decode("utf-8"))
    manifiesto = {}
    for a in sorted(archivos, key=lambda x: x["filename"]):
        nombre = a["filename"]
        if not nombre.endswith(".txt"):
            continue
        destino = carpeta / nombre
        if not destino.exists():
            _bajar(a["content_details"]["download_url"], destino)
        manifiesto[nombre] = _sha256(destino)
    (carpeta / "manifiesto.json").write_text(json.dumps(manifiesto, indent=2), encoding="utf-8")
    print(f"Dalpiaz: {len(manifiesto)} archivos en {carpeta}")
    return carpeta


def leer_dalpiaz(ruta: Path) -> list[tuple[int, str]]:
    """
    Devuelve (número de línea, HU) de un archivo de Dalpiaz, sin líneas vacías.

    Algunos archivos vienen en UTF-8 y otros en Windows-1252 (por ejemplo, el apóstrofo ’ de
    g13-planningpoker); se prueba UTF-8 primero.
    """
    crudo = ruta.read_bytes()
    try:
        texto = crudo.decode("utf-8")
    except UnicodeDecodeError:
        texto = crudo.decode("cp1252", errors="replace")
    texto = texto.replace("﻿", "").replace("’", "'").replace("‘", "'")
    return [(n, linea.strip()) for n, linea in enumerate(texto.splitlines(), start=1) if linea.strip()]


# ================================================================= TAWOS
def valores_sql(linea: str) -> Iterator[list]:
    """
    Recorre las tuplas de una línea `INSERT INTO ... VALUES (...),(...);` de mysqldump.

    Entiende cadenas entre comillas simples con escapes de barra invertida, números y NULL.
    Devuelve cada tupla como lista de str | float | int | None.
    """
    i = linea.find(" VALUES ")
    if i < 0:
        return
    i += len(" VALUES ")
    n = len(linea)
    escapes = {"n": "\n", "r": "\r", "t": "\t", "0": "\0", "Z": "\x1a", "b": "\b"}
    while i < n:
        if linea[i] != "(":
            i += 1
            continue
        i += 1
        fila: list = []
        while True:
            c = linea[i]
            if c == "'":
                i += 1
                partes = []
                while True:
                    c = linea[i]
                    if c == "\\":
                        siguiente = linea[i + 1]
                        partes.append(escapes.get(siguiente, siguiente))
                        i += 2
                    elif c == "'":
                        if i + 1 < n and linea[i + 1] == "'":
                            partes.append("'")
                            i += 2
                        else:
                            i += 1
                            break
                    else:
                        j = i
                        while linea[j] not in "\\'":
                            j += 1
                        partes.append(linea[i:j])
                        i = j
                fila.append("".join(partes))
            else:
                j = i
                while linea[j] not in ",)":
                    j += 1
                bruto = linea[i:j].strip()
                if bruto == "NULL":
                    fila.append(None)
                else:
                    try:
                        fila.append(int(bruto))
                    except ValueError:
                        try:
                            fila.append(float(bruto))
                        except ValueError:
                            fila.append(bruto)
                i = j
            if linea[i] == ",":
                i += 1
                continue
            if linea[i] == ")":
                i += 1
                yield fila
                break


def _limpiar(texto: str) -> str:
    """Quita URLs, espacios repetidos y las comillas con que TAWOS envuelve título y descripción."""
    texto = _RE_URL.sub("[URL]", texto)
    texto = " ".join(texto.split())
    while len(texto) >= 2 and texto[0] == texto[-1] and texto[0] in "\"'":
        texto = texto[1:-1].strip()
    while '""' in texto:  # TAWOS escribe las comillas internas duplicadas
        texto = texto.replace('""', '"')
    return texto


def candidata(fila: list) -> dict | None:
    """Convierte una fila de Issue en referencia si cumple los filtros; si no, None."""
    if len(fila) != len(COLUMNAS_ISSUE):
        return None
    r = dict(zip(COLUMNAS_ISSUE, fila))
    puntos = r["Story_Point"]
    if r["Type"] != "Story" or puntos is None or float(puntos) not in ESCALA:
        return None
    # Solo estimaciones estables: el título, la descripción y los puntos no cambiaron después.
    if any(r[c] for c in ("Title_Changed_After_Estimation", "Description_Changed_After_Estimation",
                          "Story_Point_Changed_After_Estimation")):
        return None
    titulo = _limpiar(str(r["Title"] or ""))
    descripcion = _limpiar(str(r["Description_Text"] or ""))
    texto = f"{titulo}. {descripcion}" if descripcion else titulo
    if not (LARGO_TEXTO[0] <= len(texto) <= LARGO_TEXTO[1]) or _RE_CORREO.search(texto):
        return None
    return {"id": f"TAWOS-{r['Issue_Key']}", "texto": texto, "story_points": int(float(puntos)),
            "proyecto": str(r["Issue_Key"]).split("-")[0], "fuente": "TAWOS"}


def muestra_estable(candidatas: list[dict], por_puntaje: int = POR_PUNTAJE,
                    max_por_proyecto: int = 4) -> list[dict]:
    """
    Elige `por_puntaje` referencias por valor de la escala, ordenando por el sha1 del id.

    Es determinista: el mismo volcado siempre da la misma muestra, sin semilla aleatoria. Toma a lo
    sumo `max_por_proyecto` historias de un mismo proyecto por valor, para que un proyecto grande
    no acapare la muestra; si no alcanza, completa con las siguientes en el mismo orden.
    """
    elegidas = []
    for sp in ESCALA:
        grupo = sorted((c for c in candidatas if c["story_points"] == sp),
                       key=lambda c: hashlib.sha1(c["id"].encode()).hexdigest())
        tomadas: list[dict] = []
        por_proyecto: dict[str, int] = {}
        for c in grupo:
            if len(tomadas) == por_puntaje:
                break
            if por_proyecto.get(c["proyecto"], 0) < max_por_proyecto:
                tomadas.append(c)
                por_proyecto[c["proyecto"]] = por_proyecto.get(c["proyecto"], 0) + 1
        resto = [c for c in grupo if c not in tomadas]
        tomadas.extend(resto[:por_puntaje - len(tomadas)])
        elegidas.extend(tomadas)
    return elegidas


def extraer_referencias(zip_tawos: Path, destino: Path = REFERENCIAS) -> int:
    candidatas: list[dict] = []
    with zipfile.ZipFile(zip_tawos) as z:
        sql = next(n for n in z.namelist() if n.endswith(".sql"))
        with z.open(sql) as crudo:
            for linea in io.TextIOWrapper(crudo, encoding="utf-8", errors="replace"):
                if linea.startswith("INSERT INTO `Issue` VALUES"):
                    for fila in valores_sql(linea):
                        c = candidata(fila)
                        if c:
                            candidatas.append(c)
    elegidas = muestra_estable(candidatas)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8", newline="\n") as f:
        for r in elegidas:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"TAWOS: {len(candidatas)} historias candidatas; {len(elegidas)} referencias en {destino}")
    return len(elegidas)


def descargar_tawos() -> None:
    zip_tawos = CRUDOS / "tawos" / "TAWOS.sql.zip"
    if not zip_tawos.exists():
        print("TAWOS: descargando 637 MB (puede tardar varios minutos)...")
        _bajar(TAWOS_ZIP_URL, zip_tawos)
    extraer_referencias(zip_tawos)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Descarga los datos públicos de la F5")
    ap.add_argument("--solo", choices=("dalpiaz", "tawos"), default=None)
    args = ap.parse_args(argv)
    if args.solo in (None, "dalpiaz"):
        descargar_dalpiaz()
    if args.solo in (None, "tawos"):
        descargar_tawos()
    return 0


if __name__ == "__main__":
    sys.exit(main())
