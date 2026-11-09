"""Testes unitários da camada de Domínio."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from pathlib import Path

import pytest

from karaoke.domain import (
    InvalidLyricsTimeError,
    InvalidPitchPointError,
    InvalidScoreError,
    LyricsLine,
    Performance,
    PitchCurve,
    PitchPoint,
    Score,
    ScoreResult,
    Song,
    SongNotReadyError,
    SongStatus,
)


class TestScoreValueObject:
    def test_valid_scores(self) -> None:
        score_zero = Score(0.0)
        score_mid = Score(75.5)
        score_max = Score(100.0)

        assert score_zero.value == 0.0
        assert score_mid.value == 75.5
        assert score_max.value == 100.0
        assert score_mid.as_integer() == 76

    @pytest.mark.parametrize("invalid_value", [-0.1, -10.0, 100.1, 150.0])
    def test_invalid_score_raises_exception(self, invalid_value: float) -> None:
        with pytest.raises(InvalidScoreError):
            Score(invalid_value)

    def test_score_is_immutable(self) -> None:
        score = Score(80.0)
        with pytest.raises(FrozenInstanceError):
            score.value = 90.0  # type: ignore[misc]


class TestLyricsLineValueObject:
    def test_valid_lyrics_line(self) -> None:
        line = LyricsLine(start_time=1.5, end_time=4.2, text="Don't stop believin'")
        assert line.start_time == 1.5
        assert line.end_time == 4.2
        assert line.text == "Don't stop believin'"

    def test_negative_start_time_raises_exception(self) -> None:
        with pytest.raises(InvalidLyricsTimeError):
            LyricsLine(start_time=-1.0, end_time=3.0, text="Invalid")

    def test_start_greater_than_end_raises_exception(self) -> None:
        with pytest.raises(InvalidLyricsTimeError):
            LyricsLine(start_time=5.0, end_time=2.0, text="Invalid order")


class TestPitchCurveValueObjects:
    def test_pitch_curve_empty(self) -> None:
        curve = PitchCurve()
        assert curve.is_empty is True
        assert curve.duration == 0.0

    def test_pitch_curve_with_points(self) -> None:
        p1 = PitchPoint(timestamp=0.5, frequency_hz=440.0)
        p2 = PitchPoint(timestamp=1.2, frequency_hz=466.16)
        curve = PitchCurve(points=(p1, p2))

        assert curve.is_empty is False
        assert len(curve.points) == 2
        assert curve.duration == 1.2

    def test_negative_timestamp_raises_domain_error(self) -> None:
        with pytest.raises(InvalidPitchPointError):
            PitchPoint(timestamp=-0.1, frequency_hz=440.0)

    def test_negative_frequency_raises_domain_error(self) -> None:
        with pytest.raises(InvalidPitchPointError):
            PitchPoint(timestamp=0.1, frequency_hz=-10.0)


class TestScoreResultValueObject:
    def test_score_result_calculation(self) -> None:
        pitch = Score(80.0)
        timing = Score(90.0)

        # 80 * 0.70 + 90 * 0.30 = 56 + 27 = 83.0
        result = ScoreResult.calculate(
            pitch_score=pitch,
            timing_score=timing,
            pitch_weight=0.7,
            timing_weight=0.3,
            details={"pitch_cents_error": 12.5},
        )

        assert result.pitch_score.value == 80.0
        assert result.timing_score.value == 90.0
        assert result.total_score.value == 83.0
        assert result.details["pitch_cents_error"] == 12.5

    def test_score_result_is_immutable(self) -> None:
        result = ScoreResult.calculate(
            pitch_score=Score(80.0), timing_score=Score(90.0)
        )
        with pytest.raises(FrozenInstanceError):
            result.total_score = Score(100.0)  # type: ignore[misc]


class TestSongEntity:
    def test_initial_song_state(self) -> None:
        song = Song(
            id="song-123",
            title="Bohemian Rhapsody",
            artist="Queen",
        )
        assert song.status == SongStatus.PENDING
        assert song.duration == 0.0
        assert song.instrumental_path is None
        assert song.vocals_path is None

    def test_lifecycle_and_state_transitions(self) -> None:
        song = Song(id="song-123", title="Song Test", artist="Artist Test")

        # Inicia processamento
        song.mark_as_processing()
        assert song.status == SongStatus.PROCESSING

        # Tentar verificar prontidão antes de pronta deve falhar
        with pytest.raises(SongNotReadyError):
            song.ensure_is_ready()

        # Define como pronta com os arquivos gerados
        inst_path = Path("/storage/processed/song-123_inst.wav")
        voc_path = Path("/storage/processed/song-123_voc.wav")
        song.mark_as_ready(
            instrumental_path=inst_path, vocals_path=voc_path, duration=185.0
        )

        assert song.status == SongStatus.READY
        assert song.instrumental_path == inst_path
        assert song.vocals_path == voc_path
        assert song.duration == 185.0
        song.ensure_is_ready()  # Não deve lançar exceção

    def test_mark_as_failed(self) -> None:
        song = Song(id="song-123", title="Song Test", artist="Artist Test")
        song.mark_as_failed()
        assert song.status == SongStatus.FAILED
        with pytest.raises(SongNotReadyError):
            song.ensure_is_ready()


class TestPerformanceEntity:
    def test_create_performance(self) -> None:
        now = datetime.now(UTC)
        path = Path("/storage/recordings/rec-001.wav")
        perf = Performance(
            id="perf-001",
            song_id="song-123",
            recording_path=path,
            timestamp=now,
        )
        assert perf.id == "perf-001"
        assert perf.song_id == "song-123"
        assert perf.recording_path == path
        assert perf.timestamp == now
