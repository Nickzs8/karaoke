"""Entidade: Performance."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class Performance:
    """Representa a sessão de canto do usuário para uma música específica."""

    id: str
    song_id: str
    recording_path: Path
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
