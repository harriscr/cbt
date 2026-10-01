"""
CLI golden tests for Hsbench.run_command().

These tests mock common.pdsh to capture the hsbench command strings and
assert the presence/absence of individual flags across representative
configurations.

Known quirks from existing string-builder (D-series):
  D2a: Per-client object prefix uses backtick shell interpolation
       `hostname -f` for remote client execution.
  D2b: Prefill mode appends '.prefill' to both -o (CSV) and -j (JSON) output
       paths rather than using distinct output files.

"""

# pyright: strict, reportPrivateUsage=false

import unittest
from typing import Any, Optional
from unittest.mock import MagicMock, patch

from benchmark.hsbench import Hsbench

_FAKE_CLIENT = "fake-client"
_FAKE_CLUSTER_SETTINGS: dict[str, Any] = {
    "tmp_dir": "/tmp/cbt-test",
    "osd_ra": "0",
}

_FAKE_ENDPOINT = {
    "access_key": "AKIAIOSFODNN7EXAMPLE",
    "secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "url": "http://localhost:8080",
}


def _mock_cluster() -> MagicMock:
    cluster: MagicMock = MagicMock()
    cluster.config = {}
    cluster.tmp_conf = "/etc/ceph/ceph.conf"
    return cluster


def _make(extra: Optional[dict[str, Any]] = None) -> Hsbench:
    config: dict[str, Any] = {
        "iteration": 0,
        "objects": 1000,
        "duration": 30,
        "buckets": 1,
        "threads": 4,
        "size": "4K",
        "modes": "cxip",
        "cmd_path": "/usr/local/bin/hsbench",
    }
    if extra:
        config.update(extra)
    with (
        patch("settings.cluster", _FAKE_CLUSTER_SETTINGS),
        patch("settings.getnodes", return_value=_FAKE_CLIENT),
        patch("common.get_osd_ra", return_value="0"),
    ):
        bm = Hsbench(archive_dir="/tmp/archive", cluster=_mock_cluster(), config=config)
    bm.cmd_path_full = "/usr/local/bin/hsbench"
    # Stub endpoint attributes normally set by initialize_endpoints()
    bm.endpoint_type = "s3"
    bm.endpoints_per_client = 1
    bm.endpoints = [_FAKE_ENDPOINT]
    return bm


def _cli_run(extra: Optional[dict[str, Any]] = None) -> str:
    """Return the pdsh CLI string produced by Hsbench._run_io_loop() in normal (non-prefill) mode."""
    bm = _make(extra)
    pdsh_mock = MagicMock()
    pdsh_mock.return_value = MagicMock()
    with patch("common.pdsh", pdsh_mock):
        bm._run_io_loop()  # pylint: disable=protected-access
    bench_calls = [str(c.args[1]) for c in pdsh_mock.call_args_list]
    return bench_calls[-1]


def _cli_prefill(extra: Optional[dict[str, Any]] = None) -> str:
    """Return the pdsh CLI string produced by Hsbench.prefill()."""
    bm = _make({"prefill": True, **(extra or {})})
    pdsh_mock = MagicMock()
    pdsh_mock.return_value = MagicMock()
    with patch("common.pdsh", pdsh_mock):
        bm.prefill()
    bench_calls = [str(c.args[1]) for c in pdsh_mock.call_args_list]
    return bench_calls[0]


class TestHsbenchRunCli(unittest.TestCase):  # pylint: disable=too-many-public-methods
    """CLI flag assertions for normal (non-prefill) hsbench run."""

    def test_cmd_path_present(self) -> None:
        """The configured hsbench executable path is emitted."""
        self.assertIn("/usr/local/bin/hsbench", _cli_run())

    def test_objects_flag(self) -> None:
        """-n flag is emitted with the configured objects count."""
        self.assertIn("-n 1000", _cli_run())

    def test_duration_flag(self) -> None:
        """-d flag is emitted with the configured duration."""
        self.assertIn("-d 30", _cli_run())

    def test_buckets_flag(self) -> None:
        """-b flag is emitted with the configured bucket count."""
        self.assertIn("-b 1", _cli_run())

    def test_threads_flag(self) -> None:
        """-t flag is emitted with the configured thread count."""
        self.assertIn("-t 4", _cli_run())

    def test_size_flag(self) -> None:
        """-z flag is emitted with the configured object size."""
        self.assertIn("-z 4K", _cli_run())

    def test_modes_flag(self) -> None:
        """-m flag is emitted with the configured modes."""
        self.assertIn("-m cxip", _cli_run())

    def test_access_key_flag(self) -> None:
        """-a flag is emitted with the endpoint access key."""
        self.assertIn("-a AKIAIOSFODNN7EXAMPLE", _cli_run())

    def test_secret_key_flag(self) -> None:
        """-s flag is emitted with the endpoint secret key."""
        self.assertIn("-s wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY", _cli_run())

    def test_url_flag(self) -> None:
        """-u flag is emitted with the endpoint URL."""
        self.assertIn("-u http://localhost:8080", _cli_run())

    def test_output_csv_flag(self) -> None:
        """-o flag (CSV output) is emitted."""
        self.assertIn("-o ", _cli_run())
        self.assertIn("output.0.csv", _cli_run())

    def test_output_json_flag(self) -> None:
        """-j flag (JSON output) is emitted."""
        self.assertIn("-j ", _cli_run())
        self.assertIn("output.0.json", _cli_run())

    def test_per_client_object_prefix_uses_backtick_hostname(self) -> None:
        """Per-client object prefix uses `hostname -f` backtick interpolation (D2a)."""
        self.assertIn("`hostname -f`", _cli_run())

    def test_custom_object_prefix_with_per_client(self) -> None:
        """When object_prefix is set, it is prepended to the hostname-based prefix."""
        cli = _cli_run({"object_prefix": "myprefix"})
        self.assertIn("-op myprefix-`hostname -f`", cli)

    def test_custom_object_prefix_without_per_client(self) -> None:
        """When per_client_object_prefix=False, static object_prefix is used as-is."""
        cli = _cli_run({"object_prefix": "myprefix", "per_client_object_prefix": False})
        self.assertIn("-op myprefix", cli)
        self.assertNotIn("`hostname -f`", cli)

    def test_bucket_prefix_flag(self) -> None:
        """-bp flag is emitted when bucket_prefix is set."""
        cli = _cli_run({"bucket_prefix": "mybucket"})
        self.assertIn("-bp mybucket", cli)

    def test_bucket_prefix_absent_by_default(self) -> None:
        """-bp flag is absent when bucket_prefix is not configured."""
        self.assertNotIn("-bp ", _cli_run())

    def test_region_flag_when_set(self) -> None:
        """-r flag is emitted when region is configured."""
        self.assertIn("-r us-east-1", _cli_run({"region": "us-east-1"}))

    def test_region_absent_by_default(self) -> None:
        """-r flag is absent when region is not configured."""
        self.assertNotIn("-r ", _cli_run())

    def test_loop_flag_when_set(self) -> None:
        """-l flag is emitted when loop is configured."""
        self.assertIn("-l 5", _cli_run({"loop": 5}))

    def test_loop_absent_by_default(self) -> None:
        """-l flag is absent when loop is not configured."""
        self.assertNotIn("-l ", _cli_run())

    def test_max_keys_flag_when_set(self) -> None:
        """-mk flag is emitted when max_keys is configured."""
        self.assertIn("-mk 1000", _cli_run({"max_keys": 1000}))

    def test_max_keys_absent_by_default(self) -> None:
        """-mk flag is absent by default."""
        self.assertNotIn("-mk ", _cli_run())

    def test_report_intervals_flag_when_set(self) -> None:
        """-ri flag is emitted when report_intervals is configured."""
        self.assertIn("-ri 10", _cli_run({"report_intervals": 10}))

    def test_report_intervals_absent_by_default(self) -> None:
        """-ri flag is absent by default."""
        self.assertNotIn("-ri ", _cli_run())

    def test_sudo_prefix(self) -> None:
        """Command is prefixed with 'sudo'."""
        self.assertTrue(_cli_run().startswith("sudo "))


class TestHsbenchPrefillCli(unittest.TestCase):
    """CLI flag assertions for hsbench prefill mode."""

    def test_prefill_uses_prefill_modes(self) -> None:
        """-m flag in prefill uses prefill_modes, not modes (D2b)."""
        # Default prefill_modes is "cxip"
        self.assertIn("-m cxip", _cli_prefill())

    def test_prefill_csv_output_has_prefill_suffix(self) -> None:
        """CSV output file has .prefill suffix in prefill mode (D2b)."""
        cli = _cli_prefill()
        self.assertIn("output.0.csv.prefill", cli)

    def test_prefill_json_output_has_prefill_suffix(self) -> None:
        """JSON output file has .prefill suffix in prefill mode (D2b)."""
        cli = _cli_prefill()
        self.assertIn("output.0.json.prefill", cli)

    def test_prefill_custom_prefill_modes(self) -> None:
        """-m flag uses custom prefill_modes when configured."""
        self.assertIn("-m cp", _cli_prefill({"prefill_modes": "cp"}))

    def test_prefill_does_not_use_run_modes(self) -> None:
        """Prefill mode does NOT emit run-mode value (e.g. 'rwm') in -m flag."""
        cli = _cli_prefill({"modes": "rwm", "prefill_modes": "cp"})
        # should use prefill modes, not run modes
        self.assertNotIn("-m rwm", cli)
        self.assertIn("-m cp", cli)


if __name__ == "__main__":
    unittest.main()
