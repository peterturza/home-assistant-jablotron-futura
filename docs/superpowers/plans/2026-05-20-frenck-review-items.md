# Frenck Review Items Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Address the four non-blocking heads-up items from frenck's review on hacs/default#6509 (pullrequestreview-4308155345): cache the auth session token, prevent duplicate config entries via `async_set_unique_id`, scope entity `unique_id`s by device serial (with registry migration), and switch to `has_entity_name` for friendly entity names.

**Architecture:** Four small, focused changes inside `custom_components/jablotron_futura/`. Task 1 mutates `Futura` so credentials are only re-sent on 401. Task 2 sets the config-entry unique id from the device serial. Task 3 prefixes all entity `unique_id`s with the serial and migrates the entity registry. Task 4 enables `_attr_has_entity_name = True` and sources display names from `EntityDescription.name` / `_attr_name`. All work happens on a feature branch off `master` and is delivered as a single pull request against `master` (per CLAUDE.md: never push directly to master). The version bump + GitHub release that backs HACS's view of `0.4.0` happens **after** PR merge as a follow-up; this plan stops at the PR.

**Tech Stack:** Home Assistant custom component (Python 3.12+), `aiohttp`, `homeassistant.helpers.update_coordinator.DataUpdateCoordinator`, `homeassistant.helpers.entity_registry.async_migrate_entries`, `pytest-homeassistant-custom-component`.

**Out of scope:** Backfilling `unique_id` on an existing config entry that was created without one (frenck's review only requires the prevention going forward). Touching anything outside `custom_components/jablotron_futura/` or `tests/`.

**Testing:** Run the suite locally in a 3.13 venv (the repo uses 3.12+ `type` syntax — system 3.11 fails to import):

```bash
/tmp/ha-futura-venv/bin/python -m pytest -q
```

The venv was created in the previous session at `/tmp/ha-futura-venv` with `pip install -r requirements_test.txt`. If it's gone, recreate it:

```bash
python3.13 -m venv /tmp/ha-futura-venv
/tmp/ha-futura-venv/bin/pip install -q -r requirements_test.txt
```

Baseline before starting: 14 tests pass on commit `c8db750`.

**Real-HA smoke test:** Task 5 runs the integration in the sibling `homeassistant-core` devcontainer against a live Jablotron unit. Setup instructions and per-task verification checklist live in `CLAUDE.md` ("Testing Against a Real Home Assistant Installation" → "Path B"). `CLAUDE.md` exists in the working tree but is intentionally **not committed** and must not be added to any task commit below — the user is keeping it local for now.

---

## Task 0: Create Feature Branch

**Why:** CLAUDE.md forbids pushing directly to `master`. All work below commits onto a dedicated branch, which is opened as a PR in Task 6.

- [ ] **Step 1: Confirm clean working tree on master**

```bash
git status
git rev-parse --abbrev-ref HEAD
```

Expected: working tree clean, on `master`.

- [ ] **Step 2: Pull latest master**

```bash
git fetch origin
git checkout master
git pull --ff-only origin master
```

- [ ] **Step 3: Cut the feature branch**

```bash
git checkout -b frenck-review-followups
```

All Task 1–4 commits land here. Do not push yet.

---

## File Structure

Files touched, grouped by responsibility:

- `custom_components/jablotron_futura/futura.py`
  - `Futura` class — Task 1 adds `_authenticated` flag + 401 retry wrapper.
  - `FuturaEntity` base — Task 3 stores the serial; Task 4 sets `_attr_has_entity_name = True` and drops the `name` property. `FuturaControlEntity.unique_id` is rewritten in Task 3.
- `custom_components/jablotron_futura/config_flow.py`
  - Task 2 returns the serial from `validate_input` and calls `async_set_unique_id` + `_abort_if_unique_id_configured`.
- `custom_components/jablotron_futura/__init__.py`
  - Task 3 adds an `async_migrate_entries` block inside `async_setup_entry` to rewrite existing entity registry unique_ids on first launch of the new version.
- `custom_components/jablotron_futura/sensor.py` — Task 3 changes `unique_id` to include the serial.
- `custom_components/jablotron_futura/binary_sensor.py` — Task 3 same as sensor.
- `custom_components/jablotron_futura/switch.py` — Task 3 unique_id; Task 4 adds `_attr_name` from a constructor-supplied display name.
- `custom_components/jablotron_futura/number.py` — Task 3 unique_id; Task 4 passes a display name into `FuturaControlEntity.__init__`.
- `custom_components/jablotron_futura/select.py` — Task 3 unique_id; Task 4 display name.
- `custom_components/jablotron_futura/manifest.json` — final task bumps version to `0.4.0`.
- `CHANGELOG.md` — final task adds `0.4.0` entry.
- `tests/conftest.py` — Task 3 unique_id assertions may reference `MOCK_SERIAL`; expose it as a module-level constant if not already.
- `tests/test_config_flow.py` — Task 2 adds a duplicate-entry test.
- `tests/test_init.py` — Task 1 adds a re-auth gating test; Task 3 adds a migration test.
- `tests/test_sensor.py` / `test_binary_sensor.py` / `test_number.py` / `test_select.py` — Task 3 updates expected `unique_id`s where asserted; Task 4 updates expected entity_ids if `has_entity_name` changes them.

---

## Task 1: Cache Authentication, Re-auth Only on 401

**Why:** `Futura.sync()`, `Futura.set_control()`, and `Futura.set_setting_extended_property()` each call `self.authorize()` unconditionally, which POSTs the user's cleartext credentials to `/userAuthorize.json` on every 5-minute coordinator refresh and every entity command. The aiohttp session's cookie jar already carries the Jablotron session after the first authorize, so subsequent calls only need to re-auth when the server actually rejects the existing cookie (401/403).

**Files:**
- Modify: `custom_components/jablotron_futura/futura.py:46-176`
- Test: `tests/test_init.py` (new test added at bottom)

- [ ] **Step 1: Add the failing test for auth caching**

Append to `tests/test_init.py`:

```python
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
```

`AsyncMock` and `setup_integration`/`create_mock_session` already exist in `tests/conftest.py`; add the import if missing:

```python
from unittest.mock import AsyncMock
from .conftest import create_mock_session, setup_integration
```

- [ ] **Step 2: Run the test and watch it fail**

```bash
/tmp/ha-futura-venv/bin/python -m pytest tests/test_init.py::test_authorize_called_once_across_multiple_refreshes -v
```

Expected: FAIL with `assert auth_calls == 1` reporting `2` (initial setup + one refresh both authorize today).

- [ ] **Step 3: Add the failing test for 401 retry**

Append to `tests/test_init.py`:

```python
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
```

Add `from .conftest import MockResponse` if missing.

- [ ] **Step 4: Run both new tests, confirm they fail**

```bash
/tmp/ha-futura-venv/bin/python -m pytest tests/test_init.py -v -k "authorize"
```

Expected: both fail.

- [ ] **Step 5: Implement the cached auth + retry**

Edit `custom_components/jablotron_futura/futura.py`. Replace the `__init__` and `authorize` of `Futura` and add a `_post_with_reauth` helper. Rewrite `sync`, `set_control`, `set_setting_extended_property` to use it:

```python
class Futura:
    def __init__(self, hass: core.HomeAssistant, username: str, password: str) -> None:
        self._hass: core.HomeAssistant = hass
        self._username: str = username
        self._password: str = password
        self._central_unit: FuturaCentralUnit | None = None
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
        if not self._authenticated:
            await self.authorize()

    async def _post(self, url: str, json: dict, headers: dict):
        """POST with one transparent re-auth on 401/403. Returns parsed JSON or raises."""
        await self._ensure_authorized()
        try:
            async with self._session.post(url, json=json, headers=headers) as result:
                if result.status in (401, 403):
                    # Session cookie expired — invalidate and retry once.
                    self._authenticated = False
                    await self._ensure_authorized()
                    async with self._session.post(url, json=json, headers=headers) as retry:
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
```

Then rewrite `sync` to consume `_post`. Keep behaviour identical otherwise:

```python
    async def sync(self):
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
        service = futura_services[0]

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
        self._central_unit = FuturaCentralUnit(
            service_id=device["id"],
            model=device["type"],
            hw_version=device["details"]["hw_revision"],
            fw_version=device["details"]["fw_version"],
            serial_no=device["details"]["serial_no"],
            room_id=device["rooms"][0]["id"],
        )
        return device_json
```

Rewrite `set_control` and `set_setting_extended_property` the same way — they currently ignore the response, so just call `_post` and discard the return:

```python
    async def set_control(self, control, value) -> None:
        await self._post(
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
        )

    async def set_setting_extended_property(self, prop_name: str, prop_value) -> None:
        await self._post(
            "{}/setDevice.json".format(JABLOTRON_API),
            json={
                "device": {
                    "type": JABLOTRON_FUTURA_NAMESPACE,
                    "settings": {"extended_properties": {prop_name: prop_value}},
                    "id": self._central_unit.service_id,
                },
                "system": "IOS",
            },
            headers=JABLOTRON_API_DEFAULT_HEADERS
            | {JABLOTRON_FUTURA_NAMESPACE_KEY: JABLOTRON_FUTURA_NAMESPACE},
        )
```

- [ ] **Step 6: Run both new tests, confirm pass**

```bash
/tmp/ha-futura-venv/bin/python -m pytest tests/test_init.py -v -k "authorize"
```

Expected: both pass.

- [ ] **Step 7: Run the full suite, confirm no regressions**

```bash
/tmp/ha-futura-venv/bin/python -m pytest -q
```

Expected: 16 passed (14 baseline + 2 new).

- [ ] **Step 8: Commit**

```bash
git add custom_components/jablotron_futura/futura.py tests/test_init.py
git commit -m "feat(auth): cache session, re-auth only on 401

Track an _authenticated flag and gate authorize() behind it so the
Jablotron cleartext credentials are no longer re-POSTed on every
coordinator refresh and every command. Subsequent calls reuse the
aiohttp cookie jar; a 401/403 on any non-auth endpoint invalidates
the flag, re-authorizes once, and retries the original call.

Addresses frenck/hacs/default#6509 review item 1."
```

---

## Task 2: Set Config-Entry Unique Id from Device Serial

**Why:** `config_flow.py` never calls `async_set_unique_id`, so a user can add the same Jablotron account twice and end up with two coordinators polling the same device every 5 minutes. The device serial number (`central_unit.serial_no`) is a stable, account-independent unique id.

**Files:**
- Modify: `custom_components/jablotron_futura/config_flow.py:27-74`
- Test: `tests/test_config_flow.py` (new test added at bottom)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_config_flow.py`:

```python
async def test_config_flow_aborts_on_duplicate_serial(hass: HomeAssistant):
    """Adding the same Jablotron account twice must abort with 'already_configured'."""
    mock_session = create_mock_session()

    with patch(
        "custom_components.jablotron_futura.futura.aiohttp_client.async_get_clientsession",
        return_value=mock_session,
    ):
        # First entry succeeds.
        first = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        first = await hass.config_entries.flow.async_configure(first["flow_id"], MOCK_CONFIG)
        assert first["type"] == FlowResultType.CREATE_ENTRY

        # Second attempt with the same credentials -> same serial -> abort.
        second = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        second = await hass.config_entries.flow.async_configure(second["flow_id"], MOCK_CONFIG)
        assert second["type"] == FlowResultType.ABORT
        assert second["reason"] == "already_configured"
```

- [ ] **Step 2: Run the test, confirm it fails**

```bash
/tmp/ha-futura-venv/bin/python -m pytest tests/test_config_flow.py::test_config_flow_aborts_on_duplicate_serial -v
```

Expected: FAIL — second flow produces `CREATE_ENTRY` (no abort) because no unique id is set.

- [ ] **Step 3: Implement the unique-id check**

Edit `custom_components/jablotron_futura/config_flow.py`:

Change `validate_input` to also return the serial:

```python
async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    futura = Futura(hass, data[CONF_USERNAME], data[CONF_PASSWORD])
    await futura.sync()
    central_unit = futura.central_unit()
    if not central_unit:
        raise ServiceNotFoundError

    return {"title": central_unit.model, "serial_no": central_unit.serial_no}
```

In `async_step_user`, set the unique id before creating the entry:

```python
        try:
            info = await validate_input(self.hass, user_input)
        except ApiAuthError as ex:
            _LOGGER.exception(ex)
            errors["base"] = "invalid_auth"
        except ServiceNotFoundError as ex:
            _LOGGER.exception(ex)
            errors["base"] = "service_not_found"
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.exception(ex)
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(info["serial_no"])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=info["title"], data=user_input)
```

- [ ] **Step 4: Run the new test, confirm pass**

```bash
/tmp/ha-futura-venv/bin/python -m pytest tests/test_config_flow.py::test_config_flow_aborts_on_duplicate_serial -v
```

Expected: PASS.

- [ ] **Step 5: Run the full suite**

```bash
/tmp/ha-futura-venv/bin/python -m pytest -q
```

Expected: 17 passed.

- [ ] **Step 6: Commit**

```bash
git add custom_components/jablotron_futura/config_flow.py tests/test_config_flow.py
git commit -m "feat(config): set config-entry unique id from device serial

Call async_set_unique_id(serial_no) + _abort_if_unique_id_configured()
so the same Jablotron account cannot be added twice.

Addresses frenck/hacs/default#6509 review item 2."
```

---

## Task 3: Scope Entity unique_ids by Device Serial (with Migration)

**Why:** Every entity's `unique_id` is currently the raw description key (e.g. `\"filter_health\"`) or control idx (e.g. `\"control_temperature\"`). Once Task 2 enables multiple-entry abort it's still possible to have legacy duplicate entries from before the upgrade, and any future multi-device support would collide. Prefix with the device serial.

A registry migration rewrites existing entries so users keep their entity history (history graphs, automations referencing `entity_id` are unaffected — `entity_id` is independent of `unique_id`, but the registry row must still match for an entity to be reused instead of duplicated).

**Files:**
- Modify: `custom_components/jablotron_futura/futura.py` — `FuturaControlEntity.unique_id` (line 224-225)
- Modify: `custom_components/jablotron_futura/sensor.py` — both `unique_id` properties
- Modify: `custom_components/jablotron_futura/binary_sensor.py` — `unique_id`
- Modify: `custom_components/jablotron_futura/switch.py` — `unique_id`
- Modify: `custom_components/jablotron_futura/__init__.py` — add `async_migrate_entries` call in `async_setup_entry`
- Test: `tests/test_sensor.py`, `tests/test_binary_sensor.py`, `tests/test_number.py`, `tests/test_select.py`, `tests/test_init.py`

- [ ] **Step 1: Expose MOCK_SERIAL in conftest**

In `tests/conftest.py`, add a module-level constant near `MOCK_USERNAME`:

```python
MOCK_SERIAL = "SN123456789"  # matches MOCK_DEVICE_RESPONSE.device.details.serial_no
```

(It already exists in `MOCK_DEVICE_RESPONSE["device"]["details"]["serial_no"]` — this just gives tests a name to import.)

- [ ] **Step 2: Write the failing migration test**

Append to `tests/test_init.py`:

```python
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
```

Add to imports at the top of the file as needed:

```python
from unittest.mock import patch
from custom_components.jablotron_futura.const import DOMAIN
```

- [ ] **Step 3: Run the migration test, confirm it fails**

```bash
/tmp/ha-futura-venv/bin/python -m pytest tests/test_init.py::test_unique_id_migration_rewrites_legacy_keys -v
```

Expected: FAIL — `migrated.unique_id == \"filter_health\"` (no migration yet).

- [ ] **Step 4: Implement migration in __init__.py**

Edit `custom_components/jablotron_futura/__init__.py`. Add `async_migrate_entries` import and call it inside `async_setup_entry` *after* the first refresh (we need the serial from the coordinator):

```python
from homeassistant.helpers import entity_registry as er

async def async_setup_entry(hass: HomeAssistant, entry: JablotronFuturaConfigEntry) -> bool:
    """Set up Jablotron Futura from a config entry."""
    futura = Futura(
        hass, username=entry.data[CONF_USERNAME], password=entry.data[CONF_PASSWORD]
    )
    coordinator = FuturaCoordinator(hass, futura)

    await coordinator.async_config_entry_first_refresh()

    serial_no = coordinator.futura.central_unit().serial_no

    @callback
    def _migrate_unique_id(entry: er.RegistryEntry) -> dict | None:
        prefix = f"{serial_no}_"
        if entry.unique_id.startswith(prefix):
            return None
        return {"new_unique_id": f"{prefix}{entry.unique_id}"}

    await er.async_migrate_entries(hass, entry.entry_id, _migrate_unique_id)

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True
```

Add `from homeassistant.core import HomeAssistant, callback` (replace the existing `HomeAssistant`-only import).

- [ ] **Step 5: Update each platform's `unique_id` to include the serial**

In `custom_components/jablotron_futura/sensor.py`, both `FuturaSummarySensorEntity.unique_id` and `FuturaPeripherySensorEntity.unique_id`:

```python
    @property
    def unique_id(self) -> str:
        return f"{self._central_unit.serial_no}_{self.entity_description.key}"
```

In `custom_components/jablotron_futura/binary_sensor.py`, `FuturaSummaryBinarySensorEntity.unique_id`:

```python
    @property
    def unique_id(self) -> str:
        return f"{self._central_unit.serial_no}_{self.entity_description.key}"
```

In `custom_components/jablotron_futura/switch.py`, `FuturaSettingsSwitchEntity.unique_id`:

```python
    @property
    def unique_id(self) -> str:
        return f"{self._central_unit.serial_no}_{self._idx}"
```

In `custom_components/jablotron_futura/futura.py`, `FuturaControlEntity.unique_id`:

```python
    @property
    def unique_id(self) -> str:
        return f"{self._central_unit.serial_no}_{self._idx}"
```

(`FuturaControlEntity` is the base for number and select, so this covers both.)

- [ ] **Step 6: Run migration test + full suite**

```bash
/tmp/ha-futura-venv/bin/python -m pytest tests/test_init.py::test_unique_id_migration_rewrites_legacy_keys -v
/tmp/ha-futura-venv/bin/python -m pytest -q
```

Expected: migration test passes. The existing platform tests (test_sensor.py etc.) assert against `entity_id` (e.g. `sensor.jablotron_futura_filter_health`), not `unique_id`, so they should still pass — HA derives entity_id from `domain.{device_name}_{name}` using the slug of the original `name` property (which Task 4 will replace), not from unique_id. If a platform test breaks here, it's a real regression — investigate before continuing.

- [ ] **Step 7: Commit**

```bash
git add custom_components/jablotron_futura/__init__.py \
        custom_components/jablotron_futura/futura.py \
        custom_components/jablotron_futura/sensor.py \
        custom_components/jablotron_futura/binary_sensor.py \
        custom_components/jablotron_futura/switch.py \
        tests/conftest.py tests/test_init.py
git commit -m "feat(entities): scope unique_id by device serial + migrate registry

Prefix every entity unique_id with the device serial so multi-entry
setups never collide. async_migrate_entries rewrites existing rows so
upgrading users keep their entity history.

Addresses frenck/hacs/default#6509 review item 3."
```

---

## Task 4: Use has_entity_name for Friendly Display Names

**Why:** `FuturaEntity.name` returns `\"{DOMAIN}.{unique_id}\"` — that reads as an entity_id, not a friendly name. Modern Home Assistant entities set `_attr_has_entity_name = True` and let either `entity_description.name` or `_attr_name` provide the display name; HA composes `\"{device_name} {entity_name}\"` automatically.

The sensor / binary_sensor classes already have `entity_description.name`. Switch / number / select don't — they need an `_attr_name` (or a name passed into the constructor).

**Files:**
- Modify: `custom_components/jablotron_futura/futura.py` — `FuturaEntity` (drop `name`, set `_attr_has_entity_name`)
- Modify: `custom_components/jablotron_futura/switch.py` — supply per-switch display name
- Modify: `custom_components/jablotron_futura/number.py` — supply display name
- Modify: `custom_components/jablotron_futura/select.py` — supply display name
- Test: `tests/test_sensor.py`, `tests/test_binary_sensor.py`, `tests/test_switch.py` (create if missing), `tests/test_number.py`, `tests/test_select.py`

- [ ] **Step 1: Confirm whether test_switch.py exists**

```bash
ls tests/test_switch.py 2>&1
```

If it does not exist, create a minimal one in step 4 — otherwise update in place.

- [ ] **Step 2: Write/update a failing assertion for entity friendly_name**

Append to `tests/test_sensor.py`:

```python
async def test_summary_sensor_has_friendly_name(hass: HomeAssistant):
    """Summary sensor should expose a friendly name from its EntityDescription."""
    await setup_integration(hass)

    state = hass.states.get("sensor.jablotron_futura_filter_health")
    assert state is not None
    assert state.attributes["friendly_name"] == "jablotron_futura Filter Health"
```

(`device_info.name` is `DOMAIN` — `\"jablotron_futura\"` — so the composed friendly name is `\"jablotron_futura Filter Health\"`.)

- [ ] **Step 3: Run it, confirm it fails**

```bash
/tmp/ha-futura-venv/bin/python -m pytest tests/test_sensor.py::test_summary_sensor_has_friendly_name -v
```

Expected: FAIL — current `name` returns `\"jablotron_futura.SN123456789_filter_health\"`.

- [ ] **Step 4: Update FuturaEntity to use has_entity_name**

Edit `custom_components/jablotron_futura/futura.py`, `FuturaEntity`:

```python
class FuturaEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._futura = coordinator.futura
        self._central_unit = self._futura.central_unit()

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._central_unit.serial_no)},
            manufacturer=JABLOTRON,
            name=DOMAIN,
            model=self._central_unit.model,
            sw_version=self._central_unit.fw_version,
            hw_version=self._central_unit.hw_version,
            via_device=(DOMAIN, self._central_unit.serial_no),
        )
```

(Drop the `name` property entirely.)

- [ ] **Step 5: Add explicit names to switch / number / select**

`custom_components/jablotron_futura/switch.py` — supply a display name per switch:

```python
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


class FuturaSettingsSwitchEntity(FuturaEntity, SwitchEntity):
    def __init__(self, idx, name, device_class, coordinator):
        super().__init__(coordinator)
        self._idx = idx
        self._attr_name = name
        self._device_class = device_class
```

`custom_components/jablotron_futura/number.py`:

```python
class FuturaControlTemperatureEntity(FuturaControlEntity, NumberEntity):
    _attr_name = "Temperature"

    def __init__(self, coordinator) -> None:
        super().__init__("control_temperature", NumberDeviceClass.TEMPERATURE, coordinator)
```

`custom_components/jablotron_futura/select.py`:

```python
class FuturaControlFanPowerEntity(FuturaControlEntity, SelectEntity):
    _attr_name = "Fan Power"

    def __init__(self, coordinator) -> None:
        super().__init__("control_fan_power", None, coordinator)


class FuturaControlHumidityEntity(FuturaControlEntity, SelectEntity):
    _attr_name = "Humidity"

    def __init__(self, coordinator) -> None:
        super().__init__("control_humidity", None, coordinator)
```

- [ ] **Step 6: Run the friendly-name test + full suite, fix breakage**

```bash
/tmp/ha-futura-venv/bin/python -m pytest -q
```

`has_entity_name = True` changes entity_id slug generation. Existing tests assert against entity_ids like `sensor.jablotron_futura_filter_health`. After this change, HA composes the entity_id from device + entity name. The device name is `\"jablotron_futura\"`, the entity name is `\"Filter Health\"`, so the slug is `sensor.jablotron_futura_filter_health` — same string. Verify by running the suite. If any entity_id assertions break, update them to match HA's new composition (e.g. expect `sensor.jablotron_futura_filter_health` exactly).

Switch entity_ids: with name `\"Bypass\"` and device `\"jablotron_futura\"` → `switch.jablotron_futura_bypass`. Update existing switch tests accordingly if they reference a different id.

Expected after fixes: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add custom_components/jablotron_futura/futura.py \
        custom_components/jablotron_futura/switch.py \
        custom_components/jablotron_futura/number.py \
        custom_components/jablotron_futura/select.py \
        tests/
git commit -m "feat(entities): use _attr_has_entity_name for friendly names

Drop FuturaEntity.name (which returned an entity_id-style string) and
let HA compose friendly names from device + EntityDescription.name or
_attr_name. Switch/number/select entities now supply _attr_name
explicitly.

Addresses frenck/hacs/default#6509 review item 4."
```

---

## Task 5: Manual Smoke Test in the HA Devcontainer

**Why:** The unit suite uses `pytest-homeassistant-custom-component` against a stub HA. Before opening the PR, exercise the integration against a live Jablotron unit inside the sibling `homeassistant-core` devcontainer so anything that only surfaces in real HA (registry migration, friendly-name composition, coordinator behaviour over the wire) is caught. The full setup procedure is in `CLAUDE.md` — this task just lists the steps to execute and the per-item checks to confirm.

**Files:**
- None modified by this task. **Do not** commit `CLAUDE.md` here or in any other task; the user wants it kept local for now.

- [ ] **Step 1: Bring up the HA devcontainer with this integration mounted**

Follow `CLAUDE.md` → "Path B" → "One-time setup" steps 1–3 if the devcontainer hasn't been built yet. The key gate is that `../homeassistant-core/.devcontainer/devcontainer.json` has the `home-assistant-jablotron-futura` bind-mount line uncommented. Open `homeassistant-core` in VS Code → Dev Containers: Reopen in Container.

- [ ] **Step 2: Start HA inside the container**

Command palette → Run Task → **Run Home Assistant Core** (or F5 to attach the debugger). HA listens on http://localhost:8123.

- [ ] **Step 3: First boot — fresh install path**

If this is a fresh `homeassistant-core/config/` dir, complete the HA onboarding wizard, then Settings → Devices & Services → Add Integration → "Jablotron Futura". Enter real credentials. Confirm the device appears with its serial number and entities populate.

- [ ] **Step 4: Verify Task 1 — auth caching**

Open the terminal in the container and tail the log:

```bash
tail -f config/home-assistant.log | grep -iE "userAuthorize|jablotron_futura"
```

Wait ≥ 5 minutes (one coordinator cycle). Expected: zero `userAuthorize.json` POST log lines after initial setup. Then force a session expiry (briefly disconnect the network or wait for cookie TTL), confirm exactly one transparent re-auth + retry happens on the next refresh with no `ConfigEntryAuthFailed`.

- [ ] **Step 5: Verify Task 2 — duplicate config entry abort**

Settings → Devices & Services → Add Integration → "Jablotron Futura" → enter the same credentials again. Expected: the flow aborts with the `already_configured` reason. HA renders this as "Already configured" / no second entry created.

- [ ] **Step 6: Verify Task 3 — entity unique_id migration (upgrade path)**

Stop HA. From inside the container, inspect the entity registry:

```bash
python -c "import json; r = json.load(open('config/.storage/core.entity_registry')); print('\n'.join(sorted({e['unique_id'] for e in r['data']['entities'] if e['platform']=='jablotron_futura'})))"
```

Expected: every line starts with the device serial (e.g. `SN123456789_filter_health`, `SN123456789_control_temperature`, …). No bare keys like `filter_health` remain.

If you started fresh in Step 3, this only proves the new-entry path. To exercise the migration path, before Step 2 you must have a `config/` from before this branch — easiest is to launch HA once on `master` first, add the integration, stop HA, then `git checkout frenck-review-followups`, restart HA, and rerun this check. Entity history (states, energy graphs) must remain intact in the UI.

- [ ] **Step 7: Verify Task 4 — friendly names**

Settings → Devices & Services → Jablotron Futura device card. Each entity's display name should read like `"jablotron_futura Filter Health"` (device name + capitalized name from `EntityDescription.name` / `_attr_name`), not `"jablotron_futura.filter_health"`. Spot-check at least one sensor, one switch, the temperature number, and one select.

- [ ] **Step 8: Exercise control entities once**

Toggle one switch (e.g. Bypass), set the temperature number, change the fan-power select. Each should round-trip through the API and reflect the new value within one coordinator refresh. No exceptions in the log.

- [ ] **Step 9: Record the result**

If everything passes, proceed to Task 6. If anything fails, fix in the corresponding task, re-run the unit suite, and redo this task. **Do not** commit anything from this task — it's verification only.

---

## Task 6: Stage Release 0.4.0 and Open PR

**Why:** All four review items shipped on `frenck-review-followups` and smoke-tested in Task 5. CLAUDE.md forbids pushing directly to `master`, so the change ships as a PR. The manifest/changelog bump rides along in the PR so a merge produces a release-ready `master` in one click. The actual git tag + GitHub release are a follow-up after merge (see "After-Merge Follow-up" below) — those are what HACS reads as `0.4.0`.

**Files:**
- Modify: `custom_components/jablotron_futura/manifest.json`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Bump manifest version**

Edit `custom_components/jablotron_futura/manifest.json`:

```json
    "version": "0.4.0"
```

- [ ] **Step 2: Add CHANGELOG entry**

Prepend after the `# CHANGELOG` heading in `CHANGELOG.md`:

```markdown
## Version 0.4.0

- Auth: cache session token, only re-authorize on 401 (no more cleartext credentials every 5 minutes)
- Config flow: prevent adding the same Jablotron account twice (`async_set_unique_id` on device serial)
- Entities: scope `unique_id` by device serial; existing entity registry rows auto-migrate
- Entities: use `_attr_has_entity_name = True` for friendly display names
```

- [ ] **Step 3: Run the full suite one more time**

```bash
/tmp/ha-futura-venv/bin/python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 4: Commit the version bump on the feature branch**

```bash
git add custom_components/jablotron_futura/manifest.json CHANGELOG.md
git commit -m "chore: bump version to 0.4.0"
```

- [ ] **Step 5: Push the feature branch to origin**

```bash
git push -u origin frenck-review-followups
```

This pushes to a **new branch**, not `master`. Safe under CLAUDE.md.

- [ ] **Step 6: Open the pull request against master**

```bash
gh pr create \
  --repo peterturza/home-assistant-jablotron-futura \
  --base master \
  --head frenck-review-followups \
  --title "Address frenck review heads-up items (0.4.0)" \
  --body "$(cat <<'EOF'
Follow-up to the security fix in 0.3.2. Addresses the four non-blocking heads-up items from frenck's review on hacs/default#6509 (pullrequestreview-4308155345):

1. **Auth caching** — `Futura` no longer re-POSTs cleartext credentials on every coordinator refresh and every command. A session-level `_authenticated` flag gates `authorize()`; a 401/403 on any non-auth endpoint transparently re-authorizes and retries once.
2. **Config-entry unique id** — `async_set_unique_id(serial_no)` + `_abort_if_unique_id_configured()` so the same Jablotron account can't be added twice.
3. **Entity unique_id scoping** — every entity `unique_id` is now prefixed with the device serial; an `async_migrate_entries` step rewrites pre-upgrade registry rows so existing users keep their entity history.
4. **Friendly entity names** — `_attr_has_entity_name = True` on `FuturaEntity`; sensors/binary sensors source the name from `EntityDescription.name`, switch/number/select set `_attr_name` explicitly.

Each item is its own atomic commit; the final commit bumps `manifest.json` and `CHANGELOG.md` to 0.4.0. After merge, tag `0.4.0` on master and create the GitHub release — that's what HACS consumes.

Plan: `docs/superpowers/plans/2026-05-20-frenck-review-items.md`
EOF
)"
```

The command prints the PR URL. Capture it for the follow-up step.

- [ ] **Step 7: Wait for HACS + hassfest workflows to go green on the PR**

```bash
gh pr checks --repo peterturza/home-assistant-jablotron-futura --watch
```

Expected: both `HACS Action` and `Validate with hassfest` report success.

---

## After-Merge Follow-up (Not Part of This Plan)

Once the PR above is reviewed, approved, and merged to `master`, this is the rest of the release flow (do NOT execute as part of this plan):

```bash
git checkout master
git pull --ff-only origin master
git tag 0.4.0
git push origin 0.4.0
gh release create 0.4.0 \
  --repo peterturza/home-assistant-jablotron-futura \
  --title "0.4.0" \
  --notes-from-tag
gh pr comment 6509 --repo hacs/default --body "0.4.0 cut — all four heads-up items from review-4308155345 addressed: auth caching, config-entry unique id, serial-scoped entity unique_ids with registry migration, and \`has_entity_name\` friendly names. Release notes: https://github.com/peterturza/home-assistant-jablotron-futura/releases/tag/0.4.0"
```

---

## Self-Review Notes

- **Spec coverage:** Frenck's four heads-up items → Tasks 1, 2, 3, 4 respectively. Branch setup is Task 0; manual smoke test against real HA is Task 5 (see `CLAUDE.md`); PR delivery is Task 6. The blocking `verify_ssl=False` item already shipped in `0.3.2` (commit `c8db750`) and is intentionally out of scope here.
- **CLAUDE.md handling:** `CLAUDE.md` is referenced by Task 5 but is **not** committed by any task. The user is keeping it local for now. None of the `git add` invocations in this plan include it; if you find yourself about to stage it, stop.
- **Migration risk:** Task 3 ships a registry migration. If it misfires, users see duplicated entities. The migration is idempotent (early return when the unique_id already has the serial prefix) and covered by `test_unique_id_migration_rewrites_legacy_keys`.
- **Ordering dependency:** Task 4's friendly-name change reads `entity_description.name` (sensors/binary sensors) and `_attr_name` (switch/number/select). It does NOT depend on Task 3's unique_id change, but shipping them together in a single PR avoids a double rename for users.
- **No direct master push:** every git write in this plan is either a commit on `frenck-review-followups` or a push of that branch. The tag/release flow that *does* touch master lives in "After-Merge Follow-up" and runs only after the PR is merged by a human.
