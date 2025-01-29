"""Solplanet number platform."""

from collections import abc
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SolplanetConfigEntry
from .const import BATTERY_IDENTIFIER, DOMAIN
from .coordinator import SolplanetDataUpdateCoordinator
from .entity import SolplanetEntity, SolplanetEntityDescription

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SolplanetNumberEntityDescription(
    SolplanetEntityDescription, NumberEntityDescription
):
    """Describe Solplanet number entity."""

    callback: abc.Callable[[float], Any]


class SolplanetNumber(SolplanetEntity, NumberEntity):
    """Representation of a Solplanet number."""

    entity_description: SolplanetNumberEntityDescription
    _attr_native_value: float | None

    def __init__(
        self,
        description: SolplanetNumberEntityDescription,
        isn: str,
        coordinator: SolplanetDataUpdateCoordinator,
    ) -> None:
        """Initialize the number."""
        super().__init__(description=description, isn=isn, coordinator=coordinator)

    async def async_set_native_value(self, value: float) -> None:
        """Set the selected value."""
        await self.entity_description.callback(value)
        await self.coordinator.async_request_refresh()


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
            SolplanetNumber(
                description=entity_description,
                isn=isn,
                coordinator=coordinator,
            )
            for entity_description in create_battery_entites_description(
                coordinator, isn
            )
        )
