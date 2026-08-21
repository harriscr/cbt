"""
Process the CPU statistics as provided by FIO
"""

import os
from logging import Logger, getLogger
from pathlib import Path
from typing import Any

from post_processing.run_results.resource_result import ResourceResult

log: Logger = getLogger("formatter")


class FIOResource(ResourceResult):
    """
    Processes resource usage statistics from FIO benchmark output.

    FIO includes CPU usage statistics in its JSON output, which this class
    extracts and formats for inclusion in the common intermediate format.
    """

    @property
    def source(self) -> str:
        return "fio"

    def _get_resource_output_file_from_file_path(self, file_path: Path) -> Path:
        """
        Get the path to the resource usage file.

        For FIO, resource usage details are stored in the same file as the
        benchmark results, so this simply returns the input path.

        Args:
            file_path: Path to the FIO output file

        Returns:
            The same path, as FIO stores resource data in the benchmark output file
        """
        return file_path

    def _parse(self) -> None:
        """
        Extract CPU and memory usage from FIO output data.

        Combines system CPU and user CPU percentages to get total CPU usage.
        FIO reports usr_cpu/sys_cpu as a percentage of one CPU core
        (100% = one core fully busy), so the sum is divided by os.cpu_count()
        to normalise to system capacity (0-100% = all cores fully busy).

        For multi-job runs the per-job CPU figures are averaged across all
        jobs, because each job entry already reflects one numjob's usage.

        Memory usage is currently not extracted from FIO output.
        """
        data = self._read_results_from_file()
        jobs: list[dict[str, Any]] = data.get("jobs", [])
        if not jobs:
            log.warning("No job data found in FIO output at %s", self._resource_file_path)
            self._cpu = "0.00"
            self._memory = "0.00"
            self._has_been_parsed = True
            return

        cpu_count: int = os.cpu_count() or 1
        total_cpu: float = sum(float(job.get("sys_cpu", 0.0)) + float(job.get("usr_cpu", 0.0)) for job in jobs)
        avg_cpu: float = (total_cpu / len(jobs)) / cpu_count

        self._cpu = f"{avg_cpu:.2f}"
        self._memory = "0.00"
        self._has_been_parsed = True
