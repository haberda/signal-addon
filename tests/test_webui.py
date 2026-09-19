"""Offline contract/security tests. Never connect to a real Signal account."""

import base64
import http.client
import importlib.util
import json
import threading
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "signal_webui", ROOT / "signal/webui/server.py"
)
web = importlib.util.module_from_spec(spec)
spec.loader.exec_module(web)
ACCOUNT = "+12025550101"
GROUP = "group.YWJjZA=="
PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a3ioAAAAASUVORK5CYII="


def request(action="send", data=None, params=None, **extra):
    return {
        "action": action,
        "params": {"account": ACCOUNT} if params is None else params,
        "data": {"recipients": [ACCOUNT], "message": "Test"} if data is None else data,
        "confirmed": True,
        "request_id": "12345678-1234-1234-1234-123456789012",
        **extra,
    }


class ContractTests(unittest.TestCase):
    def test_every_route_has_a_valid_contract(self):
        examples = {
            "text": "example",
            "optional_text": "",
            "bool": False,
            "int": 100,
            "list": [ACCOUNT],
            "image": "data:image/png;base64," + PNG,
            "permissions": {"edit_group": "only-admins"},
        }
        for action, (_, route, schema, required) in web.ROUTES.items():
            with self.subTest(action=action):
                params = {
                    key: {
                        "account": ACCOUNT,
                        "group": GROUP,
                        "device": "2",
                        "code": "123456",
                        "recipient": ACCOUNT,
                    }[key]
                    for key in web.re.findall(r"\{(\w+)\}", route)
                }
                if action == "send":
                    params["account"] = ACCOUNT
                data = {
                    key: (
                        schema[key][0]
                        if isinstance(schema[key], tuple)
                        else examples[schema[key]]
                    )
                    for key in required
                }
                if action == "poll":
                    data["answers"] = ["one", "two"]
                if action == "send":
                    data["message"] = "test"
                if action == "trust":
                    data["verified_safety_number"] = "1" * 60
                if action == "add_device":
                    data["uri"] = "sgnl://linkdevice?uuid=example&pub_key=example"
                if action == "profile":
                    data["remove_avatar"] = True
                if action == "update_group":
                    data["name"] = "new name"
                if action == "privacy":
                    data["share_number"] = False
                method = web.prepare(request(action, data, params))[1]
                self.assertEqual(method, web.ROUTES[action][0])

    def test_no_receive_or_arbitrary_proxy(self):
        for action in (
            "receive",
            "exec",
            "unregister",
            "delete_local_data",
            "http://example.com",
        ):
            with self.subTest(action=action), self.assertRaises(web.Invalid):
                web.prepare(request(action))

    def test_paths_and_unknown_fields_rejected(self):
        for value in ("../accounts", "%2faccounts", "a/b", "x?y", "x#y", "a\\b"):
            with self.subTest(value=value), self.assertRaises(web.Invalid):
                web.prepare(request("group", {}, {"account": ACCOUNT, "group": value}))
        with self.assertRaises(web.Invalid):
            web.prepare(
                request(
                    data={
                        "message": "test",
                        "recipients": [ACCOUNT],
                        "number": "+19999999999",
                    }
                )
            )
        with self.assertRaises(web.Invalid):
            web.prepare(request(confirmed=False))
        with self.assertRaises(web.Invalid):
            web.prepare(
                request("remove_device", {}, {"account": ACCOUNT, "device": "1"})
            )

    def test_send_is_one_destination_and_account_is_server_assigned(self):
        _, method, route, data, _ = web.prepare(request())
        self.assertEqual((method, route), ("POST", "/v2/send"))
        self.assertEqual(data["number"], ACCOUNT)
        self.assertTrue(data["notify_self"])
        with self.assertRaises(web.Invalid):
            web.prepare(
                request(
                    data={"recipients": [ACCOUNT, "+12025550102"], "message": "test"}
                )
            )
        with self.assertRaises(web.Invalid):
            web.prepare(
                request(
                    data={
                        "recipients": [ACCOUNT],
                        "message": "test",
                        "quote_timestamp": 100,
                    }
                )
            )

    def test_profile_never_silently_removes_avatar(self):
        with self.assertRaises(web.Invalid):
            web.prepare(request("profile", {"name": "Alice"}))
        data = web.prepare(
            request("profile", {"name": "Alice", "remove_avatar": True})
        )[3]
        self.assertEqual(data, {"name": "Alice"})
        data = web.prepare(
            request(
                "profile",
                {"name": "Alice", "base64_avatar": "data:image/png;base64," + PNG},
            )
        )[3]
        self.assertEqual(data["base64_avatar"], PNG)
        with self.assertRaises(web.Invalid):
            web.prepare(
                request(
                    "profile",
                    {
                        "name": "Alice",
                        "remove_avatar": True,
                        "base64_avatar": "data:image/png;base64," + PNG,
                    },
                )
            )

    def test_validation_preserves_false_and_zero(self):
        self.assertEqual(
            web.prepare(request("privacy", {"share_number": False}))[3],
            {"share_number": False},
        )
        self.assertEqual(
            web.prepare(
                request(
                    "update_group",
                    {"expiration_time": 0},
                    {"account": ACCOUNT, "group": GROUP},
                )
            )[3],
            {"expiration_time": 0},
        )
        for data in ({"share_number": "false"}, {"unknown": True}):
            with self.assertRaises(web.Invalid):
                web.prepare(request("privacy", data))
        for value in (-1, True, 1.5, 9007199254740992):
            with self.assertRaises(web.Invalid):
                web.validate(value, "int")

    def test_no_blanket_trust_and_avatar_limits(self):
        with self.assertRaises(web.Invalid):
            web.prepare(
                request(
                    "trust",
                    {"trust_all_known_keys": True},
                    {"account": ACCOUNT, "recipient": ACCOUNT},
                )
            )
        for image in (
            "data:image/svg+xml;base64," + PNG,
            "data:image/png;base64,!!!",
            "data:image/png;base64,"
            + base64.b64encode(b"a" * (2 * 1024 * 1024 + 1)).decode(),
        ):
            with self.assertRaises(web.Invalid):
                web.validate(image, "image")

    def test_mutation_deduplication_including_uncertain_errors(self):
        gateway = web.Gateway()
        with patch.object(
            web, "upstream", return_value={"timestamp": "123"}
        ) as upstream:
            self.assertEqual(gateway.execute(request()), gateway.execute(request()))
            upstream.assert_called_once()
            with self.assertRaises(web.Invalid):
                gateway.execute(
                    request(data={"recipients": [ACCOUNT], "message": "Changed"})
                )
        gateway = web.Gateway()
        with patch.object(
            web, "upstream", side_effect=web.BackendError("uncertain")
        ) as upstream:
            self.assertEqual(gateway.execute(request())[0], 502)
            self.assertEqual(gateway.execute(request())[0], 502)
            upstream.assert_called_once()

    def test_group_zero_timer_rpc_guard(self):
        gateway = web.Gateway()
        with patch.object(
            web, "upstream", return_value={"mode": "json-rpc"}
        ) as upstream:
            status, body = gateway.execute(
                request(
                    "update_group",
                    {"expiration_time": 0},
                    {"account": ACCOUNT, "group": GROUP},
                )
            )
            self.assertEqual(status, 502)
            self.assertIn("group timers", body["error"])
            upstream.assert_called_once_with("GET", "/v1/about", None)

    def test_link_qr_is_generated_locally(self):
        with patch.object(
            web,
            "upstream",
            return_value={
                "device_link_uri": "sgnl://linkdevice?uuid=example&pub_key=example"
            },
        ):
            status, body = web.Gateway().execute(
                request("link", {"device_name": "Home Assistant"}, {})
            )
        self.assertEqual(status, 200)
        self.assertTrue(base64.b64decode(body["result"]["qr"]).startswith(b"\x89PNG"))
        self.assertNotIn("device_link_uri", body["result"])


class LocalServer(web.Server):
    """Test-only local ingress substitute; production never accepts loopback UI clients."""

    def verify_request(self, request, address):
        return address[0] == "127.0.0.1"


@contextmanager
def running_server(server_class=LocalServer):
    server = server_class(("127.0.0.1", 0))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


class HTTPTests(unittest.TestCase):
    def test_peer_check_uses_socket_address(self):
        self.assertTrue(web.Server.verify_request(None, None, ("172.30.32.2", 1)))
        for peer in ("127.0.0.1", "172.30.32.3", "192.168.1.2", "::1"):
            self.assertFalse(web.Server.verify_request(None, None, (peer, 1)))

    def test_http_security_and_ingress_assets(self):
        with running_server() as server:

            def call(method, path, body=None, headers=None):
                connection = http.client.HTTPConnection(
                    *server.server_address, timeout=5
                )
                connection.request(method, path, body=body, headers=headers or {})
                response = connection.getresponse()
                result = (response.status, dict(response.getheaders()), response.read())
                connection.close()
                return result

            status, headers, body = call(
                "GET", "/", headers={"X-Ingress-Path": "/api/hassio_ingress/test-token"}
            )
            self.assertEqual(status, 200)
            self.assertIn(b'"/api/hassio_ingress/test-token/app.js"', body)
            self.assertEqual(headers["Cache-Control"], "no-store")
            self.assertIn("frame-ancestors 'self'", headers["Content-Security-Policy"])
            self.assertNotIn("Access-Control-Allow-Origin", headers)
            self.assertEqual(call("GET", "/../server.py")[0], 404)
            self.assertEqual(
                call("GET", "/", headers={"X-Ingress-Path": '/x" onload=evil'})[0], 400
            )
            token = json.loads(call("GET", "/session")[2])["token"]
            payload = json.dumps(request())
            self.assertEqual(
                call(
                    "POST", "/api/action", payload, {"Content-Type": "application/json"}
                )[0],
                403,
            )
            headers = {"Content-Type": "application/json", "X-Signal-CSRF": token}
            self.assertEqual(
                call("POST", "/api/action", payload, {**headers, "X-Signal-CSRF": "é"})[
                    0
                ],
                403,
            )
            self.assertEqual(
                call(
                    "POST",
                    "/api/action",
                    payload,
                    {**headers, "Sec-Fetch-Site": "cross-site"},
                )[0],
                403,
            )
            self.assertEqual(call("POST", "/api/action", "[]", headers)[0], 400)
            self.assertEqual(call("POST", "/api/action", "{", headers)[0], 400)
            self.assertEqual(
                call(
                    "POST",
                    "/api/action",
                    payload,
                    {**headers, "Content-Length": str(web.MAX_BODY + 1)},
                )[0],
                413,
            )
            with patch.object(
                web, "upstream", return_value={"timestamp": "123"}
            ) as upstream:
                self.assertEqual(call("POST", "/api/action", payload, headers)[0], 200)
                upstream.assert_called_once_with(
                    "POST",
                    "/v2/send",
                    {
                        "recipients": [ACCOUNT],
                        "message": "Test",
                        "number": ACCOUNT,
                        "notify_self": True,
                    },
                )

    def test_loopback_requests_are_denied_even_with_spoofed_headers(self):
        with running_server(web.Server) as server:
            conn = http.client.HTTPConnection(*server.server_address, timeout=5)
            conn.request("GET", "/", headers={"X-Forwarded-For": "172.30.32.2"})
            with self.assertRaises(http.client.RemoteDisconnected):
                conn.getresponse()
            conn.close()


class TransportTests(unittest.TestCase):
    def test_fixed_upstream_no_redirects_bounded_and_sanitized_errors(self):
        visited = []

        class Backend(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                visited.append(self.path)
                if self.path == "/redirect":
                    self.send_response(302)
                    self.send_header("Location", "/should-not-follow")
                    self.end_headers()
                    return
                self.send_response(400 if self.path == "/error" else 200)
                self.end_headers()
                bodies = {
                    "/good": b'{"ok": true}',
                    "/invalid": b"not json",
                    "/error": b'{"error": "Unsupported operation"}',
                    "/large": b"x" * 100,
                }
                self.wfile.write(bodies.get(self.path, b""))

        backend = ThreadingHTTPServer(("127.0.0.1", 0), Backend)
        thread = threading.Thread(target=backend.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.object(
                web, "UPSTREAM", f"http://127.0.0.1:{backend.server_port}"
            ):
                self.assertEqual(web.upstream("GET", "/good", None), {"ok": True})
                for path in ("/redirect", "/invalid", "/error"):
                    with self.subTest(path=path), self.assertRaises(web.BackendError):
                        web.upstream("GET", path, None)
                with (
                    patch.object(web, "MAX_RESPONSE", 32),
                    self.assertRaises(web.BackendError),
                ):
                    web.upstream("GET", "/large", None)
                self.assertNotIn("/should-not-follow", visited)
        finally:
            backend.shutdown()
            backend.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
