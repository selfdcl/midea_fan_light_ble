"""Midea BLE fan light integration."""

from __future__ import annotations

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import MideaFanLightCoordinator

MideaFanLightConfigEntry = ConfigEntry[MideaFanLightCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: MideaFanLightConfigEntry
) -> bool:
    """Set up a configured fan light."""
    address = entry.data[CONF_ADDRESS]
    coordinator = MideaFanLightCoordinator(hass, address, entry.title)
    entry.runtime_data = coordinator

    coordinator.process_initial_service_info(
        bluetooth.async_last_service_info(hass, address, connectable=False)
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(coordinator.async_start())
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: MideaFanLightConfigEntry
) -> bool:
    """Unload a configured fan light."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
