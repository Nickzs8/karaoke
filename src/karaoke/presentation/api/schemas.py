"""Schemas Pydantic V2 para validação e serialização de dados da API."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SongPrepareRequest(BaseModel):
    """Payload para solicitação de preparação de música via YouTube ou busca."""

    model_config = ConfigDict(extra="forbid")

    query_or_url: str | None = Field(
        default=None,
        description="Termo de busca ou URL direta do vídeo/áudio no YouTube.",
        examples=[
            "Queen Bohemian Rhapsody",
            "https://www.youtube.com/watch?v=fJ9rUzIMcZQ",
        ],
    )
    title: str | None = Field(
        default=None,
        description="Título opcional da música caso queira sobrescrever os metadados.",
        examples=["Bohemian Rhapsody"],
    )
    artist: str | None = Field(
        default=None,
        description="Nome opcional do artista.",
        examples=["Queen"],
    )


class SongResponse(BaseModel):
    """Resposta com dados de uma música processada ou em processamento."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="Identificador único da música.")
    title: str = Field(description="Título da música.")
    artist: str = Field(description="Artista ou banda.")
    duration: float = Field(description="Duração da faixa em segundos.")
    status: str = Field(
        description="Status atual (PENDING, PROCESSING, READY, FAILED)."
    )
    instrumental_url: str | None = Field(
        default=None,
        description="URL para streaming da faixa instrumental (sem vocal).",
    )
    vocals_url: str | None = Field(
        default=None,
        description="URL para streaming da faixa vocal isolada.",
    )


class SongCatalogItemResponse(BaseModel):
    """Item resumido do catálogo de músicas prontas para o karaokê."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="Identificador único da música.")
    title: str = Field(description="Título da música.")
    artist: str = Field(description="Artista ou banda.")
    duration: float = Field(description="Duração total em segundos.")
    status: str = Field(description="Status de prontidão da música.")
    instrumental_url: str | None = Field(
        default=None,
        description="URL de streaming da faixa instrumental.",
    )
    vocals_url: str | None = Field(
        default=None,
        description="URL de streaming da faixa vocal de referência.",
    )


class LyricWordResponse(BaseModel):
    """Palavra individual com tempos de início e fim sincronizados."""

    model_config = ConfigDict(from_attributes=True)

    text: str = Field(description="Texto da palavra.")
    start_time: float = Field(description="Tempo de início da palavra em segundos.")
    end_time: float = Field(description="Tempo de término da palavra em segundos.")


class LyricLineResponse(BaseModel):
    """Verso sincronizado no tempo da letra da música."""

    model_config = ConfigDict(from_attributes=True)

    start_time: float = Field(
        description="Tempo de início da linha em segundos.",
        examples=[12.35],
    )
    end_time: float = Field(
        description="Tempo de término da linha em segundos.",
        examples=[15.80],
    )
    text: str = Field(
        description="Texto da letra cantada.",
        examples=["Is this the real life? Is this just fantasy?"],
    )
    words: list[LyricWordResponse] = Field(
        default_factory=list,
        description="Lista de palavras individuais sincronizadas do verso.",
    )


class LyricsResponse(BaseModel):
    """Letra completa sincronizada e formatada em JSON."""

    model_config = ConfigDict(from_attributes=True)

    song_id: str = Field(description="Identificador da música correspondente.")
    lines: list[LyricLineResponse] = Field(
        default_factory=list,
        description="Lista ordenada de versos sincronizados.",
    )
    estimated_offset: float = Field(
        default=0.0,
        description="Offset em segundos para compensar silêncio inicial do áudio.",
    )


class PerformanceEvaluationResponse(BaseModel):
    """Resultado detalhado da avaliação da performance vocal do usuário."""

    model_config = ConfigDict(from_attributes=True)

    total_score: float = Field(
        ge=0.0,
        le=100.0,
        description="Nota final consolidada (0 a 100) ponderando afinação e ritmo.",
        examples=[87.5],
    )
    pitch_score: float = Field(
        ge=0.0,
        le=100.0,
        description="Nota de afinação melódica de 0 a 100.",
        examples=[90.0],
    )
    timing_score: float = Field(
        ge=0.0,
        le=100.0,
        description="Nota de precisão rítmica de 0 a 100.",
        examples=[81.7],
    )
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Métricas adicionais do alinhamento DTW e análise harmônica.",
    )


class PerformanceEvaluateJsonRequest(BaseModel):
    """Payload JSON alternativo para avaliação direta via caminho de arquivo."""

    model_config = ConfigDict(extra="forbid")

    song_id: str = Field(description="Identificador da música de referência.")
    recording_path: str = Field(
        description="Caminho do arquivo de áudio gravado no disco."
    )


class ErrorResponse(BaseModel):
    """Modelo padrão de resposta de erro da API."""

    detail: str = Field(description="Descrição detalhada do erro ocorrido.")
