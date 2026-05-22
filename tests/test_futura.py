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
