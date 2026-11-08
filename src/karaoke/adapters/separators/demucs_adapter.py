"""Adaptador de Separação de Áudio com IA: DemucsSeparatorAdapter."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import demucs.api
import torch

from karaoke.application.ports import AudioSeparatorPort, SeparatedTracks
from karaoke.domain import AudioSeparationError


class DemucsSeparatorAdapter(AudioSeparatorPort):
    """Implementa AudioSeparatorPort utilizando o modelo neural Demucs.

    Detecta GPU (CUDA) automaticamente com fallback para CPU.
    Isola a faixa em vocals.wav e no_vocals.wav, executando a inferência
    em uma thread dedicada para não travar a aplicação.
    """

    def __init__(
        self,
        model_name: str = "htdemucs",
        device: str | None = None,
        shifts: int = 1,
        overlap: float = 0.25,
    ) -> None:
        self.model_name = model_name
        self.shifts = shifts
        self.overlap = overlap
        self.device = self._detect_device(device)
        self._separator: demucs.api.Separator | None = None
        self._executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="demucs-worker"
        )

    def separate(self, audio_path: Path, output_dir: Path) -> SeparatedTracks:
        """Orquestra o isolamento vocal e instrumental de um arquivo de áudio."""
        valid_audio = self._validate_audio_path(audio_path)
        target_dir = self._ensure_output_dir(output_dir)

        samplerate, stems = self._execute_separation_in_thread(valid_audio)
        vocals, no_vocals = self._extract_vocal_and_instrumental_tensors(stems)

        return self._save_tracks(vocals, no_vocals, samplerate, target_dir)

    def _detect_device(self, preferred_device: str | None) -> str:
        """Detecta disponibilidade de GPU CUDA ou aplica fallback para CPU."""
        if preferred_device:
            return preferred_device.lower()
        return "cuda" if torch.cuda.is_available() else "cpu"

    def _get_separator(self) -> demucs.api.Separator:
        """Inicializa e mantém o modelo Demucs em cache (Lazy Loading)."""
        if self._separator is None:
            try:
                self._separator = demucs.api.Separator(
                    model=self.model_name,
                    device=self.device,
                    shifts=self.shifts,
                    overlap=self.overlap,
                )
            except Exception as exc:
                raise AudioSeparationError(
                    f"Falha ao carregar modelo Demucs '{self.model_name}' "
                    f"no dispositivo '{self.device}': {exc}"
                ) from exc
        return self._separator

    def _validate_audio_path(self, audio_path: Path) -> Path:
        """Valida a existência do arquivo de áudio de entrada."""
        resolved = Path(audio_path).resolve()
        if not resolved.is_file():
            raise AudioSeparationError(
                f"Arquivo de áudio não encontrado para separação: {audio_path}"
            )
        return resolved

    def _ensure_output_dir(self, output_dir: Path) -> Path:
        """Garante a existência do diretório de destino."""
        target_dir = Path(output_dir).resolve()
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir

    def _execute_separation_in_thread(
        self, audio_path: Path
    ) -> tuple[int, dict[str, torch.Tensor]]:
        """Executa a inferência de IA em uma thread dedicada."""
        separator = self._get_separator()

        def _infer() -> tuple[int, dict[str, torch.Tensor]]:
            try:
                _origin, stems = separator.separate_audio_file(audio_path)
                return separator.samplerate, stems
            except Exception as exc:
                msg = (
                    f"Erro durante o processamento do Demucs para "
                    f"'{audio_path.name}': {exc}"
                )
                raise AudioSeparationError(msg) from exc

        future = self._executor.submit(_infer)
        return future.result()

    def _extract_vocal_and_instrumental_tensors(
        self, stems: dict[str, torch.Tensor]
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Extrai o tensor vocal e calcula o tensor instrumental combinando faixas."""
        if "vocals" not in stems:
            raise AudioSeparationError(
                "A faixa de vocais não foi encontrada no resultado do Demucs."
            )

        vocals = stems["vocals"]

        # Se o modelo já fornecer no_vocals (2-stem model), usa direto
        if "no_vocals" in stems:
            no_vocals = stems["no_vocals"]
        else:
            # Em modelos 4-stems (drums, bass, other, vocals), soma as não-vocais
            non_vocal_stems = [
                tensor for name, tensor in stems.items() if name != "vocals"
            ]
            if not non_vocal_stems:
                raise AudioSeparationError(
                    "Não foi possível calcular a faixa instrumental a partir dos stems."
                )
            no_vocals = sum(non_vocal_stems)

        return vocals, no_vocals

    def _save_tracks(
        self,
        vocals: torch.Tensor,
        no_vocals: torch.Tensor,
        samplerate: int,
        output_dir: Path,
    ) -> SeparatedTracks:
        """Salva as faixas separadas em vocals.wav e no_vocals.wav."""
        vocals_path = output_dir / "vocals.wav"
        instrumental_path = output_dir / "no_vocals.wav"

        try:
            demucs.api.save_audio(vocals, vocals_path, samplerate=samplerate)
            demucs.api.save_audio(no_vocals, instrumental_path, samplerate=samplerate)
        except Exception as exc:
            raise AudioSeparationError(
                f"Falha ao salvar as faixas separadas em disco: {exc}"
            ) from exc

        return SeparatedTracks(
            instrumental_path=instrumental_path,
            vocals_path=vocals_path,
        )
