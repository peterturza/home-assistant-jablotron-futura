"""Select definitions for Jablotron Futura integration."""
from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
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
    """Set up Futura select entities."""
    coordinator = entry.runtime_data

    async_add_entities(
        [
            FuturaControlFanPowerEntity(coordinator),
            FuturaControlHumidityEntity(coordinator),
        ]
    )


class FuturaControlFanPowerEntity(FuturaControlEntity, SelectEntity):
    """Fan power control entity."""

    def __init__(self, coordinator) -> None:
        super().__init__(
            "control_fan_power", None, coordinator
        )

    @property
    def options(self) -> list[str]:
        data = self.data()
        device = self.coordinator.data["device"]
        airflow_units = device["summary"]["airflow_units"]
        airflows = [
            "{} {}".format(airflow, airflow_units)
            for airflow in device["summary"]["airflow"]
        ]
        if data["extended_properties"]["min"] == 0:
            airflows.insert(0, "off")

        options = [
            option
            for option in range(
                data["extended_properties"]["min"],
                data["extended_properties"]["max"],
            )
        ]
        return [
            "{} ({})".format(option, airflow)
            for option, airflow in zip(options, airflows)
        ] + ["auto"]

    @property
    def current_option(self) -> str | None:
        data = self.data()
        return self.options[int(data["extended_properties"]["value"])]

    async def async_select_option(self, option: str) -> None:
        await self._futura.set_control("fan_power", self.options.index(option))
        await self.coordinator.async_refresh()


class FuturaControlHumidityEntity(FuturaControlEntity, SelectEntity):
    """Humidity control entity."""

    def __init__(self, coordinator) -> None:
        super().__init__("control_humidity", None, coordinator)

    @property
    def options(self) -> list[str]:
        data = self.data()
        return [option["title"] for option in data["extended_properties"]["options"]]

    @property
    def current_option(self) -> str | None:
        data = self.data()
        return [
            option
            for option in data["extended_properties"]["options"]
            if option["id"] == data["extended_properties"]["value"]
        ][0]["title"]

    async def async_select_option(self, option: str) -> None:
        data = self.data()
        value = [
            opt
            for opt in data["extended_properties"]["options"]
            if opt["title"] == option
        ][0]["id"]
        await self._futura.set_control("humidity", value)
        await self.coordinator.async_refresh()
