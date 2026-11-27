"""The built-in spaghetti detection, which does the work of the blueprint.

While the printer is printing, a picture of the camera is sent to the Obico ML server every few
seconds. The scores are added to the running averages in algorithm.py, which are kept in the number
entities of the integration, and a failure is reported as an event.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.util import dt as dt_util

from . import algorithm
from .const import (
    CONF_AUTO_LIGHT,
    CONF_CAMERA,
    CONF_CAMERA_2,
    CONF_ENABLED,
    CONF_FREQUENCY,
    CONF_HA_HOST,
    CONF_LIGHT,
    CONF_OBICO_HOST,
    CONF_OBICO_TOKEN,
    CONF_PRINT_STATUS,
    CONF_STAGE,
    DEFAULT_FREQUENCY,
    EVENT_FAILURE_DETECTED,
    NUMBER_KEYS,
    STATUS_ERROR,
    STATUS_MONITORING,
    STATUS_OFF,
    STATUS_WAITING,
    STATUS_WARMING_UP,
)
from .dashboard import blueprint_automation_is_on
from .ml_client import MLServerError, async_predict
from .runtime import Runtime

_LOGGER = logging.getLogger(__name__)

# The print status that means a print is under way.
PRINT_RUNNING = "running"
# The stage that a print starts with.
STAGE_PRINTING = "printing"
# A failure is not reported again within this time.
REPORT_INTERVAL = timedelta(minutes=1)

REQUIRED_OPTIONS = (CONF_OBICO_HOST, CONF_OBICO_TOKEN, CONF_CAMERA, CONF_PRINT_STATUS, CONF_STAGE)

# The values that change in every round, and those that only change once enough pictures are in.
ROUND_KEYS = (
    "p_sum", "current_frame_number", "lifetime_frame_number", "ewm_mean", "rolling_mean_short",
    "rolling_mean_long",
)
VERDICT_KEYS = ("adjusted_ewm_mean", "rolling_mean_diff", "thresh_warning", "thresh_failure", "p", "normalized_p")
RESET_KEYS = (
    "current_frame_number", "ewm_mean", "rolling_mean_short", "rolling_mean_long", "normalized_p",
    "adjusted_ewm_mean", "p_sum",
)


class DetectionEngine:
    """Runs the detection of one config entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, runtime: Runtime) -> None:
        self.hass = hass
        self._entry = entry
        self._runtime = runtime
        self._lock = asyncio.Lock()
        self._unsubscribers: list[Any] = []
        self._last_error: str | None = None

    @property
    def _options(self) -> dict[str, Any]:
        return self._entry.options

    @property
    def enabled(self) -> bool:
        return bool(self._options.get(CONF_ENABLED))

    @property
    def cameras(self) -> list[str]:
        return [camera for camera in (self._options.get(CONF_CAMERA), self._options.get(CONF_CAMERA_2)) if camera]

    # -- start and stop ---------------------------------------------------------------------------

    async def async_start(self) -> None:
        """Start the detection when it is turned on in the settings."""
        if not self.enabled:
            self._set_status(STATUS_OFF)
            return
        if missing := [key for key in REQUIRED_OPTIONS if not self._options.get(key)]:
            self._set_status(STATUS_ERROR, error=f"Not set up, missing: {', '.join(missing)}")
            return

        self._unsubscribers.append(
            async_track_state_change_event(self.hass, [self._options[CONF_STAGE]], self._async_stage_changed)
        )
        seconds = int(self._options.get(CONF_FREQUENCY) or DEFAULT_FREQUENCY)
        self._unsubscribers.append(
            async_track_time_interval(self.hass, self._async_round, timedelta(seconds=seconds))
        )
        self._set_status(STATUS_WAITING)

    async def async_stop(self) -> None:
        """Stop the detection."""
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()

    # -- a new print ------------------------------------------------------------------------------

    @callback
    def _async_stage_changed(self, event: Event) -> None:
        """Start over when a print starts."""
        new, old = event.data.get("new_state"), event.data.get("old_state")
        if new is None or new.state != STAGE_PRINTING:
            return
        if old is not None and old.state == STAGE_PRINTING:
            return
        self.hass.async_create_task(self._async_new_print())

    async def _async_new_print(self) -> None:
        async with self._lock:
            state = self._read_state()
            algorithm.reset_for_new_print(state)
            await self._async_write(state, RESET_KEYS)
            await self._async_ensure_light()

    # -- one round --------------------------------------------------------------------------------

    async def _async_round(self, _now: Any) -> None:
        """Analyse the pictures of the cameras once, if a print is under way."""
        if self._lock.locked():
            # The previous round is still going, the next one is skipped.
            return
        async with self._lock:
            status = self.hass.states.get(self._options[CONF_PRINT_STATUS])
            if status is None or status.state != PRINT_RUNNING:
                self._set_status(STATUS_WAITING)
                return

            await self._async_ensure_light()
            try:
                score, camera, scores, errors = await self._async_score()
            except MLServerError as err:
                self._report_error(str(err))
                return
            self._last_error = None

            state = self._read_state()
            verdict = algorithm.update(state, score)
            await self._async_write(state, ROUND_KEYS)
            if verdict is not algorithm.Verdict.WARMING_UP:
                await self._async_write(state, VERDICT_KEYS)

            self._set_status(
                STATUS_WARMING_UP if verdict is algorithm.Verdict.WARMING_UP else STATUS_MONITORING,
                last_run=dt_util.utcnow().isoformat(),
                score=score,
                frames=state.current_frame_number,
                camera_scores=scores,
                camera_errors=errors or None,
            )
            if verdict is algorithm.Verdict.FAILURE:
                await self._async_failure(state, camera)

    async def _async_score(self) -> tuple[float, str, dict[str, float], dict[str, str]]:
        """Return the highest score of the cameras and the camera it came from.

        A camera that fails is skipped as long as another one works.
        """
        host = self._options[CONF_OBICO_HOST]
        token = self._options[CONF_OBICO_TOKEN]
        scores: dict[str, float] = {}
        errors: dict[str, str] = {}
        for camera in self.cameras:
            try:
                answer = await async_predict(self.hass, host, token, self._image_url(camera))
                scores[camera] = algorithm.score_of(answer.get("detections") or [])
            except MLServerError as err:
                errors[camera] = str(err)
            except (TypeError, IndexError, ValueError) as err:
                errors[camera] = f"The Obico ML server gave an answer that was not understood: {err}"
        if not scores:
            raise MLServerError("; ".join(errors.values()) or "No camera is set")
        best = max(scores, key=lambda camera: scores[camera])
        return scores[best], best, scores, errors

    def _image_url(self, camera: str) -> str:
        """Return the address the ML server fetches the picture of a camera from."""
        state = self.hass.states.get(camera)
        picture = state.attributes.get("entity_picture") if state is not None else None
        if not picture:
            raise MLServerError(f"The camera {camera} has no picture at the moment")
        if picture.startswith(("http://", "https://")):
            return picture
        return f"{self._base_url()}{picture}"

    def _base_url(self) -> str:
        configured = (self._options.get(CONF_HA_HOST) or "").strip()
        if configured:
            return configured.rstrip("/")
        try:
            return get_url(self.hass, allow_external=False, allow_cloud=False)
        except NoURLAvailableError as err:
            raise MLServerError(
                "Home Assistant has no internal address to give the ML server. "
                "Set the Home Assistant Host in the settings of the integration."
            ) from err

    # -- a failure --------------------------------------------------------------------------------

    async def _async_failure(self, state: algorithm.State, camera: str) -> None:
        """Report a failure, unless one was reported a moment ago."""
        now = dt_util.utcnow()
        last_notify = self._runtime.last_notify
        last = last_notify.native_value if last_notify is not None else None
        if last is not None and now - last < REPORT_INTERVAL:
            return

        self.hass.bus.async_fire(
            EVENT_FAILURE_DETECTED, {"confidence": state.normalized_p, "camera": camera}
        )
        algorithm.reset_after_failure(state)
        await self._async_write(state, RESET_KEYS)
        if last_notify is not None:
            await last_notify.async_set_value(now)

    # -- helpers ----------------------------------------------------------------------------------

    async def _async_ensure_light(self) -> None:
        """Turn the chamber light on if that is wanted, so the pictures are good."""
        light = self._options.get(CONF_LIGHT)
        if not light or not self._options.get(CONF_AUTO_LIGHT, True):
            return
        state = self.hass.states.get(light)
        if state is not None and state.state == "off":
            await self.hass.services.async_call("light", "turn_on", {"entity_id": light}, blocking=False)

    def _read_state(self) -> algorithm.State:
        state = algorithm.State()
        for key in NUMBER_KEYS:
            entity = self._runtime.numbers.get(key)
            value = entity.native_value if entity is not None else None
            setattr(state, key, float(value) if value is not None else 0.0)
        return state

    async def _async_write(self, state: algorithm.State, keys: tuple[str, ...]) -> None:
        for key in keys:
            entity = self._runtime.numbers.get(key)
            if entity is not None:
                await entity.async_set_native_value(getattr(state, key))

    def _set_status(self, status: str, **attributes: Any) -> None:
        if self._runtime.status is not None:
            warning = (
                "The automation made from the blueprint is turned on too. Turn it off, or both "
                "update the same values."
                if blueprint_automation_is_on(self.hass)
                else None
            )
            self._runtime.status.async_set_status(status, warning=warning, **attributes)

    def _report_error(self, message: str) -> None:
        """Show an error in the status and log it once, not in every round."""
        if message != self._last_error:
            _LOGGER.warning("Spaghetti detection: %s", message)
        self._last_error = message
        self._set_status(STATUS_ERROR, error=message, last_run=dt_util.utcnow().isoformat())
