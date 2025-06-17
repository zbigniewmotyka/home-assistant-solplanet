"""Solplanet data coordinator."""

import asyncio
from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import (
    BatteryWorkMode,
    BatteryWorkModes,
    DataType,
    ScheduleSlot,
    SolplanetApi,
    BatterySchedule,
)
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

            # Get schedule for each battery
            battery_schedules = []
            for isn in battery_isns:
                raw_response = await self.__api.get_schedule()
                battery_schedules.append(
                    {
                        "raw": raw_response.get(
                            "raw", {}
                        ),  # Store the raw API response
                        "slots": raw_response.get(
                            "slots", {}
                        ),  # Decode using new method
                        "Pin": raw_response.get("Pin", 5000),
                        "Pout": raw_response.get("Pout", 5000),
                    }
                )
            _LOGGER.debug("Battery schedules: %s", battery_schedules)

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
                        "schedule": battery_schedules[i],
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

    async def set_battery_schedule_slots(
        self, sn: str, slots: dict[str, list[ScheduleSlot]]
    ) -> None:
        """Set battery schedule slots."""
        _LOGGER.debug("Setting schedule slots for %s: %s", sn, slots)
        current = await self.__api.get_schedule()
        raw_schedule = BatterySchedule.encode_schedule(
            slots,
            pin=current["raw"].get("Pin", 5000),
            pout=current["raw"].get("Pout", 5000),
        )
        _LOGGER.debug("Encoded schedule: %s", raw_schedule)
        await self.__api.set_schedule_slots(raw_schedule)
        await self.async_refresh()

    async def set_battery_schedule_power(
        self, sn: str, pin: int | None = None, pout: int | None = None
    ) -> None:
        """Set battery schedule power settings."""
        await self.__api.set_schedule_power(pin, pout)
        await self.async_refresh()

    async def set_battery_schedule_pin(self, sn: str, pin: int) -> None:
        """Set battery schedule pin."""
        await self.__api.set_schedule_pin(pin)
        await self.async_refresh()

    async def set_battery_schedule_pout(self, sn: str, pout: int) -> None:
        """Set battery schedule pout."""
        await self.__api.set_schedule_pout(pout)
        await self.async_refresh()

    async def modbus_write_single_holding_register(
        self,
        data_type: DataType,
        device_address: int,
        register_address: int,
        value: int,
        dry_run: bool = False,
    ) -> None:
        """Write single holding register."""
        await self.__api.modbus_write_single_holding_register(
            data_type=data_type,
            device_address=device_address,
            register_address=register_address,
            value=value,
            dry_run=dry_run,
        )
        await self.async_refresh()
