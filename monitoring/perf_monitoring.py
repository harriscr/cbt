"""Perf monitoring backend."""

import glob
import logging
import os
import re
from typing import Any, ClassVar, Optional, cast

import common
import settings
from monitoring.monitoring import Monitoring

logger = logging.getLogger("cbt")


class PerfMonitoring(Monitoring):
    """Monitoring backend that captures perf output.

    Runs ``perf`` with a caller-supplied ``args`` template.  For OSD-specific
    PID discovery use :class:`OsdPerfMonitoring` instead.
    """

    DEFAULT_NODES: ClassVar[list[str]] = ["osds"]

    def __init__(self, mconfig: dict[str, Any]) -> None:
        """Initialize perf monitoring configuration."""
        super().__init__(mconfig)
        if "args" not in mconfig:
            raise ValueError("PerfMonitoring requires 'args' in mconfig")
        # Remove these casts once settings.cluster.get() is fully typed.
        self._user = cast(str, settings.cluster.get("user"))
        self._perf_cmd = mconfig.get("perf_cmd", "sudo perf")
        self._args_template: str = mconfig["args"]
        self._perf_runners: list[Any] = []
        self._perf_dir = ""

    def start(self, directory: str) -> None:
        """Create the perf output directory and start perf collection."""
        perf_dir = f"{directory}/perf"
        self._perf_dir = perf_dir
        common.pdsh(self._nodes, f"mkdir -p -m0755 -- {perf_dir}").communicate()  # type: ignore[no-untyped-call]

        perf_template = f"{self._perf_cmd} {self._args_template}"
        perf_cmd = perf_template.format(perf_dir=perf_dir)
        local_node = common.get_localnode(self._nodes)  # type: ignore[no-untyped-call]
        if local_node:
            runner = common.sh(local_node, perf_cmd)  # type: ignore[no-untyped-call]
            self._perf_runners.append(runner)
        else:
            common.pdsh(self._nodes, perf_cmd).communicate()  # type: ignore[no-untyped-call]

    def stop(self, directory: Optional[str]) -> None:
        """Stop perf collection and adjust file ownership when needed."""
        if self._perf_runners:
            for runner in self._perf_runners:
                runner.kill()
        else:
            common.pdsh(self._nodes, r"sudo pkill -SIGINT -f perf\ ").communicate()  # type: ignore[no-untyped-call]
        if directory:
            common.pdsh(  # type: ignore[no-untyped-call]
                self._nodes, f"sudo chown {self._user}:{self._user} {directory}/perf/perf.data"
            ).communicate()
            common.pdsh(  # type: ignore[no-untyped-call]
                self._nodes, f"sudo chown {self._user}:{self._user} {directory}/perf/perf_stat.*"
            ).communicate()

    def get_cpu_cycles(self, out_dir: str) -> Optional[int]:
        """Return total CPU cycles from perf stat output, if available."""
        total_cpu_cycles = 0
        matches = glob.glob(out_dir + "/perf*")
        if not matches:
            logger.warning("get_cpu_cycles: no perf output directory found under %s", out_dir)
            return None
        perf_dir_name = matches[0]
        perf_stat_fnames = os.listdir(perf_dir_name)
        for perf_out_fname in perf_stat_fnames:
            with open(f"{perf_dir_name}/{perf_out_fname}", encoding="utf-8") as perf_output_file:
                match = re.search(r"(.*) cycles(.*?) .*", perf_output_file.read(), re.M | re.I)
            if match:
                cpu_cycles = match.group(1).strip()
            else:
                return None
            total_cpu_cycles = total_cpu_cycles + int(cpu_cycles.replace(",", ""))
        return cast(Optional[int], total_cpu_cycles)


class OsdPerfMonitoring(PerfMonitoring):
    """PerfMonitoring specialised for Ceph OSD processes.

    Discovers the target PIDs by scanning PID files matching ``pid_glob``
    inside ``pid_dir`` (read from ``settings.cluster``), then launches a
    separate ``perf`` invocation per OSD PID.
    """

    def __init__(self, mconfig: dict[str, Any]) -> None:
        """Initialize OSD perf monitoring configuration."""
        super().__init__(mconfig)
        self._pid_dir = cast(str, settings.cluster.get("pid_dir"))
        self._pid_glob = mconfig.get("pid_glob", "osd.*.pid")

    def start(self, directory: str) -> None:
        """Create the perf output directory and start a perf instance per OSD PID."""
        perf_dir = f"{directory}/perf"
        self._perf_dir = perf_dir
        common.pdsh(self._nodes, f"mkdir -p -m0755 -- {perf_dir}").communicate()  # type: ignore[no-untyped-call]

        perf_template = f"{self._perf_cmd} {self._args_template}"
        local_node = common.get_localnode(self._nodes)  # type: ignore[no-untyped-call]
        if local_node:
            logger.debug("OsdPerfMonitoring: local_node pid_dir=%s", self._pid_dir)
            pid_paths = glob.glob(os.path.join(self._pid_dir, self._pid_glob))
            if not pid_paths:
                logger.warning(
                    "OsdPerfMonitoring: no PID files matched %s in %s — no perf processes started",
                    self._pid_glob,
                    self._pid_dir,
                )
            for pid_path in pid_paths:
                with open(pid_path, encoding="utf-8") as pidfile:
                    pid = pidfile.read().strip()
                    perf_cmd = perf_template.format(perf_dir=perf_dir, pid=pid)
                    runner = common.sh(local_node, perf_cmd)  # type: ignore[no-untyped-call]
                    self._perf_runners.append(runner)
        else:
            logger.debug("OsdPerfMonitoring: remote_node")
            pid_glob_path = f"{self._pid_dir}/{self._pid_glob}"
            ls_runner = common.pdsh(self._nodes, f"ls {pid_glob_path} 2>/dev/null")  # type: ignore[no-untyped-call]
            stdout, _ = ls_runner.communicate()
            if not stdout.strip():
                logger.warning(
                    "OsdPerfMonitoring: no PID files matched %s on remote nodes — no perf processes started",
                    pid_glob_path,
                )
            perf_cmd = perf_template.format(perf_dir=perf_dir, pid="${pid}")
            common.pdsh(  # type: ignore[no-untyped-call]
                self._nodes,
                [f"for pid in `cat {pid_glob_path}`;", "do", perf_cmd, ";", "done"],
            )
