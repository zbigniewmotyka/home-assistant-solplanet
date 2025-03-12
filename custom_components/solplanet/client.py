"""Solplanet client for solplanet integration."""

import base64
from dataclasses import dataclass
from inspect import signature
import json
import logging
from typing import Any

from aiohttp import ClientResponse, ClientSession

__author__ = "Zbigniew Motyka"
__copyright__ = "Zbigniew Motyka"
__license__ = "MIT"

_LOGGER = logging.getLogger(__name__)


@dataclass
class GetInverterDataResponse:
    """Get inverter data response model.

    Attributes
    ----------
    flg : int
        TBD ??
    tim : str
        Datetime in format YYYYMMDDHHMMSS
    tmp : int
        Inverter temperature [C]
    fac : int
        AC frequency [Hz]
    pac : int
        AC real power [W]
    sac : int
        AC apparent power [VA]
    qac : int
        AC reactive / complex power [VAR]
    eto : int
        Energy produced total [kWh]
    etd : int
        Energy produced today [kWh]
    hto : int
        Total running time [h]
    pf : int
        Power factor
    wan : int
        TBD ??
    err : int
        Error
    vac : list[int]
        AC voltages [V]
    iac : list[int]
        AC current [A]
    vpv : list[int]
        DC voltages [V]
    ipv : list[int]
        DC current [A]
    str : list[int]
        TBD ??

    """

    flg: int | None = None
    tim: str | None = None
    tmp: int | None = None
    fac: int | None = None
    pac: int | None = None
    sac: int | None = None
    qac: int | None = None
    eto: int | None = None
    etd: int | None = None
    hto: int | None = None
    pf: int | None = None
    wan: int | None = None
    err: int | None = None
    vac: list[int] | None = None
    iac: list[int] | None = None
    vpv: list[int] | None = None
    ipv: list[int] | None = None
    str: list[int] | None = None
    stu: int | None = None
    pac1: int | None = None
    qac1: int | None = None
    pac2: int | None = None
    qac2: int | None = None
    pac3: int | None = None
    qac3: int | None = None


@dataclass
class GetInverterInfoItemResponse:
    """Get inverter info item response."""

    isn: str | None = None
    add: int | None = None
    safety: int | None = None
    rate: int | None = None
    msw: str | None = None
    ssw: str | None = None
    tsw: str | None = None
    pac: int | None = None
    etd: int | None = None
    eto: int | None = None
    err: int | None = None
    cmv: str | None = None
    mty: int | None = None
    model: str | None = None

    def isStorage(self) -> bool:
        """Check if device supports battery."""
        return self.mty in (11, 12, 13, 14, 15, 16, 17, 18, 19, 20) or (
            self.isn is not None and self.isn.startswith("BE")
        )


@dataclass
class GetInverterInfoResponse:
    """Get inverter info response."""

    inv: list[GetInverterInfoItemResponse]
    num: int | None = None


@dataclass
class GetMeterDataResponse:
    """Get meter data response model.

    Attributes
    ----------
    flg : int
        TBD ??
    tim : str
        Datetime in format YYYYMMDDHHMMSS
    pac : int
        AC real power [W]
    itd : int
        Input today
    otd : int
        Output today
    iet : int
        Input total
    oet : int
        Output total
    mod : int
        TBD ??
    enb : int
        TBD ??

    """

    flg: int | None = None
    tim: str | None = None
    pac: int | None = None
    itd: int | None = None
    otd: int | None = None
    iet: int | None = None
    oet: int | None = None
    mod: int | None = None
    enb: int | None = None


@dataclass
class GetMeterInfoResponse:
    """Get meter info response."""

    mod: int | None = None
    enb: int | None = None
    exp_m: int | None = None
    regulate: int | None = None
    enb_PF: int | None = None  # noqa: N815
    target_PF: int | None = None  # noqa: N815
    total_pac: int | None = None
    total_fac: int | None = None
    meter_pac: int | None = None
    sn: str | None = None
    manufactory: str | None = None
    type: str | None = None
    name: str | None = None
    model: int | None = None
    abs: int | None = None
    offset: int | None = None


@dataclass
class GetBatteryDataResponse:
    """Get battery data response model.

    Attributes
    ----------
    flg : int
        TBD ??
    tim : str
        Datetime in format YYYYMMDDHHMMSS
    vb : int
        Battery voltage [V] (/100)
    cb : int
        Battery current [A] (/10)
    pb : int
        Power pattery [W]
    tb : int
        Temperature [dC]
    soc : int
        State of charge [%]
    soh : int
        State of health [%]

    """

    flg: int | None = None
    tim: str | None = None
    ppv: int | None = None
    etdpv: int | None = None
    etopv: int | None = None
    cst: int | None = None
    bst: int | None = None
    eb1: int = 65535
    eb2: int = 65535
    eb3: int = 65535
    eb4: int = 65535
    wb1: int = 65535
    wb2: int = 65535
    wb3: int = 65535
    wb4: int = 65535
    vb: int | None = None
    cb: int | None = None
    pb: int | None = None
    tb: int | None = None
    soc: int | None = None
    soh: int | None = None
    cli: int | None = None
    clo: int | None = None
    ebi: int | None = None
    ebo: int | None = None
    eaci: int | None = None
    eaco: int | None = None
    vesp: int | None = None
    cesp: int | None = None
    fesp: int | None = None
    pesp: int | None = None
    rpesp: int | None = None
    etdesp: int | None = None
    etoesp: int | None = None
    charge_ac_td: int | None = None
    charge_ac_to: int | None = None
    vl1esp: int | None = None
    il1esp: int | None = None
    pac1esp: int | None = None
    qac1esp: int | None = None
    vl2esp: int | None = None
    il2esp: int | None = None
    pac2esp: int | None = None
    qac2esp: int | None = None
    vl3esp: int | None = None
    il3esp: int | None = None
    pac3esp: int | None = None
    qac3esp: int | None = None


@dataclass
class GetBatteryInfoItemResponse:
    """Get battery info item response."""

    bid: int | None = None
    devtype: str | None = None
    manufactoty: str | None = None
    partno: str | None = None
    model1sn: str | None = None
    model2sn: str | None = None
    model3sn: str | None = None
    model4sn: str | None = None
    model5sn: str | None = None
    model6sn: str | None = None
    model7sn: str | None = None
    model8sn: str | None = None
    modeltotal: int | None = None
    monomertotoal: int | None = None
    monomerinmodel: int | None = None
    ratedvoltage: int | None = None
    capacity: int | None = None
    hardwarever: str | None = None
    softwarever: str | None = None


@dataclass
class GetBatteryInfoResponse:
    """Get battery data response model.

    Attributes
    ----------
    charge_max : int
        Max charge battery level [%]
    discharge_max : int
        Max discharge battery level [%]

    """

    type: int
    mod_r: int
    battery: GetBatteryInfoItemResponse | None = None
    isn: str | None = None
    stu_r: int | None = None
    muf: int | None = None
    mod: int | None = None
    num: int | None = None
    fir_r: int | None = None
    charging: int | None = None
    charge_max: int | None = None
    discharge_max: int | None = None


@dataclass
class SetBatteryConfigValueRequest:
    """Set battery config value request."""

    type: int
    mod_r: int
    sn: str | None
    discharge_max: int | None
    charge_max: int | None
    muf: int | None
    mod: int | None
    num: int | None


@dataclass
class SetBatteryConfigRequest:
    """Set battery config request."""

    value: SetBatteryConfigValueRequest
    device: int = 4
    action: str = "setbattery"


@dataclass
class SetScheduleRequest:
    """Set schedule request."""
    value: dict[str, Any]
    device: int = 4
    action: str = "setdefine"


@dataclass
class BatteryWorkMode:
    """Represent data for battery work mode."""

    name: str

    mod_r: int
    type: int


class BatteryWorkModes:
    """Helper to for BatteryWorkMode."""

    _battery_modes: list[BatteryWorkMode] = [
        BatteryWorkMode("Self-consumption mode", 2, 1),
        BatteryWorkMode("Reserve power mode", 3, 1),
        BatteryWorkMode("Custom mode", 4, 1),
        BatteryWorkMode("Off-grid mode", 1, 2),
        BatteryWorkMode("Time of use mode", 5, 1),
    ]

    def get_all_modes(self, type: int, mod_r: int) -> list[BatteryWorkMode]:
        """Get all possible battery work modes."""
        selected = next(
            (x for x in self._battery_modes if x.mod_r == mod_r and x.type == type),
            None,
        )
        result = []
        result.extend(self._battery_modes)

        if selected is None:
            result.append(
                BatteryWorkMode(f"Unknown (mod_r: {mod_r}, type: {type})", mod_r, type)
            )

        return result

    def get_mode(self, type: int, mod_r: int) -> BatteryWorkMode | None:
        """Get battery work mode by type and mod_r."""
        return next(
            (
                x
                for x in self.get_all_modes(type, mod_r)
                if x.type == type and x.mod_r == mod_r
            ),
            None,
        )


@dataclass
class ScheduleSlot:
    """Represent a battery schedule time slot."""
    start_hour: int
    start_minute: int
    duration: int
    mode: str

    @classmethod
    def from_raw(cls, code: int) -> 'ScheduleSlot | None':
        """Create slot from raw inverter code."""
        if code == 0:
            return None
            
        discharge_bit = code & 0x1
        duration_bits = (code >> 14) & 0x3
        half_hour_bit = (code >> 17) & 0x1
        hour_bits = code >> 24

        return cls(
            start_hour=hour_bits,
            start_minute=30 if half_hour_bit else 0,
            duration=duration_bits + 1,
            mode="discharge" if discharge_bit else "charge"
        )

    @classmethod
    def from_time(cls, start: str, duration: int, mode: str) -> 'ScheduleSlot':
        """Create slot from time string (HH:MM), duration and mode."""
        hour, minute = map(int, start.split(':'))
        if minute not in [0, 30]:
            raise ValueError("Minutes must be 0 or 30")
        if not 0 <= hour <= 23:
            raise ValueError("Hour must be between 0 and 23")
        if not 1 <= duration <= 4:
            raise ValueError("Duration must be between 1 and 4 hours")
        if mode not in ["charge", "discharge"]:
            raise ValueError("Mode must be 'charge' or 'discharge'")
            
        return cls(
            start_hour=hour,
            start_minute=minute,
            duration=duration,
            mode=mode
        )

    @classmethod
    def from_dict(cls, data: dict) -> 'ScheduleSlot':
        """Create slot from dictionary with start, duration, mode."""
        if isinstance(data.get('start'), str):
            return cls.from_time(data['start'], data['duration'], data['mode'])
        return cls(
            start_hour=data['start_hour'],
            start_minute=data['start_minute'],
            duration=data['duration'],
            mode=data['mode']
        )

    def to_raw(self) -> int:
        """Convert slot to raw inverter format."""
        if self.start_minute not in [0, 30]:
            raise ValueError("Minutes must be 0 or 30")
            
        BASE = 0x3C02
        HOUR = 0x1000000
        HALF = 0x1E0000
        DURATION = 0x3C00
        
        return (BASE +
                (self.start_hour * HOUR) +
                ((self.start_minute // 30) * HALF) +
                ((self.duration - 1) * DURATION) +
                (1 if self.mode == "discharge" else 0))

    def to_dict(self) -> dict:
        """Convert slot to dictionary format."""
        return {
            "start_hour": self.start_hour,
            "start_minute": self.start_minute,
            "duration": self.duration,
            "mode": self.mode
        }

    def human_readable(self, format: str = "{start} - {end} ({mode})") -> str:
        """Convert slot to human readable string.
        
        Args:
            format: Format string with {start}, {end}, {mode} placeholders
        """
        end_hour = (self.start_hour + self.duration) % 24
        return format.format(
            start=f"{self.start_hour:02d}:{self.start_minute:02d}",
            end=f"{end_hour:02d}:{self.start_minute:02d}",
            mode=self.mode
        )

    def validate_duration(self) -> None:
        """Validate slot duration doesn't cross midnight."""
        end_hour = self.start_hour + self.duration
        if end_hour > 24:
            raise ValueError(f"Slot ending at {end_hour}:00 crosses midnight. At {self.start_hour}:00 max duration is {24-self.start_hour} hours")

    @staticmethod
    def validate_slots(slots: list['ScheduleSlot']) -> None:
        """Validate a list of slots."""
        if len(slots) > 6:
            raise ValueError("Maximum 6 slots per day allowed")
            
        sorted_slots = sorted(slots, key=lambda x: (x.start_hour, x.start_minute))
        
        for i, slot in enumerate(sorted_slots):
            slot.validate_duration()
            
            if i < len(sorted_slots) - 1:
                next_slot = sorted_slots[i + 1]
                current_end = slot.start_hour + slot.duration
                current_end_mins = slot.start_minute
                next_start = next_slot.start_hour
                next_start_mins = next_slot.start_minute
                
                if (current_end > next_start) or (current_end == next_start and current_end_mins > next_start_mins):
                    raise ValueError(f"Slot {slot.human_readable()} overlaps with {next_slot.human_readable()}")


class BatterySchedule:
    """Helper for battery schedule operations."""
    DAYS = ["Mon", "Tus", "Wen", "Thu", "Fri", "Sat", "Sun"]

    @staticmethod
    def decode_schedule(raw_schedule: dict) -> dict[str, list[ScheduleSlot]]:
        """Decode raw schedule into slots."""
        return {
            day: [
                slot for code in raw_schedule.get(day, [])[:6]  # Limit to 6 slots
                if (slot := ScheduleSlot.from_raw(code)) is not None
            ]
            for day in BatterySchedule.DAYS
        }

    @staticmethod
    def encode_schedule(slots: dict[str, list[ScheduleSlot]], pin: int = 5000, pout: int = 5000) -> dict:
        """Encode slots into raw schedule."""
        # Validate slots for each day
        for day, day_slots in slots.items():
            if day_slots:  # Only validate if there are slots
                ScheduleSlot.validate_slots(day_slots)
                
        return {
            **{
                day: [slot.to_raw() for slot in day_slots]
                for day, day_slots in slots.items()
                if day_slots  # Only include days with slots
            },
            "Pin": pin,
            "Pout": pout
        }


class SolplanetClient:
    """Solplanet http client."""

    def __init__(self, host: str, session: ClientSession) -> None:
        """Create instance of solplanet http client."""
        self.host = host
        self.port = 8484
        self.session = session

    def get_url(self, endpoint: str) -> str:
        """Get URL for specified endpoint."""
        return "http://" + self.host + ":" + str(self.port) + "/" + endpoint

    async def get(self, endpoint: str):
        """Make get request to specified endpoint."""
        return await self._parse_response(
            await self.session.get(self.get_url(endpoint))
        )

    async def post(self, endpoint: str, data: Any):
        """Make get request to specified endpoint."""
        return await self._parse_response(
            await self.session.post(self.get_url(endpoint), json=data)
        )

    async def _parse_response(self, response: ClientResponse):
        """Parse response from inverter endpoints."""
        content = await response.read()
        _LOGGER.debug(
            "Received from %s:\nheaders: %s,\ncontent: %s",
            response.request_info.url,
            response.raw_headers,
            base64.b64encode(content),
        )
        return json.loads(
            s=content.strip().decode(response.get_encoding(), "replace"), strict=False
        )


class SolplanetApi:
    """Solplanet api v2 client."""

    def __init__(self, client: SolplanetClient) -> None:
        """Create instance of solplanet api."""
        _LOGGER.debug("Creating api instance")
        self.client = client

    async def get_inverter_data(self, sn: str) -> GetInverterDataResponse:
        """Get inverter data."""
        _LOGGER.debug("Getting inverter (%s) data", sn)
        response = await self.client.get("getdevdata.cgi?device=2&sn=" + sn)
        return self._create_class_from_dict(GetInverterDataResponse, response)

    async def get_inverter_info(self) -> GetInverterInfoResponse:
        """Get inverter info."""
        _LOGGER.debug("Getting inverter info")
        response = await self.client.get("getdev.cgi?device=2")
        response["inv"] = [
            self._create_class_from_dict(GetInverterInfoItemResponse, item)
            for item in response["inv"]
        ]
        return self._create_class_from_dict(GetInverterInfoResponse, response)

    async def get_meter_data(self) -> GetMeterDataResponse:
        """Get meter data."""
        _LOGGER.debug("Getting meter data")
        response = await self.client.get("getdevdata.cgi?device=3")
        return self._create_class_from_dict(GetMeterDataResponse, response)

    async def get_meter_info(self) -> GetMeterInfoResponse:
        """Get meter info."""
        _LOGGER.debug("Getting meter info")
        response = await self.client.get("getdev.cgi?device=3")
        return self._create_class_from_dict(GetMeterInfoResponse, response)

    async def get_battery_data(self, sn: str) -> GetBatteryDataResponse:
        """Get battery data."""
        _LOGGER.debug("Getting battery data")
        response = await self.client.get("getdevdata.cgi?device=4&sn=" + sn)
        return self._create_class_from_dict(GetBatteryDataResponse, response)

    async def get_battery_info(self, sn: str) -> GetBatteryInfoResponse:
        """Get battery info."""
        _LOGGER.debug("Getting battery info")
        response = await self.client.get("getdev.cgi?device=4&sn=" + sn)
        if "battery" in response:
            response["battery"] = self._create_class_from_dict(
                GetBatteryInfoItemResponse, response["battery"]
            )
        return self._create_class_from_dict(GetBatteryInfoResponse, response)

    async def set_battery_work_mode(self, sn: str, mode: BatteryWorkMode) -> None:
        """Set battery work mode."""
        current_config = await self.get_battery_info(sn)
        value = SetBatteryConfigValueRequest(
            type=mode.type,
            mod_r=mode.mod_r,
            muf=current_config.muf,
            mod=current_config.mod,
            num=current_config.num,
            sn=current_config.isn,
            charge_max=current_config.charge_max,
            discharge_max=current_config.discharge_max,
        )
        request = SetBatteryConfigRequest(value=value)
        await self.client.post("setting.cgi", request)

    async def set_battery_soc_min(self, sn: str, soc_min: int) -> None:
        """Set battery work mode."""
        current_config = await self.get_battery_info(sn)
        value = SetBatteryConfigValueRequest(
            type=current_config.type,
            mod_r=current_config.mod_r,
            muf=current_config.muf,
            mod=current_config.mod,
            num=current_config.num,
            sn=current_config.isn,
            charge_max=current_config.charge_max,
            discharge_max=soc_min,
        )
        request = SetBatteryConfigRequest(value=value)
        await self.client.post("setting.cgi", request)

    async def set_battery_soc_max(self, sn: str, soc_max: int) -> None:
        """Set battery work mode."""
        current_config = await self.get_battery_info(sn)
        value = SetBatteryConfigValueRequest(
            type=current_config.type,
            mod_r=current_config.mod_r,
            muf=current_config.muf,
            mod=current_config.mod,
            num=current_config.num,
            sn=current_config.isn,
            charge_max=soc_max,
            discharge_max=current_config.discharge_max,
        )
        request = SetBatteryConfigRequest(value=value)
        await self.client.post("setting.cgi", request)

    async def get_schedule(self) -> dict:
        """Get battery schedule configuration."""
        _LOGGER.debug("Getting battery schedule")
        raw_response = await self.client.get("getdefine.cgi")
        slots = BatterySchedule.decode_schedule(raw_response)
        return {
            "raw": raw_response,       # Store raw API response as-is
            "slots": slots,            # Store decoded schedule
            "Pin": raw_response.get("Pin", 5000),
            "Pout": raw_response.get("Pout", 5000)
        }

    async def set_schedule_slots(self, slots: dict[str, list[ScheduleSlot]]) -> None:
        """Set battery schedule slots configuration."""
        _LOGGER.debug("Setting battery schedule slots: %s", slots)
        current = await self.get_schedule()
        schedule = BatterySchedule.encode_schedule(slots)  # Changed from create_slots_schedule
        request = SetScheduleRequest(value=schedule)
        await self.client.post("setting.cgi", request)

    async def set_schedule_power(self, pin: int | None = None, pout: int | None = None) -> None:
        """Set battery schedule power configuration."""
        _LOGGER.debug("Setting battery schedule power - pin: %s, pout: %s", pin, pout)
        current = await self.get_schedule()
        schedule = BatterySchedule.encode_schedule({},   # Changed method name and use empty slots
            pin=pin if pin is not None else current["Pin"],
            pout=pout if pout is not None else current["Pout"])
        request = SetScheduleRequest(value=schedule)
        await self.client.post("setting.cgi", request)

    async def set_schedule_pin(self, pin: int) -> None:
        """Set battery schedule pin configuration."""
        _LOGGER.debug("Setting battery schedule pin: %s", pin)
        current = await self.get_schedule()
        schedule = BatterySchedule.encode_schedule({}, pin=pin, pout=current["Pout"])  # Changed method
        request = SetScheduleRequest(value=schedule)
        await self.client.post("setting.cgi", request)

    async def set_schedule_pout(self, pout: int) -> None:
        """Set battery schedule pout configuration."""
        _LOGGER.debug("Setting battery schedule pout: %s", pout)
        current = await self.get_schedule()
        schedule = BatterySchedule.encode_schedule({}, pin=current["Pin"], pout=pout)  # Changed method
        request = SetScheduleRequest(value=schedule)
        await self.client.post("setting.cgi", request)

    async def set_schedule_slots(self, schedule: dict) -> None:
        """Set battery schedule configuration directly with raw schedule."""
        _LOGGER.debug("Setting raw schedule: %s", schedule)
        request = SetScheduleRequest(value=schedule)
        await self.client.post("setting.cgi", request)

    def _create_class_from_dict(self, cls, dict):
        return cls(**{k: v for k, v in dict.items() if k in signature(cls).parameters})
