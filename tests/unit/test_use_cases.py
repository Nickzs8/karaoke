"""Testes unitários para os casos de uso da camada de Aplicação."""

import json
from pathlib import Path
from typing import BinaryIO

import pytest

from karaoke.adapters.audio import DtwPerformanceScorerAdapter
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
from karaoke.application.use_cases import (
    EvaluatePerformanceUseCase,
    GetLyricsUseCase,
    ListSongsUseCase,
    PrepareSongUseCase,
)
from karaoke.domain import (
    AudioSeparationError,
    InvalidAudioFormatError,
    InvalidStoragePathError,
    LyricsLine,
    LyricsNotFoundError,
    PitchCurve,
    PitchPoint,
    Score,
    ScoreResult,
    Song,
    SongNotFoundError,
    SongNotReadyError,
    SongStatus,
)

# Fakes das Portas para Testes Unitários Isolados


class FakeDownloader(AudioDownloaderPort):
    def __init__(self, output_file: Path) -> None:
        self.output_file = output_file
        self.download_called = False

    def download(self, query_or_url: str, output_dir: Path) -> DownloadedAudio:
        self.download_called = True
        self.output_file.write_bytes(b"audio_bytes")
        return DownloadedAudio(
            file_path=self.output_file,
            title="Bohemian Rhapsody",
            artist="Queen",
            duration=354.0,
        )


class FakeSeparator(AudioSeparatorPort):
    def __init__(
        self,
        instrumental_path: Path,
        vocals_path: Path,
        should_fail: bool = False,
    ) -> None:
        self.instrumental_path = instrumental_path
        self.vocals_path = vocals_path
        self.should_fail = should_fail

    def separate(self, audio_path: Path, output_dir: Path) -> SeparatedTracks:
        if self.should_fail:
            raise AudioSeparationError("Falha simulada na separação de faixas.")
        self.instrumental_path.write_bytes(b"instrumental_data")
        self.vocals_path.write_bytes(b"vocals_data")
        return SeparatedTracks(
            instrumental_path=self.instrumental_path,
            vocals_path=self.vocals_path,
        )


class FakeStorage(AudioStoragePort):
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def save_file(
        self, file_data: bytes | BinaryIO, filename: str, subfolder: str
    ) -> Path:
        target = self.base_dir / subfolder / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(file_data, bytes):
            target.write_bytes(file_data)
        else:
            target.write_bytes(file_data.read())
        return target

    def get_path(self, filename: str, subfolder: str) -> Path:
        target = self.base_dir / subfolder / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def file_exists(self, filename: str, subfolder: str) -> bool:
        return (self.base_dir / subfolder / filename).is_file()

    def delete_file(self, filename: str, subfolder: str) -> bool:
        p = self.base_dir / subfolder / filename
        if p.is_file():
            p.unlink()
            return True
        return False

    def list_files(self, subfolder: str) -> list[str]:
        target = self.base_dir / subfolder
        if not target.is_dir():
            return []
        return [
            p.name
            for p in sorted(target.iterdir())
            if p.is_file() and p.name != ".gitkeep"
        ]

    def clean_subfolder(self, subfolder: str) -> int:
        return 0


class FakeLyricsProvider(LyricsProviderPort):
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail

    def get_lyrics(
        self, title: str, artist: str | None = None
    ) -> tuple[LyricsLine, ...]:
        if self.should_fail:
            raise RuntimeError("API de letras offline")
        return (
            LyricsLine(start_time=1.0, end_time=3.5, text="Mama, just killed a man"),
            LyricsLine(start_time=4.0, end_time=6.0, text="Put a gun against his head"),
        )


class FakePitchExtractor(PitchExtractorPort):
    def __init__(self, mapping: dict[Path, PitchCurve] | None = None) -> None:
        self.mapping = {
            Path(p).resolve(): curve for p, curve in (mapping or {}).items()
        }

    def register_curve(self, path: Path, curve: PitchCurve) -> None:
        self.mapping[Path(path).resolve()] = curve

    def extract_pitch(self, audio_path: Path) -> PitchCurve:
        resolved = Path(audio_path).resolve()
        if resolved in self.mapping:
            return self.mapping[resolved]
        return PitchCurve(
            points=(
                PitchPoint(timestamp=0.1, frequency_hz=440.0, midi_note=69.0),
                PitchPoint(timestamp=0.2, frequency_hz=440.0, midi_note=69.0),
            )
        )


class FakePerformanceScorer(PerformanceScorerPort):
    def score_performance(
        self, reference_curve: PitchCurve, user_curve: PitchCurve
    ) -> ScoreResult:
        return ScoreResult.calculate(
            pitch_score=Score(95.0),
            timing_score=Score(90.0),
            details={"aligned_points": 2},
        )


# Testes do PrepareSongUseCase


class TestPrepareSongUseCase:
    @pytest.fixture
    def setup_use_case(self, tmp_path: Path):
        storage = FakeStorage(tmp_path)
        download_target = tmp_path / "raw" / "downloaded.mp3"
        download_target.parent.mkdir(parents=True, exist_ok=True)
        downloader = FakeDownloader(download_target)

        inst_path = tmp_path / "processed" / "inst.wav"
        voc_path = tmp_path / "processed" / "voc.wav"
        separator = FakeSeparator(inst_path, voc_path)

        lyrics_provider = FakeLyricsProvider()

        use_case = PrepareSongUseCase(
            downloader=downloader,
            separator=separator,
            storage=storage,
            lyrics_provider=lyrics_provider,
        )
        return {
            "use_case": use_case,
            "downloader": downloader,
            "separator": separator,
            "storage": storage,
            "tmp_path": tmp_path,
        }

    def test_prepare_song_from_search_query_success(self, setup_use_case) -> None:
        use_case: PrepareSongUseCase = setup_use_case["use_case"]
        downloader: FakeDownloader = setup_use_case["downloader"]
        storage: FakeStorage = setup_use_case["storage"]

        song = use_case.execute(query_or_url="Queen Bohemian Rhapsody")

        assert downloader.download_called is True
        assert song.status == SongStatus.READY
        assert song.title == "Bohemian Rhapsody"
        assert song.artist == "Queen"
        assert song.duration == 354.0
        assert song.instrumental_path is not None
        assert song.vocals_path is not None

        # Garante que os metadados JSON foram salvos no disco em storage/processed/
        metadata_file = storage.get_path(f"{song.id}.json", "processed")
        assert metadata_file.is_file() is True
        data = json.loads(metadata_file.read_text(encoding="utf-8"))
        assert data["id"] == song.id
        assert data["status"] == "READY"

    def test_prepare_song_from_local_file_success(self, setup_use_case) -> None:
        use_case: PrepareSongUseCase = setup_use_case["use_case"]
        downloader: FakeDownloader = setup_use_case["downloader"]
        tmp_path: Path = setup_use_case["tmp_path"]

        local_audio = tmp_path / "my_song.mp3"
        local_audio.write_bytes(b"local_audio_content")

        song = use_case.execute(
            local_file_path=local_audio,
            title="Custom Title",
            artist="Custom Artist",
        )

        assert downloader.download_called is False
        assert song.status == SongStatus.READY
        assert song.title == "Custom Title"
        assert song.artist == "Custom Artist"

    def test_prepare_song_fails_without_input(self, setup_use_case) -> None:
        use_case: PrepareSongUseCase = setup_use_case["use_case"]
        with pytest.raises(InvalidAudioFormatError):
            use_case.execute()

    def test_prepare_song_fails_when_local_file_not_found(self, setup_use_case) -> None:
        use_case: PrepareSongUseCase = setup_use_case["use_case"]
        tmp_path: Path = setup_use_case["tmp_path"]

        missing_file = tmp_path / "nao_existe.mp3"
        with pytest.raises(InvalidStoragePathError):
            use_case.execute(local_file_path=missing_file)

    def test_prepare_song_marks_as_failed_when_separation_fails(
        self, setup_use_case
    ) -> None:
        setup_use_case["separator"].should_fail = True
        use_case: PrepareSongUseCase = setup_use_case["use_case"]
        storage: FakeStorage = setup_use_case["storage"]

        with pytest.raises(AudioSeparationError):
            use_case.execute(query_or_url="Queen Bohemian Rhapsody")

        # Verifica se o arquivo JSON registrou o status FAILED
        files = storage.list_files("processed")
        json_files = [f for f in files if f.endswith(".json")]
        assert len(json_files) == 1
        content = json.loads(storage.get_path(json_files[0], "processed").read_text())
        assert content["status"] == "FAILED"

    def test_prepare_song_succeeds_even_when_lyrics_fail(self, setup_use_case) -> None:
        use_case: PrepareSongUseCase = setup_use_case["use_case"]
        use_case.lyrics_provider = FakeLyricsProvider(should_fail=True)

        song = use_case.execute(query_or_url="Queen Bohemian Rhapsody")
        assert song.status == SongStatus.READY


# Testes do EvaluatePerformanceUseCase


class TestEvaluatePerformanceUseCase:
    @pytest.fixture
    def setup_evaluate(self, tmp_path: Path):
        storage = FakeStorage(tmp_path)
        pitch_extractor = FakePitchExtractor()
        scorer = FakePerformanceScorer()

        voc_path = tmp_path / "processed" / "vocals.wav"
        voc_path.parent.mkdir(parents=True, exist_ok=True)
        voc_path.write_bytes(b"vocals")

        inst_path = tmp_path / "processed" / "inst.wav"
        inst_path.write_bytes(b"instrumental")

        ready_song = Song(
            id="song-1",
            title="Bohemian Rhapsody",
            artist="Queen",
            duration=120.0,
        )
        ready_song.mark_as_ready(instrumental_path=inst_path, vocals_path=voc_path)

        # Salva o arquivo JSON de metadados no storage
        metadata = {
            "id": ready_song.id,
            "title": ready_song.title,
            "artist": ready_song.artist,
            "duration": ready_song.duration,
            "status": ready_song.status.value,
            "raw_audio_path": None,
            "instrumental_path": str(ready_song.instrumental_path),
            "vocals_path": str(ready_song.vocals_path),
            "created_at": ready_song.created_at.isoformat(),
        }
        storage.save_file(
            file_data=json.dumps(metadata).encode("utf-8"),
            filename=f"{ready_song.id}.json",
            subfolder="processed",
        )

        user_recording = tmp_path / "recordings" / "user_rec.wav"
        user_recording.parent.mkdir(parents=True, exist_ok=True)
        user_recording.write_bytes(b"user_voice")

        use_case = EvaluatePerformanceUseCase(
            storage=storage,
            pitch_extractor=pitch_extractor,
            scorer=scorer,
        )

        return {
            "use_case": use_case,
            "storage": storage,
            "ready_song": ready_song,
            "user_recording": user_recording,
            "tmp_path": tmp_path,
        }

    def test_evaluate_performance_success(self, setup_evaluate) -> None:
        use_case: EvaluatePerformanceUseCase = setup_evaluate["use_case"]
        user_recording: Path = setup_evaluate["user_recording"]

        result = use_case.execute(song_id="song-1", recording_path=user_recording)

        assert isinstance(result, ScoreResult)
        assert result.total_score.value > 0.0
        assert result.pitch_score.value == 95.0
        assert result.timing_score.value == 90.0

    def test_evaluate_performance_raises_song_not_found(self, setup_evaluate) -> None:
        use_case: EvaluatePerformanceUseCase = setup_evaluate["use_case"]
        user_recording: Path = setup_evaluate["user_recording"]

        with pytest.raises(SongNotFoundError):
            use_case.execute(song_id="inexistente", recording_path=user_recording)

    def test_evaluate_performance_raises_when_song_not_ready(
        self, setup_evaluate
    ) -> None:
        use_case: EvaluatePerformanceUseCase = setup_evaluate["use_case"]
        storage: FakeStorage = setup_evaluate["storage"]
        user_recording: Path = setup_evaluate["user_recording"]

        # Cria uma música com status PENDING em JSON
        pending_metadata = {
            "id": "song-pending",
            "title": "Pending",
            "artist": "Artist",
            "duration": 0.0,
            "status": "PENDING",
            "created_at": "2026-11-08T00:00:00Z",
        }
        storage.save_file(
            file_data=json.dumps(pending_metadata).encode("utf-8"),
            filename="song-pending.json",
            subfolder="processed",
        )

        with pytest.raises(SongNotReadyError):
            use_case.execute(song_id="song-pending", recording_path=user_recording)

    def test_evaluate_performance_raises_when_vocals_file_missing(
        self, setup_evaluate
    ) -> None:
        use_case: EvaluatePerformanceUseCase = setup_evaluate["use_case"]
        ready_song: Song = setup_evaluate["ready_song"]
        user_recording: Path = setup_evaluate["user_recording"]

        # Deleta o arquivo físico de vocal
        if ready_song.vocals_path and ready_song.vocals_path.is_file():
            ready_song.vocals_path.unlink()

        with pytest.raises(InvalidStoragePathError):
            use_case.execute(song_id=ready_song.id, recording_path=user_recording)

    def test_evaluate_performance_raises_when_recording_missing(
        self, setup_evaluate
    ) -> None:
        use_case: EvaluatePerformanceUseCase = setup_evaluate["use_case"]
        tmp_path: Path = setup_evaluate["tmp_path"]

        missing_rec = tmp_path / "rec_fantasma.wav"
        with pytest.raises(InvalidStoragePathError):
            use_case.execute(song_id="song-1", recording_path=missing_rec)

    def test_evaluate_performance_compares_user_recording_with_song_returns_score(
        self, setup_evaluate
    ) -> None:
        """Compara a gravação do usuário com a música e retorna pontuação exata."""
        storage: FakeStorage = setup_evaluate["storage"]
        ready_song: Song = setup_evaluate["ready_song"]
        tmp_path: Path = setup_evaluate["tmp_path"]

        # Melodia de referência da música (5 notas na escala C4..G4)
        ref_points = (
            PitchPoint(timestamp=0.0, frequency_hz=261.63, midi_note=60.0),
            PitchPoint(timestamp=0.5, frequency_hz=293.66, midi_note=62.0),
            PitchPoint(timestamp=1.0, frequency_hz=329.63, midi_note=64.0),
            PitchPoint(timestamp=1.5, frequency_hz=349.23, midi_note=65.0),
            PitchPoint(timestamp=2.0, frequency_hz=392.00, midi_note=67.0),
        )
        ref_curve = PitchCurve(points=ref_points)

        # Gravação real simulada do usuário:
        # - Latência de buffer de 150ms
        # - Desvio de afinação de 150 cents (+1.5 semitons) apenas na 3ª nota
        user_recording_file = tmp_path / "recordings" / "user_performance.wav"
        user_recording_file.parent.mkdir(parents=True, exist_ok=True)
        user_recording_file.write_bytes(b"user_audio_stream")

        user_points = (
            PitchPoint(timestamp=0.15, frequency_hz=261.63, midi_note=60.0),
            PitchPoint(timestamp=0.65, frequency_hz=293.66, midi_note=62.0),
            PitchPoint(timestamp=1.15, frequency_hz=359.80, midi_note=65.5),
            PitchPoint(timestamp=1.65, frequency_hz=349.23, midi_note=65.0),
            PitchPoint(timestamp=2.15, frequency_hz=392.00, midi_note=67.0),
        )
        user_curve = PitchCurve(points=user_points)

        assert ready_song.vocals_path is not None
        extractor = FakePitchExtractor(
            mapping={
                ready_song.vocals_path: ref_curve,
                user_recording_file: user_curve,
            }
        )
        scorer = DtwPerformanceScorerAdapter(pitch_weight=0.7, timing_weight=0.3)

        use_case = EvaluatePerformanceUseCase(
            storage=storage,
            pitch_extractor=extractor,
            scorer=scorer,
        )

        result = use_case.execute(
            song_id=ready_song.id,
            recording_path=user_recording_file,
        )

        # 4 notas perfeitas (100.0) e 1 nota com 150 cents de erro (66.67) -> 93.33
        assert result.pitch_score.value == 93.33
        # Latência de 150ms compensada dentro da tolerância rítmica de 500ms -> 100.0
        assert result.timing_score.value == 100.0
        # Pontuação total ponderada: 93.33 * 0.7 + 100.0 * 0.3 = 95.33
        assert result.total_score.value == 95.33
        # Detalhes e métricas consolidadas
        assert result.details["coverage_ratio"] == 100.0
        assert result.details["mean_pitch_error_cents"] == 30.0
        assert result.details["max_pitch_error_cents"] == 150.0
        assert result.details["global_latency_seconds"] == 0.15
        assert result.details["reference_points_count"] == 5
        assert result.details["user_points_count"] == 5

    def test_evaluate_performance_partial_recording_scales_coverage_score(
        self, setup_evaluate
    ) -> None:
        """Garante que gravação parcial escala nota proporcional à cobertura."""
        storage: FakeStorage = setup_evaluate["storage"]
        ready_song: Song = setup_evaluate["ready_song"]
        tmp_path: Path = setup_evaluate["tmp_path"]

        # Música de referência com 5 notas espaçadas
        ref_points = (
            PitchPoint(timestamp=0.0, frequency_hz=261.63, midi_note=60.0),
            PitchPoint(timestamp=0.5, frequency_hz=293.66, midi_note=62.0),
            PitchPoint(timestamp=10.0, frequency_hz=329.63, midi_note=64.0),
            PitchPoint(timestamp=10.5, frequency_hz=349.23, midi_note=65.0),
            PitchPoint(timestamp=11.0, frequency_hz=392.00, midi_note=67.0),
        )
        ref_curve = PitchCurve(points=ref_points)

        # Gravação de usuário com apenas os primeiros 2 trechos (40% de cobertura)
        short_rec_file = tmp_path / "recordings" / "user_short.wav"
        short_rec_file.parent.mkdir(parents=True, exist_ok=True)
        short_rec_file.write_bytes(b"short_audio")

        user_curve = PitchCurve(
            points=(
                PitchPoint(timestamp=0.0, frequency_hz=261.63, midi_note=60.0),
                PitchPoint(timestamp=0.5, frequency_hz=293.66, midi_note=62.0),
            )
        )

        assert ready_song.vocals_path is not None
        extractor = FakePitchExtractor(
            mapping={
                ready_song.vocals_path: ref_curve,
                short_rec_file: user_curve,
            }
        )
        scorer = DtwPerformanceScorerAdapter(pitch_weight=0.7, timing_weight=0.3)

        use_case = EvaluatePerformanceUseCase(
            storage=storage,
            pitch_extractor=extractor,
            scorer=scorer,
        )

        result = use_case.execute(
            song_id=ready_song.id,
            recording_path=short_rec_file,
        )

        assert result.pitch_score.value == 100.0
        assert result.timing_score.value == 100.0
        assert result.details["coverage_ratio"] == 40.0
        # 100.0 total bruto * 0.40 cobertura = 40.0
        assert result.total_score.value == 40.0


# Testes do ListSongsUseCase


class TestListSongsUseCase:
    @pytest.fixture
    def setup_catalog(self, tmp_path: Path):
        storage = FakeStorage(tmp_path)

        def save_meta(s_id: str, status: str) -> None:
            data = {
                "id": s_id,
                "title": f"Title {s_id}",
                "artist": "Artist Test",
                "duration": 180.0,
                "status": status,
                "instrumental_path": str(tmp_path / "processed" / f"{s_id}_inst.wav"),
                "vocals_path": str(tmp_path / "processed" / f"{s_id}_voc.wav"),
                "created_at": "2026-11-08T00:00:00Z",
            }
            storage.save_file(
                file_data=json.dumps(data).encode("utf-8"),
                filename=f"{s_id}.json",
                subfolder="processed",
            )

        # Salva 3 músicas: 1 READY, 1 PROCESSING, 1 FAILED
        save_meta("s1", "READY")
        save_meta("s2", "PROCESSING")
        save_meta("s3", "FAILED")

        use_case = ListSongsUseCase(
            storage=storage,
            base_audio_url="/api/v1/audio",
        )

        return {"use_case": use_case, "storage": storage}

    def test_list_songs_returns_only_ready_by_default(self, setup_catalog) -> None:
        use_case: ListSongsUseCase = setup_catalog["use_case"]

        items = use_case.execute(only_ready=True)

        assert len(items) == 1
        assert items[0].id == "s1"
        assert items[0].status == "READY"
        assert items[0].instrumental_url == "/api/v1/audio/processed/s1_inst.wav"
        assert items[0].vocals_url == "/api/v1/audio/processed/s1_voc.wav"

    def test_list_songs_can_return_all_songs(self, setup_catalog) -> None:
        use_case: ListSongsUseCase = setup_catalog["use_case"]

        items = use_case.execute(only_ready=False)

        assert len(items) == 3
        statuses = {item.status for item in items}
        assert statuses == {"READY", "PROCESSING", "FAILED"}

    def test_list_songs_empty_catalog(self, tmp_path: Path) -> None:
        empty_storage = FakeStorage(tmp_path / "empty")
        use_case = ListSongsUseCase(storage=empty_storage)

        items = use_case.execute()
        assert items == []


class TestGetLyricsUseCase:
    def test_get_lyrics_success(self, tmp_path: Path) -> None:
        storage = FakeStorage(tmp_path)
        # Salva metadados da música
        storage.save_file(b'{"id": "song_123"}', "song_123.json", "processed")
        # Salva arquivo .lrc
        lrc_text = (
            "[00:05.50]Primeira linha de teste\n"
            "[00:10.00]Segunda linha de teste\n"
            "[00:15.00]\n"
        )
        storage.save_file(lrc_text.encode("utf-8"), "song_123.lrc", "lyrics")

        use_case = GetLyricsUseCase(storage=storage)
        lines = use_case.execute("song_123")

        assert len(lines) == 2
        assert lines[0].text == "Primeira linha de teste"
        assert lines[0].start_time == 5.5
        assert lines[0].end_time == 10.0
        assert lines[1].text == "Segunda linha de teste"
        assert lines[1].start_time == 10.0
        assert lines[1].end_time == 15.0

    def test_get_lyrics_song_not_found(self, tmp_path: Path) -> None:
        storage = FakeStorage(tmp_path)
        use_case = GetLyricsUseCase(storage=storage)

        with pytest.raises(SongNotFoundError, match="não encontrada no catálogo"):
            use_case.execute("song_inexistente")

    def test_get_lyrics_lyrics_file_not_found(self, tmp_path: Path) -> None:
        storage = FakeStorage(tmp_path)
        storage.save_file(
            b'{"id": "song_sem_letra"}', "song_sem_letra.json", "processed"
        )

        use_case = GetLyricsUseCase(storage=storage)

        with pytest.raises(
            LyricsNotFoundError, match="Letra sincronizada não encontrada"
        ):
            use_case.execute("song_sem_letra")

    def test_estimate_offset_without_detector(self, tmp_path: Path) -> None:
        storage = FakeStorage(tmp_path)
        use_case = GetLyricsUseCase(storage=storage)
        assert use_case.estimate_offset("song_123", 0.5) == 0.0

    def test_estimate_offset_with_detector_success(self, tmp_path: Path) -> None:
        storage = FakeStorage(tmp_path)
        vocals_file = tmp_path / "vocals.wav"
        vocals_file.write_bytes(b"dummy wav data")

        meta = f'{{"id": "song_123", "vocals_path": "{vocals_file}"}}'
        storage.save_file(meta.encode("utf-8"), "song_123.json", "processed")

        class MockOnsetDetector:
            def detect_onset(self, audio_path: Path) -> float | None:
                return 5.4

        use_case = GetLyricsUseCase(storage=storage, onset_detector=MockOnsetDetector())
        offset = use_case.estimate_offset("song_123", first_lyric_start=0.5)
        assert offset == 4.9
