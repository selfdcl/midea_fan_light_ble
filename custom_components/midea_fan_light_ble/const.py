"""Constants for the Midea BLE fan light integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "midea_fan_light_ble"
CONF_BRIDGE_ACTION = "bridge_action"
CONF_XOR_BASE = "xor_base"
CONF_TEMPERATURE_ENTITY = "temperature_entity"
CONF_AUTO_TEMP_2 = "auto_temp_2"
CONF_AUTO_TEMP_3 = "auto_temp_3"
CONF_AUTO_TEMP_4 = "auto_temp_4"
CONF_AUTO_TEMP_5 = "auto_temp_5"
CONF_AUTO_TEMP_6 = "auto_temp_6"
BRIDGE_ACTION_SUFFIX = "_midea_ble_broadcast"

DEFAULT_AUTO_THRESHOLDS = (22.0, 24.0, 26.0, 28.0, 30.0)

MANUFACTURER_ID = 0x06A8
ADVERTISEMENT_HEADER = bytes((0x81, 0x63, 0x01))

SERVICE_UUID = "0000aaaa-0000-1000-8000-00805f9b34fb"
STATE_CHARACTERISTIC_UUID = "0000bbb1-0000-1000-8000-00805f9b34fb"
CONTROL_CHARACTERISTIC_UUID = "0000bbb0-0000-1000-8000-00805f9b34fb"

MODE_LIGHT = 0x01
MODE_FAN = 0x02
MODE_NIGHT_LIGHT = 0x04
MODE_REVERSE = 0x20

COMMAND_LIGHT = 0x06
COMMAND_FAN = 0x09
COMMAND_NIGHT_LIGHT = 0x5F
COMMAND_REVERSE = 0x1C
COMMAND_BRIGHTNESS = 0x51
COMMAND_COLOR_TEMPERATURE = 0x55

COMMAND_SPEED_BY_LEVEL = {
    1: 0x19,
    2: 0x1A,
    3: 0x81,
    4: 0x88,
    5: 0x85,
    6: 0x86,
}

COMMAND_TIMER_BY_HOURS = {
    0: 0x50,
    1: 0x52,
    2: 0x53,
    3: 0x54,
    4: 0x56,
    5: 0x57,
    6: 0x58,
}

FAN_PRESET_STANDARD = "标准风"
FAN_PRESET_NATURAL = "自然风"
FAN_PRESET_AUTO = "自动"

COMMAND_BY_MODE_BIT = {
    MODE_LIGHT: COMMAND_LIGHT,
    MODE_FAN: COMMAND_FAN,
    MODE_NIGHT_LIGHT: COMMAND_NIGHT_LIGHT,
}

PLATFORMS: list[Platform] = [
    Platform.LIGHT,
    Platform.FAN,
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.SENSOR,
]

CONTROL_TIMEOUT = 15.0
