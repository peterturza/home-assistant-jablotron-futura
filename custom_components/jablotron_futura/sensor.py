"""Sensor definitions for Jablotron Futura integration."""
from __future__ import annotations

from datetime import date, datetime
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .__init__ import JablotronFuturaConfigEntry
from .futura import FuturaEntity

_LOGGER = logging.getLogger(__name__)


SUMMARY_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="filter_health",
        name="Filter Health",
    ),
    SensorEntityDescription(
        key="device_consumption",
        name="Device Consumption",
        device_class=SensorDeviceClass.POWER,
    ),
    SensorEntityDescription(
        key="heating_recovered_current",
        name="Heating Recovered Current",
        device_class=SensorDeviceClass.POWER,
    ),
)

PERIPHERY_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="fut_co2_ppm_max",
        name="CO2 Max",
        device_class=SensorDeviceClass.CO2,
    ),
    SensorEntityDescription(
        key="fut_humi_indoor",
        name="Indoor Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    SensorEntityDescription(
        key="fut_temp_indoor",
        name="Indoor Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="fut_temp_outdoor",
        name="Outdoor Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JablotronFuturaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Futura sensors."""
    coordinator = entry.runtime_data

    async_add_entities(
        [
            FuturaSummarySensorEntity(coordinator, description)
            for description in SUMMARY_SENSORS
        ]
        + [
            FuturaPeripherySensorEntity(coordinator, description)
            for description in PERIPHERY_SENSORS
        ]
    )


class FuturaSummarySensorEntity(FuturaEntity, SensorEntity):
    """Futura summary sensor entity."""

    entity_description: SensorEntityDescription

    def __init__(self, coordinator, description: SensorEntityDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description

    @property
    def unique_id(self) -> str:
        return self.entity_description.key

    @property
    def available(self) -> bool:
        return self.entity_description.key in self.coordinator.data["device"]["summary"]

    @property
    def native_value(self) -> StateType | date | datetime:
        return self.coordinator.data["device"]["summary"][self.entity_description.key]

    @property
    def state_class(self) -> SensorStateClass | str | None:
        return SensorStateClass.MEASUREMENT

    @property
    def native_unit_of_measurement(self) -> str | None:
        return self.coordinator.data["device"]["summary"][
            "{}_units".format(self.entity_description.key)
        ]


class FuturaPeripherySensorEntity(FuturaEntity, SensorEntity):
    """Futura periphery sensor entity."""

    entity_description: SensorEntityDescription

    def __init__(self, coordinator, description: SensorEntityDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description

    @property
    def periphery(self) -> dict[str, Any] | None:
        peripheries = self.coordinator.data["device"]["peripheries"]
        filtered = [
            p for p in peripheries if p["id"] == self.entity_description.key
        ]
        return filtered[0] if filtered else None

    @property
    def available(self) -> bool:
        return self.periphery is not None

    @property
    def unique_id(self) -> str:
        return self.entity_description.key

    @property
    def native_value(self) -> StateType | date | datetime:
        value = self.periphery["extended_properties"]["value"]
        return round(value, 1) if value else None

    @property
    def state_class(self) -> SensorStateClass | str | None:
        return SensorStateClass.MEASUREMENT

    @property
    def native_unit_of_measurement(self) -> str | None:
        return self.periphery["extended_properties"]["units"]
