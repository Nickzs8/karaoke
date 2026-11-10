"""Testes unitários para o adaptador MmsForcedAligner."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import torch

from karaoke.adapters.audio.mms_forced_aligner import MmsForcedAligner
from karaoke.domain import LyricsLine, LyricWord


class TestMmsForcedAligner:
    @pytest.fixture
    def aligner_adapter(self) -> MmsForcedAligner:
        return MmsForcedAligner(device="cpu")

    def test_clean_word_removes_accents_and_punctuation(
        self, aligner_adapter: MmsForcedAligner
    ) -> None:
        assert aligner_adapter._clean_word("coração!") == "coracao"
        assert aligner_adapter._clean_word("você?") == "voce"
        assert aligner_adapter._clean_word("don't") == "don't"
        assert aligner_adapter._clean_word("Água,") == "agua"
        assert aligner_adapter._clean_word("123") == ""

    def test_prepare_word_pairs(self, aligner_adapter: MmsForcedAligner) -> None:
        pairs = aligner_adapter._prepare_word_pairs("Olá, meu amigo!")
        assert len(pairs) == 3
        assert pairs[0] == ("Olá,", "ola")
        assert pairs[1] == ("meu", "meu")
        assert pairs[2] == ("amigo!", "amigo")

    def test_align_lyrics_with_empty_lines_returns_empty(
        self, aligner_adapter: MmsForcedAligner, tmp_path: Path
    ) -> None:
        audio_file = tmp_path / "vocals.wav"
        audio_file.write_bytes(b"dummy")
        result = aligner_adapter.align_lyrics(audio_file, ())
        assert result == ()

    def test_align_lyrics_with_missing_audio_returns_original_lines(
        self, aligner_adapter: MmsForcedAligner, tmp_path: Path
    ) -> None:
        missing_file = tmp_path / "nonexistent.wav"
        line = LyricsLine(start_time=1.0, end_time=3.0, text="hello world")
        result = aligner_adapter.align_lyrics(missing_file, (line,))
        assert len(result) == 1
        assert result[0] == line
        assert result[0].words == ()

    def test_compute_word_spans_calculates_correct_timestamps(
        self, aligner_adapter: MmsForcedAligner
    ) -> None:
        aligner_adapter._bundle = MagicMock()
        aligner_adapter._bundle.sample_rate = 16000
        aligner_adapter._model = MagicMock()
        aligner_adapter._aligner = MagicMock()

        # Mock token spans for 2 words: "hello" (0 to 5), "world" (6 to 10)
        span_w1 = [MagicMock(start=0, end=5)]
        span_w2 = [MagicMock(start=6, end=10)]
        aligner_adapter._aligner.return_value = [span_w1, span_w2]

        # Waveform of 16000 samples (1s), emission of 50 frames
        mock_waveform = torch.zeros((1, 16000))
        mock_emission = torch.zeros((1, 50, 29))
        aligner_adapter._model.return_value = (mock_emission, None)

        words = aligner_adapter._compute_word_spans(
            waveform=mock_waveform,
            tokens=[[1, 2], [3, 4]],
            word_pairs=[("hello", "hello"), ("world", "world")],
            chunk_start=2.0,
            line_end=5.0,
        )

        assert len(words) == 2
        assert isinstance(words[0], LyricWord)
        assert words[0].text == "hello"
        assert words[0].start_time == 2.0
        assert words[0].end_time > 2.0
        assert words[1].text == "world"
        assert words[1].start_time >= words[0].end_time

    def test_align_single_line_exception_falls_back_gracefully(
        self, aligner_adapter: MmsForcedAligner, tmp_path: Path
    ) -> None:
        line = LyricsLine(start_time=1.0, end_time=4.0, text="falha total")
        with patch.object(
            aligner_adapter, "_prepare_word_pairs", side_effect=RuntimeError("GPU OOM")
        ):
            res = aligner_adapter._align_single_line(line, tmp_path / "dummy.wav")
            assert res == line
            assert res.words == ()
