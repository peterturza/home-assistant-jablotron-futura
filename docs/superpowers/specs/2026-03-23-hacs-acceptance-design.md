# HACS Default Repository Acceptance — Design Spec

## Context

The Jablotron Futura integration was rejected from the HACS default repository by @ludeeus with the feedback:
- "The repository contains virtually no documentation"
- "It also looks abandoned already?"

This spec covers the work needed to address that feedback and modernize the codebase to make a stronger impression on resubmission.

## Goals

1. Write comprehensive README documentation
2. Fix bugs that would cause runtime errors
3. Modernize code to follow current Home Assistant patterns
4. Preserve backwards compatibility for existing installations

## Non-Goals

- Adding new features (climate entity, diagnostics, etc.)
- Changing entity naming scheme (`has_entity_name = True`) — risks breaking existing entity IDs
- Changing config entry schema — no migration needed

---

## 1. README & Repository Presentation

### README.md

Write a comprehensive README covering:

- **Header**: Integration name, HACS badge, HA compatibility badge
- **Description**: What Jablotron Futura is (heat recovery ventilation unit), what this integration provides
- **Features**: List of all exposed entities and controls
- **Installation**: HACS install steps + manual install steps
- **Configuration**: UI-based config flow, Jablotron cloud account credentials required
- **Entities table**: Table of all entities with type, description, and device class
- **Troubleshooting/FAQ**: Common issues (cloud API, credentials, polling interval)

### Repository Settings (Already Done)

- Description: "Home Assistant custom component for JABLOTRON Futura recuperation unit"
- Topics: `custom-component`, `hacs`, `hacs-integration`, `home-assistant`, `integration`, `jablotron`, `jablotron-futura`, `hvac`
- Formal GitHub releases: exist (0.2.0, 0.2.1, 0.2.2)

---

## 2. Bug Fixes & Cleanup

### Remove `Platform.SWITCH`

`__init__.py` lists `Platform.SWITCH` in the `PLATFORMS` list, but no `switch.py` file exists. This will cause a runtime error when Home Assistant tries to forward entry setup to the switch platform. Remove it from the list.

**File**: `custom_components/jablotron_futura/__init__.py`

### `.DS_Store` cleanup

- Add `.DS_Store` to `.gitignore`
- Remove tracked `.DS_Store` file from the repository

---

## 3. Code Modernization

### 3.1 EntityDescription Dataclasses

Replace the current pattern of passing `idx` and `device_class` as constructor args with typed `EntityDescription` dataclasses.

**Current pattern** (e.g., in `sensor.py`):
```python
FuturaSummarySensorEntity(idx, device_class, coordinator)
```

**New pattern**:
```python
@dataclass(frozen=True, kw_only=True)
class FuturaSummarySensorEntityDescription(SensorEntityDescription):
    # additional fields if needed
    pass

SUMMARY_SENSORS: tuple[FuturaSummarySensorEntityDescription, ...] = (
    FuturaSummarySensorEntityDescription(
        key="filter_health",
        name="Filter Health",
        ...
    ),
    ...
)
```

Apply to: `sensor.py`, `binary_sensor.py`, `select.py`, `number.py`

### 3.2 ConfigEntry.runtime_data

Replace `hass.data[DOMAIN][entry.entry_id]` with typed `ConfigEntry.runtime_data`.

**Current pattern** (`__init__.py`):
```python
hass.data.setdefault(DOMAIN, {})
hass.data[DOMAIN][entry.entry_id] = coordinator
```

**New pattern**:
```python
type JablotronFuturaConfigEntry = ConfigEntry[FuturaCoordinator]

entry.runtime_data = coordinator
```

Platform files access coordinator via `entry.runtime_data` instead of `hass.data[DOMAIN][entry.entry_id]`.

### 3.3 API Error Handling

**`futura.py` — `authorize()`**:
- Raise `ConfigEntryAuthFailed` on HTTP 401/403 (triggers HA reauth flow)
- Raise `UpdateFailed` on other HTTP errors (lets coordinator retry)

**`futura.py` — `sync()`**:
- Wrap API calls with proper error handling
- Raise `UpdateFailed` on transient failures

### 3.4 Type Annotations

Add proper type annotations to `async_setup_entry` in all platform files:

```python
async def async_setup_entry(
    hass: HomeAssistant,
    entry: JablotronFuturaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
```

### 3.5 Rename Shadowed Builtins

In `futura.py`:
- `set_setting_extended_property(self, property, value)` — rename `property` to `prop_name` and `value` to `prop_value`
- Various uses of `filter` as variable name — rename to avoid shadowing

---

## 4. Backwards Compatibility

### Entity unique_id Preservation

All existing `unique_id` values must be preserved exactly:
- `filter_health`, `device_consumption`, `heating_recovered_current`
- `fut_co2_ppm_max`, `fut_humi_indoor`, `fut_temp_indoor`, `fut_temp_outdoor`
- `current_servo_drying`, `current_servo_bypass`
- `control_fan_power`, `control_humidity`, `control_temperature`

These become the `key` field in each `EntityDescription`.

### Entity ID Preservation

Skip `has_entity_name = True` to ensure HA-generated entity IDs remain unchanged. Entity names continue using the `DOMAIN.unique_id` pattern.

### Config Entry Compatibility

- `ConfigFlow.VERSION` stays at `1`
- Config data schema unchanged (username + password)
- No migration code needed

### runtime_data Transition

`ConfigEntry.runtime_data` is set during `async_setup_entry` (same lifecycle as the old `hass.data` pattern). Existing config entries load normally — no migration needed.

---

## 5. Brand Icon

Already exists in the user's fork: `peterturza/home-assistant-brands` under `custom_integrations/jablotron_futura/`. No action needed in this repository.

---

## Files Changed

| File | Change |
|---|---|
| `README.md` | Complete rewrite |
| `.gitignore` | Add `.DS_Store` |
| `custom_components/jablotron_futura/__init__.py` | Remove `Platform.SWITCH`, use `runtime_data`, add types |
| `custom_components/jablotron_futura/futura.py` | Better error handling, rename shadowed builtins, add types |
| `custom_components/jablotron_futura/sensor.py` | Use `EntityDescription`, use `runtime_data`, add types |
| `custom_components/jablotron_futura/binary_sensor.py` | Use `EntityDescription`, use `runtime_data`, add types |
| `custom_components/jablotron_futura/select.py` | Use `EntityDescription`, use `runtime_data`, add types |
| `custom_components/jablotron_futura/number.py` | Use `EntityDescription`, use `runtime_data`, add types |
| `custom_components/jablotron_futura/const.py` | No changes expected |
| `custom_components/jablotron_futura/errors.py` | No changes expected |
| `custom_components/jablotron_futura/manifest.json` | Version bump to 0.3.0 |
| `CHANGELOG.md` | Add 0.3.0 entry |
