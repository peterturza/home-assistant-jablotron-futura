"""Switch definitions for Jablotron Futura integration."""

from __future__ import annotations

import logging
from enum import StrEnum

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity

from .futura import FuturaEntity

_LOGGER = logging.getLogger(__name__)


SWITCHES = (
    ("bypass", "Bypass", SwitchDeviceClass.SWITCH),
    ("cooling", "Cooling", SwitchDeviceClass.SWITCH),
    ("heating", "Heating", SwitchDeviceClass.SWITCH),
    ("radon_protection", "Radon Protection", SwitchDeviceClass.SWITCH),
)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    async_add_entities(
        FuturaSettingsSwitchEntity(idx, name, device_class, coordinator)
        for idx, name, device_class in SWITCHES
    )


class FuturaEnabledEnum(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"


class FuturaSettingsSwitchEntity(FuturaEntity, SwitchEntity):
    def __init__(self, idx, name, device_class, coordinator):
        super().__init__(coordinator)
        self._idx = idx
        self._attr_name = name
        self._device_class = device_class

    @property
    def unique_id(self) -> str:
        return f"{self._central_unit.serial_no}_{self._idx}"

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
