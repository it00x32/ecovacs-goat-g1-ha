"""Ecovacs Goat G1 – direct cloud API client (no MQTT, no external deps)."""
from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from typing import Any
from urllib.parse import urlencode

from aiohttp import ClientSession

_LOGGER = logging.getLogger(__name__)

CLIENT_KEY         = "1520391301804"
CLIENT_SECRET      = "6c319b2a5cd3e66e39159c2e28f2fce9"
AUTH_CLIENT_KEY    = "1520391491841"
AUTH_CLIENT_SECRET = "77ef58ce3afbe337da74aa8c5ab963a9"
REALM              = "ecouser.net"
USER_AGENT         = "Dalvik/2.1.0 (Linux; U; Android 5.1.1; A5010 Build/LMY48Z)"
DEVICE_ID          = hashlib.md5(b"ecovacs-ha-goat-g1").hexdigest()
META               = {"lang": "EN", "appCode": "global_e", "appVersion": "1.6.3",
                      "channel": "google_play", "deviceType": "1"}

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


def _md5(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()


def _get_urls(country: str) -> dict[str, str]:
    eco = "UK" if country == "GB" else country
    c   = eco.lower()
    if   country == "CN": portal = "https://portal.ecouser.net"
    elif country in EU:   portal = "https://portal-eu.ecouser.net"
    elif country in ASC:  portal = "https://portal-as.ecouser.net"
    elif country in NA:   portal = "https://portal-na.ecouser.net"
    else:                 portal = "https://portal-ww.ecouser.net"
    return {
        "portal": portal,
        "login":    f"https://gl-{c}-api.ecovacs.com",
        "authcode": f"https://gl-{c}-openapi.ecovacs.com",
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

    def __init__(self, session: ClientSession) -> None:
        self._s       = session
        self.country  = ""
        self.user_id  = ""
        self.token    = ""
        self.device: dict[str, Any] | None = None
        self.devices: list[dict[str, Any]] = []

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

    async def _api(self, path: str, body: dict, query: dict | None = None) -> Any:
        urls  = _get_urls(self.country)
        fbody = {
            **body,
            "auth": {"with": "users", "userid": self.user_id, "realm": REALM,
                     "token": self.token, "resource": DEVICE_ID},
        }
        url = f"{urls['portal']}/api/{path}"
        if query:
            url += f"?{urlencode(query)}"
        return await self._post(url, fbody)

    # ── Authentication ────────────────────────────────────────────────────────

    async def login(self, email: str, password_hash: str, country: str) -> None:
        """3-step Ecovacs cloud authentication."""
        urls = _get_urls(country)
        eco  = urls["eco"]
        meta = {**META, "country": eco.lower(), "deviceId": DEVICE_ID}

        p1 = _sign(
            {"account": email, "password": password_hash,
             "requestId": _md5(str(time.time())),
             "authTimespan": str(int(time.time() * 1000)),
             "authTimeZone": "GMT-8"},
            meta, CLIENT_KEY, CLIENT_SECRET,
        )
        path = f"/v1/private/{eco.lower()}/EN/{DEVICE_ID}/global_e/1.6.3/google_play/1/user/login"
        j1 = await self._get(f"{urls['login']}{path}?{urlencode(p1)}")
        if j1.get("code") != "0000":
            raise AuthError(f"Login failed: {j1.get('msg', j1)}")
        uid, access_token = j1["data"]["uid"], j1["data"]["accessToken"]

        p2 = _sign(
            {"uid": uid, "accessToken": access_token, "bizType": "ECOVACS_IOT",
             "deviceId": DEVICE_ID, "authTimespan": str(int(time.time() * 1000))},
            {"openId": "global"}, AUTH_CLIENT_KEY, AUTH_CLIENT_SECRET,
        )
        j2 = await self._get(f"{urls['authcode']}/v1/global/auth/getAuthCode?{urlencode(p2)}")
        if j2.get("code") != "0000":
            raise AuthError(f"AuthCode failed: {j2.get('msg', j2)}")
        auth_code = j2["data"]["authCode"]

        token_body = {"edition": "ECOGLOBLE", "userId": uid, "token": auth_code,
                      "realm": REALM, "resource": DEVICE_ID, "org": "ECOWW",
                      "last": "", "country": eco, "todo": "loginByItToken"}
        j3: dict | None = None
        for _ in range(3):
            j3 = await self._post(f"{urls['portal']}/api/users/user.do", token_body)
            if j3.get("result") == "ok":
                break
            if j3.get("error") != "set token error.":
                break
        if not j3 or j3.get("result") != "ok":
            raise AuthError(f"Token login failed: {j3}")

        self.country = country
        self.user_id = j3["userId"]
        self.token   = j3["token"]

    async def fetch_devices(self) -> list[dict[str, Any]]:
        r1, r2 = await asyncio.gather(
            self._api("users/user.do",  {"userid": self.user_id, "todo": "GetDeviceList"}),
            self._api("appsvr/app.do",  {"userid": self.user_id, "todo": "GetGlobalDeviceList"}),
        )
        seen: dict[str, Any] = {}
        for r in (r1, r2):
            for d in r.get("devices", []):
                seen[d["did"]] = d
        self.devices = list(seen.values())
        return self.devices

    # ── Command helper ────────────────────────────────────────────────────────

    async def send_cmd(self, cmd: str, data: Any = None) -> dict[str, Any]:
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
        if not self._ok(r):
            raise GoatG1Error(f"start_border failed: {r}")

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
            maps  = self._data(map_r).get("maps", [])
            _LOGGER.debug("Maps found: %d → %s", len(maps), maps)

            # Prefer the currently active map; fall back to any map
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

            # Try both area types the G1 might use
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
                # Use the name from the subset list directly when available
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
                # Fix latin-1 → utf-8 mis-encoding
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
