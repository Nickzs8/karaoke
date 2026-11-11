"""Adaptador de Áudio: MmsForcedAligner."""

import logging
import re
import unicodedata
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import soundfile as sf
import torch
import torchaudio

from karaoke.application.ports.forced_aligner_port import ForcedAlignerPort
from karaoke.domain import LyricsLine, LyricWord

logger = logging.getLogger(__name__)


class MmsForcedAligner(ForcedAlignerPort):
    """Implementa alinhamento forçado usando o modelo Wav2Vec2 MMS da Meta."""

    def __init__(self, device: str | None = None) -> None:
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._bundle = None
        self._model = None
        self._tokenizer = None
        self._aligner = None

    def align_lyrics(
        self,
        audio_path: Path,
        lines: Sequence[LyricsLine],
    ) -> tuple[LyricsLine, ...]:
        """Calcula timestamps de palavras para cada verso da letra."""
        if not lines or not audio_path.exists():
            return tuple(lines)

        self._ensure_initialized()

        aligned_lines: list[LyricsLine] = []
        for line in lines:
            aligned_line = self._align_single_line(line, audio_path)
            aligned_lines.append(aligned_line)

        return tuple(aligned_lines)

    def _ensure_initialized(self) -> None:
        """Carrega o bundle, modelo, tokenizer e aligner de forma lazy."""
        if self._model is not None:
            return

        from torchaudio.pipelines import MMS_FA

        self._bundle = MMS_FA
        self._model = self._bundle.get_model().to(self.device)
        self._model.eval()
        self._tokenizer = self._bundle.get_tokenizer()
        self._aligner = self._bundle.get_aligner()

    def _align_single_line(self, line: LyricsLine, audio_path: Path) -> LyricsLine:
        """Alinha um único verso; em caso de falha retorna a linha original."""
        try:
            word_pairs = self._prepare_word_pairs(line.text)
            if not word_pairs:
                return line

            tokens = self._tokenizer([pair[1] for pair in word_pairs])

            # Limita a fatia de áudio para o limite razoável do verso cantado,
            # impedindo que dezenas de segundos de solos ou silêncio entrem no aligner
            expected_max_duration = max(6.0, len(word_pairs) * 2.0)
            capped_end_time = min(line.end_time, line.start_time + expected_max_duration)

            chunk_start, chunk_waveform = self._load_audio_slice(
                audio_path=audio_path,
                start_time=line.start_time,
                end_time=capped_end_time,
            )

            if chunk_waveform is None or chunk_waveform.shape[1] == 0:
                return line

            words = self._compute_word_spans(
                waveform=chunk_waveform,
                tokens=tokens,
                word_pairs=word_pairs,
                chunk_start=chunk_start,
                line_end=line.end_time,
            )

            if not words:
                return line

            return LyricsLine(
                start_time=line.start_time,
                end_time=line.end_time,
                text=line.text,
                words=tuple(words),
            )
        except Exception as exc:
            logger.warning(
                "Falha ao alinhar verso '%s' (%ss - %ss): %s",
                line.text,
                line.start_time,
                line.end_time,
                exc,
            )
            return line

    def _prepare_word_pairs(self, text: str) -> list[tuple[str, str]]:
        """Extrai palavras brutas e suas formas limpas para o tokenizer."""
        raw_words = text.strip().split()
        pairs: list[tuple[str, str]] = []
        for word in raw_words:
            cleaned = self._clean_word(word)
            if cleaned:
                pairs.append((word, cleaned))
        return pairs

    def _clean_word(self, word: str) -> str:
        """Remove acentos e pontuações, preservando apenas letras e apóstrofos."""
        normalized = (
            unicodedata.normalize("NFKD", word)
            .encode("ASCII", "ignore")
            .decode("utf-8")
        )
        return re.sub(r"[^a-z\']", "", normalized.lower())

    def _load_audio_slice(
        self,
        audio_path: Path,
        start_time: float,
        end_time: float,
        padding_sec: float = 0.2,
    ) -> tuple[float, torch.Tensor | None]:
        """Lê apenas a fatia de áudio correspondente ao verso com margem temporal."""
        target_sr = self._bundle.sample_rate
        chunk_start = max(0.0, start_time - padding_sec)
        chunk_end = end_time + padding_sec

        with sf.SoundFile(str(audio_path)) as sound_file:
            sr = sound_file.samplerate
            total_frames = len(sound_file)
            start_frame = min(int(chunk_start * sr), total_frames)
            stop_frame = min(int(chunk_end * sr), total_frames)
            num_frames = stop_frame - start_frame
            if num_frames <= 0:
                return chunk_start, None

            sound_file.seek(start_frame)
            data = sound_file.read(num_frames, dtype="float32")

        waveform = torch.from_numpy(data)
        if waveform.ndim == 1:
            waveform = waveform.unsqueeze(0)
        else:
            waveform = waveform.T

        if sr != target_sr:
            waveform = torchaudio.functional.resample(waveform, sr, target_sr)

        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)

        return chunk_start, waveform

    def _compute_word_spans(
        self,
        waveform: torch.Tensor,
        tokens: list[list[int]],
        word_pairs: list[tuple[str, str]],
        chunk_start: float,
        line_end: float,
    ) -> list[LyricWord]:
        """Calcula os timestamps de cada palavra através do aligner CTC."""
        target_sr = self._bundle.sample_rate
        waveform = waveform.to(self.device)

        with torch.inference_mode():
            emission, _ = self._model(waveform)
            token_spans = self._aligner(emission[0], tokens)

        num_frames = emission.shape[1]
        if num_frames == 0:
            return []

        frame_duration = waveform.shape[1] / num_frames / target_sr
        raw_words = self._extract_raw_spans(
            word_pairs=word_pairs,
            token_spans=token_spans,
            chunk_start=chunk_start,
            frame_duration=frame_duration,
        )
        return self._constrain_word_durations(raw_words)

    def _extract_raw_spans(
        self,
        word_pairs: list[tuple[str, str]],
        token_spans: Any,
        chunk_start: float,
        frame_duration: float,
    ) -> list[LyricWord]:
        """Extrai LyricWord com timestamps brutos a partir dos spans do tokenizer."""
        lyric_words: list[LyricWord] = []
        for (raw_text, _), spans in zip(word_pairs, token_spans, strict=False):
            if not spans:
                continue
            w_start = round(chunk_start + (spans[0].start * frame_duration), 2)
            w_end = round(chunk_start + (spans[-1].end * frame_duration), 2)
            w_start = max(0.0, w_start)
            w_end = max(w_start, w_end)

            lyric_words.append(
                LyricWord(
                    text=raw_text,
                    start_time=w_start,
                    end_time=w_end,
                )
            )
        return lyric_words

    def _constrain_word_durations(
        self, words: list[LyricWord]
    ) -> list[LyricWord]:
        """Limita esticamentos anômalos causados pela dispersão do trellis CTC sobre pausas/silêncios."""
        if not words:
            return []

        constrained: list[LyricWord] = []
        total_words = len(words)

        for i, word in enumerate(words):
            w_start = word.start_time
            w_end = word.end_time
            w_dur = w_end - w_start

            if i == total_words - 1:
                # Na última palavra antes de uma pausa/solo instrumental, limita com base no ritmo anterior
                ref_dur = 0.6
                if total_words > 1:
                    prev_durs = [w.end_time - w.start_time for w in constrained]
                    ref_dur = sum(prev_durs) / len(prev_durs)

                max_last_dur = min(3.8, max(3.0, ref_dur * 3.5))
                if w_dur > max_last_dur:
                    w_end = round(w_start + max_last_dur, 2)
            else:
                # Palavras intermediárias não devem ultrapassar teto fisiológico razoável
                if w_dur > 4.0:
                    w_end = round(w_start + 4.0, 2)

            constrained.append(
                LyricWord(
                    text=word.text,
                    start_time=w_start,
                    end_time=max(w_start, w_end),
                )
            )

        return constrained
