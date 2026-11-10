"""Acceso al backlog mediante un puerto con adaptadores intercambiables."""

from revisor.backlog.puerto import (
    ErrorBacklog,
    Historia,
    HistoriaNoEncontrada,
    HistoriaSimilar,
    OperacionProhibida,
    PuertoBacklog,
    Recomendacion,
    Revision,
)

__all__ = [
    "ErrorBacklog",
    "Historia",
    "HistoriaSimilar",
    "HistoriaNoEncontrada",
    "OperacionProhibida",
    "PuertoBacklog",
    "Recomendacion",
    "Revision",
]
