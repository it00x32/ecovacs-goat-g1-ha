"""DataUpdateCoordinator for Ecovacs Goat G1."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import GoatG1Api, GoatG1Error
from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class GoatG1Coordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls the Goat G1 cloud API and distributes data to all entities."""

    def __init__(self, hass: HomeAssistant, api: GoatG1Api) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )
        self.api      = api
        self.zones:    list[dict[str, Any]] = []
        self.settings: dict[str, Any]       = {}
        self.network:  dict[str, Any]       = {}
        self.lifespan: dict[str, Any]       = {}
        self.stats:    dict[str, Any]       = {}
        self.errors:   list[int]            = []
        self.fw_version: str | None         = None
        self.direction: int                 = 0
        self.selected_zone_id: str | None   = None

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.api.poll_status()
        except GoatG1Error as err:
            raise UpdateFailed(f"Goat G1 update failed: {err}") from err

    async def async_load_static_data(self) -> None:
        """Load once-per-session data (settings, network, life span, stats, direction)."""
        import asyncio
        results = await asyncio.gather(
            self.api.get_firmware_version(),
            self.api.get_settings(),
            self.api.get_network_info(),
            self.api.get_life_span(),
            self.api.get_stats(),
            self.api.get_errors(),
            self.api.get_mowing_direction(),
            self.api.fetch_zones(),
            return_exceptions=True,
        )
        if not isinstance(results[0], Exception): self.fw_version = results[0]
        if not isinstance(results[1], Exception): self.settings   = results[1]
        if not isinstance(results[2], Exception): self.network    = results[2]
        if not isinstance(results[3], Exception): self.lifespan   = results[3]
        if not isinstance(results[4], Exception): self.stats      = results[4]
        if not isinstance(results[5], Exception): self.errors     = results[5]
        if not isinstance(results[6], Exception): self.direction  = results[6]
        if not isinstance(results[7], Exception):
            self.zones = results[7]
            if self.zones and self.selected_zone_id is None:
                self.selected_zone_id = self.zones[0]["id"]
        _LOGGER.debug("Static data loaded: fw=%s zones=%d", self.fw_version, len(self.zones))
