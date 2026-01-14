"""Solplanet button platform."""

from __future__ import annotations

from collections import abc
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SolplanetConfigEntry
from .const import DOMAIN, DONGLE_IDENTIFIER
from .coordinator import SolplanetDataUpdateCoordinator
from .entity import SolplanetEntity, SolplanetEntityDescription

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SolplanetButtonEntityDescription(
    SolplanetEntityDescription, ButtonEntityDescription
):
    """Describe Solplanet button entity."""

    callback: abc.Callable[[], Any]


class SolplanetButton(SolplanetEntity, ButtonEntity):
    """Representation of a Solplanet button."""

    entity_description: SolplanetButtonEntityDescription

    def _set_native_value(self) -> None:
        """Buttons do not have state."""
        return

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.entity_description.callback()
        await self.coordinator.async_request_refresh()


def create_dongle_entities_description(
    coordinator: SolplanetDataUpdateCoordinator, dongle_id: str
) -> list[SolplanetButtonEntityDescription]:
    """Create button entities for dongle actions."""
    return [
        SolplanetButtonEntityDescription(
            key=f"{dongle_id}_sync_time",
            name="Sync time",
            icon="mdi:clock",
            entity_category=EntityCategory.CONFIG,
            data_field_device_type=DONGLE_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=[],
            unique_id_suffix="sync_time",
            callback=lambda: coordinator.dongle_sync_time(),
        ),
        SolplanetButtonEntityDescription(
            key=f"{dongle_id}_reboot",
            name="Reboot",
            icon="mdi:restart",
            entity_category=EntityCategory.CONFIG,
            data_field_device_type=DONGLE_IDENTIFIER,
            data_field_data_type="data",
            data_field_path=[],
            unique_id_suffix="reboot",
            callback=lambda: coordinator.dongle_reboot(),
        ),
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolplanetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities for Solplanet from a config entry."""
    coordinator: SolplanetDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    buttons: list[SolplanetButton] = []

    for dongle_id in coordinator.data.get(DONGLE_IDENTIFIER, {}):
        for description in create_dongle_entities_description(coordinator, dongle_id):
            buttons.append(
                SolplanetButton(
                    description=description,
                    isn=dongle_id,
                    coordinator=coordinator,
                )
            )

    async_add_entities(buttons)
