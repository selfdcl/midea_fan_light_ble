"""Sensor platform for formatted fan timer state."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MideaFanLightConfigEntry
from .entity import MideaFanLightEntity
from .protocol import format_timer_minutes


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MideaFanLightConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the formatted remaining-time sensor."""
    async_add_entities([MideaTimerRemaining(entry.runtime_data, entry.title)])


class MideaTimerRemaining(MideaFanLightEntity, SensorEntity):
    """Show the device-reported countdown as HH:MM."""

    _attr_translation_key = "timer_remaining"
    _attr_icon = "mdi:timer-outline"

    def __init__(self, coordinator, entry_title: str) -> None:
        """Initialize the remaining-time sensor."""
        super().__init__(coordinator, entry_title, "timer_remaining")

    @property
    def native_value(self) -> str | None:
        """Return remaining countdown using a zero-padded HH:MM value."""
        if self.coordinator.data is None:
            return None
        return format_timer_minutes(self.coordinator.data.timer_minutes)
