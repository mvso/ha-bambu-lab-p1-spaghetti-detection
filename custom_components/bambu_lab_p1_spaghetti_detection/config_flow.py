from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

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
    DOMAIN,
    FREQUENCIES,
)
from .ml_client import MLAuthError, MLNoSecretError, MLServerError, async_predict

_LOGGER = logging.getLogger(__name__)

# What must be filled in when the detection is turned on.
REQUIRED_FIELDS = (CONF_OBICO_HOST, CONF_OBICO_TOKEN, CONF_CAMERA, CONF_PRINT_STATUS, CONF_STAGE)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        return self.async_create_entry(title="Bambu Lab P1 - Spaghetti Detection", data={})

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return SpaghettiOptionsFlow()


def _is_url(value: str) -> bool:
    return value.startswith(("http://", "https://")) and len(value.split("//", 1)[1]) > 0


class SpaghettiOptionsFlow(OptionsFlow):
    """The settings of the built-in detection."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input = self._clean(user_input)
            errors = await self._async_validate(user_input)
            if not errors:
                return self.async_create_entry(data=user_input)

        values = user_input if user_input is not None else dict(self.config_entry.options)
        return self.async_show_form(step_id="init", data_schema=self._schema(values), errors=errors)

    @staticmethod
    def _clean(user_input: dict[str, Any]) -> dict[str, Any]:
        """Remove empty values and stray spaces."""
        cleaned: dict[str, Any] = {}
        for key, value in user_input.items():
            if isinstance(value, str):
                value = value.strip()
            if value in (None, "", []):
                continue
            cleaned[key] = value
        return cleaned

    async def _async_validate(self, user_input: dict[str, Any]) -> dict[str, str]:
        """Check the settings. Nothing is checked as long as the detection is turned off."""
        if not user_input.get(CONF_ENABLED):
            return {}

        errors = {key: "required" for key in REQUIRED_FIELDS if not user_input.get(key)}
        for key in (CONF_OBICO_HOST, CONF_HA_HOST):
            value = user_input.get(key)
            if value and not _is_url(value):
                errors[key] = "invalid_url"
        if errors:
            return errors

        try:
            await async_predict(self.hass, user_input[CONF_OBICO_HOST], user_input[CONF_OBICO_TOKEN])
        except MLAuthError:
            errors[CONF_OBICO_TOKEN] = "invalid_auth"
        except MLNoSecretError:
            errors[CONF_OBICO_TOKEN] = "no_secret"
        except MLServerError as err:
            _LOGGER.debug("Connection test failed: %s", err)
            errors[CONF_OBICO_HOST] = "cannot_connect"
        return errors

    @staticmethod
    def _schema(values: dict[str, Any]) -> vol.Schema:
        def suggested(key: str) -> dict[str, Any]:
            return {"suggested_value": values.get(key)}

        def entity(domain: str) -> selector.EntitySelector:
            return selector.EntitySelector(selector.EntitySelectorConfig(domain=domain))

        return vol.Schema(
            {
                vol.Required(CONF_ENABLED, default=bool(values.get(CONF_ENABLED, False))): selector.BooleanSelector(),
                vol.Optional(CONF_OBICO_HOST, description=suggested(CONF_OBICO_HOST)): selector.TextSelector(),
                vol.Optional(CONF_OBICO_TOKEN, description=suggested(CONF_OBICO_TOKEN)): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
                vol.Optional(CONF_HA_HOST, description=suggested(CONF_HA_HOST)): selector.TextSelector(),
                vol.Optional(CONF_CAMERA, description=suggested(CONF_CAMERA)): entity("camera"),
                vol.Optional(CONF_CAMERA_2, description=suggested(CONF_CAMERA_2)): entity("camera"),
                vol.Optional(CONF_PRINT_STATUS, description=suggested(CONF_PRINT_STATUS)): entity("sensor"),
                vol.Optional(CONF_STAGE, description=suggested(CONF_STAGE)): entity("sensor"),
                vol.Optional(CONF_LIGHT, description=suggested(CONF_LIGHT)): entity("light"),
                vol.Required(
                    CONF_AUTO_LIGHT, default=bool(values.get(CONF_AUTO_LIGHT, True))
                ): selector.BooleanSelector(),
                vol.Required(
                    CONF_FREQUENCY, default=str(values.get(CONF_FREQUENCY) or DEFAULT_FREQUENCY)
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=list(FREQUENCIES),
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        translation_key="frequency",
                    )
                ),
            }
        )
