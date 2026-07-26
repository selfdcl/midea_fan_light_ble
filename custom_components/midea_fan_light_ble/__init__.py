"""Midea BLE fan light integration."""

from __future__ import annotations

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er

from .bridge import async_available_bridge_actions
from .const import (
    CONF_AUTO_TEMP_2,
    CONF_AUTO_TEMP_3,
    CONF_AUTO_TEMP_4,
    CONF_AUTO_TEMP_5,
    CONF_AUTO_TEMP_6,
    CONF_BRIDGE_ACTION,
    CONF_TEMPERATURE_ENTITY,
    CONF_XOR_BASE,
    DEFAULT_AUTO_THRESHOLDS,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import MideaFanLightCoordinator
from .protocol import DEFAULT_XOR_BASE, format_xor_base, xor_base_for_address

MideaFanLightConfigEntry = ConfigEntry[MideaFanLightCoordinator]


async def async_migrate_entry(
    hass: HomeAssistant, entry: MideaFanLightConfigEntry
) -> bool:
    """Add the device-specific protocol key to entries created before v3."""
    if entry.version >= 3:
        return True

    data = dict(entry.data)
    address = data[CONF_ADDRESS]
    base = xor_base_for_address(address) or DEFAULT_XOR_BASE
    data[CONF_XOR_BASE] = format_xor_base(base)
    hass.config_entries.async_update_entry(entry, data=data, version=3)
    return True


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

    threshold_keys = (
        CONF_AUTO_TEMP_2,
        CONF_AUTO_TEMP_3,
        CONF_AUTO_TEMP_4,
        CONF_AUTO_TEMP_5,
        CONF_AUTO_TEMP_6,
    )
    auto_thresholds = tuple(
        float(entry.options.get(key, default))
        for key, default in zip(threshold_keys, DEFAULT_AUTO_THRESHOLDS)
    )
    xor_base = entry.options.get(CONF_XOR_BASE, entry.data.get(CONF_XOR_BASE))
    if xor_base is None:
        xor_base = format_xor_base(xor_base_for_address(address) or DEFAULT_XOR_BASE)
    coordinator = MideaFanLightCoordinator(
        hass,
        address,
        entry.title,
        bridge_action,
        xor_base,
        entry.options.get(CONF_TEMPERATURE_ENTITY),
        auto_thresholds,
    )
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
