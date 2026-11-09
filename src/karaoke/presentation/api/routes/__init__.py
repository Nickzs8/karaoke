"""Módulo de rotas da API FastAPI."""

from karaoke.presentation.api.routes.performances import (
    router as performances_router,
)
from karaoke.presentation.api.routes.songs import router as songs_router

__all__ = ["performances_router", "songs_router"]
