# Ingress management UI

## Architecture and feasibility

Home Assistant ingress forwards to the unpublished port 8099. The Python HTTP service checks the socket peer against `172.30.32.2`, as required by [Home Assistant ingress](https://developers.home-assistant.io/docs/apps/presentation/#ingress); forwarded IP headers are not trusted. Only the upstream REST port 8080 remains in the add-on's published ports.

The browser uses same-origin, ingress-relative URLs. A small gateway maps explicit operations to `http://127.0.0.1:8080`, validates their fields, and does not forward browser authentication headers. There is no generic proxy, CLI runner, filesystem endpoint, receive consumer, CDN, or remotely generated QR image. Static assets use a restrictive CSP and backend data is inserted as text, not HTML. Mutations require a CSRF token and confirmation; duplicate operation IDs are remembered for five minutes (not durable across restart). UI request bodies are limited to 3 MiB and backend responses to 4 MiB.

The service runs as UID/GID 65534, with supplementary groups cleared and no inherited Home Assistant tokens. It uses Ubuntu's Python and QR/Pillow packages, with no Node runtime or JavaScript build step. The launcher preserves upstream's entrypoint, monitors both services, exits if either dies, and terminates the JSON-RPC supervisor on shutdown. No ingress authentication code is added to the upstream REST API.

## Feature review

Reviewed against [signal-cli-rest-api 0.100](https://github.com/bbernhard/signal-cli-rest-api/blob/0.100/src/api/api.go), its [client implementation](https://github.com/bbernhard/signal-cli-rest-api/blob/0.100/src/client/client.go), [signal-cli 0.14.5 commands](https://github.com/AsamK/signal-cli/blob/v0.14.5/man/signal-cli.1.adoc), and the [companion integration](https://github.com/haberda/signal-integration).

| Area                   | Web UI coverage                                                                                                           |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| Onboarding             | Local QR linking; account selection; SMS/voice registration, verification, optional CAPTCHA/PIN                           |
| Groups                 | List/detail, create, settings/avatar/permissions/timer, members/admins, accept own invitation, leave, block               |
| Messages               | Explicit single-destination test send, attachment, quote, edit, remote delete, reactions, create/close poll               |
| Accounts               | Profile/avatar, username, number privacy, PIN, rate-limit challenge                                                       |
| People/devices         | Contacts and timers, contact sync, linked devices, verified identity trust                                                |
| Not exposed by this UI | Incoming inbox, account/data deletion, blanket trust, arbitrary proxy or command execution                                |
| CLI features deferred  | Number changes, arbitrary invite-link joining, group ban/unban/link reset, device rename, contact block/unblock, payments |

Management features absent from the companion integration can therefore use the same backend without adding a second account-storage owner. Not every CLI command is an appropriate admin UI feature, and unsupported REST operations are not emulated through direct CLI execution. The UI does not configure Assist or Home Assistant automations; those remain in the integration.

Two upstream edge cases are explicitly guarded: omitted profile avatars cause deletion, and JSON-RPC group updates omit an expiration value of zero. See the user-facing [limitations](../DOCS.md#scope-and-upstream-limitations).

## Validation

Run offline contract/security and browser tests from the repository root:

```sh
python3 -m venv /tmp/signal-webui-tests
/tmp/signal-webui-tests/bin/pip install -r tests/requirements.txt
/tmp/signal-webui-tests/bin/playwright install chromium
/tmp/signal-webui-tests/bin/python -m unittest discover -s tests -v
```

Browser tests simulate an ingress URL prefix and a local backend; they never call Signal. Production has no localhost bypass for ingress authentication. Tests supply their own local-only server subclass. Set `SIGNAL_UI_SCREENSHOT` to an output path for a mobile screenshot during browser tests. The browser test skips if Playwright is not installed; CI installs it and Chromium explicitly.

Before releasing, test the built container on HAOS on both architectures and all four modes. Confirm ingress works while direct access to port 8099 is denied, the existing integration still connects to 8080, restart/shutdown cleans up all processes, QR linking completes with a test phone, and direct/group sends and mutations work on a disposable account/group. Check primary versus companion-device restrictions and backend/HA disconnects. This cannot be established by mock tests alone.

## AI assistance

AI was used to maintain and improve the existing add-on. The management web interface described here was generated entirely with AI assistance.
