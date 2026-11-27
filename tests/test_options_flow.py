"""The settings form of the built-in detection."""
import aiohttp
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bambu_lab_p1_spaghetti_detection.const import DOMAIN

ML = "http://ml:3333/p/"
VALID = {
    "enabled": True,
    "obico_host": "http://ml:3333",
    "obico_auth_token": "secret",
    "camera": "camera.printer",
    "print_status_sensor": "sensor.p_status",
    "stage_sensor": "sensor.p_stage",
    "auto_turn_on_light": True,
    "detection_frequency": "10",
}


async def _open(hass: HomeAssistant) -> tuple[MockConfigEntry, dict]:
    entry = MockConfigEntry(domain=DOMAIN, title="Spaghetti", data={}, options={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(entry.entry_id)
    return entry, result


async def test_form_is_shown_with_nothing_filled_in(hass: HomeAssistant) -> None:
    _, result = await _open(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    schema = {str(key): key for key in result["data_schema"].schema}
    # Turned off by default, and no address is suggested.
    assert schema["enabled"].default() is False
    assert schema["detection_frequency"].default() == "5"
    assert schema["auto_turn_on_light"].default() is True
    assert set(schema) == {
        "enabled", "obico_host", "obico_auth_token", "home_assistant_host", "camera", "camera_2",
        "print_status_sensor", "stage_sensor", "chamber_light", "auto_turn_on_light", "detection_frequency",
    }


async def test_it_can_be_saved_turned_off_without_checks(hass: HomeAssistant, aioclient_mock) -> None:
    entry, result = await _open(hass)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"enabled": False, "obico_host": "not an address", "detection_frequency": "5"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert not aioclient_mock.mock_calls
    assert entry.options["enabled"] is False


async def test_a_good_connection_is_saved(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(ML, json={"detections": []})
    entry, result = await _open(hass)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**VALID, "obico_host": "  http://ml:3333/  ", "obico_auth_token": " secret "}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    # The connection was tested with the secret, without a picture.
    assert aioclient_mock.mock_calls[0][3]["Authorization"] == "Bearer secret"
    assert "img" not in aioclient_mock.mock_calls[0][1].query
    # Stray spaces are removed, and what was left empty is not stored.
    assert entry.options["obico_host"] == "http://ml:3333/"
    assert entry.options["obico_auth_token"] == "secret"
    assert "camera_2" not in entry.options
    assert entry.options["detection_frequency"] == "10"
    assert hass.states.get("sensor.bambu_lab_p1_spaghetti_detection_status").state == "waiting"


async def test_what_is_missing_is_pointed_out(hass: HomeAssistant, aioclient_mock) -> None:
    _, result = await _open(hass)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"enabled": True, "detection_frequency": "5"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {
        "obico_host": "required",
        "obico_auth_token": "required",
        "camera": "required",
        "print_status_sensor": "required",
        "stage_sensor": "required",
    }
    assert not aioclient_mock.mock_calls


async def test_an_address_must_be_a_url(hass: HomeAssistant, aioclient_mock) -> None:
    _, result = await _open(hass)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**VALID, "obico_host": "192.168.1.50:3333", "home_assistant_host": "ha:8123"}
    )
    assert result["errors"] == {"obico_host": "invalid_url", "home_assistant_host": "invalid_url"}
    assert not aioclient_mock.mock_calls


@pytest.mark.parametrize(
    ("mock", "errors"),
    [
        ({"status": 401}, {"obico_auth_token": "invalid_auth"}),
        ({"status": 503}, {"obico_auth_token": "no_secret"}),
        ({"status": 500}, {"obico_host": "cannot_connect"}),
        ({"exc": aiohttp.ClientConnectionError()}, {"obico_host": "cannot_connect"}),
        ({"exc": TimeoutError()}, {"obico_host": "cannot_connect"}),
    ],
)
async def test_a_bad_connection_is_explained_and_nothing_is_saved(
    hass: HomeAssistant, aioclient_mock, mock: dict, errors: dict
) -> None:
    aioclient_mock.get(ML, **mock)
    entry, result = await _open(hass)
    result = await hass.config_entries.options.async_configure(result["flow_id"], VALID)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors
    assert entry.options == {}


async def test_the_form_keeps_what_was_typed_after_an_error(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(ML, status=401)
    _, result = await _open(hass)
    result = await hass.config_entries.options.async_configure(result["flow_id"], VALID)
    schema = {str(key): key for key in result["data_schema"].schema}
    assert schema["obico_host"].description == {"suggested_value": "http://ml:3333"}
    assert schema["detection_frequency"].default() == "10"
