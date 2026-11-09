"""Testes unitários para EnergyVocalOnsetDetectorAdapter."""

from pathlib import Path

import numpy as np
import pytest
import scipy.io.wavfile as wavfile

from karaoke.adapters.audio import EnergyVocalOnsetDetectorAdapter


class TestEnergyVocalOnsetDetectorAdapter:
    @pytest.fixture
    def detector(self) -> EnergyVocalOnsetDetectorAdapter:
        return EnergyVocalOnsetDetectorAdapter(
            analysis_window_seconds=0.1,
            hop_seconds=0.05,
            energy_threshold_ratio=0.1,
            max_duration_seconds=10.0,
            consecutive_windows=2,
        )

    def test_detect_onset_nonexistent_file(
        self, detector: EnergyVocalOnsetDetectorAdapter, tmp_path: Path
    ) -> None:
        result = detector.detect_onset(tmp_path / "nonexistent.wav")
        assert result is None

    def test_detect_onset_silent_audio(
        self, detector: EnergyVocalOnsetDetectorAdapter, tmp_path: Path
    ) -> None:
        sr = 22050
        duration = 3.0
        data = np.zeros(int(sr * duration), dtype=np.int16)

        wav_path = tmp_path / "silence.wav"
        wavfile.write(str(wav_path), sr, data)

        result = detector.detect_onset(wav_path)
        assert result is None

    def test_detect_onset_with_intro_silence_then_voice(
        self, detector: EnergyVocalOnsetDetectorAdapter, tmp_path: Path
    ) -> None:
        sr = 22050
        silence_duration = 2.0
        voice_duration = 2.0

        silence = np.zeros(int(sr * silence_duration), dtype=np.float32)
        # Tom simulando vocal (440 Hz)
        t = np.linspace(0, voice_duration, int(sr * voice_duration), endpoint=False)
        voice = (np.sin(2 * np.pi * 440 * t) * 10000).astype(np.float32)

        combined = np.concatenate([silence, voice]).astype(np.int16)
        wav_path = tmp_path / "delayed_voice.wav"
        wavfile.write(str(wav_path), sr, combined)

        onset = detector.detect_onset(wav_path)
        assert onset is not None
        # O início detectado deve estar muito próximo de 2.0s (+-0.1s de janela)
        assert 1.9 <= onset <= 2.1
