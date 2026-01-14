"""Config flow for Solplanet integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api_adapter import SolplanetApiAdapter
from .client import SolplanetClient
from .const import CONF_INTERVAL, DEFAULT_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_INTERVAL, default=DEFAULT_INTERVAL): int,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    client = SolplanetClient(data[CONF_HOST], async_get_clientsession(hass))
    api = await SolplanetApiAdapter.create(client)
    _LOGGER.info("Detected Solplanet protocol version: %s", api.version)

    try:
        await api.get_inverter_info()
    except Exception as err:
        _LOGGER.debug("Exception occurred during adding device", exc_info=err)
        raise CannotConnect from err
    else:
        return {
            "title": data[CONF_HOST],
        }


class SolplanetConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solplanet."""

    VERSION = 1
    MINOR_VERSION = 2

    @staticmethod
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SolplanetOptionsFlow:
        """Get the options flow for this handler."""
        return SolplanetOptionsFlow(config_entry)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])

        if user_input is not None:
            # Update the config entry with new interval
            new_data = {**entry.data, CONF_INTERVAL: user_input[CONF_INTERVAL]}
            self.hass.config_entries.async_update_entry(entry, data=new_data)
            await self.hass.config_entries.async_reload(entry.entry_id)
            return self.async_abort(reason="reconfigure_successful")

        # Show form with current interval value
        current_interval = entry.data.get(CONF_INTERVAL, DEFAULT_INTERVAL)
        schema = vol.Schema(
            {
                vol.Required(CONF_INTERVAL, default=current_interval): int,
            }
        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["title"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class SolplanetOptionsFlow(OptionsFlow):
    """Handle options flow for Solplanet."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        # HA exposes OptionsFlow.config_entry as a read-only property in newer versions.
        # Store the entry on our own attribute.
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            # Update the config entry data with new interval
            new_data = {
                **self._config_entry.data,
                CONF_INTERVAL: user_input[CONF_INTERVAL],
            }
            self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)
            await self.hass.config_entries.async_reload(self._config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        # Show form with current interval value
        current_interval = self._config_entry.data.get(CONF_INTERVAL, DEFAULT_INTERVAL)
        schema = vol.Schema(
            {
                vol.Required(CONF_INTERVAL, default=current_interval): int,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
