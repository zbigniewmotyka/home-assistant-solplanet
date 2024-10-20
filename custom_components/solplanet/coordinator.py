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
    """Solplanet coordinator."""

    def __init__(self, hass: HomeAssistant, api: SolplanetApi) -> None:
        """Create instance of solplanet coordinator."""
        self.__api = api

        _LOGGER.debug("Creating coordinator")

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
        )

    async def _async_update_data(self):
        """Fetch data from REST API."""
        try:
            _LOGGER.debug("Updating data")
            inverters = await self.__api.get_inverter_info()
            isns = [x.isn for x in inverters.inv]
            inverters_data = await asyncio.gather(
                *[self.__api.get_inverter_data(isn) for isn in isns]
            )
            _LOGGER.debug("Data updated")
            return {isns[i]: inverters_data[i] for i in range(len(isns))}

        except Exception as err:
            _LOGGER.debug(err, stack_info=True, exc_info=True)
            raise UpdateFailed(f"Error fetching data from API: {err}") from err
