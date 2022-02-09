"""Main class definitions"""
from __future__ import annotations

import logging
from typing import Any

from config.custom_components.jablotron_futura.const import (
    DOMAIN,
    JABLOTRON,
    JABLOTRON_API,
    JABLOTRON_API_DEFAULT_HEADERS,
    JABLOTRON_FUTURA_NAMESPACE,
    JABLOTRON_FUTURA_NAMESPACE_KEY,
)
from config.custom_components.jablotron_futura.errors import ApiAuthError
from homeassistant import core
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

_LOGGER = logging.getLogger(__name__)


class FuturaCentralUnit:
    def __init__(
        self,
        service_id: str,
        model: str,
        hw_version: str,
        fw_version: str,
        serial_no: str,
        room_id: str,
    ) -> None:
        self.service_id: str = service_id
        self.model: str = model
        self.hw_version: str = hw_version
        self.fw_version: str = fw_version
        self.serial_no: str = serial_no
        self.room_id: str = room_id


class Futura:
    def __init__(self, hass: core.HomeAssistant, username: str, password: str) -> None:
        self._hass: core.HomeAssistant = hass
        self._username: str = username
        self._password: str = password
        self._central_unit: FuturaCentralUnit | None = None
        self._session = aiohttp_client.async_get_clientsession(
            self._hass, verify_ssl=False
        )

    async def authorize(self) -> None:
        async with self._session.post(
            "{}/userAuthorize.json".format(JABLOTRON_API),
            json={
                "login": self._username,
                "password": self._password,
            },
            headers=JABLOTRON_API_DEFAULT_HEADERS,
        ) as result:
            if result.status != 200:
                _LOGGER.error(result)
                raise ApiAuthError

    async def sync(self):
        await self.authorize()
        async with self._session.post(
            "{}/serviceListGet.json".format(JABLOTRON_API),
            json={
                "visibility": "DEFAULT",
                "list-type": "EXTENDED",
                "checksum": "",
            },
            headers=JABLOTRON_API_DEFAULT_HEADERS,
        ) as result:
            json = await result.json()
            _LOGGER.debug(json)
            data = json["data"]
            futura_services = filter(
                lambda service: service["visible"]
                and service["status"] == "ENABLED"
                and service["service-type"].lower() == JABLOTRON_FUTURA_NAMESPACE,
                data["services"],
            )
            service = list(futura_services)[0]
        async with self._session.post(
            "{}/getDevice.json".format(JABLOTRON_API),
            json={
                "id": str(service["service-id"]),
                "status": "true",
                "type": JABLOTRON_FUTURA_NAMESPACE,
                "system": "IOS",
                "checksum": "",
            },
            headers=JABLOTRON_API_DEFAULT_HEADERS
            | {JABLOTRON_FUTURA_NAMESPACE_KEY: JABLOTRON_FUTURA_NAMESPACE},
        ) as result:
            json = await result.json()
            device = json["device"]
            _LOGGER.debug(device)
            self._central_unit = FuturaCentralUnit(
                service_id=device["id"],
                model=device["type"],
                hw_version=device["details"]["hw_revision"],
                fw_version=device["details"]["fw_version"],
                serial_no=device["details"]["serial_no"],
                room_id=device["rooms"][0]["id"],
            )
            return json

    async def set_control(self, control, value) -> None:
        async with self._session.post(
            "{}/setDevice.json".format(JABLOTRON_API),
            json={
                "device": {
                    "type": JABLOTRON_FUTURA_NAMESPACE,
                    "control": [
                        {
                            "manual": {control: value},
                            "room_id": self._central_unit.room_id,
                        }
                    ],
                    "id": self._central_unit.service_id,
                },
                "system": "IOS",
            },
            headers=JABLOTRON_API_DEFAULT_HEADERS
            | {JABLOTRON_FUTURA_NAMESPACE_KEY: JABLOTRON_FUTURA_NAMESPACE},
        ) as result:
            return

    async def set_setting_extended_property(self, property, value) -> None:
        async with self._session.post(
            "{}/setDevice.json".format(JABLOTRON_API),
            json={
                "device": {
                    "type": JABLOTRON_FUTURA_NAMESPACE,
                    "settings": {"extended_properties": {property: value}},
                    "id": self._central_unit.service_id,
                },
                "system": "IOS",
            },
            headers=JABLOTRON_API_DEFAULT_HEADERS
            | {JABLOTRON_FUTURA_NAMESPACE_KEY: JABLOTRON_FUTURA_NAMESPACE},
        ) as result:
            return

    def central_unit(self) -> FuturaCentralUnit:
        return self._central_unit


class FuturaEntity(CoordinatorEntity):
    def __init__(self, coordinator):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self._futura = coordinator.futura
        self._central_unit = self._futura.central_unit()

    @property
    def name(self) -> str | None:
        return "{}.{}".format(DOMAIN, self.unique_id)

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self._central_unit.serial_no)
            },
            manufacturer=JABLOTRON,
            name=DOMAIN,
            model=self._central_unit.model,
            sw_version=self._central_unit.fw_version,
            hw_version=self._central_unit.hw_version,
            via_device=(DOMAIN, self._central_unit.serial_no),
        )


class FuturaControlEntity(FuturaEntity):
    def __init__(self, idx, device_class, coordinator):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self._idx = idx
        self._device_class = device_class

    def data(self) -> dict[str, Any]:
        controls = self.coordinator.data["device"]["data"]["controls"]
        return list(filter(lambda control: control["id"] == self._idx, controls))[0]

    @property
    def available(self) -> bool:
        return self.data is not None

    @property
    def unique_id(self) -> str:
        return self._idx

    @property
    def device_class(self) -> str | None:
        return self._device_class
