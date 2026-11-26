"""Run the detection steps of the blueprint against fake services.

The blueprint is loaded the way Home Assistant loads it, its inputs are filled in, and the
detection trigger is run with stand-ins for the ML server and the number entities.
"""
from pathlib import Path

import pytest
from homeassistant.components.blueprint import models, schemas
from homeassistant.core import Context, HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, script
from homeassistant.util.yaml import loader

BLUEPRINT = Path(__file__).parent.parent / "blueprints" / "spaghetti_detection.yaml"
PREFIX = "number.bambu_lab_p1_spaghetti_detection_"
NUMBERS = (
    "current_frame_number", "lifetime_frame_number", "ewm_mean", "adjusted_ewm_mean", "p", "normalized_p",
    "p_sum", "rolling_mean_diff", "rolling_mean_long", "rolling_mean_short", "thresh_warning", "thresh_failure",
)
INPUTS = {
    "home_assistant_host": "http://ha:8123",
    "obico_host": "http://ml:3333",
    "obico_auth_token": "secret",
    "printer_print_status_sensor": "sensor.p_status",
    "printer_current_stage_sensor": "sensor.p_stage",
    "printer_camera": "camera.printer",
    "printer_chamber_light": "light.p_light",
    "notification_service": "notify.test",
}


class Env:
    """The fake services and what they recorded."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.scores: dict[str, list[float] | None] = {}  # image url -> confidences, None = fails
        self.predictions: list[str] = []
        self.notifications: list[dict] = []

        async def predict(call: ServiceCall):
            url = call.data["image_url"]
            self.predictions.append(url)
            confidences = self.scores.get(url, [])
            if confidences is None:
                raise HomeAssistantError("Could not reach the Obico ML server")
            return {"result": {"detections": [["failure", c, [0, 0, 1, 1]] for c in confidences]}}

        async def set_value(call: ServiceCall):
            targets = call.data["entity_id"]
            for entity_id in [targets] if isinstance(targets, str) else targets:
                if "datetime" in call.data:
                    hass.states.async_set(entity_id, str(call.data["datetime"]))
                else:
                    hass.states.async_set(entity_id, str(call.data["value"]))

        async def notify(call: ServiceCall):
            self.notifications.append(dict(call.data))

        async def ignore(call: ServiceCall):
            return None

        hass.services.async_register(
            "bambu_lab_p1_spaghetti_detection", "predict", predict, supports_response=SupportsResponse.ONLY
        )
        hass.services.async_register("number", "set_value", set_value)
        hass.services.async_register("datetime", "set_value", set_value)
        hass.services.async_register("notify", "test", notify)
        hass.services.async_register("light", "turn_on", ignore)
        hass.services.async_register("button", "press", ignore)

        hass.states.async_set("sensor.p_status", "running")
        hass.states.async_set("light.p_light", "on")
        hass.states.async_set("camera.printer", "idle", {"entity_picture": "/api/camera_proxy/camera.printer?token=a"})
        hass.states.async_set("camera.second", "idle", {"entity_picture": "/api/camera_proxy/camera.second?token=b"})
        for key in NUMBERS:
            hass.states.async_set(PREFIX + key, "0")
        hass.states.async_set("datetime.bambu_lab_p1_spaghetti_detection_last_notify_time", "1970-01-01T00:00:00+00:00")

    @property
    def printer_url(self) -> str:
        return "http://ha:8123/api/camera_proxy/camera.printer?token=a"

    @property
    def second_url(self) -> str:
        return "http://ha:8123/api/camera_proxy/camera.second?token=b"

    def number(self, key: str) -> float:
        return float(self.hass.states.get(PREFIX + key).state)

    async def run_detection(self, **extra_inputs) -> None:
        """Run one detection round of the automation."""
        hass = self.hass
        data = loader.parse_yaml(BLUEPRINT.read_text())
        blueprint = models.Blueprint(data, expected_domain="automation", path="x.yaml", schema=schemas.BLUEPRINT_SCHEMA)
        inputs = models.BlueprintInputs(
            blueprint, {"use_blueprint": {"path": "x.yaml", "input": {**INPUTS, **extra_inputs}}}
        )
        inputs.validate()
        config = inputs.async_substitute()
        variables = cv.SCRIPT_VARIABLES_SCHEMA(config["variables"]).async_render(hass, {})
        runner = script.Script(hass, cv.SCRIPT_SCHEMA(config["action"]), "test", "test")
        await runner.async_run(
            {**variables, "trigger": {"platform": "time_pattern", "id": "BAMBU_LAB_DETECTION_TRIGGER"}},
            Context(),
        )
        await hass.async_block_till_done()


@pytest.fixture
def env(hass: HomeAssistant, freezer) -> Env:
    # The detection only runs when the second is a multiple of the detection frequency.
    freezer.move_to("2026-11-26 12:00:05+00:00")
    return Env(hass)


async def test_blueprint_is_valid_with_and_without_optional_inputs(hass: HomeAssistant) -> None:
    data = loader.parse_yaml(BLUEPRINT.read_text())
    blueprint = models.Blueprint(data, expected_domain="automation", path="x.yaml", schema=schemas.BLUEPRINT_SCHEMA)
    for extra in ({}, {"printer_camera_2": "camera.second"}):
        inputs = models.BlueprintInputs(
            blueprint, {"use_blueprint": {"path": "x.yaml", "input": {**INPUTS, **extra}}}
        )
        inputs.validate()
        config = inputs.async_substitute()
        cv.SCRIPT_SCHEMA(config["action"])
        cv.SCRIPT_VARIABLES_SCHEMA(config["variables"])


async def test_one_camera_works_as_before(env: Env) -> None:
    env.scores = {env.printer_url: [0.25, 0.5]}
    await env.run_detection()
    assert env.predictions == [env.printer_url]
    assert env.number("p_sum") == pytest.approx(0.75)
    assert env.number("current_frame_number") == 1
    assert env.number("lifetime_frame_number") == 1


async def test_one_camera_failing_stops_the_run(env: Env) -> None:
    env.scores = {env.printer_url: None}
    with pytest.raises(HomeAssistantError):
        await env.run_detection()
    assert env.number("current_frame_number") == 0


async def test_two_cameras_use_the_highest_score(env: Env) -> None:
    env.scores = {env.printer_url: [0.1], env.second_url: [0.2, 0.3]}
    await env.run_detection(printer_camera_2="camera.second")
    assert env.predictions == [env.printer_url, env.second_url]
    assert env.number("p_sum") == pytest.approx(0.5)
    # One frame is counted per round, not per camera.
    assert env.number("current_frame_number") == 1

    env.scores = {env.printer_url: [0.6], env.second_url: [0.2]}
    await env.run_detection(printer_camera_2="camera.second")
    assert env.number("p_sum") == pytest.approx(0.6)


async def test_two_cameras_continue_when_one_fails(env: Env) -> None:
    env.scores = {env.printer_url: None, env.second_url: [0.4]}
    await env.run_detection(printer_camera_2="camera.second")
    assert env.number("p_sum") == pytest.approx(0.4)
    assert env.number("current_frame_number") == 1

    env.scores = {env.printer_url: [0.3], env.second_url: None}
    await env.run_detection(printer_camera_2="camera.second")
    assert env.number("p_sum") == pytest.approx(0.3)
    assert env.number("current_frame_number") == 2


async def test_two_cameras_failing_ends_the_run_without_counting(env: Env) -> None:
    env.scores = {env.printer_url: None, env.second_url: None}
    # The run is stopped with an error (shown in the automation trace), nothing is counted.
    await env.run_detection(printer_camera_2="camera.second")
    assert env.predictions == [env.printer_url, env.second_url]
    assert env.number("p_sum") == 0
    assert env.number("current_frame_number") == 0
    assert not env.notifications


def _prepare_for_notification(env: Env) -> None:
    """A long running print whose score has jumped well above its average."""
    env.hass.states.async_set(PREFIX + "current_frame_number", "40")
    env.hass.states.async_set(PREFIX + "lifetime_frame_number", "40")
    env.hass.states.async_set(PREFIX + "ewm_mean", "5")


async def test_notification_uses_the_picture_of_the_camera_with_the_highest_score(env: Env) -> None:
    _prepare_for_notification(env)
    env.scores = {env.printer_url: [0.1], env.second_url: [0.9]}
    await env.run_detection(printer_camera_2="camera.second")
    assert len(env.notifications) == 1
    assert env.notifications[0]["data"]["image"] == env.second_url

    env.notifications.clear()
    env.hass.states.async_set("datetime.bambu_lab_p1_spaghetti_detection_last_notify_time", "1970-01-01T00:00:00+00:00")
    _prepare_for_notification(env)
    env.scores = {env.printer_url: [0.9], env.second_url: [0.1]}
    await env.run_detection(printer_camera_2="camera.second")
    assert env.notifications[0]["data"]["image"] == env.printer_url


async def test_notification_with_one_camera_uses_the_printer_camera(env: Env) -> None:
    _prepare_for_notification(env)
    env.scores = {env.printer_url: [0.9]}
    await env.run_detection()
    assert len(env.notifications) == 1
    assert env.notifications[0]["data"]["image"] == env.printer_url
