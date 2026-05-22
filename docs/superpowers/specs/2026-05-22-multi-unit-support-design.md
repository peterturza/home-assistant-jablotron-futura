# Multi-unit support — design

**Issue:** [#10 — Adding a second recovery ventilation unit](https://github.com/peterturza/home-assistant-jablotron-futura/issues/10)
**Date:** 2026-05-22

## Problem

The integration only ever sets up the *first* Futura service it finds on a Jablotron
cloud account (`futura_services[0]`) and uses that unit's serial number as the config
entry's unique ID. A user with two units on one account can add only one of them;
adding the account a second time aborts with `already_configured`.

## Goal

Support an arbitrary number of Futura units under a single Jablotron account: one config
entry per account, one Home Assistant device per unit (serial number), with all existing
single-unit installs migrating cleanly (no lost entities or history).

## Decisions

- **Entry model:** one config entry per account; a single coordinator fetches all units
  in one poll cycle; one HA device per serial number.
- **Discovery timing:** units are enumerated once at setup. Adding/removing hardware on
  the account requires reloading the integration (or restarting HA). No live add/remove
  on the 5-minute poll.
- **Edge case 1 (legacy entity prefix):** legacy unique-id prefixing is gated to
  single-unit accounts (see Migration).
- **Edge case 2 (stale devices):** add `async_remove_config_entry_device` so users can
  delete a device for a unit that has left the account.

## Architecture

Single coordinator, single auth/poll cycle:

```
async_setup_entry
  └─ FuturaCoordinator.first_refresh
       └─ Futura.sync()
            ├─ serviceListGet.json        (once)
            └─ getDevice.json × N          (one per Futura service)
       → coordinator.data = { serial_no: device_json, … }

per platform async_setup_entry:
  for unit in coordinator.futura.units():
      build that platform's entity set, bound to unit.serial_no
```

```
Account config entry  (unique_id = account login)
├─ Device: Futura (serial A) ── sensors / numbers / selects / switches / binary_sensors
└─ Device: Futura (serial B) ── sensors / numbers / selects / switches / binary_sensors
```

## Component changes

### 1. Data layer — `futura.py`

- `Futura.sync()`:
  - Stop selecting `futura_services[0]`. Iterate **all** services matching the existing
    visible / `ENABLED` / Futura-namespace filter.
  - For each service, call `getDevice.json` and build a `FuturaCentralUnit`.
  - Store `self._units: dict[str, FuturaCentralUnit]` keyed by `serial_no`, preserving
    service order (first service = "primary", used for legacy migration).
  - Return `{ serial_no: device_json, … }` (the per-unit `getDevice` payloads).
  - Raise `UpdateFailed("No Futura service found")` only when **zero** services match
    (unchanged behaviour for empty accounts).
- Replace `central_unit() -> FuturaCentralUnit` with:
  - `units() -> dict[str, FuturaCentralUnit]`
  - `primary_unit() -> FuturaCentralUnit | None` (first by service order; for migration).
- `set_control(serial, control, value)` and
  `set_setting_extended_property(serial, prop_name, prop_value)` take a leading `serial`
  argument and resolve `room_id` / `service_id` from `self._units[serial]`.

### 2. Coordinator & setup — `__init__.py`

- `coordinator.data` is now `{ serial_no: device_json, … }`.
- After `async_config_entry_first_refresh()`, require at least one unit with a
  serial number; otherwise `ConfigEntryError` (same guard as today, applied per account).
- **Config-entry unique_id migration** (inline in `async_setup_entry`, consistent with the
  repo's existing inline migration style):

  ```python
  username = entry.data[CONF_USERNAME]
  if entry.unique_id != username:
      hass.config_entries.async_update_entry(entry, unique_id=username)
  ```

  Retargeting `unique_id` does not touch `entry_id`; entity↔entry links are keyed on
  `entry_id`, so this is invisible to entities. (Alternative considered: bump
  `ConfigFlow.VERSION` to 2 + `async_migrate_entry`. Rejected for consistency with the
  existing inline migration; revisit if entry **data** shape ever changes.)
- **Entity unique_id migration** (`_migrate_unique_id`): kept and idempotent. Gated to
  single-unit accounts — only prefix unprefixed ids when `len(units) == 1`, using that
  unit's serial. Accounts that upgraded through 0.4.0 are already prefixed (no-op);
  multi-unit accounts skip legacy prefixing entirely, avoiding the wrong-serial ambiguity.
- Add `async_remove_config_entry_device(hass, entry, device_entry)` returning `True` when
  the device's serial is no longer among the account's current units (lets users remove a
  unit that has left the account from the UI).

### 3. Entities — base classes + all 5 platform files

- `FuturaEntity.__init__(self, coordinator, central_unit)` stores the specific
  `central_unit` instead of calling `coordinator.futura.central_unit()`. Store
  `self._serial = central_unit.serial_no`.
- All data reads change from `coordinator.data["device"]…` to
  `coordinator.data[self._serial]["device"]…`.
- `FuturaControlEntity.__init__(self, idx, device_class, coordinator, central_unit)`
  threads `central_unit` through to the base.
- Each platform's `async_setup_entry` loops over `coordinator.futura.units().values()`
  and creates its full entity set per unit.
- Control entities call `self._futura.set_control(self._serial, …)` and
  `self._futura.set_setting_extended_property(self._serial, …)`.
- `device_info`: built per unit; **drop** the self-referential `via_device`
  (no hub device exists — it currently points a device at itself).
- unique_ids stay `f"{serial}_{key}"` — already serial-scoped, unique across units, no
  scheme change.

### 4. Config flow — `config_flow.py`

- `validate_input`: after `sync()`, require at least one unit (`futura.units()` non-empty),
  else `ServiceNotFoundError`. Return `{"title": <account login>, "username": <login>}`.
- `async_step_user`: `async_set_unique_id(username)` + `_abort_if_unique_id_configured()`.
  Duplicate now means "account already configured" rather than "serial already configured".

## Migration summary

Existing single-unit install (serial A, set up on ≥0.4.0):

| Registry      | Before                       | After                              |
|---------------|------------------------------|------------------------------------|
| Config entry  | `unique_id = serialA`        | `unique_id = account login`        |
| Entities      | `serialA_<key>`              | `serialA_<key>` (unchanged)        |
| Device        | `(DOMAIN, serialA)`          | `(DOMAIN, serialA)` (unchanged; `via_device` self-link dropped) |
| Second unit   | —                            | new device `(DOMAIN, serialB)` + fresh `serialB_<key>` entities |

Net: same entry, same device, same entities and history; the second unit appears as a new
device. Nothing is deleted or re-keyed.

## Testing — `tests/conftest.py` + suites

- New multi-unit fixtures:
  - `serviceListGet` response with two services (distinct `service-id`s).
  - `getDevice` mock dispatches on the request body's `id` → returns a distinct device
    payload (distinct `serial_no`) per service.
- New tests:
  - Two devices registered; each platform creates one entity set per unit.
  - Entity ids are serial-scoped and distinct across units (no collision).
  - Config-entry unique_id migration: an entry created with `unique_id = serialA` is
    updated to the account login on setup.
  - Legacy entity-prefix migration runs only for single-unit accounts.
  - `async_remove_config_entry_device` returns `True` for an absent serial, `False` for a
    current one.
  - Write path: `set_control` / `set_setting_extended_property` target the correct unit's
    `service_id` / `room_id`.
- Update existing single-unit tests for the `{ serial: device_json }` data shape and the
  account-based config-entry unique id (e.g. `test_config_flow_aborts_on_duplicate_serial`
  → duplicate account).

## Out of scope

- Live add/remove of units on the poll cycle (reload required instead).
- Per-unit credentials / multiple accounts in one entry (each account stays its own entry).
- Any change to the set of exposed entities or the Jablotron API surface used.
