"""Solplanet sensors platform."""

from collections import abc
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfInformation,
    UnitOfPower,
    UnitOfReactivePower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SolplanetConfigEntry
from .client import GetInverterDataResponse
from .const import (
    BATTERY_COMMUNICATION_STATUS,
    BATTERY_ERRORS_1,
    BATTERY_ERRORS_2,
    BATTERY_ERRORS_3,
    BATTERY_ERRORS_4,
    BATTERY_IDENTIFIER,
    BATTERY_STATUS,
    BATTERY_WARNINGS_1,
    BATTERY_WARNINGS_2,
    BATTERY_WARNINGS_3,
    BATTERY_WARNINGS_4,
    DONGLE_IDENTIFIER,
    DOMAIN,
    INVERTER_ERROR_CODES,
    INVERTER_IDENTIFIER,
    INVERTER_STATUS,
    METER_IDENTIFIER,
)
from .coordinator import SolplanetDataUpdateCoordinator
from .entity import SolplanetEntity, SolplanetEntityDescription

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SolplanetSensorEntityDescription(
    SolplanetEntityDescription, SensorEntityDescription
):
    """Describe Solplanet sensor entity."""


class SolplanetSensor(SolplanetEntity, SensorEntity):
    """Representation of a Solplanet sensor."""

    entity_description: SolplanetSensorEntityDescription
    _attr_native_value: float | int | str | None

    def __init__(
        self,
        description: SolplanetSensorEntityDescription,
        isn: str,
        coordinator: SolplanetDataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(description=description, isn=isn, coordinator=coordinator)


def _create_mppt_power_mapper(index: int) -> abc.Callable:
    def map_mppt_power(data: GetInverterDataResponse) -> float | None:
        if data.ipv and data.vpv:
            current = data.ipv[index] or 0
            voltage = data.vpv[index] or 0
            return current * voltage
        return None

    return map_mppt_power


def _create_dict_mapper(
    dictionary: dict, default: str = "Unknown (code: {value})"
) -> abc.Callable:
    def map_dict(value: str | int) -> str:
        return dictionary.get(value, default.replace("{value}", str(value)))

    return map_dict


def _create_dict_set_mapper(
    length: int,
    fields: list[str],
    errors: list[dict[int, str]],
    none_value: str,
    default: str = "Unknown (code: {value})",
):
    def map_set_dict(data: dict[str, int]) -> str:
        messages: list[str] = []
        for idx, field in enumerate(fields):
            value = getattr(data, field)

            if value is None:
                continue

            binary_str = bin(value)[2:].zfill(length)
            positions: list[str] = [
                errors[idx].get(i, default.replace("{value}", str(i)))
                for i in range(length)
                if binary_str[length - 1 - i] == "0"
            ]

            messages.extend(filter(lambda x: x is not None, positions))

        if not messages:
            return none_value

        result = ", ".join(messages)

        return result if len(result) <= 255 else f"{result[:252]}..."

    return map_set_dict


def create_inverter_entites_description(
    coordinator: SolplanetDataUpdateCoordinator, isn: str
) -> list[SolplanetSensorEntityDescription]:
    """Create entities for inverter."""
    sensors = [
        SolplanetSensorEntityDescription(
            key=f"{isn}_flg",
            name="Inverter Status",
            data_field_device_type=INVERTER_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["flg"],
            data_field_NaN_value=0xFF,
            device_class=SensorDeviceClass.ENUM,
            data_field_value_mapper=_create_dict_mapper(INVERTER_STATUS),
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_err",
            name="Error code",
            data_field_device_type=INVERTER_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["err"],
            data_field_value_mapper=_create_dict_mapper(INVERTER_ERROR_CODES),
            device_class=SensorDeviceClass.ENUM,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_fac",
            name="Frequency",
            data_field_device_type=INVERTER_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["fac"],
            data_field_NaN_value=0xFFFF,
            data_field_value_multiply=0.01,
            native_unit_of_measurement=UnitOfFrequency.HERTZ,
            device_class=SensorDeviceClass.FREQUENCY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_pac",
            name="Power",
            data_field_device_type=INVERTER_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["pac"],
            data_field_NaN_value=0xFFFFFFFF,
            native_unit_of_measurement=UnitOfPower.WATT,
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_sac",
            name="Apparent power",
            data_field_device_type=INVERTER_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["sac"],
            data_field_NaN_value=0xFFFFFFFF,
            native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
            device_class=SensorDeviceClass.APPARENT_POWER,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_qac",
            name="Reactive power",
            data_field_device_type=INVERTER_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["qac"],
            data_field_NaN_value=0x80000000,
            native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
            device_class=SensorDeviceClass.REACTIVE_POWER,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_pf",
            name="Power factor",
            data_field_device_type=INVERTER_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["pf"],
            data_field_value_multiply=0.01,
            device_class=SensorDeviceClass.POWER_FACTOR,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_eto",
            name="Energy produced total",
            data_field_device_type=INVERTER_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["eto"],  # codespell:ignore eto
            data_field_NaN_value=0xFFFFFFFF,
            data_field_value_multiply=0.1,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_etd",
            name="Energy produced today",
            data_field_device_type=INVERTER_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["etd"],
            data_field_NaN_value=0xFFFFFFFF,
            data_field_value_multiply=0.1,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_tmp",
            name="Temperature",
            data_field_device_type=INVERTER_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["tmp"],
            data_field_NaN_value=-32768,
            data_field_value_multiply=0.1,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_hto",
            name="Total working hours",
            data_field_device_type=INVERTER_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["hto"],
            data_field_NaN_value=0xFFFFFFFF,
            native_unit_of_measurement=UnitOfTime.HOURS,
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
    ]

    for i in range(3):
        sensors.extend(
            [
                SolplanetSensorEntityDescription(
                    key=f"{isn}_pac{i + 1}",
                    name=f"AC phase {i + 1} power",
                    data_field_device_type=INVERTER_IDENTIFIER,
                    data_field_data_type="data",
                    data_field_path=[f"pac{i + 1}"],
                    native_unit_of_measurement=UnitOfPower.WATT,
                    device_class=SensorDeviceClass.POWER,
                    state_class=SensorStateClass.MEASUREMENT,
                ),
                SolplanetSensorEntityDescription(
                    key=f"{isn}_qac{i + 1}",
                    name=f"AC phase {i + 1} reactive power",
                    data_field_device_type=INVERTER_IDENTIFIER,
                    data_field_data_type="data",
                    data_field_path=[f"qac{i + 1}"],
                    native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
                    device_class=SensorDeviceClass.REACTIVE_POWER,
                    state_class=SensorStateClass.MEASUREMENT,
                ),
            ]
        )

    data: GetInverterDataResponse = coordinator.data[INVERTER_IDENTIFIER][isn]["data"]

    for i in range(len(data.vac or [])):
        sensors.extend(
            [
                SolplanetSensorEntityDescription(
                    key=f"{isn}_vac_{i}",
                    name=f"AC phase {i + 1!s} voltage",
                    data_field_device_type=INVERTER_IDENTIFIER,
                    data_field_data_type="data",
                    data_field_path=["vac", i],
                    data_field_value_multiply=0.1,
                    native_unit_of_measurement=UnitOfElectricPotential.VOLT,
                    device_class=SensorDeviceClass.VOLTAGE,
                    state_class=SensorStateClass.MEASUREMENT,
                ),
                SolplanetSensorEntityDescription(
                    key=f"{isn}_iac_{i}",
                    name=f"AC phase {i + 1!s} current",
                    data_field_device_type=INVERTER_IDENTIFIER,
                    data_field_data_type="data",
                    data_field_path=["iac", i],
                    data_field_value_multiply=0.1,
                    native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
                    device_class=SensorDeviceClass.CURRENT,
                    state_class=SensorStateClass.MEASUREMENT,
                ),
            ]
        )

    for i in range(len(data.vpv or [])):
        sensors.extend(
            [
                SolplanetSensorEntityDescription(
                    key=f"{isn}_vpv_{i}",
                    name=f"MPPT {i + 1!s} voltage",
                    data_field_device_type=INVERTER_IDENTIFIER,
                    data_field_data_type="data",
                    data_field_path=["vpv", i],
                    data_field_value_multiply=0.1,
                    native_unit_of_measurement=UnitOfElectricPotential.VOLT,
                    device_class=SensorDeviceClass.VOLTAGE,
                    state_class=SensorStateClass.MEASUREMENT,
                ),
                SolplanetSensorEntityDescription(
                    key=f"{isn}_ipv_{i}",
                    name=f"MPPT {i + 1!s} current",
                    data_field_device_type=INVERTER_IDENTIFIER,
                    data_field_data_type="data",
                    data_field_path=["ipv", i],
                    data_field_value_multiply=0.01,
                    native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
                    device_class=SensorDeviceClass.CURRENT,
                    state_class=SensorStateClass.MEASUREMENT,
                ),
                SolplanetSensorEntityDescription(
                    key=f"{isn}_mppt_power_{i}",
                    name=f"MPPT {i + 1!s} power",
                    data_field_device_type=INVERTER_IDENTIFIER,
                    data_field_data_type="data",
                    data_field_path=[],
                    data_field_value_mapper=_create_mppt_power_mapper(i),
                    data_field_value_multiply=0.001,
                    unique_id_suffix=f"mppt_{i}_power",
                    native_unit_of_measurement=UnitOfPower.WATT,
                    device_class=SensorDeviceClass.POWER,
                    state_class=SensorStateClass.MEASUREMENT,
                ),
            ]
        )

    return sensors


def create_meter_entites_description(
    coordinator: SolplanetDataUpdateCoordinator, isn: str
) -> list[SolplanetSensorEntityDescription]:
    """Create entities for meter."""
    return [
        SolplanetSensorEntityDescription(
            key=f"{isn}_pac",
            name="Grid power",
            data_field_device_type=METER_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["pac"],
            native_unit_of_measurement=UnitOfPower.WATT,
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_iet",
            name="Grid energy in total",
            data_field_device_type=METER_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["iet"],
            data_field_value_multiply=0.1,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_oet",
            name="Grid energy out total",
            data_field_device_type=METER_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["oet"],
            data_field_value_multiply=0.1,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_itd",
            name="Grid energy in today",
            data_field_device_type=METER_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["itd"],
            data_field_value_multiply=0.01,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_otd",
            name="Grid energy out today",
            data_field_device_type=METER_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["otd"],
            data_field_value_multiply=0.01,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
    ]


def create_dongle_entites_description(
    coordinator: SolplanetDataUpdateCoordinator, dongle_id: str
) -> list[SolplanetSensorEntityDescription]:
    """Create diagnostic entities for the dongle (V2)."""

    def _stringify(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value)
        return text if len(text) <= 255 else f"{text[:252]}..."

    def _warnings_text(value: Any) -> str:
        # Endpoint behavior observed: it may 404 (no warnings) or otherwise be missing.
        if value is None:
            return "No warnings"
        if isinstance(value, dict) and not value:
            return "No warnings"
        return _stringify(value) or "No warnings"

    return [
        # ---- Common / useful diagnostics (enabled by default) ----
        SolplanetSensorEntityDescription(
            key=f"{dongle_id}_network_mode",
            name="Network mode",
            entity_category=EntityCategory.DIAGNOSTIC,
            data_field_device_type=DONGLE_IDENTIFIER,
            data_field_data_type="network",
            data_field_path=["mode"],
            data_field_value_mapper=_stringify,
        ),
        SolplanetSensorEntityDescription(
            key=f"{dongle_id}_network_ssid",
            name="WiFi SSID",
            icon="mdi:wifi",
            entity_category=EntityCategory.DIAGNOSTIC,
            data_field_device_type=DONGLE_IDENTIFIER,
            data_field_data_type="network",
            data_field_path=["sid"],
            data_field_value_mapper=_stringify,
        ),
        SolplanetSensorEntityDescription(
            key=f"{dongle_id}_wifi_rssi",
            name="WiFi signal strength",
            icon="mdi:wifi",
            entity_category=EntityCategory.DIAGNOSTIC,
            data_field_device_type=DONGLE_IDENTIFIER,
            data_field_data_type="network",
            data_field_path=["srh"],
            native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
            device_class=SensorDeviceClass.SIGNAL_STRENGTH,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SolplanetSensorEntityDescription(
            key=f"{dongle_id}_network_ip",
            name="IP address",
            entity_category=EntityCategory.DIAGNOSTIC,
            data_field_device_type=DONGLE_IDENTIFIER,
            data_field_data_type="network",
            data_field_path=["ip"],
            data_field_value_mapper=_stringify,
        ),
        SolplanetSensorEntityDescription(
            key=f"{dongle_id}_network_gateway",
            name="Gateway",
            entity_category=EntityCategory.DIAGNOSTIC,
            data_field_device_type=DONGLE_IDENTIFIER,
            data_field_data_type="network",
            data_field_path=["gtw"],
            data_field_value_mapper=_stringify,
        ),
        SolplanetSensorEntityDescription(
            key=f"{dongle_id}_network_netmask",
            name="Netmask",
            entity_category=EntityCategory.DIAGNOSTIC,
            data_field_device_type=DONGLE_IDENTIFIER,
            data_field_data_type="network",
            data_field_path=["msk"],
            data_field_value_mapper=_stringify,
        ),
        SolplanetSensorEntityDescription(
            key=f"{dongle_id}_warnings",
            name="Warnings",
            icon="mdi:alert-circle-outline",
            entity_category=EntityCategory.DIAGNOSTIC,
            data_field_device_type=DONGLE_IDENTIFIER,
            data_field_data_type="warnings",
            data_field_path=[],
            data_field_value_mapper=_warnings_text,
        ),
    ]


def create_battery_entites_description(
    coordinator: SolplanetDataUpdateCoordinator, isn: str
) -> list[SolplanetSensorEntityDescription]:
    """Create entities for battery."""
    sensors = [
        SolplanetSensorEntityDescription(
            key=f"{isn}_cst",
            name="Communication status",
            data_field_device_type=BATTERY_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["cst"],
            data_field_value_mapper=_create_dict_mapper(
                BATTERY_COMMUNICATION_STATUS, "Fault (code: {value})"
            ),
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_bst",
            name="Battery status",
            data_field_device_type=BATTERY_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["bst"],
            data_field_value_mapper=_create_dict_mapper(BATTERY_STATUS),
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_eb1",
            name="Battery errors",
            data_field_device_type=BATTERY_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=[],
            data_field_value_mapper=_create_dict_set_mapper(
                16,
                ["eb1", "eb2", "eb3", "eb4"],
                [
                    BATTERY_ERRORS_1,
                    BATTERY_ERRORS_2,
                    BATTERY_ERRORS_3,
                    BATTERY_ERRORS_4,
                ],
                "No errors",
            ),
            unique_id_suffix="eb1",
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_wb1",
            name="Battery warnings",
            data_field_device_type=BATTERY_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=[],
            data_field_value_mapper=_create_dict_set_mapper(
                16,
                ["wb1", "wb2", "wb3", "wb4"],
                [
                    BATTERY_WARNINGS_1,
                    BATTERY_WARNINGS_2,
                    BATTERY_WARNINGS_3,
                    BATTERY_WARNINGS_4,
                ],
                "No warnings",
            ),
            unique_id_suffix="wb1",
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_ppv",
            name="PV power",
            data_field_device_type=BATTERY_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["ppv"],
            native_unit_of_measurement=UnitOfPower.WATT,
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_etdpv",
            name="PV energy today",
            data_field_device_type=BATTERY_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["etdpv"],
            data_field_value_multiply=0.1,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_etopv",
            name="PV energy total",
            data_field_device_type=BATTERY_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["etopv"],
            data_field_value_multiply=0.1,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_vb",
            name="Battery voltage",
            data_field_device_type=BATTERY_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["vb"],
            data_field_value_multiply=0.01,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_cb",
            name="Battery current",
            data_field_device_type=BATTERY_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["cb"],
            data_field_value_multiply=0.1,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_pb",
            name="Battery power",
            data_field_device_type=BATTERY_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["pb"],
            native_unit_of_measurement=UnitOfPower.WATT,
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_tb",
            name="Battery temperature",
            data_field_device_type=BATTERY_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["tb"],
            data_field_value_multiply=0.1,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_soc",
            name="Battery state of charge",
            data_field_device_type=BATTERY_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["soc"],
            native_unit_of_measurement=PERCENTAGE,
            device_class=SensorDeviceClass.BATTERY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_soh",
            name="Battery state of health",
            data_field_device_type=BATTERY_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["soh"],
            native_unit_of_measurement=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_cli",
            name="Current limit for charging",
            data_field_device_type=BATTERY_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["cli"],
            data_field_value_multiply=0.1,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_clo",
            name="Current limit for discharging",
            data_field_device_type=BATTERY_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["clo"],
            data_field_value_multiply=0.1,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_ebi",
            name="Battery energy for charging",
            data_field_device_type=BATTERY_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["ebi"],
            data_field_value_multiply=0.1,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_ebo",
            name="Battery energy for discharging",
            data_field_device_type=BATTERY_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["ebo"],
            data_field_value_multiply=0.1,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_eaci",
            name="AC energy for charging",
            data_field_device_type=BATTERY_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["eaci"],
            data_field_value_multiply=0.1,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_eaco",
            name="AC energy for discharging",
            data_field_device_type=BATTERY_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["eaco"],
            data_field_value_multiply=0.1,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_vesp",
            name="EPS voltage",
            data_field_device_type=BATTERY_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["vesp"],
            data_field_value_multiply=0.1,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_cesp",
            name="EPS current",
            data_field_device_type=BATTERY_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["cesp"],
            data_field_value_multiply=0.1,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_fesp",
            name="EPS frequency",
            data_field_device_type=BATTERY_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["fesp"],
            data_field_value_multiply=0.01,
            native_unit_of_measurement=UnitOfFrequency.HERTZ,
            device_class=SensorDeviceClass.FREQUENCY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_pesp",
            name="EPS power",
            data_field_device_type=BATTERY_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["pesp"],
            native_unit_of_measurement=UnitOfPower.WATT,
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_rpesp",
            name="EPS reactive power",
            data_field_device_type=BATTERY_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["rpesp"],
            native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
            device_class=SensorDeviceClass.REACTIVE_POWER,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_etdesp",
            name="EPS energy today",
            data_field_device_type=BATTERY_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["etdesp"],
            data_field_value_multiply=0.1,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_etoesp",
            name="EPS energy total",
            data_field_device_type=BATTERY_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["etoesp"],
            data_field_value_multiply=0.1,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_charge_ac_td",
            name="AC charge today",
            data_field_device_type=BATTERY_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["charge_ac_td"],
            data_field_value_multiply=0.1,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_charge_ac_to",
            name="AC charge total",
            data_field_device_type=BATTERY_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=["charge_ac_to"],
            data_field_value_multiply=0.1,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
    ]

    for i in range(3):
        sensors.extend(
            [
                SolplanetSensorEntityDescription(
                    key=f"{isn}_vl{i + 1}esp",
                    name=f"EPS phase {i + 1} current",
                    data_field_device_type=BATTERY_IDENTIFIER,
                    data_field_data_type="data",
                    data_field_path=[f"vl{i + 1}esp"],
                    data_field_value_multiply=0.1,
                    native_unit_of_measurement=UnitOfElectricPotential.VOLT,
                    device_class=SensorDeviceClass.VOLTAGE,
                    state_class=SensorStateClass.MEASUREMENT,
                ),
                SolplanetSensorEntityDescription(
                    key=f"{isn}_il{i + 1}esp",
                    name=f"EPS phase {i + 1} voltage",
                    data_field_device_type=BATTERY_IDENTIFIER,
                    data_field_data_type="data",
                    data_field_path=[f"il{i + 1}esp"],
                    data_field_value_multiply=0.1,
                    native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
                    device_class=SensorDeviceClass.CURRENT,
                    state_class=SensorStateClass.MEASUREMENT,
                ),
                SolplanetSensorEntityDescription(
                    key=f"{isn}_pac{i + 1}esp",
                    name=f"EPS phase {i + 1} power",
                    data_field_device_type=BATTERY_IDENTIFIER,
                    data_field_data_type="data",
                    data_field_path=[f"pac{i + 1}esp"],
                    native_unit_of_measurement=UnitOfPower.WATT,
                    device_class=SensorDeviceClass.POWER,
                    state_class=SensorStateClass.MEASUREMENT,
                ),
                SolplanetSensorEntityDescription(
                    key=f"{isn}_qac{i + 1}esp",
                    name=f"EPS phase {i + 1} reactive power",
                    data_field_device_type=BATTERY_IDENTIFIER,
                    data_field_data_type="data",
                    data_field_path=[f"qac{i + 1}esp"],
                    native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
                    device_class=SensorDeviceClass.REACTIVE_POWER,
                    state_class=SensorStateClass.MEASUREMENT,
                ),
            ]
        )

    return sensors


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolplanetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for Solplanet Inverter from a config entry."""
    coordinator: SolplanetDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    sensors: list[SolplanetSensor] = []

    for dongle_id in coordinator.data.get(DONGLE_IDENTIFIER, {}):
        sensors.extend(
            SolplanetSensor(
                description=entity_description,
                isn=dongle_id,
                coordinator=coordinator,
            )
            for entity_description in create_dongle_entites_description(
                coordinator, dongle_id
            )
        )

    for isn in coordinator.data[INVERTER_IDENTIFIER]:
        sensors.extend(
            SolplanetSensor(
                description=entity_description,
                isn=isn,
                coordinator=coordinator,
            )
            for entity_description in create_inverter_entites_description(
                coordinator, isn
            )
        )

    for isn in coordinator.data[BATTERY_IDENTIFIER]:
        sensors.extend(
            SolplanetSensor(
                description=entity_description,
                isn=isn,
                coordinator=coordinator,
            )
            for entity_description in create_battery_entites_description(
                coordinator, isn
            )
        )

    for isn in coordinator.data[METER_IDENTIFIER]:
        sensors.extend(
            SolplanetSensor(
                description=entity_description,
                isn=isn,
                coordinator=coordinator,
            )
            for entity_description in create_meter_entites_description(coordinator, isn)
        )

    # Always add entities. If the inverter is slow/sleeping at startup, filtering here would
    # permanently prevent entities from being created.
    async_add_entities(sensors)
