"""CephTestRados benchmark implementation.

Runs the `ceph_test_rados` tool against a Ceph cluster.
"""

import logging
import os
from typing import Any, Optional

import common
import settings
from benchmark.benchmark import Benchmark
from command.cephtestrados_command import CephTestRadosCommand
from monitoring.monitoring_factory import MonitoringFactory

logger = logging.getLogger("cbt")


class CephTestRados(Benchmark):  # pylint: disable=too-many-instance-attributes
    """Benchmark class for running ceph_test_rados workloads."""

    def __init__(self, archive_dir: str, cluster: Any, config: dict[str, Any]) -> None:
        super().__init__(archive_dir, cluster, config)

        self.tmp_conf: str = self.cluster.tmp_conf

        self.bools: dict[str, bool] = {}
        if config.get("ec_pool", False):
            self.bools["ec_pool"] = True
        if config.get("write_fadvise_dontneed", False):
            self.bools["write_fadvise_dontneed"] = True
        if config.get("pool_snaps", False):
            self.bools["pool_snaps"] = True
        if config.get("write_append_excl", True):
            self.bools["write_append_excl"] = True

        self.variables: dict[str, str] = {}
        self.variables["object_size"] = str(int(config.get("object_size", 4000000)))
        self.variables["max_ops"] = str(config.get("ops", 10000))
        self.variables["objects"] = str(config.get("objects", 500))
        self.variables["max_in_flight"] = str(config.get("max_in_flight", 16))
        self.variables["size"] = str(int(config.get("object_size", 4000000)))
        self.variables["min_stride_size"] = str(
            config.get("min_stride_size", int(config.get("object_size", 4000000)) // 10)
        )
        self.variables["max_stride_size"] = str(
            config.get("max_stride_size", int(config.get("object_size", 4000000)) // 5)
        )
        self.variables["max_seconds"] = str(config.get("max_seconds", 0))

        # D4b fix: `append` is a separate key — the legacy weight list had
        # `'cache_evict' 'append'` which Python concatenated into
        # `'cache_evictappend'`, making `append` unreachable from the loop.
        self.weights: dict[str, float] = {"read": 100, "write": 100, "delete": 10}
        for weight in [
            "snap_create",
            "snap_remove",
            "rollback",
            "setattr",
            "rmattr",
            "watch",
            "copy_from",
            "hit_set_list",
            "is_dirty",
            "cache_flush",
            "cache_try_flush",
            "cache_evict",
            "append",  # D4b: separate entry (was accidentally merged with cache_evict)
            "write",
            "read",
            "delete",
        ]:
            self.addweight(weight)
        if "write_append_excl" in self.bools and "append" in self.weights:
            self.weights["append"] = self.weights["write"] / 2
            self.weights["append_excl"] = self.weights["write"]

        if "write_append_excl" in self.bools and "write" in self.weights:
            self.weights["write"] = self.weights["write"] / 2
            self.weights["write_excl"] = self.weights["write"]

        self.run_dir = f"{self.run_dir}object_size-{int(self.variables['object_size']):08d}"
        self.out_dir = (
            f"{self.archive_dir}/osd_ra-{int(self.osd_ra):08d}/object_size-{int(self.variables['object_size']):08d}"
        )
        self.pool_profile: str = config.get("pool_profile", "default")
        self.cmd_path: str = config.get("cmd_path", "/usr/bin/ceph_test_rados")

    @property
    def benchmark_type(self) -> str:
        return "cephtestrados"

    def setup_targets(self) -> None:
        """Create the ceph_test_rados pool."""
        self.mkpool()

    def cleanup_targets(self) -> None:
        """No cleanup needed for ceph_test_rados."""

    def addweight(self, weight: str) -> None:
        """Set a custom weight for the given op type if configured."""
        value: Optional[Any] = self.config.get(f"{weight}_weight", None)
        if value is not None:
            self.weights[weight] = int(value)

    def exists(self) -> bool:
        if os.path.exists(self.out_dir):
            print(f"Skipping existing test in {self.out_dir}.")
            return True
        return False

    def _get_command_options(self) -> dict[str, Any]:
        """Build the options dict for CephTestRadosCommand."""
        opts: dict[str, Any] = {}
        for flag in ["ec_pool", "write_fadvise_dontneed", "pool_snaps"]:
            opts[flag] = "true" if flag in self.bools else None
        for var in ["max_ops", "objects", "max_in_flight", "size", "min_stride_size", "max_stride_size", "max_seconds"]:
            opts[var] = self.variables.get(var)
        opts["weights"] = dict(self.weights)
        return opts

    def _run_io_loop(self) -> None:
        """I/O dispatch only: build CephTestRadosCommand, call pdsh, wait."""
        logger.info("Running ceph_test_rados.")
        options = self._get_command_options()
        ps = []
        for _ in range(1):
            cmd = CephTestRadosCommand(
                options=options,
                run_dir=self.run_dir,
            )
            cmd.set_executable(self.cmd_path_full)
            p = common.pdsh(settings.getnodes("clients"), cmd.get())
            ps.append(p)
        for p in ps:
            p.wait()
        # If we were doing recovery, wait until it's done.
        if "recovery_test" in self.cluster.config:
            self.cluster.wait_recovery_done()

    def mkpool(self) -> None:
        """Recreate the ceph_test_rados pool with pool monitoring active."""
        MonitoringFactory.start(f"{self.run_dir}/pool_monitoring")
        self.cluster.rmpool("ceph_test_rados", self.pool_profile)
        self.cluster.mkpool("ceph_test_rados", self.pool_profile, "ceph_test_rados")
        MonitoringFactory.stop()

    def recovery_callback(self) -> None:
        """Kill ceph_test_rados processes on all clients during cluster recovery."""
        common.pdsh(settings.getnodes("clients"), "sudo pkill -f ceph_test_rados").communicate()

    def __str__(self) -> str:
        return f"{self.run_dir}\n{self.out_dir}\n{super().__str__()}"
