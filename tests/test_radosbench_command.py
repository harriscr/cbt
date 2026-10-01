"""
Unit tests for RadosbenchCommand.
"""

import unittest
from typing import Optional
from unittest.mock import patch

from command.radosbench_command import RadosbenchCommand


class TestRadosbenchCommand(unittest.TestCase):
    """Tests for the RadosbenchCommand CLI generator."""

    def setUp(self) -> None:
        self.options: dict[str, Optional[str]] = {
            "op_size": "4194304",
            "object_set_id": "",
            "pool_per_proc": None,
            "write_omap": None,
            "max_objects": None,
        }
        self.run_dir = "/tmp/cbt/results/00000000/id-12345678/op_size-04194304/concurrent_ops-00000016/write"

    def _build_cmd(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        options: Optional[dict[str, Optional[str]]] = None,
        proc_id: int = 0,
        pool_name: str = "rados-bench-cbt",
        conf_path: str = "/etc/ceph/ceph.conf",
        runtime: str = "60",
        mode: str = "write",
        concurrent_ops: int = 16,
    ) -> RadosbenchCommand:
        """Helper to construct a RadosbenchCommand with test defaults."""
        opts = dict(self.options)
        if options is not None:
            opts.update(options)
        cmd = RadosbenchCommand(
            options=opts,
            run_dir=self.run_dir,
            proc_id=proc_id,
            pool_name=pool_name,
            conf_path=conf_path,
            runtime=runtime,
            mode=mode,
            concurrent_ops=concurrent_ops,
        )
        cmd.set_executable("/usr/bin/rados")
        return cmd

    def test_benchmark_property(self) -> None:
        """Verify the benchmark property returns radosbench."""
        cmd = self._build_cmd()
        self.assertEqual(cmd.benchmark, "radosbench")

    def test_output_directory(self) -> None:
        """Verify output_directory matches run_dir."""
        cmd = self._build_cmd()
        self.assertEqual(cmd.output_directory, self.run_dir)

    def test_no_executable_returns_empty_string(self) -> None:
        """Verify get() returns empty string when executable is unset."""
        cmd = RadosbenchCommand(options=self.options, run_dir=self.run_dir)
        self.assertEqual(cmd.get(), "")

    @patch("common.get_fqdn_cmd", return_value="hostname -f")
    def test_write_mode_full_command(self, _mock_fqdn: object) -> None:
        """Verify CLI string generation for standard write mode."""
        cmd = self._build_cmd(mode="write")
        cli = cmd.get()
        expected = (
            "/usr/bin/rados -c /etc/ceph/ceph.conf -p rados-bench-cbt bench "
            "-b 4194304 60 write --concurrent-ios 16 --run-name  `hostname -f`-0 "
            f"--no-cleanup 2> {self.run_dir}/objecter.0.log > {self.run_dir}/output.0"
        )
        self.assertEqual(cli, expected)

    @patch("common.get_fqdn_cmd", return_value="hostname -f")
    def test_seq_read_mode_omits_op_size(self, _mock_fqdn: object) -> None:
        """Verify op_size (-b) is omitted for sequential read mode."""
        cmd = self._build_cmd(mode="seq")
        cli = cmd.get()
        self.assertNotIn("-b ", cli)
        self.assertIn("60 seq --concurrent-ios 16", cli)

    @patch("common.get_fqdn_cmd", return_value="hostname -f")
    def test_prefill_mode_maps_to_write_and_includes_op_size(self, _mock_fqdn: object) -> None:
        """Verify prefill mode sets op_type to write and includes op_size."""
        cmd = self._build_cmd(mode="prefill")
        cli = cmd.get()
        self.assertIn("-b 4194304", cli)
        self.assertIn("60 write --concurrent-ios 16", cli)

    @patch("common.get_fqdn_cmd", return_value="hostname -f")
    def test_pool_per_proc_mode(self, _mock_fqdn: object) -> None:
        """Verify pool_per_proc creates per-process pool flag and omits run-name."""
        cmd = self._build_cmd(options={"pool_per_proc": "true"}, proc_id=2)
        cli = cmd.get()
        self.assertIn("-p rados-bench-`hostname -f`-2", cli)
        self.assertNotIn("--run-name", cli)

    @patch("common.get_fqdn_cmd", return_value="hostname -f")
    def test_max_objects_and_write_omap_flags(self, _mock_fqdn: object) -> None:
        """Verify max-objects and write-omap CLI flags are formatted correctly."""
        cmd = self._build_cmd(options={"max_objects": "5000", "write_omap": "true"})
        cli = cmd.get()
        self.assertIn("--max-objects 5000", cli)
        self.assertIn("--write-omap", cli)


if __name__ == "__main__":
    unittest.main()
