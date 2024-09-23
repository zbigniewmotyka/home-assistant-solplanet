"""Solplanet sensors platform."""

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SolplanetConfigEntry
from .client import GetInverterDataResponse
from .const import DOMAIN
from .coordinator import SolplanetInverterDataCoordinator


def create_inverter_entites(coordinator: SolplanetInverterDataCoordinator, isn: str):
    """Create entities for inverter."""
    data: GetInverterDataResponse = coordinator.data[isn]

    sensors = [
        SolplanetInverterSensor(
            isn,
            coordinator,
            "Power",
            "pac",
            None,
            1,
            UnitOfPower.WATT,
            SensorDeviceClass.POWER,
            SensorStateClass.MEASUREMENT,
        ),
        SolplanetInverterSensor(
            isn,
            coordinator,
            "Apparent power",
            "sac",
            None,
            1,
            UnitOfApparentPower.VOLT_AMPERE,
            SensorDeviceClass.APPARENT_POWER,
            SensorStateClass.MEASUREMENT,
        ),
        SolplanetInverterSensor(
            isn,
            coordinator,
            "Reactive / complex power",
            "qac",
            None,
            1,
            UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
            SensorDeviceClass.REACTIVE_POWER,
            SensorStateClass.MEASUREMENT,
        ),
        SolplanetInverterSensor(
            isn,
            coordinator,
            "Power factor",
            "pf",
            None,
            1,
            None,
            SensorDeviceClass.POWER_FACTOR,
            SensorStateClass.MEASUREMENT,
        ),
        SolplanetInverterSensor(
            isn,
            coordinator,
            "Energy produced total",
            "eto",
            None,
            0.1,
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL_INCREASING,
        ),
        SolplanetInverterSensor(
            isn,
            coordinator,
            "Energy produced today",
            "etd",
            None,
            0.1,
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL_INCREASING,
        ),
        SolplanetInverterSensor(
            isn,
            coordinator,
            "Temperature",
            "tmp",
            None,
            0.1,
            UnitOfTemperature.CELSIUS,
            SensorDeviceClass.TEMPERATURE,
            SensorStateClass.MEASUREMENT,
        ),
        SolplanetInverterSensor(
            isn,
            coordinator,
            "Total working hours",
            "hto",
            None,
            1,
            UnitOfTime.HOURS,
            SensorDeviceClass.DURATION,
            SensorStateClass.MEASUREMENT,
        ),
    ]

    for i in range(len(data.vac)):
        sensors.append(  # noqa: PERF401
            SolplanetInverterSensor(
                isn,
                coordinator,
                "AC voltage phase " + str(i + 1),
                "vac",
                i,
                0.1,
                UnitOfElectricPotential.VOLT,
                SensorDeviceClass.VOLTAGE,
                SensorStateClass.MEASUREMENT,
            )
        )

    for i in range(len(data.iac)):
        sensors.append(  # noqa: PERF401
            SolplanetInverterSensor(
                isn,
                coordinator,
                "AC current phase " + str(i + 1),
                "iac",
                i,
                0.1,
                UnitOfElectricCurrent.AMPERE,
                SensorDeviceClass.CURRENT,
                SensorStateClass.MEASUREMENT,
            ),
        )

    for i in range(len(data.vpv)):
        sensors.append(  # noqa: PERF401
            SolplanetInverterSensor(
                isn,
                coordinator,
                "DC voltage string " + str(i + 1),
                "vpv",
                i,
                0.1,
                UnitOfElectricPotential.VOLT,
                SensorDeviceClass.VOLTAGE,
                SensorStateClass.MEASUREMENT,
            ),
        )

    for i in range(len(data.ipv)):
        sensors.append(  # noqa: PERF401
            SolplanetInverterSensor(
                isn,
                coordinator,
                "DC current string " + str(i + 1),
                "ipv",
                i,
                0.01,
                UnitOfElectricCurrent.AMPERE,
                SensorDeviceClass.CURRENT,
                SensorStateClass.MEASUREMENT,
            ),
        )

    return sensors


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolplanetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for Solplanet Inverter from a config entry."""
    coordinator: SolplanetInverterDataCoordinator = hass.data[DOMAIN][entry.entry_id]

    for isn in coordinator.data:
        async_add_entities(create_inverter_entites(coordinator, isn))


class SolplanetInverterSensor(CoordinatorEntity, Entity):
    """Representation of a Solplanet Inverter sensor."""

    def __init__(
        self,
        isn: str,
        coordinator: SolplanetInverterDataCoordinator,
        name: str,
        key: str,
        item_index: int | None,
        multiply: float,
        unit: str | None,
        device_class: SensorDeviceClass,
        state_class: SensorStateClass,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._isn = isn
        self._multiply = multiply
        self._name = name
        self._key = key
        self._item_index = item_index
        self._unit = unit
        self._device_class = device_class
        self._state_class = state_class
        self._unique_id = f"{key}_{item_index}_{isn}_solplanet_inverter"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this sensor."""
        return self._unique_id

    @property
    def state(self) -> float:
        """Return the state of the sensor."""
        data = getattr(self.coordinator.data[self._isn], self._key)
        return (
            data[self._item_index] if self._item_index is not None else data
        ) * self._multiply

    @property
    def unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        return self._unit

    @property
    def device_class(self) -> str:
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def state_class(self) -> str:
        """Return the state class of the sensor."""
        return self._state_class

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this sensor."""
        return {
            "identifiers": {(DOMAIN, self._isn)},
        }
