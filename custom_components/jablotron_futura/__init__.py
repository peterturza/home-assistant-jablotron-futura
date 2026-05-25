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

    # Migrate legacy un-prefixed entity unique ids to the primary unit's serial.
    # Pre-0.4.0 installs only ever set up the primary (first) unit, so its legacy
    # rows belong to it; migrating them before platform setup lets the new
    # entities reuse the rows and preserve history. Rows already scoped to any
    # known unit serial are left alone, and any rename whose target already
    # exists is skipped — a prior multi-unit boot can leave both the legacy and
    # the serial-prefixed form in the registry, and renaming into the existing
    # id would raise and fail setup (#10).
    primary = coordinator.futura.primary_unit()
    registry = er.async_get(hass)
    existing_unique_ids = {
        registry_entry.unique_id
        for registry_entry in er.async_entries_for_config_entry(
            registry, entry.entry_id
        )
    }

    @callback
    def _migrate_unique_id(registry_entry: er.RegistryEntry) -> dict | None:
        if any(
            registry_entry.unique_id.startswith(f"{serial}_") for serial in units
        ):
            return None
        new_unique_id = f"{primary.serial_no}_{registry_entry.unique_id}"
        if new_unique_id in existing_unique_ids:
            return None
        return {"new_unique_id": new_unique_id}

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
