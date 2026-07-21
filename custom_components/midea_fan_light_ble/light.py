"""Light platform for Midea BLE fan lights."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MideaFanLightConfigEntry
from .entity import MideaFanLightEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MideaFanLightConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the main light entity."""
    async_add_entities([MideaMainLight(entry.runtime_data, entry.title)])


class MideaMainLight(MideaFanLightEntity, LightEntity):
    """Main light switch."""

    _attr_translation_key = "main_light"
    _attr_supported_color_modes = {ColorMode.COLOR_TEMP}
    _attr_color_mode = ColorMode.COLOR_TEMP
    _attr_min_color_temp_kelvin = 2700
    _attr_max_color_temp_kelvin = 6500

    def __init__(self, coordinator, entry_title: str) -> None:
        """Initialize the main light."""
        super().__init__(coordinator, entry_title, "main_light")

    @property
    def is_on(self) -> bool | None:
        """Return the current light power bit."""
        return self.coordinator.data.light_on if self.coordinator.data else None

    @property
    def brightness(self) -> int | None:
        """Return native 0..255 brightness."""
        return self.coordinator.data.brightness_raw if self.coordinator.data else None

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return decoded color temperature in kelvin."""
        return (
            self.coordinator.data.color_temperature_kelvin
            if self.coordinator.data
            else None
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on and optionally adjust brightness/color temperature."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness is not None and brightness <= 0:
            await self.coordinator.async_turn_off_light()
            return

        kelvin = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
        color_raw = None
        if kelvin is not None:
            kelvin = max(2700, min(6500, int(kelvin)))
            color_raw = round((kelvin - 2700) * 255 / 3800)
        await self.coordinator.async_turn_on_light(
            brightness_raw=brightness,
            color_raw=color_raw,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self.coordinator.async_turn_off_light()
