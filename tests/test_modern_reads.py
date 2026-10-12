import json
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, unquote, urlsplit

from test_ha_read import TOKEN
from ha_read import Client, HAError, safe_json
from ha_ws_read import WSClient


class TargetServiceTests(unittest.TestCase):
    def test_discovery_sends_only_target_query(self):
        client = WSClient("http://localhost:8123", TOKEN)
        target = {"entity_id": ["light.kitchen"]}
        with patch.object(client, "_exchange", return_value={"result": ["light.turn_on"]}) as exchange:
            self.assertEqual(client.target_services(target), {"result": ["light.turn_on"]})
        exchange.assert_called_once_with({"type": "get_services_for_target", "target": target, "expand_group": False})

    def test_discovery_rejects_broad_or_invalid_scope_before_network(self):
        client = WSClient("http://localhost:8123", TOKEN)
        with patch.object(client, "_exchange") as exchange:
            for target in [{}, {"entity_id": ["all"]}, {"entity_id": ["light.*"]},
                           {"service": ["light.turn_on"]}, {"entity_id": ["light.kitchen"] * 65}]:
                with self.assertRaises(HAError):
                    client.target_services(target)
            exchange.assert_not_called()


class ModernRestTests(unittest.TestCase):
    def setUp(self):
        self.client = Client("http://localhost:8123", TOKEN)

    def test_profile_reports_installed_version_and_actions_without_sensitive_config(self):
        config = {"version": "2026.10.1", "components": ["weather", "conversation"], "time_zone": "UTC",
                  "unit_system": {"temperature": "°C"}, "latitude": 12, "longitude": 34,
                  "config_dir": "/private", "location_name": "Private Home", "internal_url": "private"}
        services = [{"domain": "weather", "services": {"get_forecasts": {"response": {"optional": False}}}}]
        with patch.object(self.client, "get", side_effect=[config, services]) as get:
            result = self.client.profile()
        self.assertEqual(get.call_args_list[0].args, ("/api/config",))
        self.assertEqual(get.call_args_list[1].args, ("/api/services",))
        self.assertEqual(result["version"], "2026.10.1")
        self.assertEqual(result["actions"], {"weather": ["get_forecasts"]})
        self.assertFalse(set(result) & {"latitude", "longitude", "config_dir", "location_name", "internal_url"})

    def test_action_schema_preserves_selectors_response_and_targets_without_execution(self):
        schema = {"fields": {"color_temp_kelvin": {"selector": {"color_temp": {"unit": "kelvin"}}}},
                  "target": {"entity": [{"domain": "light"}]}, "response": {"optional": True}}
        with patch.object(self.client, "get", return_value=[{"domain": "light", "services": {"turn_on": schema}}]) as get:
            self.assertEqual(self.client.action_schema("light.turn_on"), {"action": "light.turn_on", "schema": schema})
        get.assert_called_once_with("/api/services")

    def test_missing_and_invalid_action_names_never_invoke_an_action(self):
        with patch.object(self.client, "get", return_value=[]):
            with self.assertRaisesRegex(HAError, "not exposed"):
                self.client.action_schema("light.turn_on")
        with patch.object(self.client, "get") as get:
            for name in ["light/turn_on", "light.turn_on?x=1", "all", "light.turn_on.extra"]:
                with self.assertRaises(HAError):
                    self.client.action_schema(name)
            get.assert_not_called()

    def test_health_preserves_unknown_vs_unavailable_and_suppresses_attributes(self):
        states = [{"entity_id": "sensor.energy", "state": "unavailable", "attributes": {"token": TOKEN}},
                  {"entity_id": "sensor.power", "state": "unknown"}, {"entity_id": "light.kitchen", "state": "off"}]
        with patch.object(self.client, "get", return_value=states):
            result = self.client.health()
        self.assertEqual(result, {"entity_count": 3, "domains": {"light": 1, "sensor": 2},
                                  "unavailable": ["sensor.energy"], "unknown": ["sensor.power"]})

    def test_history_encodes_timestamps_and_limits_scope(self):
        with patch.object(self.client, "_request", return_value=[[]]) as request:
            self.assertEqual(self.client.history("sensor.energy", "2026-10-11T00:00:00+02:00", "2026-10-12T00:00:00+02:00"), [[]])
        path = request.call_args.args[0]
        self.assertEqual(unquote(urlsplit(path).path), "/api/history/period/2026-10-11T00:00:00+02:00")
        query = parse_qs(urlsplit(path).query, keep_blank_values=True)
        self.assertEqual(query["filter_entity_id"], ["sensor.energy"])
        self.assertEqual(query["end_time"], ["2026-10-12T00:00:00+02:00"])
        self.assertIn("minimal_response", query)
        self.assertIn("no_attributes", query)

    def test_invalid_windows_are_rejected_before_network(self):
        with patch.object(self.client, "_request") as request:
            for start, end in [("2026-10-11", "2026-10-12"), ("2026-10-11T00:00:00Z", "2026-10-10T00:00:00Z"),
                               ("2026-10-11T00:00:00Z", "2026-10-19T00:00:00Z"), ("bad", "bad")]:
                with self.assertRaises(HAError):
                    self.client.history("sensor.energy", start, end)
            request.assert_not_called()

    def test_json_redaction_preserves_escapes_keys_and_numeric_values(self):
        for token in ["n", '"', "\\", ":", "fake-token"]:
            raw = {"name": "line\n" + token, token: [12, True, None]}
            result = json.loads(safe_json(raw, token))
            self.assertEqual(result["[REDACTED]"], [12, True, None])
            self.assertEqual(result["name".replace(token, "[REDACTED]")], ("line\n" + token).replace(token, "[REDACTED]"))

    def test_empty_query_or_fragment_is_not_a_base_origin(self):
        for url in ["https://example.test?", "https://example.test#"]:
            with self.assertRaises(HAError):
                Client(url, TOKEN)

    def test_malformed_profile_is_a_safe_failure(self):
        for config, services in [({"version": "test", "components": None}, []),
                                 ({"version": "test"}, [{"domain": "light", "services": ["turn_on"]}]),
                                 ({}, {}), ({"version": "test", "components": [None]}, [])]:
            with patch.object(self.client, "get", side_effect=[config, services]), self.assertRaises(HAError):
                self.client.profile()


if __name__ == "__main__":
    unittest.main()
