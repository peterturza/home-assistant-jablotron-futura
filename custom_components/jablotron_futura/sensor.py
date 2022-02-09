"""Example integration using DataUpdateCoordinator."""
from __future__ import annotations

from datetime import date, datetime
import logging
from typing import Any

from .futura import FuturaEntity
from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    DEVICE_CLASS_CO2,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
)
from homeassistant.helpers.typing import StateType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Config entry example."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            FuturaSummarySensorEntity(idx, device_class, coordinator)
            for idx, device_class in [
                ("filter_health", None),
                ("device_consumption", DEVICE_CLASS_POWER),
                ("heating_recovered_current", DEVICE_CLASS_POWER),
            ]
        ]
        + [
            FuturaPeripherySensorEnity(idx, device_class, coordinator)
            for idx, device_class in [
                ("fut_co2_ppm_max", DEVICE_CLASS_CO2),
                ("fut_humi_indoor", DEVICE_CLASS_HUMIDITY),
                ("fut_temp_indoor", DEVICE_CLASS_TEMPERATURE),
                ("fut_temp_outdoor", DEVICE_CLASS_TEMPERATURE),
            ]
        ]
    )


class FuturaSummarySensorEntity(FuturaEntity, SensorEntity):
    def __init__(self, idx, device_class, coordinator):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self._idx = idx
        self._device_class = device_class

    @property
    def unique_id(self) -> str:
        return self._idx

    @property
    def available(self) -> bool:
        return self._idx in self.coordinator.data["device"]["summary"]

    @property
    def native_value(self) -> StateType | date | datetime:
        return self.coordinator.data["device"]["summary"][self._idx]

    @property
    def state_class(self) -> SensorStateClass | str | None:
        return STATE_CLASS_MEASUREMENT

    @property
    def device_class(self) -> SensorDeviceClass | str | None:
        return self._device_class

    @property
    def native_unit_of_measurement(self) -> str | None:
        return self.coordinator.data["device"]["summary"]["{}_units".format(self._idx)]


class FuturaPeripherySensorEnity(FuturaEntity, SensorEntity):
    def __init__(self, idx, device_class, coordinator):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self._idx = idx
        self._device_class = device_class

    @property
    def periphery(self) -> dict[str, Any] | None:
        peripheries = self.coordinator.data["device"]["peripheries"]
        filtered = list(
            filter(lambda periphery: periphery["id"] == self._idx, peripheries)
        )
        return filtered[0] if filtered else None

    @property
    def available(self) -> bool:
        return self.periphery is not None

    @property
    def unique_id(self) -> str:
        return self._idx

    @property
    def native_value(self) -> StateType | date | datetime:
        value = self.periphery["extended_properties"]["value"]
        return round(value, 1) if value else None

    @property
    def state_class(self) -> SensorStateClass | str | None:
        return STATE_CLASS_MEASUREMENT

    @property
    def device_class(self) -> SensorDeviceClass | str | None:
        return self._device_class

    @property
    def native_unit_of_measurement(self) -> str | None:
        return self.periphery["extended_properties"]["units"]
