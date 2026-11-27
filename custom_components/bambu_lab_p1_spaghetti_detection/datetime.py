from datetime import datetime, timezone

from homeassistant.components.datetime import DateTimeEntity, DateTimeEntityDescription
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .runtime import get_runtime

DATETIME_TYPES: tuple[DateTimeEntityDescription, ...] = (
    DateTimeEntityDescription(
        key="last_notify_time",
        name="Spaghetti Detection - Last Notify Time"
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    entities = [
        BambuLabP1SpaghettiDetectionDateTimeEntity(entity_description) for entity_description in DATETIME_TYPES
    ]

    runtime = get_runtime(hass, entry.entry_id)
    if runtime is not None:
        runtime.last_notify = entities[0]

    async_add_entities(entities)


class BambuLabP1SpaghettiDetectionDateTimeEntity(DateTimeEntity, RestoreEntity):
    def __init__(self, entity_description):
        self.entity_description = entity_description

        self.entity_id = "number.bambu_lab_p1_spaghetti_detection_%s" % entity_description.key
        self._attr_unique_id = "number.bambu_lab_p1_spaghetti_detection_%s" % entity_description.key
        self._attr_native_value = datetime.fromtimestamp(0, timezone.utc)

    async def async_added_to_hass(self) -> None:
        """Take the time from before a restart, so a failure is not reported twice within a minute."""
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            restored = dt_util.parse_datetime(last.state)
            if restored is not None and restored.tzinfo is not None:
                self._attr_native_value = restored

    async def async_set_value(self, value: datetime) -> None:
        """Set the value of the datetime entity."""
        self._attr_native_value = value
        self.async_write_ha_state()

    async def set_value(self, value: datetime) -> None:
        """Set the value of the datetime entity."""
        await self.async_set_value(value)
