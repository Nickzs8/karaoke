"""Teste de integração para o adaptador DemucsSeparatorAdapter com áudio sintético."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import soundfile as sf
import torch

from karaoke.adapters.separators import DemucsSeparatorAdapter


class TestDemucsIntegration:
    @pytest.fixture
    def synthetic_audio(self, tmp_path: Path) -> Path:
        """Gera arquivo sintético estéreo de 0.2s (tom senoidal de 440Hz)."""
        sr = 44100
        duration = 0.2
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        mono_sine = 0.5 * np.sin(2 * np.pi * 440 * t)
        stereo_sine = np.column_stack((mono_sine, mono_sine))

        audio_file = tmp_path / "synthetic_song.wav"
        sf.write(str(audio_file), stereo_sine, samplerate=sr, format="WAV")
        return audio_file

    @patch("demucs.api.Separator")
    def test_pipeline_integration_with_synthetic_audio(
        self,
        mock_separator_class: MagicMock,
        synthetic_audio: Path,
        tmp_path: Path,
    ) -> None:
        """Valida a integração da pipeline completa de separação com áudio sintético."""
        output_dir = tmp_path / "separated"

        mock_instance = MagicMock()
        mock_instance.samplerate = 44100
        mock_separator_class.return_value = mock_instance

        # Tensores sintéticos de 0.2s a 44100Hz
        samples = int(44100 * 0.2)
        mock_instance.separate_audio_file.return_value = (
            torch.zeros((2, samples)),
            {
                "vocals": torch.zeros((2, samples)),
                "drums": torch.zeros((2, samples)),
                "bass": torch.zeros((2, samples)),
                "other": torch.zeros((2, samples)),
            },
        )

        adapter = DemucsSeparatorAdapter(device="cpu")
        result = adapter.separate(synthetic_audio, output_dir)

        assert result.vocals_path.is_file()
        assert result.instrumental_path.is_file()
        assert result.vocals_path.name == "vocals.wav"
        assert result.instrumental_path.name == "no_vocals.wav"
