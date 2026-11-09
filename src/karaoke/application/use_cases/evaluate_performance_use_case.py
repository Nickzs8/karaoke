"""Caso de Uso: EvaluatePerformanceUseCase."""

import json
from datetime import datetime
from pathlib import Path

from karaoke.application.ports import (
    AudioStoragePort,
    PerformanceScorerPort,
    PitchExtractorPort,
)
from karaoke.domain import (
    InvalidStoragePathError,
    ScoreResult,
    Song,
    SongNotFoundError,
    SongNotReadyError,
    SongStatus,
)


class EvaluatePerformanceUseCase:
    """Orquestra a avaliação objetiva da performance vocal do usuário.

    Recupera a música dos metadados locais no storage, valida sua prontidão,
    extrai as curvas de pitch da referência e do usuário e executa o DTW scorer.
    """

    def __init__(
        self,
        storage: AudioStoragePort,
        pitch_extractor: PitchExtractorPort,
        scorer: PerformanceScorerPort,
    ) -> None:
        self.storage = storage
        self.pitch_extractor = pitch_extractor
        self.scorer = scorer

    def execute(self, song_id: str, recording_path: Path | str) -> ScoreResult:
        """Executa a extração melódica de ambas as faixas e pontua a performance."""
        song = self._get_ready_song(song_id)
        valid_recording = self._validate_recording_path(recording_path)

        reference_vocals_path = self._get_vocals_path(song)

        reference_curve = self.pitch_extractor.extract_pitch(reference_vocals_path)
        user_curve = self.pitch_extractor.extract_pitch(valid_recording)

        return self.scorer.score_performance(
            reference_curve=reference_curve,
            user_curve=user_curve,
        )

    def _get_ready_song(self, song_id: str) -> Song:
        """Recupera a música salva em disco e assegura que está pronta."""
        metadata_filename = f"{song_id}.json"
        if not self.storage.file_exists(metadata_filename, "processed"):
            raise SongNotFoundError(
                f"Música com identificador '{song_id}' não encontrada no armazenamento."
            )

        metadata_file = self.storage.get_path(metadata_filename, "processed")
        song = self._deserialize_song(metadata_file)
        song.ensure_is_ready()
        return song

    def _deserialize_song(self, metadata_path: Path) -> Song:
        """Carrega e instancia a entidade Song a partir do arquivo JSON salvo."""
        content = metadata_path.read_text(encoding="utf-8")
        data = json.loads(content)

        raw_path = Path(data["raw_audio_path"]) if data.get("raw_audio_path") else None
        inst_path = (
            Path(data["instrumental_path"]) if data.get("instrumental_path") else None
        )
        voc_path = Path(data["vocals_path"]) if data.get("vocals_path") else None

        return Song(
            id=data["id"],
            title=data["title"],
            artist=data["artist"],
            duration=float(data.get("duration", 0.0)),
            status=SongStatus(data["status"]),
            raw_audio_path=raw_path,
            instrumental_path=inst_path,
            vocals_path=voc_path,
            created_at=datetime.fromisoformat(data["created_at"]),
        )

    def _get_vocals_path(self, song: Song) -> Path:
        """Valida a existência física do caminho da faixa vocal de referência."""
        if song.vocals_path is None:
            raise SongNotReadyError(
                f"A faixa vocal da música '{song.title}' não está disponível."
            )
        resolved = Path(song.vocals_path).resolve()
        if not resolved.is_file():
            # Tenta resolver dentro da subpasta processed/{song.id}/vocals.wav
            song_folder_candidate = (
                self.storage.get_path(song.id, "processed")
                / Path(song.vocals_path).name
            )
            if song_folder_candidate.is_file():
                return song_folder_candidate

            # Tenta resolver como arquivo direto em processed
            direct_candidate = self.storage.get_path(
                Path(song.vocals_path).name, "processed"
            )
            if direct_candidate.is_file():
                return direct_candidate

            raise InvalidStoragePathError(
                f"Faixa vocal de referência não encontrada: {song.vocals_path}"
            )
        return resolved

    def _validate_recording_path(self, recording_path: Path | str) -> Path:
        """Assegura a existência do arquivo de áudio gravado pelo usuário."""
        resolved = Path(recording_path).resolve()
        if not resolved.is_file():
            raise InvalidStoragePathError(
                f"Arquivo de gravação do usuário não encontrado: {recording_path}"
            )
        return resolved
