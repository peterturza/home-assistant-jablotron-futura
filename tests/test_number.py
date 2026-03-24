"""Tests for the Jablotron Futura number platform."""
from __future__ import annotations

from homeassistant.core import HomeAssistant

from .conftest import setup_integration


async def test_temperature_number_created(hass: HomeAssistant):
    """Test that temperature number entity is created with correct value."""
    await setup_integration(hass)

    state = hass.states.get("number.jablotron_futura_control_temperature")
    assert state is not None
    assert state.state == "22.0"


async def test_temperature_number_attributes(hass: HomeAssistant):
    """Test that temperature number entity has correct attributes."""
    await setup_integration(hass)

    state = hass.states.get("number.jablotron_futura_control_temperature")
    assert state is not None
    assert state.attributes.get("min") == 15.0
    assert state.attributes.get("max") == 30.0
    assert state.attributes.get("step") == 0.5
