"""Switch platform for Midea BLE fan lights."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MideaFanLightConfigEntry
from .const import MODE_NIGHT_LIGHT
from .entity import MideaFanLightEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MideaFanLightConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the night-light switch."""
    async_add_entities([MideaNightLight(entry.runtime_data, entry.title)])


class MideaNightLight(MideaFanLightEntity, SwitchEntity):
    """Night-light mode control."""

    _attr_translation_key = "night_light"

    def __init__(self, coordinator, entry_title: str) -> None:
        """Initialize the night-light switch."""
        super().__init__(coordinator, entry_title, "night_light")

    @property
    def is_on(self) -> bool | None:
        """Return whether night-light mode is active."""
        return self.coordinator.data.night_light_on if self.coordinator.data else None

    async def async_turn_on(self, **kwargs) -> None:
        """Enable night-light mode."""
        await self.coordinator.async_set_mode_bit(MODE_NIGHT_LIGHT, True)

    async def async_turn_off(self, **kwargs) -> None:
        """Disable night-light mode."""
        await self.coordinator.async_set_mode_bit(MODE_NIGHT_LIGHT, False)
