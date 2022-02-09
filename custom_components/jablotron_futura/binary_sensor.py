"""Example integration using DataUpdateCoordinator."""
from __future__ import annotations

import logging

from config.custom_components.jablotron_futura.futura import FuturaEntity
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Config entry example."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            FuturaSummaryBinarySensorEntity(idx, device_class, coordinator)
            for idx, device_class in [
                ("current_servo_drying", BinarySensorDeviceClass.OPENING),
                ("current_servo_bypass", BinarySensorDeviceClass.OPENING),
            ]
        ]
    )


class FuturaSummaryBinarySensorEntity(FuturaEntity, BinarySensorEntity):
    def __init__(self, idx, device_class, coordinator):
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
    def is_on(self) -> bool:
        return self.coordinator.data["device"]["summary"][self._idx]

    @property
    def device_class(self) -> str | None:
        return self._device_class
