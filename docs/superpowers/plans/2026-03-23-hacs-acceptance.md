# HACS Default Repository Acceptance — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare the Jablotron Futura integration for HACS default repository acceptance by writing documentation, fixing bugs, and modernizing code.

**Architecture:** Cloud-polling Home Assistant custom integration communicating with the Jablotron API. All entities use a `DataUpdateCoordinator` that syncs every 5 minutes. Modernization follows current HA patterns (EntityDescription, runtime_data, typed error handling) while preserving all existing unique_ids and entity IDs.

**Tech Stack:** Python 3.12+, Home Assistant 2025.1.0+, aiohttp (via HA client session)

**Note:** This project has no test suite. HA integrations are typically tested against a running HA instance. Tasks focus on implementation and manual verification via HACS/hassfest GitHub Actions.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `.gitignore` | Modify | Add `.DS_Store` |
| `custom_components/jablotron_futura/__init__.py` | Modify | Remove `Platform.SWITCH`, use `runtime_data`, add type alias |
| `custom_components/jablotron_futura/futura.py` | Modify | Error handling, rename shadowed builtins, typing |
| `custom_components/jablotron_futura/sensor.py` | Modify | EntityDescription, `runtime_data`, typing |
| `custom_components/jablotron_futura/binary_sensor.py` | Modify | EntityDescription, `runtime_data`, typing |
| `custom_components/jablotron_futura/select.py` | Modify | EntityDescription, `runtime_data`, typing |
| `custom_components/jablotron_futura/number.py` | Modify | EntityDescription, `runtime_data`, typing |
| `custom_components/jablotron_futura/manifest.json` | Modify | Version bump to 0.3.0 |
| `README.md` | Rewrite | Comprehensive documentation |
| `CHANGELOG.md` | Modify | Add 0.3.0 entry |

---

### Task 1: Cleanup — Remove .DS_Store and Platform.SWITCH

**Files:**
- Modify: `.gitignore`
- Modify: `custom_components/jablotron_futura/__init__.py:18-24`

- [ ] **Step 1: Add `.DS_Store` to `.gitignore`**

Add this line to the top of `.gitignore` (before the Python section):

```
.DS_Store
```

- [ ] **Step 2: Remove tracked `.DS_Store` from git**

Run:
```bash
git rm --cached custom_components/jablotron_futura/.DS_Store
```

- [ ] **Step 3: Remove `Platform.SWITCH` from `PLATFORMS`**

In `custom_components/jablotron_futura/__init__.py`, change the `PLATFORMS` list from:

```python
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
]
```

To:

```python
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.BINARY_SENSOR,
]
```

- [ ] **Step 4: Commit**

```bash
git add .gitignore custom_components/jablotron_futura/__init__.py
git commit -m "fix: remove .DS_Store tracking and unused Platform.SWITCH"
```

---

### Task 2: Modernize `futura.py` — Error Handling & Shadowed Builtins

**Files:**
- Modify: `custom_components/jablotron_futura/futura.py`

- [ ] **Step 1: Add imports for HA exceptions**

At the top of `futura.py`, add:

```python
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
```

- [ ] **Step 2: Improve `authorize()` error handling**

Replace the current `authorize` method:

```python
async def authorize(self) -> None:
    """Authorize user via API"""
    try:
        async with self._session.post(
            "{}/userAuthorize.json".format(JABLOTRON_API),
            json={
                "login": self._username,
                "password": self._password,
            },
            headers=JABLOTRON_API_DEFAULT_HEADERS,
        ) as result:
            if result.status in (401, 403):
                raise ConfigEntryAuthFailed("Invalid Jablotron credentials")
            if result.status != 200:
                raise UpdateFailed(
                    f"Jablotron API authorization failed with status {result.status}"
                )
    except (TimeoutError, aiohttp.ClientError) as err:
        raise UpdateFailed(f"Error communicating with Jablotron API: {err}") from err
```

Also add to the imports at the top of the file:

```python
import aiohttp
```

- [ ] **Step 3: Wrap `sync()` with error handling**

Replace the current `sync` method. Add a try/except around the API calls:

```python
async def sync(self):
    """Get data from API"""
    await self.authorize()
    try:
        async with self._session.post(
            "{}/serviceListGet.json".format(JABLOTRON_API),
            json={
                "visibility": "DEFAULT",
                "list-type": "EXTENDED",
                "checksum": "",
            },
            headers=JABLOTRON_API_DEFAULT_HEADERS,
        ) as result:
            if result.status != 200:
                raise UpdateFailed(
                    f"Failed to get service list: status {result.status}"
                )
            json = await result.json()
            _LOGGER.debug(json)
            data = json["data"]
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
        async with self._session.post(
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
        ) as result:
            if result.status != 200:
                raise UpdateFailed(
                    f"Failed to get device: status {result.status}"
                )
            json = await result.json()
            device = json["device"]
            _LOGGER.debug(device)
            self._central_unit = FuturaCentralUnit(
                service_id=device["id"],
                model=device["type"],
                hw_version=device["details"]["hw_revision"],
                fw_version=device["details"]["fw_version"],
                serial_no=device["details"]["serial_no"],
                room_id=device["rooms"][0]["id"],
            )
            return json
    except (TimeoutError, aiohttp.ClientError) as err:
        raise UpdateFailed(f"Error communicating with Jablotron API: {err}") from err
```

Note: Also replaced `filter()` with a list comprehension in the services lookup — cleaner and avoids no issues.

- [ ] **Step 4: Rename shadowed builtins in `set_setting_extended_property`**

Change method signature from:

```python
async def set_setting_extended_property(self, property, value) -> None:
```

To:

```python
async def set_setting_extended_property(self, prop_name: str, prop_value) -> None:
```

And update the body to use `prop_name` and `prop_value`:

```python
async def set_setting_extended_property(self, prop_name: str, prop_value) -> None:
    """Sets extended property value via API"""
    await self.authorize()
    async with self._session.post(
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
    ) as result:
        return
```

- [ ] **Step 5: Verify no callers of `set_setting_extended_property` break**

Run:
```bash
grep -r "set_setting_extended_property" custom_components/
```

Confirm it's only defined in `futura.py`. There is no `switch.py` file despite `Platform.SWITCH` being listed (removed in Task 1). The method has no callers — parameter rename is safe.

- [ ] **Step 6: Commit**

```bash
git add custom_components/jablotron_futura/futura.py
git commit -m "refactor: improve API error handling and rename shadowed builtins"
```

---

### Task 3: Modernize `__init__.py` — ConfigEntry.runtime_data

**Files:**
- Modify: `custom_components/jablotron_futura/__init__.py`

- [ ] **Step 1: Add type alias and update imports**

Add the type alias and update imports. The full updated file should have these imports and alias:

```python
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_PASSWORD, CONF_USERNAME, DOMAIN
from .futura import Futura

type JablotronFuturaConfigEntry = ConfigEntry[FuturaCoordinator]
```

- [ ] **Step 2: Update `async_setup_entry` to use `runtime_data`**

Replace:

```python
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
```

With:

```python
async def async_setup_entry(hass: HomeAssistant, entry: JablotronFuturaConfigEntry) -> bool:
    """Set up Jablotron Futura from a config entry."""
    futura = Futura(
        hass, username=entry.data[CONF_USERNAME], password=entry.data[CONF_PASSWORD]
    )
    coordinator = FuturaCoordinator(hass, futura)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True
```

Note: `runtime_data` must be set AFTER `async_config_entry_first_refresh()` succeeds — if the first refresh fails, HA handles the error before runtime_data is set.

- [ ] **Step 3: Update `async_unload_entry`**

Replace:

```python
async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
```

With:

```python
async def async_unload_entry(hass: HomeAssistant, entry: JablotronFuturaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
```

No need to clean up `hass.data` since we're not using it anymore. `runtime_data` is managed by HA.

- [ ] **Step 4: Commit**

```bash
git add custom_components/jablotron_futura/__init__.py
git commit -m "refactor: use ConfigEntry.runtime_data instead of hass.data"
```

---

### Task 4: Modernize `sensor.py` — EntityDescription & runtime_data

**Files:**
- Modify: `custom_components/jablotron_futura/sensor.py`

- [ ] **Step 1: Rewrite sensor.py**

Replace the entire file with:

```python
"""Sensor definitions for Jablotron Futura integration."""
from __future__ import annotations

from datetime import date, datetime
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .__init__ import JablotronFuturaConfigEntry
from .futura import FuturaEntity

_LOGGER = logging.getLogger(__name__)


SUMMARY_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="filter_health",
        name="Filter Health",
    ),
    SensorEntityDescription(
        key="device_consumption",
        name="Device Consumption",
        device_class=SensorDeviceClass.POWER,
    ),
    SensorEntityDescription(
        key="heating_recovered_current",
        name="Heating Recovered Current",
        device_class=SensorDeviceClass.POWER,
    ),
)

PERIPHERY_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="fut_co2_ppm_max",
        name="CO2 Max",
        device_class=SensorDeviceClass.CO2,
    ),
    SensorEntityDescription(
        key="fut_humi_indoor",
        name="Indoor Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    SensorEntityDescription(
        key="fut_temp_indoor",
        name="Indoor Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="fut_temp_outdoor",
        name="Outdoor Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JablotronFuturaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Futura sensors."""
    coordinator = entry.runtime_data

    async_add_entities(
        [
            FuturaSummarySensorEntity(coordinator, description)
            for description in SUMMARY_SENSORS
        ]
        + [
            FuturaPeripherySensorEntity(coordinator, description)
            for description in PERIPHERY_SENSORS
        ]
    )


class FuturaSummarySensorEntity(FuturaEntity, SensorEntity):
    """Futura summary sensor entity."""

    entity_description: SensorEntityDescription

    def __init__(self, coordinator, description: SensorEntityDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description

    @property
    def unique_id(self) -> str:
        return self.entity_description.key

    @property
    def available(self) -> bool:
        return self.entity_description.key in self.coordinator.data["device"]["summary"]

    @property
    def native_value(self) -> StateType | date | datetime:
        return self.coordinator.data["device"]["summary"][self.entity_description.key]

    @property
    def state_class(self) -> SensorStateClass | str | None:
        return SensorStateClass.MEASUREMENT

    @property
    def native_unit_of_measurement(self) -> str | None:
        return self.coordinator.data["device"]["summary"][
            "{}_units".format(self.entity_description.key)
        ]


class FuturaPeripherySensorEntity(FuturaEntity, SensorEntity):
    """Futura periphery sensor entity."""

    entity_description: SensorEntityDescription

    def __init__(self, coordinator, description: SensorEntityDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description

    @property
    def periphery(self) -> dict[str, Any] | None:
        peripheries = self.coordinator.data["device"]["peripheries"]
        filtered = [
            p for p in peripheries if p["id"] == self.entity_description.key
        ]
        return filtered[0] if filtered else None

    @property
    def available(self) -> bool:
        return self.periphery is not None

    @property
    def unique_id(self) -> str:
        return self.entity_description.key

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

Key changes:
- `SensorEntityDescription` defines sensors declaratively (using base class directly — no empty subclasses)
- `entry.runtime_data` replaces `hass.data[DOMAIN][entry.entry_id]`
- Typed `async_setup_entry` signature
- `unique_id` uses `entity_description.key` (same values as before — backwards compatible)
- Replaced `filter()` with list comprehension in `periphery` property

- [ ] **Step 2: Verify hassfest passes**

Run:
```bash
# If hassfest is available locally, or rely on GitHub Actions after push
python -c "import ast; ast.parse(open('custom_components/jablotron_futura/sensor.py').read()); print('Syntax OK')"
```

- [ ] **Step 3: Commit**

```bash
git add custom_components/jablotron_futura/sensor.py
git commit -m "refactor: modernize sensor.py with EntityDescription and runtime_data"
```

---

### Task 5: Modernize `binary_sensor.py` — EntityDescription & runtime_data

**Files:**
- Modify: `custom_components/jablotron_futura/binary_sensor.py`

- [ ] **Step 1: Rewrite binary_sensor.py**

Replace the entire file with:

```python
"""Binary Sensor definitions for Jablotron Futura integration."""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .__init__ import JablotronFuturaConfigEntry
from .futura import FuturaEntity

_LOGGER = logging.getLogger(__name__)


BINARY_SENSORS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="current_servo_drying",
        name="Servo Drying",
        device_class=BinarySensorDeviceClass.OPENING,
    ),
    BinarySensorEntityDescription(
        key="current_servo_bypass",
        name="Servo Bypass",
        device_class=BinarySensorDeviceClass.OPENING,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JablotronFuturaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Futura binary sensors."""
    coordinator = entry.runtime_data

    async_add_entities(
        [
            FuturaSummaryBinarySensorEntity(coordinator, description)
            for description in BINARY_SENSORS
        ]
    )


class FuturaSummaryBinarySensorEntity(FuturaEntity, BinarySensorEntity):
    """Futura summary binary sensor entity."""

    entity_description: BinarySensorEntityDescription

    def __init__(self, coordinator, description: BinarySensorEntityDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description

    @property
    def unique_id(self) -> str:
        return self.entity_description.key

    @property
    def available(self) -> bool:
        return self.entity_description.key in self.coordinator.data["device"]["summary"]

    @property
    def is_on(self) -> bool:
        return self.coordinator.data["device"]["summary"][self.entity_description.key]
```

Key changes: same pattern as sensor.py — `BinarySensorEntityDescription` (base class directly), `runtime_data`, typed signature, preserved `unique_id`.

- [ ] **Step 2: Verify syntax**

Run:
```bash
python -c "import ast; ast.parse(open('custom_components/jablotron_futura/binary_sensor.py').read()); print('Syntax OK')"
```

- [ ] **Step 3: Commit**

```bash
git add custom_components/jablotron_futura/binary_sensor.py
git commit -m "refactor: modernize binary_sensor.py with EntityDescription and runtime_data"
```

---

### Task 6: Modernize `select.py` — EntityDescription & runtime_data

**Files:**
- Modify: `custom_components/jablotron_futura/select.py`

- [ ] **Step 1: Rewrite select.py**

Replace the entire file with:

```python
"""Select definitions for Jablotron Futura integration."""
from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .__init__ import JablotronFuturaConfigEntry
from .futura import FuturaControlEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JablotronFuturaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Futura select entities."""
    coordinator = entry.runtime_data

    async_add_entities(
        [
            FuturaControlFanPowerEntity(coordinator),
            FuturaControlHumidityEntity(coordinator),
        ]
    )


class FuturaControlFanPowerEntity(FuturaControlEntity, SelectEntity):
    """Fan power control entity."""

    def __init__(self, coordinator) -> None:
        super().__init__(
            "control_fan_power", None, coordinator
        )

    @property
    def options(self) -> list[str]:
        data = self.data()
        device = self.coordinator.data["device"]
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
        await self._futura.set_control("fan_power", self.options.index(option))
        await self.coordinator.async_refresh()


class FuturaControlHumidityEntity(FuturaControlEntity, SelectEntity):
    """Humidity control entity."""

    def __init__(self, coordinator) -> None:
        super().__init__("control_humidity", None, coordinator)

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
        await self._futura.set_control("humidity", value)
        await self.coordinator.async_refresh()
```

Key changes:
- `runtime_data` access, typed `async_setup_entry`
- Replaced `filter()` with list comprehensions throughout
- Removed unused `NumberDeviceClass` import (was incorrectly imported for select entities)
- Passed `None` for device_class (selects don't use NumberDeviceClass)

- [ ] **Step 2: Verify syntax**

Run:
```bash
python -c "import ast; ast.parse(open('custom_components/jablotron_futura/select.py').read()); print('Syntax OK')"
```

- [ ] **Step 3: Commit**

```bash
git add custom_components/jablotron_futura/select.py
git commit -m "refactor: modernize select.py with runtime_data and list comprehensions"
```

---

### Task 7: Modernize `number.py` — runtime_data & typing

**Files:**
- Modify: `custom_components/jablotron_futura/number.py`

- [ ] **Step 1: Rewrite number.py**

Replace the entire file with:

```python
"""Number definitions for Jablotron Futura integration."""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .__init__ import JablotronFuturaConfigEntry
from .futura import FuturaControlEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JablotronFuturaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Futura number entities."""
    coordinator = entry.runtime_data

    async_add_entities(
        [
            FuturaControlTemperatureEntity(coordinator),
        ]
    )


class FuturaControlTemperatureEntity(FuturaControlEntity, NumberEntity):
    """Temperature control entity."""

    def __init__(self, coordinator) -> None:
        super().__init__(
            "control_temperature", NumberDeviceClass.TEMPERATURE, coordinator
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
        await self._futura.set_control("temperature", value)
        await self.coordinator.async_refresh()
```

Key changes: `runtime_data`, typed `async_setup_entry`, removed unused `DOMAIN` import.

- [ ] **Step 2: Verify syntax**

Run:
```bash
python -c "import ast; ast.parse(open('custom_components/jablotron_futura/number.py').read()); print('Syntax OK')"
```

- [ ] **Step 3: Commit**

```bash
git add custom_components/jablotron_futura/number.py
git commit -m "refactor: modernize number.py with runtime_data and typing"
```

---

### Task 8: Write Comprehensive README

**Files:**
- Rewrite: `README.md`

- [ ] **Step 1: Write README.md**

Replace the current 1-line README with the following:

```markdown
# Jablotron Futura

[![HACS Action](https://github.com/peterturza/home-assistant-jablotron-futura/actions/workflows/hacs.yaml/badge.svg)](https://github.com/peterturza/home-assistant-jablotron-futura/actions/workflows/hacs.yaml)
[![Validate with hassfest](https://github.com/peterturza/home-assistant-jablotron-futura/actions/workflows/validate.yaml/badge.svg)](https://github.com/peterturza/home-assistant-jablotron-futura/actions/workflows/validate.yaml)

Home Assistant custom integration for **Jablotron Futura** heat recovery ventilation units. Connects to the Jablotron cloud API to monitor and control your Futura recuperation system.

## Features

- Monitor indoor/outdoor temperature, humidity, and CO2 levels
- Track filter health, power consumption, and recovered heat
- Control fan speed, target temperature, and humidity mode
- View servo bypass and drying status

## Supported Entities

### Sensors

| Entity | Description | Device Class |
|--------|-------------|--------------|
| Filter Health | Current filter condition | — |
| Device Consumption | Current power consumption | Power |
| Heating Recovered Current | Heat being recovered | Power |
| CO2 Max | Maximum CO2 level (ppm) | CO2 |
| Indoor Humidity | Indoor humidity level | Humidity |
| Indoor Temperature | Indoor air temperature | Temperature |
| Outdoor Temperature | Outdoor air temperature | Temperature |

### Binary Sensors

| Entity | Description | Device Class |
|--------|-------------|--------------|
| Servo Drying | Drying servo status | Opening |
| Servo Bypass | Bypass servo status | Opening |

### Controls

| Entity | Type | Description |
|--------|------|-------------|
| Fan Power | Select | Fan speed level with airflow display |
| Humidity | Select | Humidity control mode |
| Temperature | Number | Target temperature setpoint |

## Requirements

- A Jablotron Futura recuperation unit
- A Jablotron cloud account (same credentials used in the Jablotron app)
- Home Assistant 2025.1.0 or newer

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click on **Integrations**
3. Click the **+** button and search for **Jablotron Futura**
4. Click **Install**
5. Restart Home Assistant

### Manual

1. Download the latest release from the [releases page](https://github.com/peterturza/home-assistant-jablotron-futura/releases)
2. Copy the `custom_components/jablotron_futura` folder to your Home Assistant `custom_components` directory
3. Restart Home Assistant

## Configuration

1. Go to **Settings** > **Devices & Services**
2. Click **+ Add Integration**
3. Search for **Jablotron Futura**
4. Enter your Jablotron cloud account credentials (username and password)
5. The integration will discover your Futura unit and create all entities

The integration polls the Jablotron cloud API every 5 minutes for updated data.

## Troubleshooting

**Authentication failed**: Verify your credentials work in the official Jablotron app. The integration uses the same cloud API.

**No service found**: Ensure your Futura unit is registered and visible in the Jablotron app with status "Enabled".

**Entities unavailable**: The Jablotron cloud API may be temporarily unreachable. The integration will retry automatically on the next polling interval.

## License

This project is licensed under the MIT License — see [LICENSE.md](LICENSE.md) for details.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: write comprehensive README for HACS submission"
```

---

### Task 9: Version Bump & Changelog

**Files:**
- Modify: `custom_components/jablotron_futura/manifest.json`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Bump version in manifest.json**

Change `"version": "0.2.2"` to `"version": "0.3.0"` in `custom_components/jablotron_futura/manifest.json`.

- [ ] **Step 2: Update CHANGELOG.md**

Add a new entry at the top (after the `# CHANGELOG` header):

```markdown
## Version 0.3.0

- Added comprehensive README documentation
- Fixed crash caused by missing switch platform
- Modernized code to follow current Home Assistant patterns
- Improved API error handling with proper HA exception types
- Used EntityDescription dataclasses for sensor and binary sensor entities
- Switched to ConfigEntry.runtime_data for coordinator storage
- Added proper type annotations throughout
```

- [ ] **Step 3: Commit**

```bash
git add custom_components/jablotron_futura/manifest.json CHANGELOG.md
git commit -m "chore: bump version to 0.3.0 and update changelog"
```

---

## Post-Implementation

After all tasks are complete:

1. Push to GitHub
2. Create a GitHub release for `0.3.0`
3. Verify HACS Action and Hassfest workflows pass on GitHub
4. Resubmit PR to `hacs/default` repository
