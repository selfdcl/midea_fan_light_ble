"""Pure Python codec for Midea BLE fan lights."""

from __future__ import annotations

from dataclasses import dataclass

MANUFACTURER_ID = 0x06A8
ADVERTISEMENT_HEADER = bytes((0x81, 0x63, 0x01))

MODE_LIGHT = 0x01
MODE_FAN = 0x02
MODE_NIGHT_LIGHT = 0x04
MODE_REVERSE = 0x20

COMMAND_LIGHT = 0x06
COMMAND_FAN = 0x09
COMMAND_NIGHT_LIGHT = 0x5F

_CONTROL_COMPANY_ID = bytes((0x11, 0x4D))

_XOR_BASE = bytes(
    (
        0xD1,
        0xF3,
        0x51,
        0xD3,
        0x73,
        0x95,
        0xF3,
        0x60,
        0x82,
        0xE0,
        0x22,
        0x80,
        0xA2,
        0x46,
        0x44,
        0x31,
    )
)


class MideaProtocolError(ValueError):
    """Raised when a packet does not match the supported protocol."""


@dataclass(frozen=True, slots=True)
class MideaFanLightState:
    """Decoded state shared by advertisements and BBB1 notifications."""

    mode: int
    brightness_raw: int
    color_raw: int
    timer_minutes: int
    speed_raw: int
    tail: int
    sequence: int | None = None
    rssi: int | None = None

    @property
    def light_on(self) -> bool:
        """Return whether the light power bit is set."""
        return bool(self.mode & MODE_LIGHT)

    @property
    def fan_on(self) -> bool:
        """Return whether the fan bit is set."""
        return bool(self.mode & MODE_FAN)

    @property
    def night_light_on(self) -> bool:
        """Return whether night-light mode is set."""
        return bool(self.mode & MODE_NIGHT_LIGHT)

    @property
    def reverse(self) -> bool:
        """Return whether reverse direction is active."""
        return self.fan_on and bool(self.mode & MODE_REVERSE)

    @property
    def speed(self) -> int:
        """Return the one-based fan speed, or zero while stopped."""
        return self.speed_raw + 1 if self.fan_on and self.speed_raw <= 5 else 0

    @property
    def brightness_percent(self) -> int:
        """Return brightness converted to a percentage."""
        return round(self.brightness_raw * 100 / 255)

    @property
    def color_temperature_kelvin(self) -> int:
        """Return the color-temperature field converted to kelvin."""
        return round(2700 + self.color_raw * (6500 - 2700) / 255)

    def mode_bit_is_on(self, mode_bit: int) -> bool:
        """Return the current state of a controllable mode bit."""
        return bool(self.mode & mode_bit)


def normalize_address(address: str) -> str:
    """Return an uppercase colon-separated Bluetooth address."""
    compact = address.replace(":", "").replace("-", "").upper()
    if len(compact) != 12 or any(char not in "0123456789ABCDEF" for char in compact):
        raise MideaProtocolError(f"Invalid Bluetooth address: {address}")
    return ":".join(compact[index : index + 2] for index in range(0, 12, 2))


def speed_to_percentage(speed: int) -> int:
    """Convert one of six fan levels to Home Assistant percentage."""
    if not 1 <= speed <= 6:
        raise MideaProtocolError(f"Speed must be 1..6, got {speed}")
    return round(speed * 100 / 6)


def percentage_to_speed(percentage: int) -> int:
    """Convert Home Assistant percentage back to the nearest fan level."""
    if not 1 <= percentage <= 100:
        raise MideaProtocolError(f"Percentage must be 1..100, got {percentage}")
    return max(1, min(6, round(percentage * 6 / 100)))


def format_timer_minutes(timer_minutes: int) -> str:
    """Format a non-negative countdown value as zero-padded HH:MM."""
    minutes = max(0, timer_minutes)
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def embedded_address(data: bytes) -> str:
    """Extract the normal-order address from an 0x06A8 status payload."""
    if len(data) != 20 or data[:3] != ADVERTISEMENT_HEADER:
        raise MideaProtocolError("Not a supported 0x06A8 status payload")
    return ":".join(f"{value:02X}" for value in reversed(data[3:9]))


def parse_advertisement(
    data: bytes, *, address: str | None = None, rssi: int | None = None
) -> MideaFanLightState:
    """Decode the 20-byte manufacturer payload broadcast by the device."""
    if len(data) != 20:
        raise MideaProtocolError(f"Expected 20 advertisement bytes, got {len(data)}")
    if data[:3] != ADVERTISEMENT_HEADER:
        raise MideaProtocolError("Unexpected advertisement header")
    if address is not None and embedded_address(data) != normalize_address(address):
        raise MideaProtocolError("Embedded address does not match advertiser address")

    return MideaFanLightState(
        mode=data[11],
        brightness_raw=data[14],
        color_raw=data[15],
        timer_minutes=(data[16] << 8) | data[17],
        speed_raw=data[18],
        tail=data[19],
        rssi=rssi,
    )


def parse_bbb1(data: bytes, *, rssi: int | None = None) -> MideaFanLightState:
    """Decode a 13-byte BBB1 GATT notification."""
    if len(data) != 13:
        raise MideaProtocolError(f"Expected 13 BBB1 bytes, got {len(data)}")
    if data[0] != 0x0C or data[1] & 0x0F != 0x0B:
        raise MideaProtocolError("Unexpected BBB1 frame header")

    sequence = (data[1] >> 4) & 0x0F
    decoded = bytes(
        data[2 + index] ^ _XOR_BASE[(sequence + 14 + index) & 0x0F]
        for index in range(11)
    )
    if decoded[:2] != bytes((0x08, 0x00)):
        raise MideaProtocolError("Unexpected BBB1 plaintext header")

    return MideaFanLightState(
        mode=decoded[2],
        brightness_raw=decoded[5],
        color_raw=decoded[6],
        timer_minutes=(decoded[7] << 8) | decoded[8],
        speed_raw=decoded[9],
        tail=decoded[10],
        sequence=sequence,
        rssi=rssi,
    )


def build_control_frame(command: int, sequence: int) -> bytes:
    """Build an original-compatible 18-byte BBB0 write frame."""
    if not 0 <= sequence <= 0x0F:
        raise MideaProtocolError(f"Sequence must be 0..15, got {sequence}")
    if not 0 <= command <= 0xFF:
        raise MideaProtocolError(f"Command must be a byte, got {command}")

    plaintext = bytearray(16)
    plaintext[0] = 0x01
    plaintext[1] = 0x01
    plaintext[3] = command
    plaintext[15] = sum(plaintext[:15]) & 0xFF

    encrypted = bytes(
        plaintext[index] ^ _XOR_BASE[(sequence + 14 + index) & 0x0F]
        for index in range(16)
    )
    return bytes((0x10, (sequence << 4) | 0x0B)) + encrypted


def build_broadcast_frame(
    address: str,
    command: int,
    sequence: int,
    *,
    value: int = 0,
    light_command: bool = False,
) -> bytes:
    """Build a connectionless 0x4D11 command advertisement."""
    if not 0 <= sequence <= 0x0F:
        raise MideaProtocolError(f"Sequence must be 0..15, got {sequence}")
    if not 0 <= command <= 0xFF or not 0 <= value <= 0xFF:
        raise MideaProtocolError("Command and value must be bytes")

    address_bytes = bytes.fromhex(normalize_address(address).replace(":", ""))
    frame = bytearray(
        _CONTROL_COMPANY_ID
        + bytes((0x19, 0x10 | sequence))
        + bytes(reversed(address_bytes))
        + bytes((0x01,))
        + bytes(_XOR_BASE[(sequence + 14 + index) & 0x0F] for index in range(15))
    )
    tail_offset = 11
    frame[tail_offset] ^= 0x01
    if light_command:
        frame[tail_offset + 1] ^= 0x01
    frame[tail_offset + 2] ^= command
    if light_command:
        frame[tail_offset + 3] ^= value
        frame[tail_offset + 14] ^= (command + value + 3) & 0xFF
    else:
        frame[tail_offset + 14] ^= (command + 2) & 0xFF
    return bytes(frame)


def build_broadcast_release_frame(address: str, sequence: int) -> bytes:
    """Build the release packet sent after a 0x4D11 command."""
    return build_broadcast_frame(address, 0, sequence)
