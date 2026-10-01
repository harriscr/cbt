"""
CLI golden tests for Radosbench._run_phase().

These tests mock common.pdsh to capture the rados bench command strings
sent to the clients and assert the presence/absence of individual flags
across representative configurations.

Known quirks from existing string-builder (D-series):
  D1a: op_size (-b flag) is only emitted when op_type is 'write' (not for reads).
  D1b: --run-name uses backtick shell interpolation `hostname -f` for remote execution.
"""

# pyright: strict, reportPrivateUsage=false
# pylint: disable=protected-access

import unittest
from typing import Any, Optional
from unittest.mock import MagicMock, patch

from benchmark.radosbench import Radosbench

_FAKE_CLIENT = "fake-client"
_FAKE_CLUSTER_SETTINGS: dict[str, Any] = {
    "tmp_dir": "/tmp/cbt-test",
    "osd_ra": "0",
}


def _mock_cluster() -> MagicMock:
    cluster: MagicMock = MagicMock()
    cluster.config = {}
    cluster.tmp_conf = "/etc/ceph/ceph.conf"
    cluster.rados_cmd = "/usr/local/bin/rados"
    return cluster


def _make(extra: Optional[dict[str, Any]] = None) -> Radosbench:
    config: dict[str, Any] = {
        "iteration": 0,
        "time": "60",
        "concurrent_procs": 1,
        "concurrent_ops": 16,
        "op_size": 4194304,
    }
    if extra:
        config.update(extra)
    with (
        patch("settings.cluster", _FAKE_CLUSTER_SETTINGS),
        patch("settings.getnodes", return_value=_FAKE_CLIENT),
        patch("common.get_osd_ra", return_value="0"),
    ):
        bm = Radosbench(archive_dir="/tmp/archive", cluster=_mock_cluster(), config=config)
    bm.cmd_path_full = "/usr/local/bin/rados"
    return bm


def _run_phase(bm: Radosbench, mode: str, run_dir: str, max_objects: Optional[int], runtime: str) -> list[str]:
    """
    Invoke _run_phase() with external calls stubbed out; return the list of CLI
    strings that were passed to common.pdsh (one per concurrent process).
    """
    pdsh_mock = MagicMock()
    proc_mock = MagicMock()
    pdsh_mock.return_value = proc_mock

    with (
        patch("common.pdsh", pdsh_mock),
        patch.object(bm, "get_rados_version", return_value=12),
    ):
        bm._run_phase(
            mode=mode, run_dir=run_dir, max_objects=max_objects, runtime=runtime
        )  # pylint: disable=protected-access

    # The only pdsh calls inside _run_phase() are the bench commands (one per proc).
    bench_calls = [str(c.args[1]) for c in pdsh_mock.call_args_list]
    return bench_calls


def _cli_write(extra: Optional[dict[str, Any]] = None) -> str:
    """Return the single pdsh CLI string for a standard write phase."""
    bm = _make(extra)
    calls = _run_phase(bm, mode="write", run_dir="/tmp/cbt-test/write", max_objects=None, runtime="60")
    return calls[0]


def _cli_read(extra: Optional[dict[str, Any]] = None) -> str:
    """Return the pdsh CLI string for a sequential read phase."""
    bm = _make(extra)
    calls = _run_phase(bm, mode="seq", run_dir="/tmp/cbt-test/seq", max_objects=None, runtime="60")
    return calls[0]


def _cli_prefill(extra: Optional[dict[str, Any]] = None) -> str:
    """Return the pdsh CLI string for a prefill phase."""
    bm = _make(extra)
    calls = _run_phase(bm, mode="prefill", run_dir="/tmp/cbt-test/prefill", max_objects=None, runtime="60")
    return calls[0]


class TestRadosbenchWriteCli(unittest.TestCase):
    """CLI flag assertions for the write phase."""

    def test_cmd_path_present(self) -> None:
        """The configured rados executable path is emitted."""
        self.assertIn("/usr/local/bin/rados", _cli_write())

    def test_conf_flag(self) -> None:
        """-c is passed with the tmp_conf path."""
        self.assertIn("-c /etc/ceph/ceph.conf", _cli_write())

    def test_bench_subcommand(self) -> None:
        """'bench' subcommand is present."""
        self.assertIn("bench", _cli_write())

    def test_write_op_type(self) -> None:
        """op_type 'write' is emitted."""
        self.assertIn("write", _cli_write())

    def test_op_size_present_on_write(self) -> None:
        """-b <op_size> is emitted for write (D1a)."""
        self.assertIn("-b 4194304", _cli_write())

    def test_concurrent_ops_flag(self) -> None:
        """--concurrent-ios is emitted with the configured value."""
        self.assertIn("--concurrent-ios 16", _cli_write())

    def test_duration_present(self) -> None:
        """The configured runtime is emitted."""
        self.assertIn("60", _cli_write())

    def test_no_cleanup_flag(self) -> None:
        """--no-cleanup is present."""
        self.assertIn("--no-cleanup", _cli_write())

    def test_stdout_redirect(self) -> None:
        """stdout is redirected to an output file."""
        cli = _cli_write()
        self.assertIn("> ", cli)
        self.assertIn("output.", cli)

    def test_stderr_redirect(self) -> None:
        """stderr is redirected to an objecter log file."""
        self.assertIn("2> ", _cli_write())
        self.assertIn("objecter.", _cli_write())

    def test_pool_flag(self) -> None:
        """-p flag with pool name is present."""
        self.assertIn("-p rados-bench-cbt", _cli_write())

    def test_max_objects_absent_when_none(self) -> None:
        """--max-objects is absent when max_objects is None."""
        self.assertNotIn("--max-objects", _cli_write())

    def test_write_omap_absent_by_default(self) -> None:
        """--write-omap is absent by default."""
        self.assertNotIn("--write-omap", _cli_write())

    def test_run_name_uses_backtick_hostname(self) -> None:
        """--run-name uses backtick shell interpolation for `hostname -f` (D1b)."""
        cli = _cli_write()
        self.assertIn("--run-name", cli)
        self.assertIn("`hostname -f`", cli)

    def test_op_size_flag_absent_for_reads(self) -> None:
        """-b flag is NOT emitted for read phases (D1a)."""
        self.assertNotIn("-b 4194304", _cli_read())

    def test_max_objects_present_when_set(self) -> None:
        """--max-objects is emitted when max_objects is set."""
        bm = _make()
        calls = _run_phase(bm, mode="write", run_dir="/tmp/cbt-test/write", max_objects=10000, runtime="60")
        self.assertIn("--max-objects 10000", calls[0])

    def test_write_omap_when_enabled(self) -> None:
        """--write-omap is emitted when write_omap=True."""
        bm = _make({"write_omap": True})
        calls = _run_phase(bm, mode="write", run_dir="/tmp/cbt-test/write", max_objects=None, runtime="60")
        self.assertIn("--write-omap", calls[0])

    def test_concurrent_ops_custom_value(self) -> None:
        """--concurrent-ios reflects the configured value."""
        self.assertIn("--concurrent-ios 32", _cli_write({"concurrent_ops": 32}))


class TestRadosbenchReadCli(unittest.TestCase):
    """CLI flag assertions for read phases."""

    def test_read_op_type_emitted(self) -> None:
        """'seq' op_type is emitted for a sequential read phase."""
        self.assertIn("seq", _cli_read())

    def test_op_size_absent_for_seq_read(self) -> None:
        """-b flag is NOT emitted for seq read (D1a: op_size only for write)."""
        self.assertNotIn("-b ", _cli_read())

    def test_no_cleanup_present_on_read(self) -> None:
        """--no-cleanup is present for read phases too."""
        self.assertIn("--no-cleanup", _cli_read())


class TestRadosbenchPrefillCli(unittest.TestCase):
    """CLI flag assertions for the prefill phase."""

    def test_prefill_emits_write_op_type(self) -> None:
        """Prefill mode emits 'write' as op_type (prefill maps to write)."""
        self.assertIn("write", _cli_prefill())

    def test_prefill_emits_op_size(self) -> None:
        """-b flag IS emitted for prefill (op_type is write) (D1a)."""
        self.assertIn("-b 4194304", _cli_prefill())


class TestRadosbenchPoolPerProcCli(unittest.TestCase):
    """CLI flag assertions for pool_per_proc=True mode."""

    def test_pool_per_proc_uses_hostname_in_pool_name(self) -> None:
        """pool_per_proc uses `hostname -f` in the pool name via backtick."""
        bm = _make({"pool_per_proc": True})
        calls = _run_phase(bm, mode="write", run_dir="/tmp/cbt-test/write", max_objects=None, runtime="60")
        cli = calls[0]
        # Pool name contains backtick hostname interpolation
        self.assertIn("`hostname -f`", cli)

    def test_pool_per_proc_no_run_name_flag(self) -> None:
        """pool_per_proc mode does NOT emit --run-name flag."""
        bm = _make({"pool_per_proc": True})
        calls = _run_phase(bm, mode="write", run_dir="/tmp/cbt-test/write", max_objects=None, runtime="60")
        self.assertNotIn("--run-name", calls[0])

    def test_single_pool_mode_no_hostname_in_pool_name(self) -> None:
        """Default single-pool mode uses a fixed pool name (no hostname interpolation in -p)."""
        cli = _cli_write()
        # pool name is static 'rados-bench-cbt'
        self.assertIn("-p rados-bench-cbt", cli)


class TestRadosbenchConcurrentProcsCli(unittest.TestCase):
    """Verify one pdsh call per concurrent_procs."""

    def test_two_concurrent_procs_produces_two_pdsh_calls(self) -> None:
        """concurrent_procs=2 causes two separate pdsh calls."""
        bm = _make({"concurrent_procs": 2})
        calls = _run_phase(bm, mode="write", run_dir="/tmp/cbt-test/write", max_objects=None, runtime="60")
        self.assertEqual(len(calls), 2)

    def test_proc_index_in_output_filename(self) -> None:
        """Each proc's output file includes its index (output.0, output.1, …)."""
        bm = _make({"concurrent_procs": 2})
        calls = _run_phase(bm, mode="write", run_dir="/tmp/cbt-test/write", max_objects=None, runtime="60")
        self.assertIn("output.0", calls[0])
        self.assertIn("output.1", calls[1])


if __name__ == "__main__":
    unittest.main()
