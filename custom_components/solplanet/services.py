"""Services for Solplanet integration."""
from __future__ import annotations

import logging
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr, entity_registry as er
import voluptuous as vol

from .client import ScheduleSlot, BatterySchedule
from .const import DOMAIN, BATTERY_IDENTIFIER

DAYS = ["Mon", "Tus", "Wen", "Thu", "Fri", "Sat", "Sun"]

_LOGGER = logging.getLogger(__name__)

async def get_isn_from_target(hass: HomeAssistant, target: dict) -> list[str]:
    """Get ISNs from target entity_ids or device_ids."""
    isns = set()
    
    # Handle entity_ids
    if "entity_id" in target:
        entity_reg = er.async_get(hass)
        entity_ids = target["entity_id"] if isinstance(target["entity_id"], list) else [target["entity_id"]]
            
        for entity_id in entity_ids:
            if entry := entity_reg.async_get(entity_id):
                parts = entry.unique_id.split('_')
                if len(parts) > 2:
                    isns.add(parts[2])
                
    # Handle device_ids
    if "device_id" in target:
        device_reg = dr.async_get(hass)
        device_ids = target["device_id"] if isinstance(target["device_id"], list) else [target["device_id"]]
            
        for device_id in device_ids:
            if device := device_reg.async_get(device_id):
                for identifier in device.identifiers:
                    if identifier[0] == DOMAIN:
                        isn = identifier[1].replace("battery_", "")
                        isns.add(isn)
                        break

    return list(isns)

async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Solplanet integration."""

    async def set_schedule_slot(call: ServiceCall) -> None:
        """Handle set_schedule_slot service."""
        target = call.target if hasattr(call, 'target') else {}
        if 'entity_id' in call.data:
            target['entity_id'] = call.data['entity_id']
        if 'device_id' in call.data:
            target['device_id'] = call.data['device_id']

        isns = await get_isn_from_target(hass, target)
        if not isns:
            raise vol.Invalid("No valid entities or devices found")
            
        processed = False
        for isn in isns:
            for entry_id, data in hass.data[DOMAIN].items():
                coordinator = data["coordinator"]
                if isn in coordinator.data[BATTERY_IDENTIFIER]:
                    try:
                        # Get current schedule
                        current_schedule = coordinator.data[BATTERY_IDENTIFIER][isn]["schedule"]["slots"]

                        # Check if we already have 6 slots for this day
                        if call.data["day"] in current_schedule and len(current_schedule[call.data["day"]]) >= 6:
                            raise vol.Invalid("Cannot add more than 6 slots per day")
                        
                        # Create new slot
                        slot = ScheduleSlot.from_time(
                            start=f"{call.data['start_hour']:02d}:{call.data['start_minute']:02d}",
                            duration=call.data["duration"],
                            mode=call.data["mode"]
                        )
                        
                        # Get existing slots for the day
                        new_slots = dict(current_schedule)
                        day_slots = new_slots.get(call.data["day"], [])
                        day_slots.append(slot)
                        
                        try:
                            # This will validate max slots, overlaps, and midnight crossing
                            ScheduleSlot.validate_slots(day_slots)
                        except ValueError as err:
                            raise vol.Invalid(str(err)) from err
                            
                        new_slots[call.data["day"]] = day_slots
                        
                        await coordinator.set_battery_schedule_slots(isn, new_slots)
                        processed = True
                        break
                    except Exception as err:
                        raise
                    
        if not processed:
            raise vol.Invalid(f"No valid battery coordinator found for ISNs {isns}")

    async def clear_schedule(call: ServiceCall) -> None:
        """Handle clear_schedule service."""
        target = call.target if hasattr(call, 'target') else {}
        if 'entity_id' in call.data:
            target['entity_id'] = call.data['entity_id']
        if 'device_id' in call.data:
            target['device_id'] = call.data['device_id']

        isns = await get_isn_from_target(hass, target)
        if not isns:
            raise vol.Invalid("No valid entities or devices found")
            
        processed = False
        for isn in isns:
            for entry_id, data in hass.data[DOMAIN].items():
                coordinator = data["coordinator"]
                if isn in coordinator.data[BATTERY_IDENTIFIER]:
                    # Get current schedule
                    current_schedule = coordinator.data[BATTERY_IDENTIFIER][isn]["schedule"]["slots"]
                    
                    if call.data["day"] == "all":
                        new_slots = {day: [] for day in BatterySchedule.DAYS}
                    else:
                        # Keep other days unchanged
                        new_slots = dict(current_schedule)
                        new_slots[call.data["day"]] = []
                    
                    await coordinator.set_battery_schedule_slots(isn, new_slots)
                    processed = True
                    break
                    
        if not processed:
            raise vol.Invalid(f"No valid battery coordinator found for ISNs {isns}")

    # Service schemas stay the same
    hass.services.async_register(
        DOMAIN, 
        "set_schedule_slot", 
        set_schedule_slot, 
        schema=vol.Schema({
            vol.Optional("entity_id"): vol.Any(str, [str]),
            vol.Optional("device_id"): vol.Any(str, [str]),
            vol.Required("day"): vol.In(BatterySchedule.DAYS),
            vol.Required("start_hour"): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
            vol.Required("start_minute"): vol.In([0, 30]),
            vol.Required("duration"): vol.All(vol.Coerce(int), vol.Range(min=1, max=4)),
            vol.Required("mode"): vol.In(["charge", "discharge"])
        })
    )

    hass.services.async_register(
        DOMAIN, 
        "clear_schedule", 
        clear_schedule, 
        schema=vol.Schema({
            vol.Optional("entity_id"): vol.Any(str, [str]),
            vol.Optional("device_id"): vol.Any(str, [str]),
            vol.Required("day"): vol.In(["all"] + BatterySchedule.DAYS)
        })
    )
