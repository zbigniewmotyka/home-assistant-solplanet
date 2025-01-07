"""The Solplanet integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.device_registry as dr

from .client import SolplanetApi, SolplanetClient
from .const import (
    BATTERY_IDENTIFIER,
    CONF_INTERVAL,
    DEFAULT_INTERVAL,
    DOMAIN,
    INVERTER_IDENTIFIER,
    MANUFACTURER,
    METER_IDENTIFIER,
)
from .coordinator import SolplanetDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SELECT, Platform.SENSOR]
CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)
_LOGGER = logging.getLogger(__name__)

type SolplanetConfigEntry = ConfigEntry[SolplanetApi]  # noqa: F821

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, entry: SolplanetConfigEntry) -> bool:
    """Set up the Solplanet integration."""

    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: SolplanetConfigEntry) -> bool:
    """Set up Solplanet from a config entry."""

    client = SolplanetClient(entry.data[CONF_HOST], hass)
    api = SolplanetApi(client)
    entry.runtime_data = api

    hass.data[DOMAIN][entry.entry_id] = {}

    device_registry = dr.async_get(hass)

    coordinator = SolplanetDataUpdateCoordinator(hass, api, entry.data[CONF_INTERVAL])
    hass.data[DOMAIN][entry.entry_id]["coordinator"] = coordinator
    await coordinator.async_config_entry_first_refresh()

    for inverter_isn in coordinator.data[INVERTER_IDENTIFIER]:
        inverter_info = coordinator.data[INVERTER_IDENTIFIER][inverter_isn]["info"]

        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, inverter_info.isn or "")},
            name=f"{inverter_info.model} ({inverter_info.isn})",
            model=inverter_info.model,
            manufacturer=MANUFACTURER,
            serial_number=inverter_info.isn,
            sw_version=f"Master: {inverter_info.msw}, Slave: {inverter_info.ssw}, Security: {inverter_info.tsw}",
        )

    for battery_isn in coordinator.data[BATTERY_IDENTIFIER]:
        battery_info = coordinator.data[BATTERY_IDENTIFIER][battery_isn]["info"]

        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{BATTERY_IDENTIFIER}_{battery_info.isn or ""}")},
            name=f"Battery ({battery_info.isn})",
            serial_number=battery_info.isn,
            sw_version=battery_info.battery.softwarever if battery_info.battery else "",
            hw_version=battery_info.battery.hardwarever if battery_info.battery else "",
        )

    for meter_isn in coordinator.data[METER_IDENTIFIER]:
        meter_info = coordinator.data[METER_IDENTIFIER][meter_isn]["info"]

        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{METER_IDENTIFIER}_{meter_isn or ""}")},
            name="Energy meter",
            serial_number=meter_info.sn,
            manufacturer=meter_info.manufactory,
            model=meter_info.name,
        )

    if len(coordinator.data[INVERTER_IDENTIFIER]) == 0:
        raise ConfigEntryNotReady("No device detected, inverter in sleep mode")

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SolplanetConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug(
        "Migrating configuration from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )

    if config_entry.version > 1:
        # This means the user has downgraded from a future version
        return False

    if config_entry.version == 1:
        new_data = {**config_entry.data}
        if config_entry.minor_version < 2:
            new_data[CONF_INTERVAL] = DEFAULT_INTERVAL

        hass.config_entries.async_update_entry(
            config_entry, data=new_data, minor_version=1, version=1
        )

    _LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )

    return True
