"""Testes unitários para o módulo de Infraestrutura (config e container)."""

from pathlib import Path
from unittest.mock import patch

import pytest

from karaoke.adapters.audio import (
    DtwPerformanceScorerAdapter,
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
from karaoke.infrastructure import (
    AppConfig,
    AppContainer,
    create_container,
    detect_device,
    get_container,
    load_env_file,
    reset_container,
)


class TestHardwareDetection:
    def test_detect_device_fallback_to_cpu(self) -> None:
        """Quando CUDA não está disponível, deve retornar CPU com fallback gracioso."""
        with patch("torch.cuda.is_available", return_value=False):
            assert detect_device() == "cpu"
            assert detect_device("cuda") == "cpu"
            assert detect_device("cpu") == "cpu"

    def test_detect_device_cuda_when_available(self) -> None:
        """Quando CUDA está disponível, deve priorizá-lo a menos que forçado."""
        with patch("torch.cuda.is_available", return_value=True):
            assert detect_device() == "cuda"
            assert detect_device("cuda") == "cuda"
            assert detect_device("cpu") == "cpu"


class TestAppConfig:
    def test_default_config_resolution(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifica os valores padrão e a resolução dos caminhos no AppConfig."""
        monkeypatch.setattr(
            "karaoke.infrastructure.config.load_env_file", lambda _: None
        )
        for env_var in (
            "KARAOKE_CENTS_TOLERANCE",
            "KARAOKE_PITCH_WEIGHT",
            "KARAOKE_TIMING_WEIGHT",
            "KARAOKE_STORAGE_DIR",
            "KARAOKE_DEVICE",
            "KARAOKE_DEMUCS_MODEL",
            "KARAOKE_BASE_AUDIO_URL",
            "KARAOKE_LRCLIB_URL",
        ):
            monkeypatch.delenv(env_var, raising=False)

        config = AppConfig.from_env()

        assert config.base_dir.is_dir() is True
        assert config.storage_dir.name == "storage"
        assert config.demucs_model == "htdemucs"
        assert config.base_audio_url == "/static/audio"
        assert config.lrclib_url == "https://lrclib.net/api"
        assert config.pitch_weight == 0.7
        assert config.timing_weight == 0.3
        assert config.cents_tolerance == 100.0

        # Subpastas de armazenamento
        assert config.raw_storage_dir == config.storage_dir / "raw"
        assert config.processed_storage_dir == config.storage_dir / "processed"
        assert config.recordings_storage_dir == config.storage_dir / "recordings"
        assert config.lyrics_storage_dir == config.storage_dir / "lyrics"

    def test_custom_env_variables_parsing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Valida que variáveis de ambiente sobrescrevem os defaults."""
        custom_storage = tmp_path / "custom_storage"
        monkeypatch.setenv("KARAOKE_STORAGE_DIR", str(custom_storage))
        monkeypatch.setenv("KARAOKE_DEVICE", "cpu")
        monkeypatch.setenv("KARAOKE_DEMUCS_MODEL", "mdx_extra")
        monkeypatch.setenv("KARAOKE_BASE_AUDIO_URL", "/stream/audio")
        monkeypatch.setenv("KARAOKE_PITCH_WEIGHT", "0.8")
        monkeypatch.setenv("KARAOKE_TIMING_WEIGHT", "0.2")
        monkeypatch.setenv("KARAOKE_CENTS_TOLERANCE", "40.0")

        config = AppConfig.from_env()

        assert config.storage_dir == custom_storage.resolve()
        assert config.device == "cpu"
        assert config.demucs_model == "mdx_extra"
        assert config.base_audio_url == "/stream/audio"
        assert config.pitch_weight == 0.8
        assert config.timing_weight == 0.2
        assert config.cents_tolerance == 40.0

    def test_ensure_storage_directories_creates_all_subfolders(
        self, tmp_path: Path
    ) -> None:
        """Assegura a criação física de todas as subpastas em storage/."""
        custom_storage = tmp_path / "novo_storage"
        config = AppConfig(
            base_dir=tmp_path,
            storage_dir=custom_storage,
            device="cpu",
        )

        assert not custom_storage.exists()
        config.ensure_storage_directories()

        assert config.raw_storage_dir.is_dir() is True
        assert config.processed_storage_dir.is_dir() is True
        assert config.recordings_storage_dir.is_dir() is True
        assert config.lyrics_storage_dir.is_dir() is True

    def test_load_env_file_parsing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifica se load_env_file lê corretamente chave=valor de arquivo .env."""
        env_file = tmp_path / ".env"
        env_file.write_text(
            "# Comentario\n"
            "KARAOKE_TEST_KEY=valor_teste\n"
            "KARAOKE_QUOTED_KEY='valor_com_aspas'\n"
            "\n"
            "INVALID_LINE_WITHOUT_EQUALS\n"
        )
        monkeypatch.delenv("KARAOKE_TEST_KEY", raising=False)
        monkeypatch.delenv("KARAOKE_QUOTED_KEY", raising=False)

        load_env_file(env_file)

        import os

        assert os.getenv("KARAOKE_TEST_KEY") == "valor_teste"
        assert os.getenv("KARAOKE_QUOTED_KEY") == "valor_com_aspas"


class TestAppContainer:
    @pytest.fixture(autouse=True)
    def clean_singleton(self) -> None:
        reset_container()
        yield
        reset_container()

    def test_container_composition_root_wiring(self, tmp_path: Path) -> None:
        """Valida que o container monta todos os adaptadores e casos de uso."""
        config = AppConfig(
            base_dir=tmp_path,
            storage_dir=tmp_path / "storage",
            device="cpu",
        )
        container = AppContainer(config=config)

        # 1. Adaptadores concretos
        assert isinstance(container.storage, LocalStorageAdapter)
        assert isinstance(container.downloader, YtDlpDownloaderAdapter)
        assert isinstance(container.separator, DemucsSeparatorAdapter)
        assert isinstance(container.lyrics_provider, LrclibAdapter)
        assert isinstance(container.pitch_extractor, LibrosaPitchExtractorAdapter)
        assert isinstance(container.scorer, DtwPerformanceScorerAdapter)

        # 2. Casos de uso conectados
        assert isinstance(container.prepare_song, PrepareSongUseCase)
        assert isinstance(container.evaluate_performance, EvaluatePerformanceUseCase)
        assert isinstance(container.list_songs, ListSongsUseCase)
        assert isinstance(container.get_lyrics, GetLyricsUseCase)

    def test_container_singleton_and_factory(self) -> None:
        """Testa o comportamento das funções fábrica e singleton do container."""
        c1 = get_container()
        c2 = get_container()
        assert c1 is c2  # Singleton

        c3 = create_container()
        assert c3 is not c1  # Nova instância independente

        reset_container()
        c4 = get_container()
        assert c4 is not c1  # Novo singleton após o reset
