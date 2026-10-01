"""Unit tests for HsbenchCommand."""

import unittest
from typing import Any

from command.hsbench_command import HsbenchCommand

_FAKE_ENDPOINT: dict[str, Any] = {
    "access_key": "AKIAIOSFODNN7EXAMPLE",
    "secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "url": "http://localhost:8080",
}


def _make_cmd(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    options: dict[str, Any],
    run_dir: str = "/tmp/run",
    ep_num: int = 0,
    endpoint: Any = None,
    prefill: bool = False,
    executable: str = "/usr/local/bin/hsbench",
) -> HsbenchCommand:
    """Helper to build a configured HsbenchCommand instance."""
    endpoint = endpoint or _FAKE_ENDPOINT
    cmd = HsbenchCommand(
        options=options,
        run_dir=run_dir,
        ep_num=ep_num,
        endpoint=endpoint,
        prefill=prefill,
    )
    cmd.set_executable(executable)
    return cmd


class TestHsbenchCommandIsolation(unittest.TestCase):
    """Test HsbenchCommand option parsing and CLI string generation in isolation."""

    def test_benchmark_property(self) -> None:
        """The benchmark property returns 'hsbench'."""
        cmd = _make_cmd({})
        self.assertEqual(cmd.benchmark, "hsbench")

    def test_output_directory(self) -> None:
        """The output directory returns the configured run_dir."""
        cmd = _make_cmd({}, run_dir="/custom/run/dir")
        self.assertEqual(cmd.output_directory, "/custom/run/dir")

    def test_no_executable_returns_empty_string(self) -> None:
        """When executable is not set, get() returns an empty string."""
        cmd = HsbenchCommand(options={}, run_dir="/tmp/run")
        self.assertEqual(cmd.get(), "")

    def test_full_options_command_generation(self) -> None:
        """All options and endpoint credentials are correctly formatted into the CLI command."""
        options = {
            "buckets": 2,
            "bucket_prefix": "testbucket",
            "duration": 60,
            "loop": 3,
            "modes": "cxip",
            "max_keys": 500,
            "objects": 2000,
            "object_prefix": "myobj",
            "per_client_object_prefix": True,
            "region": "us-west-1",
            "report_intervals": 5,
            "threads": 8,
            "size": "64K",
        }
        cmd = _make_cmd(options, ep_num=1)
        cli = cmd.get()

        self.assertTrue(cli.startswith("sudo /usr/local/bin/hsbench"))
        self.assertIn("-b 2", cli)
        self.assertIn("-bp testbucket", cli)
        self.assertIn("-d 60", cli)
        self.assertIn("-l 3", cli)
        self.assertIn("-m cxip", cli)
        self.assertIn("-mk 500", cli)
        self.assertIn("-n 2000", cli)
        self.assertIn("-op myobj-`hostname -f`-1-", cli)
        self.assertIn("-r us-west-1", cli)
        self.assertIn("-ri 5", cli)
        self.assertIn("-t 8", cli)
        self.assertIn("-z 64K", cli)
        self.assertIn("-o /tmp/run/output.1.csv", cli)
        self.assertIn("-j /tmp/run/output.1.json", cli)
        self.assertIn("-s wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY", cli)
        self.assertIn("-a AKIAIOSFODNN7EXAMPLE", cli)
        self.assertIn("-u http://localhost:8080", cli)

    def test_prefill_mode_uses_prefill_modes_and_suffix(self) -> None:
        """Prefill mode uses prefill_modes and adds .prefill to output flags."""
        options = {
            "modes": "rwm",
            "prefill_modes": "cp",
        }
        cmd = _make_cmd(options, prefill=True, ep_num=0)
        cli = cmd.get()

        self.assertIn("-m cp", cli)
        self.assertNotIn("-m rwm", cli)
        self.assertIn("-o /tmp/run/output.0.csv.prefill", cli)
        self.assertIn("-j /tmp/run/output.0.json.prefill", cli)

    def test_prefill_default_modes(self) -> None:
        """Prefill mode defaults to cxip when prefill_modes is unset."""
        cmd = _make_cmd({}, prefill=True)
        cli = cmd.get()
        self.assertIn("-m cxip", cli)

    def test_custom_object_prefix_without_per_client(self) -> None:
        """Static object_prefix is used without hostname when per_client_object_prefix is False."""
        options = {
            "object_prefix": "fixed-prefix",
            "per_client_object_prefix": False,
        }
        cmd = _make_cmd(options)
        cli = cmd.get()
        self.assertIn("-op fixed-prefix", cli)
        self.assertNotIn("`hostname -f`", cli)

    def test_no_object_prefix_with_per_client(self) -> None:
        """Per-client object prefix without base prefix uses hostname and endpoint index."""
        options = {
            "per_client_object_prefix": True,
        }
        cmd = _make_cmd(options, ep_num=2)
        cli = cmd.get()
        self.assertIn("-op `hostname -f`-2-", cli)


if __name__ == "__main__":
    unittest.main()
