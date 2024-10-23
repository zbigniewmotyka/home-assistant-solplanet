"""Solplanet data coordinator."""

import asyncio
from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import SolplanetApi
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class SolplanetInverterDataUpdateCoordinator(DataUpdateCoordinator):
    """Solplanet inverter coordinator."""

    def __init__(
        self, hass: HomeAssistant, api: SolplanetApi, update_interval: int
    ) -> None:
        """Create instance of solplanet coordinator."""
        self.__api = api

        _LOGGER.debug("Creating inverter coordinator")

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval),
        )

    async def _async_update_data(self):
        """Fetch data from REST API."""
        try:
            _LOGGER.debug("Updating inverters data")
            inverters = await self.__api.get_inverter_info()
            isns = [x.isn for x in inverters.inv]
            inverters_data = await asyncio.gather(
                *[self.__api.get_inverter_data(isn) for isn in isns]
            )
            _LOGGER.debug("Inverters data updated")
            return {isns[i]: inverters_data[i] for i in range(len(isns))}

        except Exception as err:
            _LOGGER.debug(err, stack_info=True, exc_info=True)
            raise UpdateFailed(f"Error fetching data from API: {err}") from err


class SolplanetBatteryDataUpdateCoordinator(DataUpdateCoordinator):
    """Solplanet battery coordinator."""

    def __init__(
        self, hass: HomeAssistant, api: SolplanetApi, update_interval: int
    ) -> None:
        """Create instance of solplanet battery coordinator."""
        self.__api = api

        _LOGGER.debug("Creating battery coordinator")

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval),
        )

    async def _async_update_data(self):
        """Fetch data from REST API."""
        try:
            _LOGGER.debug("Updating battery data")
            battery = await self.__api.get_battery_info()
            isns = [battery.isn]
            battery_data = await asyncio.gather(
                *[self.__api.get_battery_data(isn) for isn in isns]
            )
            _LOGGER.debug("Battery data updated")
            return {isns[i]: battery_data[i] for i in range(len(isns))}

        except Exception as err:
            _LOGGER.debug(err, stack_info=True, exc_info=True)
            raise UpdateFailed(f"Error fetching data from API: {err}") from err
