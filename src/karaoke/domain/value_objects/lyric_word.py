"""Objeto de Valor: LyricWord."""

from dataclasses import dataclass

from karaoke.domain.exceptions import InvalidLyricsTimeError


@dataclass(frozen=True)
class LyricWord:
    """Representa uma palavra individual da letra sincronizada no tempo."""

    text: str
    start_time: float
    end_time: float

    def __post_init__(self) -> None:
        if self.start_time < 0.0:
            raise InvalidLyricsTimeError("start_time da palavra não pode ser negativo.")
        if self.start_time > self.end_time:
            msg = (
                f"start_time ({self.start_time}) não pode ser maior que "
                f"end_time ({self.end_time}) na palavra '{self.text}'."
            )
            raise InvalidLyricsTimeError(msg)
