"""Solplanet client for solplanet integration."""

from dataclasses import dataclass
import logging

import aiohttp

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

    flg: int
    tim: str
    tmp: int
    fac: int
    pac: int
    sac: int
    qac: int
    eto: int
    etd: int
    hto: int
    pf: int
    wan: int
    err: int
    vac: list[int]
    iac: list[int]
    vpv: list[int]
    ipv: list[int]
    str: list[int]


@dataclass
class GetInverterInfoItemResponse:
    """Get inverter info item response."""

    isn: str
    add: int
    safety: int
    rate: int
    msw: str
    ssw: str
    tsw: str
    pac: int
    etd: int
    eto: int
    err: int
    cmv: str
    mty: int
    model: str


@dataclass
class GetInverterInfoResponse:
    """Get inverter info response."""

    inv: list[GetInverterInfoItemResponse]
    num: int


class SolplanetClient:
    """Solplanet http client."""

    def __init__(self, host: str) -> None:
        """Create instance of solplanet http client."""
        self.host = host
        self.port = 8484

    def get_url(self, endpoint: str) -> str:
        """Get URL for specified endpoint."""
        return "http://" + self.host + ":" + str(self.port) + "/" + endpoint

    async def get(self, endpoint: str):
        """Make get request to specified endpoint."""
        session = aiohttp.ClientSession()
        response = await session.get(self.get_url(endpoint))
        result = await response.json()
        await session.close()
        return result


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
        return GetInverterDataResponse(**response)

    async def get_inverter_info(self) -> GetInverterInfoResponse:
        """Get inverter info."""
        _LOGGER.debug("Getting inverter info")
        response = await self.client.get("getdev.cgi?device=2")
        response["inv"] = [
            GetInverterInfoItemResponse(**item) for item in response["inv"]
        ]
        return GetInverterInfoResponse(**response)
