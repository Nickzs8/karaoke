"""Injeção de dependências para as rotas FastAPI."""

from fastapi import Request

from karaoke.infrastructure import AppContainer, get_container


def get_app_container(request: Request) -> AppContainer:
    """Recupera o AppContainer da aplicação FastAPI ou o singleton padrão."""
    if hasattr(request.app.state, "container") and request.app.state.container:
        return request.app.state.container
    return get_container()
