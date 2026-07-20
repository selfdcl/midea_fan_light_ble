"""Base entity for Midea BLE fan lights."""

from __future__ import annotations

from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothCoordinatorEntity,
)
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .coordinator import MideaFanLightCoordinator


class MideaFanLightEntity(PassiveBluetoothCoordinatorEntity[MideaFanLightCoordinator]):
    """Common entity backed by one Bluetooth coordinator."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MideaFanLightCoordinator,
        entry_title: str,
        entity_key: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_{entity_key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
            manufacturer="Midea",
            model="BLE Fan Light",
            name=entry_title,
        )

    @property
    def available(self) -> bool:
        """Return whether a valid device state is available."""
        return super().available and self.coordinator.data is not None
