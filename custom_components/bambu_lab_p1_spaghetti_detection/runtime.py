"""What the integration keeps while it is set up."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from homeassistant.core import HomeAssistant

from .const import DOMAIN


@dataclass
class Runtime:
    """The entities the detection works with, and the detection itself."""

    numbers: dict[str, Any] = field(default_factory=dict)
    last_notify: Any = None
    status: Any = None
    engine: Any = None


def get_runtime(hass: HomeAssistant, entry_id: str) -> Runtime | None:
    return hass.data.get(DOMAIN, {}).get(entry_id)
