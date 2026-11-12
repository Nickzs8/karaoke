"""Configurações da aplicação e resolução de infraestrutura: AppConfig."""

import os
from dataclasses import dataclass
from pathlib import Path

import torch


def load_env_file(env_path: Path) -> None:
    """Carrega pares CHAVE=VALOR de um arquivo .env para os.environ se existir."""
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        clean_key = key.strip()
        clean_value = value.strip().strip("'\"")
        if clean_key not in os.environ:
            os.environ[clean_key] = clean_value


def detect_device(preferred_device: str | None = None) -> str:
    """Detecta automaticamente o dispositivo de hardware disponível (CUDA ou CPU).

    Se CUDA não estiver disponível ou falhar, realiza o fallback gracioso para CPU.
    """
    if preferred_device:
        normalized = preferred_device.strip().lower()
        if normalized == "cuda":
            if torch.cuda.is_available():
                return "cuda"
            return "cpu"
        if normalized == "cpu":
            return "cpu"

    return "cuda" if torch.cuda.is_available() else "cpu"


@dataclass(frozen=True)
class AppConfig:
    """Configurações centrais da aplicação e gestão de caminhos locais."""

    base_dir: Path
    storage_dir: Path
    device: str = "cpu"
    demucs_model: str = "htdemucs"
    demucs_shifts: int = 0
    demucs_overlap: float = 0.1
    base_audio_url: str = "/static/audio"
    lrclib_url: str = "https://lrclib.net/api"
    pitch_weight: float = 0.7
    timing_weight: float = 0.3
    cents_tolerance: float = 100.0

    @property
    def raw_storage_dir(self) -> Path:
        """Diretório para armazenamento de áudios brutos baixados ou enviados."""
        return self.storage_dir / "raw"

    @property
    def processed_storage_dir(self) -> Path:
        """Diretório para faixas isoladas (instrumental/vocal) e metadados JSON."""
        return self.storage_dir / "processed"

    @property
    def recordings_storage_dir(self) -> Path:
        """Diretório para gravações de áudio do microfone dos usuários."""
        return self.storage_dir / "recordings"

    @property
    def lyrics_storage_dir(self) -> Path:
        """Diretório para arquivos de letras sincronizadas em formato .lrc."""
        return self.storage_dir / "lyrics"

    @property
    def is_cuda_available(self) -> bool:
        """Indica se a aceleração gráfica por hardware (GPU CUDA) está ativa."""
        return self.device == "cuda"

    def ensure_storage_directories(self) -> None:
        """Garante a existência física de todos os subdiretórios de armazenamento."""
        for directory in (
            self.raw_storage_dir,
            self.processed_storage_dir,
            self.recordings_storage_dir,
            self.lyrics_storage_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Instancia a configuração a partir de variáveis de ambiente."""
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        load_env_file(project_root / ".env")

        env_storage = os.getenv("KARAOKE_STORAGE_DIR")
        if env_storage:
            storage_path = Path(env_storage).resolve()
        else:
            storage_path = (project_root / "storage").resolve()

        raw_device = os.getenv("KARAOKE_DEVICE")
        active_device = detect_device(raw_device)

        demucs_model = os.getenv("KARAOKE_DEMUCS_MODEL", "htdemucs")
        demucs_shifts = int(os.getenv("KARAOKE_DEMUCS_SHIFTS", "0"))
        demucs_overlap = float(os.getenv("KARAOKE_DEMUCS_OVERLAP", "0.1"))
        base_audio_url = os.getenv("KARAOKE_BASE_AUDIO_URL", "/static/audio")
        lrclib_url = os.getenv("KARAOKE_LRCLIB_URL", "https://lrclib.net/api")

        pitch_weight = float(os.getenv("KARAOKE_PITCH_WEIGHT", "0.7"))
        timing_weight = float(os.getenv("KARAOKE_TIMING_WEIGHT", "0.3"))
        cents_tolerance = float(os.getenv("KARAOKE_CENTS_TOLERANCE", "100.0"))

        return cls(
            base_dir=project_root,
            storage_dir=storage_path,
            device=active_device,
            demucs_model=demucs_model,
            demucs_shifts=demucs_shifts,
            demucs_overlap=demucs_overlap,
            base_audio_url=base_audio_url,
            lrclib_url=lrclib_url,
            pitch_weight=pitch_weight,
            timing_weight=timing_weight,
            cents_tolerance=cents_tolerance,
        )
