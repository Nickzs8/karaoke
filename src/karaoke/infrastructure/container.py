"""Container de Injeção de Dependências e Composition Root: AppContainer."""

from karaoke.adapters.audio import (
    DtwPerformanceScorerAdapter,
    EnergyVocalOnsetDetectorAdapter,
    LibrosaPitchExtractorAdapter,
)
from karaoke.adapters.downloaders import YtDlpDownloaderAdapter
from karaoke.adapters.lyrics import LrclibAdapter
from karaoke.adapters.separators import DemucsSeparatorAdapter
from karaoke.adapters.storage import LocalStorageAdapter
from karaoke.application.use_cases import (
    EvaluatePerformanceUseCase,
    GetLyricsUseCase,
    ListSongsUseCase,
    PrepareSongUseCase,
)
from karaoke.infrastructure.config import AppConfig


class AppContainer:
    """Composition Root da aplicação.

    Instancia todos os adaptadores concretos e conecta-os aos casos de uso
    correspondentes. Garante que nenhum adaptador seja instanciado fora
    da camada de infraestrutura.
    """

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.from_env()
        self.config.ensure_storage_directories()

        # 1. Adaptadores Concretos de Infraestrutura e DSP
        self.storage = LocalStorageAdapter(base_dir=self.config.storage_dir)
        self.downloader = YtDlpDownloaderAdapter()
        self.separator = DemucsSeparatorAdapter(
            model_name=self.config.demucs_model,
            device=self.config.device,
        )
        self.lyrics_provider = LrclibAdapter(base_url=self.config.lrclib_url)
        self.pitch_extractor = LibrosaPitchExtractorAdapter()
        self.onset_detector = EnergyVocalOnsetDetectorAdapter()
        self.scorer = DtwPerformanceScorerAdapter(
            pitch_weight=self.config.pitch_weight,
            timing_weight=self.config.timing_weight,
            cents_tolerance=self.config.cents_tolerance,
        )

        # 2. Casos de Uso montados e prontos para uso
        self.prepare_song = PrepareSongUseCase(
            downloader=self.downloader,
            separator=self.separator,
            storage=self.storage,
            lyrics_provider=self.lyrics_provider,
        )
        self.evaluate_performance = EvaluatePerformanceUseCase(
            storage=self.storage,
            pitch_extractor=self.pitch_extractor,
            scorer=self.scorer,
        )
        self.list_songs = ListSongsUseCase(
            storage=self.storage,
            base_audio_url=self.config.base_audio_url,
        )
        self.get_lyrics = GetLyricsUseCase(
            storage=self.storage,
            onset_detector=self.onset_detector,
            lyrics_provider=self.lyrics_provider,
        )


# Funções Fábrica e Gerenciamento de Singleton

_container_instance: AppContainer | None = None


def create_container(config: AppConfig | None = None) -> AppContainer:
    """Cria e retorna uma nova instância isolada de AppContainer."""
    return AppContainer(config=config)


def get_container() -> AppContainer:
    """Retorna uma instância singleton de AppContainer para injeção no FastAPI."""
    global _container_instance
    if _container_instance is None:
        _container_instance = create_container()
    return _container_instance


def reset_container() -> None:
    """Reinicia a instância singleton de AppContainer (útil para testes)."""
    global _container_instance
    _container_instance = None
