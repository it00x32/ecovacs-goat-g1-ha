"""Button entities for Ecovacs Goat G1."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
    async_add_entities([
        GoatG1SoundButton(coordinator),
        GoatG1BorderMowButton(coordinator),
    ])


class GoatG1SoundButton(GoatG1Entity, ButtonEntity):
    _attr_name = "Signalton"
    _attr_icon = "mdi:volume-high"

    def __init__(self, coordinator: GoatG1Coordinator) -> None:
        super().__init__(coordinator, "button_sound")

    async def async_press(self) -> None:
        await self.coordinator.api.play_sound()


class GoatG1BorderMowButton(GoatG1Entity, ButtonEntity):
    _attr_name = "Rand mähen"
    _attr_icon = "mdi:map-marker-path"

    def __init__(self, coordinator: GoatG1Coordinator) -> None:
        super().__init__(coordinator, "button_border_mow")

    async def async_press(self) -> None:
        await self.coordinator.api.start_border_mowing()
        await self.coordinator.async_request_refresh()
