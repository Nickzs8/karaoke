"""Objeto de Valor: PitchPoint."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PitchPoint:
    """Ponto de afinação em um instante temporal específico."""

    timestamp: float
    frequency_hz: float

    def __post_init__(self) -> None:
        if self.timestamp < 0.0:
            raise ValueError("O timestamp não pode ser negativo.")
        if self.frequency_hz < 0.0:
            raise ValueError("A frequência em Hertz não pode ser negativa.")
