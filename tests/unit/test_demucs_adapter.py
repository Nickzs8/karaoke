"""Testes unitários para o adaptador DemucsSeparatorAdapter utilizando Mocks."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import torch

from karaoke.adapters.separators import DemucsSeparatorAdapter
from karaoke.application.ports import AudioSeparatorPort
from karaoke.domain import AudioSeparationError


class TestDemucsSeparatorAdapter:
    @pytest.fixture
    def adapter(self) -> DemucsSeparatorAdapter:
        return DemucsSeparatorAdapter(model_name="htdemucs", device="cpu")

    def test_satisfies_audio_separator_port_protocol(
        self, adapter: DemucsSeparatorAdapter
    ) -> None:
        port: AudioSeparatorPort = adapter
        assert port is not None

    def test_default_performance_parameters(self) -> None:
        adapter = DemucsSeparatorAdapter(device="cpu")
        assert adapter.shifts == 0
        assert adapter.overlap == 0.1

    def test_custom_performance_parameters(self) -> None:
        adapter = DemucsSeparatorAdapter(device="cpu", shifts=2, overlap=0.3)
        assert adapter.shifts == 2
        assert adapter.overlap == 0.3

    def test_detect_device_cuda_fallback(self) -> None:
        adapter_cpu = DemucsSeparatorAdapter(device="cpu")
        assert adapter_cpu.device == "cpu"

        # Simula torch.cuda.is_available() retornando True
        with patch("torch.cuda.is_available", return_value=True):
            adapter_auto = DemucsSeparatorAdapter(device=None)
            assert adapter_auto.device == "cuda"

        # Simula torch.cuda.is_available() retornando False
        with patch("torch.cuda.is_available", return_value=False):
            adapter_auto_cpu = DemucsSeparatorAdapter(device=None)
            assert adapter_auto_cpu.device == "cpu"

    def test_missing_input_audio_raises_error(
        self, adapter: DemucsSeparatorAdapter, tmp_path: Path
    ) -> None:
        fake_path = tmp_path / "nao_existe.wav"
        with pytest.raises(AudioSeparationError, match="não encontrado"):
            adapter.separate(fake_path, tmp_path)

    @patch("demucs.api.save_audio")
    @patch("demucs.api.Separator")
    def test_separate_audio_success_mocked(
        self,
        mock_separator_class: MagicMock,
        mock_save_audio: MagicMock,
        adapter: DemucsSeparatorAdapter,
        tmp_path: Path,
    ) -> None:
        # Cria arquivo de entrada simulado
        input_audio = tmp_path / "song.mp3"
        input_audio.write_bytes(b"audio_bytes")

        output_dir = tmp_path / "output"

        # Mock da instância do Separator do Demucs
        mock_sep_instance = MagicMock()
        mock_sep_instance.samplerate = 44100
        mock_separator_class.return_value = mock_sep_instance

        # Cria tensores falsos representando os 4 stems
        vocals_tensor = torch.zeros((2, 44100))
        drums_tensor = torch.ones((2, 44100))
        bass_tensor = torch.ones((2, 44100))
        other_tensor = torch.ones((2, 44100))

        mock_sep_instance.separate_audio_file.return_value = (
            torch.zeros((2, 44100)),
            {
                "vocals": vocals_tensor,
                "drums": drums_tensor,
                "bass": bass_tensor,
                "other": other_tensor,
            },
        )

        result = adapter.separate(input_audio, output_dir)

        assert result.vocals_path == output_dir / "vocals.wav"
        assert result.instrumental_path == output_dir / "no_vocals.wav"

        # Valida que demucs.api.save_audio foi chamado 2 vezes (voz e instrumental)
        assert mock_save_audio.call_count == 2

    @patch("demucs.api.Separator")
    def test_demucs_exception_converted_to_domain_error(
        self,
        mock_separator_class: MagicMock,
        adapter: DemucsSeparatorAdapter,
        tmp_path: Path,
    ) -> None:
        input_audio = tmp_path / "song.mp3"
        input_audio.write_bytes(b"audio_bytes")

        mock_sep_instance = MagicMock()
        mock_sep_instance.separate_audio_file.side_effect = RuntimeError(
            "CUDA out of memory"
        )
        mock_separator_class.return_value = mock_sep_instance

        with pytest.raises(AudioSeparationError, match="Erro durante o processamento"):
            adapter.separate(input_audio, tmp_path)

    @patch("demucs.api.Separator")
    def test_missing_vocals_stem_raises_error(
        self,
        mock_separator_class: MagicMock,
        adapter: DemucsSeparatorAdapter,
        tmp_path: Path,
    ) -> None:
        input_audio = tmp_path / "song.mp3"
        input_audio.write_bytes(b"audio_bytes")

        mock_sep_instance = MagicMock()
        mock_sep_instance.samplerate = 44100
        # Retorna stems sem a chave 'vocals'
        mock_sep_instance.separate_audio_file.return_value = (
            torch.zeros((2, 44100)),
            {"drums": torch.zeros((2, 44100))},
        )
        mock_separator_class.return_value = mock_sep_instance

        with pytest.raises(AudioSeparationError, match="não foi encontrada"):
            adapter.separate(input_audio, tmp_path)
