"""The Jablotron Futura integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_PASSWORD, CONF_USERNAME, DOMAIN
from .futura import Futura

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.BINARY_SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Jablotron Futura from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    futura = Futura(
        hass, username=entry.data[CONF_USERNAME], password=entry.data[CONF_PASSWORD]
    )
    coordinator = FuturaCoordinator(hass, futura)
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class FuturaCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, futura: Futura) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_method=futura.sync,
            update_interval=timedelta(minutes=5),
        )
        self.futura = futura
