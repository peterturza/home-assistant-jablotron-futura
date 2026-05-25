"""Binary Sensor definitions for Jablotron Futura integration."""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .__init__ import JablotronFuturaConfigEntry
from .futura import FuturaEntity

_LOGGER = logging.getLogger(__name__)


BINARY_SENSORS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="current_servo_drying",
        name="Servo Drying",
        device_class=BinarySensorDeviceClass.OPENING,
    ),
    BinarySensorEntityDescription(
        key="current_servo_bypass",
        name="Servo Bypass",
        device_class=BinarySensorDeviceClass.OPENING,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JablotronFuturaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Futura binary sensors."""
    coordinator = entry.runtime_data

    entities = []
    for unit in coordinator.futura.units().values():
        entities += [
            FuturaSummaryBinarySensorEntity(coordinator, unit, description)
            for description in BINARY_SENSORS
        ]
    async_add_entities(entities)


class FuturaSummaryBinarySensorEntity(FuturaEntity, BinarySensorEntity):
    """Futura summary binary sensor entity."""

    entity_description: BinarySensorEntityDescription

    def __init__(self, coordinator, central_unit, description: BinarySensorEntityDescription) -> None:
        super().__init__(coordinator, central_unit)
        self.entity_description = description

    @property
    def unique_id(self) -> str:
        return f"{self._serial}_{self.entity_description.key}"

    @property
    def available(self) -> bool:
        return self.entity_description.key in self._device["summary"]

    @property
    def is_on(self) -> bool:
        return self._device["summary"][self.entity_description.key]
