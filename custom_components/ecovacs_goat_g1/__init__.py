"""Ecovacs Goat G1 Home Assistant integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GoatG1Api
from .const import DOMAIN, CONF_PASSWORD_HASH, CONF_COUNTRY, CONF_DEVICE_INDEX
from .coordinator import GoatG1Coordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.LAWN_MOWER,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.BUTTON,
    Platform.SELECT,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    api     = GoatG1Api(session)

    await api.login(
        entry.data["email"],
        entry.data[CONF_PASSWORD_HASH],
        entry.data[CONF_COUNTRY],
    )
    await api.fetch_devices()

    idx = entry.data.get(CONF_DEVICE_INDEX, 0)
    if not api.devices:
        _LOGGER.error("No devices found for Goat G1 account")
        return False
    api.device = api.devices[min(idx, len(api.devices) - 1)]

    coordinator = GoatG1Coordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()
    await coordinator.async_load_static_data()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return ok
