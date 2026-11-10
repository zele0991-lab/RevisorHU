"""
Validaciones del lado del servidor para las escrituras del backlog.

Por qué en el servidor y no en el agente:
    Defensa en profundidad. El servidor no confía en el modelo: aunque una HU envenenada
    convenza al agente de escribir algo indebido, el servidor lo rechaza. Además, la
    validación es la misma para cualquier backend (local o Azure DevOps).

Por qué se devuelven TODOS los errores juntos:
    Si el servidor rechazara de a uno, el modelo gastaría un paso (y tokens) por cada error.
    Con la lista completa corrige todo en un solo intento.

Las funciones son puras: reciben datos y devuelven listas de errores legibles.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence

from revisor import dominio
from revisor.backlog.puerto import Recomendacion

# ===================================================================== formato de HU
_PATRON_HU = re.compile(
    r"^\s*como\s+(?P<rol>.+?)\s*,?\s+quiero\s+(?P<accion>.+?)\s*,?\s+para\s+(?P<beneficio>.+?)\s*$",
    re.IGNORECASE | re.DOTALL,
)
_ARTICULOS = re.compile(r"^(un|una|el|la|los|las)\s+")


def _sin_tildes(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in t if not unicodedata.combining(c))


def es_formato_hu(texto: str) -> bool:
    """True si sigue "Como <rol>, quiero <acción>, para <beneficio>" (las comas son opcionales)."""
    return _PATRON_HU.match(texto) is not None


def rol_de(texto: str) -> str | None:
    """Rol normalizado (sin artículo, tildes ni mayúsculas) para comparar partes de una división."""
    m = _PATRON_HU.match(texto)
    if not m:
        return None
    rol = _sin_tildes(m.group("rol")).lower().strip()
    rol = re.sub(r"\s+", " ", rol)
    return _ARTICULOS.sub("", rol)


# ===================================================================== Gherkin
_PATRON_GHERKIN = re.compile(r"\bdado\b.*\bcuando\b.*\bentonces\b", re.IGNORECASE | re.DOTALL)


def es_gherkin(criterio: str) -> bool:
    """True si contiene, en este orden, Dado … Cuando … Entonces (Gherkin en español)."""
    return _PATRON_GHERKIN.search(criterio) is not None


# ===================================================================== datos personales
_CORREO = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_IBAN_CR = re.compile(r"\bCR\d{2}[ -]?(?:\d[ -]?){17}\d\b", re.IGNORECASE)
_SECUENCIA_DIGITOS = re.compile(r"(?<![\w.,])(?:\d[ -]?){8,18}\d(?![\w])")
_TELEFONO_CON_PREFIJO = re.compile(r"\+?506[ -]?\d{4}[ -]?\d{4}\b")
_TELEFONO = re.compile(r"(?<![\d-])[2-8]\d{3}[ -]\d{4}(?![\d-])")


def _luhn(digitos: str) -> bool:
    total = 0
    for i, c in enumerate(reversed(digitos)):
        d = int(c)
        if i % 2 == 1:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


def _enmascarar(fragmento: str) -> str:
    """No repetimos el dato completo en el mensaje de error: eso también sería exponerlo."""
    return fragmento[:2] + "***"


def buscar_datos_personales(texto: str) -> list[tuple[str, str]]:
    """
    Devuelve pares (tipo, fragmento enmascarado) de posibles datos personales.

    Tipos: correo, número de cuenta (IBAN o 10+ dígitos), tarjeta (13-19 dígitos que pasan
    Luhn), cédula (9 dígitos, con o sin guiones) y teléfono de Costa Rica (+506 o dddd-dddd).

    Por qué un número suelto de 8 dígitos no cuenta como teléfono: en una HU aparecen montos
    y cantidades; exigir el prefijo +506 o el guion evita rechazar textos legítimos.
    """
    hallazgos: list[tuple[str, str]] = []
    restante = texto

    for m in _CORREO.finditer(restante):
        hallazgos.append(("correo electrónico", _enmascarar(m.group())))
    restante = _CORREO.sub(" ", restante)

    for m in _IBAN_CR.finditer(restante):
        hallazgos.append(("número de cuenta (IBAN)", _enmascarar(m.group())))
    restante = _IBAN_CR.sub(" ", restante)

    # Orden importante: el teléfono con +506 antes de las secuencias largas (si no, sería una
    # "cuenta" de 11 dígitos), y las secuencias largas antes del formato dddd-dddd (si no,
    # "4111 1111 1111 1111" se leería como teléfono y la tarjeta quedaría mal clasificada).
    for m in _TELEFONO_CON_PREFIJO.finditer(restante):
        hallazgos.append(("número de teléfono", _enmascarar(m.group())))
    restante = _TELEFONO_CON_PREFIJO.sub(" ", restante)

    def _clasificar(m: re.Match) -> str:
        digitos = re.sub(r"\D", "", m.group())
        if 13 <= len(digitos) <= 19 and _luhn(digitos):
            tipo = "número de tarjeta"
        elif len(digitos) >= 10:
            tipo = "número de cuenta"
        elif len(digitos) == 9:
            tipo = "número de cédula"
        else:
            return m.group()
        hallazgos.append((tipo, _enmascarar(m.group())))
        return " "

    restante = _SECUENCIA_DIGITOS.sub(_clasificar, restante)

    for m in _TELEFONO.finditer(restante):
        hallazgos.append(("número de teléfono", _enmascarar(m.group())))
    return hallazgos


def errores_datos_personales(campo: str, texto: str) -> list[str]:
    return [
        f"{campo}: contiene un posible {tipo} ('{frag}'). Elimínalo o reemplázalo por un "
        f"marcador como [CORREO], [CEDULA], [TELEFONO], [CUENTA] o [MONTO]."
        for tipo, frag in buscar_datos_personales(texto)
    ]


# ===================================================================== revisión
def validar_revision(
    *,
    decision: str,
    tipo: str,
    defectos: Sequence[str],
    recomendaciones: Sequence[Recomendacion],
    historia_refinada: str,
    criterios_aceptacion: Sequence[str],
    sistema: str,
    tipos_validos: Sequence[str],
    defectos_validos: set[str],
) -> list[str]:
    """Reglas de `registrar_revision`. Devuelve la lista completa de errores (vacía si es válida)."""
    errores: list[str] = []

    if decision not in dominio.DECISIONES:
        errores.append(f"decision: '{decision}' no es válida; usa una de {', '.join(dominio.DECISIONES)}.")

    if tipo not in tipos_validos:
        errores.append(f"tipo: '{tipo}' no es válido; usa uno de: {', '.join(tipos_validos)}.")

    # ---- defectos: ids activos del catálogo que aplican al sistema de la HU
    if len(defectos) > dominio.MAX_DEFECTOS:
        errores.append(f"defectos: hay {len(defectos)}; el máximo es {dominio.MAX_DEFECTOS}.")
    repetidos = sorted({d for d in defectos if list(defectos).count(d) > 1})
    if repetidos:
        errores.append(f"defectos: ids repetidos: {', '.join(repetidos)}. Inclúyelos una sola vez.")
    invalidos = [d for d in dict.fromkeys(defectos) if d not in defectos_validos]
    if invalidos:
        errores.append(
            f"defectos: {', '.join(repr(d) for d in invalidos)} no son criterios activos que apliquen "
            f"al sistema '{sistema}'. Consulta listar_criterios(sistema='{sistema}') y usa solo esos ids."
        )

    # ---- recomendaciones: cada una apunta a un defecto de la lista
    if len(recomendaciones) > dominio.MAX_RECOMENDACIONES:
        errores.append(
            f"recomendaciones: hay {len(recomendaciones)}; el máximo es {dominio.MAX_RECOMENDACIONES}."
        )
    for i, r in enumerate(recomendaciones):
        if r.defecto not in defectos:
            errores.append(
                f"recomendaciones[{i}]: el defecto '{r.defecto}' no está en la lista 'defectos'. "
                f"Cada recomendación debe referenciar uno de los defectos reportados."
            )
        if not r.texto.strip():
            errores.append(f"recomendaciones[{i}]: el texto está vacío; di qué debe corregir el analista.")
        elif len(r.texto) > dominio.MAX_RECOMENDACION:
            errores.append(
                f"recomendaciones[{i}]: tiene {len(r.texto)} caracteres; el máximo es {dominio.MAX_RECOMENDACION}."
            )
        errores += errores_datos_personales(f"recomendaciones[{i}]", r.texto)

    # ---- historia refinada
    if historia_refinada.strip():
        if len(historia_refinada) > dominio.MAX_HISTORIA:
            errores.append(
                f"historia_refinada: tiene {len(historia_refinada)} caracteres; el máximo es {dominio.MAX_HISTORIA}."
            )
        if not es_formato_hu(historia_refinada):
            errores.append(
                "historia_refinada: debe seguir el formato 'Como <rol>, quiero <acción>, para <beneficio>'."
            )
        errores += errores_datos_personales("historia_refinada", historia_refinada)

    # ---- criterios de aceptación: siempre en Gherkin
    if len(criterios_aceptacion) > dominio.MAX_CRITERIOS_ACEPTACION:
        errores.append(
            f"criterios_aceptacion: hay {len(criterios_aceptacion)}; el máximo es {dominio.MAX_CRITERIOS_ACEPTACION}."
        )
    for i, c in enumerate(criterios_aceptacion):
        if len(c) > dominio.MAX_CRITERIO_ACEPTACION:
            errores.append(
                f"criterios_aceptacion[{i}]: tiene {len(c)} caracteres; el máximo es {dominio.MAX_CRITERIO_ACEPTACION}."
            )
        if not es_gherkin(c):
            errores.append(
                f"criterios_aceptacion[{i}]: no está en Gherkin; debe contener, en este orden, "
                f"'Dado …', 'Cuando …' y 'Entonces …'."
            )
        errores += errores_datos_personales(f"criterios_aceptacion[{i}]", c)

    # ---- coherencia con la decisión
    if decision == "aceptar":
        if defectos:
            errores.append("decision 'aceptar' con defectos: si la HU tiene defectos, la decisión es 'devolver' o 'dividir'.")
        if not criterios_aceptacion:
            errores.append("decision 'aceptar' sin criterios_aceptacion: incluye al menos un criterio en Gherkin.")
        if not historia_refinada.strip():
            errores.append("decision 'aceptar' sin historia_refinada: incluye la HU en formato 'Como…, quiero…, para…'.")
    elif decision == "devolver":
        if not defectos:
            errores.append("decision 'devolver' sin defectos: indica qué criterios incumple la HU.")
        if not recomendaciones:
            errores.append("decision 'devolver' sin recomendaciones: incluye al menos una, ligada a un defecto.")

    return errores


# ===================================================================== división
def validar_division(partes: Sequence[str]) -> list[str]:
    """Reglas de `proponer_division`: 2 a 5 partes bien formadas, con el mismo rol y sin repetir."""
    errores: list[str] = []
    if not dominio.MIN_PARTES <= len(partes) <= dominio.MAX_PARTES:
        errores.append(
            f"partes: hay {len(partes)}; una división tiene entre {dominio.MIN_PARTES} y {dominio.MAX_PARTES} partes."
        )
    roles = {}
    for i, p in enumerate(partes):
        if len(p) > dominio.MAX_HISTORIA:
            errores.append(f"partes[{i}]: tiene {len(p)} caracteres; el máximo es {dominio.MAX_HISTORIA}.")
        rol = rol_de(p)
        if rol is None:
            errores.append(f"partes[{i}]: debe seguir el formato 'Como <rol>, quiero <acción>, para <beneficio>'.")
        else:
            roles[i] = rol
        errores += errores_datos_personales(f"partes[{i}]", p)
    if len(set(roles.values())) > 1:
        detalle = "; ".join(f"partes[{i}]='{r}'" for i, r in roles.items())
        errores.append(
            f"partes: todas deben tener el mismo rol, el de la persona usuaria de la HU original ({detalle})."
        )
    normalizadas = [re.sub(r"\s+", " ", _sin_tildes(p).lower().strip()) for p in partes]
    if len(set(normalizadas)) < len(normalizadas):
        errores.append("partes: hay partes repetidas; cada parte debe cubrir un objetivo distinto.")
    return errores
