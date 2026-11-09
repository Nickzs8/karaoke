"""Adaptador de Avaliação de Desempenho Vocal: DtwPerformanceScorerAdapter."""

from typing import Any

import librosa.sequence
import numpy as np

from karaoke.application.ports import PerformanceScorerPort
from karaoke.domain import InvalidScorerConfigError, PitchCurve, Score, ScoreResult


class DtwPerformanceScorerAdapter(PerformanceScorerPort):
    """Implementa PerformanceScorerPort utilizando Dynamic Time Warping (DTW).

    Avalia objetivamente a afinação e o ritmo do canto comparando a curva
    do usuário com a curva de referência da faixa vocal original.
    """

    def __init__(
        self,
        pitch_weight: float = 0.7,
        timing_weight: float = 0.3,
        cents_tolerance: float = 50.0,
        max_cents_error: float = 200.0,
        timing_tolerance_seconds: float = 0.15,
        max_timing_deviation_seconds: float = 1.0,
        allow_octave_transposition: bool = True,
    ) -> None:
        """Inicializa o avaliador com parâmetros e tolerâncias configuráveis.

        Args:
            pitch_weight: Peso da afinação na nota consolidada final.
            timing_weight: Peso do ritmo na nota consolidada final.
            cents_tolerance: Tolerância em cents para nota máxima (50 cents).
            max_cents_error: Erro em cents acima do qual a afinação zera.
            timing_tolerance_seconds: Tolerância temporal em segundos para nota máxima.
            max_timing_deviation_seconds: Desvio temporal acima do qual o ritmo zera.
            allow_octave_transposition: Se deve tolerar diferenças de oitava.
        """
        if pitch_weight < 0.0 or timing_weight < 0.0:
            raise InvalidScorerConfigError(
                "Os pesos de afinação e ritmo não podem ser negativos."
            )
        total_weight = pitch_weight + timing_weight
        if total_weight <= 0.0:
            raise InvalidScorerConfigError("A soma dos pesos deve ser maior que zero.")

        # Normaliza os pesos para somarem 1.0
        self.pitch_weight = pitch_weight / total_weight
        self.timing_weight = timing_weight / total_weight

        if cents_tolerance < 0.0:
            raise InvalidScorerConfigError(
                "A tolerância de afinação não pode ser negativa."
            )
        if max_cents_error <= cents_tolerance:
            raise InvalidScorerConfigError(
                "max_cents_error deve ser estritamente maior que cents_tolerance."
            )

        if timing_tolerance_seconds < 0.0:
            raise InvalidScorerConfigError(
                "A tolerância de ritmo não pode ser negativa."
            )
        if max_timing_deviation_seconds <= timing_tolerance_seconds:
            raise InvalidScorerConfigError(
                "max_timing_deviation_seconds deve ser maior que "
                "timing_tolerance_seconds."
            )

        self.cents_tolerance = cents_tolerance
        self.max_cents_error = max_cents_error
        self.timing_tolerance_seconds = timing_tolerance_seconds
        self.max_timing_deviation_seconds = max_timing_deviation_seconds
        self.allow_octave_transposition = allow_octave_transposition

    def score_performance(
        self,
        reference_curve: PitchCurve,
        user_curve: PitchCurve,
    ) -> ScoreResult:
        """Orquestra a comparação entre curvas de pitch e consolida o ScoreResult."""
        ref_times, ref_midi = self._extract_pitch_arrays(reference_curve)
        user_times, user_midi = self._extract_pitch_arrays(user_curve)

        if len(ref_midi) == 0 or len(user_midi) == 0:
            return self._build_empty_score_result(len(ref_midi), len(user_midi))

        octave_shift = self._determine_octave_shift(ref_midi, user_midi)
        transposed_user_midi = self._apply_octave_transposition(user_midi, octave_shift)

        cost_matrix = self._build_cost_matrix(ref_midi, transposed_user_midi)
        warping_path = self._compute_dtw_alignment(cost_matrix)

        pitch_score_val, mean_cents, max_cents = self._calculate_pitch_metrics(
            ref_midi, transposed_user_midi, warping_path
        )
        timing_score_val, mean_timing, max_timing = self._calculate_timing_metrics(
            ref_times, user_times, warping_path
        )

        return self._build_score_result(
            pitch_score_val=pitch_score_val,
            timing_score_val=timing_score_val,
            octave_shift=octave_shift,
            mean_cents_error=mean_cents,
            max_cents_error=max_cents,
            mean_timing_deviation=mean_timing,
            max_timing_deviation=max_timing,
            warping_path_length=len(warping_path),
            ref_points_count=len(ref_midi),
            user_points_count=len(user_midi),
        )

    def _extract_pitch_arrays(self, curve: PitchCurve) -> tuple[np.ndarray, np.ndarray]:
        """Extrai timestamps e notas MIDI contínuas apenas de pontos vocais válidos."""
        valid_points = [
            point
            for point in curve.points
            if point.frequency_hz > 0.0
            and point.midi_note is not None
            and point.midi_note > 0.0
        ]
        if not valid_points:
            return np.empty(0, dtype=np.float64), np.empty(0, dtype=np.float64)

        timestamps = np.array([p.timestamp for p in valid_points], dtype=np.float64)
        midi_notes = np.array([p.midi_note for p in valid_points], dtype=np.float64)
        return timestamps, midi_notes

    def _determine_octave_shift(
        self, ref_midi: np.ndarray, user_midi: np.ndarray
    ) -> int:
        """Determina o deslocamento de oitavas entre a referência e o usuário."""
        if not self.allow_octave_transposition:
            return 0
        diff_median = float(np.median(ref_midi) - np.median(user_midi))
        return int(round(diff_median / 12.0))

    def _apply_octave_transposition(
        self, user_midi: np.ndarray, octave_shift: int
    ) -> np.ndarray:
        """Transpõe as notas MIDI do usuário pela quantidade de oitavas calculada."""
        if octave_shift == 0:
            return user_midi
        return user_midi + (float(octave_shift) * 12.0)

    def _build_cost_matrix(
        self, ref_midi: np.ndarray, user_midi: np.ndarray
    ) -> np.ndarray:
        """Constrói a matriz de custo de distância tonal entre cada par de frames."""
        diff = ref_midi[:, None] - user_midi[None, :]
        if self.allow_octave_transposition:
            octave_diff = diff - 12.0 * np.round(diff / 12.0)
            return np.abs(octave_diff)
        return np.abs(diff)

    def _compute_dtw_alignment(self, cost_matrix: np.ndarray) -> np.ndarray:
        """Executa o algoritmo Dynamic Time Warping sobre a matriz de custo."""
        _, warping_path = librosa.sequence.dtw(C=cost_matrix)
        # librosa retorna da última célula (N-1, M-1) até (0, 0); invertemos a ordem
        return warping_path[::-1]

    def _calculate_pitch_metrics(
        self,
        ref_midi: np.ndarray,
        user_midi: np.ndarray,
        warping_path: np.ndarray,
    ) -> tuple[float, float, float]:
        """Calcula afinação e estatísticas em cents ao longo do caminho DTW."""
        cents_errors: list[float] = []
        point_scores: list[float] = []

        for ref_idx, user_idx in warping_path:
            raw_diff = float(user_midi[user_idx] - ref_midi[ref_idx])
            if self.allow_octave_transposition:
                adjusted_diff = raw_diff - 12.0 * round(raw_diff / 12.0)
            else:
                adjusted_diff = raw_diff

            cents_error = abs(adjusted_diff) * 100.0
            cents_errors.append(cents_error)
            point_scores.append(self._cents_error_to_score(cents_error))

        mean_pitch_score = float(np.mean(point_scores))
        mean_cents = float(np.mean(cents_errors))
        max_cents = float(np.max(cents_errors))
        return mean_pitch_score, mean_cents, max_cents

    def _cents_error_to_score(self, cents_error: float) -> float:
        """Converte um erro absoluto em cents em uma pontuação entre 0.0 e 100.0."""
        if cents_error <= self.cents_tolerance:
            return 100.0
        if cents_error >= self.max_cents_error:
            return 0.0

        ratio = (cents_error - self.cents_tolerance) / (
            self.max_cents_error - self.cents_tolerance
        )
        return 100.0 * (1.0 - ratio)

    def _calculate_timing_metrics(
        self,
        ref_timestamps: np.ndarray,
        user_timestamps: np.ndarray,
        warping_path: np.ndarray,
    ) -> tuple[float, float, float]:
        """Calcula score de ritmo e desvios a partir do caminho ótimo do DTW."""
        timing_deviations: list[float] = []
        point_scores: list[float] = []

        for ref_idx, user_idx in warping_path:
            ref_t = float(ref_timestamps[ref_idx])
            user_t = float(user_timestamps[user_idx])
            deviation = abs(user_t - ref_t)

            timing_deviations.append(deviation)
            point_scores.append(self._timing_deviation_to_score(deviation))

        mean_timing_score = float(np.mean(point_scores))
        mean_deviation = float(np.mean(timing_deviations))
        max_deviation = float(np.max(timing_deviations))
        return mean_timing_score, mean_deviation, max_deviation

    def _timing_deviation_to_score(self, deviation_seconds: float) -> float:
        """Converte um desvio temporal em segundos para pontuação de 0.0 a 100.0."""
        if deviation_seconds <= self.timing_tolerance_seconds:
            return 100.0
        if deviation_seconds >= self.max_timing_deviation_seconds:
            return 0.0

        ratio = (deviation_seconds - self.timing_tolerance_seconds) / (
            self.max_timing_deviation_seconds - self.timing_tolerance_seconds
        )
        return 100.0 * (1.0 - ratio)

    def _build_score_result(
        self,
        pitch_score_val: float,
        timing_score_val: float,
        octave_shift: int,
        mean_cents_error: float,
        max_cents_error: float,
        mean_timing_deviation: float,
        max_timing_deviation: float,
        warping_path_length: int,
        ref_points_count: int,
        user_points_count: int,
    ) -> ScoreResult:
        """Gera a instância de ScoreResult validada com métricas de desempenho."""
        bounded_pitch = round(min(100.0, max(0.0, pitch_score_val)), 2)
        bounded_timing = round(min(100.0, max(0.0, timing_score_val)), 2)

        pitch_score = Score(bounded_pitch)
        timing_score = Score(bounded_timing)

        details: dict[str, Any] = {
            "pitch_score": pitch_score.value,
            "timing_score": timing_score.value,
            "octave_shift": octave_shift,
            "mean_pitch_error_cents": round(mean_cents_error, 2),
            "max_pitch_error_cents": round(max_cents_error, 2),
            "mean_timing_deviation_seconds": round(mean_timing_deviation, 4),
            "max_timing_deviation_seconds": round(max_timing_deviation, 4),
            "aligned_points_count": warping_path_length,
            "reference_points_count": ref_points_count,
            "user_points_count": user_points_count,
        }

        return ScoreResult.calculate(
            pitch_score=pitch_score,
            timing_score=timing_score,
            pitch_weight=self.pitch_weight,
            timing_weight=self.timing_weight,
            details=details,
        )

    def _build_empty_score_result(self, ref_count: int, user_count: int) -> ScoreResult:
        """Retorna pontuação zerada se alguma curva não possuir pontos vocais."""
        details: dict[str, Any] = {
            "warning": "Uma ou ambas as curvas não possuem pontos vocais válidos.",
            "reference_points_count": ref_count,
            "user_points_count": user_count,
        }
        return ScoreResult.calculate(
            pitch_score=Score(0.0),
            timing_score=Score(0.0),
            pitch_weight=self.pitch_weight,
            timing_weight=self.timing_weight,
            details=details,
        )


# Alias para conveniência e compatibilidade
DtwScorerAdapter = DtwPerformanceScorerAdapter
