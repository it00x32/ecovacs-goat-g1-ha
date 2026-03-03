"""Base entity for Ecovacs Goat G1."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GoatG1Coordinator


class GoatG1Entity(CoordinatorEntity[GoatG1Coordinator]):
    """Base class for all Goat G1 entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: GoatG1Coordinator, unique_suffix: str) -> None:
        super().__init__(coordinator)
        dev = coordinator.api.device or {}
        did = dev.get("did", "unknown")
        self._attr_unique_id  = f"goat_g1_{did}_{unique_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, did)},
            name=dev.get("name") or dev.get("nick") or "Goat G1",
            manufacturer="Ecovacs",
            model="Goat G1",
            sw_version=coordinator.fw_version,
        )
