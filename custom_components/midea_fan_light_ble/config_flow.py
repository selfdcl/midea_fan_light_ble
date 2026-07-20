"""Config flow for Midea BLE fan lights."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .const import DOMAIN
from .coordinator import state_from_service_info
from .protocol import normalize_address


def _device_title(address: str) -> str:
    """Create a stable default name from a Bluetooth address."""
    suffix = address.replace(":", "")[-6:]
    return f"美的风扇灯 {suffix}"


class MideaFanLightConfigFlow(ConfigFlow, domain=DOMAIN):
    """Discover and add Midea BLE fan lights."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle automatic Bluetooth discovery."""
        if state_from_service_info(discovery_info) is None:
            return self.async_abort(reason="not_supported")

        address = normalize_address(discovery_info.address)
        await self.async_set_unique_id(address)
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {"name": _device_title(address)}
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm an automatically discovered device."""
        if self._discovery_info is None:
            return self.async_abort(reason="no_devices_found")

        address = normalize_address(self._discovery_info.address)
        if user_input is not None:
            return self.async_create_entry(
                title=_device_title(address), data={CONF_ADDRESS: address}
            )

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "name": _device_title(address),
                "address": address,
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user select any currently discovered compatible device."""
        if user_input is not None:
            address = normalize_address(user_input[CONF_ADDRESS])
            discovery_info = self._discovered_devices[address]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=_device_title(address),
                data={CONF_ADDRESS: normalize_address(discovery_info.address)},
            )

        current_ids = self._async_current_ids(include_ignore=False)
        self._discovered_devices.clear()
        for discovery_info in bluetooth.async_discovered_service_info(
            self.hass, connectable=True
        ):
            address = normalize_address(discovery_info.address)
            if (
                address in current_ids
                or state_from_service_info(discovery_info) is None
            ):
                continue
            self._discovered_devices[address] = discovery_info

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        choices = {
            address: f"{_device_title(address)} ({address})"
            for address in self._discovered_devices
        }
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(choices)}),
        )
