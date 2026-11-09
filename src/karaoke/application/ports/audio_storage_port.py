"""Porta de Aplicação: AudioStoragePort."""

from pathlib import Path
from typing import BinaryIO, Protocol


class AudioStoragePort(Protocol):
    """Contrato para gestão de persistência e leitura de arquivos locais de áudio."""

    def save_file(
        self,
        file_data: bytes | BinaryIO,
        filename: str,
        subfolder: str,
    ) -> Path:
        """Salva áudio no subdiretório indicado e retorna o caminho absoluto."""
        ...

    def get_path(self, filename: str, subfolder: str) -> Path:
        """Retorna o caminho absoluto do arquivo no subdiretório especificado."""
        ...

    def file_exists(self, filename: str, subfolder: str) -> bool:
        """Verifica se um arquivo existe no subdiretório especificado."""
        ...

    def delete_file(self, filename: str, subfolder: str) -> bool:
        """Remove um arquivo do armazenamento caso ele exista."""
        ...

    def list_files(self, subfolder: str) -> list[str]:
        """Lista os nomes de arquivos existentes no subdiretório especificado."""
        ...

    def clean_subfolder(self, subfolder: str) -> int:
        """Remove todos os arquivos de um subdiretório e retorna o total removido."""
        ...
