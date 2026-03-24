"""Tests for the Jablotron Futura select platform."""
from __future__ import annotations

from homeassistant.core import HomeAssistant

from .conftest import setup_integration


async def test_fan_power_select_created(hass: HomeAssistant):
    """Test that fan power select entity is created."""
    await setup_integration(hass)

    state = hass.states.get("select.jablotron_futura_control_fan_power")
    assert state is not None


async def test_humidity_select_created(hass: HomeAssistant):
    """Test that humidity select entity is created with correct option."""
    await setup_integration(hass)

    state = hass.states.get("select.jablotron_futura_control_humidity")
    assert state is not None
    assert state.state == "Normal"  # value "normal" matches option with title "Normal"
