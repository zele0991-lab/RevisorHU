"""
Catálogo de criterios: el ÚNICO módulo que lee `conocimiento/criterios.yaml`.

Por qué un solo módulo:
    Los servidores, la herramienta de etiquetado y las métricas consumen el catálogo desde
    aquí. Si cada uno leyera el YAML por su cuenta, tarde o temprano interpretarían las
    reglas de forma distinta, y el experimento dejaría de medir lo mismo.

Por qué una validación tan estricta:
    Un error en el YAML no debe producir un comportamiento silencioso (por ejemplo, un
    `aplica_a: [banca_movl]` con un error de escritura haría que el criterio nunca se
    aplique). Si el archivo es inválido, el sistema NO arranca y el mensaje dice qué
    criterio y qué campo fallan. Nunca se corre con un catálogo a medias.

Versión y hash:
    `version` y `hash_sha256` se escriben en cada traza para saber con qué reglas se evaluó
    cada HU. El hash se calcula sobre los bytes del archivo (ver D-014 sobre los saltos de línea).
"""

from __future__ import annotations

import datetime as dt
import difflib
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

RUTA_POR_DEFECTO = Path("conocimiento/criterios.yaml")

# Semántica fija del esquema (no son reglas de negocio): por eso viven en el código.
# Las categorías, los sistemas y los tipos de HU, en cambio, se declaran en el YAML.
SEVERIDADES = ("bloqueante", "mayor", "menor")
ESTADOS = ("activo", "obsoleto")
# Formatos de criterios de aceptación que el servidor sabe validar. Cuál se usa lo decide el
# YAML (`formato_criterios_aceptacion`): pasar de uno a otro es editar datos (D-027).
FORMATOS_CRITERIOS = ("lista", "gherkin")
TODOS = "todos"
PATRON_ID = re.compile(r"^[A-Z]{2,5}-\d{3}$")
PATRON_VERSION = re.compile(r"^\d+\.\d+\.\d+$")

CAMPOS_TEXTO = ("nombre", "descripcion", "como_verificar", "ejemplo_cumple", "ejemplo_no_cumple")
CAMPOS_OBLIGATORIOS = ("id", "categoria", *CAMPOS_TEXTO, "severidad", "aplica_a", "estado")
CAMPOS_PERMITIDOS = frozenset((*CAMPOS_OBLIGATORIOS, "reemplazado_por"))
CABECERA_OBLIGATORIA = ("version", "fecha", "categorias", "sistemas", "tipos_hu",
                        "formato_criterios_aceptacion", "criterios")


class CatalogoInvalido(Exception):
    """El catálogo no se puede usar. `errores` trae cada problema por separado."""

    def __init__(self, ruta: Path, errores: list[str]):
        self.ruta = ruta
        self.errores = errores
        lineas = "\n".join(f"  - {e}" for e in errores)
        super().__init__(f"Catálogo de criterios inválido ({ruta}). El sistema no arranca hasta corregirlo:\n{lineas}")


@dataclass(frozen=True)
class Criterio:
    id: str
    categoria: str
    nombre: str
    descripcion: str
    como_verificar: str
    ejemplo_cumple: str
    ejemplo_no_cumple: str
    severidad: str
    aplica_a: tuple[str, ...]
    estado: str
    reemplazado_por: str | None = None

    @property
    def activo(self) -> bool:
        return self.estado == "activo"

    def aplica(self, sistema: str) -> bool:
        return TODOS in self.aplica_a or sistema in self.aplica_a

    def resumen(self) -> dict:
        """Solo lo necesario para listar: así el costo en tokens no crece con el detalle."""
        return {"id": self.id, "nombre": self.nombre, "severidad": self.severidad}

    def detalle(self) -> dict:
        datos = {
            "id": self.id, "categoria": self.categoria, "nombre": self.nombre,
            "descripcion": self.descripcion, "como_verificar": self.como_verificar,
            "ejemplo_cumple": self.ejemplo_cumple, "ejemplo_no_cumple": self.ejemplo_no_cumple,
            "severidad": self.severidad, "aplica_a": list(self.aplica_a), "estado": self.estado,
        }
        if self.reemplazado_por:
            datos["reemplazado_por"] = self.reemplazado_por
        return datos


@dataclass(frozen=True)
class Catalogo:
    """Catálogo validado. Implementa `FuenteReglas` (la interfaz que usa servidor_backlog)."""

    ruta: Path
    version: str
    fecha: str
    hash_sha256: str
    categorias: tuple[str, ...]
    sistemas: tuple[str, ...]
    _tipos_hu: tuple[str, ...]
    _formato_criterios: str
    criterios: tuple[Criterio, ...]

    # ------------------------------------------------------------ FuenteReglas
    def tipos_hu(self) -> list[str]:
        return list(self._tipos_hu)

    def formato_criterios_aceptacion(self) -> str:
        return self._formato_criterios

    def ids_defectos_aplicables(self, sistema: str) -> set[str]:
        return {c.id for c in self.aplicables(sistema)}

    # ------------------------------------------------------------ consultas
    @property
    def sistemas_validos(self) -> tuple[str, ...]:
        """Los sistemas declarados más `todos` (una HU sin sistema mapeado usa solo los generales)."""
        return (*self.sistemas, TODOS)

    def obtener(self, id: str) -> Criterio | None:
        return next((c for c in self.criterios if c.id == id), None)

    def vigente(self, id: str) -> Criterio | None:
        """Sigue la cadena de `reemplazado_por` hasta el criterio activo (validado: sin ciclos)."""
        c = self.obtener(id)
        while c is not None and not c.activo:
            c = self.obtener(c.reemplazado_por or "")
        return c

    def aplicables(self, sistema: str, categoria: str | None = None) -> list[Criterio]:
        """Criterios ACTIVOS que aplican al sistema (generales + los del sistema), en orden del archivo."""
        return [
            c for c in self.criterios
            if c.activo and c.aplica(sistema) and (categoria is None or c.categoria == categoria)
        ]

    def sugerir(self, id: str, n: int = 3) -> list[str]:
        """Ids parecidos, para que un error de tipeo del modelo tenga una salida útil."""
        ids = [c.id for c in self.criterios]
        return difflib.get_close_matches(id.upper(), ids, n=n, cutoff=0.5)

    def ids_activos(self) -> list[str]:
        return [c.id for c in self.criterios if c.activo]


# ===================================================================== carga y validación
def _texto(valor) -> bool:
    return isinstance(valor, str) and bool(valor.strip())


def _validar_lista(nombre: str, valor, errores: list[str]) -> tuple[str, ...]:
    if not isinstance(valor, list) or not valor or not all(_texto(v) for v in valor):
        errores.append(f"cabecera, campo '{nombre}': debe ser una lista no vacía de textos.")
        return ()
    repetidos = sorted({v for v in valor if valor.count(v) > 1})
    if repetidos:
        errores.append(f"cabecera, campo '{nombre}': valores repetidos: {', '.join(repetidos)}.")
    return tuple(valor)


def _validar_cabecera(datos: dict, errores: list[str]) -> tuple[str, str, tuple, tuple, tuple, str]:
    for campo in CABECERA_OBLIGATORIA:
        if campo not in datos:
            errores.append(f"cabecera: falta el campo obligatorio '{campo}'.")
    desconocidos = sorted(set(datos) - set(CABECERA_OBLIGATORIA))
    if desconocidos:
        errores.append(f"cabecera: campos desconocidos: {', '.join(desconocidos)}.")

    version = datos.get("version")
    if "version" in datos and not (isinstance(version, str) and PATRON_VERSION.match(version)):
        errores.append(
            f"cabecera, campo 'version': '{version}' no es válida; usa el formato X.Y.Z entre comillas (por ejemplo \"1.0.0\")."
        )
    fecha = datos.get("fecha")
    if isinstance(fecha, dt.date):
        fecha = fecha.isoformat()
    elif "fecha" in datos:
        try:
            fecha = dt.date.fromisoformat(str(fecha)).isoformat()
        except ValueError:
            errores.append(f"cabecera, campo 'fecha': '{fecha}' no es una fecha válida (AAAA-MM-DD).")

    categorias = _validar_lista("categorias", datos.get("categorias"), errores) if "categorias" in datos else ()
    sistemas = _validar_lista("sistemas", datos.get("sistemas"), errores) if "sistemas" in datos else ()
    if TODOS in sistemas:
        errores.append(f"cabecera, campo 'sistemas': '{TODOS}' es reservado; no lo declares como sistema.")
    tipos = _validar_lista("tipos_hu", datos.get("tipos_hu"), errores) if "tipos_hu" in datos else ()
    formato = datos.get("formato_criterios_aceptacion")
    if "formato_criterios_aceptacion" in datos and formato not in FORMATOS_CRITERIOS:
        errores.append(f"cabecera, campo 'formato_criterios_aceptacion': '{formato}' no es válido; "
                       f"usa {' o '.join(FORMATOS_CRITERIOS)}.")
    return str(version), str(fecha), categorias, sistemas, tipos, str(formato)


def _validar_criterio(i: int, r, categorias, sistemas, errores: list[str]) -> Criterio | None:
    if not isinstance(r, dict):
        errores.append(f"criterio #{i + 1}: debe ser un objeto con campos (id, categoria, …).")
        return None
    cid = r.get("id")
    quien = f"criterio {cid}" if _texto(cid) else f"criterio #{i + 1} (sin id)"
    n_antes = len(errores)

    for campo in CAMPOS_OBLIGATORIOS:
        if campo not in r or r[campo] is None:
            errores.append(f"{quien}, campo '{campo}': falta (es obligatorio).")
    desconocidos = sorted(set(r) - CAMPOS_PERMITIDOS)
    if desconocidos:
        errores.append(f"{quien}: campos desconocidos: {', '.join(desconocidos)} (¿error de escritura?).")

    if "id" in r and r["id"] is not None and not (isinstance(cid, str) and PATRON_ID.match(cid)):
        errores.append(f"{quien}, campo 'id': '{cid}' no tiene el formato correcto (2 a 5 mayúsculas, guion, 3 dígitos; por ejemplo ABC-001).")
    for campo in CAMPOS_TEXTO:
        if campo in r and r[campo] is not None and not _texto(r[campo]):
            errores.append(f"{quien}, campo '{campo}': debe ser un texto no vacío.")
    if r.get("categoria") is not None and r.get("categoria") not in categorias:
        errores.append(f"{quien}, campo 'categoria': '{r.get('categoria')}' no está en 'categorias' ({', '.join(categorias)}).")
    if r.get("severidad") is not None and r.get("severidad") not in SEVERIDADES:
        errores.append(f"{quien}, campo 'severidad': '{r.get('severidad')}' no es válida; usa {', '.join(SEVERIDADES)}.")
    estado = r.get("estado")
    if estado is not None and estado not in ESTADOS:
        errores.append(f"{quien}, campo 'estado': '{estado}' no es válido; usa {', '.join(ESTADOS)}.")

    aplica_a = r.get("aplica_a")
    if aplica_a is not None:
        if not isinstance(aplica_a, list) or not aplica_a or not all(_texto(s) for s in aplica_a):
            errores.append(f"{quien}, campo 'aplica_a': debe ser una lista no vacía de sistemas, o [{TODOS}].")
        elif TODOS in aplica_a and len(aplica_a) > 1:
            errores.append(f"{quien}, campo 'aplica_a': '{TODOS}' va solo; no lo combines con otros sistemas.")
        else:
            fuera = [s for s in aplica_a if s != TODOS and s not in sistemas]
            if fuera:
                errores.append(f"{quien}, campo 'aplica_a': {', '.join(fuera)} no está en 'sistemas' ({', '.join(sistemas)}).")

    reemplazo = r.get("reemplazado_por")
    if estado == "obsoleto" and not _texto(reemplazo):
        errores.append(f"{quien}, campo 'reemplazado_por': falta; un criterio obsoleto debe indicar qué id lo reemplaza.")
    if estado == "activo" and reemplazo is not None:
        errores.append(f"{quien}, campo 'reemplazado_por': solo se usa en criterios obsoletos.")

    if len(errores) > n_antes:
        return None
    return Criterio(
        id=cid, categoria=r["categoria"], nombre=r["nombre"].strip(), descripcion=r["descripcion"].strip(),
        como_verificar=r["como_verificar"].strip(), ejemplo_cumple=r["ejemplo_cumple"].strip(),
        ejemplo_no_cumple=r["ejemplo_no_cumple"].strip(), severidad=r["severidad"],
        aplica_a=tuple(aplica_a), estado=estado, reemplazado_por=reemplazo,
    )


def _validar_reemplazos(criterios: list[Criterio], errores: list[str]) -> None:
    por_id = {c.id: c for c in criterios}
    for c in criterios:
        if c.activo:
            continue
        if c.reemplazado_por not in por_id:
            errores.append(f"criterio {c.id}, campo 'reemplazado_por': '{c.reemplazado_por}' no existe en el catálogo.")
            continue
        visitados, actual = {c.id}, por_id[c.reemplazado_por]
        while not actual.activo:
            if actual.id in visitados or actual.reemplazado_por not in por_id:
                errores.append(
                    f"criterio {c.id}, campo 'reemplazado_por': la cadena de reemplazos no termina en un criterio activo."
                )
                break
            visitados.add(actual.id)
            actual = por_id[actual.reemplazado_por]


def cargar_catalogo(ruta: Path | str = RUTA_POR_DEFECTO) -> Catalogo:
    """Lee, valida y devuelve el catálogo. Lanza `CatalogoInvalido` con TODOS los errores encontrados."""
    ruta = Path(ruta)
    if not ruta.exists():
        raise CatalogoInvalido(ruta, [f"no existe el archivo {ruta}. ¿Se ejecutó desde la raíz del repositorio?"])
    contenido = ruta.read_bytes()
    try:
        datos = yaml.safe_load(contenido.decode("utf-8"))
    except (yaml.YAMLError, UnicodeDecodeError) as e:
        raise CatalogoInvalido(ruta, [f"el archivo no es YAML válido: {e}"]) from e
    if not isinstance(datos, dict):
        raise CatalogoInvalido(ruta, ["el archivo debe tener una cabecera (version, fecha, …) y la lista 'criterios'."])

    errores: list[str] = []
    version, fecha, categorias, sistemas, tipos, formato = _validar_cabecera(datos, errores)

    crudos = datos.get("criterios")
    criterios: list[Criterio] = []
    if not isinstance(crudos, list) or not crudos:
        errores.append("cabecera, campo 'criterios': debe ser una lista no vacía.")
        crudos = []
    vistos: dict[str, int] = {}
    for i, r in enumerate(crudos):
        cid = r.get("id") if isinstance(r, dict) else None
        if isinstance(cid, str) and cid in vistos:
            errores.append(f"criterio {cid}, campo 'id': id duplicado (también en el criterio #{vistos[cid] + 1}). Los ids nunca se repiten.")
            continue
        if isinstance(cid, str):
            vistos[cid] = i
        c = _validar_criterio(i, r, categorias, sistemas, errores)
        if c is not None:
            criterios.append(c)

    _validar_reemplazos(criterios, errores)
    # Se mira el estado DECLARADO: si un criterio activo tiene otro error, ya se informó ese
    # error; decir además "no hay activos" sería ruido que confunde a quien corrige el YAML.
    if crudos and not any(isinstance(r, dict) and r.get("estado") == "activo" for r in crudos):
        errores.append("el catálogo no tiene ningún criterio activo.")

    if errores:
        raise CatalogoInvalido(ruta, errores)
    return Catalogo(
        ruta=ruta, version=version, fecha=fecha, hash_sha256=hashlib.sha256(contenido).hexdigest(),
        categorias=categorias, sistemas=sistemas, _tipos_hu=tipos, _formato_criterios=formato,
        criterios=tuple(criterios),
    )
