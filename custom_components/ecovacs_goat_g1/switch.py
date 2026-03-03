"""Switch entities for Ecovacs Goat G1 settings."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, TOGGLE_SETTINGS, TOGGLE_LABELS
from .coordinator import GoatG1Coordinator
from .entity import GoatG1Entity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GoatG1Coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        GoatG1Switch(coordinator, key, get_cmd, set_cmd, field)
        for key, get_cmd, set_cmd, field in TOGGLE_SETTINGS
    )


class GoatG1Switch(GoatG1Entity, SwitchEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: GoatG1Coordinator,
        key: str,
        get_cmd: str,
        set_cmd: str,
        field: str,
    ) -> None:
        super().__init__(coordinator, f"switch_{key}")
        self._key     = key
        self._set_cmd = set_cmd
        self._field   = field
        self._attr_name = TOGGLE_LABELS.get(key, key)

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.settings.get(self._key)

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.api.set_toggle(self._set_cmd, self._field, True)
        self.coordinator.settings[self._key] = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.api.set_toggle(self._set_cmd, self._field, False)
        self.coordinator.settings[self._key] = False
        self.async_write_ha_state()
