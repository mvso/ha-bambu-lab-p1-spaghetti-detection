import logging

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError

DOMAIN = "bambu_lab_p1_spaghetti_detection"
BRAND = "Bambu Lab P1 - Spaghetti Detection"

LOGGER = logging.getLogger(__package__)

PLATFORMS = [Platform.NUMBER, Platform.DATETIME]

from .dashboard import (
    async_register_dashboard,
    async_unregister_dashboard,
    build_dashboard_config,
)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)

SPAGHETTI_DETECTION_SCHEMA = vol.Schema({
    vol.Required("obico_host"): str,
    vol.Required("obico_auth_token"): str,
    vol.Required("image_url"): str,
})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Bambu Lab P1 - Spaghetti Detection integration."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def spaghetti_detection_handler(call: ServiceCall) -> ServiceResponse:
        """Handle the custom service."""
        obico_host = call.data.get("obico_host", "")
        obico_auth_token = call.data.get("obico_auth_token", "")
        image_url = call.data.get("image_url", "")

        if obico_host.endswith("/"):
            obico_host = obico_host[:-1]

        # The image URL carries its own query string (the camera access token),
        # so it is passed as a parameter to get it encoded correctly.
        try:
            async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
                async with session.get(f"{obico_host}/p/",
                                       params={"img": image_url},
                                       headers={"Authorization": f"Bearer {obico_auth_token}"}) as response:
                    if response.status in (401, 503):
                        raise HomeAssistantError(
                            "Obico ML server rejected the auth token. Make sure the server and the "
                            "automation use the same secret, and that it is not the old default value."
                        )
                    response.raise_for_status()
                    result = await response.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise HomeAssistantError(f"Could not reach the Obico ML server: {err}") from err

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


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Bambu Lab P1 - Spaghetti Detection integration."""
    async_unregister_dashboard(hass)
    hass.services.async_remove(DOMAIN, "generate_dashboard")
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
