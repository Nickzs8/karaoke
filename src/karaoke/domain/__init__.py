"""Módulo central da camada de Domínio."""

from karaoke.domain.entities import Performance, Song, SongStatus
from karaoke.domain.exceptions import (
    AudioDownloadError,
    AudioSeparationError,
    DomainError,
    InvalidAudioFormatError,
    InvalidLyricsTimeError,
    InvalidPitchPointError,
    InvalidScoreError,
    InvalidScorerConfigError,
    InvalidStoragePathError,
    PitchExtractionError,
    SongNotFoundError,
    SongNotReadyError,
)
from karaoke.domain.value_objects import (
    LyricsLine,
    PitchCurve,
    PitchPoint,
    Score,
    ScoreResult,
)

__all__ = [
    "AudioDownloadError",
    "AudioSeparationError",
    "DomainError",
    "InvalidAudioFormatError",
    "InvalidLyricsTimeError",
    "InvalidPitchPointError",
    "InvalidScoreError",
    "InvalidScorerConfigError",
    "InvalidStoragePathError",
    "LyricsLine",
    "Performance",
    "PitchCurve",
    "PitchExtractionError",
    "PitchPoint",
    "Score",
    "ScoreResult",
    "Song",
    "SongNotFoundError",
    "SongNotReadyError",
    "SongStatus",
]
