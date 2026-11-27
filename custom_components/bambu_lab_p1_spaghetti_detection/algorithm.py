"""The scoring of the spaghetti detection.

This is the calculation of the blueprint, in the same order and with the same numbers. A round
adds the score of one picture to a short and a long running average, and a failure is reported
when the score has risen clearly above what the print has looked like so far.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

# No verdict is given before this many pictures have been analysed in the current print.
WARMUP_FRAMES = 30

_EWM_ALPHA = 2 / (12 + 1)
_SHORT_WINDOW = 310
_LONG_WINDOW = 7200
_THRESHOLD_LOW = 0.38
_THRESHOLD_HIGH = 0.78


class Verdict(Enum):
    """What a round came to."""

    WARMING_UP = "warming_up"
    BELOW_LOW = "below_low"
    BELOW_HIGH = "below_high"
    FAILURE = "failure"


@dataclass
class State:
    """The values kept between rounds, which are the number entities of the integration."""

    current_frame_number: float = 0.0
    lifetime_frame_number: float = 0.0
    ewm_mean: float = 0.0
    adjusted_ewm_mean: float = 0.0
    p: float = 0.0
    normalized_p: float = 0.0
    p_sum: float = 0.0
    rolling_mean_diff: float = 0.0
    rolling_mean_long: float = 0.0
    rolling_mean_short: float = 0.0
    thresh_warning: float = 0.0
    thresh_failure: float = 0.0


def score_of(detections: list[Any]) -> float:
    """Return the sum of the confidences of the detections of one picture.

    A detection is [name, confidence, box].
    """
    return float(sum(detection[1] for detection in detections))


def update(state: State, score: float) -> Verdict:
    """Add the score of a new picture to the state and return the verdict of the round."""
    state.p_sum = score
    state.current_frame_number += 1
    state.lifetime_frame_number += 1

    state.ewm_mean = state.p_sum * _EWM_ALPHA + state.ewm_mean * (1 - _EWM_ALPHA)
    state.rolling_mean_short += (state.p_sum - state.rolling_mean_short) / (
        _SHORT_WINDOW if _SHORT_WINDOW <= state.current_frame_number else state.current_frame_number + 1
    )
    state.rolling_mean_long += (state.p_sum - state.rolling_mean_long) / (
        _LONG_WINDOW if _LONG_WINDOW <= state.lifetime_frame_number else state.lifetime_frame_number + 1
    )

    if state.current_frame_number < WARMUP_FRAMES:
        return Verdict.WARMING_UP

    state.adjusted_ewm_mean = state.ewm_mean - state.rolling_mean_long
    state.rolling_mean_diff = (state.rolling_mean_short - state.rolling_mean_long) * 3.8
    state.thresh_warning = min(0.78, max(0.33, state.rolling_mean_diff))
    state.thresh_failure = state.thresh_warning * 1.75
    state.p = state.ewm_mean - state.rolling_mean_long

    p, warning, failure = state.p, state.thresh_warning, state.thresh_failure
    if p > failure:
        state.normalized_p = min(
            1.0, max(2 / 3, (((p - failure) * (1 - 2 / 3)) / (failure * 1.5 - failure)) + 2 / 3)
        )
    elif p > warning:
        state.normalized_p = min(
            2 / 3,
            max(1 / 3, (((p - warning) * (2 / 3 - 1 / 3)) / (failure - warning)) + 1 / 3),
        )
    else:
        state.normalized_p = min(1 / 3, max(0, (p * 1 / 3) / warning))

    if state.adjusted_ewm_mean < _THRESHOLD_LOW:
        return Verdict.BELOW_LOW
    if state.adjusted_ewm_mean < _THRESHOLD_HIGH and state.adjusted_ewm_mean < state.rolling_mean_diff:
        return Verdict.BELOW_HIGH
    return Verdict.FAILURE


def reset_for_new_print(state: State) -> None:
    """Start over when a print starts. The lifetime count and the thresholds are kept."""
    _reset_running_values(state)


def reset_after_failure(state: State) -> None:
    """Start over after a failure has been reported."""
    _reset_running_values(state)


def _reset_running_values(state: State) -> None:
    state.current_frame_number = 0.0
    state.ewm_mean = 0.0
    state.rolling_mean_short = 0.0
    state.rolling_mean_long = 0.0
    state.normalized_p = 0.0
    state.adjusted_ewm_mean = 0.0
    state.p_sum = 0.0
