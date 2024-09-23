"""Solplanet data coordinator."""

import asyncio
from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import SolplanetApi
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class SolplanetInverterDataCoordinator(DataUpdateCoordinator):
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
        _LOGGER.debug("Updating data")
        try:
            async with asyncio.timeout(10):
                inverters = await self.__api.get_inverter_info()
                isns = [x.isn for x in inverters.inv]
                inverters_data = await asyncio.gather(
                    *[self.__api.get_inverter_data(isn) for isn in isns]
                )
                return {isns[i]: inverters_data[i] for i in range(len(isns))}

        except TimeoutError as err:
            raise UpdateFailed("Timeout fetching data from API") from err
        except Exception as err:
            raise UpdateFailed(f"Error fetching data from API: {err}") from err
