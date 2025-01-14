"""Solplanet sensors platform."""

from collections import abc
from dataclasses import dataclass
import logging
import re
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfReactivePower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import INVERTER_IDENTIFIER, SolplanetConfigEntry
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
    DOMAIN,
    INVERTER_ERROR_CODES,
    INVERTER_STATUS,
    METER_IDENTIFIER,
)
from .coordinator import SolplanetDataUpdateCoordinator
from .exceptions import InverterInSleepModeError

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SolplanetSensorEntityDescription(SensorEntityDescription):
    """Describe Solplanet sensor entity."""

    data_field_device_type: str
    data_field_path: list[str | int]
    data_field_data_type: str
    data_field_NaN_value: int | None = None  # noqa: N815
    data_field_value_multiply: float | None = None
    data_field_value_mapper: abc.Callable[[Any], Any] | None = None
    unique_id_suffix: str | None = None


class SolplanetSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Solplanet sensor."""

    entity_description: SolplanetSensorEntityDescription
    unique_id_suffix: str
    sanitized_entity_id: str

    def __init__(
        self,
        description: SolplanetSensorEntityDescription,
        isn: str,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self.unique_id_suffix = (
            description.unique_id_suffix
            if description.unique_id_suffix
            else "_".join(str(x) for x in description.data_field_path)
        )
        self.sanitized_entity_id = self._sanitize_string_for_entity_id(
            f"{isn}_{description.name}"
        )
        self._isn = isn
        self._set_native_value()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._set_native_value()
        super()._handle_coordinator_update()

    def _set_native_value(self) -> None:
        try:
            self._attr_native_value = self._get_value_from_coordinator()
        except InverterInSleepModeError:
            _LOGGER.debug(
                "Component serial number not in data - this is normal if the inverter is sleeping"
            )

    def _get_value_from_coordinator(self) -> float | int | str | None:
        """Return the state of the sensor."""
        try:
            data = self.coordinator.data[
                self.entity_description.data_field_device_type
            ][self._isn][self.entity_description.data_field_data_type]
        except KeyError:
            raise InverterInSleepModeError from None

        for path_item in self.entity_description.data_field_path:
            if (isinstance(data, list) and len(data) > 0) or hasattr(data, "__dict__"):
                data = (
                    data[int(path_item)]
                    if isinstance(data, list)
                    else getattr(data, str(path_item))
                )
            else:
                return None

        if self.entity_description.data_field_value_mapper is not None:
            data = self.entity_description.data_field_value_mapper(data)

        if (
            self.entity_description.data_field_NaN_value is not None
            and data == self.entity_description.data_field_NaN_value
        ):
            _LOGGER.debug("NaN value received from Inverter")
            return None

        if (
            data is not None
            and self.entity_description.data_field_value_multiply is not None
        ):
            data = data * self.entity_description.data_field_value_multiply

        return data

    def _sanitize_string_for_entity_id(self, input_string: str) -> str:
        sanitized_string = input_string.lower()
        sanitized_string = re.sub(r"[^a-z0-9_]+", "_", sanitized_string)
        sanitized_string = re.sub(r"_+", "_", sanitized_string)
        return sanitized_string.strip("_")


class SolplanetInverterSensor(SolplanetSensor):
    """Representation of a Solplanet Inverter sensor."""

    def __init__(
        self,
        description: SolplanetSensorEntityDescription,
        isn: str,
        coordinator: SolplanetDataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(description, isn, coordinator)

        self.entity_id = f"sensor.solplanet_{self.sanitized_entity_id}"
        self._attr_unique_id = f"solplanet_{isn}_{self.unique_id_suffix}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this sensor."""
        return {
            "identifiers": {(DOMAIN, self._isn)},
        }


class SolplanetBatterySensor(SolplanetSensor):
    """Representation of a Solplanet Battery sensor."""

    def __init__(
        self,
        description: SolplanetSensorEntityDescription,
        isn: str,
        coordinator: SolplanetDataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(description, isn, coordinator)

        self.entity_id = (
            f"sensor.solplanet_{BATTERY_IDENTIFIER}_{self.sanitized_entity_id}"
        )
        self._attr_unique_id = (
            f"solplanet_{BATTERY_IDENTIFIER}_{isn}_{self.unique_id_suffix}"
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this sensor."""
        return {
            "identifiers": {(DOMAIN, f"{BATTERY_IDENTIFIER}_{self._isn}")},
        }


class SolplanetMeterSensor(SolplanetSensor):
    """Representation of a Solplanet Meter sensor."""

    def __init__(
        self,
        description: SolplanetSensorEntityDescription,
        isn: str,
        coordinator: SolplanetDataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(description, isn, coordinator)

        self.entity_id = (
            f"sensor.solplanet_{METER_IDENTIFIER}_{self.sanitized_entity_id}"
        )
        self._attr_unique_id = (
            f"solplanet_{METER_IDENTIFIER}_{isn}_{self.unique_id_suffix}"
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this sensor."""
        return {
            "identifiers": {(DOMAIN, f"{METER_IDENTIFIER}_{self._isn or ""}")},
        }


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
            data_field_path=["eto"],
            data_field_NaN_value=0xFFFFFFFF,
            data_field_value_multiply=0.1,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
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
        sensors.append(  # noqa: PERF401
            SolplanetSensorEntityDescription(
                key=f"{isn}_pac{i+1}",
                name=f"AC phase {i+1} power",
                data_field_device_type=INVERTER_IDENTIFIER,
                data_field_data_type="data",
                data_field_path=[f"pac{i+1}"],
                native_unit_of_measurement=UnitOfPower.WATT,
                device_class=SensorDeviceClass.POWER,
                state_class=SensorStateClass.MEASUREMENT,
            ),
        )
        sensors.append(  # noqa: PERF401
            SolplanetSensorEntityDescription(
                key=f"{isn}_qac{i+1}",
                name=f"AC phase {i+1} reactive power",
                data_field_device_type=INVERTER_IDENTIFIER,
                data_field_data_type="data",
                data_field_path=[f"qac{i+1}"],
                native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
                device_class=SensorDeviceClass.REACTIVE_POWER,
                state_class=SensorStateClass.MEASUREMENT,
            ),
        )

    data: GetInverterDataResponse = coordinator.data[INVERTER_IDENTIFIER][isn]["data"]

    for i in range(len(data.vac or [])):
        sensors.append(  # noqa: PERF401
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
        )

    for i in range(len(data.iac or [])):
        sensors.append(  # noqa: PERF401
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
        )

    for i in range(len(data.vpv or [])):
        sensors.append(  # noqa: PERF401
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
        )

    for i in range(len(data.ipv or [])):
        sensors.append(  # noqa: PERF401
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
        )

    for i in range(len(data.ipv or [])):
        sensors.append(  # noqa: PERF401
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
            state_class=SensorStateClass.TOTAL_INCREASING,
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
            state_class=SensorStateClass.TOTAL_INCREASING,
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
            state_class=SensorStateClass.TOTAL_INCREASING,
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
            state_class=SensorStateClass.TOTAL_INCREASING,
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
        sensors.append(  # noqa: PERF401
            SolplanetSensorEntityDescription(
                key=f"{isn}_vl{i+1}esp",
                name=f"EPS phase {i+1} current",
                data_field_device_type=BATTERY_IDENTIFIER,
                data_field_data_type="data",
                data_field_path=[f"vl{i+1}esp"],
                data_field_value_multiply=0.1,
                native_unit_of_measurement=UnitOfElectricPotential.VOLT,
                device_class=SensorDeviceClass.VOLTAGE,
                state_class=SensorStateClass.MEASUREMENT,
            ),
        )
        sensors.append(  # noqa: PERF401
            SolplanetSensorEntityDescription(
                key=f"{isn}_il{i+1}esp",
                name=f"EPS phase {i+1} voltage",
                data_field_device_type=BATTERY_IDENTIFIER,
                data_field_data_type="data",
                data_field_path=[f"il{i+1}esp"],
                data_field_value_multiply=0.1,
                native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
                device_class=SensorDeviceClass.CURRENT,
                state_class=SensorStateClass.MEASUREMENT,
            ),
        )
        sensors.append(  # noqa: PERF401
            SolplanetSensorEntityDescription(
                key=f"{isn}_pac{i+1}esp",
                name=f"EPS phase {i+1} power",
                data_field_device_type=BATTERY_IDENTIFIER,
                data_field_data_type="data",
                data_field_path=[f"pac{i+1}esp"],
                native_unit_of_measurement=UnitOfPower.WATT,
                device_class=SensorDeviceClass.POWER,
                state_class=SensorStateClass.MEASUREMENT,
            ),
        )
        sensors.append(  # noqa: PERF401
            SolplanetSensorEntityDescription(
                key=f"{isn}_qac{i+1}esp",
                name=f"EPS phase {i+1} reactive power",
                data_field_device_type=BATTERY_IDENTIFIER,
                data_field_data_type="data",
                data_field_path=[f"qac{i+1}esp"],
                native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
                device_class=SensorDeviceClass.REACTIVE_POWER,
                state_class=SensorStateClass.MEASUREMENT,
            ),
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

    for isn in coordinator.data[INVERTER_IDENTIFIER]:
        async_add_entities(
            SolplanetInverterSensor(
                description=entity_description,
                isn=isn,
                coordinator=coordinator,
            )
            for entity_description in create_inverter_entites_description(
                coordinator, isn
            )
        )

    for isn in coordinator.data[BATTERY_IDENTIFIER]:
        async_add_entities(
            SolplanetBatterySensor(
                description=entity_description,
                isn=isn,
                coordinator=coordinator,
            )
            for entity_description in create_battery_entites_description(
                coordinator, isn
            )
        )

    for isn in coordinator.data[METER_IDENTIFIER]:
        async_add_entities(
            SolplanetMeterSensor(
                description=entity_description,
                isn=isn,
                coordinator=coordinator,
            )
            for entity_description in create_meter_entites_description(coordinator, isn)
        )
