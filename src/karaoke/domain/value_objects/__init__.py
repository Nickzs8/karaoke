"""Objetos de valor da camada de Domínio."""

from karaoke.domain.value_objects.lyric_word import LyricWord
from karaoke.domain.value_objects.lyrics_line import LyricsLine
from karaoke.domain.value_objects.pitch_curve import PitchCurve
from karaoke.domain.value_objects.pitch_point import PitchPoint
from karaoke.domain.value_objects.score import Score
from karaoke.domain.value_objects.score_result import ScoreResult

__all__ = [
    "LyricWord",
    "LyricsLine",
    "PitchCurve",
    "PitchPoint",
    "Score",
    "ScoreResult",
]
