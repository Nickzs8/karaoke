"""Caso de Uso: GetLyricsUseCase."""

import json
import re
from pathlib import Path

from karaoke.application.ports import AudioStoragePort, VocalOnsetDetectorPort
from karaoke.domain import (
    LyricsLine,
    LyricsNotFoundError,
    SongNotFoundError,
)


class GetLyricsUseCase:
    """Recupera e processa letras sincronizadas (.lrc) salvas em disco local.

    Valida a existência prévia da música, carrega o arquivo de letra correspondente,
    realiza a estruturação temporal das linhas em instâncias de LyricsLine
    e opcionalmente calcula a estimativa de offset temporal com base no áudio.
    """

    TIMESTAMP_PATTERN = re.compile(r"\[(\d{2,}):(\d{2}(?:\.\d{1,3})?)\]")
    DEFAULT_LINE_DURATION = 3.0

    def __init__(
        self,
        storage: AudioStoragePort,
        onset_detector: VocalOnsetDetectorPort | None = None,
    ) -> None:
        self.storage = storage
        self.onset_detector = onset_detector

    def execute(self, song_id: str) -> tuple[LyricsLine, ...]:
        """Recupera e estrutura a letra sincronizada para a música indicada."""
        self._ensure_song_exists(song_id)
        raw_lrc = self._read_lrc_file(song_id)
        return self._parse_lrc(raw_lrc)

    def estimate_offset(self, song_id: str, first_lyric_start: float) -> float:
        """Estima o offset entre a voz no áudio e o primeiro verso."""
        if self.onset_detector is None:
            return 0.0

        metadata = self._read_song_metadata(song_id)
        if not metadata:
            return 0.0

        vocals_path = self._resolve_vocals_path(metadata)
        if vocals_path is None or not vocals_path.is_file():
            return 0.0

        detected_onset = self.onset_detector.detect_onset(vocals_path)
        if detected_onset is None:
            return 0.0

        offset = round(detected_onset - first_lyric_start, 2)
        return max(-10.0, min(offset, 60.0))

    def _read_song_metadata(self, song_id: str) -> dict[str, object] | None:
        """Lê o arquivo de metadados da música em storage/processed."""
        metadata_filename = f"{song_id}.json"
        if not self.storage.file_exists(metadata_filename, "processed"):
            return None
        metadata_path = self.storage.get_path(metadata_filename, "processed")
        try:
            return json.loads(metadata_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _resolve_vocals_path(self, metadata: dict[str, object]) -> Path | None:
        """Resolve o caminho físico da faixa vocal no host ou storage."""
        raw_path = metadata.get("vocals_path")
        if not raw_path:
            return None
        candidate = Path(str(raw_path))
        if candidate.is_file():
            return candidate

        parts = candidate.parts
        if "processed" in parts:
            idx = parts.index("processed")
            rel_subpath = "/".join(parts[idx + 1 :])
            storage_candidate = self.storage.get_path(rel_subpath, "processed")
            if storage_candidate.is_file():
                return storage_candidate

        storage_fallback = self.storage.get_path(candidate.name, "processed")
        if storage_fallback.is_file():
            return storage_fallback

        return None

    def _ensure_song_exists(self, song_id: str) -> None:
        """Verifica se a música foi devidamente registrada e processada no catálogo."""
        metadata_filename = f"{song_id}.json"
        if not self.storage.file_exists(metadata_filename, "processed"):
            raise SongNotFoundError(
                f"Música com identificador '{song_id}' não encontrada no catálogo."
            )

    def _read_lrc_file(self, song_id: str) -> str:
        """Lê o arquivo de texto LRC salvo na subpasta de letras."""
        lyrics_filename = f"{song_id}.lrc"
        if not self.storage.file_exists(lyrics_filename, "lyrics"):
            raise LyricsNotFoundError(
                f"Letra sincronizada não encontrada para a música '{song_id}'."
            )
        lyrics_path = self.storage.get_path(lyrics_filename, "lyrics")
        return lyrics_path.read_text(encoding="utf-8")

    def _parse_lrc(self, lrc_content: str) -> tuple[LyricsLine, ...]:
        """Converte o conteúdo textual em formato LRC em uma tupla de LyricsLine."""
        raw_timed_lines = self._extract_timed_lines(lrc_content)
        if not raw_timed_lines:
            return ()
        return self._build_lyrics_lines(raw_timed_lines)

    def _extract_timed_lines(self, lrc_content: str) -> list[tuple[float, str]]:
        """Extrai timestamps e seus respectivos textos, ordenando cronologicamente."""
        timed_lines: list[tuple[float, str]] = []
        for line in lrc_content.splitlines():
            clean_line = line.strip()
            if not clean_line:
                continue

            matches = self.TIMESTAMP_PATTERN.findall(clean_line)
            if not matches:
                continue

            text_content = self.TIMESTAMP_PATTERN.sub("", clean_line).strip()
            for minutes_str, seconds_str in matches:
                timestamp = self._parse_timestamp(minutes_str, seconds_str)
                timed_lines.append((timestamp, text_content))

        timed_lines.sort(key=lambda item: item[0])
        return timed_lines

    def _parse_timestamp(self, minutes_str: str, seconds_str: str) -> float:
        """Converte minutos e segundos textuais em float de segundos totais."""
        minutes = int(minutes_str)
        seconds = float(seconds_str)
        return round(minutes * 60.0 + seconds, 3)

    def _build_lyrics_lines(
        self, raw_lines: list[tuple[float, str]]
    ) -> tuple[LyricsLine, ...]:
        """Calcula início e fim de cada verso, gerando objetos LyricsLine imutáveis."""
        parsed_lines: list[LyricsLine] = []
        total_items = len(raw_lines)

        for index, (start_time, text) in enumerate(raw_lines):
            if not text:
                continue

            end_time = self._calculate_end_time(
                index=index,
                start_time=start_time,
                raw_lines=raw_lines,
                total_items=total_items,
            )
            safe_end_time = max(start_time, end_time)

            parsed_lines.append(
                LyricsLine(
                    start_time=start_time,
                    end_time=safe_end_time,
                    text=text,
                )
            )

        return tuple(parsed_lines)

    def _calculate_end_time(
        self,
        index: int,
        start_time: float,
        raw_lines: list[tuple[float, str]],
        total_items: int,
    ) -> float:
        """Determina o instante de término pelo próximo verso ou duração padrão."""
        if index + 1 < total_items:
            next_timestamp = raw_lines[index + 1][0]
            if next_timestamp >= start_time:
                return next_timestamp

        return start_time + self.DEFAULT_LINE_DURATION
