"""Exercise corrected documentation requests against a strict local API contract."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import threading
import unittest


class ContractHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.calls.append((self.path, body))
        valid = False
        if self.path == "/api/services/light/turn_on":
            valid = body.get("color_temp_kelvin") == 3333 and "color_temp" not in body
        elif self.path == "/api/services/script/bedtime_routine":
            valid = body.get("brightness") == 20 and body.get("delay_minutes") == 5 and "variables" not in body
        elif self.path == "/api/services/automation/trigger":
            valid = body.get("skip_condition") is False
        elif self.path == "/api/services/weather/get_forecasts?return_response":
            valid = body.get("entity_id") == "weather.home" and body.get("type") in {"daily", "hourly"}
        self.send_response(200 if valid else 400)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"{}")


@unittest.skipUnless(shutil.which("curl"), "curl is needed to execute the Bash curl examples")
class ExampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), ContractHandler)
        cls.server.calls = []
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.origin = f"http://127.0.0.1:{cls.server.server_port}"
        source = (Path(__file__).resolve().parents[1] / "references" / "rest-examples.md").read_text(encoding="utf-8")
        cls.commands = [line.strip() for line in source.replace("\\\n", " ").splitlines() if line.startswith("curl ")]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def exercise(self, command):
        # No shell evaluation: only curl's argv. All URLs and credentials are fake.
        argv = shlex.split(command)
        self.assertEqual(argv[0], "curl")
        self.assertIn("--connect-timeout", argv)
        self.assertIn("--max-time", argv)
        self.assertIn("-fsS", argv)
        argv = [arg.replace("$HA_URL", self.origin).replace("$HA_TOKEN", "fake-test-token") for arg in argv]
        self.assertTrue(any(arg.startswith(self.origin + "/api/") for arg in argv))
        result = subprocess.run(argv, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_kelvin_example_is_accepted(self):
        self.exercise(next(c for c in self.commands if "color_temp_kelvin" in c))

    def test_direct_script_variables_are_accepted(self):
        self.exercise(next(c for c in self.commands if "/script/bedtime_routine" in c))

    def test_automation_conditions_are_respected(self):
        self.exercise(next(c for c in self.commands if "/automation/trigger" in c))

    def test_forecasts_request_response_data(self):
        commands = [c for c in self.commands if "/weather/get_forecasts" in c]
        self.assertEqual(len(commands), 2)
        for command in commands:
            with self.subTest(command=command):
                self.exercise(command)


if __name__ == "__main__":
    unittest.main()
