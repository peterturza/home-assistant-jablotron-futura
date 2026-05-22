"""Tests for the Jablotron Futura sensor platform."""
from __future__ import annotations

from homeassistant.core import HomeAssistant

from .conftest import setup_integration


async def test_summary_sensors_created(hass: HomeAssistant):
    """Test that summary sensor entities are created."""
    await setup_integration(hass)

    state = hass.states.get("sensor.jablotron_futura_filter_health")
    assert state is not None
    assert state.state == "85"

    state = hass.states.get("sensor.jablotron_futura_device_consumption")
    assert state is not None
    assert state.state == "45.2"

    state = hass.states.get("sensor.jablotron_futura_heating_recovered_current")
    assert state is not None
    assert state.state == "120.5"


async def test_periphery_sensors_created(hass: HomeAssistant):
    """Test that periphery sensor entities are created."""
    await setup_integration(hass)

    state = hass.states.get("sensor.jablotron_futura_co2_max")
    assert state is not None
    assert state.state == "650.3"

    state = hass.states.get("sensor.jablotron_futura_indoor_humidity")
    assert state is not None
    assert state.state == "45.7"

    state = hass.states.get("sensor.jablotron_futura_indoor_temperature")
    assert state is not None
    assert state.state == "22.4"  # rounded from 22.35

    state = hass.states.get("sensor.jablotron_futura_outdoor_temperature")
    assert state is not None
    assert state.state == "8.1"  # rounded from 8.12


async def test_summary_sensor_has_friendly_name(hass: HomeAssistant):
    """Summary sensor should expose a friendly name from its EntityDescription."""
    await setup_integration(hass)

    state = hass.states.get("sensor.jablotron_futura_filter_health")
    assert state is not None
    assert state.attributes["friendly_name"] == "jablotron_futura Filter Health"


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
