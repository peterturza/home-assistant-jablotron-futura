"""Number definitions for Jablotron Futura integration."""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .__init__ import JablotronFuturaConfigEntry
from .futura import FuturaControlEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JablotronFuturaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Futura number entities."""
    coordinator = entry.runtime_data

    async_add_entities(
        [
            FuturaControlTemperatureEntity(coordinator),
        ]
    )


class FuturaControlTemperatureEntity(FuturaControlEntity, NumberEntity):
    """Temperature control entity."""

    def __init__(self, coordinator) -> None:
        super().__init__(
            "control_temperature", NumberDeviceClass.TEMPERATURE, coordinator
        )

    @property
    def native_value(self) -> float | None:
        return self.data()["extended_properties"]["value"]

    @property
    def native_min_value(self) -> float:
        return self.data()["extended_properties"]["min"]

    @property
    def native_max_value(self) -> float:
        return self.data()["extended_properties"]["max"]

    @property
    def native_step(self) -> float:
        return self.data()["extended_properties"]["step"]

    @property
    def native_unit_of_measurement(self) -> str | None:
        return self.data()["extended_properties"]["units"]

    async def async_set_native_value(self, value: float) -> None:
        await self._futura.set_control("temperature", value)
        await self.coordinator.async_refresh()
