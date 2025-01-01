"""Solplanet selects platform."""

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SolplanetConfigEntry
from .client import BatteryWorkMode
from .const import BATTERY_IDENTIFIER, DOMAIN
from .coordinator import SolplanetDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class SolplanetWorkModeSelect(CoordinatorEntity, SelectEntity):
    """Representation of a Solplanet battery work mode select."""

    _work_modes: list[BatteryWorkMode] = []
    coordinator: SolplanetDataUpdateCoordinator

    def __init__(
        self,
        coordinator: SolplanetDataUpdateCoordinator,
        isn: str,
    ) -> None:
        """Initialize battery work mode select."""
        super().__init__(coordinator)
        self._attr_name = "Work mode"
        self._attr_options = []
        self._isn = isn
        self.entity_id = f"sensor.solplanet_{BATTERY_IDENTIFIER}_{isn}_work_mode"
        self._attr_unique_id = f"solplanet_{BATTERY_IDENTIFIER}_{isn}_work_mode"
        self._refresh_work_modes()

    async def async_select_option(self, option: str) -> None:
        """Handle the option selection."""
        item = next((x for x in self._work_modes if x.name == option), None)

        if item is not None:
            await self.coordinator.set_battery_work_mode(self._isn, item)
            self._attr_current_option = option
            self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._refresh_work_modes()
        super()._handle_coordinator_update()

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this select."""
        return {
            "identifiers": {(DOMAIN, f"{BATTERY_IDENTIFIER}_{self._isn}")},
        }

    def _refresh_work_modes(self) -> None:
        self._work_modes = self.coordinator.data[BATTERY_IDENTIFIER][self._isn][
            "work_modes"
        ]["all"]
        selected = self.coordinator.data[BATTERY_IDENTIFIER][self._isn]["work_modes"][
            "selected"
        ]

        self._attr_options = [x.name for x in self._work_modes]
        self._attr_current_option = selected.name if selected is not None else None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolplanetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up selects for Solplanet Inverter from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    for isn in coordinator.data[BATTERY_IDENTIFIER]:
        async_add_entities(
            [
                SolplanetWorkModeSelect(
                    coordinator=coordinator,
                    isn=isn,
                )
            ]
        )
