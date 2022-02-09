"""Errors for the Futura component."""
from homeassistant.exceptions import HomeAssistantError


class FuturaError(HomeAssistantError):
    """Base class for Futura exceptions."""


class ApiAuthError(FuturaError):
    """Auth error"""


class ServiceNotFoundError(FuturaError):
    """Service is not available."""
