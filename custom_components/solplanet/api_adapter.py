"""Solplanet API Adapter - automatically detects and uses V1 or V2 protocol."""

import logging
from typing import Literal

from .client import (
    BatteryWorkMode,
    GetBatteryDataResponse,
    GetBatteryInfoResponse,
    GetInverterDataResponse,
    GetInverterInfoResponse,
    GetMeterDataResponse,
    GetMeterInfoResponse,
    SolplanetApiV1,
    SolplanetApiV2,
    SolplanetClient,
)
from .modbus import DataType

__author__ = "Zbigniew Motyka"
__copyright__ = "Zbigniew Motyka"
__license__ = "MIT"

_LOGGER = logging.getLogger(__name__)


class SolplanetApiAdapter:
    """Adapter that automatically detects protocol version and delegates to appropriate client.

    This adapter provides a unified interface for both V1 and V2 protocols.
    It automatically detects which protocol version the inverter supports
    and delegates all API calls to the appropriate client implementation.
    """

    def __init__(
        self, client: SolplanetClient, api: SolplanetApiV1 | SolplanetApiV2
    ) -> None:
        """Initialize the adapter with detected API client.

        Args:
            client: HTTP client instance
            api: Either V1 or V2 API client instance

        """
        self.client = client
        self._api = api
        self._version: Literal["v1", "v2"] = "v2" if isinstance(api, SolplanetApiV2) else "v1"

    @classmethod
    async def create(cls, client: SolplanetClient) -> "SolplanetApiAdapter":
        """Create adapter instance with automatic protocol version detection.

        Args:
            client: HTTP client instance

        Returns:
            SolplanetApiAdapter instance configured for detected protocol version

        """
        version = await cls._detect_protocol_version(client)
        _LOGGER.info("Detected Solplanet protocol version: %s", version)

        if version == "v2":
            api = SolplanetApiV2(client)
        else:
            api = SolplanetApiV1(client)

        return cls(client, api)

    @staticmethod
    async def _detect_protocol_version(
        client: SolplanetClient,
    ) -> Literal["v1", "v2"]:
        """Detect which protocol version the inverter supports.

        Tries V2 endpoint first, falls back to V1 if V2 fails.

        Args:
            client: HTTP client instance

        Returns:
            "v2" if V2 protocol is supported, "v1" otherwise

        """

        # API version configurations: (version_name, endpoint, scheme, port)
        api_configs = [
            ("v2", "getdev.cgi?device=2", "https", 443),
            ("v2", "getdev.cgi?device=2", "http", 8484),
            ("v1", "invinfo.cgi", "http", 8484),
        ]

        for version, endpoint, scheme, port in api_configs:
            client.scheme = scheme
            client.port = port
            try:
                _LOGGER.debug("Attempting to detect %s protocol using %s and port %s...",
                    version,
                    scheme,
                    port,
                )
                await client.get(endpoint)
                _LOGGER.debug("%s protocol detected successfully using %s and port %s",
                    version,
                    scheme,
                    port,
                )
                return version
            except Exception as e:
                _LOGGER.debug("%s protocol detection failed using %s and port %s: %s",
                    version,
                    scheme,
                    port,
                    e
                )

        raise RuntimeError("Failed to detect any supported protocol version")

    @property
    def version(self) -> Literal["v1", "v2"]:
        """Get detected protocol version."""
        return self._version

    def _supports_battery_operations(self) -> bool:
        """Check if the current API version supports battery operations."""
        return self._version == "v2"

    # ========================================================================
    # Delegated API methods - Common to both V1 and V2
    # ========================================================================

    async def get_inverter_data(self, sn: str) -> GetInverterDataResponse:
        """Get inverter data.

        Args:
            sn: Inverter serial number

        Returns:
            GetInverterDataResponse: Inverter data
        """
        return await self._api.get_inverter_data(sn)

    async def get_inverter_info(self) -> GetInverterInfoResponse:
        """Get inverter info.

        Returns:
            GetInverterInfoResponse: Inverter info
        """
        return await self._api.get_inverter_info()

    async def get_meter_data(self) -> GetMeterDataResponse:
        """Get meter data.

        Returns:
            GetMeterDataResponse: Meter data
        """
        return await self._api.get_meter_data()

    async def get_meter_info(self) -> GetMeterInfoResponse:
        """Get meter info.

        Returns:
            GetMeterInfoResponse: Meter info
        """
        return await self._api.get_meter_info()

    # ========================================================================
    # Battery operations - V2 only
    # ========================================================================

    async def get_battery_data(self, sn: str) -> GetBatteryDataResponse:
        """Get battery data.

        Args:
            sn: Battery serial number

        Returns:
            GetBatteryDataResponse: Battery data

        Raises:
            NotImplementedError: If battery operations are not supported (V1 protocol)
        """
        if not self._supports_battery_operations():
            raise NotImplementedError("Battery operations are not supported in V1 protocol")
        return await self._api.get_battery_data(sn)

    async def get_battery_info(self, sn: str) -> GetBatteryInfoResponse:
        """Get battery info.

        Args:
            sn: Battery serial number

        Returns:
            GetBatteryInfoResponse: Battery info

        Raises:
            NotImplementedError: If battery operations are not supported (V1 protocol)
        """
        if not self._supports_battery_operations():
            raise NotImplementedError("Battery operations are not supported in V1 protocol")
        return await self._api.get_battery_info(sn)

    async def set_battery_work_mode(self, sn: str, mode: BatteryWorkMode) -> None:
        """Set battery work mode.

        Raises:
            NotImplementedError: If battery operations are not supported (V1 protocol)
        """
        if not self._supports_battery_operations():
            raise NotImplementedError("Battery operations are not supported in V1 protocol")
        await self._api.set_battery_work_mode(sn, mode)

    async def set_battery_soc_min(self, sn: str, soc_min: int) -> None:
        """Set battery minimum SOC.

        Raises:
            NotImplementedError: If battery operations are not supported (V1 protocol)
        """
        if not self._supports_battery_operations():
            raise NotImplementedError("Battery operations are not supported in V1 protocol")
        await self._api.set_battery_soc_min(sn, soc_min)

    async def set_battery_soc_max(self, sn: str, soc_max: int) -> None:
        """Set battery maximum SOC.

        Raises:
            NotImplementedError: If battery operations are not supported (V1 protocol)
        """
        if not self._supports_battery_operations():
            raise NotImplementedError("Battery operations are not supported in V1 protocol")
        await self._api.set_battery_soc_max(sn, soc_max)

    async def get_schedule(self) -> dict:
        """Get battery schedule configuration.

        Raises:
            NotImplementedError: If battery operations are not supported (V1 protocol)
        """
        if not self._supports_battery_operations():
            raise NotImplementedError("Battery operations are not supported in V1 protocol")
        return await self._api.get_schedule()

    async def set_schedule_power(
        self, pin: int | None = None, pout: int | None = None
    ) -> None:
        """Set battery schedule power configuration.

        Raises:
            NotImplementedError: If battery operations are not supported (V1 protocol)
        """
        if not self._supports_battery_operations():
            raise NotImplementedError("Battery operations are not supported in V1 protocol")
        await self._api.set_schedule_power(pin, pout)

    async def set_schedule_pin(self, pin: int) -> None:
        """Set battery schedule pin configuration.

        Raises:
            NotImplementedError: If battery operations are not supported (V1 protocol)
        """
        if not self._supports_battery_operations():
            raise NotImplementedError("Battery operations are not supported in V1 protocol")
        await self._api.set_schedule_pin(pin)

    async def set_schedule_pout(self, pout: int) -> None:
        """Set battery schedule pout configuration.

        Raises:
            NotImplementedError: If battery operations are not supported (V1 protocol)
        """
        if not self._supports_battery_operations():
            raise NotImplementedError("Battery operations are not supported in V1 protocol")
        await self._api.set_schedule_pout(pout)

    async def set_schedule_slots(self, schedule: dict) -> None:
        """Set battery schedule configuration directly with raw schedule.

        Raises:
            NotImplementedError: If battery operations are not supported (V1 protocol)
        """
        if not self._supports_battery_operations():
            raise NotImplementedError("Battery operations are not supported in V1 protocol")
        await self._api.set_schedule_slots(schedule)

    async def get_submeter_data(self) -> GetMeterDataResponse:
        """Get submeter data.

        Returns:
            GetMeterDataResponse: Meter data
        """
        if not self._version == "v2":
            raise NotImplementedError("Submeters are not supported in V1 protocol")
        return await self._api.get_submeter_data()

    # ========================================================================
    # Modbus methods (delegated to underlying API)
    # ========================================================================

    async def modbus_read_holding_registers(
        self,
        data_type: DataType,
        device_address: int,
        register_address: int,
        register_count: int = 1,
    ) -> dict | int | str | None:
        """Read modbus holding registers."""
        return await self._api.modbus_read_holding_registers(
            data_type, device_address, register_address, register_count
        )

    async def modbus_write_single_holding_register(
        self,
        data_type: DataType,
        device_address: int,
        register_address: int,
        value: int,
        dry_run: bool = False,
    ) -> dict | int | str | None:
        """Write modbus single holding register."""
        return await self._api.modbus_write_single_holding_register(
            data_type, device_address, register_address, value, dry_run
        )

    async def modbus_read_input_registers(
        self,
        data_type: DataType,
        device_address: int,
        register_address: int,
        register_count: int = 1,
    ) -> dict | int | str | None:
        """Read modbus input registers."""
        return await self._api.modbus_read_input_registers(
            data_type, device_address, register_address, register_count
        )
