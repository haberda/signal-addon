# Ingress management UI

## Architecture

Home Assistant ingress forwards to the unpublished port 8099. The Python HTTP service checks the socket peer against `172.30.32.2`, as required by [Home Assistant ingress](https://developers.home-assistant.io/docs/apps/presentation/#ingress); forwarded IP headers are not trusted. Only the upstream REST port 8080 remains in the add-on's published ports.

The browser uses same-origin, ingress-relative URLs. A small gateway maps explicit operations to `http://127.0.0.1:8080`, validates their fields, and does not forward browser authentication headers. There is no generic proxy, CLI runner, filesystem endpoint, receive consumer, CDN, or remotely generated QR image. Static assets use a restrictive CSP. The UI inserts backend data as text, not HTML. Mutations require a CSRF token and confirmation. The gateway remembers duplicate operation IDs for five minutes; restarting clears them. UI request bodies are limited to 3 MiB and backend responses to 4 MiB.

The container's s6 init reads Supervisor's root-readable `/data/options.json` during initialization and prepares the runtime environment. The API and web UI processes run as the rootless upstream `signal-api` UID/GID 1000. The add-on uses the upstream s6 process tree, with an additional s6 longrun service for the web UI. It has no Node runtime or JavaScript build step. No ingress authentication code is added to the upstream REST API.

## Feature review

Reviewed against [signal-cli-rest-api 0.101](https://github.com/bbernhard/signal-cli-rest-api/blob/0.101/src/api/api.go), its [client implementation](https://github.com/bbernhard/signal-cli-rest-api/blob/0.101/src/client/client.go), [signal-cli 0.14.8 commands](https://github.com/AsamK/signal-cli/blob/v0.14.8/man/signal-cli.1.adoc), and the [companion integration](https://github.com/haberda/signal-integration).

| Area                   | Web UI coverage                                                                                                           |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| Onboarding             | Local QR linking; account selection; SMS/voice registration, verification, optional CAPTCHA/PIN                           |
| Groups                 | List/detail, create, settings/avatar/permissions/timer, members/admins, accept own invitation, leave, block               |
| Messages               | Explicit single-destination test send, attachment, quote, edit, remote delete, reactions, create/close poll               |
| Accounts               | Profile/avatar, username, number privacy, PIN, rate-limit challenge                                                       |
| People/devices         | Contacts and timers, contact sync, linked devices, verified identity trust                                                |
| Not exposed by this UI | Incoming inbox, account/data deletion, blanket trust, arbitrary proxy or command execution                                |
| CLI features deferred  | Number changes, arbitrary invite-link joining, group ban/unban/link reset, device rename, contact block/unblock, payments |

The UI adds management features absent from the companion integration while sharing its backend and account storage. It exposes a subset of CLI features and does not emulate unsupported REST operations through direct CLI execution. Configure Assist and Home Assistant automations in the integration.

The UI guards against two upstream edge cases: omitted profile avatars cause deletion, and JSON-RPC group updates omit an expiration value of zero. See the user-facing [limitations](../DOCS.md#scope-and-upstream-limitations).

## Validation

Run offline contract/security and browser tests from the repository root:

```sh
python3 -m venv /tmp/signal-webui-tests
/tmp/signal-webui-tests/bin/pip install -r tests/requirements.txt
/tmp/signal-webui-tests/bin/playwright install chromium
/tmp/signal-webui-tests/bin/python -m unittest discover -s tests -v
```

Browser tests simulate an ingress URL prefix and a local backend using a local-only server subclass; they never call Signal. Production has no localhost bypass for ingress authentication. Set `SIGNAL_UI_SCREENSHOT` to an output path for a mobile screenshot during browser tests. The browser test skips if Playwright is not installed; CI installs it and Chromium explicitly.

Before releasing, test the built container on HAOS on both architectures and all four modes. Confirm ingress works while direct access to port 8099 is denied, the existing integration still connects to 8080, restart/shutdown cleans up all processes, QR linking completes with a test phone, and direct/group sends and mutations work on a disposable account/group. Check primary versus companion-device restrictions and backend/HA disconnects. Mock tests alone cannot verify these behaviors.

## AI assistance

AI was used to maintain and improve the existing add-on. The management web interface described here was generated entirely with AI assistance.
