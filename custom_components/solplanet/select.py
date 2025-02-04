"""Solplanet selects platform."""

from collections import abc
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SolplanetConfigEntry
from .const import BATTERY_IDENTIFIER, DOMAIN
from .coordinator import SolplanetDataUpdateCoordinator
from .entity import SolplanetEntity, SolplanetEntityDescription

_LOGGER = logging.getLogger(__name__)


class SolplanetSelectOption:
    """Representation of a Solplanet select option."""

    def __init__(self, label: str, value: Any) -> None:
        """Initialize the select option."""
        self.label = label
        self.value = value


@dataclass(frozen=True, kw_only=True)
class SolplanetSelectEntityDescription(
    SolplanetEntityDescription, SelectEntityDescription
):
    """Describe Solplanet select entity."""

    callback: abc.Callable[[SolplanetSelectOption], Any]
    get_options: abc.Callable[[], list[SolplanetSelectOption]]


class SolplanetSelect(SolplanetEntity, SelectEntity):
    """Representation of a Solplanet sensor."""

    entity_description: SolplanetSelectEntityDescription
    _attr_native_value: str | None
    _select_options: list[SolplanetSelectOption]

    def __init__(
        self,
        description: SolplanetSelectEntityDescription,
        isn: str,
        coordinator: SolplanetDataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(description=description, isn=isn, coordinator=coordinator)
        self._refresh_options()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        super()._handle_coordinator_update()
        self._refresh_options()

    async def async_select_option(self, option: str) -> None:
        """Handle the option selection."""
        item = next((x for x in self._select_options if x.label == option), None)

        if item is not None:
            await self.entity_description.callback(item)
            self._attr_current_option = option
            self.async_write_ha_state()

    def _refresh_options(self) -> None:
        self._select_options = self.entity_description.get_options()

        self._attr_options = [x.label for x in self._select_options]
        self._attr_current_option = self._attr_native_value


def create_battery_entites_description(
    coordinator: SolplanetDataUpdateCoordinator, isn: str
) -> list[SolplanetSelectEntityDescription]:
    """Create entities for battery."""
    return [
        SolplanetSelectEntityDescription(
            key=f"{isn}_work_mode",
            name="Work mode",
            unique_id_suffix="work_mode",
            data_field_device_type=BATTERY_IDENTIFIER,
            data_field_data_type="work_modes",
            data_field_path=["selected", "name"],
            get_options=lambda: [
                SolplanetSelectOption(label=x.name, value=x)
                for x in coordinator.data[BATTERY_IDENTIFIER][isn]["work_modes"]["all"]
            ],
            callback=lambda option: coordinator.set_battery_work_mode(
                isn, option.value
            ),
        ),
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolplanetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up selects for Solplanet Inverter from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    sensors: list[SolplanetSelect] = []

    for isn in coordinator.data[BATTERY_IDENTIFIER]:
        sensors.extend(
            SolplanetSelect(
                description=entity_description,
                isn=isn,
                coordinator=coordinator,
            )
            for entity_description in create_battery_entites_description(
                coordinator, isn
            )
        )

    async_add_entities([sensor for sensor in sensors if sensor.has_value_in_response()])
