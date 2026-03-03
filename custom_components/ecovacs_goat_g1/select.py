"""Zone select entity for Ecovacs Goat G1."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import GoatG1Coordinator
from .entity import GoatG1Entity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GoatG1Coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([GoatG1ZoneSelect(coordinator)])


class GoatG1ZoneSelect(GoatG1Entity, SelectEntity):
    """Dropdown to pick the active mowing zone."""

    _attr_name = "Zone"
    _attr_icon = "mdi:map-marker"

    def __init__(self, coordinator: GoatG1Coordinator) -> None:
        super().__init__(coordinator, "zone_select")

    @property
    def options(self) -> list[str]:
        return [z["name"] for z in (self.coordinator.zones or [])]

    @property
    def current_option(self) -> str | None:
        zones = self.coordinator.zones or []
        if not zones:
            return None
        for z in zones:
            if z["id"] == self.coordinator.selected_zone_id:
                return z["name"]
        # Fallback: first zone
        return zones[0]["name"]

    async def async_select_option(self, option: str) -> None:
        for z in (self.coordinator.zones or []):
            if z["name"] == option:
                self.coordinator.selected_zone_id = z["id"]
                break
        self.async_write_ha_state()
