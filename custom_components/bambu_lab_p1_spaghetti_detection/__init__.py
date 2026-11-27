import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse

from .const import DOMAIN
from .dashboard import (
    async_register_dashboard,
    async_unregister_dashboard,
    build_dashboard_config,
)
from .detection import DetectionEngine
from .ml_client import async_predict
from .runtime import Runtime

BRAND = "Bambu Lab P1 - Spaghetti Detection"

LOGGER = logging.getLogger(__package__)

PLATFORMS = [Platform.NUMBER, Platform.DATETIME, Platform.SENSOR]

SPAGHETTI_DETECTION_SCHEMA = vol.Schema({
    vol.Required("obico_host"): str,
    vol.Required("obico_auth_token"): str,
    vol.Required("image_url"): str,
})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Bambu Lab P1 - Spaghetti Detection integration."""
    runtime = Runtime()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # The built-in detection, which is only active when it is turned on in the settings.
    runtime.engine = DetectionEngine(hass, entry, runtime)
    await runtime.engine.async_start()
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    async def spaghetti_detection_handler(call: ServiceCall) -> ServiceResponse:
        """Handle the custom service."""
        result = await async_predict(
            hass,
            call.data.get("obico_host", ""),
            call.data.get("obico_auth_token", ""),
            call.data.get("image_url", ""),
        )
        return {"result": result}

    hass.services.async_register(
        DOMAIN,
        "predict",
        spaghetti_detection_handler,
        schema=SPAGHETTI_DETECTION_SCHEMA,
        supports_response=SupportsResponse.ONLY
    )

    async def generate_dashboard_handler(call: ServiceCall) -> ServiceResponse:
        """Return the printer dashboard, ready to paste into a dashboard's raw configuration editor."""
        return build_dashboard_config(hass)

    hass.services.async_register(
        DOMAIN,
        "generate_dashboard",
        generate_dashboard_handler,
        supports_response=SupportsResponse.ONLY
    )

    # Adds the generated printer dashboard to the sidebar. Failing to do so is
    # not fatal, the generate_dashboard action covers that case.
    async_register_dashboard(hass)

    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Start over with the new settings."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Bambu Lab P1 - Spaghetti Detection integration."""
    runtime = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if runtime is not None and runtime.engine is not None:
        await runtime.engine.async_stop()
    async_unregister_dashboard(hass)
    hass.services.async_remove(DOMAIN, "generate_dashboard")
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unloaded
