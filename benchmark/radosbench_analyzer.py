"""RadosBenchAnalyzer — result parser for ``rados bench`` JSON output files."""

import json
import os
from typing import Any, Optional

from benchmark.result import DataAnalyzer
from monitoring.monitoring_factory import MonitoringFactory


class RadosBenchAnalyzer(DataAnalyzer):
    """Analyzer for radosbench test results."""

    def __init__(self, archive_dir: str, run: str, host: str, proc: int) -> None:
        super().__init__(archive_dir, run, host, proc)
        self.out_dir: str = os.path.join(self.archive_dir, run)
        self.radosbench_out_fname: str = os.path.join(self.out_dir, f"json_output.{proc}.{host}")
        with open(self.radosbench_out_fname, encoding="utf-8") as fd:
            self.radosbench_json_output: dict[str, Any] = json.load(fd)

    def get_total_ops(self) -> Any:
        """Get total writes or reads made."""
        search_key = "made"  # looking for either 'Total writes made' or 'Total reads made'
        res = [val for key, val in self.radosbench_json_output.items() if search_key in key]
        return res[0]

    def get_cpu_cycles(self) -> Any:
        """Extract cpu cycles from monitoring."""
        return MonitoringFactory.get_cpu_cycles(self.out_dir)

    def get_cpu_cycles_per_op(self) -> Optional[float]:
        """Return CPU cycles per operation, or None if perf data is unavailable."""
        num_cpu_cycles = self.get_cpu_cycles()
        if num_cpu_cycles is not None:
            return int(self.get_cpu_cycles()) / int(self.get_total_ops())
        return None

    def get_latency_avg(self) -> Any:
        """Return average latency."""
        search_key = "Average Latency"
        res = [val for key, val in self.radosbench_json_output.items() if search_key in key]
        return res[0]

    def get_bandwidth(self) -> Any:
        """Return bandwidth."""
        search_key = "Bandwidth"
        res = [val for key, val in self.radosbench_json_output.items() if search_key in key]
        return res[0]

    def get_iops_avg(self) -> Any:
        """Return average IOPS."""
        return self.radosbench_json_output["Average IOPS"]

    def get_iops_stddev(self) -> Any:
        """Return IOPS standard deviation."""
        return self.radosbench_json_output["Stddev IOPS"]
