"""Exercise PID lifecycle decisions without launching real account processes."""

import importlib.util
import signal
import subprocess
import unittest
from unittest.mock import Mock, patch

from test_webui import ROOT

spec = importlib.util.spec_from_file_location(
    "signal_launcher", ROOT / "signal/webui/launcher.py"
)
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class LauncherTests(unittest.TestCase):
    def exercise(self, mode, api_failed=False, ui_hung=False):
        handlers = {}
        api = Mock(pid=101)
        api.poll.return_value = 1 if api_failed else None
        ui = Mock(pid=102)
        ui.poll.return_value = None
        if ui_hung:
            ui.wait.side_effect = [subprocess.TimeoutExpired("ui", 10), 0]

        def stopping(_delay):
            handlers[signal.SIGTERM](signal.SIGTERM, None)

        with (
            patch.object(
                launcher.signal,
                "signal",
                side_effect=lambda sig, fn: handlers.update({sig: fn}),
            ),
            patch.object(launcher.subprocess, "Popen", side_effect=[api, ui]) as popen,
            patch.object(launcher.subprocess, "run") as supervisor,
            patch.object(launcher.os, "killpg") as kill,
            patch.object(launcher.time, "sleep", side_effect=stopping),
            patch.dict(
                launcher.os.environ,
                {"MODE": mode, "SUPERVISOR_TOKEN": "must-not-inherit"},
            ),
        ):
            code = launcher.main()
        self.assertEqual(popen.call_args_list[0].args[0], ["/entrypoint.sh"])
        options = popen.call_args_list[1].kwargs
        self.assertEqual(options["user"], 65534)
        self.assertEqual(options["group"], 65534)
        self.assertEqual(options["extra_groups"], [])
        self.assertNotIn("SUPERVISOR_TOKEN", options["env"])
        self.assertTrue(options["start_new_session"])
        return code, supervisor, kill

    def test_clean_shutdown_in_all_modes(self):
        for mode in ("normal", "native", "json-rpc", "json-rpc-native"):
            with self.subTest(mode=mode):
                code, supervisor, kill = self.exercise(mode)
                self.assertEqual(code, 0)
                self.assertEqual(
                    supervisor.call_count, int(mode.startswith("json-rpc"))
                )
                kill.assert_any_call(101, signal.SIGTERM)
                kill.assert_any_call(102, signal.SIGTERM)

    def test_child_failure_fails_container(self):
        code, _, kill = self.exercise("normal", api_failed=True)
        self.assertEqual(code, 1)
        kill.assert_called_once_with(102, signal.SIGTERM)

    def test_hung_child_is_killed(self):
        code, _, kill = self.exercise("json-rpc", ui_hung=True)
        self.assertEqual(code, 0)
        kill.assert_any_call(102, signal.SIGKILL)

    def test_webui_can_be_disabled(self):
        api = Mock(pid=101)
        api.poll.return_value = None
        handlers = {}

        def stopping(_delay):
            handlers[signal.SIGTERM](signal.SIGTERM, None)

        with patch.object(launcher.signal, "signal", side_effect=lambda sig, fn: handlers.update({sig: fn})), \
             patch.object(launcher.subprocess, "Popen", return_value=api) as popen, \
             patch.object(launcher.time, "sleep", side_effect=stopping), \
             patch.object(launcher.subprocess, "run"), \
             patch.dict(launcher.os.environ, {"WEBUI_ENABLED": "false"}):
            self.assertEqual(launcher.main(), 0)
        self.assertEqual(popen.call_count, 1)
        self.assertEqual(popen.call_args.args[0], ["/entrypoint.sh"])


if __name__ == "__main__":
    unittest.main()
