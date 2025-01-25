"""Solplanet number platform."""

from collections import abc
from dataclasses import dataclass
import logging
import re
from typing import Any

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SolplanetConfigEntry
from .const import BATTERY_IDENTIFIER, DOMAIN
from .coordinator import SolplanetDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SolplanetNumberEntityDescription(NumberEntityDescription):
    """Describe Solplanet sensor entity."""

    callback: abc.Callable[[float], Any]
    data_field_device_type: str
    data_field_path: list[str | int]
    data_field_data_type: str
    data_field_NaN_value: int | None = None  # noqa: N815
    data_field_value_multiply: float | None = None
    data_field_value_mapper: abc.Callable[[Any], Any] | None = None
    unique_id_suffix: str | None = None


class SolplanetNumber(CoordinatorEntity, NumberEntity):
    """Representation of a Solplanet sensor."""

    entity_description: SolplanetNumberEntityDescription
    unique_id_suffix: str
    sanitized_entity_id: str

    def __init__(
        self,
        description: SolplanetNumberEntityDescription,
        isn: str,
        coordinator: SolplanetDataUpdateCoordinator,
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
        self._attr_native_value = self._get_value_from_coordinator()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Set the native value here so we can use it in available property
        # without having to recalculate it
        data = self._get_value_from_coordinator()
        if data:
            self._attr_native_value = data
        super()._handle_coordinator_update()

    def _get_value_from_coordinator(self) -> float | None:
        """Return the state of the sensor."""
        try:
            data = self.coordinator.data[
                self.entity_description.data_field_device_type
            ][self._isn][self.entity_description.data_field_data_type]
        except KeyError:
            _LOGGER.debug(
                "Component serial number not in data. This is normal if the inverter is sleeping"
            )
            return None

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

    async def async_set_native_value(self, value: float) -> None:
        """Set the selected value."""
        await self.entity_description.callback(int(value))
        await self.coordinator.async_request_refresh()


class SolplanetBatteryNumber(SolplanetNumber):
    """Representation of a Solplanet Battery number."""

    def __init__(
        self,
        description: SolplanetNumberEntityDescription,
        isn: str,
        coordinator: SolplanetDataUpdateCoordinator,
    ) -> None:
        """Initialize the number."""
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


def create_battery_entites_description(
    coordinator: SolplanetDataUpdateCoordinator, isn: str
) -> list[SolplanetNumberEntityDescription]:
    """Create entities for battery."""
    return [
        SolplanetNumberEntityDescription(
            key=f"{isn}_soc_max",
            name="SOC max",
            data_field_device_type=BATTERY_IDENTIFIER,
            data_field_data_type="info",
            data_field_path=["charge_max"],
            native_min_value=10,
            native_max_value=100,
            native_step=1,
            native_unit_of_measurement=PERCENTAGE,
            callback=lambda value: coordinator.set_battery_soc_max(isn, int(value)),
        ),
        SolplanetNumberEntityDescription(
            key=f"{isn}_soc_min",
            name="SOC min",
            data_field_device_type=BATTERY_IDENTIFIER,
            data_field_data_type="info",
            data_field_path=["discharge_max"],
            native_min_value=10,
            native_max_value=100,
            native_step=1,
            native_unit_of_measurement=PERCENTAGE,
            callback=lambda value: coordinator.set_battery_soc_min(isn, int(value)),
        ),
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolplanetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number for Solplanet Inverter from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    for isn in coordinator.data[BATTERY_IDENTIFIER]:
        async_add_entities(
            SolplanetBatteryNumber(
                description=entity_description,
                isn=isn,
                coordinator=coordinator,
            )
            for entity_description in create_battery_entites_description(
                coordinator, isn
            )
        )
