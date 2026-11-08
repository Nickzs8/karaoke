"""Porta de Aplicação: AudioDownloaderPort."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class DownloadedAudio:
    """Metadados do áudio baixado."""

    file_path: Path
    title: str
    artist: str
    duration: float


class AudioDownloaderPort(Protocol):
    """Contrato para download de áudio a partir de termos de busca ou URLs."""

    def download(self, query_or_url: str, output_dir: Path) -> DownloadedAudio:
        """Busca, baixa e converte o áudio, retornando metadados e caminho local."""
        ...
