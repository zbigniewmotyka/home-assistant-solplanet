"""The Solplanet integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.device_registry as dr

from .client import SolplanetApi, SolplanetClient
from .const import DOMAIN
from .coordinator import SolplanetInverterDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]
CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

type SolplanetConfigEntry = ConfigEntry[SolplanetApi]  # noqa: F821


async def async_setup(hass: HomeAssistant, entry: SolplanetConfigEntry) -> bool:
    """Set up the Solplanet integration."""

    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: SolplanetConfigEntry) -> bool:
    """Set up Solplanet from a config entry."""

    client = SolplanetClient(entry.data[CONF_HOST], hass)
    api = SolplanetApi(client)

    coordinator = SolplanetInverterDataUpdateCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    entry.runtime_data = api

    inverters_info = await api.get_inverter_info()

    device_registry = dr.async_get(hass)

    for inverter_info in inverters_info.inv:
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, inverter_info.isn)},
            name=inverter_info.model + " (" + inverter_info.isn + ")",
            model=inverter_info.model,
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SolplanetConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
