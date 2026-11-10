"""Acceso al backlog mediante un puerto con adaptadores intercambiables."""

from revisor.backlog.puerto import (
    ErrorBacklog,
    Historia,
    HistoriaNoEncontrada,
    OperacionProhibida,
    PuertoBacklog,
    Recomendacion,
    Revision,
)

__all__ = [
    "ErrorBacklog",
    "Historia",
    "HistoriaNoEncontrada",
    "OperacionProhibida",
    "PuertoBacklog",
    "Recomendacion",
    "Revision",
]
