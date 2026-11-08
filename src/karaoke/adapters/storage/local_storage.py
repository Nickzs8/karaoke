"""Adaptador de Armazenamento Local: LocalStorageAdapter."""

import shutil
from pathlib import Path
from typing import BinaryIO

from karaoke.application.ports import AudioStoragePort


class LocalStorageAdapter(AudioStoragePort):
    """Implementa AudioStoragePort gerenciando arquivos no disco local.

    Protege contra ataques de Path Traversal e suporta escrita tanto
    em memória (bytes) quanto streaming de arquivos abertos (BinaryIO).
    """

    def __init__(self, base_dir: Path | str = Path("storage")) -> None:
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_secure_path(self, filename: str, subfolder: str) -> Path:
        """Resolve o caminho de forma segura, impedindo ataques de Path Traversal."""
        # Extrai apenas o nome final do arquivo, descartando qualquer '../' ou '/'
        clean_filename = Path(filename).name
        if not clean_filename or clean_filename in (".", ".."):
            raise ValueError(f"Nome de arquivo inválido: '{filename}'")

        # Sanitiza o nome do subdiretório
        clean_subfolder = Path(subfolder).name
        if not clean_subfolder or clean_subfolder in (".", ".."):
            raise ValueError(f"Nome de subdiretório inválido: '{subfolder}'")

        target_dir = (self.base_dir / clean_subfolder).resolve()
        target_path = (target_dir / clean_filename).resolve()

        # Garante que o caminho final reside estritamente dentro de base_dir
        if not target_path.is_relative_to(self.base_dir):
            raise ValueError(
                f"Tentativa de Path Traversal detectada com o arquivo '{filename}'."
            )

        return target_path

    def save_file(
        self,
        file_data: bytes | BinaryIO,
        filename: str,
        subfolder: str,
    ) -> Path:
        """Salva áudio no subdiretório indicado e retorna o caminho absoluto."""
        target_path = self._resolve_secure_path(filename, subfolder)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        with target_path.open("wb") as destination:
            if isinstance(file_data, bytes):
                destination.write(file_data)
            else:
                # Streaming eficiente em blocos de 64KB (evita estouro de memória RAM)
                shutil.copyfileobj(file_data, destination, length=64 * 1024)

        return target_path

    def get_path(self, filename: str, subfolder: str) -> Path:
        """Retorna o caminho absoluto seguro do arquivo no subdiretório."""
        return self._resolve_secure_path(filename, subfolder)

    def file_exists(self, filename: str, subfolder: str) -> bool:
        """Verifica se um arquivo existe no subdiretório especificado."""
        try:
            target_path = self._resolve_secure_path(filename, subfolder)
            return target_path.is_file()
        except ValueError:
            return False

    def delete_file(self, filename: str, subfolder: str) -> bool:
        """Remove um arquivo do armazenamento caso ele exista."""
        target_path = self._resolve_secure_path(filename, subfolder)
        if target_path.is_file():
            target_path.unlink()
            return True
        return False

    def clean_subfolder(self, subfolder: str) -> int:
        """Remove todos os arquivos do subdiretório preservando arquivos .gitkeep."""
        clean_subfolder = Path(subfolder).name
        target_dir = (self.base_dir / clean_subfolder).resolve()

        if not target_dir.is_dir() or not target_dir.is_relative_to(self.base_dir):
            return 0

        deleted_count = 0
        for item in target_dir.iterdir():
            # Preserva .gitkeep para não desestruturar o repositório
            if item.is_file() and item.name != ".gitkeep":
                item.unlink()
                deleted_count += 1
            elif item.is_dir():
                shutil.rmtree(item)
                deleted_count += 1

        return deleted_count
