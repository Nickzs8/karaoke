"""Testes unitários da API FastAPI: endpoints de músicas e performances."""

from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient

from karaoke.domain import (
    LyricsLine,
    LyricsNotFoundError,
    Score,
    ScoreResult,
    Song,
    SongNotFoundError,
    SongNotReadyError,
    SongStatus,
)
from karaoke.infrastructure import AppConfig, AppContainer
from karaoke.presentation.api import create_app


@pytest.fixture
def mock_container(tmp_path: Path) -> AppContainer:
    """Cria um container com adaptadores mockados e storage temporário."""
    config = AppConfig(
        base_dir=tmp_path,
        storage_dir=tmp_path / "storage",
        device="cpu",
    )
    container = AppContainer(config=config)

    # Substitui os use cases por mocks para isolar a camada de apresentação
    container.prepare_song = MagicMock()
    container.list_songs = MagicMock()
    container.get_lyrics = MagicMock()
    container.evaluate_performance = MagicMock()

    return container


@pytest.fixture
def client(mock_container: AppContainer) -> TestClient:
    """TestClient configurado com o mock_container injetado."""
    app = create_app(container=mock_container)
    return TestClient(app)


class TestHealthCheck:
    def test_health_check_returns_ok(self, client: TestClient) -> None:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_root_serves_frontend_html(self, client: TestClient) -> None:
        response = client.get("/")
        assert response.status_code == 200
        assert "Karaokê" in response.text
        assert "text/html" in response.headers.get("content-type", "")


class TestPrepareSongEndpoint:
    def test_prepare_song_via_json(
        self, client: TestClient, mock_container: AppContainer
    ) -> None:
        mock_song = Song(
            id="song_abc123",
            title="Bohemian Rhapsody",
            artist="Queen",
            duration=354.0,
            status=SongStatus.READY,
            instrumental_path=Path("storage/processed/inst.wav"),
            vocals_path=Path("storage/processed/voc.wav"),
        )
        mock_container.prepare_song.execute.return_value = mock_song

        payload = {
            "query_or_url": "Queen Bohemian Rhapsody",
            "title": "Bohemian Rhapsody",
            "artist": "Queen",
        }
        response = client.post("/api/songs/prepare", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "song_abc123"
        assert data["title"] == "Bohemian Rhapsody"
        assert data["status"] == "READY"
        assert data["instrumental_url"] == "/static/audio/processed/inst.wav"
        assert data["vocals_url"] == "/static/audio/processed/voc.wav"

        mock_container.prepare_song.execute.assert_called_once_with(
            query_or_url="Queen Bohemian Rhapsody",
            local_file_path=None,
            title="Bohemian Rhapsody",
            artist="Queen",
        )

    def test_prepare_song_via_file_upload(
        self, client: TestClient, mock_container: AppContainer
    ) -> None:
        mock_song = Song(
            id="song_upload_99",
            title="Custom Track",
            artist="Indie Artist",
            duration=120.0,
            status=SongStatus.READY,
        )
        mock_container.prepare_song.execute.return_value = mock_song

        file_content = b"fake audio content"
        files = {"file": ("my_song.mp3", file_content, "audio/mpeg")}
        data = {"title": "Custom Track", "artist": "Indie Artist"}

        response = client.post("/api/songs/prepare", data=data, files=files)

        assert response.status_code == 201
        assert response.json()["id"] == "song_upload_99"
        mock_container.prepare_song.execute.assert_called_once()

    def test_prepare_song_empty_request_returns_bad_request(
        self, client: TestClient
    ) -> None:
        response = client.post("/api/songs/prepare", json={"query_or_url": "   "})
        assert response.status_code == 400
        assert "não pode ser vazio" in response.json()["detail"]


class TestListSongsEndpoint:
    def test_list_songs_default_only_ready(
        self, client: TestClient, mock_container: AppContainer
    ) -> None:
        mock_item = MagicMock()
        mock_item.id = "s1"
        mock_item.title = "Song One"
        mock_item.artist = "Artist One"
        mock_item.duration = 200.0
        mock_item.status = "READY"
        mock_item.instrumental_url = "/static/audio/processed/inst.wav"
        mock_item.vocals_url = "/static/audio/processed/voc.wav"

        mock_container.list_songs.execute.return_value = [mock_item]

        response = client.get("/api/songs")

        assert response.status_code == 200
        items = response.json()
        assert len(items) == 1
        assert items[0]["id"] == "s1"
        assert items[0]["instrumental_url"] == "/static/audio/processed/inst.wav"
        mock_container.list_songs.execute.assert_called_once_with(only_ready=True)

    def test_list_songs_include_all(
        self, client: TestClient, mock_container: AppContainer
    ) -> None:
        mock_container.list_songs.execute.return_value = []
        response = client.get("/api/songs?only_ready=false")

        assert response.status_code == 200
        mock_container.list_songs.execute.assert_called_once_with(only_ready=False)


class TestGetLyricsEndpoint:
    def test_get_lyrics_success(
        self, client: TestClient, mock_container: AppContainer
    ) -> None:
        mock_lines = (
            LyricsLine(start_time=1.0, end_time=4.0, text="Primeiro verso"),
            LyricsLine(start_time=4.5, end_time=8.0, text="Segundo verso"),
        )
        mock_container.get_lyrics.execute.return_value = mock_lines

        response = client.get("/api/songs/song_123/lyrics")

        assert response.status_code == 200
        data = response.json()
        assert data["song_id"] == "song_123"
        assert len(data["lines"]) == 2
        assert data["lines"][0]["text"] == "Primeiro verso"
        assert data["lines"][0]["start_time"] == 1.0
        assert data["lines"][0]["end_time"] == 4.0

    def test_get_lyrics_song_not_found(
        self, client: TestClient, mock_container: AppContainer
    ) -> None:
        mock_container.get_lyrics.execute.side_effect = SongNotFoundError(
            "Música não encontrada."
        )

        response = client.get("/api/songs/inexistente/lyrics")

        assert response.status_code == 404
        assert response.json()["detail"] == "Música não encontrada."

    def test_get_lyrics_not_found(
        self, client: TestClient, mock_container: AppContainer
    ) -> None:
        mock_container.get_lyrics.execute.side_effect = LyricsNotFoundError(
            "Letra sincronizada não encontrada."
        )

        response = client.get("/api/songs/sem_letra/lyrics")

        assert response.status_code == 404
        assert "Letra sincronizada não encontrada" in response.json()["detail"]


class TestEvaluatePerformanceEndpoint:
    def test_evaluate_performance_via_upload(
        self, client: TestClient, mock_container: AppContainer
    ) -> None:
        mock_score = ScoreResult(
            pitch_score=Score(88.0),
            timing_score=Score(92.0),
            total_score=Score(89.2),
            details={"mean_cents_error": 12.5, "octave_shift": 0},
        )
        mock_container.evaluate_performance.execute.return_value = mock_score

        files = {"audio_file": ("mic.wav", b"user singing audio", "audio/wav")}
        data = {"song_id": "song_123"}

        response = client.post("/api/performances/evaluate", data=data, files=files)

        assert response.status_code == 200
        data_res = response.json()
        assert data_res["total_score"] == 89.2
        assert data_res["pitch_score"] == 88.0
        assert data_res["timing_score"] == 92.0
        assert data_res["details"]["mean_cents_error"] == 12.5

    def test_evaluate_performance_via_json(
        self, client: TestClient, mock_container: AppContainer
    ) -> None:
        mock_score = ScoreResult(
            pitch_score=Score(95.0),
            timing_score=Score(90.0),
            total_score=Score(93.5),
        )
        mock_container.evaluate_performance.execute.return_value = mock_score

        payload = {
            "song_id": "song_123",
            "recording_path": "/tmp/rec.wav",
        }
        response = client.post("/api/performances/evaluate", json=payload)

        assert response.status_code == 200
        assert response.json()["total_score"] == 93.5

    def test_evaluate_performance_missing_song_id(self, client: TestClient) -> None:
        files = {"audio_file": ("mic.wav", b"singing", "audio/wav")}
        response = client.post("/api/performances/evaluate", data={}, files=files)
        assert response.status_code == 400
        assert "song_id" in response.json()["detail"]

    def test_evaluate_performance_song_not_ready_returns_409(
        self, client: TestClient, mock_container: AppContainer
    ) -> None:
        mock_container.evaluate_performance.execute.side_effect = SongNotReadyError(
            "Faixa ainda em processamento."
        )

        files = {"audio_file": ("mic.wav", b"audio", "audio/wav")}
        data = {"song_id": "song_not_ready"}

        response = client.post("/api/performances/evaluate", data=data, files=files)

        assert response.status_code == 409
        assert "Faixa ainda em processamento" in response.json()["detail"]


@pytest.mark.anyio
async def test_api_with_httpx_async_client(mock_container: AppContainer) -> None:
    """Valida o uso com httpx.AsyncClient conforme critério de aceite."""
    app = create_app(container=mock_container)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        response = await client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
