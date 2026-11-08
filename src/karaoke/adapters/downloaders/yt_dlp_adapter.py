"""Adaptador de Download de Áudio: YtDlpDownloaderAdapter."""

from pathlib import Path
from typing import Any

import yt_dlp

from karaoke.application.ports import AudioDownloaderPort, DownloadedAudio
from karaoke.domain import AudioDownloadError


class YtDlpDownloaderAdapter(AudioDownloaderPort):
    """Implementa AudioDownloaderPort utilizando a biblioteca yt-dlp.

    Segue estritamente o princípio da responsabilidade única (SRP do SOLID),
    compondo métodos curtos e especializados para cada etapa do download.
    """

    def __init__(
        self,
        audio_format: str = "mp3",
        sample_rate: int = 44100,
        audio_quality: str = "320",
    ) -> None:
        self.audio_format = audio_format.lower()
        self.sample_rate = sample_rate
        self.audio_quality = audio_quality

    def download(self, query_or_url: str, output_dir: Path) -> DownloadedAudio:
        """Orquestra o download completo de áudio."""
        target = self._prepare_target(query_or_url)
        target_dir = self._ensure_output_dir(output_dir)
        ydl_opts = self._build_ydl_options(target_dir)

        raw_info = self._execute_download(target, ydl_opts, query_or_url)
        entry = self._extract_entry(raw_info, query_or_url)

        video_id = entry.get("id") or "audio"
        file_path = self._find_downloaded_file(target_dir, video_id)

        return self._create_downloaded_audio(entry, file_path)

    def _prepare_target(self, query_or_url: str) -> str:
        """Valida e formata o alvo da busca (URL direta ou termo de pesquisa)."""
        clean_query = query_or_url.strip()
        if not clean_query:
            raise AudioDownloadError("O termo de busca ou URL não pode ser vazio.")

        if clean_query.startswith(("http://", "https://", "www.")):
            return clean_query
        return f"ytsearch1:{clean_query}"

    def _ensure_output_dir(self, output_dir: Path) -> Path:
        """Resolve o diretório de destino e garante sua criação no disco."""
        target_dir = Path(output_dir).resolve()
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir

    def _build_ydl_options(self, target_dir: Path) -> dict[str, Any]:
        """Constrói as opções de configuração do yt-dlp e pós-processador FFmpeg."""
        return {
            "format": "bestaudio/best",
            "outtmpl": str(target_dir / "%(id)s.%(ext)s"),
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": self.audio_format,
                    "preferredquality": self.audio_quality,
                }
            ],
            "postprocessor_args": [
                "-ar",
                str(self.sample_rate),
            ],
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
        }

    def _execute_download(
        self,
        target: str,
        ydl_opts: dict[str, Any],
        original_query: str,
    ) -> dict[str, Any]:
        """Executa a chamada ao yt-dlp capturando e convertendo exceções externas."""
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(target, download=True)
                if not info:
                    raise AudioDownloadError(
                        f"Nenhum resultado encontrado para '{original_query}'."
                    )
                return info
        except AudioDownloadError:
            raise
        except Exception as exc:
            raise AudioDownloadError(
                f"Erro durante o download com yt-dlp para '{original_query}': {exc}"
            ) from exc

    def _extract_entry(
        self,
        info: dict[str, Any],
        original_query: str,
    ) -> dict[str, Any]:
        """Extrai o registro principal de metadados a partir do resultado do yt-dlp."""
        if "entries" in info:
            if not info["entries"]:
                raise AudioDownloadError(
                    f"Nenhum áudio válido encontrado para '{original_query}'."
                )
            return info["entries"][0]
        return info

    def _find_downloaded_file(self, target_dir: Path, video_id: str) -> Path:
        """Localiza o arquivo de áudio convertido gerado no diretório de destino."""
        expected_file = target_dir / f"{video_id}.{self.audio_format}"
        if expected_file.is_file():
            return expected_file

        matching_files = list(target_dir.glob(f"{video_id}.*"))
        if matching_files:
            return matching_files[0]

        raise AudioDownloadError(
            f"Arquivo processado não foi encontrado: {expected_file}"
        )

    def _create_downloaded_audio(
        self,
        entry: dict[str, Any],
        file_path: Path,
    ) -> DownloadedAudio:
        """Mapeia os metadados do yt-dlp para o DTO de aplicação DownloadedAudio."""
        title = entry.get("title") or "Título Desconhecido"
        artist = (
            entry.get("artist")
            or entry.get("creator")
            or entry.get("uploader")
            or entry.get("channel")
            or "Artista Desconhecido"
        )
        duration = float(entry.get("duration") or 0.0)

        return DownloadedAudio(
            file_path=file_path,
            title=title,
            artist=artist,
            duration=duration,
        )
