"""Futura class definitions"""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .const import (
    DOMAIN,
    JABLOTRON,
    JABLOTRON_API,
    JABLOTRON_API_DEFAULT_HEADERS,
    JABLOTRON_FUTURA_NAMESPACE,
    JABLOTRON_FUTURA_NAMESPACE_KEY,
)
from .errors import ApiAuthError
from homeassistant import core
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class FuturaCentralUnit:
    """Represents Futura main unit"""

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
        self._units: dict[str, FuturaCentralUnit] = {}
        self._authenticated: bool = False
        self._session = aiohttp_client.async_get_clientsession(self._hass)

    async def authorize(self) -> None:
        """Authorize user via API. Sets _authenticated on success."""
        self._authenticated = False
        try:
            async with self._session.post(
                "{}/userAuthorize.json".format(JABLOTRON_API),
                json={"login": self._username, "password": self._password},
                headers=JABLOTRON_API_DEFAULT_HEADERS,
            ) as result:
                if result.status in (401, 403):
                    raise ApiAuthError("Invalid Jablotron credentials")
                if result.status != 200:
                    raise UpdateFailed(
                        f"Jablotron API authorization failed with status {result.status}"
                    )
                self._authenticated = True
        except (TimeoutError, aiohttp.ClientError) as err:
            raise UpdateFailed(f"Error communicating with Jablotron API: {err}") from err

    async def _ensure_authorized(self) -> None:
        """Call authorize() only when the cached session has been invalidated."""
        if not self._authenticated:
            await self.authorize()

    async def _post(self, url: str, json: dict[str, Any], headers: dict[str, str]) -> Any:
        """POST with one transparent re-auth on 401/403. Returns parsed JSON or raises."""
        await self._ensure_authorized()
        try:
            async with self._session.post(url, json=json, headers=headers) as result:
                if result.status in (401, 403):
                    # Session cookie expired — invalidate and retry once.
                    self._authenticated = False
                    await self._ensure_authorized()
                    async with self._session.post(url, json=json, headers=headers) as retry:
                        if retry.status in (401, 403):
                            raise ApiAuthError(
                                f"Jablotron API still rejected request after re-auth (status {retry.status})"
                            )
                        if retry.status != 200:
                            raise UpdateFailed(
                                f"Jablotron API call failed with status {retry.status}"
                            )
                        return await retry.json()
                if result.status != 200:
                    raise UpdateFailed(
                        f"Jablotron API call failed with status {result.status}"
                    )
                return await result.json()
        except (TimeoutError, aiohttp.ClientError) as err:
            raise UpdateFailed(f"Error communicating with Jablotron API: {err}") from err

    async def sync(self) -> dict[str, Any]:
        """Fetch every Futura unit on the account.

        Returns a dict keyed by serial number: ``{serial_no: device_json}``.
        """
        service_json = await self._post(
            "{}/serviceListGet.json".format(JABLOTRON_API),
            json={"visibility": "DEFAULT", "list-type": "EXTENDED", "checksum": ""},
            headers=JABLOTRON_API_DEFAULT_HEADERS,
        )
        _LOGGER.debug(service_json)
        data = service_json["data"]
        futura_services = [
            service
            for service in data["services"]
            if service["visible"]
            and service["status"] == "ENABLED"
            and service["service-type"].lower() == JABLOTRON_FUTURA_NAMESPACE
        ]
        if not futura_services:
            raise UpdateFailed("No Futura service found")

        units: dict[str, FuturaCentralUnit] = {}
        result: dict[str, Any] = {}
        for service in futura_services:
            device_json = await self._post(
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
            )
            device = device_json["device"]
            _LOGGER.debug(device)
            serial_no = device["details"]["serial_no"]
            units[serial_no] = FuturaCentralUnit(
                service_id=device["id"],
                model=device["type"],
                hw_version=device["details"]["hw_revision"],
                fw_version=device["details"]["fw_version"],
                serial_no=serial_no,
                room_id=device["rooms"][0]["id"],
            )
            result[serial_no] = device_json

        self._units = units
        return result

    async def set_control(self, serial: str, control, value) -> None:
        """Sets control value via API for the unit with the given serial."""
        unit = self._units[serial]
        await self._post(
            "{}/setDevice.json".format(JABLOTRON_API),
            json={
                "device": {
                    "type": JABLOTRON_FUTURA_NAMESPACE,
                    "control": [
                        {
                            "manual": {control: value},
                            "room_id": unit.room_id,
                        }
                    ],
                    "id": unit.service_id,
                },
                "system": "IOS",
            },
            headers=JABLOTRON_API_DEFAULT_HEADERS
            | {JABLOTRON_FUTURA_NAMESPACE_KEY: JABLOTRON_FUTURA_NAMESPACE},
        )

    async def set_setting_extended_property(
        self, serial: str, prop_name: str, prop_value
    ) -> None:
        """Sets extended property value via API for the unit with the given serial."""
        unit = self._units[serial]
        await self._post(
            "{}/setDevice.json".format(JABLOTRON_API),
            json={
                "device": {
                    "type": JABLOTRON_FUTURA_NAMESPACE,
                    "settings": {"extended_properties": {prop_name: prop_value}},
                    "id": unit.service_id,
                },
                "system": "IOS",
            },
            headers=JABLOTRON_API_DEFAULT_HEADERS
            | {JABLOTRON_FUTURA_NAMESPACE_KEY: JABLOTRON_FUTURA_NAMESPACE},
        )

    def units(self) -> dict[str, FuturaCentralUnit]:
        return self._units

    def primary_unit(self) -> FuturaCentralUnit | None:
        """First unit by service order; used for legacy entity-id migration."""
        return next(iter(self._units.values()), None)


class FuturaEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, central_unit):
        super().__init__(coordinator)
        self._futura = coordinator.futura
        self._central_unit = central_unit
        self._serial = central_unit.serial_no

    @property
    def _device(self) -> dict[str, Any]:
        """This unit's device payload from the coordinator data."""
        return self.coordinator.data[self._serial]["device"]

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._serial)},
            manufacturer=JABLOTRON,
            name=DOMAIN,
            model=self._central_unit.model,
            sw_version=self._central_unit.fw_version,
            hw_version=self._central_unit.hw_version,
        )


class FuturaControlEntity(FuturaEntity):
    def __init__(self, idx, device_class, coordinator, central_unit):
        super().__init__(coordinator, central_unit)
        self._idx = idx
        self._device_class = device_class

    def data(self) -> dict[str, Any] | None:
        controls = self._device["data"]["controls"]
        matched = [c for c in controls if c["id"] == self._idx]
        return matched[0] if matched else None

    @property
    def available(self) -> bool:
        return self.data() is not None

    @property
    def unique_id(self) -> str:
        return f"{self._serial}_{self._idx}"

    @property
    def device_class(self) -> str | None:
        return self._device_class
