"""Light platform for Midea BLE fan lights."""

from __future__ import annotations

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MideaFanLightConfigEntry
from .const import MODE_LIGHT
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
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_color_mode = ColorMode.ONOFF

    def __init__(self, coordinator, entry_title: str) -> None:
        """Initialize the main light."""
        super().__init__(coordinator, entry_title, "main_light")

    @property
    def is_on(self) -> bool | None:
        """Return the current light power bit."""
        return self.coordinator.data.light_on if self.coordinator.data else None

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the light on."""
        await self.coordinator.async_set_mode_bit(MODE_LIGHT, True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the light off."""
        await self.coordinator.async_set_mode_bit(MODE_LIGHT, False)
