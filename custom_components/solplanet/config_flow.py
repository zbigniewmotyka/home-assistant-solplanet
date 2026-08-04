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

from .client import SolplanetApi, SolplanetClient
from .const import (
    CONF_INTERVAL,
    CONF_PORT,
    CONF_USE_HTTPS,
    DEFAULT_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_USE_HTTPS,
    DOMAIN,
    LEGACY_PORT,
    LEGACY_USE_HTTPS,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.All(
            int, vol.Range(min=1, max=65535)
        ),
        vol.Optional(CONF_USE_HTTPS, default=DEFAULT_USE_HTTPS): bool,
        vol.Required(CONF_INTERVAL, default=DEFAULT_INTERVAL): int,
    }
)


async def _try_connect(
    hass: HomeAssistant, host: str, port: int, use_https: bool
) -> bool:
    """Return True if ``get_inverter_info`` succeeds against ``host:port``."""
    client = SolplanetClient(
        host, async_get_clientsession(hass), port=port, use_https=use_https
    )
    api = SolplanetApi(client)
    try:
        await api.get_inverter_info()
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug(
            "Connect attempt failed for %s://%s:%s (%s)",
            "https" if use_https else "http",
            host,
            port,
            err,
        )
        return False
    return True


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Tries the user-supplied scheme/port first; on failure falls back to
    the legacy HTTP 8484 endpoint so the integration works on both
    newer (HTTPS 443) and older (HTTP 8484) Ai-Dongle firmware versions
    without manual intervention.
    """
    host = data[CONF_HOST]
    port = data.get(CONF_PORT, DEFAULT_PORT)
    use_https = data.get(CONF_USE_HTTPS, DEFAULT_USE_HTTPS)

    if await _try_connect(hass, host, port, use_https):
        return {
            "title": host,
            CONF_PORT: port,
            CONF_USE_HTTPS: use_https,
        }

    # Fallback to the legacy scheme.
    legacy_port, legacy_https = LEGACY_PORT, LEGACY_USE_HTTPS
    if (legacy_port, legacy_https) == (port, use_https):
        # User already chose the legacy endpoint; nothing to fall back to.
        raise CannotConnect

    if await _try_connect(hass, host, legacy_port, legacy_https):
        return {
            "title": host,
            CONF_PORT: legacy_port,
            CONF_USE_HTTPS: legacy_https,
        }

    raise CannotConnect


class SolplanetConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solplanet."""

    VERSION = 1
    MINOR_VERSION = 3

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
            new_data = {
                **entry.data,
                CONF_INTERVAL: user_input[CONF_INTERVAL],
                CONF_PORT: user_input[CONF_PORT],
                CONF_USE_HTTPS: user_input[CONF_USE_HTTPS],
            }
            self.hass.config_entries.async_update_entry(entry, data=new_data)
            await self.hass.config_entries.async_reload(entry.entry_id)
            return self.async_abort(reason="reconfigure_successful")

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_PORT,
                    default=entry.data.get(CONF_PORT, DEFAULT_PORT),
                ): vol.All(int, vol.Range(min=1, max=65535)),
                vol.Required(
                    CONF_USE_HTTPS,
                    default=entry.data.get(CONF_USE_HTTPS, DEFAULT_USE_HTTPS),
                ): bool,
                vol.Required(
                    CONF_INTERVAL,
                    default=entry.data.get(CONF_INTERVAL, DEFAULT_INTERVAL),
                ): int,
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
                # Merge auto-detected port/use_https into the persisted data.
                data = {**user_input, **info}
                return self.async_create_entry(title=info["title"], data=data)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class SolplanetOptionsFlow(OptionsFlow):
    """Handle options flow for Solplanet."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            new_data = {**self.config_entry.data, CONF_INTERVAL: user_input[CONF_INTERVAL]}
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        current_interval = self.config_entry.data.get(CONF_INTERVAL, DEFAULT_INTERVAL)
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
