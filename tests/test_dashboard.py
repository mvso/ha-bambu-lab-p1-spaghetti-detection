"""Tests for the generated printer dashboard."""
from pathlib import Path
from types import SimpleNamespace

import pytest
from homeassistant.components.automation import DATA_COMPONENT as AUTOMATION_DATA_COMPONENT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er, template
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bambu_lab_p1_spaghetti_detection.dashboard import (
    DASHBOARD_URL_PATH,
    DOMAIN,
    build_dashboard_config,
)

SERIAL = "01P00A123456789"
AMS_SERIAL = "006A0000001"


def _all_entities(config: dict) -> set[str]:
    """Collect every entity ID referenced by the cards of a dashboard."""
    found: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            if isinstance(node.get("entity"), str):
                found.add(node["entity"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(config)
    return found


def _cards(view: dict) -> list[dict]:
    """All top-level cards of a sections view, from left to right."""
    return [card for section in view["sections"] for card in section["cards"]]


def _add_printer(hass: HomeAssistant, with_ams: bool = True, with_camera: bool = True) -> MockConfigEntry:
    """Register a printer the way the Bambu Lab integration does, with renamed entities."""
    entry = MockConfigEntry(domain="bambu_lab", title=f"P1S_{SERIAL}", data={"serial": SERIAL})
    entry.add_to_hass(hass)
    entities = er.async_get(hass)
    devices = dr.async_get(hass)

    def add(domain: str, unique_id: str, object_id: str, device_id: str | None = None, **kwargs):
        entities.async_get_or_create(
            domain, "bambu_lab", unique_id, suggested_object_id=object_id,
            config_entry=entry, device_id=device_id, **kwargs,
        )

    # Entity IDs are deliberately unrelated to the keys: only unique IDs may be relied on.
    for key in ("print_progress", "subtask_name", "print_status", "stage", "remaining_time",
                "nozzle_temp", "target_nozzle_temp", "bed_temp", "wifi_signal", "active_tray"):
        add("sensor", f"{SERIAL}_{key}", f"min_printer_{key}_omdopt")
    add("sensor", f"{SERIAL}_end_time", "disabled_end_time", disabled_by=er.RegistryEntryDisabler.USER)
    add("binary_sensor", f"{SERIAL}_online", "min_printer_tilkoblet")
    add("binary_sensor", f"{SERIAL}_hms", "min_printer_hms")
    add("light", f"{SERIAL}_chamber_light", "min_printer_lys")
    if with_camera:
        add("camera", f"{SERIAL}_camera", "min_printer_kamera")
    else:
        add("image", f"{SERIAL}_p1p_camera", "min_printer_bilde")

    if with_ams:
        ams = devices.async_get_or_create(
            config_entry_id=entry.entry_id, identifiers={("bambu_lab", AMS_SERIAL)}, name=f"P1S_{SERIAL}_AMS_1"
        )
        prefix = f"P1S_{SERIAL}_AMS_{AMS_SERIAL}"
        for slot in (1, 2, 3, 4):
            add("sensor", f"{prefix}_tray_{slot}", f"ams_spor_{slot}", ams.id)
        add("sensor", f"{prefix}_humidity_index", "ams_fukt", ams.id)
        add("sensor", f"P1S_{SERIAL}_ExternalSpool_external_spool", "ekstern_spole")
    return entry


async def test_dashboard_uses_registry_entities(hass: HomeAssistant) -> None:
    _add_printer(hass)
    config = build_dashboard_config(hass)

    assert [view["path"] for view in config["views"]] == ["printer", "filament"]
    entities = _all_entities(config)
    assert "sensor.min_printer_print_status_omdopt" in entities
    assert "camera.min_printer_kamera" in entities
    assert "light.min_printer_lys" in entities
    assert "sensor.ams_fukt" in entities
    # Disabled entities and entities the printer does not have are left out.
    assert "sensor.disabled_end_time" not in entities
    assert not any("chamber_temp" in entity for entity in entities)
    # Every referenced entity exists in the registry.
    registry = er.async_get(hass)
    assert all(registry.async_get(entity) for entity in entities)


async def test_filament_table_renders(hass: HomeAssistant) -> None:
    _add_printer(hass)
    hass.states.async_set("sensor.ams_spor_1", "Bambu PLA Basic",
                          {"color": "#FF0000FF", "active": True, "empty": False, "type": "PLA", "remain": 72})
    hass.states.async_set("sensor.ams_spor_2", "Generic PETG",
                          {"color": "#00AA55FF", "active": False, "empty": False, "type": "PETG", "remain": -1})
    hass.states.async_set("sensor.ams_spor_3", "Empty", {"color": "#00000000", "empty": True, "remain": 0})
    config = build_dashboard_config(hass)
    filament = next(view for view in config["views"] if view["path"] == "filament")
    tables = [card for card in filament["cards"] if card["type"] == "markdown"]
    assert [card["title"] for card in tables] == ["AMS 1", "External spool"]

    rendered = template.Template(tables[0]["content"], hass).async_render()
    lines = rendered.splitlines()
    assert lines[2] == '| <font color="#FF0000">⬤</font> | 1 ▶ | Bambu PLA Basic | PLA | 72 % |'
    assert lines[3] == '| <font color="#00AA55">⬤</font> | 2 | Generic PETG | PETG | – |'
    assert lines[4] == '| <font color="#000000">⬤</font> | 3 | Empty | – | – |'
    assert lines[5] == '| <font color="#888888">⬤</font> | 4 | – | – | – |'
    template.Template(tables[1]["content"], hass).async_render()


async def test_printer_without_ams_or_camera_entity(hass: HomeAssistant) -> None:
    _add_printer(hass, with_ams=False, with_camera=False)
    config = build_dashboard_config(hass)
    assert [view["path"] for view in config["views"]] == ["printer"]
    picture = _cards(config["views"][0])[0]
    assert picture["entity"] == "image.min_printer_bilde"
    assert "camera_view" not in picture
    # The overview picture needs a camera entity, so it is left out here.
    assert not any(card["type"] == "picture-elements" for card in _cards(config["views"][0]))


async def test_no_printer(hass: HomeAssistant) -> None:
    config = build_dashboard_config(hass)
    assert len(config["views"]) == 1
    assert config["views"][0]["cards"][0]["type"] == "markdown"


async def test_norwegian_labels(hass: HomeAssistant) -> None:
    hass.config.language = "nb"
    _add_printer(hass)
    config = build_dashboard_config(hass)
    assert config["title"] == "3D-printer"
    gauge = next(
        card["cards"][0] for card in _cards(config["views"][0])
        if card["type"] == "vertical-stack" and card["cards"][0]["type"] == "gauge"
    )
    assert gauge["name"] == "Fremdrift"
    overview = next(card for card in _cards(config["views"][0]) if card["type"] == "picture-elements")
    labels = [e for e in overview["elements"] if e["type"] == "state-label"]
    assert labels[2]["prefix"] == "Fremdrift: "


async def test_dashboard_is_registered_and_served(hass: HomeAssistant, hass_ws_client) -> None:
    """The dashboard appears as a panel and is served through the Lovelace API."""
    _add_printer(hass)
    assert await async_setup_component(hass, "lovelace", {})
    entry = MockConfigEntry(domain=DOMAIN, title="Spaghetti")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "get_panels"})
    panels = (await client.receive_json())["result"]
    assert panels[DASHBOARD_URL_PATH]["component_name"] == "lovelace"
    assert panels[DASHBOARD_URL_PATH]["title"] == "3D printer"

    await client.send_json({"id": 2, "type": "lovelace/config", "url_path": DASHBOARD_URL_PATH})
    response = await client.receive_json()
    assert response["success"]
    entities = _all_entities(response["result"])
    assert "sensor.min_printer_print_status_omdopt" in entities
    # The integration's own detection values are included once its entities exist.
    assert f"number.{DOMAIN}_normalized_p" in entities

    # The fallback action returns the same dashboard, ready to paste.
    result = await hass.services.async_call(DOMAIN, "generate_dashboard", {}, blocking=True, return_response=True)
    assert result == response["result"]

    assert await hass.config_entries.async_unload(entry.entry_id)
    await client.send_json({"id": 3, "type": "get_panels"})
    assert DASHBOARD_URL_PATH not in (await client.receive_json())["result"]


def _automations(hass: HomeAssistant, *inputs: dict) -> None:
    """Make Home Assistant report automations made from the blueprint with these inputs."""
    hass.data[AUTOMATION_DATA_COMPONENT] = SimpleNamespace(
        entities=[
            SimpleNamespace(raw_config={"use_blueprint": {"path": "x.yaml", "input": dict(i)}}) for i in inputs
        ]
    )


BLUEPRINT_INPUTS = {"obico_host": "http://ml:3333", "printer_camera": "camera.min_printer_kamera"}


async def test_inputs_are_found_where_newer_home_assistant_keeps_them(hass: HomeAssistant) -> None:
    """Newer versions replace raw_config by the generated automation and keep the inputs apart."""
    _add_printer(hass)
    hass.states.async_set("switch.printer_plug", "on")
    hass.states.async_set("camera.workshop", "idle")
    saved = {
        "use_blueprint": {
            "path": "x.yaml",
            "input": {**BLUEPRINT_INPUTS, "printer_power_switch": "switch.printer_plug", "printer_camera_2": "camera.workshop"},
        }
    }
    generated = {"alias": "Bambu Lab - Spaghetti Detection", "trigger": [], "action": []}
    hass.data[AUTOMATION_DATA_COMPONENT] = SimpleNamespace(
        entities=[
            SimpleNamespace(raw_config=generated, _blueprint_inputs=saved),  # a loaded automation
            SimpleNamespace(raw_config=generated, _raw_blueprint_inputs=saved),  # one that failed to load
        ]
    )
    cards = _cards(build_dashboard_config(hass)["views"][0])
    assert cards[0]["cards"][0]["entities"] == [{"entity": "switch.printer_plug"}]
    assert cards[1]["camera_image"] == "camera.workshop"


async def test_plug_and_second_camera_come_from_the_blueprint(hass: HomeAssistant) -> None:
    _add_printer(hass)
    hass.states.async_set("switch.printer_plug", "on")
    hass.states.async_set("camera.workshop", "idle")
    _automations(
        hass, {**BLUEPRINT_INPUTS, "printer_power_switch": "switch.printer_plug", "printer_camera_2": "camera.workshop"}
    )
    view = build_dashboard_config(hass)["views"][0]

    assert view["type"] == "sections"
    assert view["max_columns"] == 4
    cards = _cards(view)
    # Power plug, overview picture, camera, then the generated cards.
    assert cards[0]["type"] == "vertical-stack"
    assert cards[0]["cards"][0]["entities"] == [{"entity": "switch.printer_plug"}]
    assert cards[0]["cards"][1]["type"] == "history-graph"
    assert cards[1]["type"] == "picture-elements"
    assert cards[1]["camera_image"] == "camera.workshop"
    assert cards[2]["type"] == "picture-entity"
    assert cards[2]["entity"] == "camera.min_printer_kamera"
    assert cards[2]["fit_mode"] == "fill"
    # Every card sits in a section of its own.
    assert all(len(section["cards"]) == 1 for section in view["sections"])


async def test_second_camera_is_shown_even_when_it_is_unavailable(hass: HomeAssistant) -> None:
    _add_printer(hass)
    hass.states.async_set("camera.workshop", "unavailable")
    _automations(hass, {**BLUEPRINT_INPUTS, "printer_camera_2": "camera.workshop"})
    cards = _cards(build_dashboard_config(hass)["views"][0])
    overview = next(card for card in cards if card["type"] == "picture-elements")
    assert overview["camera_image"] == "camera.workshop"
    # The overview is the first of the two pictures, the printer camera comes after it.
    pictures = [card for card in cards if card["type"] in ("picture-elements", "picture-entity")]
    assert [card["type"] for card in pictures] == ["picture-elements", "picture-entity"]
    assert pictures[1]["entity"] == "camera.min_printer_kamera"


@pytest.mark.parametrize(
    "inputs",
    [
        None,  # no automation at all
        {**BLUEPRINT_INPUTS},  # optional inputs not set
        {**BLUEPRINT_INPUTS, "printer_power_switch": [], "printer_camera_2": []},  # stored as empty lists
        {**BLUEPRINT_INPUTS, "printer_power_switch": "switch.missing", "printer_camera_2": "camera.missing"},
    ],
)
async def test_nothing_extra_without_blueprint_inputs(hass: HomeAssistant, inputs) -> None:
    _add_printer(hass)
    if inputs is not None:
        _automations(hass, inputs)
    cards = _cards(build_dashboard_config(hass)["views"][0])
    assert "switch." not in str(cards)
    assert cards[0]["type"] == "picture-elements"
    assert cards[0]["camera_image"] == "camera.min_printer_kamera"


async def test_automation_is_matched_to_the_printer_by_its_camera(hass: HomeAssistant) -> None:
    _add_printer(hass)
    hass.states.async_set("switch.plug_one", "on")
    hass.states.async_set("switch.plug_two", "on")
    _automations(
        hass,
        {**BLUEPRINT_INPUTS, "printer_camera": "camera.other_printer", "printer_power_switch": "switch.plug_two"},
        {**BLUEPRINT_INPUTS, "printer_power_switch": "switch.plug_one"},
    )
    cards = _cards(build_dashboard_config(hass)["views"][0])
    assert cards[0]["cards"][0]["entities"] == [{"entity": "switch.plug_one"}]


async def test_other_automations_and_odd_data_are_ignored(hass: HomeAssistant) -> None:
    _add_printer(hass)
    hass.states.async_set("switch.printer_plug", "on")
    hass.data[AUTOMATION_DATA_COMPONENT] = SimpleNamespace(
        entities=[
            SimpleNamespace(raw_config=None),
            SimpleNamespace(raw_config={}),
            SimpleNamespace(),  # no raw_config at all
            SimpleNamespace(raw_config={"use_blueprint": "text"}),
            SimpleNamespace(raw_config={"use_blueprint": {"input": "text"}}),
            # Another blueprint that happens to have a plug input.
            SimpleNamespace(
                raw_config={"use_blueprint": {"path": "y.yaml", "input": {"printer_power_switch": "switch.printer_plug"}}}
            ),
        ]
    )
    cards = _cards(build_dashboard_config(hass)["views"][0])
    assert "switch.printer_plug" not in str(cards)


async def test_overview_overlay_only_has_existing_entities(hass: HomeAssistant) -> None:
    _add_printer(hass)
    overview = next(
        card for card in _cards(build_dashboard_config(hass)["views"][0]) if card["type"] == "picture-elements"
    )
    labels = [e for e in overview["elements"] if e["type"] == "state-label"]
    # Labels are packed from the top with the same spacing, no gaps for missing entities.
    assert [e["style"]["top"] for e in labels] == ["3%", "11%", "19%", "27%", "35%", "43%"]
    assert [e["entity"] for e in labels] == [
        "sensor.min_printer_subtask_name_omdopt",
        "sensor.min_printer_print_status_omdopt",
        "sensor.min_printer_print_progress_omdopt",
        "sensor.min_printer_bed_temp_omdopt",
        "sensor.min_printer_nozzle_temp_omdopt",
        "sensor.min_printer_remaining_time_omdopt",
    ]
    assert "prefix" not in labels[0]
    assert labels[1]["prefix"] == "Status: "
    icons = {e["entity"]: e for e in overview["elements"] if e["type"] == "state-icon"}
    assert set(icons) == {"binary_sensor.min_printer_hms", "light.min_printer_lys"}
    assert icons["light.min_printer_lys"]["tap_action"] == {"action": "toggle"}
    assert icons["light.min_printer_lys"]["style"]["bottom"] == "2%"


async def test_inputs_are_read_from_a_real_automation(hass: HomeAssistant) -> None:
    """Use Home Assistant's own automation and blueprint loading instead of stand-ins."""
    _add_printer(hass)
    hass.states.async_set("switch.printer_plug", "on")
    hass.states.async_set("camera.workshop", "idle")

    target = Path(hass.config.path("blueprints/automation/test/spaghetti_detection.yaml"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text((Path(__file__).parent.parent / "blueprints" / "spaghetti_detection.yaml").read_text())

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "use_blueprint": {
                    "path": "test/spaghetti_detection.yaml",
                    "input": {
                        "obico_host": "http://ml:3333",
                        "printer_print_status_sensor": "sensor.min_printer_print_status_omdopt",
                        "printer_current_stage_sensor": "sensor.min_printer_stage_omdopt",
                        "printer_camera": "camera.min_printer_kamera",
                        "printer_camera_2": "camera.workshop",
                        "printer_power_switch": "switch.printer_plug",
                        "printer_chamber_light": "light.min_printer_lys",
                    },
                }
            }
        },
    )
    await hass.async_block_till_done()

    cards = _cards(build_dashboard_config(hass)["views"][0])
    assert cards[0]["cards"][0]["entities"] == [{"entity": "switch.printer_plug"}]
    assert cards[1]["camera_image"] == "camera.workshop"
