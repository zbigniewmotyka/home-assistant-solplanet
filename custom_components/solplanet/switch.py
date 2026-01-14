"""Solplanet switch platform."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SolplanetConfigEntry
from .const import BATTERY_IDENTIFIER, DOMAIN
from .coordinator import SolplanetDataUpdateCoordinator
from .entity import SolplanetEntity, SolplanetEntityDescription

_LOGGER = logging.getLogger(__name__)

# Battery "More Settings" are controlled via Modbus RTU over `fdbg.cgi` using holding-register offsets:
# 1500 power, 1501 sleep flag, 1502 LED color, 1503 LED brightness.
# Power and Sleep are exposed as HA switches and delegate writes via coordinator helper methods.


@dataclass(frozen=True, kw_only=True)
class SolplanetSwitchEntityDescription(SolplanetEntityDescription, SwitchEntityDescription):
    """Describe Solplanet switch entity."""

    coordinator_method: str


class SolplanetSwitch(SolplanetEntity, SwitchEntity):
    """Representation of a Solplanet switch."""

    entity_description: SolplanetSwitchEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        try:
            return bool(self._get_value_from_coordinator())
        except Exception:  # noqa: BLE001
            return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._call_coordinator(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._call_coordinator(False)

    async def _call_coordinator(self, on: bool) -> None:
        """Call the coordinator setter for this switch."""
        method = getattr(self.coordinator, self.entity_description.coordinator_method)
        await method(on)


def create_battery_switches(isn: str) -> list[SolplanetSwitchEntityDescription]:
    """Create switch entities for battery 'More Settings'."""
    return [
        SolplanetSwitchEntityDescription(
            key=f"{isn}_battery_power",
            name="Power",
            icon="mdi:power",
            entity_category=EntityCategory.CONFIG,
            data_field_device_type=BATTERY_IDENTIFIER,
            data_field_data_type="more_settings",
            data_field_path=["power_on"],
            unique_id_suffix="battery_power",
            coordinator_method="set_battery_power",
        ),
        SolplanetSwitchEntityDescription(
            key=f"{isn}_battery_sleep_enabled",
            name="Sleep",
            icon="mdi:sleep",
            entity_category=EntityCategory.CONFIG,
            data_field_device_type=BATTERY_IDENTIFIER,
            data_field_data_type="more_settings",
            data_field_path=["sleep_enabled"],
            unique_id_suffix="battery_sleep_enabled",
            coordinator_method="set_battery_sleep_enabled",
        ),
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolplanetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches for Solplanet from a config entry."""
    coordinator: SolplanetDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    switches: list[SolplanetSwitch] = []
    for isn in coordinator.data.get(BATTERY_IDENTIFIER, {}):
        for description in create_battery_switches(isn):
            switches.append(SolplanetSwitch(description=description, isn=isn, coordinator=coordinator))

    async_add_entities(switches)
