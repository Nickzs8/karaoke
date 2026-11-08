"""Testes unitários para validação dos contratos das Portas (Protocols)."""

from pathlib import Path
from typing import BinaryIO

from karaoke.application.ports import (
    AudioDownloaderPort,
    AudioSeparatorPort,
    AudioStoragePort,
    DownloadedAudio,
    LyricsProviderPort,
    PerformanceScorerPort,
    PitchExtractorPort,
    SeparatedTracks,
)
from karaoke.domain import (
    LyricsLine,
    PitchCurve,
    PitchPoint,
    Score,
    ScoreResult,
)


class FakeAudioDownloader:
    def download(self, query_or_url: str, output_dir: Path) -> DownloadedAudio:
        return DownloadedAudio(
            file_path=output_dir / "song.mp3",
            title="Fake Song",
            artist="Fake Artist",
            duration=120.0,
        )


class FakeAudioSeparator:
    def separate(self, audio_path: Path, output_dir: Path) -> SeparatedTracks:
        return SeparatedTracks(
            instrumental_path=output_dir / "instrumental.wav",
            vocals_path=output_dir / "vocals.wav",
        )


class FakeLyricsProvider:
    def get_lyrics(
        self, title: str, artist: str | None = None
    ) -> tuple[LyricsLine, ...]:
        return (LyricsLine(start_time=0.0, end_time=2.0, text="Fake Lyrics"),)


class FakePitchExtractor:
    def extract_pitch(self, audio_path: Path) -> PitchCurve:
        return PitchCurve(points=(PitchPoint(timestamp=0.1, frequency_hz=440.0),))


class FakePerformanceScorer:
    def score_performance(
        self, reference_curve: PitchCurve, user_curve: PitchCurve
    ) -> ScoreResult:
        return ScoreResult.calculate(pitch_score=Score(85.0), timing_score=Score(90.0))


class FakeAudioStorage:
    def save_file(
        self, file_data: bytes | BinaryIO, filename: str, subfolder: str
    ) -> Path:
        return Path(f"/storage/{subfolder}/{filename}")

    def get_path(self, filename: str, subfolder: str) -> Path:
        return Path(f"/storage/{subfolder}/{filename}")

    def file_exists(self, filename: str, subfolder: str) -> bool:
        return True

    def delete_file(self, filename: str, subfolder: str) -> bool:
        return True

    def clean_subfolder(self, subfolder: str) -> int:
        return 0


def test_ports_structural_subtyping() -> None:
    """Verifica que as implementações de teste satisfazem os contratos das Portas."""
    downloader: AudioDownloaderPort = FakeAudioDownloader()
    separator: AudioSeparatorPort = FakeAudioSeparator()
    lyrics: LyricsProviderPort = FakeLyricsProvider()
    pitch_extractor: PitchExtractorPort = FakePitchExtractor()
    scorer: PerformanceScorerPort = FakePerformanceScorer()
    storage: AudioStoragePort = FakeAudioStorage()

    downloaded = downloader.download("queen", Path("/tmp"))
    assert downloaded.title == "Fake Song"

    separated = separator.separate(Path("/tmp/audio.mp3"), Path("/tmp"))
    assert separated.instrumental_path.name == "instrumental.wav"

    lyric_lines = lyrics.get_lyrics("queen")
    assert len(lyric_lines) == 1

    curve = pitch_extractor.extract_pitch(Path("/tmp/vocals.wav"))
    assert len(curve.points) == 1

    score_result = scorer.score_performance(curve, curve)
    assert score_result.total_score.value > 0

    saved_path = storage.save_file(b"content", "test.wav", "raw")
    assert str(saved_path) == "/storage/raw/test.wav"
    assert storage.file_exists("test.wav", "raw") is True
