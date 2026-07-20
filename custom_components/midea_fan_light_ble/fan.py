"""Fan platform for Midea BLE fan lights."""

from __future__ import annotations

import math
from typing import Any

from homeassistant.components.fan import (
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    FanEntity,
    FanEntityFeature,
)
from homeassistant.exceptions import HomeAssistantError
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
    _attr_supported_features = (
        FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.SET_SPEED
        | FanEntityFeature.DIRECTION
    )
    _attr_percentage_step = 100 / 6

    def __init__(self, coordinator, entry_title: str) -> None:
        """Initialize the fan."""
        super().__init__(coordinator, entry_title, "fan")

    @property
    def is_on(self) -> bool | None:
        """Return whether the fan is running."""
        return self.coordinator.data.fan_on if self.coordinator.data else None

    @property
    def percentage(self) -> int | None:
        """Return six fan levels as a Home Assistant percentage."""
        if self.coordinator.data is None:
            return None
        if not self.coordinator.data.fan_on:
            return 0
        return round(self.coordinator.data.speed * 100 / 6)

    @property
    def current_direction(self) -> str | None:
        """Return current forward/reverse direction."""
        if self.coordinator.data is None or not self.coordinator.data.fan_on:
            return None
        return DIRECTION_REVERSE if self.coordinator.data.reverse else DIRECTION_FORWARD

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on."""
        if percentage is not None and percentage > 0:
            await self.async_set_percentage(percentage)
            return
        await self.coordinator.async_set_mode_bit(MODE_FAN, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        await self.coordinator.async_set_mode_bit(MODE_FAN, False)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set one of six speed levels, or turn off at zero percent."""
        if percentage <= 0:
            await self.coordinator.async_set_mode_bit(MODE_FAN, False)
            return
        speed = max(1, min(6, math.ceil(percentage * 6 / 100)))
        await self.coordinator.async_set_speed(speed)

    async def async_set_direction(self, direction: str) -> None:
        """Set forward or reverse direction."""
        if direction not in (DIRECTION_FORWARD, DIRECTION_REVERSE):
            raise HomeAssistantError(f"Unsupported fan direction: {direction}")
        await self.coordinator.async_set_direction(direction == DIRECTION_REVERSE)
