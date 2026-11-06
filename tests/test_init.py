"""Tests for the Jablotron Futura integration setup."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.jablotron_futura.const import DOMAIN
from .conftest import MockResponse, create_mock_session, setup_integration


async def test_setup_entry(hass: HomeAssistant):
    """Test successful setup of config entry."""
    entry = await setup_integration(hass)

    assert entry.state == ConfigEntryState.LOADED
    assert entry.runtime_data is not None


async def test_setup_entry_auth_failure(hass: HomeAssistant):
    """Test setup fails with auth error."""
    mock_session = create_mock_session(auth_status=401)
    entry = await setup_integration(hass, mock_session)

    assert entry.state == ConfigEntryState.SETUP_ERROR


async def test_unload_entry(hass: HomeAssistant):
    """Test unloading a config entry."""
    entry = await setup_integration(hass)

    assert entry.state == ConfigEntryState.LOADED

    with patch(
        "custom_components.jablotron_futura.futura.aiohttp_client.async_get_clientsession",
    ):
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.NOT_LOADED


async def test_authorize_called_once_across_multiple_refreshes(hass: HomeAssistant):
    """Two coordinator refreshes should authorize the session only once."""
    auth_calls = 0
    real_post = create_mock_session().post  # reuse the default mock router

    def counting_post(url, **kwargs):
        nonlocal auth_calls
        if "userAuthorize" in url:
            auth_calls += 1
        return real_post(url, **kwargs)

    mock_session = AsyncMock()
    mock_session.post = counting_post

    entry = await setup_integration(hass, mock_session)
    coordinator = entry.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert auth_calls == 1, f"expected 1 authorize call, got {auth_calls}"


async def test_session_re_authorizes_after_401(hass: HomeAssistant):
    """A 401 from a non-auth call must trigger one fresh authorize + retry."""
    state = {"auth_calls": 0, "device_calls": 0}
    default_session = create_mock_session()

    def post(url, **kwargs):
        if "userAuthorize" in url:
            state["auth_calls"] += 1
            return default_session.post(url, **kwargs)
        if "getDevice" in url:
            state["device_calls"] += 1
            # First call after the initial sync returns 401, then 200.
            if state["device_calls"] == 2:
                return MockResponse({}, status=401)
        return default_session.post(url, **kwargs)

    mock_session = AsyncMock()
    mock_session.post = post

    entry = await setup_integration(hass, mock_session)
    coordinator = entry.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Initial setup = 1 authorize. Refresh hits 401 on getDevice, re-auths
    # once, retries — so 2 total authorize calls expected.
    assert state["auth_calls"] == 2
    assert coordinator.last_update_success is True
    assert coordinator.data is not None


async def test_unique_id_migration_rewrites_legacy_keys(hass: HomeAssistant):
    """Pre-existing entity registry rows must be migrated to serial-scoped unique_ids."""
    from homeassistant.helpers import entity_registry as er
    from .conftest import MOCK_SERIAL, create_mock_entry, create_mock_session

    entry = create_mock_entry()
    entry.add_to_hass(hass)
    registry = er.async_get(hass)

    # Seed a pre-migration registry row with the legacy unique_id.
    legacy = registry.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id="filter_health",
        config_entry=entry,
    )
    assert legacy.unique_id == "filter_health"

    mock_session = create_mock_session()
    with patch(
        "custom_components.jablotron_futura.futura.aiohttp_client.async_get_clientsession",
        return_value=mock_session,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    migrated = registry.async_get(legacy.entity_id)
    assert migrated.unique_id == f"{MOCK_SERIAL}_filter_health"


async def test_unique_id_migration_skips_already_prefixed(hass: HomeAssistant):
    """An already serial-prefixed unique_id must be left untouched (idempotent)."""
    from homeassistant.helpers import entity_registry as er
    from .conftest import MOCK_SERIAL, create_mock_entry, create_mock_session

    entry = create_mock_entry()
    entry.add_to_hass(hass)
    registry = er.async_get(hass)

    already_prefixed = f"{MOCK_SERIAL}_filter_health"
    existing = registry.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id=already_prefixed,
        config_entry=entry,
    )

    mock_session = create_mock_session()
    with patch(
        "custom_components.jablotron_futura.futura.aiohttp_client.async_get_clientsession",
        return_value=mock_session,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    after = registry.async_get(existing.entity_id)
    assert after.unique_id == already_prefixed  # no double prefix


async def test_unique_id_migration_isolates_other_entries(hass: HomeAssistant):
    """The migration must not touch registry rows owned by another config entry."""
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from .conftest import create_mock_entry, create_mock_session

    other_entry = MockConfigEntry(domain="other_domain", title="other", data={})
    other_entry.add_to_hass(hass)
    registry = er.async_get(hass)
    foreign = registry.async_get_or_create(
        domain="sensor",
        platform="other_domain",
        unique_id="filter_health",
        config_entry=other_entry,
    )

    entry = create_mock_entry()
    entry.add_to_hass(hass)

    mock_session = create_mock_session()
    with patch(
        "custom_components.jablotron_futura.futura.aiohttp_client.async_get_clientsession",
        return_value=mock_session,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    after = registry.async_get(foreign.entity_id)
    assert after.unique_id == "filter_health"  # untouched


async def test_unique_id_migration_skips_collision(hass: HomeAssistant):
    """If the serial-prefixed target already exists, the legacy row is left as-is.

    Regression for #10: a prior multi-unit boot can leave both a legacy
    un-prefixed entity and its serial-prefixed counterpart in the registry.
    Migrating the legacy one would collide and previously crashed setup with
    `ValueError: Unique id '..._filter_health' is already in use`.
    """
    from homeassistant.helpers import entity_registry as er
    from .conftest import MOCK_SERIAL, create_mock_entry, create_mock_session

    entry = create_mock_entry()
    entry.add_to_hass(hass)
    registry = er.async_get(hass)

    legacy = registry.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id="filter_health",
        config_entry=entry,
    )
    prefixed = registry.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id=f"{MOCK_SERIAL}_filter_health",
        config_entry=entry,
    )

    mock_session = create_mock_session()
    with patch(
        "custom_components.jablotron_futura.futura.aiohttp_client.async_get_clientsession",
        return_value=mock_session,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Setup must not crash on the collision.
    assert entry.state is ConfigEntryState.LOADED
    # The legacy row is left untouched; the prefixed row keeps its id.
    assert registry.async_get(legacy.entity_id).unique_id == "filter_health"
    assert (
        registry.async_get(prefixed.entity_id).unique_id
        == f"{MOCK_SERIAL}_filter_health"
    )


async def test_unique_id_migration_runs_for_multi_unit_legacy(hass: HomeAssistant):
    """Legacy un-prefixed rows migrate to the primary unit's serial even with multiple units.

    Pre-0.4.0 installs only ever had one (the primary) unit, so legacy entity
    rows belong to it. Migrating them before platform setup lets the new
    primary-unit entities reuse the rows and preserve history.
    """
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from .conftest import (
        MOCK_CONFIG,
        MOCK_SERIAL,
        MOCK_USERNAME,
        create_multi_unit_session,
    )

    entry = MockConfigEntry(
        domain=DOMAIN, title=MOCK_USERNAME, data=MOCK_CONFIG, unique_id=MOCK_USERNAME
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)

    legacy = registry.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id="filter_health",
        config_entry=entry,
    )

    with patch(
        "custom_components.jablotron_futura.futura.aiohttp_client.async_get_clientsession",
        return_value=create_multi_unit_session(),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Primary unit is the first service (MOCK_SERIAL); legacy row migrated to it.
    assert registry.async_get(legacy.entity_id).unique_id == f"{MOCK_SERIAL}_filter_health"


async def test_two_devices_registered_for_multi_unit_account(hass: HomeAssistant):
    """Both units must appear as distinct devices in the registry."""
    from homeassistant.helpers import device_registry as dr
    from .conftest import MOCK_SERIAL, MOCK_SERIAL_2, setup_integration_multi

    await setup_integration_multi(hass)
    registry = dr.async_get(hass)

    assert registry.async_get_device(identifiers={(DOMAIN, MOCK_SERIAL)}) is not None
    assert registry.async_get_device(identifiers={(DOMAIN, MOCK_SERIAL_2)}) is not None


async def test_entities_created_per_unit(hass: HomeAssistant):
    """Each unit gets its own serial-scoped entity in the registry."""
    from homeassistant.helpers import entity_registry as er
    from .conftest import MOCK_SERIAL, MOCK_SERIAL_2, setup_integration_multi

    entry = await setup_integration_multi(hass)
    registry = er.async_get(hass)

    ids = {
        e.unique_id
        for e in er.async_entries_for_config_entry(registry, entry.entry_id)
    }
    assert f"{MOCK_SERIAL}_filter_health" in ids
    assert f"{MOCK_SERIAL_2}_filter_health" in ids


async def test_config_entry_unique_id_migrates_to_account(hass: HomeAssistant):
    """An entry keyed on a unit serial must migrate to the account login."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from .conftest import (
        MOCK_CONFIG,
        MOCK_SERIAL,
        MOCK_USERNAME,
        create_mock_session,
    )

    entry = MockConfigEntry(
        domain=DOMAIN, title="Futura 2", data=MOCK_CONFIG, unique_id=MOCK_SERIAL
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.jablotron_futura.futura.aiohttp_client.async_get_clientsession",
        return_value=create_mock_session(),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.unique_id == MOCK_USERNAME


async def test_remove_config_entry_device(hass: HomeAssistant):
    """Devices for absent units can be removed; current units cannot."""
    from homeassistant.helpers import device_registry as dr
    from custom_components.jablotron_futura import async_remove_config_entry_device
    from .conftest import MOCK_SERIAL, setup_integration_multi

    entry = await setup_integration_multi(hass)
    registry = dr.async_get(hass)

    current = registry.async_get_device(identifiers={(DOMAIN, MOCK_SERIAL)})
    assert current is not None
    stale = dr.DeviceEntry(identifiers={(DOMAIN, "SN000000000")})

    assert await async_remove_config_entry_device(hass, entry, current) is False
    assert await async_remove_config_entry_device(hass, entry, stale) is True


async def test_device_versions_are_strings_when_api_returns_numbers(hass: HomeAssistant):
    """Numeric hw_revision/fw_version from the API must reach the device registry as str (#14)."""
    from homeassistant.helpers import device_registry as dr
    from .conftest import MOCK_DEVICE_RESPONSE, MOCK_SERIAL
    import copy

    device_response = copy.deepcopy(MOCK_DEVICE_RESPONSE)
    device_response["device"]["details"]["hw_revision"] = 3
    device_response["device"]["details"]["fw_version"] = 125

    await setup_integration(hass, create_mock_session(device_response=device_response))
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, MOCK_SERIAL)})

    assert device is not None
    assert device.hw_version == "3"
    assert device.sw_version == "125"


async def test_device_versions_stay_none_when_api_returns_null(hass: HomeAssistant):
    """A null hw_revision/fw_version must stay None, not become the string "None" (#14)."""
    from homeassistant.helpers import device_registry as dr
    from .conftest import MOCK_DEVICE_RESPONSE, MOCK_SERIAL
    import copy

    device_response = copy.deepcopy(MOCK_DEVICE_RESPONSE)
    device_response["device"]["details"]["hw_revision"] = None
    device_response["device"]["details"]["fw_version"] = None

    await setup_integration(hass, create_mock_session(device_response=device_response))
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, MOCK_SERIAL)})

    assert device is not None
    assert device.hw_version is None
    assert device.sw_version is None
