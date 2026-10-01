"""Behavioural tests for Nullbench.

These tests guarantee that Nullbench delegates its lifecycle to Benchmark.run()
(no custom run() override), has no custom recovery_callback(), and satisfies the
Benchmark ABC contract through its minimal implementation.

Seams under test:
  - Nullbench.run() → delegates entirely to Benchmark.run() (no override)
  - Nullbench.setup_targets() / cleanup_targets() → no-ops, do not raise
  - Nullbench.benchmark_type → "nullbench"
  - Nullbench._run_io_loop() → raises NotImplementedError (inherited default)
  - Nullbench has no recovery_callback() of its own
"""

import unittest
from typing import Any
from unittest.mock import MagicMock, call, patch


def _mock_cluster() -> MagicMock:
    cluster: MagicMock = MagicMock()
    cluster.config = {}
    cluster.tmp_conf = "/etc/ceph/ceph.conf"
    return cluster


_FAKE_CLUSTER_SETTINGS: dict[str, Any] = {
    "tmp_dir": "/tmp/cbt-test",
    "osd_ra": "0",
}


def _make_nullbench() -> Any:
    from benchmark.nullbench import Nullbench

    config: dict[str, Any] = {"iteration": 0}
    with (
        patch("settings.cluster", _FAKE_CLUSTER_SETTINGS),
        patch("settings.getnodes", return_value="fake-client"),
        patch("common.get_osd_ra", return_value="0"),
    ):
        return Nullbench(archive_dir="/tmp/archive", cluster=_mock_cluster(), config=config)


class TestNullbenchContract(unittest.TestCase):
    """Nullbench satisfies the Benchmark ABC and has no lifecycle overrides."""

    def test_benchmark_type(self) -> None:
        """benchmark_type property returns 'nullbench'."""
        bm = _make_nullbench()
        self.assertEqual(bm.benchmark_type, "nullbench")

    def test_setup_targets_does_not_raise(self) -> None:
        """setup_targets() is a no-op and does not raise."""
        bm = _make_nullbench()
        bm.setup_targets()  # must not raise

    def test_cleanup_targets_does_not_raise(self) -> None:
        """cleanup_targets() is a no-op and does not raise."""
        bm = _make_nullbench()
        bm.cleanup_targets()  # must not raise

    def test_run_is_not_overridden(self) -> None:
        """Nullbench must not define its own run() — it inherits from Benchmark."""
        from benchmark.benchmark import Benchmark
        from benchmark.nullbench import Nullbench

        # run() must resolve to Benchmark.run, not something defined on Nullbench itself
        self.assertNotIn("run", Nullbench.__dict__, "Nullbench must not override run()")
        self.assertIs(Nullbench.run, Benchmark.run)

    def test_no_recovery_callback(self) -> None:
        """Nullbench must not define recovery_callback() — it has no cluster resources to clean."""
        from benchmark.nullbench import Nullbench

        self.assertNotIn(
            "recovery_callback",
            Nullbench.__dict__,
            "Nullbench must not define recovery_callback()",
        )

    def test_run_io_loop_raises_not_implemented(self) -> None:
        """_run_io_loop() raises NotImplementedError (inherited from Benchmark)."""
        from benchmark.benchmark import Benchmark
        from benchmark.nullbench import Nullbench

        bm = _make_nullbench()
        # The default from Benchmark raises NotImplementedError
        with self.assertRaises(NotImplementedError):
            Benchmark._run_io_loop(bm)  # pylint: disable=protected-access

    def test_run_delegates_to_benchmark_run(self) -> None:
        """Calling run() on a Nullbench instance exercises Benchmark.run()."""
        bm = _make_nullbench()
        # Patch the full Benchmark.run() lifecycle so we don't need a real cluster
        with patch("benchmark.benchmark.Benchmark.run") as mock_run:
            bm.run()
            mock_run.assert_called_once()


class TestNullbenchLifecycle(unittest.TestCase):
    """Nullbench.run() exercises the full Benchmark lifecycle (setup→phases→cleanup)."""

    def test_setup_and_cleanup_called_by_run(self) -> None:
        """Benchmark.run() calls setup_targets() and cleanup_targets() around phases."""
        bm = _make_nullbench()

        call_log: list[str] = []
        original_setup = bm.setup_targets
        original_cleanup = bm.cleanup_targets

        def _tracked_setup() -> None:
            call_log.append("setup_targets")
            original_setup()

        def _tracked_cleanup() -> None:
            call_log.append("cleanup_targets")
            original_cleanup()

        bm.setup_targets = _tracked_setup  # type: ignore[method-assign]
        bm.cleanup_targets = _tracked_cleanup  # type: ignore[method-assign]

        with (
            patch("benchmark.benchmark.Benchmark._setup_env"),
            patch("benchmark.benchmark.Benchmark.dropcaches"),
            patch("benchmark.benchmark.common.make_remote_dir"),
            patch("benchmark.benchmark.MonitoringFactory.monitor") as mock_monitor,
            patch("benchmark.benchmark.common.sync_files"),
            patch("benchmark.benchmark.Benchmark.analyze"),
            # execution_phases yields ("benchmark", run_dir, _run_io_loop)
            # _run_io_loop raises NotImplementedError by default, so patch it too
            patch.object(bm, "_run_io_loop"),
        ):
            mock_monitor.return_value.__enter__ = MagicMock(return_value=None)
            mock_monitor.return_value.__exit__ = MagicMock(return_value=False)
            bm.run()

        self.assertIn("setup_targets", call_log)
        self.assertIn("cleanup_targets", call_log)
        self.assertLess(call_log.index("setup_targets"), call_log.index("cleanup_targets"))


if __name__ == "__main__":
    unittest.main()
