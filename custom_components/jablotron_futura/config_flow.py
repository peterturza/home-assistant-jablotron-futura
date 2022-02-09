"""Config flow for Jablotron Futura integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from .errors import ServiceNotFoundError
from .futura import Futura
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_PASSWORD, CONF_USERNAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    futura = Futura(hass, data[CONF_USERNAME], data[CONF_PASSWORD])
    await futura.sync()
    central_unit = futura.central_unit()
    if not central_unit:
        raise ServiceNotFoundError

    # Return info that you want to store in the config entry.
    return {"title": central_unit.model}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Jablotron Futura."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.exception(ex)
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
