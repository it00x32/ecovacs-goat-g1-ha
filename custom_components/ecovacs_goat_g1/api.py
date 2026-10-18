"""Ecovacs Goat G1 – direct cloud API client (no MQTT)."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode

from aiohttp import ClientSession
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

_LOGGER = logging.getLogger(__name__)

CLIENT_KEY         = "1520391301804"
CLIENT_SECRET      = "6c319b2a5cd3e66e39159c2e28f2fce9"
AUTH_CLIENT_KEY    = "1520391491841"
AUTH_CLIENT_SECRET = "77ef58ce3afbe337da74aa8c5ab963a9"
REALM              = "ecouser.net"
USER_AGENT         = "Dalvik/2.1.0 (Linux; U; Android 14; Pixel 7 Build/UP1A.231105.001)"
PUBLIC_KEY_CONFIG  = "PUBLIC.KEY.CONFIG"
ANDROID_MODEL      = "Pixel 7"
ANDROID_SYSTEM     = "Android 14"

# Ecovacs rejects the old 1.6.3 password login with code 1013; current app uses 3.14.0
META = {
    "lang": "EN",
    "appCode": "global_e",
    "appVersion": "3.14.0",
    "channel": "google_play",
    "deviceType": "1",
}

EU = {"AD","AL","AT","AX","BA","BE","BG","BY","CH","CY","CZ","DE","DK","EE","ES","FI",
      "FO","FR","GB","GG","GI","GR","HR","HU","IE","IM","IS","IT","JE","LI","LT","LU",
      "LV","MC","MD","ME","MK","MT","NL","NO","PL","PT","RO","RS","RU","SE","SI","SJ",
      "SK","SM","UA","VA"}
ASC= {"AE","AF","AM","AZ","BD","BH","BN","BT","CC","CX","GE","HK","ID","IL","IN","IO",
      "IQ","IR","JP","KG","KH","KP","KR","KW","KZ","LA","LB","LK","MM","MN","MO","MV",
      "MY","NP","OM","PH","PK","PS","QA","SA","SG","SY","TH","TJ","TM","TR","TW","UZ",
      "VN","YE"}
NA = {"AG","AI","AW","BB","BL","BM","BQ","BS","BZ","CA","CR","CU","CW","DM","DO","GL",
      "GP","GT","GU","HN","HT","JM","KN","KY","LC","MF","MQ","MS","MX","NI","PA","PM",
      "PR","SV","SX","TC","TT","VC","VG","VI"}


class GoatG1Error(Exception):
    """Generic API error."""


class AuthError(GoatG1Error):
    """Authentication failed."""


class DeviceVerificationRequiredError(AuthError):
    """Ecovacs requires email device verification (API code 1013)."""


class InvalidVerificationCodeError(AuthError):
    """Email verification code rejected (API code 1012)."""


def _md5(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()


def generate_device_id() -> str:
    """Stable-looking client device id (must stay constant after email verification)."""
    return _md5(f"ecovacs-ha-goat-g1-{time.time_ns()}")


def _get_urls(country: str) -> dict[str, str]:
    eco = "UK" if country == "GB" else country
    c   = eco.lower()
    if   country == "CN": portal = "https://portal.ecouser.net"
    elif country in EU:   portal = "https://portal-eu.ecouser.net"
    elif country in ASC:  portal = "https://portal-as.ecouser.net"
    elif country in NA:   portal = "https://portal-na.ecouser.net"
    else:                 portal = "https://portal-ww.ecouser.net"
    tld = "cn" if country == "CN" else "com"
    return {
        "portal":   portal,
        "login":    f"https://gl-{c}-api.ecovacs.{tld}",
        "authcode": f"https://gl-{c}-openapi.ecovacs.{tld}",
        "eco":      eco,
    }


def _sign(params: dict, extra: dict, key: str, secret: str) -> dict:
    all_p = {**extra, **params}
    text  = key + "".join(f"{k}={all_p[k]}" for k in sorted(all_p)) + secret
    params["authSign"]   = _md5(text)
    params["authAppkey"] = key
    return params


class GoatG1Api:
    """Async API client for Ecovacs Goat G1."""

    def __init__(self, session: ClientSession, device_id: str | None = None) -> None:
        self._s         = session
        self.device_id  = device_id or generate_device_id()
        self.country    = ""
        self.user_id    = ""
        self.token      = ""
        self.expires_at = 0
        self.device: dict[str, Any] | None = None
        self.devices: list[dict[str, Any]] = []
        self._public_key: rsa.RSAPublicKey | None = None
        self._email: str = ""
        self._password_hash: str = ""
        self._account_uid: str = ""
        self._access_token: str = ""
        self._auth_lock = asyncio.Lock()
        self._auth_blocked_until = 0.0
        self._on_credentials: Callable[[dict[str, Any]], None] | None = None

    # ── Internal HTTP helpers ─────────────────────────────────────────────────

    async def _get(self, url: str) -> Any:
        async with self._s.get(url, headers={"User-Agent": USER_AGENT}) as r:
            return await r.json(content_type=None)

    async def _post(self, url: str, payload: Any) -> Any:
        async with self._s.post(
            url, json=payload,
            headers={"User-Agent": USER_AGENT, "Content-Type": "application/json"},
        ) as r:
            return await r.json(content_type=None)

    def _meta(self, country: str) -> dict[str, str]:
        eco = "UK" if country == "GB" else country
        return {**META, "country": eco.lower(), "deviceId": self.device_id}

    def _private_path(self, country: str, endpoint: str) -> str:
        m = self._meta(country)
        return (
            f"/v1/private/{m['country']}/{m['lang']}/{m['deviceId']}/"
            f"{m['appCode']}/{m['appVersion']}/{m['channel']}/{m['deviceType']}/{endpoint}"
        )

    async def _private_api(self, country: str, endpoint: str, params: dict[str, Any]) -> Any:
        urls = _get_urls(country)
        meta = self._meta(country)
        now  = time.time()
        body = {
            **params,
            "requestId": _md5(str(now)),
            "authTimespan": str(int(now * 1000)),
            "authTimeZone": "GMT-8",
        }
        signed = _sign(body, meta, CLIENT_KEY, CLIENT_SECRET)
        url = f"{urls['login']}{self._private_path(country, endpoint)}?{urlencode(signed)}"
        return await self._get(url)

    def _raise_auth(self, j: dict, context: str) -> None:
        code = j.get("code")
        msg  = j.get("msg", "")
        if code == "0000":
            return
        if code in ("1005", "1010"):
            raise AuthError(f"{context}: {msg or j}")
        if code == "1012":
            raise InvalidVerificationCodeError(msg or "Incorrect verification code")
        if code == "1013":
            raise DeviceVerificationRequiredError(
                msg or "Please update to the latest version / device verification required"
            )
        raise AuthError(f"{context}: code={code} {msg or j}")

    async def _api(self, path: str, body: dict, query: dict | None = None) -> Any:
        urls  = _get_urls(self.country)
        fbody = {
            **body,
            "auth": {
                "with": "users",
                "userid": self.user_id,
                "realm": REALM,
                "token": self.token,
                "resource": self.device_id,
            },
        }
        url = f"{urls['portal']}/api/{path}"
        if query:
            url += f"?{urlencode(query)}"
        return await self._post(url, fbody)

    # ── Authentication ────────────────────────────────────────────────────────

    def apply_credentials(self, user_id: str, token: str, country: str,
                          expires_at: int = 0) -> None:
        """Reuse previously stored portal credentials (skip password login)."""
        self.user_id    = user_id
        self.token      = token
        self.country    = country
        self.expires_at = expires_at

    def set_on_credentials(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Called after a portal token is minted so the config entry can be updated."""
        self._on_credentials = callback

    def credentials_data(self) -> dict[str, Any]:
        """Serializable auth fields for ConfigEntry storage."""
        return {
            "device_id":     self.device_id,
            "user_id":       self.user_id,
            "token":         self.token,
            "expires_at":    self.expires_at,
            "account_uid":   self._account_uid,
            "access_token":  self._access_token,
        }

    def token_valid(self) -> bool:
        return bool(self.token and self.user_id and self.expires_at > time.time() + 60)

    async def _get_public_key(self, country: str) -> rsa.RSAPublicKey:
        if self._public_key is not None:
            return self._public_key
        j = await self._private_api(country, "common/getConfig", {"keys": PUBLIC_KEY_CONFIG})
        self._raise_auth(j, "getConfig")
        entries = j.get("data")
        if not isinstance(entries, list):
            raise AuthError("Invalid public key configuration response")
        for entry in entries:
            if isinstance(entry, dict) and entry.get("key") == PUBLIC_KEY_CONFIG:
                value = entry.get("value")
                if isinstance(value, str):
                    self._public_key = self._load_public_key(value)
                    return self._public_key
        raise AuthError("Ecovacs public key configuration is missing")

    @staticmethod
    def _load_public_key(config_value: str) -> rsa.RSAPublicKey:
        import json
        try:
            encoded = json.loads(config_value)["publicKey"]
            key = serialization.load_der_public_key(base64.b64decode(encoded, validate=True))
        except Exception as ex:
            raise AuthError("Invalid Ecovacs public key") from ex
        if not isinstance(key, rsa.RSAPublicKey):
            raise AuthError("Ecovacs public key is not an RSA key")
        return key

    async def _encrypt_account(self, country: str, account: str) -> str:
        public_key = await self._get_public_key(country)
        encrypted  = public_key.encrypt(account.encode(), padding.PKCS1v15())
        return base64.b64encode(encrypted).decode()

    async def _complete_login(self, country: str, uid: str, access_token: str) -> None:
        urls = _get_urls(country)
        eco  = urls["eco"]

        p2 = _sign(
            {"uid": uid, "accessToken": access_token, "bizType": "ECOVACS_IOT",
             "deviceId": self.device_id, "authTimespan": str(int(time.time() * 1000))},
            {"openId": "global"}, AUTH_CLIENT_KEY, AUTH_CLIENT_SECRET,
        )
        j2 = await self._get(f"{urls['authcode']}/v1/global/auth/getAuthCode?{urlencode(p2)}")
        self._raise_auth(j2, "AuthCode")
        auth_code = j2["data"]["authCode"]

        token_body = {
            "edition": "ECOGLOBLE",
            "userId": uid,
            "token": auth_code,
            "realm": REALM,
            "resource": self.device_id,
            "org": "ECOCN" if country == "CN" else "ECOWW",
            "last": "",
            "country": "Chinese" if country == "CN" else eco,
            "todo": "loginByItToken",
        }
        j3: dict | None = None
        for _ in range(3):
            j3 = await self._post(f"{urls['portal']}/api/users/user.do", token_body)
            if j3.get("result") == "ok":
                break
            if j3.get("error") != "set token error.":
                break
        if not j3 or j3.get("result") != "ok":
            raise AuthError(f"Token login failed: {j3}")

        self.country       = country
        self._account_uid  = uid
        self._access_token = access_token
        self.user_id       = j3["userId"]
        self.token         = j3["token"]
        # last = validity in ms (usually 7 days); store ~99%
        validity_ms = int(j3.get("last") or 604800000)
        self.expires_at = int(time.time() + validity_ms / 1000 * 0.99)
        self._auth_blocked_until = 0.0

    async def login(self, email: str, password_hash: str, country: str) -> None:
        """Password login. May raise DeviceVerificationRequiredError (code 1013)."""
        self._email = email
        self._password_hash = password_hash
        endpoint = "user/loginCheckMobile" if country == "CN" else "user/login"
        j1 = await self._private_api(
            country, endpoint, {"account": email, "password": password_hash},
        )
        self._raise_auth(j1, "Login")
        data = j1.get("data") or {}
        await self._complete_login(country, str(data["uid"]), str(data["accessToken"]))

    async def request_device_verification_code(self, email: str, country: str) -> None:
        """Send one-time email code to verify this client device_id."""
        self._email = email
        encrypted = await self._encrypt_account(country, email)
        j = await self._private_api(
            country,
            "user/sendEmailVerifyCode",
            {
                "encryptEmail": encrypted,
                "verifyType": "EMAIL_VERIFY_DEVICE",
                "supportChar": "N",
                "isForce": "N",
            },
        )
        self._raise_auth(j, "sendEmailVerifyCode")

    async def verify_device(
        self, email: str, country: str, verification_code: str
    ) -> None:
        """Complete device verification with email code, then finish portal login."""
        self._email = email
        encrypted = await self._encrypt_account(country, email)
        j = await self._private_api(
            country,
            "user/verifyDevice",
            {
                "encryptAccount": encrypted,
                "backUpEmail": "",
                "verifyCode": verification_code.strip(),
                "model": ANDROID_MODEL,
                "system": ANDROID_SYSTEM,
            },
        )
        self._raise_auth(j, "verifyDevice")
        data = j.get("data") or {}
        await self._complete_login(country, str(data["uid"]), str(data["accessToken"]))

    async def ensure_login(
        self,
        email: str,
        password_hash: str,
        country: str,
        *,
        user_id: str = "",
        token: str = "",
        expires_at: int = 0,
        account_uid: str = "",
        access_token: str = "",
    ) -> None:
        """Prefer cached token; otherwise mint one from the account token or password."""
        self._email = email
        self._password_hash = password_hash
        if account_uid:
            self._account_uid = account_uid
        if access_token:
            self._access_token = access_token
        if user_id and token and expires_at > time.time() + 60:
            self.apply_credentials(user_id, token, country, expires_at)
            return
        if self._account_uid and self._access_token:
            try:
                await self._complete_login(country, self._account_uid, self._access_token)
                return
            except AuthError:
                _LOGGER.debug("Stored account token rejected", exc_info=True)
        await self.login(email, password_hash, country)

    async def refresh_auth(self) -> None:
        """Mint a new portal token after the cloud rejected the current one."""
        if not self.country:
            raise AuthError("auth denied")
        refreshed = False
        if self._account_uid and self._access_token:
            try:
                await self._complete_login(
                    self.country, self._account_uid, self._access_token
                )
                refreshed = True
            except AuthError:
                _LOGGER.debug("Account-token refresh failed", exc_info=True)
        if not refreshed:
            if not self._email or not self._password_hash:
                raise AuthError("auth denied")
            await self.login(self._email, self._password_hash, self.country)
        if self._on_credentials is not None:
            self._on_credentials(self.credentials_data())

    def _collect_devices(self, responses: tuple[Any, ...]) -> tuple[list[dict[str, Any]], bool]:
        seen: dict[str, Any] = {}
        denied = False
        for r in responses:
            if self._auth_denied(r):
                denied = True
                continue
            if not isinstance(r, dict):
                continue
            for d in r.get("devices") or []:
                if isinstance(d, dict) and d.get("did"):
                    seen[d["did"]] = d
        return list(seen.values()), denied

    async def _request_device_lists(self) -> tuple[Any, Any]:
        return await asyncio.gather(
            self._api("users/user.do",  {"userid": self.user_id, "todo": "GetDeviceList"}),
            self._api("appsvr/app.do",  {"userid": self.user_id, "todo": "GetGlobalDeviceList"}),
        )

    async def fetch_devices(self) -> list[dict[str, Any]]:
        responses = await self._request_device_lists()
        devices, denied = self._collect_devices(responses)
        if not devices and denied:
            _LOGGER.warning("Device list rejected with auth denied; refreshing portal token")
            await self.refresh_auth()
            responses = await self._request_device_lists()
            devices, _denied = self._collect_devices(responses)
        self.devices = devices
        return self.devices

    # ── Command helper ────────────────────────────────────────────────────────

    @staticmethod
    def _auth_denied(r: Any) -> bool:
        """Portal OAuth rejection (errno 3), before the mower sees the command."""
        status = r.get("ret") if isinstance(r, dict) else None
        if status is None and isinstance(r, dict):
            status = r.get("result")
        return isinstance(r, dict) and status == "fail" and str(r.get("errno")) == "3"

    async def _dispatch_cmd(self, cmd: str, data: Any = None) -> dict[str, Any]:
        dev = self.device
        if not dev:
            raise GoatG1Error("No device selected")
        payload: dict[str, Any] = {
            "header": {"pri": "1", "ts": time.time(), "tzm": 480, "ver": "0.0.50"}
        }
        if data is not None and (isinstance(data, list) or (isinstance(data, dict) and data)):
            payload["body"] = {"data": data}
        return await self._api(
            "iot/devmanager.do",
            {"cmdName": cmd, "payload": payload, "payloadType": "j", "td": "q",
             "toId": dev["did"], "toRes": dev["resource"], "toType": dev["class"]},
            {"mid": dev["class"], "did": dev["did"], "td": "q",
             "u": self.user_id, "cv": "1.67.3", "t": "a", "av": "1.3.1"},
        )

    async def send_cmd(self, cmd: str, data: Any = None) -> dict[str, Any]:
        if time.time() < self._auth_blocked_until:
            raise AuthError(
                "Ecovacs hat die Anmeldung abgelehnt (auth denied). "
                "Bitte die Integration neu authentifizieren."
            )
        r = await self._dispatch_cmd(cmd, data)
        if not self._auth_denied(r):
            return r
        async with self._auth_lock:
            r = await self._dispatch_cmd(cmd, data)
            if not self._auth_denied(r):
                return r
            _LOGGER.warning(
                "Ecovacs rejected %s with auth denied; refreshing portal token", cmd
            )
            try:
                await self.refresh_auth()
            except AuthError:
                self._auth_blocked_until = time.time() + 300
                raise
            r = await self._dispatch_cmd(cmd, data)
        if self._auth_denied(r):
            self._auth_blocked_until = time.time() + 300
            raise AuthError(
                "Ecovacs hat die Anmeldung abgelehnt (auth denied). "
                "Bitte die Integration neu authentifizieren."
            )
        return r

    def _ok(self, r: Any) -> bool:
        return isinstance(r, dict) and r.get("ret") == "ok"

    def _data(self, r: Any) -> dict[str, Any]:
        return r.get("resp", {}).get("body", {}).get("data", {}) if isinstance(r, dict) else {}

    # ── Status ────────────────────────────────────────────────────────────────

    async def poll_status(self) -> dict[str, Any]:
        batt_r, clean_r, charge_r = await asyncio.gather(
            self.send_cmd("getBattery"),
            self.send_cmd("getCleanInfo_V2"),
            self.send_cmd("getChargeState"),
            return_exceptions=True,
        )
        for item in (batt_r, clean_r, charge_r):
            if isinstance(item, AuthError):
                raise item
        out: dict[str, Any] = {"battery": None, "state": "unknown", "available": False}

        if not isinstance(batt_r, Exception):
            out["available"] = self._ok(batt_r)
            bd = self._data(batt_r)
            if bd.get("value") is not None:
                out["battery"] = bd["value"]

        if not isinstance(clean_r, Exception) and self._ok(clean_r):
            cd  = self._data(clean_r)
            st  = cd.get("state")
            ms  = cd.get("cleanState", {}).get("motionState")
            if cd.get("trigger") == "alert":
                out["state"] = "error"
            elif st in ("clean", "washing"):
                out["state"] = ("mowing" if ms == "working" else
                                "paused"    if ms == "pause"      else
                                "returning" if ms == "goCharging" else "mowing")
            elif st == "goCharging":
                out["state"] = "returning"
            elif st == "idle":
                ch = {} if isinstance(charge_r, Exception) else self._data(charge_r)
                out["state"] = "docked" if ch.get("isCharging") == 1 else "idle"
            else:
                out["state"] = st or "unknown"
        return out

    async def get_firmware_version(self) -> str | None:
        try:
            r = await self.send_cmd("getOta")
            return self._data(r).get("ver")
        except Exception:
            return None

    # ── Settings ──────────────────────────────────────────────────────────────

    async def get_settings(self) -> dict[str, Any]:
        from .const import TOGGLE_SETTINGS
        tasks = [self.send_cmd(t[1]) for t in TOGGLE_SETTINGS] + [self.send_cmd("getVolume")]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        out: dict[str, Any] = {}
        for i, (key, _, __, field) in enumerate(TOGGLE_SETTINGS):
            r = results[i]
            v = None if isinstance(r, Exception) else self._data(r).get(field)
            out[key] = (True if v == 1 else False if v == 0 else None)
        vol_r = results[len(TOGGLE_SETTINGS)]
        out["volume"] = (None if isinstance(vol_r, Exception)
                         else self._data(vol_r).get("volume"))
        return out

    async def set_toggle(self, set_cmd: str, field: str, value: bool) -> None:
        r = await self.send_cmd(set_cmd, {field: 1 if value else 0})
        if not self._ok(r):
            raise GoatG1Error(f"{set_cmd} failed: {r}")

    async def set_volume(self, volume: int) -> None:
        r = await self.send_cmd("setVolume", {"volume": max(0, min(10, round(volume)))})
        if not self._ok(r):
            raise GoatG1Error(f"setVolume failed: {r}")

    # ── Mowing direction ──────────────────────────────────────────────────────

    async def get_mowing_direction(self) -> int:
        r = await self.send_cmd("getCutDirection")
        return self._data(r).get("angle", 0)

    async def set_mowing_direction(self, angle: int) -> None:
        deg = max(0, min(180, round(angle)))
        r   = await self.send_cmd("setCutDirection", {"angle": deg})
        if not self._ok(r):
            raise GoatG1Error(f"setCutDirection failed: {r}")

    # ── Info queries ──────────────────────────────────────────────────────────

    async def get_network_info(self) -> dict[str, Any]:
        r = await self.send_cmd("getNetInfo")
        d = self._data(r)
        return {"ip": d.get("ip"), "ssid": d.get("ssid"),
                "rssi": d.get("rssi"), "mac": d.get("mac")}

    async def get_life_span(self) -> dict[str, Any]:
        r    = await self.send_cmd("getLifeSpan", ["blade", "lensBrush"])
        data = self._data(r)
        out: dict[str, Any] = {}
        if isinstance(data, list):
            for c in data:
                left  = int(c.get("left",  0))
                total = int(c.get("total", 1))
                out[c["type"]] = round((left / total) * 100) if total > 0 else 0
        return out

    async def get_stats(self) -> dict[str, Any]:
        sr, tr = await asyncio.gather(
            self.send_cmd("getStats"), self.send_cmd("getTotalStats"),
            return_exceptions=True,
        )
        sd = {} if isinstance(sr, Exception) else self._data(sr)
        td = {} if isinstance(tr, Exception) else self._data(tr)
        return {"last_area": sd.get("area"), "last_time": sd.get("time"),
                "total_area": td.get("area"), "total_time": td.get("time"),
                "total_count": td.get("count")}

    async def get_errors(self) -> list[int]:
        r     = await self.send_cmd("getError")
        codes = self._data(r).get("code", [])
        return codes if isinstance(codes, list) else []

    # ── Actions ───────────────────────────────────────────────────────────────

    async def play_sound(self) -> None:
        await self.send_cmd("playSound", {"count": 1, "sid": 30})

    async def start_mowing(self) -> None:
        r = await self.send_cmd("clean_V2", {"act": "start", "content": {"type": "auto"}})
        if not self._ok(r):
            raise GoatG1Error(f"start failed: {r}")

    async def start_border_mowing(self) -> None:
        r = await self.send_cmd("clean_V2", {"act": "start", "content": {"type": "border"}})
        _LOGGER.warning("start_border_mowing response: %s", r)
        if not self._ok(r):
            ret = r.get("ret") if isinstance(r, dict) else "?"
            raise GoatG1Error(f"start_border failed (ret={ret}): {r}")

    async def start_zone(self, zone_id: str) -> None:
        r = await self.send_cmd(
            "clean_V2",
            {"act": "start", "content": {"type": "spotArea", "value": str(zone_id)}},
        )
        if not self._ok(r):
            raise GoatG1Error(f"start_zone failed: {r}")

    async def pause(self) -> None:
        await self.send_cmd("clean_V2", {"act": "pause",  "content": {"type": ""}})

    async def stop(self) -> None:
        await self.send_cmd("clean_V2", {"act": "stop",   "content": {"type": ""}})

    async def dock(self) -> None:
        await self.send_cmd("charge", {"act": "go"})

    # ── Zones ─────────────────────────────────────────────────────────────────

    async def fetch_zones(self) -> list[dict[str, Any]]:
        try:
            map_r = await self.send_cmd("getCachedMapInfo")
            _LOGGER.debug("getCachedMapInfo raw response: %s", map_r)
            d     = self._data(map_r)
            maps  = d.get("info") or d.get("maps") or []
            _LOGGER.debug("Maps found: %d → %s", len(maps), maps)

            active = (
                next((m for m in maps if m.get("using") == 1 and m.get("built") == 1), None)
                or next((m for m in maps if m.get("using") == 1), None)
                or (maps[0] if maps else None)
            )
            if not active:
                _LOGGER.warning("fetch_zones: no map available")
                return []

            mid = active["mid"]
            _LOGGER.debug("Using map mid=%s", mid)

            subsets: list[dict] = []
            for map_type in ("ar", "vw", "sa"):
                set_r = await self.send_cmd("getMapSet", {"mid": mid, "type": map_type})
                _LOGGER.debug("getMapSet type=%s raw: %s", map_type, set_r)
                subsets = self._data(set_r).get("subsets", [])
                if subsets:
                    _LOGGER.debug("Found %d subsets with type=%s", len(subsets), map_type)
                    break

            if not subsets:
                _LOGGER.warning("fetch_zones: no subsets found for mid=%s", mid)
                return []

            async def fetch_one(sub: dict) -> dict[str, Any]:
                mssid = sub.get("mssid") or sub.get("id") or str(sub)
                name = sub.get("name") or ""
                if not name:
                    try:
                        sr   = await self.send_cmd("getMapSubSet",
                                                   {"mid": mid, "mssid": mssid, "type": "ar"})
                        _LOGGER.debug("getMapSubSet mssid=%s raw: %s", mssid, sr)
                        name = self._data(sr).get("name") or mssid
                    except Exception as e:
                        _LOGGER.debug("getMapSubSet failed for %s: %s", mssid, e)
                        name = mssid
                try:
                    fixed = bytes(name, "latin-1").decode("utf-8")
                    name  = fixed if "\ufffd" not in fixed else name
                except Exception:
                    pass
                _LOGGER.debug("Zone: id=%s name=%s", mssid, name)
                return {"id": mssid, "name": name}

            return list(await asyncio.gather(*[fetch_one(s) for s in subsets]))
        except Exception as exc:
            _LOGGER.warning("Could not load zones: %s", exc)
            return []
