"""Porta de Aplicação: VocalOnsetDetectorPort."""

from pathlib import Path
from typing import Protocol


class VocalOnsetDetectorPort(Protocol):
    """Contrato para detecção temporal do início de voz em uma faixa."""

    def detect_onset(self, audio_path: Path) -> float | None:
        """Calcula o instante em segundos do primeiro início vocal audível na faixa."""
        ...
