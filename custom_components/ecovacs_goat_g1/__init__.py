"""Ecovacs Goat G1 Home Assistant integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    AuthError,
    DeviceVerificationRequiredError,
    GoatG1Api,
    generate_device_id,
)
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_ACCOUNT_UID,
    CONF_COUNTRY,
    CONF_DEVICE_ID,
    CONF_DEVICE_INDEX,
    CONF_EXPIRES_AT,
    CONF_PASSWORD_HASH,
    CONF_TOKEN,
    CONF_USER_ID,
    DOMAIN,
)
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


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entries to store device_id / tokens."""
    if entry.version < 2:
        data = {**entry.data}
        if CONF_DEVICE_ID not in data:
            # Keep a deterministic id for existing installs so a one-time
            # email verification can stick across restarts.
            data[CONF_DEVICE_ID] = generate_device_id()
        hass.config_entries.async_update_entry(entry, data=data, version=2)
        _LOGGER.info("Migrated Ecovacs Goat G1 config entry to version 2")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    device_id = entry.data.get(CONF_DEVICE_ID) or generate_device_id()
    api = GoatG1Api(session, device_id=device_id)

    try:
        await api.ensure_login(
            entry.data["email"],
            entry.data[CONF_PASSWORD_HASH],
            entry.data[CONF_COUNTRY],
            user_id=entry.data.get(CONF_USER_ID, ""),
            token=entry.data.get(CONF_TOKEN, ""),
            expires_at=int(entry.data.get(CONF_EXPIRES_AT) or 0),
            account_uid=entry.data.get(CONF_ACCOUNT_UID, ""),
            access_token=entry.data.get(CONF_ACCESS_TOKEN, ""),
        )
    except DeviceVerificationRequiredError as err:
        raise ConfigEntryAuthFailed(
            "Ecovacs erfordert eine Geräteverifizierung per E-Mail-Code. "
            "Bitte die Integration erneut authentifizieren."
        ) from err
    except AuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err

    def _persist_credentials(creds: dict) -> None:
        hass.config_entries.async_update_entry(entry, data={**entry.data, **creds})

    api.set_on_credentials(_persist_credentials)

    # Persist refreshed credentials / device_id without wiping other fields
    new_data = {**entry.data, **api.credentials_data()}
    if new_data != dict(entry.data):
        hass.config_entries.async_update_entry(entry, data=new_data)

    try:
        await api.fetch_devices()
    except DeviceVerificationRequiredError as err:
        raise ConfigEntryAuthFailed(
            "Ecovacs erfordert eine Geräteverifizierung per E-Mail-Code. "
            "Bitte die Integration erneut authentifizieren."
        ) from err
    except AuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err

    idx = entry.data.get(CONF_DEVICE_INDEX, 0)
    if not api.devices:
        _LOGGER.error("No devices found for Goat G1 account")
        return False
    api.device = api.devices[min(idx, len(api.devices) - 1)]

    coordinator = GoatG1Coordinator(hass, api, entry)
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
