"""Fixtures for Jablotron Futura tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.jablotron_futura.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
)

@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests."""
    yield


MOCK_USERNAME = "test@example.com"
MOCK_PASSWORD = "testpassword"

MOCK_CONFIG = {
    CONF_USERNAME: MOCK_USERNAME,
    CONF_PASSWORD: MOCK_PASSWORD,
}

MOCK_SERVICE_LIST_RESPONSE = {
    "data": {
        "services": [
            {
                "service-id": 12345,
                "visible": True,
                "status": "ENABLED",
                "service-type": "FUTURA2",
            }
        ]
    }
}

MOCK_DEVICE_RESPONSE = {
    "device": {
        "id": "12345",
        "type": "Futura 2",
        "details": {
            "hw_revision": "1.0",
            "fw_version": "2.5.1",
            "serial_no": "SN123456789",
        },
        "rooms": [{"id": "room1"}],
        "summary": {
            "filter_health": 85,
            "filter_health_units": "%",
            "device_consumption": 45.2,
            "device_consumption_units": "W",
            "heating_recovered_current": 120.5,
            "heating_recovered_current_units": "W",
            "current_servo_drying": False,
            "current_servo_bypass": True,
            "airflow": [50, 100, 150, 200],
            "airflow_units": "m3/h",
        },
        "peripheries": [
            {
                "id": "fut_co2_ppm_max",
                "extended_properties": {"value": 650.3, "units": "ppm"},
            },
            {
                "id": "fut_humi_indoor",
                "extended_properties": {"value": 45.7, "units": "%"},
            },
            {
                "id": "fut_temp_indoor",
                "extended_properties": {"value": 22.35, "units": "\u00b0C"},
            },
            {
                "id": "fut_temp_outdoor",
                "extended_properties": {"value": 8.12, "units": "\u00b0C"},
            },
        ],
        "data": {
            "controls": [
                {
                    "id": "control_fan_power",
                    "extended_properties": {
                        "value": 2,
                        "min": 0,
                        "max": 5,
                    },
                },
                {
                    "id": "control_humidity",
                    "extended_properties": {
                        "value": "normal",
                        "options": [
                            {"id": "low", "title": "Low"},
                            {"id": "normal", "title": "Normal"},
                            {"id": "high", "title": "High"},
                        ],
                    },
                },
                {
                    "id": "control_temperature",
                    "extended_properties": {
                        "value": 22.0,
                        "min": 15.0,
                        "max": 30.0,
                        "step": 0.5,
                        "units": "\u00b0C",
                    },
                },
            ]
        },
    }
}


class MockResponse:
    """Mock aiohttp response."""

    def __init__(self, json_data, status=200):
        self._json_data = json_data
        self.status = status

    async def json(self):
        return self._json_data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


def create_mock_session(
    auth_status=200,
    service_list_response=None,
    device_response=None,
    set_device_status=200,
):
    """Create a mock aiohttp session that simulates the Jablotron API."""
    if service_list_response is None:
        service_list_response = MOCK_SERVICE_LIST_RESPONSE
    if device_response is None:
        device_response = MOCK_DEVICE_RESPONSE

    def mock_post(url, **kwargs):
        if "userAuthorize" in url:
            return MockResponse({}, status=auth_status)
        elif "serviceListGet" in url:
            return MockResponse(service_list_response)
        elif "getDevice" in url:
            return MockResponse(device_response)
        elif "setDevice" in url:
            return MockResponse({}, status=set_device_status)
        return MockResponse({}, status=404)

    mock_session = AsyncMock()
    mock_session.post = mock_post
    return mock_session


@pytest.fixture
def mock_session():
    """Fixture providing a mock aiohttp session with successful responses."""
    return create_mock_session()


@pytest.fixture
def mock_session_auth_failure():
    """Fixture providing a mock session that fails authentication."""
    return create_mock_session(auth_status=401)


@pytest.fixture
def mock_setup(mock_session):
    """Fixture that patches aiohttp_client to return mock session."""
    with patch(
        "custom_components.jablotron_futura.futura.aiohttp_client.async_get_clientsession",
        return_value=mock_session,
    ) as mock_client:
        yield mock_client


def create_mock_entry():
    """Create a MockConfigEntry for the integration."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Futura 2",
        data=MOCK_CONFIG,
    )


async def setup_integration(hass: HomeAssistant, mock_session=None):
    """Set up the integration with a mock session."""
    if mock_session is None:
        mock_session = create_mock_session()

    entry = create_mock_entry()
    entry.add_to_hass(hass)

    with patch(
        "custom_components.jablotron_futura.futura.aiohttp_client.async_get_clientsession",
        return_value=mock_session,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
