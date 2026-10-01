"""CLI golden tests for CephTestRados._run_io_loop().

These tests mock common.pdsh to capture the ceph_test_rados command strings
sent to clients and assert the presence/absence of individual flags.

Known fixes from the Command class (D-series):
  D4a: awk pipeline now emits `}' >` with a space before `>`.
  D4b: `append` is a separately addressable weight key (was accidentally
       merged with `cache_evict` in the legacy builder).
  D4c: --max-seconds is suppressed when the value is zero.
"""

import unittest
from typing import Any, Optional
from unittest.mock import MagicMock, patch

from benchmark.cephtestrados import CephTestRados

_FAKE_CLIENT = "fake-client"
_FAKE_CLUSTER_SETTINGS: dict[str, Any] = {
    "tmp_dir": "/tmp/cbt-test",
    "osd_ra": "0",
}


def _mock_cluster() -> MagicMock:
    cluster: MagicMock = MagicMock()
    cluster.config = {}
    cluster.tmp_conf = "/etc/ceph/ceph.conf"
    return cluster


def _make(extra: Optional[dict[str, Any]] = None) -> CephTestRados:
    config: dict[str, Any] = {
        "iteration": 0,
        "object_size": 4000000,
        "ops": 1000,
        "objects": 100,
        "max_in_flight": 16,
        "max_seconds": 0,
    }
    if extra:
        config.update(extra)
    with (
        patch("settings.cluster", _FAKE_CLUSTER_SETTINGS),
        patch("settings.getnodes", return_value=_FAKE_CLIENT),
        patch("common.get_osd_ra", return_value="0"),
    ):
        bm = CephTestRados(archive_dir="/tmp/archive", cluster=_mock_cluster(), config=config)
    bm.cmd_path_full = "/usr/bin/ceph_test_rados"
    return bm


def _cli(extra: Optional[dict[str, Any]] = None) -> str:
    """Return the CLI string produced by CephTestRados._run_io_loop()."""
    bm = _make(extra)
    pdsh_mock = MagicMock()
    pdsh_mock.return_value = MagicMock()
    with (
        patch("common.pdsh", pdsh_mock),
        patch("benchmark.cephtestrados.MonitoringFactory"),
    ):
        bm._run_io_loop()  # pylint: disable=protected-access
    calls = [str(c.args[1]) for c in pdsh_mock.call_args_list]
    return calls[0]


class TestCephTestRadosCli(unittest.TestCase):
    """CLI flag assertions for CephTestRados._run_io_loop()."""

    def test_executable_present(self) -> None:
        """Configured executable path is emitted."""
        self.assertIn("/usr/bin/ceph_test_rados", _cli())

    def test_max_ops_flag(self) -> None:
        """--max-ops is emitted with the configured ops value."""
        self.assertIn("--max-ops 1000", _cli())

    def test_objects_flag(self) -> None:
        """--objects is emitted with the configured objects count."""
        self.assertIn("--objects 100", _cli())

    def test_max_in_flight_flag(self) -> None:
        """--max-in-flight is emitted with the configured value."""
        self.assertIn("--max-in-flight 16", _cli())

    def test_size_flag(self) -> None:
        """--size is emitted with the configured object_size."""
        self.assertIn("--size 4000000", _cli())

    def test_pool_flag(self) -> None:
        """--pool ceph_test_rados is always present."""
        self.assertIn("--pool ceph_test_rados", _cli())

    def test_max_seconds_suppressed_when_zero(self) -> None:
        """--max-seconds is NOT emitted when value is 0 (D4c)."""
        self.assertNotIn("--max-seconds", _cli({"max_seconds": 0}))

    def test_max_seconds_emitted_when_nonzero(self) -> None:
        """--max-seconds IS emitted when value is non-zero (D4c)."""
        self.assertIn("--max-seconds 120", _cli({"max_seconds": 120}))

    def test_stdout_redirected(self) -> None:
        """stdout is redirected to an output file."""
        self.assertIn("> ", _cli())
        self.assertIn("output", _cli())

    def test_awk_pipeline_present(self) -> None:
        """awk pipeline for timestamped output is present."""
        self.assertIn("awk", _cli())
        self.assertIn("strftime", _cli())

    def test_awk_pipeline_space_before_redirect(self) -> None:
        """awk pipeline ends with `}' >` — space before `>` (D4a fix)."""
        cli = _cli()
        self.assertIn("}' >", cli)
        self.assertNotIn("}'>", cli.replace("}' >", ""))

    def test_default_write_weight_present(self) -> None:
        """Default write weight is emitted as --op write <weight>."""
        self.assertIn("--op write", _cli())

    def test_default_read_weight_present(self) -> None:
        """Default read weight is emitted as --op read <weight>."""
        self.assertIn("--op read", _cli())

    def test_default_delete_weight_present(self) -> None:
        """Default delete weight is emitted as --op delete <weight>."""
        self.assertIn("--op delete", _cli())

    def test_ec_pool_flag_absent_by_default(self) -> None:
        """--ec-pool is absent when ec_pool is not set."""
        self.assertNotIn("--ec-pool", _cli())

    def test_ec_pool_flag_when_set(self) -> None:
        """--ec-pool is emitted when ec_pool=True."""
        self.assertIn("--ec-pool", _cli({"ec_pool": True}))

    def test_pool_snaps_flag_absent_by_default(self) -> None:
        """--pool-snaps is absent by default."""
        self.assertNotIn("--pool-snaps", _cli())

    def test_pool_snaps_flag_when_set(self) -> None:
        """--pool-snaps is emitted when pool_snaps=True."""
        self.assertIn("--pool-snaps", _cli({"pool_snaps": True}))

    def test_write_fadvise_dontneed_absent_by_default(self) -> None:
        """--write-fadvise-dontneed is absent by default."""
        self.assertNotIn("--write-fadvise-dontneed", _cli())

    def test_write_fadvise_dontneed_when_set(self) -> None:
        """--write-fadvise-dontneed is emitted when configured."""
        self.assertIn("--write-fadvise-dontneed", _cli({"write_fadvise_dontneed": True}))


class TestCephTestRadosWeights(unittest.TestCase):
    """Weight configuration maps correctly to --op flags."""

    def test_custom_read_weight(self) -> None:
        """Custom read_weight value is reflected in --op read."""
        cli = _cli({"read_weight": 50})
        self.assertIn("--op read", cli)
        self.assertIn("50", cli)

    def test_write_append_excl_adds_write_excl(self) -> None:
        """write_append_excl=True splits the write weight and adds --op write_excl."""
        cli = _cli({"write_append_excl": True})
        self.assertIn("--op write_excl", cli)

    def test_write_append_excl_with_append_weight_adds_append_excl(self) -> None:
        """write_append_excl=True AND an explicit append_weight adds --op append_excl."""
        cli = _cli({"write_append_excl": True, "append_weight": 100})
        self.assertIn("--op append_excl", cli)
        self.assertIn("--op write_excl", cli)

    def test_append_weight_separate_from_cache_evict(self) -> None:
        """'append' appears as a standalone --op entry, not merged with cache_evict (D4b)."""
        cli = _cli()
        # If the D4b bug were present, we'd see 'cache_evictappend' — assert it's absent
        self.assertNotIn("cache_evictappend", cli)

    def test_min_stride_size_flag(self) -> None:
        """--min-stride-size is emitted from the variables dict."""
        self.assertIn("--min-stride-size", _cli())

    def test_max_stride_size_flag(self) -> None:
        """--max-stride-size is emitted from the variables dict."""
        self.assertIn("--max-stride-size", _cli())


if __name__ == "__main__":
    unittest.main()
