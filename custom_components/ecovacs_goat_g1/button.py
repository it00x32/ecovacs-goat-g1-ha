"""Button entities for Ecovacs Goat G1."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import GoatG1Error
from .const import DOMAIN
from .coordinator import GoatG1Coordinator
from .entity import GoatG1Entity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GoatG1Coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        GoatG1SoundButton(coordinator),
        GoatG1BorderMowButton(coordinator),
        GoatG1ZoneStartButton(coordinator),
        GoatG1ZoneSyncButton(coordinator),
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
        try:
            await self.coordinator.api.start_border_mowing()
            await self.coordinator.async_request_refresh()
        except GoatG1Error as err:
            _LOGGER.error("Rand mähen fehlgeschlagen: %s", err)
            raise HomeAssistantError(str(err)) from err


class GoatG1ZoneStartButton(GoatG1Entity, ButtonEntity):
    _attr_name = "Zone starten"
    _attr_icon = "mdi:map-marker-check"

    def __init__(self, coordinator: GoatG1Coordinator) -> None:
        super().__init__(coordinator, "button_zone_start")

    @property
    def available(self) -> bool:
        return super().available and bool(self.coordinator.selected_zone_id)

    async def async_press(self) -> None:
        zone_id = self.coordinator.selected_zone_id
        if zone_id:
            await self.coordinator.api.start_zone(zone_id)
            await self.coordinator.async_request_refresh()


class GoatG1ZoneSyncButton(GoatG1Entity, ButtonEntity):
    _attr_name = "Zonen aktualisieren"
    _attr_icon = "mdi:sync"

    def __init__(self, coordinator: GoatG1Coordinator) -> None:
        super().__init__(coordinator, "button_zone_sync")

    async def async_press(self) -> None:
        zones = await self.coordinator.api.fetch_zones()
        self.coordinator.zones = zones
        if zones and self.coordinator.selected_zone_id not in {z["id"] for z in zones}:
            self.coordinator.selected_zone_id = zones[0]["id"]
        await self.coordinator.async_request_refresh()
