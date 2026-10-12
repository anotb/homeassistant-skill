# Home Assistant REST examples

Read the setup, transport and safety requirements in `SKILL.md` first. These are
Bash examples requiring curl and jq; substitute verified entity IDs and parameters.
Never run device actions as connectivity tests. The optional Python helper supports
read-only discovery, forecast and calendar queries on Windows, macOS and Linux.

## Switches

```bash
# Turn on
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/switch/turn_on" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "switch.office_lamp"}'

# Turn off
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/switch/turn_off" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "switch.office_lamp"}'

# Toggle
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/switch/toggle" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "switch.office_lamp"}'
```

## Lights

```bash
# Turn on with brightness
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/light/turn_on" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "light.living_room", "brightness_pct": 80}'

# Turn on with color (RGB)
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/light/turn_on" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "light.living_room", "rgb_color": [255, 150, 50]}'

# Turn on with color temperature (Kelvin; check supported_color_modes and min/max_color_temp_kelvin)
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/light/turn_on" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "light.living_room", "color_temp_kelvin": 3333}'

# Turn off
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/light/turn_off" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "light.living_room"}'
```

## Scenes

```bash
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/scene/turn_on" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "scene.movie_time"}'
```

## Scripts

```bash
# List all scripts
curl -fsS --connect-timeout 5 --max-time 30 "$HA_URL/api/states" -H "Authorization: Bearer $HA_TOKEN" \
  | jq -r '.[] | select(.entity_id | startswith("script.")) | "\(.entity_id): \(.state)"'

# Run a script
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/script/turn_on" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "script.bedtime_routine"}'

# Run a script with variables
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/script/bedtime_routine" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"brightness": 20, "delay_minutes": 5}'
```

Direct `script.NAME` calls take variables at the top level and wait for completion;
`script.turn_on` takes `variables` nested alongside `entity_id` and starts the script
without waiting. A timeout may occur after execution starts: inspect state before
doing anything further, and never blindly retry a script or toggle.

## Automations

```bash
# List all automations
curl -fsS --connect-timeout 5 --max-time 30 "$HA_URL/api/states" -H "Authorization: Bearer $HA_TOKEN" \
  | jq -r '.[] | select(.entity_id | startswith("automation.")) | "\(.entity_id): \(.state)"'

# Trigger an automation
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/automation/trigger" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "automation.morning_routine", "skip_condition": false}'

# Enable automation
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/automation/turn_on" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "automation.morning_routine"}'

# Disable automation
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/automation/turn_off" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "automation.morning_routine"}'
```

`automation.trigger` skips conditions by default. The example explicitly respects
them; bypass conditions only when the user requests it and the effects are known.

## Climate Control

```bash
# Get thermostat state
curl -fsS --connect-timeout 5 --max-time 30 "$HA_URL/api/states/climate.thermostat" -H "Authorization: Bearer $HA_TOKEN" \
  | jq '{state: .state, current_temp: .attributes.current_temperature, target_temp: .attributes.temperature}'

# Set temperature
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/climate/set_temperature" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "climate.thermostat", "temperature": 72}'

# Set HVAC mode (heat, cool, auto, off)
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/climate/set_hvac_mode" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "climate.thermostat", "hvac_mode": "auto"}'
```

Use the entity's `temperature_unit`, `min_temp`, `max_temp`, `target_temp_step`
and `hvac_modes` rather than assuming Fahrenheit or a supported mode.

## Covers (Blinds, Garage Doors)

**Safety:** Confirm with the user before opening/closing garage doors or gates.

```bash
# Open
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/cover/open_cover" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "cover.garage_door"}'

# Close
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/cover/close_cover" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "cover.garage_door"}'

# Set position (0 = closed, 100 = open)
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/cover/set_cover_position" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "cover.blinds", "position": 50}'
```

## Locks

**Safety:** Always confirm with the user before locking/unlocking.

```bash
# Lock
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/lock/lock" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "lock.front_door"}'

# Unlock
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/lock/unlock" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "lock.front_door"}'
```

## Fans

```bash
# Turn on
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/fan/turn_on" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "fan.bedroom", "percentage": 50}'

# Turn off
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/fan/turn_off" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "fan.bedroom"}'
```

## Media Players

```bash
# Play/pause
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/media_player/media_play_pause" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "media_player.living_room_tv"}'

# Set volume (0.0 to 1.0)
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/media_player/volume_set" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "media_player.living_room_tv", "volume_level": 0.5}'
```

## Vacuum

```bash
# Start cleaning
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/vacuum/start" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "vacuum.robot"}'

# Return to dock
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/vacuum/return_to_base" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "vacuum.robot"}'
```

## Alarm Control Panel

**Safety:** Always confirm with the user before arming/disarming.

```bash
# Arm (home mode)
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/alarm_control_panel/alarm_arm_home" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "alarm_control_panel.home"}'

# Disarm (requires code if configured)
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/alarm_control_panel/alarm_disarm" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "alarm_control_panel.home", "code": "1234"}'
```

## Notifications

```bash
# List available notification targets
curl -fsS --connect-timeout 5 --max-time 30 "$HA_URL/api/services" -H "Authorization: Bearer $HA_TOKEN" \
  | jq -r '.[] | select(.domain == "notify") | .services | keys[]' | sort

# Send a notification to a mobile device
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/notify/mobile_app_phone" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "Front door opened", "title": "Home Alert"}'

# Call the configured default notification group (not necessarily all devices)
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/notify/notify" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "System alert", "title": "Home Assistant"}'
```

Replace `mobile_app_phone` with the actual service name from the list command.
For entity-based notification integrations, discover `notify.*` entities and the
`notify.send_message` action instead. Verify recipients and scope before sending;
notifications and TTS are external effects, not read-only tests.

## Person & Presence

```bash
# Who is home?
curl -fsS --connect-timeout 5 --max-time 30 "$HA_URL/api/states" -H "Authorization: Bearer $HA_TOKEN" \
  | jq -r '.[] | select(.entity_id | startswith("person.")) | "\(.attributes.friendly_name // .entity_id): \(.state)"'

# Device tracker locations
curl -fsS --connect-timeout 5 --max-time 30 "$HA_URL/api/states" -H "Authorization: Bearer $HA_TOKEN" \
  | jq -r '.[] | select(.entity_id | startswith("device_tracker.")) | "\(.entity_id): \(.state)"'
```

States: `home`, `not_home`, or a zone name.

## Weather

```bash
# Current weather
curl -fsS --connect-timeout 5 --max-time 30 "$HA_URL/api/states/weather.home" -H "Authorization: Bearer $HA_TOKEN" \
  | jq '{state: .state, temperature: .attributes.temperature, humidity: .attributes.humidity, wind_speed: .attributes.wind_speed}'

# Get forecast (daily)
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/weather/get_forecasts?return_response" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "weather.home", "type": "daily"}'

# Get forecast (hourly)
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/weather/get_forecasts?return_response" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "weather.home", "type": "hourly"}'
```

Forecast services require `?return_response`; extract
`.service_response["weather.home"].forecast` with `jq`. Select a forecast type
supported by that entity (`daily`, `hourly`, or `twice_daily`). Do not use the old
`forecast` state attribute or interpret the normal changed-states array as forecast
data. Current conditions and forecasts use the entity's reported units.

## Input Helpers

```bash
# Toggle an input boolean
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/input_boolean/toggle" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "input_boolean.guest_mode"}'

# Set input number
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/input_number/set_value" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "input_number.target_temperature", "value": 72}'

# Set input select
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/input_select/select_option" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "input_select.house_mode", "option": "Away"}'

# Set input text
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/input_text/set_value" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "input_text.welcome_message", "value": "Welcome home!"}'

# Set input datetime
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/input_datetime/set_datetime" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "input_datetime.alarm_time", "time": "07:30:00"}'
```

## Calendar

```bash
# List all calendars
curl -fsS --connect-timeout 5 --max-time 30 "$HA_URL/api/calendars" -H "Authorization: Bearer $HA_TOKEN" \
  | jq -r '.[].entity_id'

# Get upcoming events with explicit timezone-aware bounds (end is exclusive)
START='2026-10-11T00:00:00+00:00'
END='2026-10-18T00:00:00+00:00'
curl -fsS --connect-timeout 5 --max-time 30 --get "$HA_URL/api/calendars/calendar.personal" \
  -H "Authorization: Bearer $HA_TOKEN" \
  --data-urlencode "start=$START" --data-urlencode "end=$END" \
  | jq '[.[] | {summary, start: (.start.dateTime // .start.date), end: (.end.dateTime // .end.date)}]'
```

Choose dates for the requested window, or use `ha_read.py calendar` for a rolling
window on Windows, Linux or macOS. All-day events use `date` rather than `dateTime`.

## Text-to-Speech

```bash
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/tts/speak" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "tts.google_en", "media_player_entity_id": "media_player.living_room_speaker", "message": "Dinner is ready"}'
```

Replace `tts.google_en` with your TTS entity and `media_player.living_room_speaker` with the target speaker.

## Call Any Service

The general pattern for any HA service:

```bash
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/{domain}/{service}" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "domain.entity_name"}'
```

### Batch operations

Control multiple entities in one call by passing an array of entity IDs:

```bash
# Turn off all living room lights at once
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/services/light/turn_off" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": ["light.living_room", "light.living_room_lamp", "light.living_room_ceiling"]}'
```

## Template Evaluation

The `/api/template` endpoint evaluates Jinja2 templates server-side. Useful for computed queries.

```bash
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/template" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"template": "TEMPLATE_STRING"}'
```

### Examples

```bash
# Count entities by domain
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/template" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"template": "{{ states.light | list | count }} lights"}'

# Get entity state in a template
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/template" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"template": "{{ states(\"light.living_room\") }}"}'

# List all entities that are "on"
curl -fsS --connect-timeout 5 --max-time 30 -X POST "$HA_URL/api/template" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"template": "{{ states | selectattr(\"state\", \"eq\", \"on\") | map(attribute=\"entity_id\") | list }}"}'
```

Available template functions: `states()`, `is_state()`, `state_attr()`, `areas()`, `area_entities()`, `area_name()`, `floors()`, `floor_areas()`, `labels()`, `label_entities()`, `devices()`, `device_entities()`, `now()`, `relative_time()`.

## History & Logbook

### Entity state history

```bash
# Last 24 hours for a specific entity
curl -fsS --connect-timeout 5 --max-time 30 "$HA_URL/api/history/period?filter_entity_id=sensor.temperature" \
  -H "Authorization: Bearer $HA_TOKEN" \
  | jq '.[0] | [.[] | {state: .state, last_changed: .last_changed}]'

# Specific time range (ISO 8601)
curl -fsS --connect-timeout 5 --max-time 30 "$HA_URL/api/history/period/2025-01-15T00:00:00Z?end_time=2025-01-15T23:59:59Z&filter_entity_id=sensor.temperature" \
  -H "Authorization: Bearer $HA_TOKEN" \
  | jq '.[0]'
```

### Logbook

```bash
# Recent logbook entries
curl -fsS --connect-timeout 5 --max-time 30 "$HA_URL/api/logbook" -H "Authorization: Bearer $HA_TOKEN" \
  | jq '.[:10]'

# Logbook for a specific entity
curl -fsS --connect-timeout 5 --max-time 30 "$HA_URL/api/logbook?entity=light.living_room" \
  -H "Authorization: Bearer $HA_TOKEN" \
  | jq '.[:10] | [.[] | {name: .name, message: .message, when: .when}]'
```

## Dashboard Overview

Quick status of all active devices:

```bash
# All lights that are on
curl -fsS --connect-timeout 5 --max-time 30 "$HA_URL/api/states" -H "Authorization: Bearer $HA_TOKEN" \
  | jq -r '.[] | select(.entity_id | startswith("light.")) | select(.state == "on") | .entity_id'

# All open doors/windows (binary sensors)
curl -fsS --connect-timeout 5 --max-time 30 "$HA_URL/api/states" -H "Authorization: Bearer $HA_TOKEN" \
  | jq -r '.[] | select(.entity_id | startswith("binary_sensor.")) | select(.state == "on") | select(.attributes.device_class == "door" or .attributes.device_class == "window") | .entity_id'

# Temperature sensors
curl -fsS --connect-timeout 5 --max-time 30 "$HA_URL/api/states" -H "Authorization: Bearer $HA_TOKEN" \
  | jq -r '.[] | select(.entity_id | startswith("sensor.")) | select(.attributes.device_class == "temperature") | "\(.attributes.friendly_name // .entity_id): \(.state)\(.attributes.unit_of_measurement // "")"'

# Climate summary (all thermostats)
curl -fsS --connect-timeout 5 --max-time 30 "$HA_URL/api/states" -H "Authorization: Bearer $HA_TOKEN" \
  | jq -r '.[] | select(.entity_id | startswith("climate.")) | "\(.attributes.friendly_name // .entity_id): \(.state), current: \(.attributes.current_temperature)°, target: \(.attributes.temperature)°"'

# Lock status
curl -fsS --connect-timeout 5 --max-time 30 "$HA_URL/api/states" -H "Authorization: Bearer $HA_TOKEN" \
  | jq -r '.[] | select(.entity_id | startswith("lock.")) | "\(.attributes.friendly_name // .entity_id): \(.state)"'

# Who is home
curl -fsS --connect-timeout 5 --max-time 30 "$HA_URL/api/states" -H "Authorization: Bearer $HA_TOKEN" \
  | jq -r '.[] | select(.entity_id | startswith("person.")) | "\(.attributes.friendly_name // .entity_id): \(.state)"'
```

## Entity Domains

| Domain | Examples |
|--------|----------|
| `switch.*` | Smart plugs, generic switches |
| `light.*` | Lights (Hue, LIFX, etc.) |
| `scene.*` | Pre-configured scenes |
| `script.*` | Reusable action sequences |
| `automation.*` | Automations |
| `climate.*` | Thermostats, AC units |
| `cover.*` | Blinds, garage doors, gates |
| `lock.*` | Smart locks |
| `fan.*` | Fans, ventilation |
| `media_player.*` | TVs, speakers, streaming devices |
| `vacuum.*` | Robot vacuums |
| `alarm_control_panel.*` | Security systems |
| `notify.*` | Notification targets |
| `person.*` | People / presence tracking |
| `device_tracker.*` | Device locations |
| `weather.*` | Weather conditions and forecasts |
| `calendar.*` | Calendar events |
| `tts.*` | Text-to-speech engines |
| `sensor.*` | Temperature, humidity, power, etc. |
| `binary_sensor.*` | Motion, door/window, presence |
| `input_boolean.*` | Virtual toggles |
| `input_number.*` | Numeric sliders |
| `input_select.*` | Dropdown selectors |
| `input_text.*` | Text inputs |
| `input_datetime.*` | Date/time inputs |
