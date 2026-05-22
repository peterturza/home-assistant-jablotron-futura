# Multi-unit Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Support multiple Futura units on a single Jablotron account — one config entry per account, one Home Assistant device per unit (serial number) — with existing single-unit installs migrating cleanly.

**Architecture:** A single `FuturaCoordinator` fetches every Futura service in one poll cycle (`serviceListGet` once, then `getDevice` per service). `coordinator.data` becomes `{ serial_no: device_json }`. Each platform builds its entity set once per unit, binding entities to a specific `FuturaCentralUnit`. Entity `unique_id`s are already serial-scoped, so they need no scheme change; the config-entry `unique_id` migrates from the first unit's serial to the account login.

**Tech Stack:** Python 3.12+, Home Assistant custom integration, `pytest` + `pytest-homeassistant-custom-component`. Tests run with `/tmp/ha-futura-venv/bin/python -m pytest -q`.

---

## Important notes for the implementer

1. **This is a coordinated data-shape change.** Changing `coordinator.data` from `{"device": …}` to `{ serial: {"device": …} }` breaks every entity at once. The plan is ordered so the suite has two clean green points:
   - End of **Task 2** — `tests/test_futura.py` (tests `Futura` directly, does not load HA platforms) is green.
   - End of **Task 4** — the full integration suite is green again.
   Between Task 2 and Task 4 the integration suite is expected to be red. Do not "fix" intermediate redness by half-migrating.

2. **Device naming is intentionally left as-is (`name=DOMAIN`).** Both units' devices are named `"jablotron_futura"`, so the second unit's entity slugs get a `_2` suffix and friendly names share a prefix. Distinguishing device names would change existing users' friendly names (they derive from device name via `_attr_has_entity_name`), which is out of scope for this issue. Flagged as a possible follow-up; do **not** change device naming here.

3. **Python version:** the package uses 3.12+ syntax. Always use `/tmp/ha-futura-venv/bin/python` (3.13). Recreate per `CLAUDE.md` if missing.

---

## File structure

| File | Responsibility | Change |
|------|----------------|--------|
| `custom_components/jablotron_futura/futura.py` | API client, per-unit model, base entity classes | Rewrite `sync`/`set_*`/`Futura`; rework `FuturaEntity`/`FuturaControlEntity` for per-unit binding |
| `custom_components/jablotron_futura/__init__.py` | Coordinator, setup, migrations | Per-unit guard, config-entry unique_id migration, gated entity migration, device-removal handler |
| `custom_components/jablotron_futura/{sensor,binary_sensor,number,select,switch}.py` | Platform entities | Loop over units in `async_setup_entry`; thread `central_unit` through |
| `custom_components/jablotron_futura/config_flow.py` | Config flow | Account-login unique_id; require ≥1 unit |
| `custom_components/jablotron_futura/manifest.json` | Version | Bump `0.4.0` → `0.5.0` |
| `tests/conftest.py` | Test fixtures | Add multi-unit fixtures + per-id `getDevice` dispatch |
| `tests/test_futura.py` | New: direct `Futura` tests | Create |
| `tests/test_init.py` | Setup/migration tests | Add multi-unit + entry-unique_id-migration + device-removal tests |
| `tests/{test_sensor,test_binary_sensor,test_number,test_select}.py` | Platform tests | Add multi-unit assertions |
| `tests/test_config_flow.py` | Config-flow tests | Update unique_id/title expectations |

---

## Task 1: Multi-unit test fixtures in conftest

**Files:**
- Modify: `tests/conftest.py`

This task adds test infrastructure only; no production code changes. The default single-unit fixtures keep their current shape so the existing suite is unaffected until later tasks change production code.

- [ ] **Step 1: Add multi-unit constants and helpers**

In `tests/conftest.py`, after the existing `MOCK_DEVICE_RESPONSE` block (around line 127), add:

```python
import copy

MOCK_SERIAL_2 = "SN987654321"

MOCK_SERVICE_LIST_MULTI = {
    "data": {
        "services": [
            {
                "service-id": 12345,
                "visible": True,
                "status": "ENABLED",
                "service-type": "FUTURA2",
            },
            {
                "service-id": 67890,
                "visible": True,
                "status": "ENABLED",
                "service-type": "FUTURA2",
            },
        ]
    }
}


def make_device_response(device_id: str, serial_no: str) -> dict:
    """Clone MOCK_DEVICE_RESPONSE with a distinct id + serial number."""
    resp = copy.deepcopy(MOCK_DEVICE_RESPONSE)
    resp["device"]["id"] = device_id
    resp["device"]["details"]["serial_no"] = serial_no
    return resp


MOCK_DEVICE_RESPONSES_MULTI = {
    "12345": make_device_response("12345", MOCK_SERIAL),
    "67890": make_device_response("67890", MOCK_SERIAL_2),
}
```

- [ ] **Step 2: Teach `create_mock_session` to dispatch `getDevice` by request id**

Replace the `create_mock_session` function (lines 147-172) with:

```python
def create_mock_session(
    auth_status=200,
    service_list_response=None,
    device_response=None,
    device_responses=None,
    set_device_status=200,
):
    """Create a mock aiohttp session that simulates the Jablotron API.

    Pass ``device_responses`` (dict keyed by the string ``id`` sent in the
    getDevice body) to simulate multiple units; otherwise ``device_response``
    is returned for every getDevice call.
    """
    if service_list_response is None:
        service_list_response = MOCK_SERVICE_LIST_RESPONSE
    if device_response is None:
        device_response = MOCK_DEVICE_RESPONSE

    def mock_post(url, **kwargs):
        if "userAuthorize" in url:
            return MockResponse({}, status=auth_status)
        elif "serviceListGet" in url:
            return MockResponse(service_list_response)
        elif "getDevice" in url:
            if device_responses is not None:
                req_id = kwargs.get("json", {}).get("id")
                return MockResponse(device_responses[req_id])
            return MockResponse(device_response)
        elif "setDevice" in url:
            return MockResponse({}, status=set_device_status)
        return MockResponse({}, status=404)

    mock_session = AsyncMock()
    mock_session.post = mock_post
    return mock_session
```

- [ ] **Step 3: Add multi-unit session + setup helpers**

After `setup_integration` (end of file), add:

```python
def create_multi_unit_session():
    """Mock session returning two Futura units."""
    return create_mock_session(
        service_list_response=MOCK_SERVICE_LIST_MULTI,
        device_responses=MOCK_DEVICE_RESPONSES_MULTI,
    )


async def setup_integration_multi(hass: HomeAssistant):
    """Set up the integration with a two-unit account."""
    entry = MockConfigEntry(
        domain=DOMAIN, title=MOCK_USERNAME, data=MOCK_CONFIG, unique_id=MOCK_USERNAME
    )
    entry.add_to_hass(hass)
    session = create_multi_unit_session()
    with patch(
        "custom_components.jablotron_futura.futura.aiohttp_client.async_get_clientsession",
        return_value=session,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry
```

- [ ] **Step 4: Verify conftest imports cleanly**

Run: `/tmp/ha-futura-venv/bin/python -m pytest -q tests/test_sensor.py`
Expected: PASS (default single-unit fixtures unchanged; production code not yet touched).

- [ ] **Step 5: Commit**

```bash
git add tests/conftest.py
git commit -m "test: add multi-unit fixtures and per-id getDevice dispatch"
```

---

## Task 2: Per-unit `Futura` client and base entity classes

**Files:**
- Modify: `custom_components/jablotron_futura/futura.py`
- Test: `tests/test_futura.py` (create)

- [ ] **Step 1: Write failing tests for `Futura` multi-unit behaviour**

Create `tests/test_futura.py`:

```python
"""Direct tests for the Futura API client (no HA platform loading)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.core import HomeAssistant

from custom_components.jablotron_futura.futura import Futura
from .conftest import (
    MOCK_PASSWORD,
    MOCK_SERIAL,
    MOCK_SERIAL_2,
    MOCK_USERNAME,
    create_multi_unit_session,
)

PATCH_SESSION = (
    "custom_components.jablotron_futura.futura.aiohttp_client.async_get_clientsession"
)


async def test_sync_returns_every_unit(hass: HomeAssistant):
    session = create_multi_unit_session()
    with patch(PATCH_SESSION, return_value=session):
        futura = Futura(hass, MOCK_USERNAME, MOCK_PASSWORD)
        data = await futura.sync()

    assert set(data) == {MOCK_SERIAL, MOCK_SERIAL_2}
    assert set(futura.units()) == {MOCK_SERIAL, MOCK_SERIAL_2}
    assert data[MOCK_SERIAL]["device"]["details"]["serial_no"] == MOCK_SERIAL


async def test_primary_unit_is_first_service(hass: HomeAssistant):
    session = create_multi_unit_session()
    with patch(PATCH_SESSION, return_value=session):
        futura = Futura(hass, MOCK_USERNAME, MOCK_PASSWORD)
        await futura.sync()

    assert futura.primary_unit().serial_no == MOCK_SERIAL


async def test_set_control_targets_the_named_unit(hass: HomeAssistant):
    captured = {}
    base = create_multi_unit_session()

    def post(url, **kwargs):
        if "setDevice" in url:
            captured["json"] = kwargs["json"]
        return base.post(url, **kwargs)

    session = AsyncMock()
    session.post = post
    with patch(PATCH_SESSION, return_value=session):
        futura = Futura(hass, MOCK_USERNAME, MOCK_PASSWORD)
        await futura.sync()
        await futura.set_control(MOCK_SERIAL_2, "fan_power", 3)

    device = captured["json"]["device"]
    assert device["id"] == "67890"  # service_id of the second unit
    assert device["control"][0]["manual"] == {"fan_power": 3}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/tmp/ha-futura-venv/bin/python -m pytest -q tests/test_futura.py`
Expected: FAIL — `Futura` has no `units`/`primary_unit`; `set_control` takes 2 args not 3.

- [ ] **Step 3: Rewrite `Futura` for multiple units**

In `custom_components/jablotron_futura/futura.py`, replace the `Futura` class body (lines 46-188) with:

```python
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
```

- [ ] **Step 4: Rework the base entity classes for per-unit binding**

In the same file, replace `FuturaEntity` and `FuturaControlEntity` (lines 191-233) with:

```python
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
```

- [ ] **Step 5: Run the `Futura` tests**

Run: `/tmp/ha-futura-venv/bin/python -m pytest -q tests/test_futura.py`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add custom_components/jablotron_futura/futura.py tests/test_futura.py
git commit -m "feat: enumerate every Futura unit per account"
```

Note: the integration suite (`tests/test_sensor.py` etc.) is now red — expected until Task 4.

---

## Task 3: Coordinator, migrations, and device-removal handler

**Files:**
- Modify: `custom_components/jablotron_futura/__init__.py`

(No standalone test run here — `__init__` setup forwards to the not-yet-migrated platforms, so its tests pass only after Task 4. Verification is folded into Task 4.)

- [ ] **Step 1: Rewrite `async_setup_entry` and add the device-removal handler**

In `custom_components/jablotron_futura/__init__.py`, replace `async_setup_entry` (lines 32-61) with:

```python
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
            "Jablotron device returned no serial number; cannot scope entity unique IDs"
        )

    # Migrate the config-entry unique id from a unit serial (legacy) to the
    # account login, so all units on one account share a single entry.
    username = entry.data[CONF_USERNAME]
    if entry.unique_id != username:
        hass.config_entries.async_update_entry(entry, unique_id=username)

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
```

- [ ] **Step 2: Add the device-registry import**

In the imports block, alongside `from homeassistant.helpers import entity_registry as er` (line 12), add:

```python
from homeassistant.helpers import device_registry as dr
```

- [ ] **Step 3: Verify it imports**

Run: `/tmp/ha-futura-venv/bin/python -c "import ast; ast.parse(open('custom_components/jablotron_futura/__init__.py').read())"`
Expected: no output (syntax OK). Full test run happens in Task 4.

- [ ] **Step 4: Commit**

```bash
git add custom_components/jablotron_futura/__init__.py
git commit -m "feat: per-account coordinator with entry-unique_id migration and device removal"
```

---

## Task 4: Migrate all five platform files to per-unit entities

**Files:**
- Modify: `custom_components/jablotron_futura/sensor.py`
- Modify: `custom_components/jablotron_futura/binary_sensor.py`
- Modify: `custom_components/jablotron_futura/number.py`
- Modify: `custom_components/jablotron_futura/select.py`
- Modify: `custom_components/jablotron_futura/switch.py`

All five change the same way: `async_setup_entry` loops over `coordinator.futura.units().values()`; each entity takes a `central_unit`; data reads use `self._device`; control writes pass `self._serial`.

- [ ] **Step 1: `sensor.py`**

Replace `async_setup_entry` (lines 65-82) with:

```python
async def async_setup_entry(
    hass: HomeAssistant,
    entry: JablotronFuturaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Futura sensors."""
    coordinator = entry.runtime_data

    entities: list[SensorEntity] = []
    for unit in coordinator.futura.units().values():
        entities += [
            FuturaSummarySensorEntity(coordinator, unit, description)
            for description in SUMMARY_SENSORS
        ]
        entities += [
            FuturaPeripherySensorEntity(coordinator, unit, description)
            for description in PERIPHERY_SENSORS
        ]
    async_add_entities(entities)
```

Replace `FuturaSummarySensorEntity` (lines 85-114) with:

```python
class FuturaSummarySensorEntity(FuturaEntity, SensorEntity):
    """Futura summary sensor entity."""

    entity_description: SensorEntityDescription

    def __init__(self, coordinator, central_unit, description: SensorEntityDescription) -> None:
        super().__init__(coordinator, central_unit)
        self.entity_description = description

    @property
    def unique_id(self) -> str:
        return f"{self._serial}_{self.entity_description.key}"

    @property
    def available(self) -> bool:
        return self.entity_description.key in self._device["summary"]

    @property
    def native_value(self) -> StateType | date | datetime:
        return self._device["summary"][self.entity_description.key]

    @property
    def state_class(self) -> SensorStateClass | str | None:
        return SensorStateClass.MEASUREMENT

    @property
    def native_unit_of_measurement(self) -> str | None:
        return self._device["summary"][
            "{}_units".format(self.entity_description.key)
        ]
```

Replace `FuturaPeripherySensorEntity` (lines 117-153) with:

```python
class FuturaPeripherySensorEntity(FuturaEntity, SensorEntity):
    """Futura periphery sensor entity."""

    entity_description: SensorEntityDescription

    def __init__(self, coordinator, central_unit, description: SensorEntityDescription) -> None:
        super().__init__(coordinator, central_unit)
        self.entity_description = description

    @property
    def periphery(self) -> dict[str, Any] | None:
        peripheries = self._device["peripheries"]
        filtered = [
            p for p in peripheries if p["id"] == self.entity_description.key
        ]
        return filtered[0] if filtered else None

    @property
    def available(self) -> bool:
        return self.periphery is not None

    @property
    def unique_id(self) -> str:
        return f"{self._serial}_{self.entity_description.key}"

    @property
    def native_value(self) -> StateType | date | datetime:
        value = self.periphery["extended_properties"]["value"]
        return round(value, 1) if value else None

    @property
    def state_class(self) -> SensorStateClass | str | None:
        return SensorStateClass.MEASUREMENT

    @property
    def native_unit_of_measurement(self) -> str | None:
        return self.periphery["extended_properties"]["units"]
```

- [ ] **Step 2: `binary_sensor.py`**

Replace `async_setup_entry` (lines 34-47) with:

```python
async def async_setup_entry(
    hass: HomeAssistant,
    entry: JablotronFuturaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Futura binary sensors."""
    coordinator = entry.runtime_data

    entities = []
    for unit in coordinator.futura.units().values():
        entities += [
            FuturaSummaryBinarySensorEntity(coordinator, unit, description)
            for description in BINARY_SENSORS
        ]
    async_add_entities(entities)
```

Replace `FuturaSummaryBinarySensorEntity` (lines 50-69) with:

```python
class FuturaSummaryBinarySensorEntity(FuturaEntity, BinarySensorEntity):
    """Futura summary binary sensor entity."""

    entity_description: BinarySensorEntityDescription

    def __init__(self, coordinator, central_unit, description: BinarySensorEntityDescription) -> None:
        super().__init__(coordinator, central_unit)
        self.entity_description = description

    @property
    def unique_id(self) -> str:
        return f"{self._serial}_{self.entity_description.key}"

    @property
    def available(self) -> bool:
        return self.entity_description.key in self._device["summary"]

    @property
    def is_on(self) -> bool:
        return self._device["summary"][self.entity_description.key]
```

- [ ] **Step 3: `number.py`**

Replace `async_setup_entry` (lines 16-28) with:

```python
async def async_setup_entry(
    hass: HomeAssistant,
    entry: JablotronFuturaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Futura number entities."""
    coordinator = entry.runtime_data

    async_add_entities(
        FuturaControlTemperatureEntity(coordinator, unit)
        for unit in coordinator.futura.units().values()
    )
```

Replace `FuturaControlTemperatureEntity.__init__` and `async_set_native_value` (lines 36-37 and 59-61) so the class reads:

```python
class FuturaControlTemperatureEntity(FuturaControlEntity, NumberEntity):
    """Temperature control entity."""

    _attr_name = "Temperature"

    def __init__(self, coordinator, central_unit) -> None:
        super().__init__(
            "control_temperature", NumberDeviceClass.TEMPERATURE, coordinator, central_unit
        )

    @property
    def native_value(self) -> float | None:
        return self.data()["extended_properties"]["value"]

    @property
    def native_min_value(self) -> float:
        return self.data()["extended_properties"]["min"]

    @property
    def native_max_value(self) -> float:
        return self.data()["extended_properties"]["max"]

    @property
    def native_step(self) -> float:
        return self.data()["extended_properties"]["step"]

    @property
    def native_unit_of_measurement(self) -> str | None:
        return self.data()["extended_properties"]["units"]

    async def async_set_native_value(self, value: float) -> None:
        await self._futura.set_control(self._serial, "temperature", value)
        await self.coordinator.async_refresh()
```

- [ ] **Step 4: `select.py`**

Replace `async_setup_entry` (lines 16-29) with:

```python
async def async_setup_entry(
    hass: HomeAssistant,
    entry: JablotronFuturaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Futura select entities."""
    coordinator = entry.runtime_data

    entities = []
    for unit in coordinator.futura.units().values():
        entities.append(FuturaControlFanPowerEntity(coordinator, unit))
        entities.append(FuturaControlHumidityEntity(coordinator, unit))
    async_add_entities(entities)
```

Replace `FuturaControlFanPowerEntity` (lines 32-71) with:

```python
class FuturaControlFanPowerEntity(FuturaControlEntity, SelectEntity):
    """Fan power control entity."""

    _attr_name = "Fan Power"

    def __init__(self, coordinator, central_unit) -> None:
        super().__init__("control_fan_power", None, coordinator, central_unit)

    @property
    def options(self) -> list[str]:
        data = self.data()
        device = self._device
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
        await self._futura.set_control(
            self._serial, "fan_power", self.options.index(option)
        )
        await self.coordinator.async_refresh()
```

Replace `FuturaControlHumidityEntity.__init__` and `async_select_option` so the class reads:

```python
class FuturaControlHumidityEntity(FuturaControlEntity, SelectEntity):
    """Humidity control entity."""

    _attr_name = "Humidity"

    def __init__(self, coordinator, central_unit) -> None:
        super().__init__("control_humidity", None, coordinator, central_unit)

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
        await self._futura.set_control(self._serial, "humidity", value)
        await self.coordinator.async_refresh()
```

- [ ] **Step 5: `switch.py`**

Replace `async_setup_entry` (lines 23-28) with:

```python
async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    entities = []
    for unit in coordinator.futura.units().values():
        entities += [
            FuturaSettingsSwitchEntity(idx, name, device_class, coordinator, unit)
            for idx, name, device_class in SWITCHES
        ]
    async_add_entities(entities)
```

Replace `FuturaSettingsSwitchEntity` (lines 36-75) with:

```python
class FuturaSettingsSwitchEntity(FuturaEntity, SwitchEntity):
    def __init__(self, idx, name, device_class, coordinator, central_unit):
        super().__init__(coordinator, central_unit)
        self._idx = idx
        self._attr_name = name
        self._device_class = device_class

    @property
    def unique_id(self) -> str:
        return f"{self._serial}_{self._idx}"

    @property
    def value(self) -> str:
        return self._device["settings"]["extended_properties"][self._idx]

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
            self._serial, self._idx, FuturaEnabledEnum.ENABLED
        )
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs):
        await self._futura.set_setting_extended_property(
            self._serial, self._idx, FuturaEnabledEnum.DISABLED
        )
        await self.coordinator.async_refresh()
```

- [ ] **Step 6: Run the existing single-unit suite (default fixtures still single-unit)**

Run: `/tmp/ha-futura-venv/bin/python -m pytest -q tests/test_sensor.py tests/test_binary_sensor.py tests/test_number.py tests/test_select.py tests/test_init.py`
Expected: PASS — single-unit behaviour preserved with the new data shape and per-unit entities. (`test_init` migration tests still pass: single unit ⇒ legacy prefixing runs.)

- [ ] **Step 7: Commit**

```bash
git add custom_components/jablotron_futura/{sensor,binary_sensor,number,select,switch}.py
git commit -m "feat: build one entity set per Futura unit"
```

---

## Task 5: Multi-unit integration tests

**Files:**
- Modify: `tests/test_init.py`
- Modify: `tests/test_sensor.py`

- [ ] **Step 1: Write multi-unit + migration tests in `test_init.py`**

Append to `tests/test_init.py`:

```python
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

    current = dr.DeviceEntry(identifiers={(DOMAIN, MOCK_SERIAL)})
    stale = dr.DeviceEntry(identifiers={(DOMAIN, "SN000000000")})

    assert await async_remove_config_entry_device(hass, entry, current) is False
    assert await async_remove_config_entry_device(hass, entry, stale) is True
```

- [ ] **Step 2: Add a multi-unit state assertion in `test_sensor.py`**

Append to `tests/test_sensor.py`:

```python
async def test_sensors_created_for_both_units(hass: HomeAssistant):
    """A two-unit account exposes a filter_health sensor for each unit."""
    from homeassistant.helpers import entity_registry as er
    from .conftest import MOCK_SERIAL, MOCK_SERIAL_2, setup_integration_multi

    entry = await setup_integration_multi(hass)
    registry = er.async_get(hass)

    by_uid = {
        e.unique_id: e.entity_id
        for e in er.async_entries_for_config_entry(registry, entry.entry_id)
    }
    for serial in (MOCK_SERIAL, MOCK_SERIAL_2):
        entity_id = by_uid[f"{serial}_filter_health"]
        assert hass.states.get(entity_id).state == "85"
```

- [ ] **Step 3: Run the new tests**

Run: `/tmp/ha-futura-venv/bin/python -m pytest -q tests/test_init.py tests/test_sensor.py`
Expected: PASS (existing + new).

- [ ] **Step 4: Commit**

```bash
git add tests/test_init.py tests/test_sensor.py
git commit -m "test: cover multi-unit setup, entry-id migration, and device removal"
```

---

## Task 6: Account-based config flow

**Files:**
- Modify: `custom_components/jablotron_futura/config_flow.py`
- Modify: `tests/test_config_flow.py`

- [ ] **Step 1: Update the config-flow tests to expect account-based identity**

In `tests/test_config_flow.py`:

In `test_config_flow_success`, replace lines 41-43:

```python
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "test@example.com"
        assert result["data"] == MOCK_CONFIG
        assert result["result"].unique_id == "test@example.com"
```

Rename `test_config_flow_aborts_on_duplicate_serial` to `test_config_flow_aborts_on_duplicate_account` (the body is unchanged — same credentials now yield the same account unique id):

```python
async def test_config_flow_aborts_on_duplicate_account(hass: HomeAssistant):
    """Adding the same Jablotron account twice must abort with 'already_configured'."""
```

- [ ] **Step 2: Run to verify failure**

Run: `/tmp/ha-futura-venv/bin/python -m pytest -q tests/test_config_flow.py::test_config_flow_success`
Expected: FAIL — title/unique_id are still the serial.

- [ ] **Step 3: Update `config_flow.py`**

Replace `validate_input` (lines 27-39) with:

```python
async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    futura = Futura(hass, data[CONF_USERNAME], data[CONF_PASSWORD])
    await futura.sync()
    if not futura.units():
        raise ServiceNotFoundError

    # The account login uniquely identifies the entry; a single account may
    # carry several Futura units, each modelled as its own device.
    return {"title": data[CONF_USERNAME]}
```

Replace the success branch (lines 69-72) with:

```python
        else:
            await self.async_set_unique_id(user_input[CONF_USERNAME])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=info["title"], data=user_input)
```

- [ ] **Step 4: Run config-flow tests**

Run: `/tmp/ha-futura-venv/bin/python -m pytest -q tests/test_config_flow.py`
Expected: PASS (all, including the renamed duplicate-account test).

- [ ] **Step 5: Commit**

```bash
git add custom_components/jablotron_futura/config_flow.py tests/test_config_flow.py
git commit -m "feat: key config entry on account login, not unit serial"
```

---

## Task 7: Version bump and full-suite verification

**Files:**
- Modify: `custom_components/jablotron_futura/manifest.json`

- [ ] **Step 1: Bump the manifest version**

In `custom_components/jablotron_futura/manifest.json`, change:

```json
    "version": "0.4.0"
```

to:

```json
    "version": "0.5.0"
```

- [ ] **Step 2: Run the entire suite**

Run: `/tmp/ha-futura-venv/bin/python -m pytest -q`
Expected: PASS — all tests across all files green.

- [ ] **Step 3: Commit**

```bash
git add custom_components/jablotron_futura/manifest.json
git commit -m "chore: bump version to 0.5.0"
```

---

## Done-when

- A two-unit account creates two HA devices, each with its full entity set; entity `unique_id`s are serial-scoped and collision-free.
- An existing single-unit entry (unique_id = serial) migrates to unique_id = account login on setup, with entities/history intact.
- Adding the same account twice aborts with `already_configured`.
- A device for a unit no longer on the account can be deleted from the UI.
- `/tmp/ha-futura-venv/bin/python -m pytest -q` is green.
- `manifest.json` version is `0.5.0`.

## Follow-ups (out of scope)

- Distinguish device names per unit (currently both named `jablotron_futura`, so the second unit's entity slugs get a `_2` suffix). Requires deciding how to name without breaking existing friendly names.
- Live add/remove of units on the poll cycle (currently requires a reload).
- Manual verification against a real HA install per `CLAUDE.md` (auth caching, duplicate-account abort, entity migration, friendly names) before requesting re-review.
