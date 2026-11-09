"""Rotas da API para avaliação de performance vocal: /api/performances."""

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from karaoke.domain import InvalidAudioFormatError, ScoreResult
from karaoke.infrastructure import AppContainer
from karaoke.presentation.api.dependencies import get_app_container
from karaoke.presentation.api.schemas import (
    PerformanceEvaluateJsonRequest,
    PerformanceEvaluationResponse,
)

router = APIRouter(prefix="/api/performances", tags=["Performances"])
ContainerDep = Annotated[AppContainer, Depends(get_app_container)]


@router.post(
    "/evaluate",
    response_model=PerformanceEvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Avalia o áudio cantado em relação à música de referência",
)
async def evaluate_performance(
    request: Request,
    container: ContainerDep,
) -> PerformanceEvaluationResponse:
    """Compara as curvas melódicas e rítmicas e calcula a nota consolidada (0-100)."""
    song_id, recording_path = await _resolve_evaluate_inputs(request, container)

    score_result = await run_in_threadpool(
        container.evaluate_performance.execute,
        song_id=song_id,
        recording_path=recording_path,
    )

    return _build_evaluation_response(score_result)


# Funções Auxiliares Especializadas (SRP)


async def _resolve_evaluate_inputs(
    request: Request,
    container: AppContainer,
) -> tuple[str, Path]:
    """Extrai o ID da música e o caminho da gravação a partir de JSON ou formulário."""
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        return await _handle_json_evaluate(request)

    if "multipart/form-data" in content_type or "form" in content_type:
        return await _handle_form_evaluate(request, container)

    raise InvalidAudioFormatError(
        "Formato de requisição inválido. Envie áudio via formulário ou JSON."
    )


async def _handle_json_evaluate(request: Request) -> tuple[str, Path]:
    """Processa o payload JSON de avaliação."""
    body = await request.json()
    payload = PerformanceEvaluateJsonRequest.model_validate(body)
    return payload.song_id, Path(payload.recording_path)


async def _handle_form_evaluate(
    request: Request,
    container: AppContainer,
) -> tuple[str, Path]:
    """Processa o upload do áudio gravado e o ID da música via formulário."""
    form = await request.form()
    song_id_val = form.get("song_id")
    if not song_id_val or not str(song_id_val).strip():
        raise InvalidAudioFormatError("O campo 'song_id' é obrigatório.")

    song_id = str(song_id_val).strip()

    file_val = form.get("audio_file") or form.get("file")
    if not file_val or not isinstance(file_val, UploadFile) or not file_val.filename:
        raise InvalidAudioFormatError(
            "O arquivo de áudio gravado ('audio_file') é obrigatório."
        )

    content = await file_val.read()
    if not content:
        raise InvalidAudioFormatError("O arquivo de áudio gravado enviado está vazio.")

    clean_name = Path(file_val.filename).name
    unique_name = f"rec_{song_id}_{uuid.uuid4().hex[:8]}_{clean_name}"
    container.storage.save_file(
        file_data=content,
        filename=unique_name,
        subfolder="recordings",
    )
    recording_path = container.storage.get_path(unique_name, "recordings")

    return song_id, recording_path


def _build_evaluation_response(
    score_result: ScoreResult,
) -> PerformanceEvaluationResponse:
    """Serializa o ScoreResult para o schema de resposta Pydantic V2."""
    return PerformanceEvaluationResponse(
        total_score=score_result.total_score.value,
        pitch_score=score_result.pitch_score.value,
        timing_score=score_result.timing_score.value,
        details=score_result.details,
    )
