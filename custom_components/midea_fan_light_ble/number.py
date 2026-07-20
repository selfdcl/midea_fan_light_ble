"""Number controls for the Midea fan light."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MideaFanLightConfigEntry
from .entity import MideaFanLightEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MideaFanLightConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up timer, brightness and color-temperature controls."""
    async_add_entities(
        [
            MideaFanTimer(entry.runtime_data, entry.title),
            MideaBrightness(entry.runtime_data, entry.title),
            MideaColorTemperature(entry.runtime_data, entry.title),
        ]
    )


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
    def native_value(self) -> float | None:
        """Return the remaining timer in hours."""
        if self.coordinator.data is None:
            return None
        minutes = self.coordinator.data.timer_minutes
        return minutes / 60

    async def async_set_native_value(self, value: float) -> None:
        """Set timer to zero through six whole hours."""
        await self.coordinator.async_set_timer(round(value))


class MideaBrightness(MideaFanLightEntity, NumberEntity):
    """Expose light brightness directly on the device page."""

    _attr_translation_key = "brightness"
    _attr_native_min_value = 1
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "%"
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator, entry_title: str) -> None:
        """Initialize the brightness control."""
        super().__init__(coordinator, entry_title, "brightness")

    @property
    def native_value(self) -> float | None:
        """Return brightness as a percentage."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.brightness_percent

    async def async_set_native_value(self, value: float) -> None:
        """Set brightness and turn on the main light when required."""
        percent = max(1, min(100, round(value)))
        raw = max(1, min(255, round(percent * 255 / 100)))
        await self.coordinator.async_turn_on_light(brightness_raw=raw)


class MideaColorTemperature(MideaFanLightEntity, NumberEntity):
    """Expose color temperature directly on the device page."""

    _attr_translation_key = "color_temperature"
    _attr_native_min_value = 2700
    _attr_native_max_value = 6500
    _attr_native_step = 10
    _attr_native_unit_of_measurement = "K"
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator, entry_title: str) -> None:
        """Initialize the color-temperature control."""
        super().__init__(coordinator, entry_title, "color_temperature")

    @property
    def native_value(self) -> float | None:
        """Return color temperature in kelvin."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.color_temperature_kelvin

    async def async_set_native_value(self, value: float) -> None:
        """Set color temperature and turn on the main light when required."""
        kelvin = max(2700, min(6500, round(value)))
        raw = max(0, min(255, round((kelvin - 2700) * 255 / 3800)))
        await self.coordinator.async_turn_on_light(color_raw=raw)
