"""Testes unitários para o adaptador YtDlpDownloaderAdapter utilizando Mocks."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yt_dlp

from karaoke.adapters.downloaders import YtDlpDownloaderAdapter
from karaoke.application.ports import AudioDownloaderPort
from karaoke.domain import AudioDownloadError


class TestYtDlpDownloaderAdapter:
    @pytest.fixture
    def adapter(self) -> YtDlpDownloaderAdapter:
        return YtDlpDownloaderAdapter(audio_format="mp3", sample_rate=44100)

    def test_satisfies_audio_downloader_port_protocol(
        self, adapter: YtDlpDownloaderAdapter
    ) -> None:
        port: AudioDownloaderPort = adapter
        assert port is not None

    @patch("yt_dlp.YoutubeDL")
    def test_download_via_search_query_success(
        self,
        mock_ytdl_class: MagicMock,
        adapter: YtDlpDownloaderAdapter,
        tmp_path: Path,
    ) -> None:
        # Simula a instância do YoutubeDL
        mock_instance = MagicMock()
        mock_ytdl_class.return_value.__enter__.return_value = mock_instance

        mock_instance.extract_info.return_value = {
            "entries": [
                {
                    "id": "video123",
                    "title": "Bohemian Rhapsody",
                    "artist": "Queen",
                    "duration": 354.0,
                }
            ]
        }

        # Simula o arquivo gerado pelo ffmpeg
        expected_audio_file = tmp_path / "video123.mp3"
        expected_audio_file.write_bytes(b"fake_mp3_content")

        result = adapter.download("queen bohemian rhapsody", tmp_path)

        # Valida que usou o prefixo 'ytsearch1:' para pesquisa
        mock_instance.extract_info.assert_called_once_with(
            "ytsearch1:queen bohemian rhapsody", download=True
        )

        assert result.title == "Bohemian Rhapsody"
        assert result.artist == "Queen"
        assert result.duration == 354.0
        assert result.file_path == expected_audio_file

    @patch("yt_dlp.YoutubeDL")
    def test_download_via_direct_url_success(
        self,
        mock_ytdl_class: MagicMock,
        adapter: YtDlpDownloaderAdapter,
        tmp_path: Path,
    ) -> None:
        mock_instance = MagicMock()
        mock_ytdl_class.return_value.__enter__.return_value = mock_instance

        mock_instance.extract_info.return_value = {
            "id": "direct_video",
            "title": "Imagine",
            "uploader": "John Lennon",
            "duration": 183.0,
        }

        expected_audio_file = tmp_path / "direct_video.mp3"
        expected_audio_file.write_bytes(b"fake_mp3_content")

        url = "https://www.youtube.com/watch?v=direct_video"
        result = adapter.download(url, tmp_path)

        # Valida que URLs diretas NÃO recebem o prefixo 'ytsearch1:'
        mock_instance.extract_info.assert_called_once_with(url, download=True)

        assert result.title == "Imagine"
        assert result.artist == "John Lennon"
        assert result.duration == 183.0
        assert result.file_path == expected_audio_file

    def test_empty_query_raises_audio_download_error(
        self, adapter: YtDlpDownloaderAdapter, tmp_path: Path
    ) -> None:
        with pytest.raises(AudioDownloadError, match="não pode ser vazio"):
            adapter.download("   ", tmp_path)

    @patch("yt_dlp.YoutubeDL")
    def test_ytdlp_exception_converted_to_domain_error(
        self,
        mock_ytdl_class: MagicMock,
        adapter: YtDlpDownloaderAdapter,
        tmp_path: Path,
    ) -> None:
        mock_instance = MagicMock()
        mock_ytdl_class.return_value.__enter__.return_value = mock_instance
        mock_instance.extract_info.side_effect = yt_dlp.utils.DownloadError(
            "Video not available"
        )

        with pytest.raises(AudioDownloadError, match="Video not available"):
            adapter.download("video inexistente", tmp_path)

    @patch("yt_dlp.YoutubeDL")
    def test_no_results_raises_audio_download_error(
        self,
        mock_ytdl_class: MagicMock,
        adapter: YtDlpDownloaderAdapter,
        tmp_path: Path,
    ) -> None:
        mock_instance = MagicMock()
        mock_ytdl_class.return_value.__enter__.return_value = mock_instance
        mock_instance.extract_info.return_value = {"entries": []}

        with pytest.raises(AudioDownloadError, match="Nenhum áudio válido"):
            adapter.download("busca sem resultado", tmp_path)

    @patch("yt_dlp.YoutubeDL")
    def test_custom_options_passed_to_ytdlp(
        self, mock_ytdl_class: MagicMock, tmp_path: Path
    ) -> None:
        custom_adapter = YtDlpDownloaderAdapter(
            audio_format="wav", sample_rate=48000, audio_quality="0"
        )

        mock_instance = MagicMock()
        mock_ytdl_class.return_value.__enter__.return_value = mock_instance
        mock_instance.extract_info.return_value = {
            "id": "audio48k",
            "title": "High Quality Audio",
            "duration": 60.0,
        }

        audio_file = tmp_path / "audio48k.wav"
        audio_file.write_bytes(b"wav")

        custom_adapter.download("musica", tmp_path)

        # Obtém o dicionário ydl_opts passado na inicialização do YoutubeDL
        called_opts = mock_ytdl_class.call_args[0][0]
        assert called_opts["postprocessors"][0]["preferredcodec"] == "wav"
        assert called_opts["postprocessor_args"] == ["-ar", "48000"]

    @patch("yt_dlp.YoutubeDL")
    def test_download_via_youtube_search_results_url_extracts_query(
        self,
        mock_ytdl_class: MagicMock,
        adapter: YtDlpDownloaderAdapter,
        tmp_path: Path,
    ) -> None:
        mock_instance = MagicMock()
        mock_ytdl_class.return_value.__enter__.return_value = mock_instance

        mock_instance.extract_info.return_value = {
            "entries": [
                {
                    "id": "search_res_1",
                    "title": "Good Old Fashioned Lover Boy",
                    "artist": "Queen",
                    "duration": 174.0,
                }
            ]
        }

        expected_audio_file = tmp_path / "search_res_1.mp3"
        expected_audio_file.write_bytes(b"mp3_data")

        search_url = (
            "https://www.youtube.com/results?search_query=good+old+fashioned+lover+boy"
        )
        result = adapter.download(search_url, tmp_path)

        # Valida que extraiu o termo e usou 'ytsearch1:'
        mock_instance.extract_info.assert_called_once_with(
            "ytsearch1:good old fashioned lover boy", download=True
        )
        assert result.title == "Good Old Fashioned Lover Boy"
