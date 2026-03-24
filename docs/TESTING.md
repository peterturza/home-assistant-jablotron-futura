# Testing Guide

## Automated Tests

### Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements_test.txt
```

### Run Tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

### What's Tested

| Test File | Coverage |
|-----------|----------|
| `test_config_flow.py` | Form display, successful setup, auth failure, API error |
| `test_init.py` | Entry setup, auth failure during setup, entry unload |
| `test_sensor.py` | Summary sensors (filter, consumption, heat recovery), periphery sensors (CO2, humidity, temps) |
| `test_binary_sensor.py` | Servo drying and bypass states |
| `test_select.py` | Fan power and humidity select entities |
| `test_number.py` | Temperature number entity value and attributes (min/max/step) |

---

## Manual Testing with Docker

### Start Dev HA Instance

```bash
docker compose up -d
```

Open http://localhost:8123 and complete the HA onboarding wizard.

The integration code is mounted from `./custom_components` — changes are reflected after restarting the container:

```bash
docker compose restart
```

### Stop

```bash
docker compose down
```

---

## Manual Test Scenarios

### 1. Integration Setup

1. Go to **Settings > Devices & Services > + Add Integration**
2. Search for "Jablotron Futura"
3. Enter your Jablotron cloud credentials
4. **Expected**: Integration creates a device with all entities
5. **Verify**: Device appears under Devices with model name, firmware, and hardware version

### 2. Invalid Credentials

1. Add the integration with wrong credentials
2. **Expected**: Error message "invalid_auth" — form stays open for retry
3. **Verify**: No entry is created, no error in HA logs beyond the auth failure

### 3. Sensor Values

1. After successful setup, check all sensor entities:
   - `sensor.jablotron_futura_filter_health` — numeric value (%)
   - `sensor.jablotron_futura_device_consumption` — numeric value (W)
   - `sensor.jablotron_futura_heating_recovered_current` — numeric value (W)
   - `sensor.jablotron_futura_fut_co2_ppm_max` — numeric value (ppm)
   - `sensor.jablotron_futura_fut_humi_indoor` — numeric value (%)
   - `sensor.jablotron_futura_fut_temp_indoor` — numeric value (C)
   - `sensor.jablotron_futura_fut_temp_outdoor` — numeric value (C)
2. **Expected**: All sensors show numeric values with correct units
3. **Verify**: Values match what the Jablotron app shows

### 4. Binary Sensors

1. Check binary sensor entities:
   - `binary_sensor.jablotron_futura_current_servo_drying`
   - `binary_sensor.jablotron_futura_current_servo_bypass`
2. **Expected**: Show on/off states correctly

### 5. Fan Power Control

1. Open `select.jablotron_futura_control_fan_power`
2. **Expected**: Dropdown shows speed levels with airflow values (e.g., "0 (off)", "1 (50 m3/h)", ..., "auto")
3. Change the selection
4. **Expected**: Value updates in HA and on the physical unit
5. **Verify**: Check the Jablotron app to confirm the change took effect

### 6. Humidity Control

1. Open `select.jablotron_futura_control_humidity`
2. **Expected**: Dropdown shows humidity mode options
3. Change the selection
4. **Expected**: Value updates in HA and on the physical unit

### 7. Temperature Control

1. Open `number.jablotron_futura_control_temperature`
2. **Expected**: Slider with min/max/step from the device, current value shown
3. Change the temperature
4. **Expected**: Value updates in HA and on the physical unit
5. **Verify**: Check the Jablotron app to confirm the change

### 8. Data Refresh

1. Wait 5+ minutes after setup
2. **Expected**: Sensor values update automatically without errors in the log
3. **Verify**: Check HA logs for any error messages related to `jablotron_futura`

### 9. Integration Unload/Reload

1. Go to **Settings > Devices & Services > Jablotron Futura**
2. Click the 3-dot menu > **Reload**
3. **Expected**: Integration reloads without errors, all entities remain available
4. Click the 3-dot menu > **Delete**
5. **Expected**: Integration and all entities are removed cleanly

### 10. Upgrade from 0.2.x

If you have the previous version installed:
1. Replace the `custom_components/jablotron_futura` folder with the new version
2. Restart Home Assistant
3. **Expected**: All existing entities keep their entity IDs and history
4. **Verify**: Check automations and dashboards still work with the same entity IDs
