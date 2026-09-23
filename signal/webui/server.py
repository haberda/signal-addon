"""Ingress-only UI and explicit, validated operations against the loopback API.

No generic proxy, CLI execution, receive consumer, or filesystem API is exposed.
Contracts: signal-cli-rest-api 0.100 / signal-cli 0.14.5.
"""

import base64
import hashlib
import io
import json
import re
import secrets
import threading
import time
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

UPSTREAM = "http://127.0.0.1:8080"
INGRESS_PEER = "172.30.32.2"
MAX_BODY = 3 * 1024 * 1024
MAX_RESPONSE = 4 * 1024 * 1024
STATIC = Path(__file__).parent / "static"


class Invalid(ValueError):
    pass


def string(value, maximum=4096, required=True):
    if not isinstance(value, str) or len(value) > maximum:
        raise Invalid("Invalid text field or field too long")
    if required and not value.strip():
        raise Invalid("A required field is empty")
    if any(ord(c) < 32 and c not in "\n\r\t" for c in value):
        raise Invalid("Control characters are not allowed")
    return value


def segment(value):
    value = string(value, 512)
    if value in (".", "..") or any(c in value for c in "/\\?#%\r\n\t"):
        raise Invalid("Invalid identifier")
    return quote(value, safe="")


def validate(value, kind):
    if isinstance(kind, tuple):
        if value not in kind or not isinstance(value, str):
            raise Invalid("Invalid selection")
        return value
    if kind == "bool":
        if type(value) is not bool:
            raise Invalid("Expected a boolean")
    elif kind == "int":
        if type(value) is not int or not 0 <= value <= 9007199254740991:
            raise Invalid("Expected a non-negative integer")
    elif kind == "list":
        if not isinstance(value, list) or not 1 <= len(value) <= 100:
            raise Invalid("Provide between 1 and 100 entries")
        value = [string(item, 512) for item in value]
    elif kind == "image":
        value = string(value, MAX_BODY)
        if not re.fullmatch(
            r"data:image/(?:png|jpeg|webp);base64,[A-Za-z0-9+/=]+", value
        ):
            raise Invalid("Use a PNG, JPEG, or WebP image")
        validate_base64(value)
        value = value.split(",", 1)[
            1
        ]  # Avatar endpoints require raw base64, not a data URI.
    elif kind == "attachments":
        if not isinstance(value, list) or len(value) != 1:
            raise Invalid("One attachment per test message is supported")
        for item in value:
            string(item, MAX_BODY)
            if not re.fullmatch(r"data:[\w.+-]+/[\w.+-]+;base64,[A-Za-z0-9+/=]+", item):
                raise Invalid("Invalid attachment")
            validate_base64(item)
    elif kind == "permissions":
        value = fields(
            value,
            {
                key: ("every-member", "only-admins")
                for key in ("add_members", "edit_group", "send_messages")
            },
        )
    else:
        value = string(value, 10000, required=kind != "optional_text")
    return value


def validate_base64(value):
    try:
        decoded = base64.b64decode(value.split(",", 1)[1], validate=True)
    except ValueError as err:
        raise Invalid("Invalid attachment encoding") from err
    if not 0 < len(decoded) <= 2 * 1024 * 1024:
        raise Invalid("Files must be nonempty and at most 2 MiB")


def fields(data, schema, required=()):
    if not isinstance(data, dict) or set(data) - set(schema):
        raise Invalid("Unexpected request fields")
    if set(required) - set(data):
        raise Invalid("Missing required fields")
    return {key: validate(value, schema[key]) for key, value in data.items()}


GROUP = {
    "name": "text",
    "description": "optional_text",
    "expiration_time": "int",
    "group_link": ("disabled", "enabled", "enabled-with-approval"),
    "permissions": "permissions",
}

# action: method, fixed route, payload schema, required fields
ROUTES = {
    "about": ("GET", "/v1/about", {}, ()),
    "accounts": ("GET", "/v1/accounts", {}, ()),
    "groups": ("GET", "/v1/groups/{account}", {}, ()),
    "group": ("GET", "/v1/groups/{account}/{group}", {}, ()),
    "contacts": ("GET", "/v1/contacts/{account}", {}, ()),
    "devices": ("GET", "/v1/devices/{account}", {}, ()),
    "identities": ("GET", "/v1/identities/{account}", {}, ()),
    "register": (
        "POST",
        "/v1/register/{account}",
        {"use_voice": "bool", "captcha": "text"},
        (),
    ),
    "verify": ("POST", "/v1/register/{account}/verify/{code}", {"pin": "text"}, ()),
    "send": (
        "POST",
        "/v2/send",
        {
            "recipients": "list",
            "message": "optional_text",
            "text_mode": ("normal", "styled"),
            "base64_attachments": "attachments",
            "edit_timestamp": "int",
            "quote_timestamp": "int",
            "quote_author": "text",
            "quote_message": "optional_text",
        },
        ("recipients", "message"),
    ),
    "delete_message": (
        "DELETE",
        "/v1/remote-delete/{account}",
        {"recipient": "text", "timestamp": "int"},
        ("recipient", "timestamp"),
    ),
    "create_group": (
        "POST",
        "/v1/groups/{account}",
        {**GROUP, "members": "list"},
        ("name", "members"),
    ),
    "update_group": (
        "PUT",
        "/v1/groups/{account}/{group}",
        {**GROUP, "base64_avatar": "image"},
        (),
    ),
    "add_members": (
        "POST",
        "/v1/groups/{account}/{group}/members",
        {"members": "list"},
        ("members",),
    ),
    "remove_members": (
        "DELETE",
        "/v1/groups/{account}/{group}/members",
        {"members": "list"},
        ("members",),
    ),
    "add_admins": (
        "POST",
        "/v1/groups/{account}/{group}/admins",
        {"admins": "list"},
        ("admins",),
    ),
    "remove_admins": (
        "DELETE",
        "/v1/groups/{account}/{group}/admins",
        {"admins": "list"},
        ("admins",),
    ),
    "leave_group": ("DELETE", "/v1/groups/{account}/{group}", {}, ()),
    "block_group": ("POST", "/v1/groups/{account}/{group}/block", {}, ()),
    "accept_invite": ("POST", "/v1/groups/{account}/{group}/join", {}, ()),
    "profile": (
        "PUT",
        "/v1/profiles/{account}",
        {
            "name": "text",
            "about": "optional_text",
            "base64_avatar": "image",
            "remove_avatar": "bool",
        },
        ("name",),
    ),
    "privacy": (
        "PUT",
        "/v1/accounts/{account}/settings",
        {"discoverable_by_number": "bool", "share_number": "bool"},
        (),
    ),
    "username": (
        "POST",
        "/v1/accounts/{account}/username",
        {"username": "text"},
        ("username",),
    ),
    "remove_username": ("DELETE", "/v1/accounts/{account}/username", {}, ()),
    "pin": ("POST", "/v1/accounts/{account}/pin", {"pin": "text"}, ("pin",)),
    "remove_pin": ("DELETE", "/v1/accounts/{account}/pin", {}, ()),
    "contact": (
        "PUT",
        "/v1/contacts/{account}",
        {"recipient": "text", "name": "optional_text", "expiration_in_seconds": "int"},
        ("recipient",),
    ),
    "sync_contacts": ("POST", "/v1/contacts/{account}/sync", {}, ()),
    "add_device": ("POST", "/v1/devices/{account}", {"uri": "text"}, ("uri",)),
    "remove_device": ("DELETE", "/v1/devices/{account}/{device}", {}, ()),
    "trust": (
        "PUT",
        "/v1/identities/{account}/trust/{recipient}",
        {"verified_safety_number": "text"},
        ("verified_safety_number",),
    ),
    "challenge": (
        "POST",
        "/v1/accounts/{account}/rate-limit-challenge",
        {"challenge_token": "text", "captcha": "text"},
        ("challenge_token", "captcha"),
    ),
    "poll": (
        "POST",
        "/v1/polls/{account}",
        {
            "recipient": "text",
            "question": "text",
            "answers": "list",
            "allow_multiple_selections": "bool",
        },
        ("recipient", "question", "answers"),
    ),
    "close_poll": (
        "DELETE",
        "/v1/polls/{account}",
        {"recipient": "text", "poll_timestamp": "text"},
        ("recipient", "poll_timestamp"),
    ),
    "react": (
        "POST",
        "/v1/reactions/{account}",
        {
            "recipient": "text",
            "reaction": "text",
            "target_author": "text",
            "timestamp": "int",
        },
        ("recipient", "reaction", "target_author", "timestamp"),
    ),
    "remove_reaction": (
        "DELETE",
        "/v1/reactions/{account}",
        {"recipient": "text", "target_author": "text", "timestamp": "int"},
        ("recipient", "target_author", "timestamp"),
    ),
}


def prepare(request):
    if not isinstance(request, dict) or set(request) - {
        "action",
        "params",
        "data",
        "confirmed",
        "request_id",
    }:
        raise Invalid("Invalid request")
    action = request.get("action")
    if not isinstance(action, str):
        raise Invalid("Invalid action")
    if action == "link":
        method, route, schema, required = (
            "GET",
            "/v1/qrcodelink/raw",
            {"device_name": "text"},
            ("device_name",),
        )
    elif action in ROUTES:
        method, route, schema, required = ROUTES[action]
    else:
        raise Invalid("Unsupported action")
    mutation = method != "GET" or action == "link"
    if mutation and request.get("confirmed") is not True:
        raise Invalid("Confirm this operation before submitting")
    params = request.get("params", {})
    expected = set(re.findall(r"\{(\w+)\}", route))
    if action == "send":
        expected.add("account")
    if not isinstance(params, dict) or set(params) != expected:
        raise Invalid("Invalid operation identifiers")
    safe = {key: segment(value) for key, value in params.items()}
    if "account" in params and not re.fullmatch(
        r"\+[1-9][0-9]{3,14}", params["account"]
    ):
        raise Invalid("Use an international account number, such as +XXXXXXXXXXX")
    if "group" in params and not params["group"].startswith("group."):
        raise Invalid("Select a REST group ID (group.…)")
    if "device" in params and (
        not params["device"].isdigit() or int(params["device"]) <= 1
    ):
        raise Invalid("The primary device cannot be removed here")
    data = fields(request.get("data", {}), schema, required)
    if action == "link":
        route += "?" + urlencode(data)
        data = None
    if action == "send":
        if len(data["recipients"]) != 1:
            raise Invalid("Test sending supports one destination per request")
        if not data["message"].strip() and not data.get("base64_attachments"):
            raise Invalid("Provide a message or attachment")
        if ("quote_timestamp" in data) != ("quote_author" in data):
            raise Invalid("A quoted reply needs both author and timestamp")
        data.update(number=params["account"], notify_self=True)
    if action == "trust":
        data["verified_safety_number"] = re.sub(
            r"\s", "", data["verified_safety_number"]
        )
        if not re.fullmatch(r"[0-9]{60}", data["verified_safety_number"]):
            raise Invalid("Enter the verified 60-digit safety number")
    if action == "profile":
        remove = data.pop("remove_avatar", False)
        if "base64_avatar" not in data and not remove:
            raise Invalid(
                "Upstream removes the avatar when none is supplied. Upload an avatar or explicitly approve its removal."
            )
        if "base64_avatar" in data and remove:
            raise Invalid("Choose either an avatar upload or removal, not both")
    if action in ("update_group", "privacy") and not data:
        raise Invalid("Choose at least one setting to change")
    if action == "poll" and not 2 <= len(data["answers"]) <= 10:
        raise Invalid("Provide 2–10 poll answers")
    if action == "add_device" and not data["uri"].startswith("sgnl://linkdevice?"):
        raise Invalid("Enter a Signal device provisioning URI")
    return (
        action,
        method,
        route.format(**safe),
        data if method != "GET" else None,
        mutation,
    )


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class BackendError(Exception):
    pass


def upstream(method, path, data):
    opener = build_opener(ProxyHandler({}), NoRedirect())
    req = Request(
        UPSTREAM + path,
        method=method,
        data=None if data is None else json.dumps(data).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with opener.open(req, timeout=90) as response:
            raw = response.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                raise BackendError(
                    "Backend response too large; check backend state before repeating an operation"
                )
            return json.loads(raw) if raw else {"ok": True}
    except HTTPError as err:
        try:
            raw = err.read(8192)
        finally:
            err.close()
        try:
            detail = str(json.loads(raw).get("error", "Request rejected"))[:2000]
        except (ValueError, AttributeError):
            detail = "Request rejected"
        raise BackendError(
            f"Backend HTTP {err.code}: {detail}. Check backend state before repeating an operation."
        ) from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise BackendError(
            "Backend unavailable or invalid response. A send or change may already have succeeded; check before retrying."
        ) from None


class Gateway:
    def __init__(self):
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.Lock()
        self.completed = OrderedDict()

    def execute(self, request):
        action, method, path, data, mutation = prepare(request)
        request_id = request.get("request_id", "")
        if mutation and (
            not isinstance(request_id, str)
            or not re.fullmatch(r"[a-zA-Z0-9-]{16,80}", request_id)
        ):
            raise Invalid("Missing operation ID")
        digest = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).digest()
        # Serialize UI requests; this does not lock out the external integration.
        if not self.lock.acquire(timeout=1):
            return 409, {
                "error": "Another UI operation is running. Wait for it to finish."
            }
        try:
            now = time.monotonic()
            self.completed = OrderedDict(
                (key, value)
                for key, value in self.completed.items()
                if now - value[0] < 300
            )
            if mutation and request_id in self.completed:
                _, previous, result = self.completed[request_id]
                if previous != digest:
                    raise Invalid("Operation ID already used")
                return result
            try:
                # 0.100 drops a zero timer from its JSON-RPC updateGroup payload.
                if action == "update_group" and data.get("expiration_time") == 0:
                    about = upstream("GET", "/v1/about", None)
                    if about.get("mode") in ("json-rpc", "json-rpc-native"):
                        raise BackendError(
                            "Upstream 0.100 cannot reliably disable group timers in JSON-RPC mode. Use your Signal phone or temporarily switch to normal/native mode."
                        )
                result = upstream(method, path, data)
                if action == "link":
                    import qrcode

                    uri = result.get("device_link_uri", "")
                    if (
                        not isinstance(uri, str)
                        or not uri.startswith("sgnl://linkdevice?")
                        or len(uri) > 4096
                    ):
                        raise BackendError("Backend returned an invalid linking URI")
                    output = io.BytesIO()
                    qrcode.make(uri).save(output, format="PNG")
                    result = {
                        "qr": base64.b64encode(output.getvalue()).decode(),
                        "expires_in": 300,
                    }
                result = (200, {"result": result})
            except BackendError as err:
                result = (502, {"error": str(err)})
            if mutation:
                self.completed[request_id] = (now, digest, result)
                while len(self.completed) > 64:
                    self.completed.popitem(last=False)
            return result
        finally:
            self.lock.release()


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, *_args):
        pass  # Never put request URLs, identifiers, PINs, or messages in UI logs.

    def respond(self, status, body, content_type="application/json"):
        if content_type == "application/json":
            body = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'",
        )
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path or "/"
        if path == "/session":
            self.respond(200, {"token": self.server.gateway.token})
            return
        assets = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/app.js": ("app.js", "text/javascript; charset=utf-8"),
            "/style.css": ("style.css", "text/css; charset=utf-8"),
        }
        if path not in assets:
            self.respond(404, {"error": "Not found"})
            return
        name, content_type = assets[path]
        body = (STATIC / name).read_bytes()
        prefix = self.headers.get("X-Ingress-Path", "").rstrip("/")
        if name == "index.html" and prefix:
            if not re.fullmatch(r"/[A-Za-z0-9_/-]+", prefix) or "//" in prefix:
                self.respond(400, {"error": "Invalid ingress path"})
                return
            body = body.replace(b'"./', ('"' + prefix + "/").encode())
        self.respond(200, body, content_type)

    def do_POST(self):
        if self.path != "/api/action":
            self.respond(404, {"error": "Not found"})
            return
        if self.headers.get(
            "Sec-Fetch-Site"
        ) == "cross-site" or not secrets.compare_digest(
            self.headers.get("X-Signal-CSRF", "").encode(),
            self.server.gateway.token.encode(),
        ):
            self.respond(
                403,
                {
                    "error": "Invalid session. Reload this page through Home Assistant ingress."
                },
            )
            return
        try:
            if self.headers.get(
                "Content-Type"
            ) != "application/json" or self.headers.get("Transfer-Encoding"):
                raise Invalid("Expected a JSON body")
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                self.respond(413, {"error": "Request too large or empty"})
                return
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise Invalid("Incomplete request")
            status, body = self.server.gateway.execute(json.loads(raw))
        except Invalid as err:
            self.respond(400, {"error": str(err)})
            return
        except (ValueError, TypeError, RecursionError):
            self.respond(
                400,
                {
                    "error": "Invalid request. Check required fields, identifiers, and file limits."
                },
            )
            return
        except OSError:
            return
        self.respond(status, body)


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address):
        self.gateway = Gateway()
        self.slots = threading.BoundedSemaphore(8)
        super().__init__(address, Handler)

    def verify_request(self, request, address):
        # Do not trust X-Forwarded-For or another client-supplied header.
        return address[0] == INGRESS_PEER

    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()

    def handle_error(self, request, address):
        pass  # Do not log request context or backend data on disconnect.


if __name__ == "__main__":
    Server(("0.0.0.0", 8099)).serve_forever()
