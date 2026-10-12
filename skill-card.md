## Description

Inspect an existing Home Assistant installation and prepare or perform authorized
home-control actions. The skill documents native MCP, REST and WebSocket routes.
Bundled Python readers provide bounded discovery and diagnostics without general
device-control commands.

## Publisher and license

[anotb](https://clawhub.ai/user/anotb). MIT; see [LICENSE](LICENSE).

## Use cases

Read state and action schemas, map entities to devices and locations, inspect
Assist and Energy configuration, query history/statistics, inspect repairs and
automation definitions, validate snippets and discover target-specific actions.
The REST cookbook covers authorized control across 25 entity domains.

## Requirements

OpenClaw requires `HA_URL`, `HA_TOKEN`, curl and jq. Python readers can run
standalone with Python 3.10+. REST uses the standard library; WebSocket reads
optionally require `websockets>=15.0.1,<18`. Bash examples require curl 7.55+.
An existing native MCP connection can be used when its discovered tools cover
the task. No custom server or HA integration is installed by this skill.

## Risks and limits

- An API token has its HA account's authority. Theft can disclose household data
  and permit device actions. Local reader allowlists do not restrict that token
  on the server. Supply existing credentials privately; never share them in chat.
- Presence, locations, calendars and history can reveal routines. Limit reads to
  the requested task and obtain authorization before sharing private results.
- Device actions, notifications and TTS have physical or outbound effects.
  Resolve targets, verify message recipients and inspect indirect effects in
  scripts/automations. Sensitive actions require explicit authorization.
- HTTPS is verified by default. Trusted LAN HTTP remains supported and sends
  credentials without encryption. Shell tracing can expose secrets even though
  curl headers are passed through stdin.
- Optional commands depend on HA version, integrations and account access.
  Unsupported or unauthorized reads fail; do not broaden access to make them work.

See [SECURITY.md](SECURITY.md) for the prior ClawHub review and its fixes.

## Verification

Version 2.2.0 has 60 local tests using fake credentials and loopback services,
with Windows/Linux CI. Authenticated frontend checks verified Core 2026.9.1 and
selected state/action discovery. Python clients remain mock-tested, not live
authenticated API-tested. No HA device action or configuration change was used
for verification.

## Output and source

JSON from readers; Markdown guidance and Bash/JSON examples. Raw outputs can
contain private household data and require review before sharing.

[GitHub source](https://github.com/anotb/homeassistant-skill) ·
[ClawHub skill](https://clawhub.ai/anotb/skills/homeassistant-skill) ·
[Release history](CHANGELOG.md).
