"""Adaptador de Extração de Pitch F0: LibrosaPitchExtractorAdapter."""

import math
import subprocess
from pathlib import Path

import librosa
import numpy as np

from karaoke.application.ports import PitchExtractorPort
from karaoke.domain import PitchCurve, PitchExtractionError, PitchPoint


class LibrosaPitchExtractorAdapter(PitchExtractorPort):
    """Implementa PitchExtractorPort utilizando o algoritmo pYIN do Librosa.

    Extrai a frequência fundamental (F0), converte para a escala contínua de
    semitons MIDI e filtra silêncios e ruídos com base em energia RMS e confiança.
    """

    def __init__(
        self,
        sample_rate: int = 22050,
        fmin: float = 65.0,  # ~C2
        fmax: float = 2093.0,  # ~C7
        frame_length: int = 2048,
        hop_length: int = 512,
        min_voiced_prob: float = 0.01,
        energy_threshold: float = 0.005,
    ) -> None:
        self.sample_rate = sample_rate
        self.fmin = fmin
        self.fmax = fmax
        self.frame_length = frame_length
        self.hop_length = hop_length
        self.min_voiced_prob = min_voiced_prob
        self.energy_threshold = energy_threshold

    def extract_pitch(self, audio_path: Path) -> PitchCurve:
        """Orquestra a extração da curva melódica F0 a partir de um arquivo de áudio."""
        valid_path = self._validate_audio_path(audio_path)
        audio_mono, sr = self._load_mono_audio(valid_path)

        f0, voiced_flag, voiced_probs = self._compute_pyin(audio_mono, sr)
        rms_energy = self._compute_rms_energy(audio_mono)
        timestamps = self._compute_timestamps(len(f0), sr)

        points = self._build_pitch_points(
            f0=f0,
            voiced_flag=voiced_flag,
            voiced_probs=voiced_probs,
            rms_energy=rms_energy,
            timestamps=timestamps,
        )
        return PitchCurve(points=points)

    def _validate_audio_path(self, audio_path: Path) -> Path:
        """Garante a existência física do arquivo de áudio para análise."""
        resolved = Path(audio_path).resolve()
        if not resolved.is_file():
            raise PitchExtractionError(
                f"Arquivo de áudio não encontrado para extração de pitch: {audio_path}"
            )
        return resolved

    def _load_mono_audio(self, audio_path: Path) -> tuple[np.ndarray, int]:
        """Carrega o áudio e converte automaticamente para canal mono."""
        try:
            y, sr = librosa.load(str(audio_path), sr=self.sample_rate, mono=True)
            return y, sr
        except Exception as exc:
            # Fallback robusto via ffmpeg para containers modernos (WebM, Opus, AAC)
            decoded = self._decode_via_ffmpeg(audio_path)
            if decoded is not None:
                return decoded, self.sample_rate

            raise PitchExtractionError(
                f"Falha ao carregar arquivo de áudio '{audio_path.name}': {exc}"
            ) from exc

    def _decode_via_ffmpeg(self, audio_path: Path) -> np.ndarray | None:
        """Decodifica qualquer container de áudio (WebM, Opus, Ogg, AAC) via ffmpeg."""
        cmd = [
            "ffmpeg",
            "-nostdin",
            "-threads",
            "1",
            "-i",
            str(audio_path),
            "-f",
            "s16le",
            "-ac",
            "1",
            "-ar",
            str(self.sample_rate),
            "-",
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, check=False)
            if result.returncode == 0 and result.stdout:
                int16_data = np.frombuffer(result.stdout, dtype=np.int16)
                if len(int16_data) > 0:
                    return int16_data.astype(np.float32) / 32768.0
        except Exception:
            return None
        return None

    def _compute_pyin(
        self, audio_mono: np.ndarray, sr: int
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Aplica o algoritmo pYIN do Librosa para estimar a frequência fundamental."""
        try:
            f0, voiced_flag, voiced_probs = librosa.pyin(
                audio_mono,
                fmin=self.fmin,
                fmax=self.fmax,
                sr=sr,
                frame_length=self.frame_length,
                hop_length=self.hop_length,
            )
            return f0, voiced_flag, voiced_probs
        except Exception as exc:
            raise PitchExtractionError(
                f"Falha durante a estimativa de afinação pYIN: {exc}"
            ) from exc

    def _compute_rms_energy(self, audio_mono: np.ndarray) -> np.ndarray:
        """Calcula a energia sonora RMS (Root-Mean-Square) de cada frame."""
        rms_matrix = librosa.feature.rms(
            y=audio_mono,
            frame_length=self.frame_length,
            hop_length=self.hop_length,
        )
        return rms_matrix[0]

    def _compute_timestamps(self, num_frames: int, sr: int) -> np.ndarray:
        """Calcula o instante temporal central de cada frame de análise."""
        return librosa.frames_to_time(
            np.arange(num_frames),
            sr=sr,
            hop_length=self.hop_length,
        )

    def _build_pitch_points(
        self,
        f0: np.ndarray,
        voiced_flag: np.ndarray,
        voiced_probs: np.ndarray,
        rms_energy: np.ndarray,
        timestamps: np.ndarray,
    ) -> tuple[PitchPoint, ...]:
        """Converte os frames válidos em instâncias de PitchPoint."""
        points: list[PitchPoint] = []
        total_frames = len(f0)

        for i in range(total_frames):
            freq = float(f0[i]) if not np.isnan(f0[i]) else 0.0
            voiced = bool(voiced_flag[i])
            prob = float(voiced_probs[i]) if not np.isnan(voiced_probs[i]) else 0.0
            energy = float(rms_energy[i]) if i < len(rms_energy) else 0.0
            timestamp = float(timestamps[i])

            if self._is_valid_voiced_frame(freq, voiced, prob, energy):
                midi_note = self._hz_to_midi(freq)
                points.append(
                    PitchPoint(
                        timestamp=round(timestamp, 4),
                        frequency_hz=round(freq, 2),
                        midi_note=round(midi_note, 4),
                    )
                )

        return tuple(points)

    def _is_valid_voiced_frame(
        self, freq: float, voiced: bool, prob: float, energy: float
    ) -> bool:
        """Determina se o frame contém voz sustentada (não silêncio/ruído)."""
        return (
            voiced
            and freq > 0.0
            and prob >= self.min_voiced_prob
            and energy >= self.energy_threshold
        )

    def _hz_to_midi(self, freq_hz: float) -> float:
        """Converte uma frequência em Hertz para semitons contínuos na escala MIDI."""
        if freq_hz <= 0.0:
            return 0.0
        return 69.0 + 12.0 * math.log2(freq_hz / 440.0)
