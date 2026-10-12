import contextlib
import base64
import hashlib
import importlib.util
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import logging
import os
import socket as socket_module
from pathlib import Path
import sys
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ha_read import HAError
from ha_ws_read import READS, WSClient, main, transport
from test_ha_read import Handler

TOKEN = "fake-test-token-only"


class AllowlistTests(unittest.TestCase):
    def setUp(self):
        self.client = WSClient("https://example.test", TOKEN)

    def test_read_aliases_only_map_to_read_commands(self):
        with patch.object(self.client, "_exchange", return_value={}) as send:
            for name, kind in READS.items():
                self.client.read(name)
                self.assertEqual(send.call_args.args[0], {"type": kind})
            for forbidden in ["call_service", "energy/save_prefs", "config/entity_registry/update", "assist_pipeline/run", "auth/long_lived_access_token"]:
                before = send.call_count
                with self.assertRaises(HAError):
                    self.client.read(forbidden)
                self.assertEqual(send.call_count, before)

    def test_definition_is_an_exact_read(self):
        with patch.object(self.client, "_exchange", return_value={}) as send:
            self.client.definition("automation.evening")
            self.assertEqual(send.call_args.args[0], {"type": "automation/config", "entity_id": "automation.evening"})
            self.client.definition("script.bedtime")
            self.assertEqual(send.call_args.args[0]["type"], "script/config")
            with self.assertRaises(HAError):
                self.client.definition("light.kitchen")

    def test_validate_config_never_sends_embedded_command_metadata(self):
        with patch.object(self.client, "_exchange", return_value={"result": {"actions": {"valid": True, "error": None}}}) as send:
            self.client.validate_config({"action": [{"action": "light.turn_on", "target": {"entity_id": "light.kitchen"}}]})
            self.assertEqual(send.call_args.args[0]["type"], "validate_config")
            self.assertIn("actions", send.call_args.args[0])
            self.assertNotIn("action", send.call_args.args[0])
            before = send.call_count
            for config in [{"type": "call_service"}, {"id": 9, "action": []}, {}, []]:
                with self.assertRaises(HAError):
                    self.client.validate_config(config)
            self.assertEqual(send.call_count, before)

    def test_target_expansion_has_no_action_and_rejects_all(self):
        target = {"entity_id": ["group.kitchen"], "area_id": ["kitchen"]}
        with patch.object(self.client, "_exchange", return_value={}) as send:
            self.client.resolve_target(target, True)
            self.assertEqual(send.call_args.args[0], {"type": "extract_from_target", "target": target, "expand_group": True})
            before = send.call_count
            for target in [{}, {"entity_id": ["all"]}, {"entity_id": ["light.*"]}, {"area_id": "all"}, {"type": ["call_service"]}]:
                with self.assertRaises(HAError):
                    self.client.resolve_target(target)
            self.assertEqual(send.call_count, before)

    def test_statistics_scope_window_and_external_ids(self):
        with patch.object(self.client, "_exchange", return_value={}) as send:
            self.client.statistics("external:solar", "2026-10-11T00:00:00Z", "2026-10-12T00:00:00Z", "hour")
            data = send.call_args.args[0]
            self.assertEqual(data["type"], "recorder/statistics_during_period")
            self.assertEqual(data["statistic_ids"], ["external:solar"])
            self.assertEqual(data["period"], "hour")
            with self.assertRaises(HAError):
                self.client.statistics("sensor.solar", "2026-10-11", "2026-10-12")

    def test_https_maps_to_wss_and_malformed_settings_fail_before_transport(self):
        self.assertEqual(self.client.uri, "wss://example.test/api/websocket")
        for scheme in ["HTTPS", "hTtPs", "https"]:
            self.assertEqual(WSClient(scheme + "://example.test:8123/", TOKEN).uri, "wss://example.test:8123/api/websocket")
        self.assertEqual(WSClient("HTTP://[::1]:8123/", TOKEN).uri, "ws://[::1]:8123/api/websocket")
        with self.assertRaises(HAError):
            WSClient("http://" + TOKEN + "@example.test", TOKEN)

    def test_validation_current_and_explicit_legacy_formats(self):
        sections = {"triggers": [], "conditions": [], "actions": []}
        expected = {key: {"valid": False, "error": "invalid section"} for key in sections}
        with patch.object(self.client, "_exchange", return_value={"result": expected}) as send:
            self.assertEqual(self.client.validate_config(sections)["result"], expected)
            self.assertEqual(send.call_args.args[0], {"type": "validate_config", **sections})
        legacy = {key[:-1]: {"valid": True, "error": None} for key in sections}
        with patch.object(self.client, "_exchange", return_value={"result": legacy}) as send:
            self.client.validate_config(sections, legacy_keys=True)
            self.assertEqual(set(send.call_args.args[0]), {"type", "trigger", "condition", "action"})

    def test_conflicting_validation_sections_and_silent_noop_fail(self):
        with patch.object(self.client, "_exchange") as send:
            with self.assertRaises(HAError):
                self.client.validate_config({"action": [], "actions": []})
            send.assert_not_called()
        for result in [{}, {"result": {}}, {"result": {"actions": {"valid": "yes"}}}]:
            with patch.object(self.client, "_exchange", return_value=result), self.assertRaises(HAError):
                self.client.validate_config({"actions": []})

    def test_missing_optional_dependency_has_safe_instruction(self):
        with patch("ha_ws_read.importlib.metadata.version", side_effect=ImportError(TOKEN)):
            with self.assertRaises(HAError) as caught:
                self.client.read("config")
        self.assertIn("requirements-websocket.txt", str(caught.exception))
        self.assertNotIn(TOKEN, str(caught.exception))


@unittest.skipUnless(importlib.util.find_spec("websockets"), "optional websockets package not installed")
class WebSocketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from websockets.sync.server import serve
        logger = logging.Logger("test-ha-ws")
        logger.disabled = True
        cls.server = serve(cls.handler, "127.0.0.1", 0, compression=None, logger=logger)
        cls.origin = f"http://127.0.0.1:{cls.server.socket.getsockname()[1]}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join()

    @classmethod
    def handler(cls, socket):
        try:
            cls.paths.append(socket.request.path)
            socket.send(json.dumps(cls.greeting))
            auth = json.loads(socket.recv(timeout=2))
            cls.received.append(auth)
            socket.send(json.dumps(cls.auth_reply))
            command = json.loads(socket.recv(timeout=2))
            cls.received.append(command)
            if command.get("type") == "validate_config":
                sections = set(command) - {"id", "type"}
                valid = bool(sections) and not sections - {"triggers", "conditions", "actions"}
                response = {"id": 1, "type": "result", "success": valid,
                            "result": {key: {"valid": True, "error": None} for key in sections} if valid else None}
                socket.send(json.dumps(response))
            else:
                socket.send(cls.raw_reply if cls.raw_reply is not None else json.dumps(cls.result))
        except Exception:
            pass

    def setUp(self):
        self.__class__.received = []
        self.__class__.paths = []
        self.__class__.greeting = {"type": "auth_required", "ha_version": "2026.10.1"}
        self.__class__.auth_reply = {"type": "auth_ok", "ha_version": "2026.10.1"}
        self.__class__.result = {"id": 1, "type": "result", "success": True, "result": {"test": True}}
        self.__class__.raw_reply = None
        self.client = WSClient(self.origin, TOKEN, 1)

    def test_real_authentication_then_correlated_query_and_close(self):
        result = self.client.read("services")
        self.assertEqual(result, {"ha_version": "2026.10.1", "result": {"test": True}})
        self.assertEqual(self.paths, ["/api/websocket"])
        self.assertEqual(self.received, [{"type": "auth", "access_token": TOKEN}, {"id": 1, "type": "get_services"}])

    def test_current_validation_wire_keys_against_strict_mock_contract(self):
        actions = [{"action": "light.turn_on", "target": {"entity_id": "light.kitchen"}}]
        result = self.client.validate_config({"action": actions})
        self.assertEqual(result["result"], {"actions": {"valid": True, "error": None}})
        self.assertEqual(self.received[1], {"id": 1, "type": "validate_config", "actions": actions})

    def test_untrusted_greeting_never_receives_credential(self):
        self.__class__.greeting = {"type": "unexpected", "message": TOKEN}
        with self.assertRaisesRegex(HAError, "no credential"):
            self.client.read("config")
        self.assertEqual(self.received, [])

    def test_invalid_auth_does_not_send_query_or_retry(self):
        self.__class__.auth_reply = {"type": "auth_invalid", "message": TOKEN}
        with self.assertRaisesRegex(HAError, "rejected authentication") as caught:
            self.client.read("config")
        self.assertNotIn(TOKEN, str(caught.exception))
        self.assertEqual(len(self.received), 1)

    def test_unknown_command_and_permission_failures_are_not_empty_success(self):
        for code in ["unknown_command", "unauthorized", "not_found", "invalid_format", TOKEN]:
            with self.subTest(code=code):
                self.__class__.received = []
                self.__class__.result = {"id": 1, "type": "result", "success": False, "error": {"code": code, "message": TOKEN}}
                with self.assertRaises(HAError) as caught:
                    self.client.read("repairs")
                self.assertNotIn(TOKEN, str(caught.exception))
                self.assertEqual(len(self.received), 2)

    def test_wrong_request_id_and_invalid_json_are_rejected(self):
        for response in ['{"id":2,"type":"result","success":true}', "[1]", TOKEN]:
            with self.subTest(response=response):
                self.__class__.raw_reply = response
                with self.assertRaises(HAError):
                    self.client.read("config")

    def test_transport_bounds_and_verified_tls_settings(self):
        with patch("ha_ws_read.transport") as factory:
            connect = factory.return_value
            connect.side_effect = TimeoutError(TOKEN)
            with self.assertRaises(HAError) as caught:
                self.client.read("config")
        self.assertNotIn(TOKEN, str(caught.exception))
        options = connect.call_args.kwargs
        self.assertIsNone(options["proxy"])
        self.assertIsNone(options["compression"])
        self.assertEqual(options["open_timeout"], 1)
        self.assertEqual(options["max_queue"], 1)
        self.assertNotIn("ssl", options)  # the library's verified default context
        self.assertTrue(options["logger"].disabled)
        self.assertEqual(connect.call_count, 1)

    def test_http_redirect_is_not_followed_and_never_carries_credentials(self):
        redirect = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        redirect.calls = []
        redirect.disconnect = False
        redirect.reply = (302, {"Location": self.client.uri}, b"")
        thread = threading.Thread(target=redirect.serve_forever, daemon=True)
        thread.start()
        try:
            client = WSClient(f"http://127.0.0.1:{redirect.server_port}", TOKEN, 1)
            with self.assertRaises(HAError):
                client.read("config")
            self.assertEqual(len(redirect.calls), 1)
            self.assertNotIn("Authorization", redirect.calls[0][2])
            self.assertEqual(self.received, [])
        finally:
            redirect.shutdown()
            redirect.server_close()
            thread.join()

    def test_oversized_websocket_message_is_rejected(self):
        self.__class__.raw_reply = " " * 257
        with patch("ha_ws_read.MAX_RESPONSE", 256), self.assertRaises(HAError):
            self.client.read("config")

    def test_watchdog_interrupts_a_blocked_send(self):
        aborted = threading.Event()

        class AbortSocket:
            def shutdown(self, how):
                aborted.set()

            def close(self):
                aborted.set()

        class BlockedConnection:
            socket = AbortSocket()

            def __init__(self):
                self.responses = iter([{"type": "auth_required"}, {"type": "auth_ok"}])
                self.receives = 0

            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.socket.close()

            def recv(self, timeout):
                self.receives += 1
                return json.dumps(next(self.responses))

            def send(self, message):
                if json.loads(message).get("type") != "auth":
                    if not aborted.wait(1.5):
                        raise AssertionError("The send deadline did not interrupt the blocked operation")
                    raise OSError("mock send interrupted")

        connection = BlockedConnection()
        client = WSClient(self.origin, TOKEN, 0.1)
        with patch("ha_ws_read.transport", return_value=lambda *args, **kwargs: connection):
            start = time.monotonic()
            with self.assertRaisesRegex(HAError, "deadline exceeded"):
                client.read("config")
        self.assertEqual(connection.receives, 2)
        self.assertTrue(aborted.is_set())
        self.assertLess(time.monotonic() - start, 1)

    def test_stalled_peer_large_query_has_an_exchange_deadline(self):
        stalled = threading.Event()
        release = threading.Event()

        class StallHandler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def do_GET(self):
                self.connection.setsockopt(socket_module.SOL_SOCKET, socket_module.SO_RCVBUF, 4096)
                key = self.headers["Sec-WebSocket-Key"]
                accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
                self.send_response(101)
                self.send_header("Upgrade", "websocket")
                self.send_header("Connection", "Upgrade")
                self.send_header("Sec-WebSocket-Accept", accept)
                self.end_headers()
                self.close_connection = True

                def send_frame(value):
                    payload = json.dumps(value).encode()
                    self.wfile.write(bytes([0x81, len(payload)]) + payload)
                    self.wfile.flush()

                send_frame({"type": "auth_required", "ha_version": "2026.10.1"})
                header = self.rfile.read(2)
                if len(header) != 2:
                    return
                size = header[1] & 0x7F
                if size == 126:
                    size = int.from_bytes(self.rfile.read(2), "big")
                mask = self.rfile.read(4)
                frame = self.rfile.read(size)
                auth = json.loads(bytes(value ^ mask[i % 4] for i, value in enumerate(frame)))
                if auth.get("access_token") != TOKEN:
                    return
                send_frame({"type": "auth_ok", "ha_version": "2026.10.1"})
                stalled.set()
                # Deliberately never consume the following WebSocket frame.
                release.wait(4)

        server = ThreadingHTTPServer(("127.0.0.1", 0), StallHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = WSClient(f"http://127.0.0.1:{server.server_port}", TOKEN, 0.4)
            config = {"actions": [{"delay": "x" * (7 * 1024 * 1024)}]}
            connect = transport()

            def bounded_buffer_connect(*args, **kwargs):
                connection = connect(*args, **kwargs)
                connection.socket.setsockopt(socket_module.SOL_SOCKET, socket_module.SO_SNDBUF, 4096)
                return connection

            start = time.monotonic()
            with patch("ha_ws_read.transport", return_value=bounded_buffer_connect), self.assertRaises(HAError):
                client.validate_config(config)
            self.assertTrue(stalled.is_set())
            self.assertLess(time.monotonic() - start, 2.5)
        finally:
            release.set()
            server.shutdown()
            server.server_close()
            thread.join()

    def test_cli_reads_and_redacts_successful_echo(self):
        self.__class__.result["result"] = {"message": TOKEN}
        with patch.dict(os.environ, {"HA_URL": self.origin, "HA_TOKEN": TOKEN}), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["read", "assist-pipelines"]), 0)
        self.assertNotIn(TOKEN, output.getvalue())
        self.assertEqual(json.loads(output.getvalue())["result"], {"message": "[REDACTED]"})


if __name__ == "__main__":
    unittest.main()
