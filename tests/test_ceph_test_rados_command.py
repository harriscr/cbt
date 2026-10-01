"""Unit tests for CephTestRadosCommand."""

import unittest
from typing import Any, Optional

from command.cephtestrados_command import CephTestRadosCommand


def _make_cmd(
    options: Optional[dict[str, Any]] = None,
    run_dir: str = "/tmp/run",
    executable: str = "/usr/bin/ceph_test_rados",
) -> CephTestRadosCommand:
    """Helper to build a configured CephTestRadosCommand instance."""
    opts: dict[str, Any] = options if options is not None else {}
    cmd = CephTestRadosCommand(options=opts, run_dir=run_dir)
    cmd.set_executable(executable)
    return cmd


class TestCephTestRadosCommandABC(unittest.TestCase):
    """Test that CephTestRadosCommand satisfies the Command ABC contract."""

    def test_benchmark_property(self) -> None:
        """The benchmark property returns 'cephtestrados'."""
        cmd = _make_cmd()
        self.assertEqual(cmd.benchmark, "cephtestrados")

    def test_output_directory_returns_run_dir(self) -> None:
        """output_directory returns the configured run_dir."""
        cmd = _make_cmd(run_dir="/custom/run/dir")
        self.assertEqual(cmd.output_directory, "/custom/run/dir")

    def test_no_executable_returns_empty_string(self) -> None:
        """When executable is not set, get() returns an empty string."""
        cmd = CephTestRadosCommand(options={}, run_dir="/tmp/run")
        self.assertEqual(cmd.get(), "")


class TestCephTestRadosCommandBugFixes(unittest.TestCase):
    """Correctness tests for D4a, D4b, and D4c bug fixes."""

    def test_d4a_awk_pipeline_has_space_before_redirect(self) -> None:
        """D4a: awk pipeline emits `}' >` with a space before the redirect.

        The legacy mkcmd() had implicit Python string literal concatenation —
        `'... fflush(); }'' '>'` produced `'... fflush(); }'>` — so the emitted
        command was `... fflush(); }'>` with no space before `>`. The corrected
        command class must emit `}' >` (space present).
        """
        cmd = _make_cmd()
        cli = cmd.get()
        self.assertIn("fflush(); }' >", cli)
        self.assertNotIn("fflush(); }'>", cli)

    def test_d4b_append_weight_is_separately_addressable(self) -> None:
        """D4b: 'append' is a separate weight key, not merged into 'cache_evictappend'.

        The legacy weight list had `'cache_evict' 'append'` which Python
        concatenated into the single string `'cache_evictappend'`, making it
        impossible to set an `append` weight via config.  The fixed command class
        treats `append` as its own key.
        """
        weights = {"append": 50, "write": 100}
        cmd = _make_cmd(options={"weights": weights})
        cli = cmd.get()
        # --op append 50 must appear
        self.assertIn("--op append 50", cli)
        # The concatenated artifact must NOT appear
        self.assertNotIn("cache_evictappend", cli)

    def test_d4b_cache_evict_and_append_are_independent(self) -> None:
        """D4b: cache_evict and append can both be set independently."""
        weights = {"cache_evict": 20, "append": 30}
        cmd = _make_cmd(options={"weights": weights})
        cli = cmd.get()
        self.assertIn("--op cache_evict 20", cli)
        self.assertIn("--op append 30", cli)

    def test_d4c_max_seconds_zero_suppressed(self) -> None:
        """D4c: --max-seconds is suppressed when the value is '0' (or 0).

        The legacy guard used `if value:` on a string, so `'0'` was truthy and
        `--max-seconds 0` was always emitted.  The fixed command class uses
        `int(value) != 0` and therefore omits the flag when the value is zero.
        """
        cmd = _make_cmd(options={"max_seconds": "0"})
        cli = cmd.get()
        self.assertNotIn("--max-seconds", cli)

    def test_d4c_max_seconds_nonzero_emitted(self) -> None:
        """D4c: --max-seconds is emitted when the value is nonzero."""
        cmd = _make_cmd(options={"max_seconds": "300"})
        cli = cmd.get()
        self.assertIn("--max-seconds 300", cli)


class TestCephTestRadosCommandOptions(unittest.TestCase):
    """Test individual flag formatting."""

    def test_executable_starts_command(self) -> None:
        """The configured executable is at the start of the CLI string."""
        cmd = _make_cmd(executable="/usr/bin/ceph_test_rados")
        self.assertTrue(cmd.get().startswith("/usr/bin/ceph_test_rados"))

    def test_ec_pool_flag_emitted(self) -> None:
        """--ec-pool flag is emitted when ec_pool is set."""
        cmd = _make_cmd(options={"ec_pool": "true"})
        self.assertIn("--ec-pool", cmd.get())

    def test_ec_pool_flag_absent_by_default(self) -> None:
        """--ec-pool flag is absent when ec_pool is not set."""
        cmd = _make_cmd()
        self.assertNotIn("--ec-pool", cmd.get())

    def test_write_fadvise_dontneed_flag_emitted(self) -> None:
        """--write-fadvise-dontneed flag is emitted when set."""
        cmd = _make_cmd(options={"write_fadvise_dontneed": "true"})
        self.assertIn("--write-fadvise-dontneed", cmd.get())

    def test_pool_snaps_flag_emitted(self) -> None:
        """--pool-snaps flag is emitted when set."""
        cmd = _make_cmd(options={"pool_snaps": "true"})
        self.assertIn("--pool-snaps", cmd.get())

    def test_max_ops_emitted(self) -> None:
        """--max-ops is emitted with its value."""
        cmd = _make_cmd(options={"max_ops": "5000"})
        self.assertIn("--max-ops 5000", cmd.get())

    def test_objects_emitted(self) -> None:
        """--objects is emitted with its value."""
        cmd = _make_cmd(options={"objects": "250"})
        self.assertIn("--objects 250", cmd.get())

    def test_max_in_flight_emitted(self) -> None:
        """--max-in-flight is emitted with its value."""
        cmd = _make_cmd(options={"max_in_flight": "8"})
        self.assertIn("--max-in-flight 8", cmd.get())

    def test_size_emitted(self) -> None:
        """--size is emitted with its value."""
        cmd = _make_cmd(options={"size": "4000000"})
        self.assertIn("--size 4000000", cmd.get())

    def test_min_stride_size_emitted(self) -> None:
        """--min-stride-size is emitted with its value."""
        cmd = _make_cmd(options={"min_stride_size": "400000"})
        self.assertIn("--min-stride-size 400000", cmd.get())

    def test_max_stride_size_emitted(self) -> None:
        """--max-stride-size is emitted with its value."""
        cmd = _make_cmd(options={"max_stride_size": "800000"})
        self.assertIn("--max-stride-size 800000", cmd.get())

    def test_op_weights_emitted(self) -> None:
        """--op <name> <weight> is emitted for each weight in the dict."""
        weights = {"read": 100, "write": 100, "delete": 10}
        cmd = _make_cmd(options={"weights": weights})
        cli = cmd.get()
        self.assertIn("--op read 100", cli)
        self.assertIn("--op write 100", cli)
        self.assertIn("--op delete 10", cli)

    def test_pool_name_fixed(self) -> None:
        """The pool name 'ceph_test_rados' is always emitted."""
        cmd = _make_cmd()
        self.assertIn("--pool ceph_test_rados", cmd.get())

    def test_stdout_redirect_to_output_file(self) -> None:
        """stdout is redirected to <run_dir>/output."""
        cmd = _make_cmd(run_dir="/tmp/run")
        self.assertIn("> /tmp/run/output", cmd.get())

    def test_awk_timestamp_pipeline(self) -> None:
        """The awk timestamp pipeline is included in the command."""
        cmd = _make_cmd()
        cli = cmd.get()
        self.assertIn("awk '{ print strftime(", cli)
        self.assertIn("fflush();", cli)

    def test_variable_flags_absent_when_none(self) -> None:
        """Variable flags are absent when not provided in options."""
        cmd = _make_cmd()
        cli = cmd.get()
        # None of the variable flags should appear if options dict is empty
        self.assertNotIn("--max-ops", cli)
        self.assertNotIn("--objects", cli)
        self.assertNotIn("--max-in-flight", cli)
        self.assertNotIn("--size", cli)
        self.assertNotIn("--max-seconds", cli)

    def test_weights_absent_when_not_provided(self) -> None:
        """No --op flags are emitted when weights dict is absent."""
        cmd = _make_cmd()
        self.assertNotIn("--op", cmd.get())

    def test_full_options_command(self) -> None:
        """All options together produce a correctly formed command."""
        options: dict[str, Any] = {
            "ec_pool": "true",
            "max_ops": "10000",
            "objects": "500",
            "max_in_flight": "16",
            "size": "4000000",
            "min_stride_size": "400000",
            "max_stride_size": "800000",
            "max_seconds": "60",
            "weights": {"read": 100, "write": 100, "delete": 10},
        }
        cmd = _make_cmd(options=options, run_dir="/tmp/run")
        cli = cmd.get()
        self.assertTrue(cli.startswith("/usr/bin/ceph_test_rados"))
        self.assertIn("--ec-pool", cli)
        self.assertIn("--max-ops 10000", cli)
        self.assertIn("--objects 500", cli)
        self.assertIn("--max-in-flight 16", cli)
        self.assertIn("--size 4000000", cli)
        self.assertIn("--min-stride-size 400000", cli)
        self.assertIn("--max-stride-size 800000", cli)
        self.assertIn("--max-seconds 60", cli)
        self.assertIn("--op read 100", cli)
        self.assertIn("--pool ceph_test_rados", cli)
        self.assertIn("fflush(); }' >", cli)
        self.assertIn("> /tmp/run/output", cli)


if __name__ == "__main__":
    unittest.main()
