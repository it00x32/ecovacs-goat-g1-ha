"""Config flow for Ecovacs Goat G1."""
from __future__ import annotations

import hashlib
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    AuthError,
    DeviceVerificationRequiredError,
    GoatG1Api,
    InvalidVerificationCodeError,
    generate_device_id,
)
from .const import (
    CONF_COUNTRY,
    CONF_DEVICE_ID,
    CONF_DEVICE_INDEX,
    CONF_PASSWORD_HASH,
    COUNTRIES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class GoatG1ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ecovacs Goat G1."""

    VERSION = 2

    def __init__(self) -> None:
        self._email: str = ""
        self._pw_hash: str = ""
        self._country: str = ""
        self._device_id: str = ""
        self._devices: list[dict] = []
        self._api: GoatG1Api | None = None
        self._reauth_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input["email"].strip()
            password = user_input["password"]
            country = user_input["country"]
            pw_hash = hashlib.md5(password.encode()).hexdigest()
            device_id = self._device_id or generate_device_id()

            session = async_get_clientsession(self.hass)
            api = GoatG1Api(session, device_id=device_id)
            try:
                await api.login(email, pw_hash, country)
            except DeviceVerificationRequiredError:
                # Request email code once; code is single-use — do not verify here
                try:
                    await api.request_device_verification_code(email, country)
                except AuthError:
                    _LOGGER.exception("Failed to send device verification email")
                    errors["base"] = "cannot_connect"
                else:
                    self._email = email
                    self._pw_hash = pw_hash
                    self._country = country
                    self._device_id = device_id
                    self._api = api
                    return await self.async_step_verify_device()
            except AuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected error during login")
                errors["base"] = "cannot_connect"
            else:
                self._email = email
                self._pw_hash = pw_hash
                self._country = country
                self._device_id = device_id
                self._api = api
                return await self._after_login()

        schema = vol.Schema({
            vol.Required("email"): str,
            vol.Required("password"): str,
            vol.Required("country", default="AT"): vol.In(COUNTRIES),
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_verify_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Enter the one-time email code from Ecovacs (device verification)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api = self._api
            if api is None:
                return await self.async_step_user()
            try:
                await api.verify_device(
                    self._email, self._country, user_input["verification_code"]
                )
            except InvalidVerificationCodeError:
                errors["base"] = "invalid_code"
            except AuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected error during device verification")
                errors["base"] = "cannot_connect"
            else:
                return await self._after_login()

        schema = vol.Schema({
            vol.Required("verification_code"): str,
        })
        return self.async_show_form(
            step_id="verify_device",
            data_schema=schema,
            errors=errors,
            description_placeholders={"email": self._email},
        )

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

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        """Re-authenticate when token expired and password login needs verification."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        if self._reauth_entry:
            self._email = self._reauth_entry.data.get("email", "")
            self._pw_hash = self._reauth_entry.data.get(CONF_PASSWORD_HASH, "")
            self._country = self._reauth_entry.data.get(CONF_COUNTRY, "AT")
            self._device_id = self._reauth_entry.data.get(CONF_DEVICE_ID) or generate_device_id()
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            password = user_input.get("password")
            if password:
                self._pw_hash = hashlib.md5(password.encode()).hexdigest()
            session = async_get_clientsession(self.hass)
            api = GoatG1Api(session, device_id=self._device_id)
            try:
                await api.login(self._email, self._pw_hash, self._country)
            except DeviceVerificationRequiredError:
                try:
                    await api.request_device_verification_code(self._email, self._country)
                except AuthError:
                    errors["base"] = "cannot_connect"
                else:
                    self._api = api
                    return await self.async_step_verify_device()
            except AuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Reauth login failed")
                errors["base"] = "cannot_connect"
            else:
                self._api = api
                return await self._after_login()

        schema = vol.Schema({
            vol.Optional("password"): str,
        })
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=schema,
            errors=errors,
            description_placeholders={"email": self._email},
        )

    async def _after_login(self) -> FlowResult:
        api = self._api
        assert api is not None
        try:
            devices = await api.fetch_devices()
        except Exception:
            _LOGGER.exception("Failed to fetch devices after login")
            return self.async_abort(reason="cannot_connect")

        self._devices = devices
        if self._reauth_entry is not None:
            return self._update_reauth_entry(0 if not devices else min(
                self._reauth_entry.data.get(CONF_DEVICE_INDEX, 0),
                max(len(devices) - 1, 0),
            ))

        if len(devices) == 0:
            return self.async_abort(reason="no_devices")
        if len(devices) == 1:
            return self._create_entry(0)
        return await self.async_step_select_device()

    def _entry_data(self, device_index: int) -> dict[str, Any]:
        api = self._api
        assert api is not None
        data = {
            "email": self._email,
            CONF_PASSWORD_HASH: self._pw_hash,
            CONF_COUNTRY: self._country,
            CONF_DEVICE_INDEX: device_index,
            **api.credentials_data(),
        }
        return data

    def _create_entry(self, device_index: int) -> FlowResult:
        dev = self._devices[device_index]
        name = dev.get("name") or dev.get("nick") or "Goat G1"
        return self.async_create_entry(title=name, data=self._entry_data(device_index))

    def _update_reauth_entry(self, device_index: int) -> FlowResult:
        assert self._reauth_entry is not None
        self.hass.config_entries.async_update_entry(
            self._reauth_entry, data=self._entry_data(device_index)
        )
        self.hass.async_create_task(
            self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
        )
        return self.async_abort(reason="reauth_successful")
