# Home Assistant Skill

An AI agent skill for controlling Home Assistant devices and automations through natural language. Lights, switches, scenes, thermostats, locks, media players, vacuums, and more — all via the HA REST API.

Works with [Claude Code](https://docs.anthropic.com/en/docs/claude-code), [OpenClaw](https://openclaw.com), [Cursor](https://cursor.com), and any tool supporting the [Agent Skills](https://github.com/anthropics/agent-skills) standard.

## Prerequisites

- Home Assistant instance with API access
- `curl` and `jq` installed

## Installation

### Claude Code

```bash
git clone https://github.com/anotb/homeassistant-skill.git ~/.claude/skills/homeassistant-skill
```

### OpenClaw (via ClawdHub)

```bash
clawhub install homeassistant-skill
```

### Cursor / Other

Clone to your agent's skill directory.

## Configuration

1. Create a long-lived access token in Home Assistant: Profile → Long-Lived Access Tokens
2. Set environment variables:

```bash
export HA_URL=http://10.0.0.10:8123
export HA_TOKEN=your-long-lived-access-token
```

## What You Can Do

| Domain | Actions |
|--------|---------|
| Switches | Turn on, off, toggle |
| Lights | On/off, brightness, color, color temp |
| Scenes | Activate scenes |
| Automations | Trigger, enable, disable |
| Climate | Set temperature, HVAC mode |
| Covers | Open, close, set position (blinds, garage) |
| Locks | Lock, unlock (with safety confirmation) |
| Fans | On/off, speed |
| Media players | Play, pause, volume |
| Vacuum | Start, return to dock |
| Alarm | Arm, disarm (with safety confirmation) |
| Sensors | Read temperature, humidity, power, etc. |

## Usage Examples

```bash
# "Turn on the office light at 80%"
curl -s -X POST "$HA_URL/api/services/light/turn_on" \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "light.office", "brightness_pct": 80}'

# "What's the temperature?"
curl -s "$HA_URL/api/states" -H "Authorization: Bearer $HA_TOKEN" \
  | jq '.[] | select(.attributes.device_class == "temperature") | {name: .attributes.friendly_name, temp: .state, unit: .attributes.unit_of_measurement}'
```

## License

MIT
