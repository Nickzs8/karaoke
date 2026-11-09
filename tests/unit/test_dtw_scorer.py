"""Testes unitários para o adaptador DtwPerformanceScorerAdapter."""

import numpy as np
import pytest

from karaoke.adapters.audio import DtwPerformanceScorerAdapter, DtwScorerAdapter
from karaoke.application.ports import PerformanceScorerPort
from karaoke.domain import (
    InvalidScorerConfigError,
    PitchCurve,
    PitchPoint,
    Score,
    ScoreResult,
)


def _create_curve(
    notes: list[float],
    start_time: float = 0.0,
    time_step: float = 0.1,
) -> PitchCurve:
    """Função auxiliar para construir PitchCurves de teste a partir de notas MIDI."""
    points: list[PitchPoint] = []
    for i, note in enumerate(notes):
        timestamp = round(start_time + (i * time_step), 3)
        # 440 * 2^((midi - 69)/12)
        freq = 440.0 * (2.0 ** ((note - 69.0) / 12.0))
        points.append(
            PitchPoint(
                timestamp=timestamp,
                frequency_hz=round(freq, 2),
                midi_note=note,
            )
        )
    return PitchCurve(points=tuple(points))


class TestDtwPerformanceScorerAdapter:
    def test_implements_performance_scorer_port(self) -> None:
        """Garante conformidade com a porta PerformanceScorerPort."""
        scorer = DtwPerformanceScorerAdapter()
        port: PerformanceScorerPort = scorer
        assert port is not None
        assert callable(getattr(scorer, "score_performance", None))
        assert DtwScorerAdapter is DtwPerformanceScorerAdapter

    def test_identical_curves_produce_perfect_score(self) -> None:
        """Curvas idênticas devem receber 100 em afinação, ritmo e nota final."""
        scorer = DtwPerformanceScorerAdapter()
        curve = _create_curve([60.0, 62.0, 64.0, 65.0, 67.0])

        result = scorer.score_performance(curve, curve)

        assert isinstance(result, ScoreResult)
        assert result.pitch_score.value == 100.0
        assert result.timing_score.value == 100.0
        assert result.total_score.value == 100.0
        assert result.details["mean_pitch_error_cents"] == 0.0
        assert result.details["mean_timing_deviation_seconds"] == 0.0
        assert result.details["octave_shift"] == 0

    def test_dtw_absorbs_timing_variations(self) -> None:
        """DTW deve alinhar notas no tempo mantendo alta precisão de afinação."""
        scorer = DtwPerformanceScorerAdapter(
            timing_tolerance_seconds=0.15,
            max_timing_deviation_seconds=1.0,
        )
        # Referência: notas com 1 frame cada
        ref_curve = _create_curve([60.0, 62.0, 64.0, 65.0, 67.0], time_step=0.2)
        # Usuário canta afinado, mas sustenta a nota 62.0 por mais tempo
        user_curve = _create_curve(
            [60.0, 62.0, 62.0, 62.0, 64.0, 65.0, 67.0], time_step=0.2
        )

        result = scorer.score_performance(ref_curve, user_curve)

        # Como as notas cantadas estão perfeitamente afinadas, afinação é 100
        assert result.pitch_score.value == 100.0
        # O desvio temporal gerou uma penalidade leve no ritmo, mas permaneceu alto
        assert 0.0 < result.timing_score.value <= 100.0
        assert 0.0 < result.total_score.value <= 100.0

    def test_octave_transposition_tolerance_for_male_female_timbre(self) -> None:
        """Deve tolerar e transpor oitavas diferentes (ex: masculino vs feminino)."""
        scorer = DtwPerformanceScorerAdapter(allow_octave_transposition=True)

        # Referência feminina: C5 a G5 (72 a 79)
        ref_curve = _create_curve([72.0, 74.0, 76.0, 77.0, 79.0])
        # Usuário masculino cantando exatamente 1 oitava abaixo (C4 a G4: 60 a 67)
        user_curve_1_oct_down = _create_curve([60.0, 62.0, 64.0, 65.0, 67.0])
        # Usuário cantando 2 oitavas abaixo (C3 a G3: 48 a 55)
        user_curve_2_oct_down = _create_curve([48.0, 50.0, 52.0, 53.0, 55.0])

        res_1 = scorer.score_performance(ref_curve, user_curve_1_oct_down)
        assert res_1.pitch_score.value == 100.0
        assert res_1.total_score.value == 100.0
        assert res_1.details["octave_shift"] == 1

        res_2 = scorer.score_performance(ref_curve, user_curve_2_oct_down)
        assert res_2.pitch_score.value == 100.0
        assert res_2.total_score.value == 100.0
        assert res_2.details["octave_shift"] == 2

    def test_octave_transposition_disabled(self) -> None:
        """Sem transposição de oitavas, erro de 1 oitava deve zerar afinação."""
        scorer = DtwPerformanceScorerAdapter(allow_octave_transposition=False)

        ref_curve = _create_curve([72.0, 74.0, 76.0])
        user_curve = _create_curve([60.0, 62.0, 64.0])  # 12 semitons de diferença

        res = scorer.score_performance(ref_curve, user_curve)
        assert res.pitch_score.value == 0.0
        assert res.details["octave_shift"] == 0

    def test_pitch_cents_tolerance_up_to_50_cents_gives_max_score(self) -> None:
        """Desvios de até 50 cents (0.5 semitons) devem receber nota máxima 100."""
        scorer = DtwPerformanceScorerAdapter(cents_tolerance=50.0)

        ref_curve = _create_curve([60.0, 62.0, 64.0])
        # Erro de 30 cents (0.30 semitons)
        user_curve_30_cents = _create_curve([60.30, 62.30, 64.30])
        # Erro de 50 cents exatos (0.50 semitons)
        user_curve_50_cents = _create_curve([60.50, 62.50, 64.50])

        res_30 = scorer.score_performance(ref_curve, user_curve_30_cents)
        res_50 = scorer.score_performance(ref_curve, user_curve_50_cents)

        assert res_30.pitch_score.value == 100.0
        assert res_50.pitch_score.value == 100.0
        assert pytest.approx(res_30.details["mean_pitch_error_cents"], 0.1) == 30.0
        assert pytest.approx(res_50.details["mean_pitch_error_cents"], 0.1) == 50.0

    def test_pitch_score_decays_above_50_cents_and_zeroes_at_max(self) -> None:
        """Acima de 50 cents o score de afinação decai e zera em max_cents_error."""
        scorer = DtwPerformanceScorerAdapter(
            cents_tolerance=50.0,
            max_cents_error=200.0,
        )
        ref_curve = _create_curve([60.0, 60.0, 60.0])

        # 125 cents de erro: metade do caminho entre 50 e 200 -> score esperado ~50.0
        user_125_cents = _create_curve([61.25, 61.25, 61.25])
        res_125 = scorer.score_performance(ref_curve, user_125_cents)
        assert pytest.approx(res_125.pitch_score.value, 0.5) == 50.0

        # 200 cents de erro (2 semitons): deve zerar a afinação
        user_200_cents = _create_curve([62.0, 62.0, 62.0])
        res_200 = scorer.score_performance(ref_curve, user_200_cents)
        assert res_200.pitch_score.value == 0.0

        # Mais de 200 cents: permanece zerado
        user_300_cents = _create_curve([63.0, 63.0, 63.0])
        res_300 = scorer.score_performance(ref_curve, user_300_cents)
        assert res_300.pitch_score.value == 0.0

    def test_timing_deviation_scoring_within_and_beyond_tolerance(self) -> None:
        """Avalia o decaimento do score de ritmo baseado no desvio do caminho do DTW."""
        scorer = DtwPerformanceScorerAdapter(
            timing_tolerance_seconds=0.15,
            max_timing_deviation_seconds=1.0,
            compensate_latency=False,
        )

        # Referência começando em 0.0s
        ref_curve = _create_curve([60.0, 62.0, 64.0], start_time=0.0, time_step=0.2)

        # Usuário com atraso constante de 0.10s (dentro da tolerância de 0.15s)
        user_fast = _create_curve([60.0, 62.0, 64.0], start_time=0.10, time_step=0.2)
        res_fast = scorer.score_performance(ref_curve, user_fast)
        assert res_fast.timing_score.value == 100.0

        # Usuário com atraso de 0.575s (metade entre 0.15s e 1.0s -> ~50.0)
        user_mid = _create_curve([60.0, 62.0, 64.0], start_time=0.575, time_step=0.2)
        res_mid = scorer.score_performance(ref_curve, user_mid)
        assert pytest.approx(res_mid.timing_score.value, 0.5) == 50.0

        # Usuário com atraso de 1.2s (acima de max_timing_deviation -> 0.0)
        user_late = _create_curve([60.0, 62.0, 64.0], start_time=1.2, time_step=0.2)
        res_late = scorer.score_performance(ref_curve, user_late)
        assert res_late.timing_score.value == 0.0

    def test_latency_compensation_absorbs_browser_buffer_delay(self) -> None:
        """Compensação de latência deve detectar offset global e preservar pontuação."""
        scorer = DtwPerformanceScorerAdapter(
            timing_tolerance_seconds=0.15,
            max_timing_deviation_seconds=1.0,
            compensate_latency=True,
            max_latency_seconds=1.5,
        )
        ref_curve = _create_curve([60.0, 62.0, 64.0], start_time=0.0, time_step=0.2)
        user_delayed = _create_curve([60.0, 62.0, 64.0], start_time=0.30, time_step=0.2)

        res = scorer.score_performance(ref_curve, user_delayed)
        assert res.timing_score.value == 100.0
        assert res.details["global_latency_seconds"] == 0.3

    def test_coverage_ratio_scales_total_score_proportionally(self) -> None:
        """Cantar apenas uma fração da música escala a nota final proporcionalmente."""
        scorer = DtwPerformanceScorerAdapter()
        # Referência completa com 10 notas (2 no início e 8 mais tarde)
        pts = [
            PitchPoint(timestamp=round(i * 0.2, 2), frequency_hz=440.0, midi_note=60.0)
            for i in range(2)
        ]
        pts += [
            PitchPoint(
                timestamp=round(10.0 + i * 0.2, 2),
                frequency_hz=440.0,
                midi_note=60.0,
            )
            for i in range(8)
        ]
        ref_curve = PitchCurve(points=tuple(pts))

        # Usuário cantou afinado e no ritmo apenas 2 notas (20% de cobertura)
        user_partial = _create_curve([60.0, 60.0], start_time=0.0, time_step=0.2)

        res = scorer.score_performance(ref_curve, user_partial)
        assert res.pitch_score.value == 100.0
        assert res.timing_score.value == 100.0
        assert res.details["coverage_ratio"] == 20.0
        # Total ponderado: (100 * 0.7 + 100 * 0.3) * 0.20 = 20.0
        assert res.total_score.value == 20.0

    def test_sakoe_chiba_window_constraint_penalizes_distant_warping(self) -> None:
        """Janela temporal impede o DTW de alinhar trechos distantes."""
        scorer = DtwPerformanceScorerAdapter(max_window_seconds=1.0)
        cost_matrix = scorer._build_cost_matrix(
            ref_midi=np.array([60.0, 60.0]),
            user_midi=np.array([60.0, 60.0]),
            ref_times=np.array([0.0, 10.0]),
            user_times=np.array([0.0, 1.0]),
        )
        # O par com diff=10.0s > 1.0s deve receber penalidade alta
        assert cost_matrix[1, 0] > 100.0

    def test_weighted_score_consolidation_and_bounds(self) -> None:
        """Garante consolidação ponderada correta e intervalo estrito [0.0, 100.0]."""
        # Pesos 80% afinação e 20% ritmo
        scorer = DtwPerformanceScorerAdapter(
            pitch_weight=0.8,
            timing_weight=0.2,
            cents_tolerance=50.0,
            max_cents_error=200.0,
        )

        ref_curve = _create_curve([60.0, 62.0, 64.0], start_time=0.0, time_step=0.2)
        # Afinação perfeita (100.0), mas atraso grande que zera ritmo (0.0)
        # Total esperado: (100 * 0.8) + (0 * 0.2) = 80.0
        user_curve = _create_curve([60.0, 62.0, 64.0], start_time=5.0, time_step=0.2)

        result = scorer.score_performance(ref_curve, user_curve)
        assert result.pitch_score.value == 100.0
        assert result.timing_score.value == 0.0
        assert result.total_score.value == 80.0
        assert isinstance(result.total_score, Score)

    def test_empty_or_silent_curves_return_safe_zero_score(self) -> None:
        """Curvas sem frames vocais devem retornar ScoreResult zerado com aviso."""
        scorer = DtwPerformanceScorerAdapter()
        normal_curve = _create_curve([60.0, 62.0])
        empty_curve = PitchCurve()
        silent_curve = PitchCurve(
            points=(
                PitchPoint(timestamp=0.1, frequency_hz=0.0, midi_note=0.0),
                PitchPoint(timestamp=0.2, frequency_hz=0.0, midi_note=0.0),
            )
        )

        # Referência vazia
        res_1 = scorer.score_performance(empty_curve, normal_curve)
        assert res_1.total_score.value == 0.0
        assert "warning" in res_1.details

        # Usuário silencioso
        res_2 = scorer.score_performance(normal_curve, silent_curve)
        assert res_2.total_score.value == 0.0
        assert "warning" in res_2.details

        # Ambas vazias
        res_3 = scorer.score_performance(empty_curve, empty_curve)
        assert res_3.total_score.value == 0.0

    def test_single_point_curve(self) -> None:
        """Curva com apenas um ponto deve ser alinhada e calculada sem erros."""
        scorer = DtwPerformanceScorerAdapter()
        p1 = PitchCurve(
            points=(PitchPoint(timestamp=0.1, frequency_hz=440.0, midi_note=69.0),)
        )
        p2 = PitchCurve(
            points=(PitchPoint(timestamp=0.1, frequency_hz=440.0, midi_note=69.0),)
        )
        result = scorer.score_performance(p1, p2)
        assert result.total_score.value == 100.0
        assert result.details["aligned_points_count"] == 1

    @pytest.mark.parametrize(
        "pitch_w, timing_w, cents_tol, max_cents, timing_tol, max_timing",
        [
            (-0.1, 0.3, 50.0, 200.0, 0.15, 1.0),
            (0.7, -0.1, 50.0, 200.0, 0.15, 1.0),
            (0.0, 0.0, 50.0, 200.0, 0.15, 1.0),
            (0.7, 0.3, -1.0, 200.0, 0.15, 1.0),
            (0.7, 0.3, 50.0, 50.0, 0.15, 1.0),
            (0.7, 0.3, 50.0, 40.0, 0.15, 1.0),
            (0.7, 0.3, 50.0, 200.0, -0.1, 1.0),
            (0.7, 0.3, 50.0, 200.0, 0.15, 0.15),
            (0.7, 0.3, 50.0, 200.0, 0.15, 0.10),
        ],
    )
    def test_invalid_init_parameters_raise_domain_error(
        self,
        pitch_w: float,
        timing_w: float,
        cents_tol: float,
        max_cents: float,
        timing_tol: float,
        max_timing: float,
    ) -> None:
        """Construtor deve validar limites levantando InvalidScorerConfigError."""
        with pytest.raises(InvalidScorerConfigError):
            DtwPerformanceScorerAdapter(
                pitch_weight=pitch_w,
                timing_weight=timing_w,
                cents_tolerance=cents_tol,
                max_cents_error=max_cents,
                timing_tolerance_seconds=timing_tol,
                max_timing_deviation_seconds=max_timing,
            )

    def test_invalid_window_or_latency_raises_domain_error(self) -> None:
        """Valida que valores inválidos de janela ou latência lançam erro de domínio."""
        with pytest.raises(InvalidScorerConfigError):
            DtwPerformanceScorerAdapter(max_window_seconds=0.0)

        with pytest.raises(InvalidScorerConfigError):
            DtwPerformanceScorerAdapter(max_window_seconds=-1.0)

        with pytest.raises(InvalidScorerConfigError):
            DtwPerformanceScorerAdapter(max_latency_seconds=-0.5)
