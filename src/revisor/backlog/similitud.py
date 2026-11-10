"""
Similitud de textos por TF-IDF y coseno, en Python puro.

Por qué no embeddings:
    Las pruebas no pueden usar la red y el experimento tiene que ser reproducible y
    determinista. TF-IDF basta para encontrar duplicados y conflictos léxicos en un backlog
    pequeño, y el mismo texto siempre da el mismo resultado. Si en el banco hace falta algo
    mejor, se cambia este módulo sin tocar el puerto ni los servidores.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter

# Palabras vacías mínimas en español e inglés (las HU de Dalpiaz están en inglés).
PALABRAS_VACIAS = frozenset(
    """
    como quiero para que los las del una uno unos unas con por sin sobre entre cuando donde
    este esta estos estas ese esa eso puede pueda poder debe deben ser sea son hay muy mas
    pero sus mis tus nuestro nuestra the and for that with from this have has will can
    able want wants would should into when where which their them they you your are was
    """.split()
)


def _normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c))
    return sin_tildes.lower()


def tokens(texto: str) -> list[str]:
    """Palabras de 3 o más letras, sin tildes y sin palabras vacías."""
    return [t for t in re.findall(r"[a-z0-9]{3,}", _normalizar(texto)) if t not in PALABRAS_VACIAS]


class IndiceSimilitud:
    """Índice TF-IDF sobre un conjunto fijo de documentos identificados por id."""

    def __init__(self, documentos: dict[str, str]):
        self._tf = {doc_id: Counter(tokens(texto)) for doc_id, texto in documentos.items()}
        n = len(self._tf) or 1
        df: Counter[str] = Counter()
        for tf in self._tf.values():
            df.update(tf.keys())
        # idf suavizado: un término que aparece en todos los documentos pesa poco pero no cero.
        self._idf = {t: math.log((1 + n) / (1 + d)) + 1 for t, d in df.items()}
        self._vectores = {doc_id: self._vector(tf) for doc_id, tf in self._tf.items()}

    def _vector(self, tf: Counter[str]) -> dict[str, float]:
        v = {t: f * self._idf.get(t, math.log(1 + len(self._tf)) + 1) for t, f in tf.items()}
        norma = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {t: x / norma for t, x in v.items()}

    def buscar(self, texto: str, limite: int) -> list[tuple[str, float]]:
        """Devuelve hasta `limite` pares (id, similitud) con similitud > 0, de mayor a menor."""
        consulta = self._vector(Counter(tokens(texto)))
        puntajes = []
        for doc_id, v in self._vectores.items():
            s = sum(peso * v.get(t, 0.0) for t, peso in consulta.items())
            if s > 0:
                puntajes.append((doc_id, round(s, 3)))
        # Desempate por id para que el orden sea determinista.
        puntajes.sort(key=lambda par: (-par[1], par[0]))
        return puntajes[:limite]
