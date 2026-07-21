"""Fan platform for Midea BLE fan lights."""

from __future__ import annotations

from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.exceptions import HomeAssistantError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MideaFanLightConfigEntry
from .const import (
    FAN_PRESET_AUTO,
    FAN_PRESET_NATURAL,
    FAN_PRESET_STANDARD,
    MODE_FAN,
)
from .entity import MideaFanLightEntity
from .protocol import percentage_to_speed, speed_to_percentage


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
        | FanEntityFeature.PRESET_MODE
    )
    _attr_percentage_step = 100 / 6
    _attr_preset_modes = [FAN_PRESET_STANDARD, FAN_PRESET_NATURAL, FAN_PRESET_AUTO]

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
        return speed_to_percentage(self.coordinator.data.speed)

    @property
    def preset_mode(self) -> str | None:
        """Return the active standard, natural, or automatic wind mode."""
        return self.coordinator.wind_preset

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on."""
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
            return
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
        await self.coordinator.async_set_speed(percentage_to_speed(percentage))

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Select standard, natural, or temperature-driven automatic wind."""
        if preset_mode not in self.preset_modes:
            raise HomeAssistantError(f"Unsupported fan preset: {preset_mode}")
        if preset_mode == FAN_PRESET_NATURAL:
            await self.coordinator.async_set_natural_wind(True)
        elif preset_mode == FAN_PRESET_AUTO:
            await self.coordinator.async_set_auto_wind(True)
        else:
            await self.coordinator.async_set_natural_wind(False)
            await self.coordinator.async_set_auto_wind(False)
