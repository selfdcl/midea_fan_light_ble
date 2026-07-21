"""Number platform for the fan timer."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MideaFanLightConfigEntry
from .entity import MideaFanLightEntity
from .protocol import timer_minutes_to_hour_slot


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MideaFanLightConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the timer number entity."""
    async_add_entities([MideaFanTimer(entry.runtime_data, entry.title)])


class MideaFanTimer(MideaFanLightEntity, NumberEntity):
    """Fan countdown timer in whole-hour presets."""

    _attr_translation_key = "timer"
    _attr_native_min_value = 0
    _attr_native_max_value = 6
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator, entry_title: str) -> None:
        """Initialize the timer entity."""
        super().__init__(coordinator, entry_title, "timer")

    @property
    def native_value(self) -> int | None:
        """Return the remaining timer's whole-hour preset slot."""
        if self.coordinator.data is None:
            return None
        return timer_minutes_to_hour_slot(self.coordinator.data.timer_minutes)

    async def async_set_native_value(self, value: float) -> None:
        """Set timer to zero through six whole hours."""
        await self.coordinator.async_set_timer(round(value))
