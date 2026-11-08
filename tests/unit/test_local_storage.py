"""Testes unitários para o adaptador LocalStorageAdapter."""

import io
from pathlib import Path

import pytest

from karaoke.adapters.storage import LocalStorageAdapter
from karaoke.application.ports import AudioStoragePort


class TestLocalStorageAdapter:
    @pytest.fixture
    def storage(self, tmp_path: Path) -> LocalStorageAdapter:
        return LocalStorageAdapter(base_dir=tmp_path)

    def test_satisfies_audio_storage_port_protocol(
        self, storage: LocalStorageAdapter
    ) -> None:
        port: AudioStoragePort = storage
        assert port is not None

    def test_save_file_bytes(self, storage: LocalStorageAdapter) -> None:
        data = b"conteudo_de_audio_binario"
        saved_path = storage.save_file(
            file_data=data,
            filename="musica.mp3",
            subfolder="raw",
        )

        assert saved_path.is_file()
        assert saved_path.read_bytes() == data
        assert saved_path.name == "musica.mp3"
        assert storage.file_exists("musica.mp3", "raw") is True

    def test_save_file_stream(self, storage: LocalStorageAdapter) -> None:
        stream = io.BytesIO(b"streaming_de_audio_64kb")
        saved_path = storage.save_file(
            file_data=stream,
            filename="gravacao.wav",
            subfolder="recordings",
        )

        assert saved_path.is_file()
        assert saved_path.read_bytes() == b"streaming_de_audio_64kb"
        assert storage.file_exists("gravacao.wav", "recordings") is True

    def test_get_path(self, storage: LocalStorageAdapter) -> None:
        path = storage.get_path("letra.lrc", "lyrics")
        assert path.name == "letra.lrc"
        assert path.parent.name == "lyrics"

    def test_delete_file(self, storage: LocalStorageAdapter) -> None:
        storage.save_file(b"data", "deletar.wav", "temp")
        assert storage.file_exists("deletar.wav", "temp") is True

        # Deleta arquivo existente
        assert storage.delete_file("deletar.wav", "temp") is True
        assert storage.file_exists("deletar.wav", "temp") is False

        # Tentar deletar arquivo inexistente retorna False
        assert storage.delete_file("nao_existe.wav", "temp") is False

    def test_clean_subfolder_preserves_gitkeep(
        self, storage: LocalStorageAdapter
    ) -> None:
        # Cria arquivos normais e um .gitkeep
        storage.save_file(b"1", "faixa1.wav", "processed")
        storage.save_file(b"2", "faixa2.wav", "processed")
        gitkeep_path = storage.get_path(".gitkeep", "processed")
        gitkeep_path.write_text("")

        assert storage.file_exists("faixa1.wav", "processed") is True
        assert storage.file_exists("faixa2.wav", "processed") is True
        assert gitkeep_path.is_file() is True

        deleted = storage.clean_subfolder("processed")
        assert deleted == 2

        # Arquivos de áudio foram limpos
        assert storage.file_exists("faixa1.wav", "processed") is False
        assert storage.file_exists("faixa2.wav", "processed") is False

        # O .gitkeep foi preservado
        assert gitkeep_path.is_file() is True

    @pytest.mark.parametrize(
        "malicious_filename",
        [
            "../../etc/passwd",
            "../secret.txt",
            "/absolute/root.wav",
        ],
    )
    def test_path_traversal_sanitization(
        self, storage: LocalStorageAdapter, malicious_filename: str
    ) -> None:
        # Path(filename).name extrai o nome base seguro sem escapar da pasta
        safe_path = storage.get_path(malicious_filename, "raw")
        assert safe_path.is_relative_to(storage.base_dir)
        assert safe_path.parent == storage.base_dir / "raw"

    @pytest.mark.parametrize("invalid_name", ["", ".", ".."])
    def test_invalid_names_raise_value_error(
        self, storage: LocalStorageAdapter, invalid_name: str
    ) -> None:
        with pytest.raises(ValueError):
            storage.get_path(invalid_name, "raw")
