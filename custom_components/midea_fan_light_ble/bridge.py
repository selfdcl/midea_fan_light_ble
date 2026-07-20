"""Helpers for discovering the ESPHome broadcast bridge action."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .const import BRIDGE_ACTION_SUFFIX


def async_available_bridge_actions(hass: HomeAssistant) -> dict[str, str]:
    """Return registered ESPHome actions compatible with this integration."""
    esphome_actions = hass.services.async_services().get("esphome", {})
    return {
        action: action.replace("_", " ").title()
        for action in sorted(esphome_actions)
        if action.endswith(BRIDGE_ACTION_SUFFIX)
    }
