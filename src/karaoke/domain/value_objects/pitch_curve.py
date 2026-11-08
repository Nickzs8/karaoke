"""Objeto de Valor Composto: PitchCurve."""

from dataclasses import dataclass

from karaoke.domain.value_objects.pitch_point import PitchPoint


@dataclass(frozen=True)
class PitchCurve:
    """Série temporal de frequências fundamentais (F0)."""

    points: tuple[PitchPoint, ...] = ()

    @property
    def is_empty(self) -> bool:
        """Indica se a curva não possui pontos registrados."""
        return len(self.points) == 0

    @property
    def duration(self) -> float:
        """Retorna a duração total da curva em segundos."""
        if not self.points:
            return 0.0
        return self.points[-1].timestamp
