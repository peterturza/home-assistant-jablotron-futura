"""Example integration using DataUpdateCoordinator."""
from __future__ import annotations

import logging

from .futura import FuturaEntity
from homeassistant.backports.enum import StrEnum
from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Config entry example."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            FuturaSettingsSwitchEntity(idx, device_class, coordinator)
            for idx, device_class in [
                ("bypass", SwitchDeviceClass.SWITCH),
                ("cooling", SwitchDeviceClass.SWITCH),
                ("heating", SwitchDeviceClass.SWITCH),
                ("radon_protection", SwitchDeviceClass.SWITCH),
            ]
        ]
    )


class FuturaEnabledEnum(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"


class FuturaSettingsSwitchEntity(FuturaEntity, SwitchEntity):
    def __init__(self, idx, device_class, coordinator):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self._idx = idx
        self._device_class = device_class

    @property
    def unique_id(self) -> str:
        return self._idx

    @property
    def value(self) -> str:
        return self.coordinator.data["device"]["settings"]["extended_properties"][
            self._idx
        ]

    @property
    def is_on(self) -> bool:
        return self.value == FuturaEnabledEnum.ENABLED

    @property
    def available(self) -> bool:
        return self.value in list(map(str, FuturaEnabledEnum))

    @property
    def device_class(self) -> str | None:
        return self._device_class

    async def async_turn_on(self, **kwargs):
        await self._futura.set_setting_extended_property(
            self._idx, FuturaEnabledEnum.ENABLED
        )
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs):
        await self._futura.set_setting_extended_property(
            self._idx, FuturaEnabledEnum.DISABLED
        )
        await self.coordinator.async_refresh()
