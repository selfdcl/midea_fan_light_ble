"""Select controls for fan speed and direction."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MideaFanLightConfigEntry
from .entity import MideaFanLightEntity

SPEED_OPTIONS = ["1档", "2档", "3档", "4档", "5档", "6档"]
DIRECTION_FORWARD = "正转"
DIRECTION_REVERSE = "反转"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MideaFanLightConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up visible fan speed and direction controls."""
    async_add_entities(
        [
            MideaFanSpeed(entry.runtime_data, entry.title),
            MideaFanDirection(entry.runtime_data, entry.title),
        ]
    )


class MideaFanSpeed(MideaFanLightEntity, SelectEntity):
    """Expose all six fan speeds directly on the device page."""

    _attr_translation_key = "fan_speed"
    _attr_options = SPEED_OPTIONS

    def __init__(self, coordinator, entry_title: str) -> None:
        """Initialize the speed selector."""
        super().__init__(coordinator, entry_title, "fan_speed")

    @property
    def current_option(self) -> str | None:
        """Return the current speed, or no selection while stopped."""
        if self.coordinator.data is None or not self.coordinator.data.fan_on:
            return None
        speed = self.coordinator.data.speed
        return SPEED_OPTIONS[speed - 1] if 1 <= speed <= 6 else None

    async def async_select_option(self, option: str) -> None:
        """Set a speed and start the fan when required."""
        await self.coordinator.async_set_speed(SPEED_OPTIONS.index(option) + 1)


class MideaFanDirection(MideaFanLightEntity, SelectEntity):
    """Expose fan direction directly on the device page."""

    _attr_translation_key = "fan_direction"
    _attr_options = [DIRECTION_FORWARD, DIRECTION_REVERSE]

    def __init__(self, coordinator, entry_title: str) -> None:
        """Initialize the direction selector."""
        super().__init__(coordinator, entry_title, "fan_direction")

    @property
    def current_option(self) -> str | None:
        """Return current direction, or no selection while stopped."""
        if self.coordinator.data is None or not self.coordinator.data.fan_on:
            return None
        return DIRECTION_REVERSE if self.coordinator.data.reverse else DIRECTION_FORWARD

    async def async_select_option(self, option: str) -> None:
        """Set direction and start the fan when required."""
        await self.coordinator.async_set_direction(option == DIRECTION_REVERSE)
