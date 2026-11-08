"""Módulo de Portas (Interfaces / Protocolos) da camada de Aplicação."""

from karaoke.application.ports.audio_downloader_port import (
    AudioDownloaderPort,
    DownloadedAudio,
)
from karaoke.application.ports.audio_separator_port import (
    AudioSeparatorPort,
    SeparatedTracks,
)
from karaoke.application.ports.audio_storage_port import AudioStoragePort
from karaoke.application.ports.lyrics_provider_port import LyricsProviderPort
from karaoke.application.ports.performance_scorer_port import PerformanceScorerPort
from karaoke.application.ports.pitch_extractor_port import PitchExtractorPort

__all__ = [
    "AudioDownloaderPort",
    "AudioSeparatorPort",
    "AudioStoragePort",
    "DownloadedAudio",
    "LyricsProviderPort",
    "PerformanceScorerPort",
    "PitchExtractorPort",
    "SeparatedTracks",
]
