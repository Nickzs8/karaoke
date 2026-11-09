"""Aplicação principal FastAPI: Fábrica create_app e configuração global."""

from pathlib import Path

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from karaoke.domain import (
    DomainError,
    InvalidAudioFormatError,
    InvalidLyricsTimeError,
    InvalidPitchPointError,
    InvalidScoreError,
    InvalidScorerConfigError,
    InvalidStoragePathError,
    LyricsNotFoundError,
    SongNotFoundError,
    SongNotReadyError,
)
from karaoke.infrastructure import AppContainer, get_container
from karaoke.presentation.api.routes import performances_router, songs_router


def create_app(container: AppContainer | None = None) -> FastAPI:
    """Fábrica de aplicação FastAPI com DI e tratamento de exceções de domínio."""
    app_container = container or get_container()

    app = FastAPI(
        title="Karaokê API",
        description="API RESTful para sistema inteligente de karaokê.",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Estado global com o container injetado
    app.state.container = app_container

    # Middleware de CORS para permitir acesso do frontend
    _setup_cors_middleware(app)

    # Handlers para mapear Exceções de Domínio em respostas HTTP adequadas
    _setup_exception_handlers(app)

    # Montagem dos arquivos estáticos para streaming de áudio
    _setup_static_audio(app, app_container)

    # Configuração do Frontend Web (templates e estáticos)
    _setup_frontend(app)

    # Registro de rotas da API
    app.include_router(songs_router)
    app.include_router(performances_router)

    # Endpoint de integridade (Health Check)
    @app.get("/api/health", tags=["Health"], summary="Verifica integridade do serviço")
    async def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return app


def _setup_cors_middleware(app: FastAPI) -> None:
    """Configura cabeçalhos de Cross-Origin Resource Sharing."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _setup_static_audio(app: FastAPI, container: AppContainer) -> None:
    """Monta o diretório de armazenamento para streaming estático de áudio."""
    storage_path = container.config.storage_dir
    storage_path.mkdir(parents=True, exist_ok=True)

    mount_path = f"/{container.config.base_audio_url.strip('/')}"
    app.mount(
        mount_path,
        StaticFiles(directory=str(storage_path)),
        name="static_audio",
    )


def _setup_frontend(app: FastAPI) -> None:
    """Configura o frontend web servindo templates HTML e arquivos estáticos."""
    web_dir = Path(__file__).resolve().parent.parent / "web"
    static_dir = web_dir / "static"
    templates_dir = web_dir / "templates"

    if static_dir.exists():
        app.mount(
            "/static/web",
            StaticFiles(directory=str(static_dir)),
            name="web_static",
        )

    if templates_dir.exists():
        templates = Jinja2Templates(directory=str(templates_dir))

        @app.get("/", include_in_schema=False)
        async def serve_index(request: Request) -> Response:
            return templates.TemplateResponse(request=request, name="index.html")


def _setup_exception_handlers(app: FastAPI) -> None:
    """Mapeia exceções de domínio para respostas HTTP padronizadas."""

    @app.exception_handler(SongNotFoundError)
    @app.exception_handler(LyricsNotFoundError)
    async def not_found_handler(request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc)},
        )

    @app.exception_handler(SongNotReadyError)
    async def conflict_handler(
        request: Request, exc: SongNotReadyError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc)},
        )

    @app.exception_handler(InvalidAudioFormatError)
    @app.exception_handler(InvalidStoragePathError)
    @app.exception_handler(InvalidScoreError)
    @app.exception_handler(InvalidLyricsTimeError)
    @app.exception_handler(InvalidPitchPointError)
    @app.exception_handler(InvalidScorerConfigError)
    @app.exception_handler(DomainError)
    async def domain_bad_request_handler(
        request: Request, exc: DomainError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)},
        )


# Instância padrão para inicialização via servidores ASGI (uvicorn)
app = create_app()
