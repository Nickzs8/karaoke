"""Objeto de Valor: LyricsLine."""

from dataclasses import dataclass

from karaoke.domain.exceptions import InvalidLyricsTimeError
from karaoke.domain.value_objects.lyric_word import LyricWord


@dataclass(frozen=True)
class LyricsLine:
    """Representa uma única linha de letra sincronizada no tempo."""

    start_time: float
    end_time: float
    text: str
    words: tuple[LyricWord, ...] = ()

    def __post_init__(self) -> None:
        if self.start_time < 0.0:
            raise InvalidLyricsTimeError("start_time não pode ser negativo.")
        if self.start_time > self.end_time:
            msg = (
                f"start_time ({self.start_time}) não pode ser maior que "
                f"end_time ({self.end_time})."
            )
            raise InvalidLyricsTimeError(msg)
