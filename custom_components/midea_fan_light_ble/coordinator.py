"""Bluetooth state and connectionless broadcast command coordinator."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothChange,
    BluetoothServiceInfoBleak,
)
from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothDataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .const import (
    COMMAND_BRIGHTNESS,
    COMMAND_BY_MODE_BIT,
    COMMAND_COLOR_TEMPERATURE,
    COMMAND_REVERSE,
    COMMAND_SPEED_BY_LEVEL,
    COMMAND_TIMER_BY_HOURS,
    CONTROL_TIMEOUT,
    MANUFACTURER_ID,
    MODE_FAN,
    MODE_LIGHT,
)
from .protocol import (
    MideaFanLightState,
    MideaProtocolError,
    normalize_address,
    parse_advertisement,
)

_LOGGER = logging.getLogger(__name__)

StatePredicate = Callable[[MideaFanLightState], bool]


def state_from_service_info(
    service_info: BluetoothServiceInfoBleak,
) -> MideaFanLightState | None:
    """Parse a supported state advertisement, or return None."""
    manufacturer_data = service_info.manufacturer_data.get(MANUFACTURER_ID)
    if manufacturer_data is None:
        return None
    try:
        return parse_advertisement(
            bytes(manufacturer_data),
            address=service_info.address,
            rssi=service_info.rssi,
        )
    except MideaProtocolError:
        return None


class MideaFanLightCoordinator(PassiveBluetoothDataUpdateCoordinator):
    """Receive 0x06A8 state and send controls through an ESPHome bridge."""

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        name: str,
        bridge_action: str,
    ) -> None:
        """Initialize the coordinator."""
        self.address = normalize_address(address)
        self._device_name = name
        self._bridge_action = bridge_action
        self._control_lock = asyncio.Lock()
        self._control_state_event: asyncio.Event | None = None
        self.data: MideaFanLightState | None = None
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            address=self.address,
            mode=bluetooth.BluetoothScanningMode.PASSIVE,
            connectable=False,
        )

    @callback
    def process_initial_service_info(
        self, service_info: BluetoothServiceInfoBleak | None
    ) -> None:
        """Seed state from Home Assistant's latest advertisement cache."""
        if service_info is not None:
            self._process_service_info(service_info)

    @callback
    def _publish_state(self, state: MideaFanLightState) -> None:
        """Publish state and wake a pending broadcast command waiter."""
        self.data = state
        self._available = True
        self.async_update_listeners()
        if self._control_state_event is not None:
            self._control_state_event.set()

    @callback
    def _process_service_info(self, service_info: BluetoothServiceInfoBleak) -> None:
        """Parse and publish one advertisement."""
        if state := state_from_service_info(service_info):
            self._publish_state(state)

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ) -> None:
        """Handle an advertisement delivered by the Bluetooth manager."""
        if state_from_service_info(service_info) is not None:
            super()._async_handle_bluetooth_event(service_info, change)

    @callback
    def _async_handle_unavailable(
        self, service_info: BluetoothServiceInfoBleak
    ) -> None:
        """Mark entities unavailable when no scanner can see the device."""
        super()._async_handle_unavailable(service_info)

    def _require_state(self) -> MideaFanLightState:
        """Return cached state or raise a user-facing error."""
        if self.data is None:
            raise HomeAssistantError(
                "No state advertisement has been received from the device"
            )
        return self.data

    async def _async_broadcast_and_wait(
        self,
        command: int,
        predicate: StatePredicate,
        *,
        value: int = 0,
        light_command: bool = False,
    ) -> None:
        """Call the ESPHome bridge and wait for matching 0x06A8 state."""
        event = asyncio.Event()
        self._control_state_event = event
        try:
            _LOGGER.debug(
                "%s: broadcast bridge=%s command=%02X value=%02X light=%s",
                self.address,
                self._bridge_action,
                command,
                value,
                light_command,
            )
            await self.hass.services.async_call(
                "esphome",
                self._bridge_action,
                {
                    "address": self.address,
                    "command": command,
                    "value": value,
                    "light_command": light_command,
                },
                blocking=True,
            )

            deadline = self.hass.loop.time() + CONTROL_TIMEOUT
            while True:
                event.clear()
                if self.data is not None and predicate(self.data):
                    return
                remaining = deadline - self.hass.loop.time()
                if remaining <= 0:
                    raise TimeoutError
                await asyncio.wait_for(event.wait(), timeout=remaining)
        except TimeoutError as err:
            raise HomeAssistantError(
                "The broadcast bridge sent the command but no matching state was received"
            ) from err
        finally:
            self._control_state_event = None

    async def _async_toggle_locked(self, mode_bit: int, desired_on: bool) -> None:
        """Toggle one feature while the caller holds the control lock."""
        state = self._require_state()
        if state.mode_bit_is_on(mode_bit) == desired_on:
            return
        command = COMMAND_BY_MODE_BIT.get(mode_bit)
        if command is None:
            raise HomeAssistantError(f"Unsupported mode bit: 0x{mode_bit:02X}")
        await self._async_broadcast_and_wait(
            command,
            lambda updated: updated.mode_bit_is_on(mode_bit) == desired_on,
        )

    async def async_set_mode_bit(self, mode_bit: int, desired_on: bool) -> None:
        """Set a toggle feature through connectionless BLE advertising."""
        async with self._control_lock:
            await self._async_toggle_locked(mode_bit, desired_on)

    async def async_turn_on_light(
        self,
        *,
        brightness_raw: int | None = None,
        color_raw: int | None = None,
    ) -> None:
        """Turn on the light and optionally set color temperature/brightness."""
        async with self._control_lock:
            await self._async_toggle_locked(MODE_LIGHT, True)
            if color_raw is not None and self._require_state().color_raw != color_raw:
                await self._async_broadcast_and_wait(
                    COMMAND_COLOR_TEMPERATURE,
                    lambda state: abs(state.color_raw - color_raw) <= 1,
                    value=color_raw,
                    light_command=True,
                )
            if (
                brightness_raw is not None
                and self._require_state().brightness_raw != brightness_raw
            ):
                await self._async_broadcast_and_wait(
                    COMMAND_BRIGHTNESS,
                    lambda state: abs(state.brightness_raw - brightness_raw) <= 1,
                    value=brightness_raw,
                    light_command=True,
                )

    async def async_set_speed(self, speed: int) -> None:
        """Set one of the six fan speeds, starting the fan when required."""
        command = COMMAND_SPEED_BY_LEVEL.get(speed)
        if command is None:
            raise HomeAssistantError(f"Unsupported fan speed: {speed}")
        async with self._control_lock:
            await self._async_toggle_locked(MODE_FAN, True)
            if self._require_state().speed == speed:
                return
            await self._async_broadcast_and_wait(
                command,
                lambda state: state.fan_on and state.speed == speed,
            )

    async def async_set_direction(self, reverse: bool) -> None:
        """Set fan direction; the device command toggles the current direction."""
        async with self._control_lock:
            await self._async_toggle_locked(MODE_FAN, True)
            if self._require_state().reverse == reverse:
                return
            await self._async_broadcast_and_wait(
                COMMAND_REVERSE,
                lambda state: state.fan_on and state.reverse == reverse,
            )

    async def async_set_timer(self, hours: int) -> None:
        """Set the fan timer to an integer hour from zero through six."""
        command = COMMAND_TIMER_BY_HOURS.get(hours)
        if command is None:
            raise HomeAssistantError(f"Unsupported timer value: {hours}")
        async with self._control_lock:
            if hours > 0:
                await self._async_toggle_locked(MODE_FAN, True)

            def timer_matches(state: MideaFanLightState) -> bool:
                if hours == 0:
                    return state.timer_minutes == 0
                return (hours - 1) * 60 < state.timer_minutes <= hours * 60

            current_minutes = self._require_state().timer_minutes
            if current_minutes == hours * 60:
                return
            await self._async_broadcast_and_wait(command, timer_matches)
