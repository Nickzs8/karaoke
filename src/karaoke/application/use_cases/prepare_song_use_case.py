"""Caso de Uso: PrepareSongUseCase."""

import json
import uuid
from pathlib import Path

from karaoke.application.ports import (
    AudioDownloaderPort,
    AudioSeparatorPort,
    AudioStoragePort,
    DownloadedAudio,
    LyricsProviderPort,
    SeparatedTracks,
)
from karaoke.domain import (
    InvalidAudioFormatError,
    InvalidStoragePathError,
    LyricsLine,
    Song,
)


class PrepareSongUseCase:
    """Orquestra a preparação de uma música para o catálogo de karaokê.

    Recebe termo de busca/URL ou arquivo local, realiza o download se necessário,
    isola as faixas vocal e instrumental via IA, busca a letra sincronizada
    e persiste os metadados localmente no armazenamento em disco.
    """

    def __init__(
        self,
        downloader: AudioDownloaderPort,
        separator: AudioSeparatorPort,
        storage: AudioStoragePort,
        lyrics_provider: LyricsProviderPort,
    ) -> None:
        self.downloader = downloader
        self.separator = separator
        self.storage = storage
        self.lyrics_provider = lyrics_provider

    def execute(
        self,
        query_or_url: str | None = None,
        local_file_path: Path | str | None = None,
        title: str | None = None,
        artist: str | None = None,
    ) -> Song:
        """Executa o pipeline completo de preparação da faixa de karaokê."""
        source_audio = self._resolve_input_audio(
            query_or_url=query_or_url,
            local_file_path=local_file_path,
            title=title,
            artist=artist,
        )

        song = self._create_initial_song(source_audio)
        self._persist_song_metadata(song)

        try:
            tracks = self._separate_audio_tracks(source_audio.file_path, song.id)
            self._sync_and_save_lyrics(song.id, song.title, song.artist)
            song.mark_as_ready(
                instrumental_path=tracks.instrumental_path,
                vocals_path=tracks.vocals_path,
                duration=source_audio.duration,
            )
            self._persist_song_metadata(song)
            return song
        except Exception:
            song.mark_as_failed()
            self._persist_song_metadata(song)
            raise

    def _resolve_input_audio(
        self,
        query_or_url: str | None,
        local_file_path: Path | str | None,
        title: str | None,
        artist: str | None,
    ) -> DownloadedAudio:
        """Determina e valida a origem do áudio (arquivo local ou download)."""
        if local_file_path is not None:
            return self._handle_local_file(
                local_path=Path(local_file_path),
                title=title,
                artist=artist,
            )
        if query_or_url is not None and query_or_url.strip():
            return self._handle_download(query_or_url.strip())

        raise InvalidAudioFormatError(
            "É obrigatório fornecer busca/URL ou caminho de arquivo local."
        )

    def _handle_local_file(
        self,
        local_path: Path,
        title: str | None,
        artist: str | None,
    ) -> DownloadedAudio:
        """Valida e processa um arquivo de áudio já existente no disco local."""
        resolved = local_path.resolve()
        if not resolved.is_file():
            raise InvalidStoragePathError(
                f"Arquivo de áudio local não encontrado: {local_path}"
            )

        resolved_title = title or resolved.stem.replace("_", " ").title()
        resolved_artist = artist or "Artista Desconhecido"

        return DownloadedAudio(
            file_path=resolved,
            title=resolved_title,
            artist=resolved_artist,
            duration=0.0,
        )

    def _handle_download(self, query_or_url: str) -> DownloadedAudio:
        """Efetua o download do áudio na pasta raw do armazenamento."""
        raw_dir = self.storage.get_path("download_target", "raw").parent
        return self.downloader.download(query_or_url, raw_dir)

    def _create_initial_song(self, audio: DownloadedAudio) -> Song:
        """Instancia a entidade Song no estado PROCESSING."""
        song_id = f"song_{uuid.uuid4().hex[:10]}"
        song = Song(
            id=song_id,
            title=audio.title,
            artist=audio.artist,
            duration=audio.duration,
            raw_audio_path=audio.file_path,
        )
        song.mark_as_processing()
        return song

    def _separate_audio_tracks(self, audio_path: Path, song_id: str) -> SeparatedTracks:
        """Executa a separação das faixas vocal e instrumental."""
        processed_dir = self.storage.get_path(f"{song_id}_target", "processed").parent
        return self.separator.separate(audio_path, processed_dir)

    def _sync_and_save_lyrics(
        self, song_id: str, title: str, artist: str | None
    ) -> None:
        """Busca a letra sincronizada e salva o arquivo .lrc caso encontrada."""
        try:
            lyrics_lines = self.lyrics_provider.get_lyrics(title=title, artist=artist)
            if lyrics_lines:
                lrc_content = self._format_lrc_content(lyrics_lines)
                self.storage.save_file(
                    file_data=lrc_content.encode("utf-8"),
                    filename=f"{song_id}.lrc",
                    subfolder="lyrics",
                )
        except Exception:
            # Letra é opcional; falha na busca não aborta a preparação da música
            pass

    def _format_lrc_content(self, lines: tuple[LyricsLine, ...]) -> str:
        """Converte uma sequência de LyricsLine para o formato padrão LRC."""
        lrc_rows: list[str] = []
        for line in lines:
            minutes = int(line.start_time // 60)
            seconds = int(line.start_time % 60)
            hundredths = int((line.start_time - int(line.start_time)) * 100)
            timestamp_str = f"[{minutes:02d}:{seconds:02d}.{hundredths:02d}]"
            lrc_rows.append(f"{timestamp_str}{line.text}")
        return "\n".join(lrc_rows)

    def _persist_song_metadata(self, song: Song) -> None:
        """Serializa e salva os metadados da música em JSON no disco local."""
        metadata = {
            "id": song.id,
            "title": song.title,
            "artist": song.artist,
            "duration": song.duration,
            "status": song.status.value,
            "raw_audio_path": str(song.raw_audio_path) if song.raw_audio_path else None,
            "instrumental_path": (
                str(song.instrumental_path) if song.instrumental_path else None
            ),
            "vocals_path": str(song.vocals_path) if song.vocals_path else None,
            "created_at": song.created_at.isoformat(),
        }
        json_data = json.dumps(metadata, indent=2).encode("utf-8")
        self.storage.save_file(
            file_data=json_data,
            filename=f"{song.id}.json",
            subfolder="processed",
        )
