"""Porta de Aplicação: PitchExtractorPort."""

from pathlib import Path
from typing import Protocol

from karaoke.domain import PitchCurve


class PitchExtractorPort(Protocol):
    """Contrato para extração da frequência fundamental (F0) de áudio."""

    def extract_pitch(self, audio_path: Path) -> PitchCurve:
        """Extrai a curva melódica de frequências fundamentais de um áudio vocal."""
        ...
