"""Solplanet sensors platform."""

from dataclasses import dataclass
import re

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfReactivePower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SolplanetConfigEntry
from .client import GetInverterDataResponse
from .const import DOMAIN
from .coordinator import SolplanetInverterDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class SolplanetSensorEntityDescription(SensorEntityDescription):
    """Describe Solplanet sensor entity."""

    data_field_name: str
    data_field_index: int | None = None
    data_field_value_multiply: float | None = None


class SolplanetInverterSensor(
    CoordinatorEntity[SolplanetInverterDataUpdateCoordinator], SensorEntity
):
    """Representation of a Solplanet Inverter sensor."""

    entity_description: SolplanetSensorEntityDescription

    def __init__(
        self,
        description: SolplanetSensorEntityDescription,
        isn: str,
        coordinator: SolplanetInverterDataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        sanitized_entity_id = self._sanitize_string_for_entity_id(
            f"{isn}_{description.name}"
        )
        self.entity_id = f"sensor.solplanet_{sanitized_entity_id}"
        self._isn = isn
        self._attr_unique_id = f"solplanet_{isn}_{description.data_field_name}_{description.data_field_index}"
        self._attr_native_value = self._get_value_from_coordinator()
        self._attr_entity_registry_enabled_default = self._attr_native_value is not None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this sensor."""
        return {
            "identifiers": {(DOMAIN, self._isn)},
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Set the native value here so we can use it in available property
        # without having to recalculate it
        self._attr_native_value = self._get_value_from_coordinator()
        super()._handle_coordinator_update()

    def _get_value_from_coordinator(self) -> float:
        """Return the state of the sensor."""
        data = getattr(
            self.coordinator.data[self._isn], self.entity_description.data_field_name
        )

        if self.entity_description.data_field_index is not None:
            data = data[self.entity_description.data_field_index]

        if self.entity_description.data_field_value_multiply is not None:
            data = data * self.entity_description.data_field_value_multiply

        return data

    def _sanitize_string_for_entity_id(self, input_string: str) -> str:
        sanitized_string = input_string.lower()
        sanitized_string = re.sub(r"[^a-z0-9_]+", "_", sanitized_string)
        sanitized_string = re.sub(r"_+", "_", sanitized_string)
        return sanitized_string.strip("_")


def create_inverter_entites_description(
    coordinator: SolplanetInverterDataUpdateCoordinator, isn: str
) -> list[SolplanetSensorEntityDescription]:
    """Create entities for inverter."""
    data: GetInverterDataResponse = coordinator.data[isn]

    sensors = [
        SolplanetSensorEntityDescription(
            key=f"{isn}_pac",
            name="Power",
            data_field_name="pac",
            native_unit_of_measurement=UnitOfPower.WATT,
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_sac",
            name="Apparent power",
            data_field_name="sac",
            native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
            device_class=SensorDeviceClass.APPARENT_POWER,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_qac",
            name="Reactive / complex power",
            data_field_name="qac",
            native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
            device_class=SensorDeviceClass.REACTIVE_POWER,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_pf",
            name="Power factor",
            data_field_name="pf",
            device_class=SensorDeviceClass.POWER_FACTOR,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_eto",
            name="Energy produced total",
            data_field_name="eto",
            data_field_value_multiply=0.1,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_etd",
            name="Energy produced today",
            data_field_name="etd",
            data_field_value_multiply=0.1,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_tmp",
            name="Temperature",
            data_field_name="tmp",
            data_field_value_multiply=0.1,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SolplanetSensorEntityDescription(
            key=f"{isn}_hto",
            name="Total working hours",
            data_field_name="hto",
            native_unit_of_measurement=UnitOfTime.HOURS,
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
    ]

    for i in range(len(data.vac or [])):
        sensors.append(  # noqa: PERF401
            SolplanetSensorEntityDescription(
                key=f"{isn}_vac_{i}",
                name="AC voltage phase " + str(i + 1),
                data_field_name="vac",
                data_field_index=i,
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
                name="AC current phase " + str(i + 1),
                data_field_name="iac",
                data_field_index=i,
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
                name="DC voltage string " + str(i + 1),
                data_field_name="vpv",
                data_field_index=i,
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
                name="DC current string " + str(i + 1),
                data_field_name="ipv",
                data_field_index=i,
                data_field_value_multiply=0.01,
                native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
                device_class=SensorDeviceClass.CURRENT,
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
    coordinator: SolplanetInverterDataUpdateCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]

    for isn in coordinator.data:
        async_add_entities(
            SolplanetInverterSensor(
                description=entity_description, isn=isn, coordinator=coordinator
            )
            for entity_description in create_inverter_entites_description(
                coordinator, isn
            )
        )
