"""Objeto de Valor Composto: ScoreResult."""

from dataclasses import dataclass, field
from typing import Any

from karaoke.domain.value_objects.score import Score


@dataclass(frozen=True)
class ScoreResult:
    """Resultado consolidado da avaliação do canto de um usuário."""

    pitch_score: Score
    timing_score: Score
    total_score: Score
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def calculate(
        cls,
        pitch_score: Score,
        timing_score: Score,
        pitch_weight: float = 0.7,
        timing_weight: float = 0.3,
        details: dict[str, Any] | None = None,
    ) -> "ScoreResult":
        """Calcula a nota consolidada ponderada entre afinação e ritmo."""
        weighted_total = (pitch_score.value * pitch_weight) + (
            timing_score.value * timing_weight
        )
        total_score = Score(round(weighted_total, 2))
        return cls(
            pitch_score=pitch_score,
            timing_score=timing_score,
            total_score=total_score,
            details=details or {},
        )
