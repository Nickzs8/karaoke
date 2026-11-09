"""Rotas da API para gerenciamento e preparo de músicas: /api/songs."""

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from karaoke.domain import InvalidAudioFormatError, Song
from karaoke.infrastructure import AppContainer
from karaoke.presentation.api.dependencies import get_app_container
from karaoke.presentation.api.schemas import (
    LyricLineResponse,
    LyricsResponse,
    PerformanceEvaluationResponse,
    SongCatalogItemResponse,
    SongPrepareRequest,
    SongResponse,
)

router = APIRouter(prefix="/api/songs", tags=["Músicas"])
ContainerDep = Annotated[AppContainer, Depends(get_app_container)]


@router.post(
    "/prepare",
    response_model=SongResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Prepara uma música para o karaokê via YouTube ou upload de áudio",
)
async def prepare_song(
    request: Request,
    container: ContainerDep,
) -> SongResponse:
    """Dispara a extração, separação de faixas e sincronização da letra."""
    query_or_url, local_path, title, artist = await _resolve_prepare_inputs(
        request, container
    )

    song = await run_in_threadpool(
        container.prepare_song.execute,
        query_or_url=query_or_url,
        local_file_path=local_path,
        title=title,
        artist=artist,
    )

    return _build_song_response(song, container.config.base_audio_url)


@router.get(
    "",
    response_model=list[SongCatalogItemResponse],
    summary="Lista músicas salvas no catálogo com URLs de streaming",
)
async def list_songs(
    container: ContainerDep,
    only_ready: bool = Query(
        default=True,
        description="Quando True, lista apenas músicas com processamento concluído.",
    ),
) -> list[SongCatalogItemResponse]:
    """Recupera todas as músicas do catálogo no armazenamento local."""
    items = await run_in_threadpool(
        container.list_songs.execute,
        only_ready=only_ready,
    )

    return [
        SongCatalogItemResponse(
            id=item.id,
            title=item.title,
            artist=item.artist,
            duration=item.duration,
            status=item.status,
            instrumental_url=item.instrumental_url,
            vocals_url=item.vocals_url,
        )
        for item in items
    ]


@router.get(
    "/{id}/lyrics",
    response_model=LyricsResponse,
    summary="Retorna a letra sincronizada da música formatada em JSON",
)
async def get_lyrics(
    id: str,
    container: ContainerDep,
) -> LyricsResponse:
    """Busca a letra em arquivo .lrc e retorna a sequência temporal dos versos."""
    lines = await run_in_threadpool(
        container.get_lyrics.execute,
        song_id=id,
    )

    estimated_offset = 0.0
    if lines and hasattr(container.get_lyrics, "estimate_offset"):
        first_time = lines[0].start_time
        try:
            estimated_offset = await run_in_threadpool(
                container.get_lyrics.estimate_offset,
                song_id=id,
                first_lyric_start=first_time,
            )
        except Exception:
            estimated_offset = 0.0

    return LyricsResponse(
        song_id=id,
        lines=[
            LyricLineResponse(
                start_time=line.start_time,
                end_time=line.end_time,
                text=line.text,
            )
            for line in lines
        ],
        estimated_offset=estimated_offset,
    )


@router.post(
    "/{id}/evaluate",
    response_model=PerformanceEvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Avalia o áudio cantado em relação à música identificada por ID",
)
async def evaluate_song(
    id: str,
    request: Request,
    container: ContainerDep,
) -> PerformanceEvaluationResponse:
    """Compara as curvas melódicas e rítmicas com a música {id} e calcula a nota."""
    recording_path = await _resolve_evaluate_recording(request, container, id)

    score_result = await run_in_threadpool(
        container.evaluate_performance.execute,
        song_id=id,
        recording_path=recording_path,
    )

    return PerformanceEvaluationResponse(
        total_score=score_result.total_score.value,
        pitch_score=score_result.pitch_score.value,
        timing_score=score_result.timing_score.value,
        details=score_result.details,
    )


# Funções Auxiliares Especializadas (SRP)


async def _resolve_evaluate_recording(
    request: Request,
    container: AppContainer,
    song_id: str,
) -> Path:
    """Extrai e salva o áudio de gravação enviado via formulário ou path em JSON."""
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        body = await request.json()
        path_str = body.get("recording_path")
        if not path_str:
            raise InvalidAudioFormatError(
                "O campo 'recording_path' é obrigatório no JSON."
            )
        return Path(path_str)

    if "multipart/form-data" in content_type or "form" in content_type:
        form = await request.form()
        file_val = form.get("audio_file") or form.get("file")
        if (
            not file_val
            or not isinstance(file_val, UploadFile)
            or not file_val.filename
        ):
            raise InvalidAudioFormatError(
                "O arquivo de áudio gravado ('audio_file') é obrigatório."
            )
        content = await file_val.read()
        if not content:
            raise InvalidAudioFormatError(
                "O arquivo de áudio gravado enviado está vazio."
            )

        clean_name = Path(file_val.filename).name
        unique_name = f"rec_{song_id}_{uuid.uuid4().hex[:8]}_{clean_name}"
        container.storage.save_file(
            file_data=content,
            filename=unique_name,
            subfolder="recordings",
        )
        return container.storage.get_path(unique_name, "recordings")

    raise InvalidAudioFormatError(
        "Formato de requisição inválido. Envie áudio via formulário ou JSON."
    )


async def _resolve_prepare_inputs(
    request: Request,
    container: AppContainer,
) -> tuple[str | None, Path | None, str | None, str | None]:
    """Identifica o Content-Type da requisição e extrai os parâmetros necessários."""
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        return await _handle_json_prepare(request)

    if "multipart/form-data" in content_type or "form" in content_type:
        return await _handle_form_prepare(request, container)

    raise InvalidAudioFormatError(
        "Formato de requisição inválido. Envie JSON ou multipart/form-data."
    )


async def _handle_json_prepare(
    request: Request,
) -> tuple[str | None, Path | None, str | None, str | None]:
    """Processa o payload JSON da requisição."""
    body = await request.json()
    payload = SongPrepareRequest.model_validate(body)
    if not payload.query_or_url or not payload.query_or_url.strip():
        raise InvalidAudioFormatError("O campo 'query_or_url' não pode ser vazio.")
    return payload.query_or_url.strip(), None, payload.title, payload.artist


async def _handle_form_prepare(
    request: Request,
    container: AppContainer,
) -> tuple[str | None, Path | None, str | None, str | None]:
    """Processa o envio de formulário com upload de arquivo ou URL."""
    form = await request.form()
    query_or_url_val = form.get("query_or_url")
    title_val = form.get("title")
    artist_val = form.get("artist")
    file_val = form.get("file")

    local_file_path: Path | None = None
    if file_val and isinstance(file_val, UploadFile) and file_val.filename:
        local_file_path = await _save_uploaded_audio(file_val, container)

    query_or_url = (
        str(query_or_url_val).strip()
        if (query_or_url_val and str(query_or_url_val).strip())
        else None
    )
    title = str(title_val).strip() if (title_val and str(title_val).strip()) else None
    artist = (
        str(artist_val).strip() if (artist_val and str(artist_val).strip()) else None
    )

    if not query_or_url and not local_file_path:
        raise InvalidAudioFormatError(
            "É obrigatório fornecer busca/URL ou arquivo de áudio."
        )

    return query_or_url, local_file_path, title, artist


async def _save_uploaded_audio(file: UploadFile, container: AppContainer) -> Path:
    """Salva os bytes do arquivo enviado na pasta temporária raw do storage."""
    content = await file.read()
    if not content:
        raise InvalidAudioFormatError("O arquivo de áudio enviado está vazio.")

    clean_filename = Path(file.filename or "upload.wav").name
    safe_name = f"upload_{uuid.uuid4().hex[:8]}_{clean_filename}"
    container.storage.save_file(
        file_data=content,
        filename=safe_name,
        subfolder="raw",
    )
    return container.storage.get_path(safe_name, "raw")


def _build_song_response(song: Song, base_audio_url: str) -> SongResponse:
    """Constrói o schema de resposta Pydantic a partir da entidade Song."""
    return SongResponse(
        id=song.id,
        title=song.title,
        artist=song.artist,
        duration=song.duration,
        status=song.status.value,
        instrumental_url=_format_audio_stream_url(
            base_audio_url, song.instrumental_path
        ),
        vocals_url=_format_audio_stream_url(base_audio_url, song.vocals_path),
    )


def _format_audio_stream_url(
    base_audio_url: str,
    file_path: Path | None,
) -> str | None:
    """Gera a URL pública para streaming do arquivo de áudio."""
    if file_path is None:
        return None
    clean_base = base_audio_url.rstrip("/")
    subfolder = file_path.parent.name
    filename = file_path.name
    return f"{clean_base}/{subfolder}/{filename}"
