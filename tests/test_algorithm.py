"""The scoring of the built-in detection, and that it matches the blueprint's."""
import random
from datetime import timedelta

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.bambu_lab_p1_spaghetti_detection import algorithm
from custom_components.bambu_lab_p1_spaghetti_detection.algorithm import State, Verdict
from custom_components.bambu_lab_p1_spaghetti_detection.const import NUMBER_KEYS

from .test_blueprint import Env


def test_score_is_the_sum_of_the_confidences() -> None:
    assert algorithm.score_of([]) == 0
    assert algorithm.score_of([["failure", 0.25, [0, 0, 1, 1]], ["failure", 0.5, [0, 0, 1, 1]]]) == pytest.approx(0.75)


def test_no_verdict_before_enough_pictures() -> None:
    state = State()
    for _ in range(algorithm.WARMUP_FRAMES - 1):
        assert algorithm.update(state, 0.9) is Verdict.WARMING_UP
    assert state.current_frame_number == algorithm.WARMUP_FRAMES - 1
    # The values of the verdict are left alone until then.
    assert state.adjusted_ewm_mean == 0
    assert state.thresh_warning == 0


def test_steady_score_is_not_a_failure() -> None:
    """Spaghetti that is there from the start is not a rise, so it is not reported."""
    state = State()
    verdicts = {algorithm.update(state, 0.8) for _ in range(120)}
    assert Verdict.FAILURE not in verdicts


def test_a_rise_after_a_normal_print_is_a_failure() -> None:
    state = State()
    for _ in range(60):
        assert algorithm.update(state, 0.0) is not Verdict.FAILURE
    verdicts = [algorithm.update(state, 0.9) for _ in range(30)]
    assert Verdict.FAILURE in verdicts
    assert state.normalized_p > 2 / 3


def test_resets() -> None:
    state = State(current_frame_number=50, lifetime_frame_number=500, ewm_mean=1, rolling_mean_short=1,
                  rolling_mean_long=1, normalized_p=1, adjusted_ewm_mean=1, p_sum=1, thresh_warning=0.5)
    algorithm.reset_for_new_print(state)
    assert (state.current_frame_number, state.ewm_mean, state.rolling_mean_short, state.rolling_mean_long,
            state.normalized_p, state.adjusted_ewm_mean, state.p_sum) == (0, 0, 0, 0, 0, 0, 0)
    # The lifetime count and the thresholds are kept.
    assert state.lifetime_frame_number == 500
    assert state.thresh_warning == 0.5


async def test_matches_the_blueprint_round_by_round(hass: HomeAssistant, freezer) -> None:
    """Run the blueprint and the built-in detection on the same scores and compare every value."""
    freezer.move_to("2026-11-26 12:00:05+00:00")
    env = Env(hass)
    rng = random.Random(7)
    # A quiet print, then a rise that is reported, then more rises that are held back for a minute.
    scores = [round(rng.uniform(0, 0.08), 4) for _ in range(45)] + [0.9] * 14 + [0.0] * 3

    state = State()
    last_notify = None
    reported = 0
    for number, score in enumerate(scores, start=1):
        env.scores = {env.printer_url: [score]}
        await env.run_detection()

        verdict = algorithm.update(state, score)
        if verdict is Verdict.FAILURE and (last_notify is None or dt_util.utcnow() - last_notify >= timedelta(minutes=1)):
            algorithm.reset_after_failure(state)
            last_notify = dt_util.utcnow()
            reported += 1

        for key in NUMBER_KEYS:
            assert env.number(key) == pytest.approx(getattr(state, key), rel=1e-9, abs=1e-9), (number, key)

    assert reported == 1
    assert len(env.notifications) == 1
