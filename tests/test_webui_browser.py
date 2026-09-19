"""Real browser, fake loopback backend and ingress prefix; no Signal traffic."""

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from test_webui import ACCOUNT, GROUP, LocalServer, running_server, web

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

PREFIX = "/api/hassio_ingress/test-token"


class PrefixHandler(web.Handler):
    def do_GET(self):
        self.path = self.path.removeprefix(PREFIX)
        self.headers["X-Ingress-Path"] = PREFIX
        super().do_GET()

    def do_POST(self):
        self.path = self.path.removeprefix(PREFIX)
        super().do_POST()


class BrowserServer(LocalServer):
    def finish_request(self, request, client_address):
        PrefixHandler(request, client_address, self)


@unittest.skipUnless(
    sync_playwright, "Install playwright and chromium for browser tests"
)
class BrowserTests(unittest.TestCase):
    def test_workflows_themes_mobile_and_no_external_requests(self):
        calls = []
        fail_send = False

        def backend(method, path, data):
            calls.append((method, path, data))
            if path == "/v1/about":
                return {"mode": "json-rpc", "version": "0.100"}
            if path == "/v1/accounts":
                return [ACCOUNT]
            if path.startswith("/v1/qrcodelink/raw"):
                return {
                    "device_link_uri": "sgnl://linkdevice?uuid=example&pub_key=example"
                }
            if path == "/v2/send":
                if fail_send:
                    raise web.BackendError("Uncertain send; check before retrying")
                return {"timestamp": "1789123456789"}
            group = {
                "id": GROUP,
                "name": "Family <script>window.pwned=true</script>",
                "members": [ACCOUNT],
                "admins": [ACCOUNT],
                "description": "Home",
                "pending_invites": [],
                "pending_requests": [],
            }
            if method == "GET":
                if path == "/v1/groups/%2B12025550101":
                    return [group]
                if "/groups/" in path:
                    return group
                if "/devices/" in path:
                    return [{"id": 2, "name": "Home Assistant"}]
                return []
            return {"ok": True}

        with (
            patch.object(web, "upstream", side_effect=backend),
            running_server(BrowserServer) as server,
            sync_playwright() as playwright,
        ):
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.set_default_timeout(7000)
            errors, urls = [], []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("request", lambda req: urls.append(req.url))
            origin = f"http://127.0.0.1:{server.server_port}"
            page.goto(origin + PREFIX + "/")
            page.wait_for_selector("text=Connected")
            self.assertEqual(page.locator("html").get_attribute("data-theme"), "dark")
            page.get_by_role("button", name="Switch to light theme", exact=True).click()
            self.assertEqual(page.locator("html").get_attribute("data-theme"), "light")
            page.reload()
            page.wait_for_selector("text=Connected")
            self.assertEqual(page.locator("html").get_attribute("data-theme"), "light")
            page.get_by_role("button", name="Switch to dark theme", exact=True).click()

            page.get_by_role("link", name="Test messages", exact=True).click()
            send = page.locator("section").filter(
                has=page.get_by_role("heading", name="Send test message", exact=True)
            )
            send.get_by_label("Recipient number").fill("+12025550102")
            send.get_by_label("Message", exact=True).fill(
                "Hello <script>alert(1)</script>"
            )
            send.get_by_role("button", name="Send test message", exact=True).click()
            page.get_by_role("button", name="Cancel", exact=True).click()
            self.assertFalse(any(path == "/v2/send" for _, path, _ in calls))
            send.get_by_role("button", name="Send test message", exact=True).click()
            page.get_by_role("button", name="Confirm", exact=True).click()
            send.get_by_text("1789123456789", exact=True).wait_for()
            sent = [data for _, path, data in calls if path == "/v2/send"]
            self.assertEqual(len(sent), 1)
            self.assertEqual(sent[0]["message"], "Hello <script>alert(1)</script>")
            fail_send = True
            send.get_by_label("Recipient number").fill("+12025550102")
            send.get_by_label("Message", exact=True).fill("uncertain")
            send.get_by_role("button", name="Send test message", exact=True).click()
            page.get_by_role("button", name="Confirm", exact=True).click()
            send.get_by_text(
                "Uncertain send; check before retrying", exact=True
            ).wait_for()
            self.assertEqual(len([1 for _, path, _ in calls if path == "/v2/send"]), 2)

            page.get_by_role("link", name="Groups", exact=True).click()
            page.get_by_label("Select group").select_option(GROUP)
            update = (
                page.locator("section")
                .filter(
                    has=page.get_by_role("heading", name="Update group", exact=True)
                )
                .last
            )
            update.get_by_label("Group name", exact=True).fill("New family name")
            update.get_by_role("button", name="Update group", exact=True).click()
            page.get_by_role("button", name="Confirm", exact=True).click()
            update.get_by_text("Backend accepted the request.", exact=False).wait_for()
            self.assertIn(
                (
                    "PUT",
                    "/v1/groups/%2B12025550101/" + GROUP.replace("=", "%3D"),
                    {"name": "New family name"},
                ),
                calls,
            )
            self.assertIsNone(page.evaluate("window.pwned"))

            page.get_by_role("link", name="Link an account", exact=True).click()
            page.get_by_role("button", name="Generate QR code", exact=True).click()
            page.get_by_role("button", name="Confirm", exact=True).click()
            page.get_by_alt_text("Signal device linking QR code").wait_for()
            page.wait_for_function("document.querySelector('.qr').naturalWidth > 0")
            page.get_by_role("button", name="I scanned it — refresh accounts").click()

            for name in (
                "Contacts",
                "Account & devices",
                "Identity & security",
                "Overview",
            ):
                page.get_by_role("link", name=name, exact=True).click()
                page.wait_for_function(
                    "document.querySelector('#main').getAttribute('aria-busy') === 'false'"
                )
            screenshot = os.environ.get("SIGNAL_UI_SCREENSHOT")
            page.locator("#notice").evaluate("node => node.hidden = true")
            if screenshot:
                page.screenshot(
                    path=str(Path(screenshot).with_name("desktop.png")), full_page=True
                )
            page.set_viewport_size({"width": 390, "height": 844})
            self.assertTrue(
                page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            )
            if screenshot:
                page.screenshot(path=screenshot, full_page=True)
            # Ingress can open the document without a trailing slash, too.
            page.goto(origin + PREFIX)
            page.wait_for_selector("text=Connected")
            self.assertFalse(errors, errors)
            self.assertTrue(
                all(url.startswith((origin + PREFIX, "data:")) for url in urls),
                urls,
            )
            self.assertFalse(any("/receive/" in path for _, path, _ in calls))
            browser.close()


if __name__ == "__main__":
    unittest.main()
