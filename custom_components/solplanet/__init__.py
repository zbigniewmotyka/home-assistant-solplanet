"""The Solplanet integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
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
from .services import async_setup_services
from .modbus import DataType

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.BINARY_SENSOR,
]
CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)
_LOGGER = logging.getLogger(__name__)

type SolplanetConfigEntry = ConfigEntry[SolplanetApi]

_LOGGER = logging.getLogger(__name__)

SERVICE_WRITE_REGISTER = "modbus_write_single_holding_register"
SERVICE_WRITE_REGISTER_SCHEMA = vol.Schema(
    {
        vol.Required("device_address"): cv.positive_int,
        vol.Required("register_address"): cv.positive_int,
        vol.Required("data_type"): vol.In(
            ["B16", "B32", "S16", "U16", "S32", "U32", "E16"]
        ),
        vol.Required("value"): vol.Coerce(int),
        vol.Required("dry_run"): cv.boolean,
    }
)


def setup_hass_services(hass: HomeAssistant, api: SolplanetApi) -> None:
    """Set up Solplanet services."""

    async def handle_write_modbus_register(call: ServiceCall) -> None:
        device_address = call.data["device_address"]
        register_address = call.data["register_address"]
        value = call.data["value"]
        data_type_str = call.data["data_type"]
        dry_run = call.data["dry_run"]

        data_type_map = {
            "B16": DataType.B16,
            "B32": DataType.B32,
            "S16": DataType.S16,
            "U16": DataType.U16,
            "S32": DataType.S32,
            "U32": DataType.U32,
            "E16": DataType.E16,
            "String": DataType.STRING,
        }
        data_type = data_type_map.get(data_type_str, DataType.S16)

        await api.modbus_write_single_holding_register(
            data_type=data_type,
            device_address=device_address,
            register_address=register_address,
            value=value,
            dry_run=dry_run,
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_WRITE_REGISTER,
        handle_write_modbus_register,
        schema=SERVICE_WRITE_REGISTER_SCHEMA,
    )


async def async_setup(hass: HomeAssistant, entry: SolplanetConfigEntry) -> bool:
    """Set up the Solplanet integration."""
    hass.data.setdefault(DOMAIN, {})
    
    # Set up services
    await async_setup_services(hass)
    
    return True


async def async_setup_entry(hass: HomeAssistant, entry: SolplanetConfigEntry) -> bool:
    """Set up Solplanet from a config entry."""

    client = SolplanetClient(
        entry.data[CONF_HOST],
        async_get_clientsession(hass),
        port=entry.data. get(CONF_PORT, DEFAULT_PORT),
        verify_ssl=entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
    )
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
            identifiers={(DOMAIN, f"{BATTERY_IDENTIFIER}_{battery_info.isn or ''}")},
            name=f"Battery ({battery_info.isn})",
            serial_number=battery_info.isn,
            sw_version=battery_info.battery.softwarever if battery_info.battery else "",
            hw_version=battery_info.battery.hardwarever if battery_info.battery else "",
        )

    for meter_isn in coordinator.data[METER_IDENTIFIER]:
        meter_info = coordinator.data[METER_IDENTIFIER][meter_isn]["info"]

        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{METER_IDENTIFIER}_{meter_isn or ''}")},
            name="Energy meter",
            serial_number=meter_info.sn,
            manufacturer=meter_info.manufactory,
            model=meter_info.name,
        )

    if len(coordinator.data[INVERTER_IDENTIFIER]) == 0:
        raise ConfigEntryNotReady("No device detected, inverter in sleep mode")

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    setup_hass_services(hass, api)

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
