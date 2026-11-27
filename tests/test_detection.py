"""The built-in detection, run in a Home Assistant against a fake ML server."""
from datetime import timedelta

import pytest
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMockResponse

from custom_components.bambu_lab_p1_spaghetti_detection.const import DOMAIN, EVENT_FAILURE_DETECTED
from custom_components.bambu_lab_p1_spaghetti_detection.runtime import get_runtime

ML = "http://ml:3333/p/"
HA = "http://ha:8123"
PREFIX = "number.bambu_lab_p1_spaghetti_detection_"
STATUS = "sensor.bambu_lab_p1_spaghetti_detection_status"
OPTIONS = {
    "enabled": True,
    "obico_host": "http://ml:3333",
    "obico_auth_token": "secret",
    "home_assistant_host": HA,
    "camera": "camera.printer",
    "print_status_sensor": "sensor.p_status",
    "stage_sensor": "sensor.p_stage",
    "detection_frequency": "5",
}


def _detections(*confidences: float) -> dict:
    return {"detections": [["failure", c, [0, 0, 1, 1]] for c in confidences]}


def _number(hass: HomeAssistant, key: str) -> float:
    return float(hass.states.get(PREFIX + key).state)


def _status(hass: HomeAssistant) -> str:
    return hass.states.get(STATUS).state


async def _setup(hass: HomeAssistant, **options) -> MockConfigEntry:
    hass.states.async_set("sensor.p_status", "running")
    hass.states.async_set("sensor.p_stage", "idle")
    hass.states.async_set("camera.printer", "idle", {"entity_picture": "/api/camera_proxy/camera.printer?token=a"})
    hass.states.async_set("camera.second", "idle", {"entity_picture": "/api/camera_proxy/camera.second?token=b"})
    entry = MockConfigEntry(domain=DOMAIN, title="Spaghetti", data={}, options={**OPTIONS, **options})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _tick(hass: HomeAssistant, freezer, seconds: int = 5) -> None:
    """Let the time for one detection round pass."""
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def _images(aioclient_mock) -> list[str]:
    """The picture addresses the ML server was asked about, in order."""
    return [call[1].query["img"] for call in aioclient_mock.mock_calls if "img" in call[1].query]


async def test_nothing_happens_while_it_is_turned_off(hass: HomeAssistant, aioclient_mock, freezer) -> None:
    await _setup(hass, enabled=False)
    assert _status(hass) == "off"
    await _tick(hass, freezer)
    assert not aioclient_mock.mock_calls


async def test_missing_settings_are_reported(hass: HomeAssistant, aioclient_mock, freezer) -> None:
    await _setup(hass, camera=None, obico_host=None)
    state = hass.states.get(STATUS)
    assert state.state == "error"
    assert "camera" in state.attributes["error"] and "obico_host" in state.attributes["error"]
    await _tick(hass, freezer)
    assert not aioclient_mock.mock_calls


async def test_waits_while_no_print_is_running(hass: HomeAssistant, aioclient_mock, freezer) -> None:
    await _setup(hass)
    hass.states.async_set("sensor.p_status", "idle")
    await _tick(hass, freezer)
    assert _status(hass) == "waiting"
    assert not aioclient_mock.mock_calls


async def test_a_round_scores_the_picture_and_counts_it(hass: HomeAssistant, aioclient_mock, freezer) -> None:
    aioclient_mock.get(ML, json=_detections(0.25, 0.5))
    await _setup(hass)
    await _tick(hass, freezer)

    assert _images(aioclient_mock) == [f"{HA}/api/camera_proxy/camera.printer?token=a"]
    assert aioclient_mock.mock_calls[0][3]["Authorization"] == "Bearer secret"
    assert _number(hass, "p_sum") == pytest.approx(0.75)
    assert _number(hass, "current_frame_number") == 1
    assert _number(hass, "lifetime_frame_number") == 1
    state = hass.states.get(STATUS)
    assert state.state == "warming_up"
    assert state.attributes["score"] == pytest.approx(0.75)
    assert state.attributes["frames"] == 1


async def test_two_cameras_use_the_highest_score_and_skip_a_failing_one(
    hass: HomeAssistant, aioclient_mock, freezer
) -> None:
    async def answer(method, url, data):
        picture = url.query["img"]
        if "camera.printer" in picture:
            return AiohttpClientMockResponse(method, url, json=_detections(0.1))
        return AiohttpClientMockResponse(method, url, json=_detections(0.4))

    aioclient_mock.get(ML, side_effect=answer)
    await _setup(hass, camera_2="camera.second")
    await _tick(hass, freezer)
    assert len(_images(aioclient_mock)) == 2
    assert _number(hass, "p_sum") == pytest.approx(0.4)
    assert _number(hass, "current_frame_number") == 1  # one frame per round

    # The second camera has no picture, the first one is still used.
    hass.states.async_set("camera.second", "unavailable")
    await _tick(hass, freezer)
    assert _number(hass, "p_sum") == pytest.approx(0.1)
    state = hass.states.get(STATUS)
    assert state.state == "warming_up"
    assert "camera.second" in state.attributes["camera_errors"]


async def test_all_cameras_failing_is_an_error_that_counts_nothing(
    hass: HomeAssistant, aioclient_mock, freezer, caplog
) -> None:
    aioclient_mock.get(ML, status=401)
    await _setup(hass)
    await _tick(hass, freezer)
    await _tick(hass, freezer)

    state = hass.states.get(STATUS)
    assert state.state == "error"
    assert "rejected the auth token" in state.attributes["error"]
    assert _number(hass, "current_frame_number") == 0
    # The error is logged once, not in every round.
    assert caplog.text.count("Spaghetti detection: ") == 1

    # It recovers by itself.
    aioclient_mock.clear_requests()
    aioclient_mock.get(ML, json=_detections(0.1))
    await _tick(hass, freezer)
    assert _status(hass) == "warming_up"


async def test_the_light_is_turned_on(hass: HomeAssistant, aioclient_mock, freezer) -> None:
    calls: list[ServiceCall] = []

    async def turn_on(call: ServiceCall) -> None:
        calls.append(call)

    hass.services.async_register("light", "turn_on", turn_on)
    aioclient_mock.get(ML, json=_detections())
    await _setup(hass, chamber_light="light.p_light")
    hass.states.async_set("light.p_light", "off")
    await _tick(hass, freezer)
    assert [call.data["entity_id"] for call in calls] == ["light.p_light"]

    calls.clear()
    hass.states.async_set("light.p_light", "on")
    await _tick(hass, freezer)
    assert not calls


async def test_a_new_print_starts_over(hass: HomeAssistant, aioclient_mock, freezer) -> None:
    aioclient_mock.get(ML, json=_detections(0.3))
    await _setup(hass)
    await _tick(hass, freezer)
    await _tick(hass, freezer)
    assert _number(hass, "current_frame_number") == 2

    hass.states.async_set("sensor.p_stage", "printing")
    await hass.async_block_till_done()
    assert _number(hass, "current_frame_number") == 0
    assert _number(hass, "ewm_mean") == 0
    assert _number(hass, "p_sum") == 0
    # The lifetime count is kept.
    assert _number(hass, "lifetime_frame_number") == 2

    # Staying in the same stage is not a new print.
    await _tick(hass, freezer)
    hass.states.async_set("sensor.p_stage", "printing", {"other": "attribute"})
    await hass.async_block_till_done()
    assert _number(hass, "current_frame_number") == 1


async def test_a_failure_is_reported_once_a_minute(hass: HomeAssistant, aioclient_mock, freezer) -> None:
    events = async_capture_events(hass, EVENT_FAILURE_DETECTED)
    aioclient_mock.get(ML, json=_detections(0.9))
    entry = await _setup(hass)

    # A long quiet print, then a rise.
    numbers = get_runtime(hass, entry.entry_id).numbers
    numbers["current_frame_number"]._attr_native_value = 40
    numbers["lifetime_frame_number"]._attr_native_value = 40
    numbers["ewm_mean"]._attr_native_value = 5
    await _tick(hass, freezer)

    assert len(events) == 1
    assert events[0].data["camera"] == "camera.printer"
    assert events[0].data["confidence"] > 2 / 3
    # The running values start over and the time is kept.
    assert _number(hass, "current_frame_number") == 0
    assert _number(hass, "p_sum") == 0
    last = dt_util.parse_datetime(hass.states.get("datetime.bambu_lab_p1_spaghetti_detection_last_notify_time").state)
    assert last == dt_util.utcnow().replace(microsecond=0)

    # Another rise within the minute is not reported.
    numbers["current_frame_number"]._attr_native_value = 40
    numbers["ewm_mean"]._attr_native_value = 5
    await _tick(hass, freezer)
    assert len(events) == 1

    numbers["current_frame_number"]._attr_native_value = 40
    numbers["ewm_mean"]._attr_native_value = 5
    await _tick(hass, freezer, seconds=60)
    assert len(events) == 2


async def test_values_survive_a_restart(hass: HomeAssistant, aioclient_mock) -> None:
    from homeassistant.core import State

    def stored(value: float) -> dict:
        return {
            "native_max_value": 1e16,
            "native_min_value": -1e15,
            "native_step": 1e-9,
            "native_unit_of_measurement": None,
            "native_value": value,
        }

    mock_restore_cache_with_extra_data(
        hass,
        (
            (State(PREFIX + "lifetime_frame_number", "123.0"), stored(123.0)),
            (State(PREFIX + "ewm_mean", "0.25"), stored(0.25)),
            (State("datetime.bambu_lab_p1_spaghetti_detection_last_notify_time", "2026-11-26T11:59:30+00:00"), {}),
        ),
    )
    await _setup(hass, enabled=False)
    assert _number(hass, "lifetime_frame_number") == 123
    assert _number(hass, "ewm_mean") == 0.25
    assert hass.states.get("datetime.bambu_lab_p1_spaghetti_detection_last_notify_time").state == "2026-11-26T11:59:30+00:00"


async def test_changing_the_settings_restarts_the_detection(hass: HomeAssistant, aioclient_mock, freezer) -> None:
    aioclient_mock.get(ML, json=_detections(0.2))
    entry = await _setup(hass, enabled=False)
    assert _status(hass) == "off"

    hass.config_entries.async_update_entry(entry, options={**OPTIONS, "enabled": True})
    await hass.async_block_till_done()
    assert _status(hass) == "waiting"
    await _tick(hass, freezer)
    assert _number(hass, "current_frame_number") == 1

    # Turned off again, the timer is gone.
    hass.config_entries.async_update_entry(entry, options={**OPTIONS, "enabled": False})
    await hass.async_block_till_done()
    aioclient_mock.mock_calls.clear()
    await _tick(hass, freezer)
    assert not aioclient_mock.mock_calls
    assert _status(hass) == "off"


async def test_the_address_falls_back_to_the_internal_url(hass: HomeAssistant, aioclient_mock, freezer) -> None:
    hass.config.internal_url = "http://internal:8123"
    aioclient_mock.get(ML, json=_detections())
    await _setup(hass, home_assistant_host=None)
    await _tick(hass, freezer)
    assert _images(aioclient_mock) == ["http://internal:8123/api/camera_proxy/camera.printer?token=a"]


async def test_the_entities_have_the_ids_the_blueprint_uses(hass: HomeAssistant, aioclient_mock) -> None:
    await _setup(hass, enabled=False)
    registry = async_get_entity_registry(hass)
    assert registry.async_get(PREFIX + "p_sum") is not None
    assert registry.async_get("datetime.bambu_lab_p1_spaghetti_detection_last_notify_time") is not None
    assert registry.async_get(STATUS) is not None


async def test_a_turned_on_blueprint_automation_is_pointed_out(hass: HomeAssistant, aioclient_mock, freezer) -> None:
    from types import SimpleNamespace

    from homeassistant.components.automation import DATA_COMPONENT

    aioclient_mock.get(ML, json=_detections())
    hass.data[DATA_COMPONENT] = SimpleNamespace(
        entities=[
            SimpleNamespace(
                entity_id="automation.spaghetti",
                raw_config={"use_blueprint": {"path": "x.yaml", "input": {"obico_host": "x", "printer_camera": "y"}}},
            )
        ]
    )
    hass.states.async_set("automation.spaghetti", "on")
    await _setup(hass)
    assert "blueprint" in hass.states.get(STATUS).attributes["warning"]

    hass.states.async_set("automation.spaghetti", "off")
    await _tick(hass, freezer)
    assert "warning" not in hass.states.get(STATUS).attributes


async def test_the_predict_service_still_works(hass: HomeAssistant, aioclient_mock) -> None:
    from homeassistant.exceptions import HomeAssistantError

    aioclient_mock.get(ML, json=_detections(0.3))
    await _setup(hass, enabled=False)
    data = {"obico_host": "http://ml:3333/", "obico_auth_token": "secret", "image_url": "http://ha/pic?token=x&y=1"}
    result = await hass.services.async_call(DOMAIN, "predict", data, blocking=True, return_response=True)
    assert result == {"result": _detections(0.3)}
    assert aioclient_mock.mock_calls[0][1].query["img"] == "http://ha/pic?token=x&y=1"

    aioclient_mock.clear_requests()
    aioclient_mock.get(ML, status=401)
    with pytest.raises(HomeAssistantError, match="rejected the auth token"):
        await hass.services.async_call(DOMAIN, "predict", data, blocking=True, return_response=True)
