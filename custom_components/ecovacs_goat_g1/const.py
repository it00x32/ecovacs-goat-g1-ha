"""Constants for the Ecovacs Goat G1 integration."""

DOMAIN = "ecovacs_goat_g1"
CONF_PASSWORD_HASH = "password_hash"
CONF_COUNTRY = "country"
CONF_DEVICE_INDEX = "device_index"

SCAN_INTERVAL = 30  # seconds

TOGGLE_SETTINGS = [
    ("border_switch",            "getBorderSwitch",          "setBorderSwitch",          "enable"),
    ("advanced_mode",            "getAdvancedMode",           "setAdvancedMode",           "enable"),
    ("child_lock",               "getChildLock",              "setChildLock",              "on"),
    ("moveup_warning",           "getMoveupWarning",          "setMoveupWarning",          "enable"),
    ("cross_map_border_warning", "getCrossMapBorderWarning",  "setCrossMapBorderWarning",  "enable"),
    ("safe_protect",             "getSafeProtect",            "setSafeProtect",            "enable"),
    ("true_detect",              "getTrueDetect",             "setTrueDetect",             "enable"),
]

TOGGLE_LABELS = {
    "border_switch":            "Randmähfunktion",
    "advanced_mode":            "Erweiterter Modus",
    "child_lock":               "Kindersicherung",
    "moveup_warning":           "Anhebe-Warnung",
    "cross_map_border_warning": "Kartengrenzwarnung",
    "safe_protect":             "Schutzfunktion",
    "true_detect":              "Hinderniserkennung",
}

COUNTRIES = [
    "AT", "AU", "BE", "CA", "CH", "CN", "CZ", "DE", "DK", "ES", "FI",
    "FR", "GB", "GR", "HU", "IE", "IT", "JP", "KR", "MX", "NL", "NO",
    "NZ", "PL", "PT", "RO", "RU", "SE", "SG", "SK", "TR", "UA", "US",
]
