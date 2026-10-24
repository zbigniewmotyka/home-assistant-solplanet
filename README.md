# Solplanet / Rahvolt Inverter Integration
[![hacs_badge](https://img.shields.io/badge/HACS-Integration-41BDF5.svg)](https://github.com/hacs/integration)
![GitHub all releases](https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=Download%20Count&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.solplanet.total)
[![GitHub Release](https://img.shields.io/github/release/zbigniewmotyka/home-assistant-solplanet.svg)](https://github.com/zbigniewmotyka/home-assistant-solplanet/releases/)

![Solplanet-Logo-Gradient](https://github.com/user-attachments/assets/9675dcad-d32d-4605-972c-b3e244eb1ee8) \
The integration locally poll from Solplanet inverter (and other with compatible inverters like Rahvolt) and exposes Inverter, Battery and Smart meter information. \
This information can be used into Home Assistant Energy Dashboard.

## Features
- Support Single and Three Phase Inverters
- Sensor includes Inverter, Battery and Smart Meter
- Switch between battery modes

## Installation

#### With HACS
[![Open in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=zbigniewmotyka&repository=home-assistant-solplanet&category=integration)

#### Manual installation
1. Place `solplanet` directory inside `config/custom_components` directory
2. Restart Home Assistant.

## Setting Up

1. Add Solplanet from the Integration page.
2. Enter the IP address of your Solplanet inverter
3. The integration will do the rest 😉

## Custom Cards
Two Lovelace cards styled after the official Solplanet app.

| Card | What it shows |
|---|---|
| `custom:solplanet-flow-card` | Inverter status, live Solar / Load / Grid / Battery power, animated house scene with power flows |
| `custom:solplanet-stats-card` | Yield today and Consumption today (with curves since midnight), Self-consumption % and Self-sufficiency % |

The house is a 3D-style render in day and night versions (embedded in the JS, no extra files). Override with `image_day` / `image_night` URLs if you want your own.

Both cards are **time aware** using `sun.sun`: the scene switches between day, dawn, dusk and night (sky colours, sun or moon on its arc, stars, panels glinting by day, windows lit at night), and both show the countdown to the next sunrise or sunset.

![custom-card](https://github.com/user-attachments/assets/890f353a-954e-4739-80d4-6dcad090fbd5)


### solplanet-flow-card

| Option | Default (auto) | Notes |
|---|---|---|
| `name` | – | Title in the header |
| `pv_power` | `sensor.solplanet_battery_*_pv_power` | Falls back to inverter `*_power` for grid-tie inverters |
| `grid_power` | `sensor.solplanet_meter_*_grid_power` | Positive = import, negative = export |
| `battery_power` | `sensor.solplanet_battery_*_battery_power` | Direction taken from `battery_status` |
| `battery_soc` | `sensor.solplanet_battery_*_battery_state_of_charge` | |
| `battery_status` | `sensor.solplanet_battery_*_battery_status` | Charging / Discharging / Idle |
| `inverter_status` | `sensor.solplanet_*_inverter_status` | Normal → Running; unavailable at night → Sleeping |
| `load_power` | computed | `pv + grid − battery charging − EV charger` (battery discharge adds) |
| `charger_power` | – | Optional EV charger. Shows a wallbox, its flow and an *EV Charger* slot. A Solplanet second meter set to the *Ev-charger* location (`sensor.solplanet_submeter_*_second_meter_power`) works, or any power sensor |
| `invert_grid` | `false` | Flip if your meter reports export as positive |
| `invert_battery` | `false` | Only used when no battery status sensor exists |
| `sun_entity` | `sun.sun` | |
| `show_updated` | `false` | Show the last-updated timestamp under the flow card |
| `force_phase` | – | `day`, `dawn`, `dusk`, `night` to preview a look |

### solplanet-stats-card

| Option | Default (auto) | Notes |
|---|---|---|
| `pv_today` | `*_pv_energy_today` or `*_energy_produced_today` | |
| `grid_in_today` / `grid_out_today` | meter `*_grid_energy_in_today` / `*_out_today` | |
| `battery_charge_total` / `battery_discharge_total` | battery `*_battery_energy_for_charging` / `_discharging` | Today's delta is taken from history since midnight |
| `battery_charge_today` / `battery_discharge_today` | – | Use if you have daily utility meters |
| `consumption_today` | computed | `yield + import − export + battery out − battery in` |
| `hide_charts` | `false` | |
| `time_aware` | `true` | Shows the production / sunrise-sunset ribbon |

Self-consumption = (yield − export) ÷ yield. Self-sufficiency = (consumption − import) ÷ consumption.

Tap any value to open its more-info dialog.

## How the percentages are calculated

Both use today's energy counters from the integration:

- **Self-consumption** = (yield today − grid export today) ÷ yield today. Sources: `..._pv_energy_today` (battery/inverter) and the meter's `..._grid_energy_out_today`.
- **Self-sufficiency** = (consumption today − grid import today) ÷ consumption today. Consumption is `consumption_today` if you set one, otherwise derived as yield + import − export + battery discharge − battery charge (battery deltas come from the charge/discharge totals' history since midnight).

Hover the ⓘ icon on either tile for the explanation.

## Flow colours

Matched to the official Solplanet app (5.2.1): power flowing **into** the inverter is cyan, power flowing **out** is orange.
Solar, battery discharge and grid export are cyan; house load, battery charge, grid import and EV charger are orange.
Each streak loops at the app's fixed speed (solar/load 3.3 s, battery 1.3 s, grid 6 s import / 5.4 s export, EV charger 2 s), independent of power.

## Home Assistant Energy Dashboard
Assign these sensors into the Energy Dashboard

| **Section**      | **Home Assistant** |  **Solplanet**           |
|:----------------:|:------------------:|:------------------------:|
| Solar Panels     | Solar Production   | PV Energy Today          |
| Electricity Grid | Grid Consumption   | Grid Energy In Total     |
|                  | Return to Grid     | Grid Energy Out Total    |
| Battery Storage  | Energy Incoming    | Battery for Charging     |
|                  | Energy Outgoing    | Battery for Discharging  |

![386017334-b4899f13-82b7-4be4-938b-e5c2f0670adf](https://github.com/user-attachments/assets/c2660112-ad3b-4ee7-b6a6-5c73fb7f42bb)

> [!Tip]
> You may choose to define the tariff according to your local electrical utility service.

![image](https://github.com/user-attachments/assets/98e4db8e-88b6-4af7-b8b0-c5b6b2956530) ![image](https://github.com/user-attachments/assets/1a8c213a-e1aa-42b7-9614-6252eb378a0a)

