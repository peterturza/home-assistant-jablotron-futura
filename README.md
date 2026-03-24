# Jablotron Futura

[![HACS Action](https://github.com/peterturza/home-assistant-jablotron-futura/actions/workflows/hacs.yaml/badge.svg)](https://github.com/peterturza/home-assistant-jablotron-futura/actions/workflows/hacs.yaml)
[![Validate with hassfest](https://github.com/peterturza/home-assistant-jablotron-futura/actions/workflows/validate.yaml/badge.svg)](https://github.com/peterturza/home-assistant-jablotron-futura/actions/workflows/validate.yaml)

Home Assistant custom integration for **Jablotron Futura** heat recovery ventilation units. Connects to the Jablotron cloud API to monitor and control your Futura recuperation system.

## Features

- Monitor indoor/outdoor temperature, humidity, and CO2 levels
- Track filter health, power consumption, and recovered heat
- Control fan speed, target temperature, and humidity mode
- View servo bypass and drying status

## Supported Entities

### Sensors

| Entity | Description | Device Class |
|--------|-------------|--------------|
| Filter Health | Current filter condition | — |
| Device Consumption | Current power consumption | Power |
| Heating Recovered Current | Heat being recovered | Power |
| CO2 Max | Maximum CO2 level (ppm) | CO2 |
| Indoor Humidity | Indoor humidity level | Humidity |
| Indoor Temperature | Indoor air temperature | Temperature |
| Outdoor Temperature | Outdoor air temperature | Temperature |

### Binary Sensors

| Entity | Description | Device Class |
|--------|-------------|--------------|
| Servo Drying | Drying servo status | Opening |
| Servo Bypass | Bypass servo status | Opening |

### Controls

| Entity | Type | Description |
|--------|------|-------------|
| Fan Power | Select | Fan speed level with airflow display |
| Humidity | Select | Humidity control mode |
| Temperature | Number | Target temperature setpoint |
| Bypass | Switch | Bypass servo opening |
| Cooling | Switch | Enable cooling (if available) |
| Heating | Switch | Enable heating |
| Radon Protection | Switch | Enable radon protection |


## Requirements

- A Jablotron Futura recuperation unit
- A Jablotron cloud account (same credentials used in the Jablotron app)
- Home Assistant 2025.1.0 or newer

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click on **Integrations**
3. Click the **+** button and search for **Jablotron Futura**
4. Click **Install**
5. Restart Home Assistant

### Manual

1. Download the latest release from the [releases page](https://github.com/peterturza/home-assistant-jablotron-futura/releases)
2. Copy the `custom_components/jablotron_futura` folder to your Home Assistant `custom_components` directory
3. Restart Home Assistant

## Configuration

1. Go to **Settings** > **Devices & Services**
2. Click **+ Add Integration**
3. Search for **Jablotron Futura**
4. Enter your Jablotron cloud account credentials (username and password)
5. The integration will discover your Futura unit and create all entities

The integration polls the Jablotron cloud API every 5 minutes for updated data.

## Troubleshooting

**Authentication failed**: Verify your credentials work in the official Jablotron app. The integration uses the same cloud API.

**No service found**: Ensure your Futura unit is registered and visible in the Jablotron app with status "Enabled".

**Entities unavailable**: The Jablotron cloud API may be temporarily unreachable. The integration will retry automatically on the next polling interval.

## License

This project is licensed under the MIT License — see [LICENSE.md](LICENSE.md) for details.
