# Ecovacs Goat G1 – Home Assistant Integration

Custom integration for the **Ecovacs Goat G1** robotic lawn mower.
Direkte Cloud-API-Anbindung, kein MQTT.

## Features

### Entitäten

| Entität | Typ | Beschreibung |
|---|---|---|
| Goat G1 | `lawn_mower` | Start, Pause, Ladestation, Status |
| Rand mähen | `button` | Rand-Mähmodus starten |
| Signalton | `button` | Akustisches Signal auslösen |
| Akku | `sensor` | Akkustand in % |
| Firmware | `sensor` | Firmware-Version |
| WLAN-Netzwerk | `sensor` | SSID |
| IP-Adresse | `sensor` | IP-Adresse |
| Signalstärke | `sensor` | WLAN-RSSI in dBm |
| MAC-Adresse | `sensor` | MAC-Adresse |
| Messerverschleiß | `sensor` | Restlebensdauer Messer in % |
| Bürstenwalzenverschleiß | `sensor` | Restlebensdauer Bürstenwalze in % |
| Letzte Mähfläche | `sensor` | Fläche der letzten Sitzung in m² |
| Letzte Mähdauer | `sensor` | Dauer der letzten Sitzung |
| Gesamtmähfläche | `sensor` | Kumulierte Mähfläche |
| Gesamtmähdauer | `sensor` | Kumulierte Mähdauer |
| Mähvorgänge gesamt | `sensor` | Anzahl der Mähvorgänge |
| Fehlercode | `sensor` | Aktueller Fehlercode |
| Randmähfunktion | `switch` | Randmähfunktion ein/aus |
| Erweiterter Modus | `switch` | Erweiterter Modus ein/aus |
| Kindersicherung | `switch` | Kindersicherung ein/aus |
| Anhebe-Warnung | `switch` | Warnung beim Anheben |
| Kartengrenzwarnung | `switch` | Kartengrenzwarnung ein/aus |
| Schutzfunktion | `switch` | Schutzfunktion ein/aus |
| Hinderniserkennung | `switch` | TrueDetect ein/aus |
| Lautstärke | `number` | Lautstärke 0–10 |
| Mährichtung | `number` | Mähwinkel 0–180° |

### Services

| Service | Parameter | Beschreibung |
|---|---|---|
| `ecovacs_goat_g1.start_border_mowing` | – | Rand-Mähmodus starten |
| `ecovacs_goat_g1.start_zone` | `zone_id` | Zone mähen |
| `ecovacs_goat_g1.set_mowing_direction` | `angle` (0–180) | Mährichtung setzen |

## Installation

### HACS (empfohlen)
1. HACS → Integrationen → ⋮ → Benutzerdefinierte Repositories
2. URL: `https://github.com/it00x32/ecovacs-goat-g1-ha`
3. Typ: Integration
4. Installieren → Home Assistant neu starten

### Manuell
1. `custom_components/ecovacs_goat_g1/` in dein HA-Konfigurationsverzeichnis kopieren
2. Home Assistant neu starten

## Einrichtung

1. **Einstellungen** → **Geräte & Dienste** → **Integration hinzufügen**
2. Nach **Ecovacs Goat G1** suchen
3. E-Mail, Passwort und Land eingeben
4. Falls Ecovacs eine **Geräteverifizierung** verlangt: Bestätigungscode aus der E-Mail eingeben (einmalig, gebunden an die gespeicherte Client-`device_id`)
5. Gerät auswählen (falls mehrere vorhanden)

> **Hinweis (API-Änderung 2026):** Der alte Passwort-Login (`appVersion` 1.6.3) liefert oft Fehler **1013**. Die Integration nutzt App-Version **3.14.0** und den neuen Flow `sendEmailVerifyCode` → `verifyDevice` → `getAuthCode` → `loginByItToken`. Token und `device_id` werden in der Config Entry gespeichert.

## Voraussetzungen

- Home Assistant 2024.1 oder neuer
- Ecovacs-Konto mit Goat G1
- `aiohttp` und `cryptography` (werden über die Integration nachgezogen / sind in HA üblich)

## Technische Details

Die Integration nutzt die direkte Ecovacs Cloud-REST-API (kein MQTT).
Status-Polling alle 30 Sekunden. Authentifizierung bevorzugt gespeicherte Tokens; bei Ablauf bzw. 1013 startet ein Reauth-Flow.

**Hinweis:** Der Rand-Mähmodus (`type: border`) ist nicht offiziell dokumentiert und basiert auf Reverse Engineering. Falls dieser nicht funktioniert, bitte ein [Issue](https://github.com/it00x32/ecovacs-goat-g1-ha/issues) erstellen.

## Lizenz

MIT License
