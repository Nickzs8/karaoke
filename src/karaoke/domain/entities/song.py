"""Entidade: Song e Enum SongStatus."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from karaoke.domain.exceptions import SongNotReadyError


class SongStatus(StrEnum):
    """Ciclo de vida do processamento de uma música."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"


@dataclass
class Song:
    """Representa uma música no catálogo do Karaokê."""

    id: str
    title: str
    artist: str
    duration: float = 0.0
    status: SongStatus = SongStatus.PENDING
    raw_audio_path: Path | None = None
    instrumental_path: Path | None = None
    vocals_path: Path | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def mark_as_processing(self) -> None:
        """Marca o início do processamento de download/separação de faixas."""
        self.status = SongStatus.PROCESSING

    def mark_as_ready(
        self,
        instrumental_path: Path,
        vocals_path: Path,
        duration: float | None = None,
    ) -> None:
        """Define a música como pronta após o isolamento de voz e instrumental."""
        self.instrumental_path = instrumental_path
        self.vocals_path = vocals_path
        if duration is not None:
            self.duration = duration
        self.status = SongStatus.READY

    def mark_as_failed(self) -> None:
        """Marca o processamento da música como falho."""
        self.status = SongStatus.FAILED

    def ensure_is_ready(self) -> None:
        """Verifica se a música está pronta para playback e canto."""
        if self.status != SongStatus.READY:
            msg = (
                f"A música '{self.title}' não está pronta para playback "
                f"(Status: {self.status.value})."
            )
            raise SongNotReadyError(msg)
