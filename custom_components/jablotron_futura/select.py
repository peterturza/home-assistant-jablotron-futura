"""Select definitions for Jablotron Futura integration."""
from __future__ import annotations

import logging

from .futura import FuturaControlEntity
from homeassistant.components.select import SelectEntity
from homeassistant.const import DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_POWER_FACTOR

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            FuturaControlFanPowerEntity(coordinator),
            FuturaControlHumidityEntity(coordinator),
        ]
    )


class FuturaControlFanPowerEntity(FuturaControlEntity, SelectEntity):
    def __init__(self, coordinator):
        super().__init__("control_fan_power", DEVICE_CLASS_POWER_FACTOR, coordinator)

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
    def __init__(self, coordinator):
        super().__init__("control_humidity", DEVICE_CLASS_HUMIDITY, coordinator)

    @property
    def options(self) -> list[str]:
        data = self.data()
        return [option["title"] for option in data["extended_properties"]["options"]]

    @property
    def current_option(self) -> str | None:
        data = self.data()
        return list(
            filter(
                lambda option: option["id"] == data["extended_properties"]["value"],
                data["extended_properties"]["options"],
            )
        )[0]["title"]

    async def async_select_option(self, option: str) -> None:
        data = self.data()
        value = list(
            filter(
                lambda opt: opt["title"] == option,
                data["extended_properties"]["options"],
            )
        )[0]["id"]
        await self._futura.set_control("humidity", value)
        await self.coordinator.async_refresh()
