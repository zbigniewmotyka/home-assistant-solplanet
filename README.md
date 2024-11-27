# Solplanet Inverter Integration
[![hacs_badge](https://img.shields.io/badge/HACS-Integration-41BDF5.svg)](https://github.com/hacs/integration)
![GitHub all releases](https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=Download%20Count&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.solplanet.total)
[![GitHub Release](https://img.shields.io/github/release/zbigniewmotyka/home-assistant-solplanet.svg)](https://github.com/zbigniewmotyka/home-assistant-solplanet/releases/)

![Solplanet-Logo-Gradient](https://github.com/user-attachments/assets/9675dcad-d32d-4605-972c-b3e244eb1ee8) \
The integration locally poll from Solplanet inverter and exposes Inverter, Battery and Smart meter information. \
This information can be used into Home Assistant Energy Dashboard.

## Features
- Support Single and Three Phase Inverters
- Sensor includes Inverter, Battery and Smart Meter

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

