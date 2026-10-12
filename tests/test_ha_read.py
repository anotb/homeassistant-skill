import contextlib
from datetime import datetime, timezone
from http.client import IncompleteRead
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ha_read import Client, HAError, main


TOKEN = "fake-test-token-never-use-in-production"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.respond()

    def do_POST(self):
        self.respond()

    def respond(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self.server.calls.append((self.command, self.path, dict(self.headers), body))
        if self.server.disconnect:
            self.connection.shutdown(socket.SHUT_RDWR)
            return
        status, headers, data = self.server.reply
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class ClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.origin = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.server.calls = []
        self.server.disconnect = False
        self.reply({"message": "API running."})
        self.client = Client(self.origin, TOKEN, 1)

    def reply(self, result, status=200):
        self.server.reply = (status, {"Content-Type": "application/json"}, json.dumps(result).encode())

    def test_api_probe_and_auth_header(self):
        self.assertEqual(self.client.get("/api/"), {"message": "API running."})
        method, path, headers, body = self.server.calls[0]
        self.assertEqual((method, path, body), ("GET", "/api/", b""))
        self.assertEqual(headers["Authorization"], "Bearer " + TOKEN)

    def test_get_does_not_mutate_states(self):
        state = {"entity_id": "sensor.temperature", "state": "unavailable", "attributes": {}}
        self.reply(state)
        self.assertEqual(self.client.get("/api/states/sensor.temperature"), state)
        self.assertEqual(self.server.calls[0][0], "GET")

    def test_allowlisted_discovery_reads(self):
        for path in ["/api/config", "/api/components", "/api/services", "/api/states", "/api/calendars"]:
            with self.subTest(path=path):
                self.client.get(path)
        self.assertEqual(len(self.server.calls), 5)

    def test_unsafe_paths_rejected_before_network(self):
        paths = ["/auth/token", "//example.test/api/", "https://example.test/api/",
                 "/api/services/light/turn_on", "/api/states/all", "/api/../auth/token",
                 "/api/states/light.kitchen?x=1", "/api/states/light.kitchen/..",
                 "/api/states/light.kitchen%2F..", "/api/template", "/api/events"]
        for path in paths:
            with self.subTest(path=path), self.assertRaises(HAError):
                self.client.get(path)
        self.assertEqual(self.server.calls, [])

    def test_forecast_requires_response_data_and_exact_target(self):
        forecasts = [{"datetime": "2026-10-11T00:00:00Z", "temperature": 20}]
        self.reply({"changed_states": [{"entity_id": "light.unrelated"}],
                    "service_response": {"weather.home": {"forecast": forecasts}}})
        self.assertEqual(self.client.forecast("weather.home", "hourly"), forecasts)
        method, path, _, body = self.server.calls[0]
        self.assertEqual((method, path), ("POST", "/api/services/weather/get_forecasts?return_response"))
        self.assertEqual(json.loads(body), {"entity_id": "weather.home", "type": "hourly"})

    def test_empty_forecast_is_valid(self):
        self.reply({"changed_states": [], "service_response": {"weather.home": {"forecast": []}}})
        self.assertEqual(self.client.forecast("weather.home", "twice_daily"), [])

    def test_malformed_forecast_is_not_interpreted_as_success(self):
        for result in [[], {}, {"service_response": {"weather.other": {"forecast": []}}},
                       {"service_response": {"weather.home": {"forecast": {}}}}]:
            with self.subTest(result=result):
                self.reply(result)
                with self.assertRaises(HAError):
                    self.client.forecast("weather.home")

    def test_calendar_bounds_are_encoded_and_all_day_dates_preserved(self):
        events = [{"summary": "Holiday", "start": {"date": "2026-10-12"}, "end": {"date": "2026-10-13"}}]
        self.reply(events)
        start = datetime(2026, 10, 11, tzinfo=timezone.utc)
        self.assertEqual(self.client.calendar("calendar.personal", 7, start), events)
        method, path, _, _ = self.server.calls[0]
        self.assertEqual(method, "GET")
        self.assertIn("%2B00%3A00", path)
        self.assertEqual(parse_qs(urlsplit(path).query), {
            "start": ["2026-10-11T00:00:00+00:00"], "end": ["2026-10-18T00:00:00+00:00"]})

    def test_invalid_entity_window_and_forecast_type_never_send(self):
        calls = [lambda: self.client.forecast("light.home"),
                 lambda: self.client.forecast("weather.home,weather.other"),
                 lambda: self.client.forecast("weather.home", "weekly"),
                 lambda: self.client.calendar("sensor.home"),
                 lambda: self.client.calendar("calendar.personal", 0),
                 lambda: self.client.calendar("calendar.personal", 32),
                 lambda: self.client.calendar("calendar.personal", 1, datetime(2026, 10, 11))]
        for call in calls:
            with self.assertRaises(HAError):
                call()
        self.assertEqual(self.server.calls, [])

    def test_invalid_settings_are_redacted(self):
        urls = ["", "ftp://example.test", "https://example.test/api", "https://example.test?q=" + TOKEN,
                "https://" + TOKEN + "@example.test", "https://example.test/#" + TOKEN,
                "http://example.test:bad", "http://example.test:0", "http://example.test\n",
                "https://example.test\\evil", "http://[invalid"]
        for url in urls:
            with self.subTest(url=url), self.assertRaises(HAError) as caught:
                Client(url, TOKEN)
            self.assertNotIn(TOKEN, str(caught.exception))
        for token in ["", " " + TOKEN, TOKEN + "\n", TOKEN + "\x00", TOKEN + "\u0100"]:
            with self.assertRaises(HAError):
                Client(self.origin, token)
        for timeout in [0, -1, 121, float("inf"), float("nan")]:
            with self.assertRaises(HAError):
                Client(self.origin, TOKEN, timeout)

    def test_trailing_slash_is_normalized(self):
        Client(self.origin + "/", TOKEN).get("/api/")
        self.assertEqual(self.server.calls[0][1], "/api/")

    def test_http_errors_do_not_echo_body_or_retry(self):
        for code in [400, 401, 403, 404, 429, 500, 503]:
            with self.subTest(code=code):
                self.server.calls = []
                self.reply({"message": TOKEN + " private home information"}, code)
                with self.assertRaises(HAError) as caught:
                    self.client.get("/api/")
                self.assertIn(str(code), str(caught.exception))
                self.assertNotIn(TOKEN, str(caught.exception))
                self.assertNotIn("private home", str(caught.exception))
                self.assertEqual(len(self.server.calls), 1)

    def test_redirects_are_never_followed_even_same_origin(self):
        for code in [301, 302, 303, 307, 308]:
            with self.subTest(code=code):
                self.server.calls = []
                self.server.reply = (code, {"Location": self.origin + "/api/config?secret=" + TOKEN}, b"")
                with self.assertRaisesRegex(HAError, "Redirect refused"):
                    self.client.get("/api/")
                self.assertEqual(len(self.server.calls), 1)

    def test_invalid_json_body_is_redacted(self):
        for raw in [TOKEN.encode(), b"\xff", b"<html>private login</html>"]:
            self.server.reply = (200, {}, raw)
            with self.assertRaisesRegex(HAError, "Expected a JSON") as caught:
                self.client.get("/api/")
            self.assertNotIn(TOKEN, str(caught.exception))

    def test_response_size_limit(self):
        self.server.reply = (200, {}, b" " * 65)
        with patch("ha_read.MAX_RESPONSE", 64), self.assertRaisesRegex(HAError, "limit"):
            self.client.get("/api/")

    def test_disconnected_request_is_not_retried(self):
        self.server.disconnect = True
        with self.assertRaisesRegex(HAError, "No retry"):
            self.client.get("/api/")
        self.assertEqual(len(self.server.calls), 1)

    def test_socket_timeout_is_redacted_and_passed_to_transport(self):
        with patch.object(self.client.opener, "open", side_effect=TimeoutError(TOKEN)) as opened:
            with self.assertRaises(HAError) as caught:
                self.client.get("/api/")
            self.assertNotIn(TOKEN, str(caught.exception))
            self.assertEqual(opened.call_args.kwargs["timeout"], 1)
            self.assertEqual(opened.call_count, 1)

    def test_incomplete_http_response_is_redacted(self):
        with patch.object(self.client.opener, "open", side_effect=IncompleteRead(TOKEN.encode())):
            with self.assertRaises(HAError) as caught:
                self.client.get("/api/")
            self.assertNotIn(TOKEN, str(caught.exception))

    def test_environment_proxy_is_ignored(self):
        with patch.dict(os.environ, {"http_proxy": "http://127.0.0.1:1", "no_proxy": ""}):
            client = Client(self.origin, TOKEN)
            self.assertEqual(client.get("/api/"), {"message": "API running."})

    def test_cli_uses_environment_and_has_clean_failure(self):
        with patch.dict(os.environ, {"HA_URL": self.origin, "HA_TOKEN": TOKEN}), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["get"]), 0)
        self.assertEqual(json.loads(output.getvalue()), {"message": "API running."})
        with patch.dict(os.environ, {"HA_URL": "", "HA_TOKEN": TOKEN}), contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(main(["get"]), 1)
        self.assertNotIn(TOKEN, errors.getvalue())
        self.assertNotIn("Traceback", errors.getvalue())

    def test_actual_cli_process(self):
        helper = Path(__file__).resolve().parents[1] / "scripts" / "ha_read.py"
        env = {**os.environ, "HA_URL": self.origin, "HA_TOKEN": TOKEN}
        result = subprocess.run([sys.executable, str(helper), "get", "/api/services"],
                                env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"message": "API running."})
        self.assertNotIn(TOKEN, result.stdout + result.stderr)

    def test_cli_redacts_credentials_echoed_by_successful_server(self):
        self.reply({"message": "echoed " + TOKEN})
        with patch.dict(os.environ, {"HA_URL": self.origin, "HA_TOKEN": TOKEN}), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["get"]), 0)
        self.assertNotIn(TOKEN, output.getvalue())
        self.assertEqual(json.loads(output.getvalue()), {"message": "echoed [REDACTED]"})


if __name__ == "__main__":
    unittest.main()
