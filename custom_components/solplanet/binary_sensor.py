"""Solplanet binary sensor platform."""
from dataclasses import dataclass
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SolplanetConfigEntry
from .client import BatterySchedule
from .const import BATTERY_IDENTIFIER, DOMAIN
from .entity import SolplanetEntity, SolplanetEntityDescription

_LOGGER = logging.getLogger(__name__)

@dataclass(frozen=True, kw_only=True)
class SolplanetBinarySensorEntityDescription(
    SolplanetEntityDescription, BinarySensorEntityDescription
):
    """Describe Solplanet binary sensor entity."""


class SolplanetBinarySensor(SolplanetEntity, BinarySensorEntity):
    """Representation of a Solplanet binary sensor."""

    entity_description: SolplanetBinarySensorEntityDescription

    def __init__(
        self,
        description: SolplanetBinarySensorEntityDescription,
        isn: str,
        coordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(description=description, isn=isn, coordinator=coordinator)
        self._attr_is_on = None  # Initialize the binary sensor state

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self._get_value_from_coordinator()


def create_battery_binary_sensors(coordinator, isn: str) -> list[SolplanetBinarySensorEntityDescription]:
    """Create binary sensors for battery."""
    def value_mapper(raw):
        has_schedule = any(
            any(code != 0 for code in raw.get(day, []))
            for day in BatterySchedule.DAYS
            if day in raw
        )
        return has_schedule

    return [
        SolplanetBinarySensorEntityDescription(
            key=f"{isn}_schedule_configured",
            name="Schedule Configured",
            data_field_device_type=BATTERY_IDENTIFIER,
            data_field_data_type="schedule",
            data_field_path=["raw"],
            data_field_value_mapper=value_mapper,
            entity_category=EntityCategory.DIAGNOSTIC,
            attributes_fn=lambda schedule: {
                "raw_schedule": schedule["raw"],
                "formatted_schedule": {
                    day: [slot.human_readable() for slot in day_slots]
                    for day, day_slots in schedule["slots"].items()
                },
                "pin": schedule["Pin"],
                "pout": schedule["Pout"]
            }
        ),
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolplanetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    sensors: list[SolplanetBinarySensor] = []
    for isn in coordinator.data[BATTERY_IDENTIFIER]:
        sensors.extend(
            SolplanetBinarySensor(description=description, isn=isn, coordinator=coordinator)
            for description in create_battery_binary_sensors(coordinator, isn)
        )

    # Always add entities; values may be missing during startup/inverter sleep.
    async_add_entities(sensors)
