# Contributing to signal-addon

## Project overview

This repository contains a Home Assistant add-on that repackages
`bbernhard/signal-cli-rest-api` and adds a Home Assistant ingress web UI.

- `signal/` is the add-on build context.
- `signal/Dockerfile` layers the add-on on the upstream rootless image.
- `signal/config.yaml` defines the Home Assistant add-on metadata, options,
  storage mapping, and ingress settings.
- `signal/options.sh` is an s6 `cont-init.d` script. It reads
  `/data/options.json`, prepares `/config`, and writes the exported runtime
  environment used by the services.
- `signal/s6-services/` contains overrides for the upstream API and JSON-RPC
  services and registers enabled services with s6.
- `signal/webui/` contains the Python ingress gateway and static frontend.
- `tests/` contains API-contract, security, and browser tests for the web UI.

## Runtime architecture

The upstream 0.101 image uses s6-overlay and the unprivileged `signal-api`
user (UID/GID 1000). Keep `/init` as the container PID 1 and keep
`init: false` in `signal/config.yaml`; Home Assistant's Docker init wrapper
must not be inserted in front of s6.

Supervisor's `/data/options.json` is root-readable. The cont-init script runs
as root, applies ownership to the Supervisor-mounted `/config` directory, and
writes `/run/signal-addon/options.env`. API, JSON-RPC, and Web UI run scripts
source that file and use `s6-setuidgid signal-api` for long-running processes.
Do not reintroduce a wrapper that launches `/init` through `setpriv` or another
child process.

The REST API is published on port 8080. The Web UI listens on 8099 and is
available only through Home Assistant ingress; do not publish 8099 externally.
The Web UI service must remain registered in
`signal/s6-services/user/contents.d/` and depend on `legacy-cont-init` so its
options environment exists before it starts.

## Changing options or services

When adding or changing an add-on option:

1. Update `options`, `schema`, and any defaults in `signal/config.yaml`.
2. Parse it in `signal/options.sh` and write it as an exported variable.
3. Preserve explicit boolean `false` values. In jq, avoid using `//` for
   booleans because jq treats `false` as an absent value.
4. Update the relevant service wrapper and documentation.
5. If the option affects the Web UI, confirm both enabled and disabled paths.

Do not store Signal state in `/data`; persistent Signal CLI state belongs in
`/config`, which is mapped as `app_config:rw`.

## Validation

Run focused checks before committing:

```sh
bash -n signal/options.sh
sh -n signal/webui-service/run \
  signal/s6-services/signal-api/run \
  signal/s6-services/signal-json-rpc/run
python3 -m py_compile signal/webui/server.py
node --check signal/webui/static/app.js
git diff --check
```

For the full web UI test suite, install `tests/requirements.txt` in an
isolated virtual environment, install Playwright Chromium, and run:

```sh
python -m unittest discover -s tests -v
```

CI also runs the Home Assistant add-on linter, Hadolint, jq/JSON validation,
ShellCheck, yamllint, Prettier, and architecture-specific Docker builds. A
local change is not complete until its affected checks pass.

## Documentation and commits

Keep the repository `README.md`, `signal/README.md`, `signal/DOCS.md`, and
`signal/webui/README.md` consistent when user-facing behavior changes. Document
security implications, ingress-only access, and rootless ownership changes.

Use focused commit messages in the form `type: short imperative summary`, for
example `fix: preserve explicit false add-on options`. Avoid committing build
artifacts, virtual environments, browser downloads, or local configuration.
