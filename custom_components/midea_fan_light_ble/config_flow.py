"""Config flow for Midea BLE fan lights."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_ADDRESS, Platform, UnitOfTemperature
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .bridge import async_available_bridge_actions
from .const import (
    CONF_AUTO_TEMP_2,
    CONF_AUTO_TEMP_3,
    CONF_AUTO_TEMP_4,
    CONF_AUTO_TEMP_5,
    CONF_AUTO_TEMP_6,
    CONF_BRIDGE_ACTION,
    CONF_TEMPERATURE_ENTITY,
    CONF_XOR_BASE,
    DEFAULT_AUTO_THRESHOLDS,
    DOMAIN,
)
from .coordinator import state_from_service_info
from .protocol import (
    MideaProtocolError,
    format_xor_base,
    normalize_address,
    xor_base_for_address,
)


def _device_title(address: str) -> str:
    """Create a stable default name from a Bluetooth address."""
    suffix = address.replace(":", "")[-6:]
    return f"美的风扇灯 {suffix}"


class MideaFanLightConfigFlow(ConfigFlow, domain=DOMAIN):
    """Discover and add Midea BLE fan lights."""

    VERSION = 3

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> MideaFanLightOptionsFlow:
        """Return the automatic-mode options flow."""
        return MideaFanLightOptionsFlow()

    def __init__(self) -> None:
        """Initialize the flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}
        self._bridge_actions: dict[str, str] = {}
        self._pending_address: str | None = None
        self._pending_bridge: str | None = None

    def _entry_data(self, address: str, bridge_action: str) -> dict[str, str]:
        """Build config-entry data for a device with a known protocol key."""
        base = xor_base_for_address(address)
        if base is None:
            raise MideaProtocolError(f"No captured XOR base for {address}")
        return {
            CONF_ADDRESS: address,
            CONF_BRIDGE_ACTION: bridge_action,
            CONF_XOR_BASE: format_xor_base(base),
        }

    async def _async_create_or_request_key(
        self, address: str, bridge_action: str
    ) -> ConfigFlowResult:
        """Create known devices immediately or ask for an unknown device key."""
        if xor_base_for_address(address) is not None:
            return self.async_create_entry(
                title=_device_title(address),
                data=self._entry_data(address, bridge_action),
            )
        self._pending_address = address
        self._pending_bridge = bridge_action
        return await self.async_step_protocol()

    def _refresh_bridges(self) -> bool:
        """Refresh compatible ESPHome broadcast bridge actions."""
        self._bridge_actions = async_available_bridge_actions(self.hass)
        return bool(self._bridge_actions)

    def _bridge_schema(self) -> dict[vol.Marker, Any]:
        """Return a bridge selector only when multiple bridges are present."""
        if len(self._bridge_actions) <= 1:
            return {}
        return {vol.Required(CONF_BRIDGE_ACTION): vol.In(self._bridge_actions)}

    def _selected_bridge(self, user_input: dict[str, Any]) -> str:
        """Return the selected bridge, or the only available bridge."""
        if bridge_action := user_input.get(CONF_BRIDGE_ACTION):
            return bridge_action
        return next(iter(self._bridge_actions))

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle automatic Bluetooth discovery."""
        if state_from_service_info(discovery_info) is None:
            return self.async_abort(reason="not_supported")
        if not self._refresh_bridges():
            return self.async_abort(reason="bridge_not_found")

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
            return await self._async_create_or_request_key(
                address, self._selected_bridge(user_input)
            )

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema(self._bridge_schema()),
            description_placeholders={
                "name": _device_title(address),
                "address": address,
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user select a discovered device and broadcast bridge."""
        if not self._refresh_bridges():
            return self.async_abort(reason="bridge_not_found")

        if user_input is not None:
            address = normalize_address(user_input[CONF_ADDRESS])
            discovery_info = self._discovered_devices[address]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return await self._async_create_or_request_key(
                normalize_address(discovery_info.address),
                self._selected_bridge(user_input),
            )

        current_ids = self._async_current_ids(include_ignore=False)
        self._discovered_devices.clear()
        for discovery_info in bluetooth.async_discovered_service_info(
            self.hass, connectable=False
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

        device_choices = {
            address: f"{_device_title(address)} ({address})"
            for address in self._discovered_devices
        }
        schema: dict[vol.Marker, Any] = {
            vol.Required(CONF_ADDRESS): vol.In(device_choices)
        }
        schema.update(self._bridge_schema())
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(schema),
        )

    async def async_step_protocol(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the per-device XOR base for a device not yet captured."""
        if self._pending_address is None or self._pending_bridge is None:
            return self.async_abort(reason="no_devices_found")

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                xor_base = format_xor_base(user_input[CONF_XOR_BASE])
            except MideaProtocolError:
                errors[CONF_XOR_BASE] = "invalid_xor_base"
            else:
                return self.async_create_entry(
                    title=_device_title(self._pending_address),
                    data={
                        CONF_ADDRESS: self._pending_address,
                        CONF_BRIDGE_ACTION: self._pending_bridge,
                        CONF_XOR_BASE: xor_base,
                    },
                )

        return self.async_show_form(
            step_id="protocol",
            data_schema=vol.Schema({vol.Required(CONF_XOR_BASE): str}),
            errors=errors,
            description_placeholders={"address": self._pending_address},
        )


class MideaFanLightOptionsFlow(OptionsFlowWithReload):
    """Configure the temperature-driven automatic fan mode."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure a temperature source and ascending speed thresholds."""
        errors: dict[str, str] = {}
        threshold_keys = (
            CONF_AUTO_TEMP_2,
            CONF_AUTO_TEMP_3,
            CONF_AUTO_TEMP_4,
            CONF_AUTO_TEMP_5,
            CONF_AUTO_TEMP_6,
        )
        if user_input is not None:
            thresholds = tuple(float(user_input[key]) for key in threshold_keys)
            try:
                user_input[CONF_XOR_BASE] = format_xor_base(
                    user_input[CONF_XOR_BASE]
                )
            except MideaProtocolError:
                errors[CONF_XOR_BASE] = "invalid_xor_base"
            if any(left >= right for left, right in zip(thresholds, thresholds[1:])):
                errors["base"] = "thresholds_not_ascending"
            elif not errors:
                return self.async_create_entry(data=user_input)

        options = self.config_entry.options
        form_values = user_input or {
            **self.config_entry.data,
            **options,
        }
        temperature_default = form_values.get(CONF_TEMPERATURE_ENTITY)
        temperature_marker: vol.Marker
        if temperature_default:
            temperature_marker = vol.Required(
                CONF_TEMPERATURE_ENTITY, default=temperature_default
            )
        else:
            temperature_marker = vol.Required(CONF_TEMPERATURE_ENTITY)

        number_selector = NumberSelector(
            NumberSelectorConfig(
                min=-10,
                max=50,
                step=0.5,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTemperature.CELSIUS,
            )
        )
        schema: dict[vol.Marker, Any] = {
            vol.Required(
                CONF_XOR_BASE,
                default=form_values[CONF_XOR_BASE],
            ): str,
            temperature_marker: EntitySelector(
                EntitySelectorConfig(
                    domain=Platform.SENSOR,
                    device_class=SensorDeviceClass.TEMPERATURE,
                )
            )
        }
        for key, default in zip(threshold_keys, DEFAULT_AUTO_THRESHOLDS):
            schema[vol.Required(key, default=form_values.get(key, default))] = (
                number_selector
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema),
            errors=errors,
        )
