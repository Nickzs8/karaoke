"""Caso de Uso: ListSongsUseCase."""

import json
from dataclasses import dataclass
from pathlib import Path

from karaoke.application.ports import AudioStoragePort
from karaoke.domain import SongStatus


@dataclass(frozen=True)
class SongCatalogItem:
    """Representação DTO de uma música no catálogo para apresentação/API."""

    id: str
    title: str
    artist: str
    duration: float
    status: str
    instrumental_url: str | None = None
    vocals_url: str | None = None


class ListSongsUseCase:
    """Lista as músicas salvas no armazenamento com seus status e links de áudio."""

    def __init__(
        self,
        storage: AudioStoragePort,
        base_audio_url: str = "/static/audio",
    ) -> None:
        self.storage = storage
        self.base_audio_url = base_audio_url.rstrip("/")

    def execute(self, only_ready: bool = True) -> list[SongCatalogItem]:
        """Recupera as músicas a partir dos metadados locais em disco."""
        filenames = self.storage.list_files("processed")
        catalog_items: list[SongCatalogItem] = []

        for filename in filenames:
            if not filename.endswith(".json"):
                continue
            item = self._load_catalog_item(filename)
            if item is None:
                continue
            if only_ready and item.status != SongStatus.READY.value:
                continue
            catalog_items.append(item)

        return catalog_items

    def _load_catalog_item(self, filename: str) -> SongCatalogItem | None:
        """Carrega e converte o arquivo JSON de metadados em SongCatalogItem."""
        try:
            path = self.storage.get_path(filename, "processed")
            data = json.loads(path.read_text(encoding="utf-8"))

            inst_path = (
                Path(data["instrumental_path"])
                if data.get("instrumental_path")
                else None
            )
            voc_path = Path(data["vocals_path"]) if data.get("vocals_path") else None

            return SongCatalogItem(
                id=data["id"],
                title=data["title"],
                artist=data["artist"],
                duration=float(data.get("duration", 0.0)),
                status=data["status"],
                instrumental_url=self._format_audio_url(inst_path),
                vocals_url=self._format_audio_url(voc_path),
            )
        except Exception:
            return None

    def _format_audio_url(self, file_path: Path | None) -> str | None:
        """Gera o link relativo de streaming para a faixa de áudio."""
        if file_path is None:
            return None
        subfolder = file_path.parent.name
        filename = file_path.name
        return f"{self.base_audio_url}/{subfolder}/{filename}"
