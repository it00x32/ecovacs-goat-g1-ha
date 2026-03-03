"""Number entities for Ecovacs Goat G1 (volume, mowing direction)."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
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
    async_add_entities([
        GoatG1Volume(coordinator),
        GoatG1Direction(coordinator),
    ])


class GoatG1Volume(GoatG1Entity, NumberEntity):
    _attr_name            = "Lautstärke"
    _attr_native_min_value = 0
    _attr_native_max_value = 10
    _attr_native_step      = 1
    _attr_mode             = NumberMode.SLIDER
    _attr_entity_category  = EntityCategory.CONFIG
    _attr_icon             = "mdi:volume-high"

    def __init__(self, coordinator: GoatG1Coordinator) -> None:
        super().__init__(coordinator, "volume")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.settings.get("volume")

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.api.set_volume(int(value))
        self.coordinator.settings["volume"] = int(value)
        self.async_write_ha_state()


class GoatG1Direction(GoatG1Entity, NumberEntity):
    _attr_name             = "Mährichtung"
    _attr_native_min_value = 0
    _attr_native_max_value = 180
    _attr_native_step      = 1
    _attr_native_unit_of_measurement = "°"
    _attr_mode             = NumberMode.SLIDER
    _attr_entity_category  = EntityCategory.CONFIG
    _attr_icon             = "mdi:compass"

    def __init__(self, coordinator: GoatG1Coordinator) -> None:
        super().__init__(coordinator, "direction")

    @property
    def native_value(self) -> float:
        return self.coordinator.direction

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.api.set_mowing_direction(int(value))
        self.coordinator.direction = int(value)
        self.async_write_ha_state()
