"""Hsbench benchmark implementation.

Runs the `hsbench` benchmark tool across Ceph object gateways (RGW / S3).
"""

import logging
import os
import pathlib
from typing import Any, Optional

import client_endpoints_factory
import common
import settings
from benchmark.benchmark import Benchmark
from command.hsbench_command import HsbenchCommand

logger = logging.getLogger("cbt")


class Hsbench(Benchmark):  # pylint: disable=too-many-instance-attributes
    """Benchmark class for running hsbench workloads."""

    def __init__(self, archive_dir: str, cluster: Any, config: dict[str, Any]) -> None:
        super().__init__(archive_dir, cluster, config)
        self.cmd_path: str = config.get("cmd_path", "/usr/local/bin/hsbench")
        self.tmp_conf: str = self.cluster.tmp_conf
        self.buckets: Optional[int] = config.get("buckets", None)
        self.bucket_prefix: Optional[str] = config.get("bucket_prefix", None)
        self.duration: Optional[int] = config.get("duration", None)
        self.loop: Optional[int] = config.get("loop", None)
        self.modes: Optional[str] = config.get("modes", None)
        self.max_keys: Optional[int] = config.get("max_keys", None)
        self.objects: Optional[int] = config.get("objects", None)
        self.object_prefix: Optional[str] = config.get("object_prefix", None)
        self.per_client_object_prefix: bool = config.get("per_client_object_prefix", True)
        self.region: Optional[str] = config.get("region", None)
        self.report_intervals: Optional[int] = config.get("report_intervals", None)
        self.threads: Optional[int] = config.get("threads", None)
        self.size: Optional[str] = config.get("size", None)
        self.out_dir: str = self.archive_dir
        self.client_endpoints: Any = config.get("client_endpoints", None)
        self.prefill_flag: bool = config.get("prefill", False)
        self.prefill_modes: str = config.get("prefill_modes", "cxip")
        self.client_endpoints_object: Any = None
        self.endpoint_type: Optional[str] = None
        self.endpoints_per_client: int = 0
        self.endpoints: list[dict[str, Any]] = []

    @property
    def benchmark_type(self) -> str:
        return "hsbench"

    def setup_targets(self) -> None:
        pass

    def cleanup_targets(self) -> None:
        pass

    def estimate_duration(self) -> int:
        """Estimate run-phase seconds from the configured duration."""
        return int(self.duration) if self.duration is not None else 0

    def exists(self) -> bool:
        if os.path.exists(self.out_dir):
            logger.info("Skipping existing test in %s.", self.out_dir)
            return True
        return False

    # Initialize may only be called once depending on rebuild_every_test setting
    def initialize(self) -> None:
        super().initialize()

        # Clean and Create the run directory
        common.clean_remote_dir(self.run_dir)
        common.make_remote_dir(self.run_dir)

    def initialize_endpoints(self) -> None:
        super().initialize_endpoints()
        if self.client_endpoints is None:
            raise ValueError("No client_endpoints defined!")
        self.client_endpoints_object = client_endpoints_factory.get(self.cluster, self.client_endpoints)

        if not self.client_endpoints_object.get_initialized():
            self.client_endpoints_object.initialize()

        self.endpoint_type = self.client_endpoints_object.get_endpoint_type()
        self.endpoints_per_client = self.client_endpoints_object.get_endpoints_per_client()
        self.endpoints = self.client_endpoints_object.get_endpoints()

    def _get_command_options(self) -> dict[str, Optional[str]]:
        return {
            "buckets": str(self.buckets) if self.buckets is not None else None,
            "bucket_prefix": self.bucket_prefix,
            "duration": str(self.duration) if self.duration is not None else None,
            "loop": str(self.loop) if self.loop is not None else None,
            "modes": self.modes,
            "prefill_modes": self.prefill_modes,
            "max_keys": str(self.max_keys) if self.max_keys is not None else None,
            "objects": str(self.objects) if self.objects is not None else None,
            "object_prefix": self.object_prefix,
            "per_client_object_prefix": "true" if self.per_client_object_prefix else None,
            "region": self.region,
            "report_intervals": str(self.report_intervals) if self.report_intervals is not None else None,
            "threads": str(self.threads) if self.threads is not None else None,
            "size": self.size,
        }

    def prefill(self) -> None:
        super().prefill()
        if not self.prefill_flag:
            return
        logger.info("Attempting to prefill hsbench objects...")
        options = self._get_command_options()
        ps = []
        for i in range(self.endpoints_per_client):
            cmd = HsbenchCommand(
                options=options,
                run_dir=self.run_dir,
                ep_num=i,
                endpoint=self.endpoints[i % len(self.endpoints)],
                prefill=True,
            )
            cmd.set_executable(self.cmd_path)
            p = common.pdsh(settings.getnodes("clients"), cmd.get())
            ps.append(p)
        for p in ps:
            p.wait()

    def _run_io_loop(self) -> None:
        logger.info("Running hsbench %s test.", self.modes)
        options = self._get_command_options()
        ps = []
        for i in range(self.endpoints_per_client):
            cmd = HsbenchCommand(
                options=options,
                run_dir=self.run_dir,
                ep_num=i,
                endpoint=self.endpoints[i % len(self.endpoints)],
                prefill=False,
            )
            cmd.set_executable(self.cmd_path_full)
            p = common.pdsh(settings.getnodes("clients"), cmd.get())
            ps.append(p)
        for p in ps:
            p.wait()

    def recovery_callback(self) -> None:
        """Callback to cleanup clients during cluster recovery."""
        self.cleanup()

    def cleanup(self) -> None:
        cmd_name = pathlib.PurePath(self.cmd_path).name
        common.pdsh(settings.getnodes("clients"), f"sudo killall -9 {cmd_name}").communicate()

    def __str__(self) -> str:
        return f"{self.run_dir}\n{self.out_dir}\n{super().__str__()}"
