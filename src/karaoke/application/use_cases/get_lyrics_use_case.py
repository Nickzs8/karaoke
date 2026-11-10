"""Caso de Uso: GetLyricsUseCase."""

import json
import re
from pathlib import Path

from karaoke.application.ports import (
    AudioStoragePort,
    ForcedAlignerPort,
    LyricsProviderPort,
    VocalOnsetDetectorPort,
)
from karaoke.domain import (
    LyricsLine,
    LyricsNotFoundError,
    LyricWord,
    SongNotFoundError,
)


class GetLyricsUseCase:
    """Recupera e processa letras sincronizadas (.lrc) salvas em disco local.

    Valida a existência prévia da música, carrega o arquivo de letra correspondente,
    realiza a estruturação temporal das linhas em instâncias de LyricsLine
    e opcionalmente calcula a estimativa de offset temporal com base no áudio.
    Permite busca sob demanda via LyricsProviderPort se o arquivo .lrc não existir.
    """

    TIMESTAMP_PATTERN = re.compile(r"\[(\d{2,}):(\d{2}(?:\.\d{1,3})?)\]")
    DEFAULT_LINE_DURATION = 3.0

    def __init__(
        self,
        storage: AudioStoragePort,
        onset_detector: VocalOnsetDetectorPort | None = None,
        lyrics_provider: LyricsProviderPort | None = None,
        forced_aligner: ForcedAlignerPort | None = None,
    ) -> None:
        self.storage = storage
        self.onset_detector = onset_detector
        self.lyrics_provider = lyrics_provider
        self.forced_aligner = forced_aligner

    def execute(self, song_id: str) -> tuple[LyricsLine, ...]:
        """Recupera e estrutura a letra sincronizada para a música indicada."""
        self._ensure_song_exists(song_id)

        json_lines = self._read_json_lyrics_file(song_id)
        if json_lines is not None:
            return json_lines

        raw_lrc = self._read_lrc_file(song_id)
        if raw_lrc is not None:
            lines = self._parse_lrc(raw_lrc)
            return self._try_align_and_cache_json(song_id, lines)

        if self.lyrics_provider is not None:
            cached_lines = self._fetch_and_cache_lyrics(song_id)
            if cached_lines:
                return cached_lines

        raise LyricsNotFoundError(
            f"Letra sincronizada não encontrada para a música '{song_id}'."
        )

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

    def _read_lrc_file(self, song_id: str) -> str | None:
        """Lê o arquivo de texto LRC salvo na subpasta de letras se existir."""
        lyrics_filename = f"{song_id}.lrc"
        if not self.storage.file_exists(lyrics_filename, "lyrics"):
            return None
        lyrics_path = self.storage.get_path(lyrics_filename, "lyrics")
        return lyrics_path.read_text(encoding="utf-8")

    def _read_json_lyrics_file(self, song_id: str) -> tuple[LyricsLine, ...] | None:
        """Lê a letra estruturada com palavras em JSON caso já tenha sido alinhada."""
        json_filename = f"{song_id}.json"
        if not self.storage.file_exists(json_filename, "lyrics"):
            return None
        json_path = self.storage.get_path(json_filename, "lyrics")
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            lines: list[LyricsLine] = []
            for item in data:
                words = tuple(
                    LyricWord(
                        text=w["text"],
                        start_time=float(w["start_time"]),
                        end_time=float(w["end_time"]),
                    )
                    for w in item.get("words", [])
                )
                lines.append(
                    LyricsLine(
                        start_time=float(item["start_time"]),
                        end_time=float(item["end_time"]),
                        text=str(item["text"]),
                        words=words,
                    )
                )
            return tuple(lines)
        except Exception:
            return None

    def _try_align_and_cache_json(
        self, song_id: str, lines: tuple[LyricsLine, ...]
    ) -> tuple[LyricsLine, ...]:
        """Tenta alinhar a letra lida do .lrc usando a faixa vocal e cacheia o JSON."""
        if self.forced_aligner is None:
            return lines

        metadata = self._read_song_metadata(song_id)
        if not metadata:
            return lines

        vocals_path = self._resolve_vocals_path(metadata)
        if vocals_path is None or not vocals_path.is_file():
            return lines

        try:
            aligned = self.forced_aligner.align_lyrics(vocals_path, lines)
            self._save_json_lyrics(song_id, aligned)
            return aligned
        except Exception:
            return lines

    def _save_json_lyrics(self, song_id: str, lines: tuple[LyricsLine, ...]) -> None:
        """Serializa os versos e palavras sincronizadas em JSON na pasta lyrics."""
        payload = [
            {
                "start_time": line.start_time,
                "end_time": line.end_time,
                "text": line.text,
                "words": [
                    {
                        "text": w.text,
                        "start_time": w.start_time,
                        "end_time": w.end_time,
                    }
                    for w in line.words
                ],
            }
            for line in lines
        ]
        json_data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.storage.save_file(
            file_data=json_data,
            filename=f"{song_id}.json",
            subfolder="lyrics",
        )

    def _fetch_and_cache_lyrics(self, song_id: str) -> tuple[LyricsLine, ...]:
        """Tenta buscar a letra sob demanda pelo provedor e salva o arquivo .lrc."""
        if self.lyrics_provider is None:
            return ()

        metadata = self._read_song_metadata(song_id)
        if not metadata:
            return ()

        title = str(metadata.get("title", "")).strip()
        raw_artist = metadata.get("artist")
        artist = str(raw_artist).strip() if raw_artist else None
        if not title:
            return ()

        try:
            lines = self.lyrics_provider.get_lyrics(title=title, artist=artist)
            if lines:
                lrc_content = self._format_lrc_content(lines)
                self.storage.save_file(
                    file_data=lrc_content.encode("utf-8"),
                    filename=f"{song_id}.lrc",
                    subfolder="lyrics",
                )
                return self._try_align_and_cache_json(song_id, lines)
        except Exception:
            return ()

        return ()

    def _format_lrc_content(self, lines: tuple[LyricsLine, ...]) -> str:
        """Converte uma sequência de LyricsLine para o formato padrão LRC."""
        lrc_rows: list[str] = []
        for line in lines:
            minutes = int(line.start_time // 60)
            seconds = line.start_time % 60
            timestamp_str = f"[{minutes:02d}:{seconds:05.2f}]"
            lrc_rows.append(f"{timestamp_str}{line.text}")
        return "\n".join(lrc_rows)

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
