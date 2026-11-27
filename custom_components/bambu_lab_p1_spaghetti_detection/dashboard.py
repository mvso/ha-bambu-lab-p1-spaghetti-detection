"""Printer dashboard generated from the entities that actually exist.

The Bambu Lab integration gives every entity a unique ID built from the
printer's serial number and a fixed key. Looking entities up by that ID finds
them no matter what they were renamed to or which language is in use.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er

DOMAIN = "bambu_lab_p1_spaghetti_detection"
BAMBU_LAB_DOMAIN = "bambu_lab"

DASHBOARD_URL_PATH = "bambu-lab-printer"
DASHBOARD_ICON = "mdi:printer-3d"

_LOGGER = logging.getLogger(__name__)

_TRAY_KEY = re.compile(r"_(tray_(\d+))$")
_AMS_NUMBER = re.compile(r"AMS[_ ]?(\w+)$")

LABELS = {
    "en": {
        "dashboard": "3D printer",
        "printer": "Printer",
        "filament": "Filament",
        "progress": "Progress",
        "print": "Print",
        "job": "Job",
        "status": "Status",
        "stage": "Stage",
        "remaining": "Remaining time",
        "end_time": "Finished at",
        "layer": "Layer",
        "total_layers": "Total layers",
        "speed": "Speed",
        "active_tray": "Active filament",
        "temperatures": "Temperatures",
        "nozzle": "Nozzle",
        "nozzle_target": "Nozzle target",
        "bed": "Bed",
        "bed_target": "Bed target",
        "chamber": "Chamber",
        "light": "Chamber light",
        "online": "Online",
        "print_error": "Print error",
        "hms": "HMS errors",
        "wifi": "Wi-Fi signal",
        "detection": "Spaghetti detection",
        "detection_status": "Detection status",
        "probability": "Failure probability",
        "mean": "Moving average",
        "frames": "Frames analysed (this job)",
        "frames_total": "Frames analysed (total)",
        "slot": "Slot",
        "type": "Type",
        "left": "Left",
        "empty": "Empty",
        "external": "External",
        "external_spool": "External spool",
        "active_note": "▶ marks the filament in use.",
        "climate": "climate",
        "humidity_index": "Humidity index",
        "humidity": "Humidity",
        "temperature": "Temperature",
        "in_use": "Filament in use",
        "in_extruder": "Filament in extruder",
        "usage": "Filament used (this job)",
        "pe_status": "Status: ",
        "pe_progress": "Progress: ",
        "pe_layer": "Layer: ",
        "pe_bed": "Bed: ",
        "pe_nozzle": "Nozzle: ",
        "pe_speed": "Speed: ",
        "pe_ams_temp": "AMS temp: ",
        "pe_ams_humidity": "AMS humidity: ",
        "pe_remaining": "Remaining: ",
        "pe_end": "Done: ",
        "no_printer": (
            "No Bambu Lab printer was found. Install and set up the Bambu Lab "
            "integration, then reload this page."
        ),
    },
    "nb": {
        "dashboard": "3D-printer",
        "printer": "Printer",
        "filament": "Filament",
        "progress": "Fremdrift",
        "print": "Utskrift",
        "job": "Jobb",
        "status": "Status",
        "stage": "Steg",
        "remaining": "Gjenstående tid",
        "end_time": "Ferdig",
        "layer": "Lag",
        "total_layers": "Lag totalt",
        "speed": "Hastighet",
        "active_tray": "Aktivt filament",
        "temperatures": "Temperaturer",
        "nozzle": "Dyse",
        "nozzle_target": "Dyse mål",
        "bed": "Plate",
        "bed_target": "Plate mål",
        "chamber": "Kammer",
        "light": "Kammerlys",
        "online": "Tilkoblet",
        "print_error": "Utskriftsfeil",
        "hms": "HMS-feil",
        "wifi": "Wi-Fi-signal",
        "detection": "Spaghetti-deteksjon",
        "detection_status": "Deteksjonsstatus",
        "probability": "Sannsynlighet for feil",
        "mean": "Glidende snitt",
        "frames": "Bilder analysert (denne jobben)",
        "frames_total": "Bilder analysert (totalt)",
        "slot": "Spor",
        "type": "Type",
        "left": "Rest",
        "empty": "Tomt",
        "external": "Ekstern",
        "external_spool": "Ekstern spole",
        "active_note": "▶ markerer filamentet som er i bruk.",
        "climate": "klima",
        "humidity_index": "Fuktighetsindeks",
        "humidity": "Luftfuktighet",
        "temperature": "Temperatur",
        "in_use": "Filament i bruk",
        "in_extruder": "Filament i ekstruder",
        "usage": "Filamentforbruk (denne jobben)",
        "pe_status": "Status: ",
        "pe_progress": "Fremdrift: ",
        "pe_layer": "Lag: ",
        "pe_bed": "Seng: ",
        "pe_nozzle": "Dyse: ",
        "pe_speed": "Hastighet: ",
        "pe_ams_temp": "AMS temp: ",
        "pe_ams_humidity": "AMS fukt: ",
        "pe_remaining": "Gjenstår: ",
        "pe_end": "Ferdig: ",
        "no_printer": (
            "Fant ingen Bambu Lab-printer. Installer og sett opp Bambu Lab-"
            "integrasjonen, og last deretter siden på nytt."
        ),
    },
}


def _labels(hass: HomeAssistant) -> dict[str, str]:
    language = (hass.config.language or "en").lower()
    if language.split("-")[0] in ("nb", "nn", "no"):
        return LABELS["nb"]
    return LABELS["en"]


def dashboard_title(hass: HomeAssistant) -> str:
    """Return the title used for the dashboard and its sidebar entry."""
    return _labels(hass)["dashboard"]


class _Printer:
    """The entities of one printer, looked up by unique ID."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        self.serial: str = entry.data.get("serial", "")
        self.name: str = entry.title or self.serial
        self.device_type: str = entry.data.get("device_type", "")
        registry = er.async_get(hass)
        self.entities = [
            entity
            for entity in er.async_entries_for_config_entry(registry, entry.entry_id)
            if entity.disabled_by is None
        ]
        self._by_unique_id = {
            (entity.domain, entity.unique_id): entity.entity_id for entity in self.entities
        }

    def get(self, domain: str, key: str) -> str | None:
        """Return the entity ID of a printer entity, or None if it does not exist."""
        return self._by_unique_id.get((domain, f"{self.serial}_{key}"))

    def ams_units(self, hass: HomeAssistant) -> list[dict[str, Any]]:
        """Return every AMS with its trays and climate sensors."""
        devices = dr.async_get(hass)
        units: dict[str, dict[str, Any]] = {}
        for entity in self.entities:
            if entity.domain != "sensor" or "_AMS_" not in entity.unique_id:
                continue
            unit = units.setdefault(entity.device_id or "", {"trays": {}})
            tray = _TRAY_KEY.search(entity.unique_id)
            if tray:
                unit["trays"][int(tray.group(2))] = entity.entity_id
                continue
            for key in ("humidity_index", "humidity", "temperature"):
                if entity.unique_id.endswith(f"_{key}"):
                    unit[key] = entity.entity_id
                    break

        result = []
        for device_id, unit in units.items():
            if not unit["trays"]:
                continue
            device = devices.async_get(device_id) if device_id else None
            device_name = (device.name_by_user or device.name or "") if device else ""
            number = _AMS_NUMBER.search(device_name)
            unit["name"] = f"AMS {number.group(1)}" if number else (device_name or "AMS")
            result.append(unit)
        return sorted(result, key=lambda unit: unit["name"])

    def external_spools(self) -> list[str]:
        """Return the external spool sensors."""
        return sorted(
            entity.entity_id
            for entity in self.entities
            if entity.domain == "sensor"
            and "_ExternalSpool" in entity.unique_id
            and entity.unique_id.endswith("_external_spool")
        )


def _rows(*pairs: tuple[str | None, str]) -> list[dict[str, str]]:
    """Build entity rows, leaving out the entities that do not exist."""
    return [{"entity": entity_id, "name": name} for entity_id, name in pairs if entity_id]


def _tray_row(entity_id: str, slot: str, labels: dict[str, str], show_left: bool) -> str:
    e = f"'{entity_id}'"
    left = (
        f"{{% set r = state_attr({e}, 'remain') %}}"
        f"{{{{ r ~ ' %' if r is number and r >= 0 and not state_attr({e}, 'empty') else '–' }}}}"
        if show_left
        else "–"
    )
    return (
        f"| <font color=\"{{{{ (state_attr({e}, 'color') or '#888888')[:7] }}}}\">⬤</font> "
        f"| {slot}{{{{ ' ▶' if state_attr({e}, 'active') else '' }}}} "
        f"| {{{{ '{labels['empty']}' if state_attr({e}, 'empty') else "
        f"('–' if states({e}) in ['unknown', 'unavailable'] else states({e})) }}}} "
        f"| {{{{ state_attr({e}, 'type') or '–' }}}} "
        f"| {left} |"
    )


def _filament_table(trays: list[tuple[str, str, bool]], labels: dict[str, str]) -> str:
    header = (
        f"| | {labels['slot']} | {labels['filament']} | {labels['type']} | {labels['left']} |\n"
        "|:-:|:-:|:--|:--|--:|\n"
    )
    rows = "\n".join(_tray_row(entity_id, slot, labels, left) for entity_id, slot, left in trays)
    return f"{header}{rows}\n\n{labels['active_note']}"


def _detection_cards(hass: HomeAssistant, labels: dict[str, str]) -> list[dict[str, Any]]:
    registry = er.async_get(hass)

    def number(key: str) -> str | None:
        return registry.async_get_entity_id(
            "number", DOMAIN, f"number.{DOMAIN}_{key}"
        )

    status = registry.async_get_entity_id("sensor", DOMAIN, f"sensor.{DOMAIN}_status")
    rows = _rows(
        (status, labels["detection_status"]),
        (number("normalized_p"), labels["probability"]),
        (number("adjusted_ewm_mean"), labels["mean"]),
        (number("current_frame_number"), labels["frames"]),
        (number("lifetime_frame_number"), labels["frames_total"]),
    )
    if not rows:
        return []

    cards: list[dict[str, Any]] = [
        {"type": "entities", "title": labels["detection"], "entities": rows}
    ]
    mean = number("adjusted_ewm_mean")
    if mean:
        cards.append(
            {
                "type": "history-graph",
                "hours_to_show": 3,
                "entities": [{"entity": mean, "name": labels["mean"]}],
            }
        )
    return [{"type": "vertical-stack", "cards": cards}]


def _entity_blueprint_inputs(entity: Any) -> dict[str, Any] | None:
    """Return the blueprint inputs of an automation entity, or None.

    Home Assistant keeps the config the user saved, with its use_blueprint section, in a
    different place depending on the version: newer versions replace raw_config by the
    automation the blueprint produced, and only keep the saved config separately. Both places
    are tried.
    """
    for name in ("_blueprint_inputs", "raw_config", "_raw_blueprint_inputs"):
        config = getattr(entity, name, None)
        use = config.get("use_blueprint") if isinstance(config, dict) else None
        inputs = use.get("input") if isinstance(use, dict) else None
        if isinstance(inputs, dict):
            return inputs
    return None


def _blueprint_inputs(hass: HomeAssistant, camera: str | None) -> dict[str, Any]:
    """Return the inputs of the spaghetti detection automation that belongs to a printer.

    The power plug and the second camera are set in the blueprint, so the dashboard reads
    them from there. The automation is recognised by its inputs, not by where the blueprint
    was imported to, and with several of them the one using the printer's camera is chosen.
    Anything unexpected gives no inputs, and the dashboard is then built without them.
    """
    try:
        from homeassistant.components.automation import DATA_COMPONENT

        component = hass.data.get(DATA_COMPONENT)
        found: list[dict[str, Any]] = []
        for entity in list(component.entities) if component is not None else []:
            inputs = _entity_blueprint_inputs(entity)
            if inputs is not None and "obico_host" in inputs and "printer_camera" in inputs:
                found.append(inputs)
    except Exception:  # noqa: BLE001 - the dashboard must never break because of this
        _LOGGER.debug("Could not read the automation inputs", exc_info=True)
        return {}

    if not found:
        _LOGGER.debug("No automation made from the spaghetti detection blueprint was found")
    for inputs in found:
        if camera and inputs.get("printer_camera") == camera:
            return inputs
    return found[0] if len(found) == 1 else {}


def blueprint_automation_is_on(hass: HomeAssistant) -> bool:
    """Return whether an automation made from the blueprint is turned on.

    The built-in detection uses the same values as the blueprint, so the two must not run together.
    Anything unexpected gives False.
    """
    try:
        from homeassistant.components.automation import DATA_COMPONENT

        component = hass.data.get(DATA_COMPONENT)
        for entity in list(component.entities) if component is not None else []:
            inputs = _entity_blueprint_inputs(entity)
            if inputs is None or "obico_host" not in inputs or "printer_camera" not in inputs:
                continue
            state = hass.states.get(entity.entity_id)
            if state is not None and state.state == "on":
                return True
    except Exception:  # noqa: BLE001 - this is only a warning
        _LOGGER.debug("Could not check the automations", exc_info=True)
    return False


def _input_entity(inputs: dict[str, Any], key: str) -> str | None:
    """Return an optional entity input, which is an empty list when it is not set."""
    value = inputs.get(key)
    return value if isinstance(value, str) and value else None


def _entity_exists(hass: HomeAssistant, entity_id: str) -> bool:
    return (
        hass.states.get(entity_id) is not None
        or er.async_get(hass).async_get(entity_id) is not None
    )


def _state_icon(entity_id: str | None, icon: str, color: str, position: dict[str, str], **extra) -> list:
    if not entity_id:
        return []
    return [
        {
            "type": "state-icon",
            "entity": entity_id,
            "icon": icon,
            **extra,
            "style": {**position, "color": color, "filter": "drop-shadow(0 0 2px black)"},
        }
    ]


def _overview_card(
    hass: HomeAssistant, printer: _Printer, labels: dict[str, str], background: str
) -> dict[str, Any]:
    """Camera picture with the printer's key values laid over it."""
    units = printer.ams_units(hass)
    ams = units[0] if units else {}

    elements: list[dict[str, Any]] = []
    elements += _state_icon(
        printer.get("binary_sensor", "print_error"), "mdi:alert-circle", "red",
        {"top": "3%", "right": "12%"},
    )
    elements += _state_icon(
        printer.get("binary_sensor", "hms"), "mdi:tools", "orange",
        {"top": "3%", "right": "2%"},
    )
    elements += _state_icon(
        printer.get("light", "chamber_light") or printer.get("light", "camera_light"),
        "mdi:lightbulb", "white", {"bottom": "2%", "right": "2%"},
        tap_action={"action": "toggle"},
    )

    # (entity, prefix, font size, extra style). Missing entities are left out and the rest moves up.
    name_style = {
        "max-width": "65%", "white-space": "nowrap", "overflow": "hidden", "text-overflow": "ellipsis",
    }
    rows = (
        (printer.get("sensor", "subtask_name"), None, "10px", name_style),
        (printer.get("sensor", "print_status"), labels["pe_status"], "11px", {}),
        (printer.get("sensor", "print_progress"), labels["pe_progress"], "11px", {}),
        (printer.get("sensor", "current_layer"), labels["pe_layer"], "11px", {}),
        (printer.get("sensor", "bed_temp"), labels["pe_bed"], "11px", {}),
        (printer.get("sensor", "nozzle_temp"), labels["pe_nozzle"], "11px", {}),
        (printer.get("sensor", "speed_profile"), labels["pe_speed"], "11px", {}),
        (ams.get("temperature"), labels["pe_ams_temp"], "11px", {}),
        (ams.get("humidity"), labels["pe_ams_humidity"], "11px", {}),
        (printer.get("sensor", "remaining_time"), labels["pe_remaining"], "11px", {}),
        (printer.get("sensor", "end_time"), labels["pe_end"], "9px", {}),
    )
    position = 0
    for entity_id, prefix, font_size, extra_style in rows:
        if not entity_id:
            continue
        element: dict[str, Any] = {
            "type": "state-label",
            "entity": entity_id,
            "style": {
                "top": f"{3 + 8 * position}%",
                "left": "1%",
                "transform": "translate(0%, -50%)",
                "color": "white",
                "background": "rgba(0,0,0,0.6)",
                "padding": "2px 6px",
                "border-radius": "4px",
                "font-size": font_size,
                **extra_style,
            },
        }
        if prefix:
            element["prefix"] = prefix
        elements.append(element)
        position += 1

    return {
        "type": "picture-elements",
        "camera_image": background,
        "camera_view": "live",
        "title": printer.device_type or labels["printer"],
        "elements": elements,
    }


def _printer_view(
    hass: HomeAssistant,
    printer: _Printer,
    labels: dict[str, str],
    suffix: str,
    path: str,
) -> dict[str, Any]:
    """Build the printer view as sections, laid out from left to right.

    The leftmost cards are the power plug history and the overview picture. The plug and the
    second camera for the overview are the optional inputs of the blueprint.
    """
    cards: list[dict[str, Any]] = []

    camera = printer.get("camera", "camera") or printer.get("image", "p1p_camera")
    if camera and camera.startswith("camera."):
        cards.append(
            {
                "type": "picture-entity",
                "entity": camera,
                "camera_image": camera,
                "camera_view": "live",
                "show_name": True,
                "show_state": True,
                "fit_mode": "fill",
            }
        )
    elif camera:
        cards.append(
            {"type": "picture-entity", "entity": camera, "show_name": False, "show_state": False}
        )

    job: list[dict[str, Any]] = []
    progress = printer.get("sensor", "print_progress")
    if progress:
        job.append(
            {"type": "gauge", "entity": progress, "name": labels["progress"], "min": 0, "max": 100}
        )
    job_rows = _rows(
        (printer.get("sensor", "subtask_name"), labels["job"]),
        (printer.get("sensor", "print_status"), labels["status"]),
        (printer.get("sensor", "stage"), labels["stage"]),
        (printer.get("sensor", "remaining_time"), labels["remaining"]),
        (printer.get("sensor", "end_time"), labels["end_time"]),
        (printer.get("sensor", "current_layer"), labels["layer"]),
        (printer.get("sensor", "total_layers"), labels["total_layers"]),
        (printer.get("sensor", "speed_profile"), labels["speed"]),
        (printer.get("sensor", "active_tray"), labels["active_tray"]),
    )
    if job_rows:
        job.append({"type": "entities", "title": labels["print"], "entities": job_rows})
    if job:
        cards.append({"type": "vertical-stack", "cards": job})

    temperatures = _rows(
        (printer.get("sensor", "nozzle_temp"), labels["nozzle"]),
        (printer.get("sensor", "target_nozzle_temp"), labels["nozzle_target"]),
        (printer.get("sensor", "bed_temp"), labels["bed"]),
        (printer.get("sensor", "target_bed_temp"), labels["bed_target"]),
        (printer.get("sensor", "chamber_temp"), labels["chamber"]),
    )
    if temperatures:
        graph = _rows(
            (printer.get("sensor", "nozzle_temp"), labels["nozzle"]),
            (printer.get("sensor", "bed_temp"), labels["bed"]),
            (printer.get("sensor", "chamber_temp"), labels["chamber"]),
        )
        stack: list[dict[str, Any]] = [
            {"type": "glance", "title": labels["temperatures"], "entities": temperatures}
        ]
        if graph:
            stack.append({"type": "history-graph", "hours_to_show": 3, "entities": graph})
        cards.append({"type": "vertical-stack", "cards": stack})

    status = _rows(
        (printer.get("light", "chamber_light") or printer.get("light", "camera_light"), labels["light"]),
        (printer.get("binary_sensor", "online"), labels["online"]),
        (printer.get("binary_sensor", "print_error"), labels["print_error"]),
        (printer.get("binary_sensor", "hms"), labels["hms"]),
        (printer.get("sensor", "wifi_signal"), labels["wifi"]),
    )
    if status:
        cards.append({"type": "entities", "title": labels["printer"], "entities": status})

    cards.extend(_detection_cards(hass, labels))

    inputs = _blueprint_inputs(hass, camera)
    leading: list[dict[str, Any]] = []

    plug = _input_entity(inputs, "printer_power_switch")
    if plug and _entity_exists(hass, plug):
        leading.append(
            {
                "type": "vertical-stack",
                "cards": [
                    {"type": "entities", "entities": [{"entity": plug}], "state_color": True},
                    {"type": "history-graph", "entities": [{"entity": plug}]},
                ],
            }
        )

    # The second camera is preferred as the picture behind the overview. The printer's own camera
    # is only used when there is none, or the entity does not exist at all. A second camera that is
    # unavailable at the moment is still shown, as that is the picture that was asked for.
    second_camera = _input_entity(inputs, "printer_camera_2")
    background = (
        second_camera
        if second_camera and _entity_exists(hass, second_camera)
        else (camera if camera and camera.startswith("camera.") else None)
    )
    if background:
        leading.append(_overview_card(hass, printer, labels, background))

    return {
        "title": f"{labels['printer']}{suffix}",
        "path": path,
        "icon": DASHBOARD_ICON,
        "type": "sections",
        "max_columns": 4,
        "sections": [{"type": "grid", "cards": [card]} for card in leading + cards],
    }


def _filament_view(
    hass: HomeAssistant, printer: _Printer, labels: dict[str, str], suffix: str, path: str
) -> dict[str, Any] | None:
    cards: list[dict[str, Any]] = []
    spools = printer.external_spools()
    units = printer.ams_units(hass)

    for unit in units:
        trays = [(entity_id, str(slot), True) for slot, entity_id in sorted(unit["trays"].items())]
        cards.append(
            {"type": "markdown", "title": unit["name"], "content": _filament_table(trays, labels)}
        )
        climate = _rows(
            (unit.get("humidity_index"), labels["humidity_index"]),
            (unit.get("humidity"), labels["humidity"]),
            (unit.get("temperature"), labels["temperature"]),
        )
        if climate:
            cards.append(
                {
                    "type": "entities",
                    "title": f"{unit['name']} {labels['climate']}",
                    "entities": climate,
                }
            )

    if spools:
        trays = [
            (entity_id, labels["external"] if len(spools) == 1 else f"{labels['external']} {index}", False)
            for index, entity_id in enumerate(spools, start=1)
        ]
        cards.append(
            {
                "type": "markdown",
                "title": labels["external_spool"],
                "content": _filament_table(trays, labels),
            }
        )

    in_use = _rows(
        (printer.get("sensor", "active_tray"), labels["active_tray"]),
        (printer.get("binary_sensor", "extruder_filament_state"), labels["in_extruder"]),
        (printer.get("sensor", "print_weight"), labels["usage"]),
    )
    if in_use:
        cards.append({"type": "entities", "title": labels["in_use"], "entities": in_use})

    if not units and not spools:
        return None

    return {
        "title": f"{labels['filament']}{suffix}",
        "path": path,
        "icon": "mdi:printer-3d-nozzle",
        "cards": cards,
    }


@callback
def build_dashboard_config(hass: HomeAssistant) -> dict[str, Any]:
    """Build the dashboard from the printers and entities that exist right now."""
    labels = _labels(hass)
    printers = [
        _Printer(hass, entry)
        for entry in hass.config_entries.async_entries(BAMBU_LAB_DOMAIN)
        if entry.data.get("serial")
    ]

    views: list[dict[str, Any]] = []
    for index, printer in enumerate(printers, start=1):
        suffix = f" – {printer.name}" if len(printers) > 1 else ""
        path_suffix = f"-{index}" if len(printers) > 1 else ""
        printer_view = _printer_view(hass, printer, labels, suffix, f"printer{path_suffix}")
        if printer_view["sections"]:
            views.append(printer_view)
        filament_view = _filament_view(hass, printer, labels, suffix, f"filament{path_suffix}")
        if filament_view:
            views.append(filament_view)

    if not views:
        views.append(
            {
                "title": labels["printer"],
                "path": "printer",
                "icon": DASHBOARD_ICON,
                "cards": [{"type": "markdown", "content": labels["no_printer"]}]
                + _detection_cards(hass, labels),
            }
        )

    return {"title": labels["dashboard"], "views": views}


def _lovelace_dashboards(hass: HomeAssistant) -> dict | None:
    """Return Home Assistant's registry of dashboards, or None if unavailable."""
    data = hass.data.get("lovelace")
    if data is None:
        return None
    dashboards = getattr(data, "dashboards", None)
    if dashboards is None and isinstance(data, dict):
        dashboards = data.get("dashboards")
    return dashboards if isinstance(dashboards, dict) else None


@callback
def async_register_dashboard(hass: HomeAssistant) -> bool:
    """Add the generated dashboard to the sidebar.

    Home Assistant has no public API for an integration to add a dashboard, so
    this relies on the Lovelace internals. If they are not as expected, nothing
    is registered and the generate_dashboard action remains as the fallback.
    """
    try:
        from homeassistant.components import frontend
        from homeassistant.components.lovelace.dashboard import LovelaceConfig

        dashboards = _lovelace_dashboards(hass)
        if dashboards is None:
            _LOGGER.warning("Dashboards are not available, the printer dashboard was not added")
            return False
        if DASHBOARD_URL_PATH in dashboards:
            return True

        class GeneratedDashboard(LovelaceConfig):
            """Read-only dashboard that is rebuilt every time it is opened."""

            @property
            def mode(self) -> str:
                return "yaml"

            async def async_get_info(self) -> dict[str, Any]:
                config = build_dashboard_config(self.hass)
                return {"mode": self.mode, "views": len(config["views"])}

            async def async_load(self, force: bool) -> dict[str, Any]:
                return build_dashboard_config(self.hass)

            async def async_json(self, force: bool):
                from homeassistant.helpers.json import json_bytes, json_fragment

                return json_fragment(json_bytes(build_dashboard_config(self.hass)))

        title = dashboard_title(hass)
        config = {
            "mode": "yaml",
            "title": title,
            "icon": DASHBOARD_ICON,
            "show_in_sidebar": True,
            "require_admin": False,
        }
        frontend.async_register_built_in_panel(
            hass,
            "lovelace",
            sidebar_title=title,
            sidebar_icon=DASHBOARD_ICON,
            frontend_url_path=DASHBOARD_URL_PATH,
            config={"mode": "yaml"},
            require_admin=False,
        )
        dashboards[DASHBOARD_URL_PATH] = GeneratedDashboard(hass, DASHBOARD_URL_PATH, config)
        return True
    except Exception:  # noqa: BLE001 - the dashboard must never break the integration
        _LOGGER.warning(
            "Could not add the printer dashboard automatically. Use the "
            "generate_dashboard action to create it manually",
            exc_info=True,
        )
        return False


@callback
def async_unregister_dashboard(hass: HomeAssistant) -> None:
    """Remove the generated dashboard again."""
    try:
        from homeassistant.components import frontend

        dashboards = _lovelace_dashboards(hass)
        if dashboards is not None and dashboards.pop(DASHBOARD_URL_PATH, None) is not None:
            frontend.async_remove_panel(hass, DASHBOARD_URL_PATH, warn_if_unknown=False)
    except Exception:  # noqa: BLE001
        _LOGGER.debug("Could not remove the printer dashboard", exc_info=True)
