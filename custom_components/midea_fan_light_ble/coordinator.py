"""Bluetooth state and connectionless broadcast command coordinator."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
import random

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothChange,
    BluetoothServiceInfoBleak,
)
from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothDataUpdateCoordinator,
)
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, UnitOfTemperature
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import (
    COMMAND_BRIGHTNESS,
    COMMAND_BY_MODE_BIT,
    COMMAND_COLOR_TEMPERATURE,
    COMMAND_REVERSE,
    COMMAND_SPEED_BY_LEVEL,
    COMMAND_TIMER_BY_HOURS,
    CONTROL_TIMEOUT,
    DOMAIN,
    FAN_PRESET_AUTO,
    FAN_PRESET_NATURAL,
    FAN_PRESET_STANDARD,
    MANUFACTURER_ID,
    MODE_FAN,
    MODE_LIGHT,
    MODE_NIGHT_LIGHT,
)
from .protocol import (
    MideaFanLightState,
    MideaProtocolError,
    normalize_address,
    parse_advertisement,
    temperature_to_speed,
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
        temperature_entity: str | None,
        auto_thresholds: tuple[float, float, float, float, float],
    ) -> None:
        """Initialize the coordinator."""
        self.address = normalize_address(address)
        self._device_name = name
        self._bridge_action = bridge_action
        self._control_lock = asyncio.Lock()
        self._control_state_event: asyncio.Event | None = None
        self._natural_wind_enabled = False
        self._natural_wind_task: asyncio.Task[None] | None = None
        self._auto_wind_enabled = False
        self._temperature_entity = temperature_entity
        self._auto_thresholds = auto_thresholds
        self._auto_temperature_unsub: Callable[[], None] | None = None
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
        if not state.fan_on:
            self._stop_wind_modes()
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
        if state := state_from_service_info(service_info):
            self._publish_state(state)

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

    @property
    def natural_wind_enabled(self) -> bool:
        """Return whether local natural-wind modulation is running."""
        return self._natural_wind_enabled

    @property
    def wind_preset(self) -> str:
        """Return the active local wind preset."""
        if self._auto_wind_enabled:
            return FAN_PRESET_AUTO
        if self._natural_wind_enabled:
            return FAN_PRESET_NATURAL
        return FAN_PRESET_STANDARD

    @callback
    def _stop_natural_wind(self) -> None:
        """Stop the natural-wind background task without changing fan power."""
        was_enabled = self._natural_wind_enabled
        self._natural_wind_enabled = False
        task = self._natural_wind_task
        self._natural_wind_task = None
        if task is not None and task is not asyncio.current_task():
            task.cancel()
        if was_enabled:
            self.async_update_listeners()

    @callback
    def _stop_auto_wind(self) -> None:
        """Stop temperature-driven automatic speed changes."""
        was_enabled = self._auto_wind_enabled
        self._auto_wind_enabled = False
        if self._auto_temperature_unsub is not None:
            self._auto_temperature_unsub()
            self._auto_temperature_unsub = None
        if was_enabled:
            self.async_update_listeners()

    @callback
    def _stop_wind_modes(self) -> None:
        """Return to standard wind without changing fan power."""
        self._stop_natural_wind()
        self._stop_auto_wind()

    @callback
    def async_shutdown(self) -> None:
        """Cancel integration-owned background work during config-entry unload."""
        self._stop_wind_modes()

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
        if mode_bit == MODE_FAN and not desired_on:
            self._stop_wind_modes()
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
            if self._require_state().night_light_on:
                await self._async_toggle_locked(MODE_NIGHT_LIGHT, False)
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

    async def async_turn_off_light(self) -> None:
        """Turn off whichever mode the combined light entity is using."""
        async with self._control_lock:
            state = self._require_state()
            mode_bit = MODE_NIGHT_LIGHT if state.night_light_on else MODE_LIGHT
            await self._async_toggle_locked(mode_bit, False)

    async def _async_set_speed_locked(self, speed: int) -> None:
        """Set fan speed while the caller owns the control lock."""
        command = COMMAND_SPEED_BY_LEVEL.get(speed)
        if command is None:
            raise HomeAssistantError(f"Unsupported fan speed: {speed}")
        await self._async_toggle_locked(MODE_FAN, True)
        if self._require_state().speed == speed:
            return
        await self._async_broadcast_and_wait(
            command,
            lambda state: state.fan_on and state.speed == speed,
        )

    async def async_set_speed(self, speed: int) -> None:
        """Set one of the six fan speeds, starting the fan when required."""
        self._stop_wind_modes()
        async with self._control_lock:
            await self._async_set_speed_locked(speed)

    async def async_set_natural_wind(self, enabled: bool) -> None:
        """Enable or disable random 1..6 speed changes every minute."""
        if not enabled:
            self._stop_natural_wind()
            return
        self._stop_auto_wind()
        async with self._control_lock:
            await self._async_toggle_locked(MODE_FAN, True)
            if self._natural_wind_enabled:
                return
            self._natural_wind_enabled = True
            self._natural_wind_task = self.hass.async_create_task(
                self._async_natural_wind_loop(),
                f"{DOMAIN} natural wind {self.address}",
                eager_start=True,
            )
            self.async_update_listeners()

    async def _async_natural_wind_loop(self) -> None:
        """Periodically choose a different fan speed while enabled."""
        try:
            while self._natural_wind_enabled:
                await asyncio.sleep(60)
                async with self._control_lock:
                    if not self._natural_wind_enabled:
                        return
                    current = self._require_state().speed
                    choices = [speed for speed in range(1, 7) if speed != current]
                    await self._async_set_speed_locked(random.choice(choices))
        except asyncio.CancelledError:
            pass
        except Exception:
            _LOGGER.exception("%s: natural-wind loop failed", self.address)
            self._stop_natural_wind()

    def _auto_temperature(self) -> float:
        """Return the configured temperature converted to Celsius."""
        if self._temperature_entity is None:
            raise HomeAssistantError(
                "Configure a temperature sensor before selecting automatic mode"
            )
        state = self.hass.states.get(self._temperature_entity)
        if state is None or state.state in ("unknown", "unavailable"):
            raise HomeAssistantError(
                f"Temperature sensor {self._temperature_entity} is unavailable"
            )
        try:
            temperature = float(state.state)
        except ValueError as err:
            raise HomeAssistantError(
                f"Temperature sensor {self._temperature_entity} is not numeric"
            ) from err
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        if unit and unit != UnitOfTemperature.CELSIUS:
            try:
                temperature = TemperatureConverter.convert(
                    temperature, unit, UnitOfTemperature.CELSIUS
                )
            except ValueError as err:
                raise HomeAssistantError(
                    f"Temperature sensor {self._temperature_entity} has unsupported unit {unit}"
                ) from err
        return temperature

    async def async_set_auto_wind(self, enabled: bool) -> None:
        """Enable temperature-driven automatic fan speed."""
        if not enabled:
            self._stop_auto_wind()
            return
        temperature = self._auto_temperature()
        speed = temperature_to_speed(temperature, self._auto_thresholds)
        self._stop_natural_wind()
        async with self._control_lock:
            await self._async_set_speed_locked(speed)
            if self._auto_wind_enabled:
                return
            self._auto_wind_enabled = True
            self._auto_temperature_unsub = async_track_state_change_event(
                self.hass,
                [self._temperature_entity],
                self._auto_temperature_changed,
            )
            self.async_update_listeners()

    @callback
    def _auto_temperature_changed(self, event: Event) -> None:
        """Schedule a speed update after the selected temperature changes."""
        if not self._auto_wind_enabled:
            return
        self.hass.async_create_task(
            self._async_apply_auto_temperature(),
            f"{DOMAIN} automatic wind {self.address}",
            eager_start=True,
        )

    async def _async_apply_auto_temperature(self) -> None:
        """Apply the current temperature to the fan speed."""
        try:
            temperature = self._auto_temperature()
            speed = temperature_to_speed(temperature, self._auto_thresholds)
            async with self._control_lock:
                if not self._auto_wind_enabled:
                    return
                await self._async_set_speed_locked(speed)
        except HomeAssistantError:
            _LOGGER.warning(
                "%s: automatic wind skipped because its temperature source is unavailable",
                self.address,
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
