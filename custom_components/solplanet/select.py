from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo

from . import SolplanetConfigEntry
from .const import DOMAIN, BATTERY_IDENTIFIER


class SolplanetWorkModeSelect(CoordinatorEntity, SelectEntity):
    def __init__(self, coordinator, name, options, initial_value, isn: str):
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_options = options
        self._attr_current_option = initial_value
        self._isn = isn
        self.entity_id = f"sensor.solplanet_{BATTERY_IDENTIFIER}_{isn}_work_mode"
        self._attr_unique_id = f"solplanet_{BATTERY_IDENTIFIER}_{isn}_work_mode"

    async def async_select_option(self, option: str):
        """Handle the option selection."""
        if option in self._attr_options:
            # Tu dodaj logikę do obsługi wyboru opcji (np. wysłanie komendy do urządzenia)
            # await self.coordinator.update_device_setting(option)
            self._attr_current_option = option
            self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this sensor."""
        return {
            "identifiers": {(DOMAIN, f"{BATTERY_IDENTIFIER}_{self._isn}")},
        }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolplanetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    for isn in coordinator.data[BATTERY_IDENTIFIER]:
        async_add_entities(
            [
                SolplanetWorkModeSelect(
                    coordinator=coordinator,
                    name="Work mode",
                    options=[
                        "Self-consumption mode",
                        "Reserve power mode",
                        "Custom mode",
                        "Off-grid mode",
                    ],
                    initial_value="Self-consumption mode",
                    isn=isn,
                )
            ]
        )
