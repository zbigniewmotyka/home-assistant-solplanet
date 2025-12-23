"""Solplanet client for solplanet integration.

This module contains:
- SolplanetClient: HTTP client for communication with Solplanet inverters
- ModbusApiMixin: Mixin providing Modbus operations (shared by V1 and V2 APIs)
- Helper classes: BatteryWorkMode, BatteryWorkModes, ScheduleSlot, BatterySchedule
- Model aliases: Import V2 models as default models for backward compatibility
"""

import base64
import json
import logging
import time
from typing import Any

from aiohttp import ClientResponse, ClientSession

from .modbus import DataType, ModbusRtuFrameGenerator

__author__ = "Zbigniew Motyka"
__copyright__ = "Zbigniew Motyka"
__license__ = "MIT"

_LOGGER = logging.getLogger(__name__)


# ============================================================================
# HTTP Client
# ============================================================================


class SolplanetClient:
    """Solplanet HTTP client."""

    def __init__(self, host: str, session: ClientSession, scheme: str = "http", port: int = 8484) -> None:
        """Create instance of solplanet http client."""
        self.host = host
        self.scheme = scheme
        self.port = port
        self.session = session

    def get_url(self, endpoint: str) -> str:
        """Get URL for specified endpoint."""
        return f"{self.scheme}://{self.host}:{self.port}/{endpoint}"

    async def get(self, endpoint: str):
        """Make get request to specified endpoint."""
        kwargs = {"ssl": False} if self.scheme == "https" else {}
        return await self._parse_response(
            await self.session.get(self.get_url(endpoint), **kwargs)
        )

    async def post(self, endpoint: str, data: Any):
        """Make post request to specified endpoint."""
        kwargs = {"ssl": False} if self.scheme == "https" else {}
        return await self._parse_response(
            await self.session.post(self.get_url(endpoint), json=data, **kwargs)
        )

    async def _parse_response(self, response: ClientResponse):
        """Parse response from inverter endpoints."""
        content = await response.read()

        # Only do expensive base64 encoding when debug logging is enabled
        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "Received from %s:\nheaders: %s,\ncontent: %s",
                response.request_info.url,
                response.raw_headers,
                base64.b64encode(content),
            )
        return json.loads(
            s=content.strip().decode(response.get_encoding(), "replace"), strict=False
        )


# ============================================================================
# Modbus API Mixin
# ============================================================================


class ModbusApiMixin:
    """Mixin providing Modbus operations for Solplanet API clients.

    This mixin is used by both V1 and V2 API clients to avoid code duplication.
    It requires the class to have a 'client' attribute of type SolplanetClient.
    """

    client: SolplanetClient  # Type hint for mixin

    async def modbus_read_holding_registers(
        self,
        data_type: DataType,
        device_address: int,
        register_address: int,
        register_count: int = 1,
    ) -> dict | int | str | None:
        """Read modbus holding registers."""
        frame = ModbusRtuFrameGenerator().generate_read_holding_register_frame(
            device_id=device_address,
            register_address=register_address,
            register_length=register_count,
        )
        return await self._send_modbus(frame=frame, data_type=data_type)

    async def modbus_write_single_holding_register(
        self,
        data_type: DataType,
        device_address: int,
        register_address: int,
        value: int,
        dry_run: bool = False,
    ) -> dict | int | str | None:
        """Write modbus single holding register."""
        frame = ModbusRtuFrameGenerator().generate_write_single_holding_register_frame(
            device_id=device_address,
            register_address=register_address,
            value=value,
            data_type=data_type,
        )
        _LOGGER.debug(
            "Generated frame for write single holding register (device_address: %s, data_type: %s, register_address: %s, value: %s, dry_run: %s): %s",
            device_address,
            data_type,
            register_address,
            value,
            dry_run,
            frame,
        )
        if dry_run:
            return frame
        return await self._send_modbus(frame=frame, data_type=data_type)

    async def modbus_read_input_registers(
        self,
        data_type: DataType,
        device_address: int,
        register_address: int,
        register_count: int = 1,
    ) -> dict | int | str | None:
        """Read modbus input registers."""
        frame = ModbusRtuFrameGenerator().generate_read_input_register_frame(
            device_id=device_address,
            register_address=register_address,
            register_length=register_count,
        )
        return await self._send_modbus(frame=frame, data_type=data_type)

    async def _send_modbus(
        self,
        frame: str,
        data_type: DataType,
    ) -> dict | int | str | None:
        """Send modbus frame via fdbg.cgi endpoint."""
        start_time = time.time()
        response = await self.client.post("fdbg.cgi", {"data": frame})
        end_time = time.time()
        elapsed_time = end_time - start_time

        _LOGGER.debug("Modbus RTU request frame: %s", frame)
        _LOGGER.debug("Modbus RTU response frame: %s", response)
        _LOGGER.debug("Modbus RTU request time: %.2f seconds", elapsed_time)

        data = ModbusRtuFrameGenerator().decode_response(
            response_hex=response["data"], data_type=data_type
        )
        _LOGGER.debug("Modbus RTU response decoded: %s", data)

        return data


# ============================================================================
# Helper Classes
# ============================================================================


from dataclasses import dataclass  # noqa: E402


@dataclass
class BatteryWorkMode:
    """Represent data for battery work mode.

    Attributes:
        name: Display name of the work mode
        mod_r: Mode register value
        type: Battery system type

    """

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
    def encode_schedule(slots: dict[str, list[ScheduleSlot]], pin: int = 0, pout: int = 0) -> dict:
        """Encode slots into raw schedule."""
        # Validate slots for each day
        for day_slots in slots.values():
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


# ============================================================================
# Response Models (shared by both V1 and V2 APIs)
# ============================================================================

from dataclasses import dataclass
from inspect import signature


@dataclass
class GetInverterDataResponse:
    """Get inverter data response model.

    Attributes:
        flg: Inverter status code
        tim: Timestamp of data
        tmp: Inverter temperature in 0.1°C
        fac: AC frequency in 0.01 Hz
        pac: Total active power output in W
        sac: Total apparent power in VA
        qac: Total reactive power in VAr
        eto: Total energy production in 0.1 kWh # codespell:ignore eto
        etd: Today's energy production in 0.1 kWh
        hto: Total working hours in h
        pf: Power factor in 0.01
        wan: Warning code
        err: Error code
        vac: AC phase voltages in 0.1 V
        iac: AC phase currents in 0.1 A
        vpv: PV input voltages per MPPT in 0.1 V
        ipv: PV input currents per MPPT in 0.01 A
        str: String values
        stu: Status value
        pac1: Phase 1 active power in W
        qac1: Phase 1 reactive power in VAr
        pac2: Phase 2 active power in W
        qac2: Phase 2 reactive power in VAr
        pac3: Phase 3 active power in W
        qac3: Phase 3 reactive power in VAr

    """

    flg: int | None = None
    tim: str | None = None
    tmp: int | None = None
    fac: int | None = None
    pac: int | None = None
    sac: int | None = None
    qac: int | None = None
    eto: int | None = None  # codespell:ignore eto
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
    """Get inverter info item response.

    Attributes:
        isn: Inverter serial number
        add: Address value
        safety: Safety code
        rate: Rate value
        msw: Main software version
        ssw: Slave software version
        tsw: Third software version
        pac: Current power output in W
        etd: Today's energy production in 0.1 kWh
        eto: Total energy production in 0.1 kWh # codespell:ignore eto
        err: Error code
        cmv: Communication version
        mty: Device model type code
        model: Device model name

    """

    isn: str | None = None
    add: int | None = None
    safety: int | None = None
    rate: int | None = None
    msw: str | None = None
    ssw: str | None = None
    tsw: str | None = None
    pac: int | None = None
    etd: int | None = None
    eto: int | None = None  # codespell:ignore eto
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
    """Get inverter info response.

    Attributes:
        inv: List of inverter info items
        num: Number of inverters

    """

    inv: list[GetInverterInfoItemResponse]
    num: int | None = None


@dataclass
class GetMeterDataResponse:
    """Get meter data response model.

    Attributes:
        flg: Meter status flag
        tim: Timestamp of data
        pac: Grid power in W (positive: import, negative: export)
        itd: Today's imported energy in 0.01 kWh
        otd: Today's exported energy in 0.01 kWh
        iet: Total imported energy in 0.1 kWh
        oet: Total exported energy in 0.1 kWh
        mod: Meter operating mode
        enb: Meter enabled status

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
    """Get meter info response.

    Attributes:
        mod: Meter mode
        enb: Meter enabled status
        exp_m: Export mode
        regulate: Regulation value
        enb_PF: Power Factor enabled status
        target_PF: Target Power Factor value
        total_pac: Total active power in W
        total_fac: Total frequency in 0.01 Hz
        meter_pac: Meter power in W
        sn: Meter serial number
        manufactory: Manufacturer name
        type: Meter type
        name: Meter name
        model: Meter model code
        abs: Absolute value flag
        offset: Offset value

    """

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

    Attributes:
        flg: Battery status flag
        tim: Timestamp of data
        ppv: PV power in W
        etdpv: PV energy today in 0.1 kWh
        etopv: PV energy total in 0.1 kWh
        cst: Communication status code
        bst: Battery status code
        eb1: Battery error code group 1
        eb2: Battery error code group 2
        eb3: Battery error code group 3
        eb4: Battery error code group 4
        wb1: Battery warning code group 1
        wb2: Battery warning code group 2
        wb3: Battery warning code group 3
        wb4: Battery warning code group 4
        vb: Battery voltage in 0.01 V
        cb: Battery current in 0.1 A
        pb: Battery power in W
        tb: Battery temperature in 0.1°C
        soc: State of charge in %
        soh: State of health in %
        cli: Current limit for charging in 0.1 A
        clo: Current limit for discharging in 0.1 A
        ebi: Battery energy for charging in 0.1 kWh
        ebo: Battery energy for discharging in 0.1 kWh
        eaci: AC energy for charging in 0.1 kWh
        eaco: AC energy for discharging in 0.1 kWh
        vesp: EPS voltage in 0.1 V
        cesp: EPS current in 0.1 A
        fesp: EPS frequency in 0.01 Hz
        pesp: EPS power in W
        rpesp: EPS reactive power in VAr
        etdesp: EPS energy today in 0.1 kWh
        etoesp: EPS energy total in 0.1 kWh
        charge_ac_td: AC charge today in 0.1 kWh
        charge_ac_to: AC charge total in 0.1 kWh
        vl1esp: EPS phase 1 voltage in 0.1 V
        il1esp: EPS phase 1 current in 0.1 A
        pac1esp: EPS phase 1 power in W
        qac1esp: EPS phase 1 reactive power in VAr
        vl2esp: EPS phase 2 voltage in 0.1 V
        il2esp: EPS phase 2 current in 0.1 A
        pac2esp: EPS phase 2 power in W
        qac2esp: EPS phase 2 reactive power in VAr
        vl3esp: EPS phase 3 voltage in 0.1 V
        il3esp: EPS phase 3 current in 0.1 A
        pac3esp: EPS phase 3 power in W
        qac3esp: EPS phase 3 reactive power in VAr

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
    """Get battery info item response.

    Attributes:
        bid: Battery ID
        devtype: Device type
        manufactoty: Manufacturer name
        partno: Part number
        model1sn: Model 1 serial number
        model2sn: Model 2 serial number
        model3sn: Model 3 serial number
        model4sn: Model 4 serial number
        model5sn: Model 5 serial number
        model6sn: Model 6 serial number
        model7sn: Model 7 serial number
        model8sn: Model 8 serial number
        modeltotal: Total number of models
        monomertotoal: Total number of monomers
        monomerinmodel: Monomers per model
        ratedvoltage: Rated voltage
        capacity: Battery capacity
        hardwarever: Hardware version
        softwarever: Software version

    """

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

    Attributes:
        type: Battery system type
        mod_r: Battery work mode
        battery: Battery detail information
        isn: Battery serial number
        stu_r: Status register
        muf: Manufacturer code
        mod: Battery model code
        num: Number of batteries
        fir_r: Firmware register
        charging: Charging status
        charge_max: Max state of charge in %
        discharge_max: Min state of charge in %

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
    """Set battery config value request.

    Attributes:
        type: Battery system type
        mod_r: Battery work mode
        sn: Battery serial number
        discharge_max: Min state of charge in %
        charge_max: Max state of charge in %
        muf: Manufacturer code
        mod: Battery model code
        num: Number of batteries

    """

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
    """Set battery config request.

    Attributes:
        value: Battery configuration values
        device: Device type ID (4 for battery)
        action: Action to perform (setbattery)

    """

    value: SetBatteryConfigValueRequest
    device: int = 4
    action: str = "setbattery"


@dataclass
class SetScheduleRequest:
    """Set schedule request."""

    value: dict[str, Any]
    device: int = 4
    action: str = "setdefine"


# ============================================================================
# API Clients
# ============================================================================


class SolplanetApiV1(ModbusApiMixin):
    """Solplanet API v1 client."""

    def __init__(self, client: SolplanetClient) -> None:
        """Create instance of solplanet api v1."""
        _LOGGER.debug("Creating api v1 instance")
        self.client = client

    async def get_inverter_data(self, sn: str) -> GetInverterDataResponse:
        """Get inverter data (V1 endpoint).

        Returns:
            GetInverterDataResponse: Inverter data
        """
        _LOGGER.debug("Getting inverter (%s) data (V1)", sn)
        response = await self.client.get("invdata.cgi?sn=" + sn)
        return self._create_class_from_dict(GetInverterDataResponse, response)

    async def get_inverter_info(self) -> GetInverterInfoResponse:
        """Get inverter info (V1 endpoint).

        Returns:
            GetInverterInfoResponse: Inverter info
        """
        _LOGGER.debug("Getting inverter info (V1)")
        response = await self.client.get("invinfo.cgi")
        response["inv"] = [
            self._create_class_from_dict(GetInverterInfoItemResponse, item)
            for item in response["inv"]
        ]
        return self._create_class_from_dict(GetInverterInfoResponse, response)

    async def get_meter_data(self) -> GetMeterDataResponse:
        """Get meter data (V1 endpoint).

        Returns:
            GetMeterDataResponse: Meter data
        """
        _LOGGER.debug("Getting meter data (V1)")
        response = await self.client.get("emeter.cgi")
        return self._create_class_from_dict(GetMeterDataResponse, response)

    async def get_meter_info(self) -> GetMeterInfoResponse:
        """Get meter info (V1 endpoint).

        Returns:
            GetMeterInfoResponse: Meter info
        """
        _LOGGER.debug("Getting meter info (V1)")
        response = await self.client.get("pwrlim.cgi")
        return self._create_class_from_dict(GetMeterInfoResponse, response)

    def _create_class_from_dict(self, cls, dict):
        """Create dataclass instance from dict."""
        return cls(**{k: v for k, v in dict.items() if k in signature(cls).parameters})


class SolplanetApiV2(ModbusApiMixin):
    """Solplanet API v2 client."""

    def __init__(self, client: SolplanetClient) -> None:
        """Create instance of solplanet api v2."""
        _LOGGER.debug("Creating api v2 instance")
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
        _LOGGER.debug("Getting battery (%s) data", sn)
        response = await self.client.get("getdevdata.cgi?device=4&sn=" + sn)
        return self._create_class_from_dict(GetBatteryDataResponse, response)

    async def get_battery_info(self, sn: str) -> GetBatteryInfoResponse:
        """Get battery info."""
        _LOGGER.debug("Getting battery (%s) info", sn)
        response = await self.client.get("getdev.cgi?device=4&sn=" + sn)
        if "battery" in response and response["battery"] is not None:
            response["battery"] = self._create_class_from_dict(
                GetBatteryInfoItemResponse, response["battery"]
            )
        return self._create_class_from_dict(GetBatteryInfoResponse, response)

    async def set_battery_work_mode(self, sn: str, mode: BatteryWorkMode) -> None:
        """Set battery work mode."""
        _LOGGER.debug("Setting battery (%s) work mode to %s", sn, mode)
        battery_info = await self.get_battery_info(sn)
        request = SetBatteryConfigRequest(
            value=SetBatteryConfigValueRequest(
                type=mode.type,
                mod_r=mode.mod_r,
                sn=sn,
                discharge_max=battery_info.discharge_max,
                charge_max=battery_info.charge_max,
                muf=battery_info.muf,
                mod=battery_info.mod,
                num=battery_info.num,
            )
        )
        await self.client.post("setting.cgi", request)

    async def set_battery_soc_min(self, sn: str, soc_min: int) -> None:
        """Set battery minimum SOC."""
        _LOGGER.debug("Setting battery (%s) SOC min to %d", sn, soc_min)
        battery_info = await self.get_battery_info(sn)
        request = SetBatteryConfigRequest(
            value=SetBatteryConfigValueRequest(
                type=battery_info.type,
                mod_r=battery_info.mod_r,
                sn=sn,
                discharge_max=soc_min,
                charge_max=battery_info.charge_max,
                muf=battery_info.muf,
                mod=battery_info.mod,
                num=battery_info.num,
            )
        )
        await self.client.post("setting.cgi", request)

    async def set_battery_soc_max(self, sn: str, soc_max: int) -> None:
        """Set battery maximum SOC."""
        _LOGGER.debug("Setting battery (%s) SOC max to %d", sn, soc_max)
        battery_info = await self.get_battery_info(sn)
        request = SetBatteryConfigRequest(
            value=SetBatteryConfigValueRequest(
                type=battery_info.type,
                mod_r=battery_info.mod_r,
                sn=sn,
                discharge_max=battery_info.discharge_max,
                charge_max=soc_max,
                muf=battery_info.muf,
                mod=battery_info.mod,
                num=battery_info.num,
            )
        )
        await self.client.post("setting.cgi", request)

    async def get_schedule(self) -> dict:
        """Get battery schedule configuration."""
        _LOGGER.debug("Getting battery schedule")
        raw_response = await self.client.get("getdefine.cgi")
        slots = BatterySchedule.decode_schedule(raw_response)
        return {
            "raw": raw_response,  # Store raw API response as-is
            "slots": slots,  # Store decoded schedule
            "Pin": raw_response.get("Pin", 0),
            "Pout": raw_response.get("Pout", 0),
        }

    async def set_schedule_power(
        self, pin: int | None = None, pout: int | None = None
    ) -> None:
        """Set battery schedule power configuration."""
        current = await self.get_schedule()
        schedule = BatterySchedule.encode_schedule(
            current["slots"],
            pin=pin if pin is not None else current["Pin"],
            pout=pout if pout is not None else current["Pout"],
        )
        request = SetScheduleRequest(value=schedule)
        await self.client.post("setting.cgi", request)

    async def set_schedule_pin(self, pin: int) -> None:
        """Set battery schedule pin configuration."""
        await self.set_schedule_power(pin=pin)

    async def set_schedule_pout(self, pout: int) -> None:
        """Set battery schedule pout configuration."""
        await self.set_schedule_power(pout=pout)

    async def set_schedule_slot(
        self,
        slot_id: int,
        start_hour: int,
        start_minute: int,
        end_hour: int,
        end_minute: int,
        power: int,
        enabled: bool,
    ) -> None:
        """Set battery schedule slot configuration."""
        current = await self.get_schedule()
        slots = current["slots"]
        slots[slot_id] = ScheduleSlot(
            start_hour=start_hour,
            start_minute=start_minute,
            end_hour=end_hour,
            end_minute=end_minute,
            power=power,
            enabled=enabled,
        )
        schedule = BatterySchedule.encode_schedule(
            slots, pin=current["Pin"], pout=current["Pout"]
        )
        request = SetScheduleRequest(value=schedule)
        await self.client.post("setting.cgi", request)

    def _create_class_from_dict(self, cls, dict):
        """Create dataclass instance from dict."""
        return cls(**{k: v for k, v in dict.items() if k in signature(cls).parameters})


# Alias for backward compatibility
SolplanetApi = SolplanetApiV2

__all__ = [
    # HTTP Client
    "SolplanetClient",
    # Modbus Mixin
    "ModbusApiMixin",
    # Helper Classes
    "BatteryWorkMode",
    "BatteryWorkModes",
    "ScheduleSlot",
    "BatterySchedule",
    # Response Models
    "GetInverterDataResponse",
    "GetInverterInfoItemResponse",
    "GetInverterInfoResponse",
    "GetMeterDataResponse",
    "GetMeterInfoResponse",
    "GetBatteryDataResponse",
    "GetBatteryInfoItemResponse",
    "GetBatteryInfoResponse",
    # Request Models
    "SetBatteryConfigValueRequest",
    "SetBatteryConfigRequest",
    "SetScheduleRequest",
    # API Clients
    "SolplanetApiV1",
    "SolplanetApiV2",
    "SolplanetApi",
]
