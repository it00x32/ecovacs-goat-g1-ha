"""Lawn mower entity for Ecovacs Goat G1."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.lawn_mower import (
    LawnMowerActivity,
    LawnMowerEntity,
    LawnMowerEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import GoatG1Coordinator
from .entity import GoatG1Entity

_LOGGER = logging.getLogger(__name__)

_STATE_MAP = {
    "mowing":    LawnMowerActivity.MOWING,
    "paused":    LawnMowerActivity.PAUSED,
    "docked":    LawnMowerActivity.DOCKED,
    "returning": LawnMowerActivity.DOCKED,
    "idle":      LawnMowerActivity.DOCKED,
    "error":     LawnMowerActivity.ERROR,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GoatG1Coordinator = hass.data[DOMAIN][entry.entry_id]
    mower = GoatG1LawnMower(coordinator)
    async_add_entities([mower])

    # Register custom services
    async def handle_start_border(call: ServiceCall) -> None:
        await coordinator.api.start_border_mowing()

    async def handle_start_zone(call: ServiceCall) -> None:
        zone_id = call.data.get("zone_id", "")
        if zone_id:
            await coordinator.api.start_zone(str(zone_id))

    async def handle_set_direction(call: ServiceCall) -> None:
        angle = int(call.data.get("angle", 0))
        await coordinator.api.set_mowing_direction(angle)
        coordinator.direction = angle

    hass.services.async_register(DOMAIN, "start_border_mowing", handle_start_border)
    hass.services.async_register(DOMAIN, "start_zone",          handle_start_zone)
    hass.services.async_register(DOMAIN, "set_mowing_direction", handle_set_direction)


class GoatG1LawnMower(GoatG1Entity, LawnMowerEntity):
    """Represents the Goat G1 as a HA lawn mower."""

    _attr_name = None  # uses device name
    _attr_supported_features = (
        LawnMowerEntityFeature.START_MOWING
        | LawnMowerEntityFeature.PAUSE
        | LawnMowerEntityFeature.DOCK
    )

    def __init__(self, coordinator: GoatG1Coordinator) -> None:
        super().__init__(coordinator, "lawn_mower")

    @property
    def activity(self) -> LawnMowerActivity | None:
        if not self.coordinator.data:
            return None
        state = self.coordinator.data.get("state", "unknown")
        return _STATE_MAP.get(state)

    async def async_start_mowing(self) -> None:
        await self.coordinator.api.start_mowing()
        await self.coordinator.async_request_refresh()

    async def async_pause(self) -> None:
        await self.coordinator.api.pause()
        await self.coordinator.async_request_refresh()

    async def async_dock(self) -> None:
        await self.coordinator.api.dock()
        await self.coordinator.async_request_refresh()
