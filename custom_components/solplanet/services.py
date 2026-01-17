"""Services for Solplanet integration."""
from __future__ import annotations

import logging
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr, entity_registry as er
import voluptuous as vol

from .client import ScheduleSlot, BatterySchedule
from .const import DOMAIN, BATTERY_IDENTIFIER, METER_IDENTIFIER

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


async def get_meter_isn_from_target(hass: HomeAssistant, target: dict) -> list[str]:
    """Get meter serial(s) from target entity_ids or device_ids."""
    isns: set[str] = set()

    if "entity_id" in target:
        entity_reg = er.async_get(hass)
        entity_ids = (
            target["entity_id"]
            if isinstance(target["entity_id"], list)
            else [target["entity_id"]]
        )
        for entity_id in entity_ids:
            if entry := entity_reg.async_get(entity_id):
                # Typical unique_id format:
                # - inverter: solplanet_<isn>_<suffix>
                # - others:  solplanet_<device_type>_<isn>_<suffix>
                parts = (entry.unique_id or "").split("_")
                if len(parts) >= 4 and parts[0] == "solplanet" and parts[1] == METER_IDENTIFIER:
                    isns.add(parts[2])

    if "device_id" in target:
        device_reg = dr.async_get(hass)
        device_ids = (
            target["device_id"]
            if isinstance(target["device_id"], list)
            else [target["device_id"]]
        )
        for device_id in device_ids:
            if device := device_reg.async_get(device_id):
                for identifier in device.identifiers:
                    if identifier[0] != DOMAIN:
                        continue
                    # Device identifiers are created as f"{METER_IDENTIFIER}_{meter_isn}".
                    if identifier[1].startswith(f"{METER_IDENTIFIER}_"):
                        isns.add(identifier[1].replace(f"{METER_IDENTIFIER}_", "", 1))

    return list(isns)

async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Solplanet integration."""

    async def set_schedule_slots(call: ServiceCall) -> None:
        """Handle set_schedule_slots service."""
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
            for data in hass.data[DOMAIN].values():
                coordinator = data["coordinator"]
                if isn in coordinator.data[BATTERY_IDENTIFIER]:
                    try:
                        # Get current schedule
                        current_schedule = coordinator.data[BATTERY_IDENTIFIER][isn]["schedule"]["slots"]

                        # Create new slot
                        slot = ScheduleSlot.from_time(
                            start=f"{call.data['start_hour']:02d}:{call.data['start_minute']:02d}",
                            duration=call.data["duration"],
                            mode=call.data["mode"]
                        )

                        # Get existing slots for the day
                        new_slots = dict(current_schedule)
                        day_slots = new_slots.get(call.data["day"], [])

                        if len(day_slots) >= 6:
                            raise vol.Invalid("Cannot add more than 6 slots per day")

                        day_slots.append(slot)
                        ScheduleSlot.validate_slots(day_slots)  # This will raise ValueError for validation issues

                        new_slots[call.data["day"]] = day_slots
                        await coordinator.set_battery_schedule_slots(isn, new_slots)
                        processed = True
                        break

                    except ValueError as err:
                        # Handle validation errors only (overlaps, duration, midnight crossing)
                        raise vol.Invalid(str(err)) from err
                    except (KeyError, ConnectionError, TimeoutError) as err:
                        # Handle specific API/network errors
                        _LOGGER.error("Failed to access inverter: %s", err)
                        raise vol.Invalid(f"Communication error: {err}") from err

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
            for data in hass.data[DOMAIN].values():
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

    async def _apply_meter_payload(target: dict, payload: dict) -> None:
        """Apply a meter payload to the targeted main meter device(s)."""
        meter_isns = await get_meter_isn_from_target(hass, target)
        if not meter_isns:
            raise vol.Invalid("No valid meter entities or devices found")

        processed = False
        for meter_isn in meter_isns:
            for data in hass.data.get(DOMAIN, {}).values():
                coordinator = data.get("coordinator")
                if coordinator and meter_isn in coordinator.data.get(METER_IDENTIFIER, {}):
                    await coordinator.set_meter_power_limit(payload)
                    processed = True
                    break

        if not processed:
            raise vol.Invalid(f"No valid meter coordinator found for meters {meter_isns}")

    async def set_meter_limit_power(call: ServiceCall) -> None:
        """Configure meter power limit mode (ctrlType=0)."""
        target = call.target if hasattr(call, "target") else {}
        if "entity_id" in call.data:
            target["entity_id"] = call.data["entity_id"]
        if "device_id" in call.data:
            target["device_id"] = call.data["device_id"]

        limit_type = int(call.data["limitType"])
        payload: dict = {
            "regulate": 10,
            "ctrlType": 0,
            "abs": int(call.data["abs"]),
            "limitType": limit_type,
            "lostTime": int(call.data["lostTime"]),
            "lostPowerMax": int(call.data["lostPowerMax"]),
            "powerDiff": int(call.data["powerDiff"]),
        }

        if limit_type == 0:
            if call.data.get("target") is None:
                raise vol.Invalid("target is required when limitType=0 (Absolute W)")
            payload["target"] = int(call.data["target"])
        else:
            if call.data.get("targetPer") is None:
                raise vol.Invalid("targetPer is required when limitType=1 (Percent)")
            payload["targetPer"] = int(call.data["targetPer"])

        await _apply_meter_payload(target, payload)

    async def set_meter_limit_current(call: ServiceCall) -> None:
        """Configure meter current limit mode (ctrlType=1)."""
        target = call.target if hasattr(call, "target") else {}
        if "entity_id" in call.data:
            target["entity_id"] = call.data["entity_id"]
        if "device_id" in call.data:
            target["device_id"] = call.data["device_id"]

        payload: dict = {
            "regulate": 10,
            "ctrlType": 1,
            # Keep vendor defaults explicitly in the payload (these were observed in the app).
            "failSafe": 1,
            "usageType": 0,
            "lostTime": int(call.data["lostTime"]),
            "lostCurrMax": int(call.data["lostCurrMax"]),
            "maxOutCurr": int(call.data["maxOutCurr"]),
            "maxInCurr": int(call.data["maxInCurr"]),
            "currDiff": int(call.data.get("currDiff") or 0),
        }

        await _apply_meter_payload(target, payload)

    async def set_meter_zero_power(call: ServiceCall) -> None:
        """Configure meter zero power mode (ctrlType=2)."""
        target = call.target if hasattr(call, "target") else {}
        if "entity_id" in call.data:
            target["entity_id"] = call.data["entity_id"]
        if "device_id" in call.data:
            target["device_id"] = call.data["device_id"]

        payload: dict = {
            "regulate": 10,
            "ctrlType": 2,
            "lostTime": int(call.data["lostTime"]),
        }

        await _apply_meter_payload(target, payload)

    async def disable_meter_power_limit(call: ServiceCall) -> None:
        """Disable meter power limit control (regulate=5)."""
        target = call.target if hasattr(call, "target") else {}
        if "entity_id" in call.data:
            target["entity_id"] = call.data["entity_id"]
        if "device_id" in call.data:
            target["device_id"] = call.data["device_id"]

        await _apply_meter_payload(target, {"regulate": 5})

    # Service schemas stay the same
    hass.services.async_register(
        DOMAIN,
        "set_schedule_slots",
        set_schedule_slots,
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

    hass.services.async_register(
        DOMAIN,
        "set_meter_limit_power",
        set_meter_limit_power,
        schema=vol.Schema(
            {
                vol.Required("device_id"): vol.Any(str, [str]),
                vol.Optional("entity_id"): vol.Any(str, [str]),
                # UI selectors in services.yaml send strings; accept both and coerce to int.
                vol.Required("abs"): vol.All(vol.Coerce(int), vol.In([0, 1])),
                vol.Required("limitType"): vol.All(vol.Coerce(int), vol.In([0, 1])),
                vol.Optional("target"): vol.All(vol.Coerce(int), vol.Range(min=0, max=10000)),
                vol.Optional("targetPer"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
                vol.Required("powerDiff"): vol.All(vol.Coerce(int), vol.Range(min=-1000, max=1000)),
                vol.Required("lostTime"): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
                vol.Required("lostPowerMax"): vol.All(vol.Coerce(int), vol.Range(min=0, max=10000)),
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        "set_meter_limit_current",
        set_meter_limit_current,
        schema=vol.Schema(
            {
                vol.Required("device_id"): vol.Any(str, [str]),
                vol.Optional("entity_id"): vol.Any(str, [str]),
                vol.Required("maxOutCurr"): vol.All(vol.Coerce(int), vol.Range(min=0, max=3000)),
                vol.Required("maxInCurr"): vol.All(vol.Coerce(int), vol.Range(min=0, max=3000)),
                vol.Optional("currDiff"): vol.All(vol.Coerce(int), vol.Range(min=-10, max=10)),
                vol.Required("lostTime"): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
                vol.Required("lostCurrMax"): vol.All(vol.Coerce(int), vol.Range(min=0, max=11)),
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        "set_meter_zero_power",
        set_meter_zero_power,
        schema=vol.Schema(
            {
                vol.Required("device_id"): vol.Any(str, [str]),
                vol.Optional("entity_id"): vol.Any(str, [str]),
                vol.Required("lostTime"): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        "disable_meter_power_limit",
        disable_meter_power_limit,
        schema=vol.Schema(
            {
                vol.Required("device_id"): vol.Any(str, [str]),
                vol.Optional("entity_id"): vol.Any(str, [str]),
            }
        ),
    )
