"""Objeto de Valor: Score."""

from dataclasses import dataclass

from karaoke.domain.exceptions import InvalidScoreError


@dataclass(frozen=True)
class Score:
    """Representa uma pontuação matemática de desempenho entre 0.0 e 100.0."""

    value: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.value <= 100.0):
            raise InvalidScoreError(
                f"O score deve estar entre 0.0 e 100.0. Valor informado: {self.value}"
            )

    def as_integer(self) -> int:
        """Retorna o valor arredondado como inteiro."""
        return round(self.value)
