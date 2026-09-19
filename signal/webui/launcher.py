"""Keep the upstream entrypoint intact; stop the container if either service dies."""

import os
import signal
import subprocess
import sys
import time
from contextlib import suppress


def main():
    stopping = False
    children = []

    def stop(_signum, _frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    code = 1
    try:
        children.append(subprocess.Popen(["/entrypoint.sh"], start_new_session=True))
        # The UI has no reason to read Signal keys, options.json, or HA tokens.
        children.append(
            subprocess.Popen(
                [sys.executable, "/opt/signal-webui/server.py"],
                user=65534,
                group=65534,
                extra_groups=[],
                start_new_session=True,
                env={
                    "PATH": "/usr/bin:/bin",
                    "LANG": "C.UTF-8",
                    "PYTHONDONTWRITEBYTECODE": "1",
                },
            )
        )
        while not stopping and all(p.poll() is None for p in children):
            time.sleep(0.2)
        code = 0 if stopping else 1
    finally:
        for process in children:
            if process.poll() is None:
                with suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGTERM)
        # Upstream's JSON-RPC supervisor daemon starts its own session.
        if os.environ.get("MODE") in ("json-rpc", "json-rpc-native"):
            try:
                subprocess.run(
                    ["supervisorctl", "shutdown"],
                    timeout=8,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                pass
        for process in children:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                with suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait()
    return code


if __name__ == "__main__":
    sys.exit(main())
