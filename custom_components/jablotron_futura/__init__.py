"""The Jablotron Futura integration."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_PASSWORD, CONF_USERNAME, DOMAIN
from .errors import ApiAuthError
from .futura import Futura

type JablotronFuturaConfigEntry = ConfigEntry[FuturaCoordinator]

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: JablotronFuturaConfigEntry) -> bool:
    """Set up Jablotron Futura from a config entry."""
    futura = Futura(
        hass, username=entry.data[CONF_USERNAME], password=entry.data[CONF_PASSWORD]
    )
    coordinator = FuturaCoordinator(hass, futura)

    await coordinator.async_config_entry_first_refresh()

    units = coordinator.futura.units()
    if not units or any(not serial for serial in units):
        raise ConfigEntryError(
            "One or more Jablotron units returned no serial number; cannot scope entity unique IDs"
        )

    # Migrate the config-entry unique id from a unit serial (legacy) to the
    # account login, so all units on one account share a single entry.
    account_uid = entry.data[CONF_USERNAME].lower()
    if entry.unique_id != account_uid:
        hass.config_entries.async_update_entry(entry, unique_id=account_uid)

    # Legacy entity unique_id prefixing only applies to single-unit accounts:
    # multi-unit accounts have unambiguous serials already, and any account that
    # passed through 0.4.0 is already prefixed (this is then a no-op).
    if len(units) == 1:
        serial_no = next(iter(units))

        @callback
        def _migrate_unique_id(registry_entry: er.RegistryEntry) -> dict | None:
            prefix = f"{serial_no}_"
            if registry_entry.unique_id.startswith(prefix):
                return None
            return {"new_unique_id": f"{prefix}{registry_entry.unique_id}"}

        await er.async_migrate_entries(hass, entry.entry_id, _migrate_unique_id)

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    entry: JablotronFuturaConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Allow deleting a device whose unit is no longer on the account."""
    coordinator = entry.runtime_data
    known = {(DOMAIN, serial) for serial in coordinator.futura.units()}
    return not (device_entry.identifiers & known)


async def async_unload_entry(hass: HomeAssistant, entry: JablotronFuturaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class FuturaCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, futura: Futura) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=5),
        )
        self.futura = futura

    async def _async_update_data(self):
        try:
            return await self.futura.sync()
        except ApiAuthError as err:
            raise ConfigEntryAuthFailed(err) from err
