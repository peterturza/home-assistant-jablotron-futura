"""Example integration using DataUpdateCoordinator."""
from __future__ import annotations

import logging

from .futura import FuturaControlEntity
from homeassistant.components.number import NumberEntity
from homeassistant.const import DEVICE_CLASS_TEMPERATURE

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Config entry example."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            FuturaControlTemperatureEntity(coordinator),
        ]
    )


class FuturaControlTemperatureEntity(FuturaControlEntity, NumberEntity):
    def __init__(self, coordinator):
        super().__init__("control_temperature", DEVICE_CLASS_TEMPERATURE, coordinator)

    @property
    def value(self) -> float | None:
        return self.data()["extended_properties"]["value"]

    @property
    def min_value(self) -> float:
        return self.data()["extended_properties"]["min"]

    @property
    def max_value(self) -> float:
        return self.data()["extended_properties"]["max"]

    @property
    def step(self) -> float:
        return self.data()["extended_properties"]["step"]

    @property
    def unit_of_measurement(self) -> str | None:
        return self.data()["extended_properties"]["units"]

    async def async_set_value(self, value: float) -> None:
        await self._futura.set_control("temperature", value)
        await self.coordinator.async_refresh()
