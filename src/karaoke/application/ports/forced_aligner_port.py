"""Porta de Aplicação: ForcedAlignerPort."""

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from karaoke.domain import LyricsLine


class ForcedAlignerPort(Protocol):
    """Contrato para alinhamento forçado entre voz e versos da letra."""

    def align_lyrics(
        self,
        audio_path: Path,
        lines: Sequence[LyricsLine],
    ) -> tuple[LyricsLine, ...]:
        """Calcula e anexa timestamps individuais de palavras aos versos."""
        ...
