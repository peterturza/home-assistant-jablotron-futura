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

    state = hass.states.get("sensor.jablotron_futura_fut_co2_ppm_max")
    assert state is not None
    assert state.state == "650.3"

    state = hass.states.get("sensor.jablotron_futura_fut_humi_indoor")
    assert state is not None
    assert state.state == "45.7"

    state = hass.states.get("sensor.jablotron_futura_fut_temp_indoor")
    assert state is not None
    assert state.state == "22.4"  # rounded from 22.35

    state = hass.states.get("sensor.jablotron_futura_fut_temp_outdoor")
    assert state is not None
    assert state.state == "8.1"  # rounded from 8.12
