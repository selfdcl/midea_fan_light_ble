"""Bluetooth state and GATT command coordinator."""

from __future__ import annotations

import asyncio
import logging

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

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
    COMMAND_BY_MODE_BIT,
    CONTROL_CHARACTERISTIC_UUID,
    CONTROL_TIMEOUT,
    MANUFACTURER_ID,
    NOTIFY_SETTLE_TIME,
    STATE_CHARACTERISTIC_UUID,
)
from .protocol import (
    MideaFanLightState,
    MideaProtocolError,
    build_control_frame,
    normalize_address,
    parse_advertisement,
    parse_bbb1,
)

_LOGGER = logging.getLogger(__name__)


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
    """Receive advertisements and serialize short-lived GATT commands."""

    def __init__(self, hass: HomeAssistant, address: str, name: str) -> None:
        """Initialize the coordinator."""
        self.address = normalize_address(address)
        self.name = name
        self._connect_lock = asyncio.Lock()
        self._next_sequence = 0
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
    def _process_service_info(self, service_info: BluetoothServiceInfoBleak) -> None:
        """Parse and publish one advertisement."""
        if state := state_from_service_info(service_info):
            self.data = state
            self._available = True
            self.async_update_listeners()

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ) -> None:
        """Handle an advertisement delivered by the Bluetooth manager."""
        if state := state_from_service_info(service_info):
            self.data = state
            super()._async_handle_bluetooth_event(service_info, change)

    @callback
    def _async_handle_unavailable(
        self, service_info: BluetoothServiceInfoBleak
    ) -> None:
        """Mark entities unavailable when no scanner can see the device."""
        super()._async_handle_unavailable(service_info)

    @callback
    def _accept_gatt_state(self, state: MideaFanLightState) -> None:
        """Publish a BBB1 state and synchronize the next sequence."""
        if state.sequence is not None:
            self._next_sequence = (state.sequence + 1) & 0x0F
        self.data = state
        self._available = True
        self.async_update_listeners()

    async def async_set_mode_bit(self, mode_bit: int, desired_on: bool) -> None:
        """Toggle one feature only when its cached state differs."""
        command = COMMAND_BY_MODE_BIT.get(mode_bit)
        if command is None:
            raise HomeAssistantError(f"Unsupported mode bit: 0x{mode_bit:02X}")

        async with self._connect_lock:
            if (
                self.data is not None
                and self.data.mode_bit_is_on(mode_bit) == desired_on
            ):
                return
            if self.data is None:
                raise HomeAssistantError(
                    "No state advertisement has been received from the device"
                )

            ble_device = bluetooth.async_ble_device_from_address(
                self.hass, self.address, connectable=True
            )
            if ble_device is None:
                reason = bluetooth.async_address_reachability_diagnostics(
                    self.hass,
                    self.address,
                    bluetooth.BluetoothReachabilityIntent.CONNECTION,
                )
                raise HomeAssistantError(f"Bluetooth device is unreachable: {reason}")

            client = await establish_connection(
                BleakClientWithServiceCache,
                ble_device,
                self.name,
                max_attempts=3,
            )
            expected_state_received = asyncio.Event()

            def notification_handler(
                _characteristic: BleakGATTCharacteristic, data: bytearray
            ) -> None:
                try:
                    state = parse_bbb1(bytes(data))
                except MideaProtocolError as err:
                    _LOGGER.debug("Ignoring unsupported BBB1 packet: %s", err)
                    return

                @callback
                def publish_notification() -> None:
                    self._accept_gatt_state(state)
                    if state.mode_bit_is_on(mode_bit) == desired_on:
                        expected_state_received.set()

                self.hass.loop.call_soon_threadsafe(publish_notification)

            try:
                await client.start_notify(
                    STATE_CHARACTERISTIC_UUID, notification_handler
                )
                await asyncio.sleep(NOTIFY_SETTLE_TIME)

                # Some firmware revisions immediately notify their current state when
                # CCCD is enabled. Avoid toggling if that state already satisfies the call.
                if (
                    self.data is not None
                    and self.data.mode_bit_is_on(mode_bit) == desired_on
                ):
                    return

                expected_state_received.clear()
                sequence = self._next_sequence
                self._next_sequence = (sequence + 1) & 0x0F
                frame = build_control_frame(command, sequence)
                _LOGGER.debug(
                    "%s: BBB0 command=%02X sequence=%X frame=%s",
                    self.address,
                    command,
                    sequence,
                    frame.hex(" ").upper(),
                )
                await client.write_gatt_char(
                    CONTROL_CHARACTERISTIC_UUID, frame, response=True
                )
                try:
                    await asyncio.wait_for(
                        expected_state_received.wait(), timeout=CONTROL_TIMEOUT
                    )
                except TimeoutError as err:
                    raise HomeAssistantError(
                        "The device accepted the GATT write but did not confirm the new state"
                    ) from err
            finally:
                if client.is_connected:
                    await client.disconnect()
                bluetooth.async_clear_advertisement_history(self.hass, self.address)
