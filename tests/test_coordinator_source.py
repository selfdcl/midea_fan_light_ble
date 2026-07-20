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


if __name__ == "__main__":
    unittest.main()
