"""Adaptador de Detecção de Onset Vocal por Energia RMS.

Implementação com EnergyVocalOnsetDetectorAdapter.
"""

from pathlib import Path

import numpy as np
import scipy.io.wavfile as wavfile

from karaoke.application.ports import VocalOnsetDetectorPort


class EnergyVocalOnsetDetectorAdapter(VocalOnsetDetectorPort):
    """Detecta o primeiro instante em que o vocal inicia em um arquivo de áudio isolado.

    Analisa janelas de energia RMS na porção inicial do arquivo de áudio
    (faixa vocal gerada pelo Demucs) para identificar quando a voz ultrapassa
    o limiar de ruído/silêncio de forma contínua.
    """

    def __init__(
        self,
        analysis_window_seconds: float = 0.1,
        hop_seconds: float = 0.05,
        energy_threshold_ratio: float = 0.06,
        max_duration_seconds: float = 45.0,
        consecutive_windows: int = 2,
    ) -> None:
        self.analysis_window_seconds = analysis_window_seconds
        self.hop_seconds = hop_seconds
        self.energy_threshold_ratio = energy_threshold_ratio
        self.max_duration_seconds = max_duration_seconds
        self.consecutive_windows = consecutive_windows

    def detect_onset(self, audio_path: Path) -> float | None:
        """Calcula o instante em segundos do primeiro início vocal audível na faixa."""
        resolved_path = Path(audio_path).resolve()
        if not resolved_path.is_file():
            return None

        audio_data, sample_rate = self._read_audio(resolved_path)
        if audio_data is None or sample_rate <= 0:
            return None

        mono_data = self._to_mono(audio_data)
        truncated_data = self._truncate_audio(mono_data, sample_rate)
        energies, timestamps = self._compute_rms_windows(truncated_data, sample_rate)

        return self._find_first_sustained_energy(energies, timestamps)

    def _read_audio(self, path: Path) -> tuple[np.ndarray | None, int]:
        """Lê os dados brutos e sample rate do arquivo wav de forma segura."""
        try:
            sample_rate, data = wavfile.read(str(path))
            return data, sample_rate
        except Exception:
            return None, 0

    def _to_mono(self, data: np.ndarray) -> np.ndarray:
        """Converte áudio estéreo em mono calculando a média dos canais."""
        if data.ndim > 1:
            return data.mean(axis=1)
        return data

    def _truncate_audio(self, data: np.ndarray, sample_rate: int) -> np.ndarray:
        """Limita o processamento à janela inicial da música para máxima eficiência."""
        max_samples = int(self.max_duration_seconds * sample_rate)
        return data[:max_samples].astype(np.float32)

    def _compute_rms_windows(
        self, data: np.ndarray, sample_rate: int
    ) -> tuple[list[float], list[float]]:
        """Calcula a energia RMS e timestamps em janelas deslizantes."""
        hop_samples = max(1, int(self.hop_seconds * sample_rate))
        win_samples = max(1, int(self.analysis_window_seconds * sample_rate))

        energies: list[float] = []
        timestamps: list[float] = []

        total_samples = len(data)
        for start_idx in range(0, total_samples - win_samples, hop_samples):
            window_slice = data[start_idx : start_idx + win_samples]
            rms = float(np.sqrt(np.mean(window_slice**2)))
            energies.append(rms)
            timestamps.append(start_idx / sample_rate)

        return energies, timestamps

    def _find_first_sustained_energy(
        self, energies: list[float], timestamps: list[float]
    ) -> float | None:
        """Identifica o primeiro ponto em que a energia se sustenta acima do limiar."""
        if not energies:
            return None

        max_energy = max(energies)
        if max_energy <= 1e-4:
            return None

        threshold = self.energy_threshold_ratio * max_energy
        count = len(energies)
        required_consecutive = self.consecutive_windows

        for i in range(count - required_consecutive + 1):
            is_sustained = all(
                energies[i + offset] > threshold
                for offset in range(required_consecutive)
            )
            if is_sustained:
                return round(timestamps[i], 2)

        return None
