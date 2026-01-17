"""Solplanet data coordinator."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api_adapter import SolplanetApiAdapter
from .client import BatterySchedule, BatteryWorkMode, BatteryWorkModes, ScheduleSlot
from .const import (
    BATTERY_IDENTIFIER,
    DOMAIN,
    DONGLE_IDENTIFIER,
    INVERTER_IDENTIFIER,
    METER_IDENTIFIER,
)
from .modbus import DataType

_LOGGER = logging.getLogger(__name__)


class SolplanetDataUpdateCoordinator(DataUpdateCoordinator):
    """Solplanet inverter coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: SolplanetApiAdapter,
        config_entry_id: str,
        update_interval: int,
    ) -> None:
        """Create instance of solplanet coordinator."""
        self.__api = api
        self.config_entry_id = config_entry_id

        # Some dongles/inverters are very sensitive to concurrent requests.
        # Serialize update cycles to reduce timeouts/flapping.
        self._update_lock = asyncio.Lock()

        _LOGGER.debug("Creating inverter coordinator")

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval),
        )

    async def _async_update_data(self):
        """Fetch data from REST API.

        The inverter dongle can be slow and may not tolerate concurrent requests well.
        We intentionally:
        - serialize update cycles with a lock,
        - avoid large `asyncio.gather()` fan-outs,
        - degrade gracefully (keep previous payload sections) where possible to reduce flapping.
        """
        async with self._update_lock:
            previous: dict = self.data or {}

            # Dongle diagnostics (V2 only). These endpoints are served by the dongle itself.
            prev_dongles: dict = (
                previous.get(DONGLE_IDENTIFIER, {}) if isinstance(previous, dict) else {}
            )
            dongle_payload: dict[str, dict] = prev_dongles

            if self.__api.version == "v2":
                try:
                    dongle_info = await self.__api.client.get("getdev.cgi")
                    dongle_id = (
                        dongle_info.get("psn")
                        or dongle_info.get("ethmac")
                        or dongle_info.get("wlanmac")
                        or "unknown"
                    )

                    # Network info (LAN/WLAN). The sample shows `info=2` for LAN.
                    try:
                        network_info = await self.__api.client.get("wlanget.cgi?info=2")
                    except Exception as err:  # noqa: BLE001
                        _LOGGER.debug("Failed fetching dongle network info: %s", err, exc_info=True)
                        network_info = prev_dongles.get(dongle_id, {}).get("network")

                    # Warnings (device=1). Observed behavior: 404 means no warnings.
                    warnings: dict | None = None
                    try:
                        warnings = await self.__api.client.get("getdevdata.cgi?device=1")
                    except Exception as err:  # noqa: BLE001
                        # Keep it lightweight: treat failures (including 404) as "no data".
                        _LOGGER.debug("Failed fetching dongle warnings: %s", err, exc_info=True)
                        warnings = prev_dongles.get(dongle_id, {}).get("warnings")

                    dongle_payload = {
                        dongle_id: {
                            "data": dongle_info,
                            "network": network_info,
                            "warnings": warnings,
                        }
                    }
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("Failed fetching dongle info: %s", err, exc_info=True)

            try:
                _LOGGER.debug("Updating inverters data")
                inverters_info = await self.__api.get_inverter_info()
            except Exception as err:
                _LOGGER.debug(err, stack_info=True, exc_info=True)
                raise UpdateFailed(f"Error fetching inverter info: {err}") from err

            isns: list[str] = [x.isn for x in inverters_info.inv if x.isn]
            inverter_payload: dict[str, dict] = {}

            # Inverter power is controlled via Modbus RTU over `fdbg.cgi`:
            # - Read holding register offset 0x00C8 (200), quantity 1 (function 0x03)
            # - Write holding register offset 0x00C8 with 0/1 (function 0x06)
            # The Modbus helper expects full holding register numbers (40001 + offset).
            inverter_power_on: bool | None = None
            try:
                power_reg = await self.__api.modbus_read_holding_registers(
                    data_type=DataType.U16,
                    device_address=3,
                    register_address=40201,  # 40001 + 200
                    register_count=1,
                )
                if isinstance(power_reg, list):
                    power_reg = power_reg[0] if power_reg else None
                if isinstance(power_reg, int):
                    inverter_power_on = power_reg == 1
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Failed reading inverter power register: %s", err, exc_info=True)

            prev_inverters: dict = (
                previous.get(INVERTER_IDENTIFIER, {}) if isinstance(previous, dict) else {}
            )
            for idx, isn in enumerate(isns):
                info = inverters_info.inv[idx]
                prev_more_settings = prev_inverters.get(isn, {}).get("more_settings", {})

                more_settings = (
                    {"power_on": inverter_power_on}
                    if inverter_power_on is not None
                    else prev_more_settings
                )

                try:
                    data = await self.__api.get_inverter_data(isn)
                    inverter_payload[isn] = {
                        "data": data,
                        "info": info,
                        "more_settings": more_settings,
                    }
                except Exception as err:  # noqa: BLE001
                    # Keep last known inverter data on transient failures.
                    _LOGGER.debug(
                        "Failed fetching inverter data for %s: %s", isn, err, exc_info=True
                    )
                    if isn in prev_inverters:
                        inverter_payload[isn] = prev_inverters[isn]
                    else:
                        inverter_payload[isn] = {
                            "data": None,
                            "info": info,
                            "more_settings": more_settings,
                        }

            # Batteries (V2 only)
            battery_payload: dict[str, dict] = {}
            prev_batteries: dict = (
                previous.get(BATTERY_IDENTIFIER, {}) if isinstance(previous, dict) else {}
            )

            try:
                battery_isns: list[str] = [
                    x.isn for x in inverters_info.inv if x.isStorage() and x.isn
                ]
                schedule: dict | None = None

                # Battery "More Settings" are controlled via Modbus RTU over `fdbg.cgi` using holding-register
                # offsets: 1500 power, 1501 sleep, 1502 LED color index, 1503 LED brightness.
                # The Modbus helper expects full holding register numbers (40001 + offset).
                more_settings: dict | None = None

                if battery_isns:
                    # getdefine.cgi is global (no sn parameter) so fetch it once
                    try:
                        schedule = await self.__api.get_schedule()
                    except Exception as err:  # noqa: BLE001
                        _LOGGER.debug("Failed fetching schedule: %s", err, exc_info=True)

                    # Read the 4-register block once and apply to all battery entries.
                    try:
                        regs = await self.__api.modbus_read_holding_registers(
                            data_type=DataType.U16,
                            device_address=3,
                            register_address=41501,  # 40001 + 1500
                            register_count=4,
                        )
                        if isinstance(regs, list) and len(regs) >= 4:
                            # regs are [power, sleep_flag, led_color, led_brightness]
                            power_reg = int(regs[0] or 0)
                            sleep_reg = int(regs[1] or 0)
                            color_reg = int(regs[2] or 0)
                            brightness_reg = int(regs[3] or 0)
                            more_settings = {
                                "power_on": power_reg == 1,
                                # Sleep flag semantics: 0 = enabled, 1 = disabled
                                "sleep_enabled": sleep_reg == 0,
                                "led_color_index": color_reg,
                                "led_brightness": brightness_reg,
                            }
                    except Exception as err:  # noqa: BLE001
                        _LOGGER.debug("Failed reading modbus More Settings: %s", err, exc_info=True)

                    for isn in battery_isns:
                        try:
                            data = await self.__api.get_battery_data(isn)
                            info = await self.__api.get_battery_info(isn)
                            battery_payload[isn] = {
                                "data": data,
                                "info": info,
                                "work_modes": {
                                    "all": BatteryWorkModes().get_all_modes(
                                        info.type, info.mod_r
                                    ),
                                    "selected": BatteryWorkModes().get_mode(
                                        info.type, info.mod_r
                                    ),
                                },
                                "schedule": schedule
                                or prev_batteries.get(isn, {}).get("schedule", {}),
                                "more_settings": more_settings
                                or prev_batteries.get(isn, {}).get("more_settings", {}),
                            }
                        except Exception as err:  # noqa: BLE001
                            _LOGGER.debug(
                                "Failed fetching battery data for %s: %s",
                                isn,
                                err,
                                exc_info=True,
                            )
                            if isn in prev_batteries:
                                battery_payload[isn] = prev_batteries[isn]
                            else:
                                # Provide minimal structure so entities can exist without crashing
                                battery_payload[isn] = {
                                    "data": None,
                                    "info": prev_batteries.get(isn, {}).get("info"),
                                    "work_modes": prev_batteries.get(isn, {}).get(
                                        "work_modes", {"all": [], "selected": None}
                                    ),
                                    "schedule": schedule or {},
                                    "more_settings": more_settings or {},
                                }
            except NotImplementedError:
                _LOGGER.info("Battery operations not supported (V1 protocol)")
                battery_payload = {}

            # Meter
            meter_payload: dict[str, dict] = {}
            prev_meter: dict = (
                previous.get(METER_IDENTIFIER, {}) if isinstance(previous, dict) else {}
            )
            meter_sn: str | None = isns[0] if isns else None

            # V2-only: additional meter inventory + live values via `POST /getting.cgi`.
            # The response can list multiple meters (main + sub). Live values are attached to the
            # discovered main meter because `get_meter_data_rsp` does not include a meter selector.
            app_meters: dict[str, dict] = {}
            app_primary_sn: str | None = None
            if self.__api.version == "v2":
                try:
                    dev_info_rsp = await self.__api.client.post(
                        "getting.cgi",
                        {"cmd": "get_app_dev_info_req", "payload": {"type": [4]}},
                    )
                    if dev_info_rsp.get("status") == 200:
                        payload = dev_info_rsp.get("payload") or {}
                        main_meters = payload.get("mainMeter") or []
                        sub_meters = payload.get("subMeter") or []

                        if main_meters and isinstance(main_meters[0], dict):
                            app_primary_sn = main_meters[0].get("sn")

                        for meter in [*main_meters, *sub_meters]:
                            if not isinstance(meter, dict):
                                continue
                            sn = meter.get("sn") or f"addr_{meter.get('address')}"
                            app_meters.setdefault(sn, {})["app_info"] = meter
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("Failed fetching app meter info: %s", err, exc_info=True)

                try:
                    meter_data_rsp = await self.__api.client.post(
                        "getting.cgi",
                        {"cmd": "get_meter_data_req"},
                    )
                    if meter_data_rsp.get("status") == 200:
                        app_data = meter_data_rsp.get("payload") or {}

                        # The response does not include a meter SN, so attach it to the primary meter
                        # (main meter) when we know it.
                        target_sn = app_primary_sn or (next(iter(app_meters)) if app_meters else None)
                        if target_sn:
                            app_meters.setdefault(target_sn, {})["app_data"] = app_data
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("Failed fetching app meter data: %s", err, exc_info=True)

                # V2 meter config (power limit / zero export)
                # - get_meter_req gives the control configuration
                # - get_meter_power_req gives rated current + metering method
                # These appear to be global for the primary meter.
                try:
                    meter_req_rsp = await self.__api.client.post(
                        "getting.cgi",
                        {"cmd": "get_meter_req"},
                    )
                    if meter_req_rsp.get("status") == 200:
                        target_sn = app_primary_sn or (next(iter(app_meters)) if app_meters else None)
                        if target_sn:
                            app_meters.setdefault(target_sn, {})["meter_req"] = (
                                meter_req_rsp.get("payload") or {}
                            )
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("Failed fetching meter config (get_meter_req): %s", err, exc_info=True)

                try:
                    meter_power_rsp = await self.__api.client.post(
                        "getting.cgi",
                        {"cmd": "get_meter_power_req"},
                    )
                    if meter_power_rsp.get("status") == 200:
                        target_sn = app_primary_sn or (next(iter(app_meters)) if app_meters else None)
                        if target_sn:
                            app_meters.setdefault(target_sn, {})["meter_power"] = (
                                meter_power_rsp.get("payload") or {}
                            )
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug(
                        "Failed fetching meter power config (get_meter_power_req): %s",
                        err,
                        exc_info=True,
                    )

            # V2: prefer app-protocol (`getting.cgi`) meters and do not create legacy device=3 meters.
            if self.__api.version == "v2":
                if app_meters:
                    for sn, entry in app_meters.items():
                        meter_payload[sn] = {"app_info": entry.get("app_info")}
                        # Only include app_data on the meter we can currently populate.
                        if entry.get("app_data") is not None:
                            meter_payload[sn]["app_data"] = entry.get("app_data")
                        if entry.get("meter_req") is not None:
                            meter_payload[sn]["meter_req"] = entry.get("meter_req")
                        if entry.get("meter_power") is not None:
                            meter_payload[sn]["meter_power"] = entry.get("meter_power")
                else:
                    # Keep previous payload on transient failures.
                    meter_payload = prev_meter
            else:
                # V1: use legacy meter endpoints.
                try:
                    meter_data = await self.__api.get_meter_data()
                    meter_info = await self.__api.get_meter_info()
                    meter = {"data": meter_data, "info": meter_info}

                    if meter_info.sn is not None:
                        meter_sn = meter_info.sn
                    if meter_sn:
                        meter_payload = {meter_sn: meter}
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("Failed fetching meter data: %s", err, exc_info=True)
                    meter_payload = prev_meter

            _LOGGER.debug("Inverters data updated")
            return {
                DONGLE_IDENTIFIER: dongle_payload,
                INVERTER_IDENTIFIER: inverter_payload,
                BATTERY_IDENTIFIER: battery_payload,
                METER_IDENTIFIER: meter_payload,
            }

    async def set_inverter_power(self, on: bool) -> None:
        """Set inverter power (offset 200). 1=on, 0=off."""
        try:
            await self.__api.modbus_write_single_holding_register(
                data_type=DataType.U16,
                device_address=3,
                register_address=40201,  # 40001 + 200
                value=1 if on else 0,
                dry_run=False,
            )
            await self.async_refresh()
        except NotImplementedError as err:
            raise HomeAssistantError(
                "Modbus operations are not supported with V1 protocol"
            ) from err

    async def dongle_sync_time(self) -> None:
        """Sync dongle time (device=1, action=settime) using Home Assistant local time."""
        if self.__api.version != "v2":
            raise HomeAssistantError("Dongle operations are not supported with V1 protocol")

        from homeassistant.util import dt as dt_util

        now = dt_util.now()
        payload = {
            "device": 1,
            "action": "settime",
            "value": {"time": now.strftime("%Y%m%d%H%M%S")},
        }

        try:
            await self.__api.client.post("setting.cgi", payload)
            await self.async_refresh()
        except Exception as err:  # noqa: BLE001
            raise HomeAssistantError(f"Failed to sync dongle time: {err}") from err

    async def dongle_reboot(self) -> None:
        """Reboot dongle (device=1, action=operation, reboot=1)."""
        if self.__api.version != "v2":
            raise HomeAssistantError("Dongle operations are not supported with V1 protocol")

        payload = {
            "device": 1,
            "action": "operation",
            "value": {"reboot": 1},
        }

        try:
            await self.__api.client.post("setting.cgi", payload)
        except Exception as err:  # noqa: BLE001
            raise HomeAssistantError(f"Failed to reboot dongle: {err}") from err

    async def set_meter_power_limit(self, payload: dict) -> None:
        """Set meter power limit / zero export configuration (V2 app-protocol).

        This is a generic wrapper around:
          POST setting.cgi {"cmd":"set_meter_req","payload":{...}}
        """
        if self.__api.version != "v2":
            raise HomeAssistantError("Meter power limit control is not supported with V1 protocol")

        try:
            rsp = await self.__api.client.post(
                "setting.cgi",
                {"cmd": "set_meter_req", "payload": payload},
            )

            # Expected success response:
            # {"cmd": "set_meter_rsp", "status": 200}
            if not isinstance(rsp, dict) or rsp.get("status") != 200:
                raise HomeAssistantError(f"Unexpected response from set_meter_req: {rsp}")

            # Do not block the service call waiting for a full coordinator refresh.
            # A full refresh can take a long time on slow/timeout-prone dongles, making the
            # Actions UI look like it's 'stuck' even though the write succeeded.
            self.async_request_refresh()
        except Exception as err:  # noqa: BLE001
            raise HomeAssistantError(f"Failed to set meter power limit: {err}") from err

    async def _write_battery_more_setting(self, register_offset: int, value: int) -> None:
        """Write a battery "More Settings" register via Modbus (function 0x10)."""
        try:
            await self.__api.modbus_write_multiple_holding_registers(
                device_address=3,
                register_address=40001 + register_offset,
                values=[value],
            )
            await self.async_refresh()
        except NotImplementedError as err:
            raise HomeAssistantError(
                "Modbus operations are not supported with V1 protocol"
            ) from err

    async def set_battery_power(self, on: bool) -> None:
        """Set battery power (offset 1500). 1=on, 0=shutdown."""
        await self._write_battery_more_setting(register_offset=1500, value=1 if on else 0)

    async def set_battery_sleep_enabled(self, enabled: bool) -> None:
        """Set battery sleep enabled flag (offset 1501). 0=enabled, 1=disabled."""
        await self._write_battery_more_setting(register_offset=1501, value=0 if enabled else 1)

    async def set_battery_led_color_index(self, index: int) -> None:
        """Set battery LED color index (offset 1502)."""
        await self._write_battery_more_setting(register_offset=1502, value=int(index))

    async def set_battery_led_brightness(self, brightness: int) -> None:
        """Set battery LED brightness percent (offset 1503)."""
        await self._write_battery_more_setting(register_offset=1503, value=int(brightness))

    async def set_battery_work_mode(self, sn: str, mode: BatteryWorkMode) -> None:
        """Set battery work mode."""
        try:
            await self.__api.set_battery_work_mode(sn, mode)
            # Do not block on full refresh; schedule it in the background.
            self.async_request_refresh()
        except NotImplementedError as err:
            raise HomeAssistantError(
                "Battery operations are not supported with V1 protocol"
            ) from err

    async def set_battery_soc_min(self, sn: str, value: int) -> None:
        """Set battery soc min."""
        try:
            await self.__api.set_battery_soc_min(sn, value)
            self.async_request_refresh()
        except NotImplementedError as err:
            raise HomeAssistantError(
                "Battery operations are not supported with V1 protocol"
            ) from err

    async def set_battery_soc_max(self, sn: str, value: int) -> None:
        """Set battery soc max."""
        try:
            await self.__api.set_battery_soc_max(sn, value)
            self.async_request_refresh()
        except NotImplementedError as err:
            raise HomeAssistantError(
                "Battery operations are not supported with V1 protocol"
            ) from err

    async def set_battery_schedule_slots(self, sn: str, slots: dict[str, list[ScheduleSlot]]) -> None:
        """Set battery schedule slots."""
        try:
            _LOGGER.debug("Setting schedule slots for %s: %s", sn, slots)
            current = await self.__api.get_schedule()
            raw_schedule = BatterySchedule.encode_schedule(
                slots,
                pin=current["raw"].get("Pin", 0),
                pout=current["raw"].get("Pout", 0)
            )
            _LOGGER.debug("Encoded schedule: %s", raw_schedule)
            await self.__api.set_schedule_slots(raw_schedule)
            self.async_request_refresh()
        except NotImplementedError as err:
            raise HomeAssistantError(
                "Battery operations are not supported with V1 protocol"
            ) from err

    async def set_battery_schedule_power(self, sn: str, pin: int | None = None, pout: int | None = None) -> None:
        """Set battery schedule power settings."""
        try:
            await self.__api.set_schedule_power(pin, pout)
            self.async_request_refresh()
        except NotImplementedError as err:
            raise HomeAssistantError(
                "Battery operations are not supported with V1 protocol"
            ) from err

    async def set_battery_schedule_pin(self, sn: str, pin: int) -> None:
        """Set battery schedule pin."""
        try:
            await self.__api.set_schedule_pin(pin)
            self.async_request_refresh()
        except NotImplementedError as err:
            raise HomeAssistantError(
                "Battery operations are not supported with V1 protocol"
            ) from err

    async def set_battery_schedule_pout(self, sn: str, pout: int) -> None:
        """Set battery schedule pout."""
        try:
            await self.__api.set_schedule_pout(pout)
            self.async_request_refresh()
        except NotImplementedError as err:
            raise HomeAssistantError(
                "Battery operations are not supported with V1 protocol"
            ) from err
