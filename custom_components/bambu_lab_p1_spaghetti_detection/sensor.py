"""The status of the built-in detection."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.core import callback

from .const import STATUS_OFF, STATUSES
from .runtime import get_runtime

STATUS_SENSOR = SensorEntityDescription(
    key="status",
    name="Spaghetti Detection - Status",
    device_class=SensorDeviceClass.ENUM,
    options=list(STATUSES),
    translation_key="status",
)


async def async_setup_entry(hass, entry, async_add_entities):
    entity = BambuLabP1SpaghettiDetectionStatusSensor(STATUS_SENSOR)
    runtime = get_runtime(hass, entry.entry_id)
    if runtime is not None:
        runtime.status = entity
    async_add_entities([entity])


class BambuLabP1SpaghettiDetectionStatusSensor(SensorEntity):
    """Says what the detection is doing, and why when it is not working."""

    _attr_should_poll = False

    def __init__(self, entity_description: SensorEntityDescription) -> None:
        self.entity_description = entity_description
        self.entity_id = "sensor.bambu_lab_p1_spaghetti_detection_%s" % entity_description.key
        self._attr_unique_id = "sensor.bambu_lab_p1_spaghetti_detection_%s" % entity_description.key
        self._attr_native_value = STATUS_OFF
        self._attributes: dict[str, Any] = {}

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._attributes

    @callback
    def async_set_status(self, status: str, **attributes: Any) -> None:
        """Set the status and its details, and write them."""
        self._attr_native_value = status
        self._attributes = {key: value for key, value in attributes.items() if value is not None}
        if self.hass is not None:
            self.async_write_ha_state()
