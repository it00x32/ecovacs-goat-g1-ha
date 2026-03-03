"""Sensor entities for Ecovacs Goat G1."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfArea,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import GoatG1Coordinator
from .entity import GoatG1Entity


@dataclass(frozen=True, kw_only=True)
class GoatSensorDescription(SensorEntityDescription):
    value_fn: Any = None


SENSORS: tuple[GoatSensorDescription, ...] = (
    GoatSensorDescription(
        key="battery",
        name="Akku",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.data.get("battery") if c.data else None,
    ),
    GoatSensorDescription(
        key="firmware",
        name="Firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: c.fw_version,
    ),
    GoatSensorDescription(
        key="ssid",
        name="WLAN-Netzwerk",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: c.network.get("ssid"),
    ),
    GoatSensorDescription(
        key="ip",
        name="IP-Adresse",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: c.network.get("ip"),
    ),
    GoatSensorDescription(
        key="rssi",
        name="Signalstärke",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: c.network.get("rssi"),
    ),
    GoatSensorDescription(
        key="mac",
        name="MAC-Adresse",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: c.network.get("mac"),
    ),
    GoatSensorDescription(
        key="blade_wear",
        name="Messerverschleiß",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: c.lifespan.get("blade"),
    ),
    GoatSensorDescription(
        key="lens_wear",
        name="Bürstenwalzenverschleiß",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: c.lifespan.get("lensBrush"),
    ),
    GoatSensorDescription(
        key="last_area",
        name="Letzte Mähfläche",
        native_unit_of_measurement=UnitOfArea.SQUARE_METERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.stats.get("last_area"),
    ),
    GoatSensorDescription(
        key="last_time",
        name="Letzte Mähdauer",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.stats.get("last_time"),
    ),
    GoatSensorDescription(
        key="total_area",
        name="Gesamtmähfläche",
        native_unit_of_measurement=UnitOfArea.SQUARE_METERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda c: c.stats.get("total_area"),
    ),
    GoatSensorDescription(
        key="total_time",
        name="Gesamtmähdauer",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda c: c.stats.get("total_time"),
    ),
    GoatSensorDescription(
        key="total_count",
        name="Mähvorgänge gesamt",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda c: c.stats.get("total_count"),
    ),
    GoatSensorDescription(
        key="error",
        name="Fehlercode",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: (
            next((e for e in c.errors if e != 0), 0) if c.errors else 0
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GoatG1Coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(GoatG1Sensor(coordinator, desc) for desc in SENSORS)


class GoatG1Sensor(GoatG1Entity, SensorEntity):
    entity_description: GoatSensorDescription

    def __init__(self, coordinator: GoatG1Coordinator, desc: GoatSensorDescription) -> None:
        super().__init__(coordinator, desc.key)
        self.entity_description = desc

    @property
    def native_value(self) -> Any:
        try:
            return self.entity_description.value_fn(self.coordinator)
        except Exception:
            return None
