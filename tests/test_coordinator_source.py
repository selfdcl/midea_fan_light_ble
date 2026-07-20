"""Source-level regression tests for the Home Assistant coordinator."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest

COORDINATOR_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "midea_fan_light_ble"
    / "coordinator.py"
)


class CoordinatorSourceTests(unittest.TestCase):
    """Guard against assignments to properties owned by the HA base class."""

    def test_does_not_assign_read_only_name_property(self) -> None:
        """The Bluetooth coordinator base class exposes name as read-only."""
        tree = ast.parse(COORDINATOR_PATH.read_text(encoding="utf-8"))
        assigned_attributes = {
            target.attr
            for node in ast.walk(tree)
            if isinstance(node, (ast.Assign, ast.AnnAssign))
            for target in (
                node.targets if isinstance(node, ast.Assign) else [node.target]
            )
            if isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "self"
        }

        self.assertNotIn("name", assigned_attributes)

    def test_bluetooth_event_publishes_fresh_state(self) -> None:
        """Every matching advertisement must replace the cached device state."""
        tree = ast.parse(COORDINATOR_PATH.read_text(encoding="utf-8"))
        coordinator_class = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == "MideaFanLightCoordinator"
        )
        handler = next(
            node
            for node in coordinator_class.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_async_handle_bluetooth_event"
        )
        called_methods = {
            node.func.attr
            for node in ast.walk(handler)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "self"
        }

        self.assertIn("_publish_state", called_methods)


if __name__ == "__main__":
    unittest.main()
