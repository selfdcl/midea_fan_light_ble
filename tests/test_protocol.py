"""Tests for the Midea BLE fan light protocol codec."""

from __future__ import annotations

import sys
from pathlib import Path
import unittest

COMPONENT_DIR = Path(__file__).parents[1] / "custom_components" / "midea_fan_light_ble"
sys.path.insert(0, str(COMPONENT_DIR))

from protocol import (  # noqa: E402
    COMMAND_FAN,
    COMMAND_LIGHT,
    COMMAND_NIGHT_LIGHT,
    MideaProtocolError,
    build_broadcast_frame,
    build_broadcast_release_frame,
    build_control_frame,
    embedded_address,
    format_xor_base,
    format_timer_minutes,
    normalize_xor_base,
    parse_advertisement,
    parse_bbb1,
    percentage_to_speed,
    speed_to_percentage,
    temperature_to_speed,
    timer_minutes_to_hour_slot,
    xor_base_for_address,
)


def from_hex(value: str) -> bytes:
    """Convert a spaced hexadecimal fixture to bytes."""
    return bytes.fromhex(value)


class ProtocolTests(unittest.TestCase):
    """Validate packets captured from the real fan light and original app."""

    def test_parse_all_off_advertisement(self) -> None:
        payload = from_hex(
            "81 63 01 D1 73 60 00 22 80 08 00 00 01 00 66 3C 00 00 00 01"
        )
        state = parse_advertisement(payload, address="80:22:00:60:73:D1", rssi=-66)

        self.assertEqual(embedded_address(payload), "80:22:00:60:73:D1")
        self.assertFalse(state.light_on)
        self.assertFalse(state.fan_on)
        self.assertFalse(state.night_light_on)
        self.assertEqual(state.brightness_percent, 40)
        self.assertEqual(state.color_temperature_kelvin, 3594)
        self.assertEqual(state.rssi, -66)

    def test_reject_mismatched_embedded_address(self) -> None:
        payload = from_hex(
            "81 63 01 D1 73 60 00 22 80 08 00 00 01 00 66 3C 00 00 00 01"
        )
        with self.assertRaises(MideaProtocolError):
            parse_advertisement(payload, address="AA:BB:CC:DD:EE:FF")

    def test_parse_bbb1_fan_on(self) -> None:
        state = parse_bbb1(from_hex("0C CB 2A 80 A0 47 44 57 ED F3 51 D3 72"))

        self.assertEqual(state.sequence, 0x0C)
        self.assertFalse(state.light_on)
        self.assertTrue(state.fan_on)
        self.assertEqual(state.speed, 1)

    def test_parse_bbb1_night_light_on(self) -> None:
        state = parse_bbb1(from_hex("0C EB AA 46 41 30 D1 F0 51 D3 73 95 F2"))

        self.assertTrue(state.light_on)
        self.assertTrue(state.night_light_on)
        self.assertFalse(state.fan_on)
        self.assertEqual(state.brightness_percent, 1)

    def test_build_light_frame(self) -> None:
        self.assertEqual(
            build_control_frame(COMMAND_LIGHT, 0),
            from_hex("10 0B 45 30 D1 F5 51 D3 73 95 F3 60 82 E0 22 80 A2 4E"),
        )

    def test_build_fan_frame(self) -> None:
        self.assertEqual(
            build_control_frame(COMMAND_FAN, 0),
            from_hex("10 0B 45 30 D1 FA 51 D3 73 95 F3 60 82 E0 22 80 A2 4D"),
        )

    def test_build_night_light_frame(self) -> None:
        self.assertEqual(
            build_control_frame(COMMAND_NIGHT_LIGHT, 0x0E),
            from_hex("10 EB A3 47 44 6E D1 F3 51 D3 73 95 F3 60 82 E0 22 E1"),
        )

    def test_build_broadcast_light_toggle(self) -> None:
        self.assertEqual(
            build_broadcast_frame("80:22:00:60:73:D1", 0x06, 4),
            from_hex(
                "11 4D 19 14 D1 73 60 00 22 80 01 50 D3 75 95 F3 60 82 "
                "E0 22 80 A2 46 44 31 D9"
            ),
        )

    def test_build_broadcast_fan_toggle(self) -> None:
        self.assertEqual(
            build_broadcast_frame("80:22:00:60:73:D1", 0x09, 0),
            from_hex(
                "11 4D 19 10 D1 73 60 00 22 80 01 45 31 D8 F3 51 D3 73 "
                "95 F3 60 82 E0 22 80 A9"
            ),
        )

    def test_build_broadcast_reverse_toggle(self) -> None:
        """The generic bridge reproduces the original app's reverse frame."""
        self.assertEqual(
            build_broadcast_frame("80:22:00:60:73:D1", 0x1C, 8),
            from_hex(
                "11 4D 19 18 D1 73 60 00 22 80 01 F2 60 9E E0 22 80 A2 "
                "46 44 31 D1 F3 51 D3 6D"
            ),
        )

    def test_build_broadcast_brightness(self) -> None:
        self.assertEqual(
            build_broadcast_frame(
                "80:22:00:60:73:D1",
                0x51,
                2,
                value=0xE8,
                light_command=True,
            ),
            from_hex(
                "11 4D 19 12 D1 73 60 00 22 80 01 D0 F2 00 3B 73 95 F3 "
                "60 82 E0 22 80 A2 46 78"
            ),
        )

    def test_build_broadcast_release(self) -> None:
        self.assertEqual(
            build_broadcast_release_frame("80:22:00:60:73:D1", 8),
            from_hex(
                "11 4D 19 18 D1 73 60 00 22 80 01 F2 60 82 E0 22 80 A2 "
                "46 44 31 D1 F3 51 D3 71"
            ),
        )

    def test_known_device_xor_bases(self) -> None:
        """Captured devices resolve to their own protocol key."""
        self.assertEqual(
            format_xor_base(xor_base_for_address("80:22:00:A0:2F:DA")),
            "DAFC5ACF2F51AFA0C2202280A24B097A",
        )
        self.assertEqual(
            format_xor_base(xor_base_for_address("80-22-00-91-78-26")),
            "2648A609789AF891B3112280A2D19EB7",
        )
        self.assertIsNone(xor_base_for_address("AA:BB:CC:DD:EE:FF"))

    def test_normalize_xor_base(self) -> None:
        """Configuration accepts readable separators and stores 16 bytes."""
        expected = bytes.fromhex("DA FC 5A CF 2F 51 AF A0 C2 20 22 80 A2 4B 09 7A")
        self.assertEqual(
            normalize_xor_base("DA:FC:5A:CF:2F:51:AF:A0:C2:20:22:80:A2:4B:09:7A"),
            expected,
        )
        with self.assertRaises(MideaProtocolError):
            normalize_xor_base("DAFC")
        with self.assertRaises(MideaProtocolError):
            normalize_xor_base("Z" * 32)

    def test_build_a02fda_captured_light_toggle(self) -> None:
        """The DA key reproduces the real app's captured command frame."""
        xor_base = xor_base_for_address("80:22:00:A0:2F:DA")
        self.assertEqual(
            build_broadcast_frame(
                "80:22:00:A0:2F:DA",
                0x06,
                0x0D,
                xor_base=xor_base,
            ),
            from_hex(
                "11 4D 19 1D DA 2F A0 00 22 80 01 81 A2 4D 09 7A DA "
                "FC 5A CF 2F 51 AF A0 C2 28"
            ),
        )

    def test_build_a02fda_captured_release(self) -> None:
        """The DA key reproduces the real app's captured release frame."""
        xor_base = xor_base_for_address("80:22:00:A0:2F:DA")
        self.assertEqual(
            build_broadcast_release_frame(
                "80:22:00:A0:2F:DA",
                0x01,
                xor_base=xor_base,
            ),
            from_hex(
                "11 4D 19 11 DA 2F A0 00 22 80 01 7B DA FC 5A CF 2F "
                "51 AF A0 C2 20 22 80 A2 49"
            ),
        )

    def test_build_other_captured_device_frames(self) -> None:
        """All captured per-device keys reproduce original-app frames."""
        fixtures = (
            (
                "80:22:00:40:83:19",
                0xFE,
                0x00,
                "11 4D 19 10 19 83 40 00 22 80 01 9D 59 E7 3B 99 C3 "
                "83 A5 03 40 62 C0 22 80 A2",
            ),
            (
                "80:22:00:91:78:26",
                0x09,
                0x0A,
                "11 4D 19 1A 26 78 91 00 22 80 01 B2 11 2B 80 A2 D1 "
                "9E B7 26 48 A6 09 78 9A F3",
            ),
        )
        for address, command, sequence, expected in fixtures:
            with self.subTest(address=address):
                self.assertEqual(
                    build_broadcast_frame(
                        address,
                        command,
                        sequence,
                        xor_base=xor_base_for_address(address),
                    ),
                    from_hex(expected),
                )

    def test_six_speed_percentage_round_trip(self) -> None:
        """Every advertised percentage must map back to its original level."""
        for speed in range(1, 7):
            self.assertEqual(
                percentage_to_speed(speed_to_percentage(speed)),
                speed,
            )

    def test_format_timer_minutes(self) -> None:
        """Countdown values are exposed as a stable HH:MM string."""
        self.assertEqual(format_timer_minutes(-1), "00:00")
        self.assertEqual(format_timer_minutes(0), "00:00")
        self.assertEqual(format_timer_minutes(65), "01:05")
        self.assertEqual(format_timer_minutes(360), "06:00")

    def test_timer_minutes_to_hour_slot(self) -> None:
        """The preset slider never exposes a fractional floating-point value."""
        fixtures = {
            -1: 0,
            0: 0,
            1: 1,
            59: 1,
            60: 1,
            61: 2,
            179: 3,
            180: 3,
            360: 6,
            361: 6,
        }
        for minutes, expected in fixtures.items():
            with self.subTest(minutes=minutes):
                self.assertEqual(timer_minutes_to_hour_slot(minutes), expected)

    def test_temperature_to_speed(self) -> None:
        """Automatic mode maps configured Celsius thresholds to six speeds."""
        thresholds = (22.0, 24.0, 26.0, 28.0, 30.0)
        fixtures = {
            10.0: 1,
            21.9: 1,
            22.0: 2,
            25.0: 3,
            26.0: 4,
            29.9: 5,
            30.0: 6,
            40.0: 6,
        }
        for temperature, expected in fixtures.items():
            with self.subTest(temperature=temperature):
                self.assertEqual(
                    temperature_to_speed(temperature, thresholds), expected
                )

    def test_temperature_thresholds_must_be_ascending(self) -> None:
        """Reject ambiguous automatic-mode threshold configurations."""
        with self.assertRaises(MideaProtocolError):
            temperature_to_speed(25.0, (22.0, 24.0, 24.0, 28.0, 30.0))


if __name__ == "__main__":
    unittest.main()
