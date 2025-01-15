"""Solplanet data coordinator."""

import asyncio
from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import BatteryWorkMode, BatteryWorkModes, SolplanetApi
from .const import BATTERY_IDENTIFIER, DOMAIN, INVERTER_IDENTIFIER, METER_IDENTIFIER

_LOGGER = logging.getLogger(__name__)


class SolplanetDataUpdateCoordinator(DataUpdateCoordinator):
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
            inverters_info = await self.__api.get_inverter_info()

            isns = [x.isn for x in inverters_info.inv]
            inverters_data = await asyncio.gather(
                *[self.__api.get_inverter_data(isn) for isn in isns]
            )

            battery_isns = [x.isn for x in inverters_info.inv if x.isStorage()]
            battery_data = await asyncio.gather(
                *[self.__api.get_battery_data(isn) for isn in battery_isns]
            )
            battery_info = await asyncio.gather(
                *[self.__api.get_battery_info(isn) for isn in battery_isns]
            )

            meter = None
            meter_sn = isns[0] if len(isns) > 0 else None
            try:
                meter_data = await self.__api.get_meter_data()
                meter_info = await self.__api.get_meter_info()
                meter = {"data": meter_data, "info": meter_info}

                if meter_info.sn is not None:
                    meter_sn = meter_info.sn
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug(err, stack_info=True, exc_info=True)

            _LOGGER.debug("Inverters data updated")
            return {
                INVERTER_IDENTIFIER: {
                    isns[i]: {"data": inverters_data[i], "info": inverters_info.inv[i]}
                    for i in range(len(isns))
                },
                BATTERY_IDENTIFIER: {
                    battery_isns[i]: {
                        "data": battery_data[i],
                        "info": battery_info[i],
                        "work_modes": {
                            "all": BatteryWorkModes().get_all_modes(
                                battery_info[i].type, battery_info[i].mod_r
                            ),
                            "selected": BatteryWorkModes().get_mode(
                                battery_info[i].type, battery_info[i].mod_r
                            ),
                        },
                    }
                    for i in range(len(battery_isns))
                },
                METER_IDENTIFIER: {meter_sn: meter} if meter and meter_sn else {},
            }

        except Exception as err:
            _LOGGER.debug(err, stack_info=True, exc_info=True)
            raise UpdateFailed(f"Error fetching data from API: {err}") from err

    async def set_battery_work_mode(self, sn: str, mode: BatteryWorkMode) -> None:
        """Set battery work mode."""
        await self.__api.set_battery_work_mode(sn, mode)
        await self.async_refresh()

    async def set_battery_soc_min(self, sn: str, value: int) -> None:
        """Set battery soc min."""
        await self.__api.set_battery_soc_min(sn, value)
        await self.async_refresh()

    async def set_battery_soc_max(self, sn: str, value: int) -> None:
        """Set battery soc max."""
        await self.__api.set_battery_soc_max(sn, value)
        await self.async_refresh()
