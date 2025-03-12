"""Solplanet sensors platform."""

from collections import abc
from dataclasses import dataclass
import logging
import re
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, INVERTER_IDENTIFIER
from .coordinator import SolplanetDataUpdateCoordinator
from .exceptions import InverterInSleepModeError

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SolplanetEntityDescription(EntityDescription):
    """Describe Solplanet sensor entity."""

    data_field_device_type: str
    data_field_path: list[str | int]
    data_field_data_type: str
    data_field_NaN_value: int | None = None  # noqa: N815
    data_field_value_multiply: float | None = None
    data_field_value_mapper: abc.Callable[[Any], Any] | None = None
    unique_id_suffix: str | None = None
    attributes_fn: abc.Callable[[Any], dict[str, Any]] | None = None


class SolplanetEntity(CoordinatorEntity, Entity):
    """Representation of a Solplanet sensor."""

    entity_description: SolplanetEntityDescription
    unique_id_suffix: str
    sanitized_entity_id: str

    def __init__(
        self,
        description: SolplanetEntityDescription,
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
        self._set_native_value()

        self.entity_id = (
            f"sensor.solplanet_{self.sanitized_entity_id}"
            if description.data_field_device_type == INVERTER_IDENTIFIER
            else f"sensor.solplanet_{self.entity_description.data_field_device_type}_{self.sanitized_entity_id}"
        )
        self._attr_unique_id = (
            f"solplanet_{isn}_{self.unique_id_suffix}"
            if description.data_field_device_type == INVERTER_IDENTIFIER
            else f"solplanet_{self.entity_description.data_field_device_type}_{isn}_{self.unique_id_suffix}"
        )

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
            if (
                (isinstance(data, list) and len(data) > 0)
                or hasattr(data, "__dict__")
                or isinstance(data, dict)
            ):
                data = (
                    data[int(path_item)]
                    if isinstance(data, list)
                    else getattr(data, str(path_item))
                    if hasattr(data, "__dict__")
                    else data.get(path_item)
                )
            else:
                if self.entity_description.data_field_path[0] == "selected":
                    _LOGGER.warning("Selected: %r", type(data))
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

    def has_value_in_response(self) -> bool:
        """Return if sensor has value in response."""
        try:
            return self._get_value_from_coordinator() is not None
        except InverterInSleepModeError:
            return False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this sensor."""
        return (
            {
                "identifiers": {(DOMAIN, self._isn)},
            }
            if self.entity_description.data_field_device_type == INVERTER_IDENTIFIER
            else {
                "identifiers": {
                    (
                        DOMAIN,
                        f"{self.entity_description.data_field_device_type}_{self._isn or ""}",
                    )
                },
            }
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        if not self.entity_description.attributes_fn:
            return None
            
        data = self.coordinator.data[
            self.entity_description.data_field_device_type
        ][self._isn][self.entity_description.data_field_data_type]

        try:
            return self.entity_description.attributes_fn(data)
        except Exception as err:
            _LOGGER.debug("Error getting attributes: %s", err)
            return None
