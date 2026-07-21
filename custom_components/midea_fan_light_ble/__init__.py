"""Midea BLE fan light integration."""

from __future__ import annotations

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er

from .bridge import async_available_bridge_actions
from .const import CONF_BRIDGE_ACTION, DOMAIN, PLATFORMS
from .coordinator import MideaFanLightCoordinator

MideaFanLightConfigEntry = ConfigEntry[MideaFanLightCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: MideaFanLightConfigEntry
) -> bool:
    """Set up a configured fan light."""
    address = entry.data[CONF_ADDRESS]
    available_bridges = async_available_bridge_actions(hass)
    bridge_action = entry.data.get(CONF_BRIDGE_ACTION)
    if bridge_action not in available_bridges:
        if len(available_bridges) != 1:
            raise ConfigEntryNotReady(
                "Exactly one ESPHome Midea BLE broadcast bridge must be available"
            )
        bridge_action = next(iter(available_bridges))
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_BRIDGE_ACTION: bridge_action},
        )

    coordinator = MideaFanLightCoordinator(hass, address, entry.title, bridge_action)
    entry.runtime_data = coordinator

    registry = er.async_get(hass)
    for domain, entity_key in (
        ("number", "brightness"),
        ("number", "color_temperature"),
        ("select", "fan_speed"),
        ("select", "fan_direction"),
    ):
        if entity_id := registry.async_get_entity_id(
            domain, DOMAIN, f"{coordinator.address}_{entity_key}"
        ):
            registry.async_remove(entity_id)

    coordinator.process_initial_service_info(
        bluetooth.async_last_service_info(hass, address, connectable=False)
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(coordinator.async_shutdown)
    entry.async_on_unload(coordinator.async_start())
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: MideaFanLightConfigEntry
) -> bool:
    """Unload a configured fan light."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
