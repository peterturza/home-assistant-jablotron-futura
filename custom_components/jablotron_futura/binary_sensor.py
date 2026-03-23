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

    async_add_entities(
        [
            FuturaSummaryBinarySensorEntity(coordinator, description)
            for description in BINARY_SENSORS
        ]
    )


class FuturaSummaryBinarySensorEntity(FuturaEntity, BinarySensorEntity):
    """Futura summary binary sensor entity."""

    entity_description: BinarySensorEntityDescription

    def __init__(self, coordinator, description: BinarySensorEntityDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description

    @property
    def unique_id(self) -> str:
        return self.entity_description.key

    @property
    def available(self) -> bool:
        return self.entity_description.key in self.coordinator.data["device"]["summary"]

    @property
    def is_on(self) -> bool:
        return self.coordinator.data["device"]["summary"][self.entity_description.key]
