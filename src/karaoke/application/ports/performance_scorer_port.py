"""Porta de Aplicação: PerformanceScorerPort."""

from typing import Protocol

from karaoke.domain import PitchCurve, ScoreResult


class PerformanceScorerPort(Protocol):
    """Contrato para avaliação de performance vocal (afinação e ritmo via DTW)."""

    def score_performance(
        self,
        reference_curve: PitchCurve,
        user_curve: PitchCurve,
    ) -> ScoreResult:
        """Compara as curvas gravada e original e gera o ScoreResult."""
        ...
