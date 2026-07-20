"""Fan platform for Midea BLE fan lights."""

from __future__ import annotations

from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MideaFanLightConfigEntry
from .const import MODE_FAN
from .entity import MideaFanLightEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MideaFanLightConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the fan entity."""
    async_add_entities([MideaFan(entry.runtime_data, entry.title)])


class MideaFan(MideaFanLightEntity, FanEntity):
    """Fan on/off control."""

    _attr_translation_key = "fan"
    _attr_supported_features = FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF

    def __init__(self, coordinator, entry_title: str) -> None:
        """Initialize the fan."""
        super().__init__(coordinator, entry_title, "fan")

    @property
    def is_on(self) -> bool | None:
        """Return whether the fan is running."""
        return self.coordinator.data.fan_on if self.coordinator.data else None

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on."""
        await self.coordinator.async_set_mode_bit(MODE_FAN, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        await self.coordinator.async_set_mode_bit(MODE_FAN, False)
