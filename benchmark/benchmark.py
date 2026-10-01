"""Benchmark abstract base class for CBT."""

import hashlib
import json
import logging
import os
from abc import ABC, abstractmethod
from collections.abc import Callable, Generator
from typing import Any, Optional

import yaml

import common
import settings
from monitoring.monitoring_factory import MonitoringFactory
from workloads.workloads import Workloads

logger = logging.getLogger("cbt")


class Benchmark(ABC):  # pylint: disable=too-many-instance-attributes
    """Abstract base class for all benchmark implementations.

    Provides common lifecycle management, environment setup, workload dispatch,
    and result comparison infrastructure. Concrete benchmarks must implement
    benchmark_type, setup_targets, cleanup_targets, and either _run_io_loop
    or override execution_phases.

    The ``too-many-instance-attributes`` suppression is intentional: ``Benchmark``
    is a lifecycle coordinator, not a data object.  Each attribute corresponds to
    a distinct, independently-configured cluster or run parameter (archive paths,
    OSD read-ahead, valgrind, workloads, logging flags, etc.).  Splitting them
    across helper objects would add indirection with no benefit.
    """

    def __init__(
        self,
        archive_dir: str,
        cluster: Any,
        config: dict[str, Any],
    ) -> None:
        self.acceptable: dict[str, Any] = config.pop("acceptable", {})
        self.config: dict[str, Any] = config
        self.cluster = cluster
        self._base_archive_directory: str = archive_dir
        hashable = json.dumps(sorted(self.config.items())).encode()
        digest = hashlib.sha1(hashable).hexdigest()[:8]
        self.archive_dir: str = os.path.join(archive_dir, "results", f"{config.get('iteration'):0>8}", f"id-{digest}")
        # This would show several dirs if run continuously
        logger.info("Results dir: %s", self.archive_dir)
        self.run_dir: str = os.path.join(
            settings.cluster.get("tmp_dir"), f"{config.get('iteration'):0>8}", self.getclass()
        )
        # Default output directory — subclasses that need a different path (e.g.
        # CephTestRados) override this in their own __init__ after calling super().
        self.out_dir: str = self.archive_dir
        self.osd_ra: str = config.get("osd_ra", "0")
        self.cmd_path: str = ""
        self.valgrind: Optional[str] = config.get("valgrind", None)
        self.cmd_path_full: str = ""
        self.log_iops: bool = config.get("log_iops", True)
        self.log_bw: bool = config.get("log_bw", True)
        self.log_lat: bool = config.get("log_lat", True)

        self.osd_ra_changed: bool = False
        if self.osd_ra:
            self.osd_ra_changed = True
        else:
            self.osd_ra = common.get_osd_ra()

        self.run_dir += f"/osd_ra-{int(self.osd_ra):08d}/"

        self._workloads: Workloads = Workloads(config, self.run_dir)
        self._create_report: bool = config.get("create_report", False)

    # ---------------------------------------------------------------------- #
    # Abstract interface
    # ---------------------------------------------------------------------- #

    @property
    @abstractmethod
    def benchmark_type(self) -> str:
        """Name string for the workloads path and benchmark identification."""

    # ---------------------------------------------------------------------- #
    # Lifecycle hooks — abstract, every concrete benchmark MUST override.
    # ---------------------------------------------------------------------- #

    @abstractmethod
    def setup_targets(self) -> None:
        """Create pools, images, filesystems, or mount points.  Must be implemented by subclasses."""

    @abstractmethod
    def cleanup_targets(self) -> None:
        """Unmount, unmap, or delete temporary resources.  Must be implemented by subclasses."""

    # ---------------------------------------------------------------------- #
    # Env setup — extracted from the old run() body
    # ---------------------------------------------------------------------- #

    def _setup_env(self) -> None:
        """Perform OSD RA, run-dir wipe, valgrind path resolution, and config snapshot."""
        if self.osd_ra and self.osd_ra_changed:
            logger.info("Setting OSD Read Ahead to: %s", self.osd_ra)
            self.cluster.set_osd_param("read_ahead_kb", self.osd_ra)

        logger.info("Cleaning existing temporary run directory: %s", self.run_dir)
        common.pdsh(settings.getnodes("clients", "osds", "mons", "rgws"), f"sudo rm -rf {self.run_dir}").communicate()
        if self.valgrind is not None:
            logger.debug("Adding valgrind to the command path.")
            self.cmd_path_full = common.setup_valgrind(self.valgrind, self.getclass(), self.run_dir)
        # Set the full command path
        self.cmd_path_full += self.cmd_path

        # Store the parameters of the test run
        config_file = os.path.join(self.archive_dir, "benchmark_config.yaml")
        if not os.path.exists(self.archive_dir):
            os.makedirs(self.archive_dir)
        if not os.path.exists(config_file):
            config_dict = {"cluster": self.config}
            with open(config_file, "w", encoding="utf-8") as fd:
                yaml.dump(config_dict, fd, default_flow_style=False)

    # ---------------------------------------------------------------------- #
    # Workloads runner
    # ---------------------------------------------------------------------- #

    def _run_workloads(self) -> None:
        """Dispatch the workloads pipeline for this benchmark."""
        self._workloads.set_benchmark_type(self.benchmark_type)
        self._workloads.set_executable(self.cmd_path)
        self._workloads.run()

    # ---------------------------------------------------------------------- #
    # I/O loop hook — non-workloads benchmarks implement this
    # ---------------------------------------------------------------------- #

    def _run_io_loop(self) -> None:
        """Execute the non-workloads I/O loop.  Raises NotImplementedError by default."""
        raise NotImplementedError(f"{self.__class__.__name__} must implement _run_io_loop()")

    # ---------------------------------------------------------------------- #
    # Phase generator
    # ---------------------------------------------------------------------- #

    def execution_phases(self) -> Generator[tuple[str, str, Callable[[], None]], None, None]:
        """Yield (phase_name, phase_run_dir, runner) for each execution phase.

        Default routes to _run_workloads() when workloads exist, otherwise
        to _run_io_loop().  Multi-phase benchmarks (e.g. Radosbench) override
        this to yield separate prefill / write / read phases.
        """
        if self._workloads.exist():
            yield ("workload", self.run_dir, self._run_workloads)
        else:
            yield ("benchmark", self.run_dir, self._run_io_loop)

    # ---------------------------------------------------------------------- #
    # Unified run() loop
    # ---------------------------------------------------------------------- #

    def run(self) -> None:
        """Execute the full benchmark lifecycle.

        1.  _setup_env()       — OSD RA, rm -rf run_dir, valgrind, config snapshot
        2.  dropcaches()
        3.  setup_targets()    — create pools, images, mounts, cred files
        4.  For each phase from execution_phases():
              make_remote_dir, MonitoringFactory.monitor context, runner(),
              sync_files
        5.  cluster.dump_historic_ops(run_dir)
        6.  analyze(out_dir)
        7.  cleanup_targets()
        """
        self._setup_env()
        self.dropcaches()
        self.setup_targets()

        for phase_name, phase_run_dir, runner in self.execution_phases():
            logger.info("Executing phase: %s (%s)", phase_name, phase_run_dir)
            common.make_remote_dir(phase_run_dir)
            with MonitoringFactory.monitor(phase_run_dir):
                runner()
            common.sync_files(f"{phase_run_dir}/*", self.out_dir)

        self.cluster.dump_historic_ops(self.run_dir)
        self.analyze(self.out_dir)
        self.cleanup_targets()

    # ---------------------------------------------------------------------- #
    # Remaining existing methods — type annotations added
    # ---------------------------------------------------------------------- #

    def analyze(self, out_dir: str) -> None:  # noqa: B027  # pylint: disable=unused-argument
        """Post-run analysis hook.  No-op by default.

        Benchmarks that produce structured output (e.g. radosbench JSON) should
        override this to parse raw output files into the archive directory.
        """

    def cleandir(self) -> None:
        """Wipe and create the run directory."""
        common.clean_remote_dir(self.run_dir)
        common.make_remote_dir(self.run_dir)

    def getclass(self) -> str:
        """Return the class name."""
        return self.__class__.__name__

    def initialize(self) -> None:  # noqa: B027
        """Initialise the benchmark.  No-op default."""

    def initialize_endpoints(self) -> None:  # noqa: B027
        """Initialise any client endpoints.  No-op default."""

    def prefill(self) -> None:  # noqa: B027
        """Pre-populate the cluster before the timed run.  No-op default."""

    def estimate_duration(self) -> int:
        """Return estimated total wall-clock seconds for all run-phase work.

        The base implementation returns 0.  Concrete benchmarks should override
        this to sum up their configured ``time``, ``ramp``, and any prefill
        durations so that :mod:`progress` can size the overall progress bar.
        """
        return 0

    def exists(self) -> bool:
        """Check if benchmark results already exist."""
        return False

    def cleanup(self) -> None:  # noqa: B027
        """Clean up after the benchmark.  No-op default."""

    def dropcaches(self) -> None:
        """Drop caches on clients and OSDs."""
        logger.info("Dropping caches on clients and OSDs...")
        nodes = settings.getnodes("clients", "osds")

        common.pdsh(nodes, "sync").communicate()
        common.pdsh(nodes, "echo 3 | sudo tee /proc/sys/vm/drop_caches").communicate()
        logger.info("Caches dropped.")

    def __str__(self) -> str:
        return str(self.config)
