"""Objeto de Valor: PitchPoint."""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class PitchPoint:
    """Ponto de afinação em um instante temporal específico.

    Armazena o timestamp em segundos, a frequência fundamental em Hertz (F0)
    e a nota equivalente na escala contínua de semitons MIDI.
    """

    timestamp: float
    frequency_hz: float
    midi_note: float | None = None

    def __post_init__(self) -> None:
        if self.timestamp < 0.0:
            raise ValueError("O timestamp não pode ser negativo.")
        if self.frequency_hz < 0.0:
            raise ValueError("A frequência em Hertz não pode ser negativa.")

        if self.midi_note is None:
            if self.frequency_hz > 0.0:
                calculated_midi = 69.0 + 12.0 * math.log2(self.frequency_hz / 440.0)
                object.__setattr__(self, "midi_note", round(calculated_midi, 4))
            else:
                object.__setattr__(self, "midi_note", 0.0)
