"""Top monitoring backend."""

import glob
import logging
import os
from typing import Any, ClassVar, Optional, cast

import common
import settings
from monitoring.base import Monitoring

logger = logging.getLogger("cbt")


class TopMonitoring(Monitoring):
    """Monitoring backend that captures top output for OSD processes."""

    DEFAULT_NODES: ClassVar[list[str]] = ["osds"]

    def __init__(self, mconfig: dict[str, Any]) -> None:
        """Initialize top monitoring configuration."""
        super().__init__(mconfig)
        # Remove these casts once settings.cluster.get() is fully typed.
        self._pid_dir = cast(str, settings.cluster.get("pid_dir"))
        self._pid_glob = mconfig.get("pid_glob", "osd.*.pid")
        self._user = cast(str, settings.cluster.get("user"))
        self._top_cmd = mconfig.get("top_cmd", "top")
        self._args = mconfig.get("args", "-b -H -1 -p {pid} -n 30 > {top_dir}/{pid}_osd_top.out")
        self._top_runners: list[Any] = []

    def start(self, directory: str) -> None:
        """Create the top output directory and start top collection."""
        top_dir = f"{directory}/top"
        common.pdsh(self._nodes, f"mkdir -p -m0755 -- {top_dir}").communicate()  # type: ignore[no-untyped-call]

        top_template = f"{self._top_cmd} {self._args}"
        local_node = common.get_localnode(self._nodes)  # type: ignore[no-untyped-call]
        if local_node:
            logger.debug("TopMonitoring: in local_node")
            logger.debug("pid_dir: %s", self._pid_dir)
            for pid_path in glob.glob(os.path.join(self._pid_dir, self._pid_glob)):
                logger.debug("TopMonitoring pid_path: %s", pid_path)
                with open(pid_path, encoding="utf-8") as pidfile:
                    pid = pidfile.read().strip()
                    top_cmd = top_template.format(top_dir=top_dir, pid=pid)
                    runner = common.sh(local_node, top_cmd)  # type: ignore[no-untyped-call]
                    self._top_runners.append(runner)
        else:
            logger.debug("TopMonitoring: remote_node")
            top_cmd = top_template.format(top_dir=top_dir, pid="${pid}")
            common.pdsh(  # type: ignore[no-untyped-call]
                self._nodes,
                [f"for pid in `cat {self._pid_dir}/{self._pid_glob}`;", "do", top_cmd, ";", "done"],
            )

    def stop(self, directory: Optional[str]) -> None:
        """Stop top collection and adjust file ownership when needed."""
        if self._top_runners:
            for runner in self._top_runners:
                runner.kill()
        else:
            common.pdsh(self._nodes, r"sudo pkill -SIGINT -f top\ ").communicate()  # type: ignore[no-untyped-call]
        if directory:
            common.pdsh(  # type: ignore[no-untyped-call]
                self._nodes,
                f"sudo chown {self._user}.{self._user} {directory}/top/*top.out",
            )
