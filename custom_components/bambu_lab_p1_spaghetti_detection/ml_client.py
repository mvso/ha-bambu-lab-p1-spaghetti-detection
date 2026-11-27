"""Client for the Obico ML server."""
from __future__ import annotations

from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)


class MLServerError(HomeAssistantError):
    """The ML server could not be used."""


class MLAuthError(MLServerError):
    """The ML server rejected the secret."""


class MLNoSecretError(MLServerError):
    """The ML server has no secret of its own, so it refuses all requests."""


async def async_predict(
    hass: HomeAssistant, host: str, token: str, image_url: str | None = None
) -> dict[str, Any]:
    """Ask the ML server about an image and return its answer.

    Without an image the server only checks the secret, which is how the connection is tested.
    The image URL carries its own query string (the camera access token), so it is passed as a
    parameter to get it encoded correctly.
    """
    session = async_get_clientsession(hass)
    try:
        async with session.get(
            f"{host.rstrip('/')}/p/",
            params={"img": image_url} if image_url else None,
            headers={"Authorization": f"Bearer {token}"},
            timeout=REQUEST_TIMEOUT,
        ) as response:
            if response.status == 401:
                raise MLAuthError(
                    "The Obico ML server rejected the auth token. Make sure the server and this "
                    "integration use the same secret, and that it is not the old default value."
                )
            if response.status == 503:
                raise MLNoSecretError(
                    "The Obico ML server has no secret of its own and refuses all requests. "
                    "Set a secret in the add-on or with ML_API_TOKEN."
                )
            response.raise_for_status()
            result = await response.json()
    except aiohttp.ClientResponseError as err:
        raise MLServerError(f"The Obico ML server answered with an error: {err.status}") from err
    except (aiohttp.ClientError, TimeoutError) as err:
        raise MLServerError(f"Could not reach the Obico ML server: {err}") from err
    if not isinstance(result, dict):
        raise MLServerError("The Obico ML server gave an answer that was not understood")
    return result
