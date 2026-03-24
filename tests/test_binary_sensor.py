"""Tests for the Jablotron Futura binary sensor platform."""
from __future__ import annotations

from homeassistant.core import HomeAssistant

from .conftest import setup_integration


async def test_binary_sensors_created(hass: HomeAssistant):
    """Test that binary sensor entities are created with correct states."""
    await setup_integration(hass)

    state = hass.states.get("binary_sensor.jablotron_futura_current_servo_drying")
    assert state is not None
    assert state.state == "off"  # False in mock data

    state = hass.states.get("binary_sensor.jablotron_futura_current_servo_bypass")
    assert state is not None
    assert state.state == "on"  # True in mock data
