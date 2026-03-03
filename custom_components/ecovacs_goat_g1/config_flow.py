"""Config flow for Ecovacs Goat G1."""
from __future__ import annotations

import hashlib
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GoatG1Api, AuthError
from .const import DOMAIN, CONF_PASSWORD_HASH, CONF_COUNTRY, CONF_DEVICE_INDEX

_LOGGER = logging.getLogger(__name__)

COUNTRIES = [
    "AT", "AU", "BE", "CA", "CH", "CN", "CZ", "DE", "DK", "ES", "FI",
    "FR", "GB", "GR", "HU", "IE", "IT", "JP", "KR", "MX", "NL", "NO",
    "NZ", "PL", "PT", "RO", "RU", "SE", "SG", "SK", "TR", "UA", "US",
]


class GoatG1ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ecovacs Goat G1."""

    VERSION = 1

    def __init__(self) -> None:
        self._email:    str = ""
        self._pw_hash:  str = ""
        self._country:  str = ""
        self._devices:  list[dict] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            email    = user_input["email"].strip()
            password = user_input["password"]
            country  = user_input["country"]
            pw_hash  = hashlib.md5(password.encode()).hexdigest()

            session = async_get_clientsession(self.hass)
            api     = GoatG1Api(session)
            try:
                await api.login(email, pw_hash, country)
                devices = await api.fetch_devices()
            except AuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected error during login")
                errors["base"] = "cannot_connect"
            else:
                self._email   = email
                self._pw_hash = pw_hash
                self._country = country
                self._devices = devices

                if len(devices) == 0:
                    errors["base"] = "no_devices"
                elif len(devices) == 1:
                    return self._create_entry(0)
                else:
                    return await self.async_step_select_device()

        schema = vol.Schema({
            vol.Required("email"):    str,
            vol.Required("password"): str,
            vol.Required("country", default="AT"): vol.In(COUNTRIES),
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_select_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            idx = int(user_input["device"])
            return self._create_entry(idx)

        choices = {
            str(i): d.get("name") or d.get("nick") or d.get("did", f"Device {i}")
            for i, d in enumerate(self._devices)
        }
        schema = vol.Schema({vol.Required("device"): vol.In(choices)})
        return self.async_show_form(step_id="select_device", data_schema=schema)

    def _create_entry(self, device_index: int) -> FlowResult:
        dev  = self._devices[device_index]
        name = dev.get("name") or dev.get("nick") or "Goat G1"
        return self.async_create_entry(
            title=name,
            data={
                "email":             self._email,
                CONF_PASSWORD_HASH:  self._pw_hash,
                CONF_COUNTRY:        self._country,
                CONF_DEVICE_INDEX:   device_index,
            },
        )
