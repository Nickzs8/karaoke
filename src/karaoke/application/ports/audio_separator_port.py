"""Porta de Aplicação: AudioSeparatorPort."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class SeparatedTracks:
    """Caminhos das faixas isoladas resultantes da separação."""

    instrumental_path: Path
    vocals_path: Path


class AudioSeparatorPort(Protocol):
    """Contrato para separação de áudio em faixas instrumental e vocal."""

    def separate(self, audio_path: Path, output_dir: Path) -> SeparatedTracks:
        """Isola as faixas vocal e instrumental a partir de um arquivo de áudio."""
        ...
