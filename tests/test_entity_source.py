"""Source-level regression tests for Home Assistant entity contracts."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest

FAN_PATH = (
    Path(__file__).parents[1] / "custom_components" / "midea_fan_light_ble" / "fan.py"
)


class EntitySourceTests(unittest.TestCase):
    """Guard entity method signatures used by Home Assistant services."""

    def test_fan_turn_on_accepts_home_assistant_arguments(self) -> None:
        """FanEntity passes percentage and preset mode as positional arguments."""
        tree = ast.parse(FAN_PATH.read_text(encoding="utf-8"))
        fan_class = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "MideaFan"
        )
        turn_on = next(
            node
            for node in fan_class.body
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "async_turn_on"
        )

        self.assertEqual(
            [argument.arg for argument in turn_on.args.args],
            ["self", "percentage", "preset_mode"],
        )
        self.assertEqual(turn_on.args.kwarg.arg, "kwargs")

    def test_fan_exposes_modes_without_fake_oscillation(self) -> None:
        """Expose wind modes without misrepresenting reverse as oscillation."""
        tree = ast.parse(FAN_PATH.read_text(encoding="utf-8"))
        fan_class = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "MideaFan"
        )
        methods = {
            node.name
            for node in fan_class.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

        self.assertIn("preset_mode", methods)
        self.assertIn("async_set_preset_mode", methods)
        self.assertNotIn("oscillating", methods)
        self.assertNotIn("async_oscillate", methods)


if __name__ == "__main__":
    unittest.main()
