"""Testes unitários para LibrosaPitchExtractorAdapter."""

import math
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from karaoke.adapters.audio import LibrosaPitchExtractorAdapter
from karaoke.domain import PitchCurve, PitchExtractionError, PitchPoint


def test_extract_pitch_raises_when_file_not_found(tmp_path: Path) -> None:
    adapter = LibrosaPitchExtractorAdapter()
    missing_path = tmp_path / "nao_existe.wav"

    with pytest.raises(PitchExtractionError, match="Arquivo de áudio não encontrado"):
        adapter.extract_pitch(missing_path)


def test_extract_pitch_wraps_librosa_load_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audio_file = tmp_path / "corrompido.wav"
    audio_file.write_bytes(b"dados invalidos")

    def mock_load(*args: object, **kwargs: object) -> None:
        raise RuntimeError("Falha de codec simulada")

    monkeypatch.setattr("librosa.load", mock_load)

    adapter = LibrosaPitchExtractorAdapter()
    with pytest.raises(
        PitchExtractionError, match="Falha ao carregar arquivo de áudio"
    ):
        adapter.extract_pitch(audio_file)


def test_hz_to_midi_conversion() -> None:
    adapter = LibrosaPitchExtractorAdapter()

    assert adapter._hz_to_midi(440.0) == 69.0
    assert adapter._hz_to_midi(880.0) == 81.0  # +1 oitava
    assert adapter._hz_to_midi(220.0) == 57.0  # -1 oitava
    assert adapter._hz_to_midi(0.0) == 0.0


def test_is_valid_voiced_frame() -> None:
    adapter = LibrosaPitchExtractorAdapter(min_voiced_prob=0.5, energy_threshold=0.01)

    # Frame vozeado perfeito
    assert adapter._is_valid_voiced_frame(
        freq=440.0, voiced=True, prob=0.9, energy=0.05
    )

    # Frame não-vozeado
    assert not adapter._is_valid_voiced_frame(
        freq=440.0, voiced=False, prob=0.9, energy=0.05
    )

    # Frequência zero ou inválida
    assert not adapter._is_valid_voiced_frame(
        freq=0.0, voiced=True, prob=0.9, energy=0.05
    )

    # Baixa confiança de voz
    assert not adapter._is_valid_voiced_frame(
        freq=440.0, voiced=True, prob=0.3, energy=0.05
    )

    # Energia sonora muito baixa (silêncio)
    assert not adapter._is_valid_voiced_frame(
        freq=440.0, voiced=True, prob=0.9, energy=0.005
    )


def test_extract_pitch_successful_mock_flow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audio_file = tmp_path / "voz.wav"
    audio_file.write_bytes(b"dummy")

    monkeypatch.setattr("librosa.load", lambda *args, **kwargs: (np.zeros(2048), 22050))
    monkeypatch.setattr(
        "librosa.pyin",
        lambda *args, **kwargs: (
            np.array([440.0, np.nan, 880.0]),
            np.array([True, False, True]),
            np.array([0.95, 0.1, 0.9]),
        ),
    )
    monkeypatch.setattr(
        "librosa.feature.rms",
        lambda *args, **kwargs: np.array([[0.05, 0.001, 0.04]]),
    )
    monkeypatch.setattr(
        "librosa.frames_to_time",
        lambda *args, **kwargs: np.array([0.0, 0.023, 0.046]),
    )

    adapter = LibrosaPitchExtractorAdapter()
    curve = adapter.extract_pitch(audio_file)

    assert isinstance(curve, PitchCurve)
    assert len(curve.points) == 2

    # Ponto 1: 440 Hz (Lá 4 / MIDI 69)
    assert curve.points[0] == PitchPoint(
        timestamp=0.0,
        frequency_hz=440.0,
        midi_note=69.0,
    )

    # Ponto 2: 880 Hz (Lá 5 / MIDI 81)
    assert curve.points[1] == PitchPoint(
        timestamp=0.046,
        frequency_hz=880.0,
        midi_note=81.0,
    )


def test_extract_pitch_with_synthetic_sine_audio(tmp_path: Path) -> None:
    """Valida pYIN real com uma onda senoidal curta de 440 Hz."""
    audio_file = tmp_path / "sine_440hz.wav"
    sample_rate = 22050
    duration_s = 0.2
    num_samples = int(sample_rate * duration_s)

    # Gera tom senoidal puro a 440 Hz
    t = np.linspace(0, duration_s, num_samples, endpoint=False)
    sine_wave = 0.5 * np.sin(2 * np.pi * 440.0 * t).astype(np.float32)
    sf.write(str(audio_file), sine_wave, sample_rate)

    adapter = LibrosaPitchExtractorAdapter(sample_rate=sample_rate)
    curve = adapter.extract_pitch(audio_file)

    assert not curve.is_empty
    # As frequências detectadas para 440 Hz devem estar próximas de 440 (+- 15 Hz)
    for point in curve.points:
        assert math.isclose(point.frequency_hz, 440.0, abs_tol=15.0)
        assert math.isclose(point.midi_note, 69.0, abs_tol=1.0)
