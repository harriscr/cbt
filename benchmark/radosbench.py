"""
Radosbench benchmark implementation.

Runs the `rados bench` benchmark tool across Ceph clusters.
"""

import json
import logging
import os
import pathlib
import re
from collections.abc import Callable, Generator
from typing import Any, ClassVar, Optional

import common
import settings
from benchmark.benchmark import Benchmark
from benchmark.lis import Env, Lispy
from benchmark.radosbench_analyzer import RadosBenchAnalyzer
from benchmark.result import DataAnalyzer, Result
from command.radosbench_command import RadosbenchCommand
from monitoring.monitoring_factory import MonitoringFactory

logger = logging.getLogger("cbt")


class Radosbench(Benchmark):  # pylint: disable=too-many-instance-attributes
    """Benchmark class for running rados bench workloads."""

    def __init__(self, archive_dir: str, cluster: Any, config: dict[str, Any]) -> None:
        super().__init__(archive_dir, cluster, config)

        self.tmp_conf: str = self.cluster.tmp_conf
        self.time: str = str(config.get("time", "300"))
        self.concurrent_procs: int = config.get("concurrent_procs", 1)
        self.concurrent_ops: int = config.get("concurrent_ops", 16)
        self.pool_per_proc: bool = config.get("pool_per_proc", False)  # default behavior used to be True
        self.write_only: bool = config.get("write_only", False)
        self.write_time: str = str(config.get("write_time", self.time))
        self.read_only: bool = config.get("read_only", False)
        self.read_time: str = str(config.get("read_time", self.time))
        self.op_size: int = config.get("op_size", 4194304)
        self.object_set_id: str = config.get("object_set_id", "")
        self.run_dir: str = os.path.join(
            self.run_dir, f"op_size-{self.op_size:0>8}", f"concurrent_ops-{self.concurrent_ops:0>8}"
        )
        self.out_dir: str = self.archive_dir
        self.pool_profile: str = config.get("pool_profile", "default")
        self.cmd_path: str = config.get("cmd_path", self.cluster.rados_cmd)
        self.pool: str = config.get("target_pool", "rados-bench-cbt")
        self.readmode: str = config.get("readmode", "seq")
        self.max_objects: Optional[int] = config.get("max_objects", None)
        self.write_omap: bool = config.get("write_omap", False)
        self.prefill_time: Optional[str] = config.get("prefill_time", None)
        self.prefill_objects: Optional[int] = config.get("prefill_objects", None)

    @property
    def benchmark_type(self) -> str:
        return "radosbench"

    def setup_targets(self) -> None:
        self.mkpools()

    def cleanup_targets(self) -> None:
        pass

    def create_data_analyzer(self, run: str, host: str, proc: int) -> DataAnalyzer:
        return RadosBenchAnalyzer(self.out_dir, run, host, proc)

    def exists(self, expect_exists: bool = False) -> bool:
        if os.path.exists(self.out_dir):
            if not expect_exists:
                logger.info("Skipping existing test in %s.", self.out_dir)
            return True
        if expect_exists:
            logger.info("test result does not exist in %s.", self.out_dir)
        return False

    def estimate_duration(self) -> int:
        """Estimate total run-phase seconds: prefill + write + read phases."""
        total = 0
        if self.prefill_time or self.prefill_objects:
            total += int(self.prefill_time or self.time)
        if not self.read_only:
            total += int(self.write_time)
        if not self.write_only:
            total += int(self.read_time)
        return total

    def get_rados_version(self) -> int:
        """Query the Ceph cluster head node to determine the rados binary version."""
        stdout, _ = common.pdsh(settings.getnodes("head"), f"{self.cmd_path} -c {self.tmp_conf} -v").communicate()
        m = (
            re.findall(r"version (\d+)(?:.\d+)* \([0-9a-f]+\)", stdout)
            or re.findall(r"version v(\d+)(?:.\d+)* \([0-9a-f]+\)", stdout)
            or (255, 0)
        )
        return int(m[0])

    def execution_phases(self) -> Generator[tuple[str, str, Callable[[], None]], None, None]:
        """Yield (phase_name, phase_run_dir, runner) for prefill, write, and read phases."""
        do_prefill = bool(self.prefill_time or self.prefill_objects)

        if self.read_only and self.write_only:
            logger.error('Both "read_only" and "write_only" are specified, but they are mutually exclusive.')
            return
        if self.read_only and not do_prefill:
            logger.error(
                'Please prefill the testbench with "prefill_time" and/or '
                '"prefill_objects" option for a "read_only" test'
            )
            return

        if do_prefill:
            yield (
                "prefill",
                os.path.join(self.run_dir, "prefill"),
                lambda: self._run_phase(
                    mode="prefill",
                    run_dir=os.path.join(self.run_dir, "prefill"),
                    max_objects=self.prefill_objects,
                    runtime=str(self.prefill_time or self.time),
                ),
            )
        if not self.read_only:
            yield (
                "write",
                os.path.join(self.run_dir, "write"),
                lambda: self._run_phase(
                    mode="write",
                    run_dir=os.path.join(self.run_dir, "write"),
                    max_objects=self.max_objects,
                    runtime=str(self.write_time),
                ),
            )
        if not self.write_only:
            yield (
                self.readmode,
                os.path.join(self.run_dir, self.readmode),
                lambda: self._run_phase(
                    mode=self.readmode,
                    run_dir=os.path.join(self.run_dir, self.readmode),
                    max_objects=None,
                    runtime=str(self.read_time),
                ),
            )

    def _run_phase(
        self,
        mode: str,
        run_dir: str,
        max_objects: Optional[int],
        runtime: str,
    ) -> None:
        rados_version = self.get_rados_version()
        if max_objects and rados_version < 10:
            raise ValueError("max_objects not supported by rados_version < 10")
        if self.write_omap and rados_version < 10:
            raise ValueError("write_omap not supported by rados_version < 10")

        logger.info("Running radosbench %s test.", mode)
        options: dict[str, Optional[str]] = {
            "op_size": str(self.op_size),
            "object_set_id": self.object_set_id,
            "pool_per_proc": "true" if self.pool_per_proc else None,
            "write_omap": "true" if self.write_omap else None,
            "max_objects": str(max_objects) if max_objects is not None else None,
        }

        ps = []
        for i in range(self.concurrent_procs):
            cmd = RadosbenchCommand(
                options=options,
                run_dir=run_dir,
                proc_id=i,
                pool_name=self.pool,
                conf_path=self.tmp_conf,
                runtime=runtime,
                mode=mode,
                concurrent_ops=self.concurrent_ops,
            )
            cmd.set_executable(self.cmd_path_full)
            p = common.pdsh(settings.getnodes("clients"), cmd.get())
            ps.append(p)
        for p in ps:
            p.wait()

    def mkpools(self) -> None:
        """Create Ceph pools for radosbench test execution."""
        with MonitoringFactory.monitor(f"{self.run_dir}/pool_monitoring"):
            if self.pool_per_proc:  # allow use of a separate storage pool per process
                for i in range(self.concurrent_procs):
                    for node in settings.getnodes("clients").split(","):
                        node = node.rpartition("@")[2]
                        self.cluster.rmpool(f"rados-bench-{node}-{i}", self.pool_profile)
                        self.cluster.mkpool(f"rados-bench-{node}-{i}", self.pool_profile, "radosbench")
            else:  # the default behavior is to use a single Ceph storage pool for all rados bench processes
                self.cluster.rmpool("rados-bench-cbt", self.pool_profile)
                self.cluster.mkpool("rados-bench-cbt", self.pool_profile, "radosbench")

    def cleanup(self) -> None:
        cmd_name = pathlib.PurePath(self.cmd_path).name
        common.pdsh(settings.getnodes("clients"), f"sudo killall -9 {cmd_name}").communicate()

    def parse(self, out_dir: str) -> None:
        """Parse raw output files from rados bench into json_output files."""
        for client in settings.getnodes("clients").split(","):
            host = settings.host_info(client)["host"]
            for i in range(self.concurrent_procs):
                result = {}
                found = 0
                out_file = f"{out_dir}/output.{i}.{host}"
                json_out_file = f"{out_dir}/json_output.{i}.{host}"
                with open(out_file, encoding="utf-8") as fd:
                    for line in fd.readlines():
                        if found == 0:
                            if "Total time run" in line:
                                found = 1
                        if found == 1:
                            line = line.strip()
                            key, val = line.split(":")
                            result[key.strip()] = val.strip()
                with open(json_out_file, "w", encoding="utf-8") as json_fd:
                    json.dump(result, json_fd)

    def analyze(self, out_dir: str) -> None:
        """Convert results to json format."""
        logger.info("Convert results to json format.")
        self.parse(out_dir)

    # Human-readable display names keyed by the metric alias used in self.acceptable.
    _METRIC_ALIASES: ClassVar[dict[str, str]] = {
        "bandwidth": "Bandwidth (MB/sec)",
        "iops_avg": "Average IOPS",
        "iops_stddev": "Stddev IOPS",
        "latency_avg": "Average Latency(s)",
        "cpu_cycles_per_op": "Cycles per operation",
    }

    def _collect_metrics(self, self_analyzer: Any, baseline_analyzer: Any) -> list[dict[str, Any]]:
        """Collect metric values from both analyzers and return [self_res, baseline_res].

        Skips any metric whose getter returns None (e.g. cpu_cycles_per_op when perf is
        unavailable) and logs a warning when the kernel paranoid level would block perf.
        """
        self_res: dict[str, Any] = {}
        baseline_res: dict[str, Any] = {}
        for alias in self.acceptable:
            name = self._METRIC_ALIASES[alias]
            self_getter = getattr(self_analyzer, "get_" + alias)
            if self_getter is None:
                logger.debug("CPU Cycles Per Operation metric is not configured for this benchmark")
                continue
            value = self_getter()
            if value is None:
                paranoid_path = "/proc/sys/kernel/perf_event_paranoid"
                with open(paranoid_path, encoding="utf-8") as f:
                    paranoid_level = int(f.read())
                    if paranoid_level >= 1:
                        msg = (
                            "Perf must be run by user with CAP_SYS_ADMIN to extract"
                            " CPU related metrics. Or you could set %s to 0,"
                            " which is %d now"
                        )
                        logger.warning("%s. %s is %d", msg, paranoid_path, paranoid_level)
                continue
            self_res[name] = value
            baseline_res[name] = getattr(baseline_analyzer, "get_" + alias)()
        return [self_res, baseline_res]

    def _compare_client_results(self, client_run: str, self_analyzer: Any, baseline_analyzer: Any) -> list[Any]:
        """Compare per-client metrics against baseline and return a list of Results."""
        res_outputs = self._collect_metrics(self_analyzer, baseline_analyzer)
        compare_results: list[Any] = []
        for alias, stmt in list(self.acceptable.items()):
            name = self._METRIC_ALIASES[alias]
            result_val, baseline_val = [float(j[name]) for j in res_outputs]
            env = Env(None, result=result_val, baseline=baseline_val)
            lispy = Lispy()
            accepted = lispy.eval(lispy.parse(stmt), env)
            compare_results.append(Result(client_run, alias, result_val, baseline_val, stmt, accepted))
        return compare_results

    def evaluate(self, baseline: Any) -> list[Any]:
        """Compare this run's results against *baseline* and return a list of :class:`~benchmark.result.Result`.

        Only applicable to Radosbench — other benchmarks do not support comparison.
        """
        runs: list[str] = []
        if self.prefill_time or self.prefill_objects:
            runs.append("prefill")
        if not self.read_only:
            runs.append("write")
        if not self.write_only:
            runs.append(self.readmode)
        results: list[Any] = []
        for run in runs:
            for client in settings.getnodes("clients").split(","):
                host = settings.host_info(client)["host"]
                for proc in range(self.concurrent_procs):
                    self_analyzer = self.create_data_analyzer(run, host, proc)
                    baseline_analyzer = baseline.create_data_analyzer(run, host, proc)
                    client_run = f"{run}/{client}/{proc}"
                    results.extend(self._compare_client_results(client_run, self_analyzer, baseline_analyzer))
            # Check results from monitors (not yet implemented)
        return results

    def __str__(self) -> str:
        return f"{self.run_dir}\n{self.out_dir}\n{super().__str__()}"
