"""
A class that encapsulates the resource usage results from a benchmark run

This could be CPU, Memory etc
"""

from abc import ABC, abstractmethod
from logging import Logger, getLogger
from pathlib import Path
from typing import Any

from post_processing.common import file_is_empty

log: Logger = getLogger("formatter")


class ResourceResult(ABC):
    """
    This is the top level class for a resource run result. As each
    resource monitoring toop produces different output results we will need a
    sub-class for each type
    """

    def __init__(self, file_path: Path) -> None:
        self._resource_file_path: Path = self._get_resource_output_file_from_file_path(file_path)
        self._cpu: str = ""
        self._memory: str = ""
        self._has_been_parsed: bool = False

    @property
    def cpu_statistics(self) -> str:
        """
        The CPU usage statistics for this particular workload
        """
        return self._cpu

    @property
    def memory_statistics(self) -> str:
        """
        The memory usage statistics
        """
        return self._memory

    @abstractmethod
    def _get_resource_output_file_from_file_path(self, file_path: Path) -> Path:
        """
        Given a particular resource file name find the corresponding
        resource usage statistics file path
        """

    @abstractmethod
    def _parse(self, data: dict[str, Any]) -> tuple[str, str]:
        """
        Read the resource usage data from the read data and return the
        relevant resource usage statistics
        """

    @abstractmethod
    def _read_results_from_file(self) -> dict[str, Any]:
        """
        Read the data from the results file and return the results in a dict
        """

    def _add_data_to_common_format_file(self) -> None:
        """
        Add the data from the resource monitoring into the common output
        format file for this test run
        """
        if file_is_empty(self._resource_file_path):
            log.warning("Unable to process file %s as it is empty", self._resource_file_path)
            return

        raw_data = self._read_results_from_file()
        self._parse(raw_data)

        # TODO: add the data to the results file

        # The following should be in the fio sub module
        # try:
        #    with self._resource_file_path.open("r", encoding="utf-8") as file:
        #        data: dict[str, Any] = json.load(file)
        #        self._cpu, self._memory = self._parse(data)
        #        self._has_been_parsed = True

        # except json.JSONDecodeError:
        #    log.warning("Unable to process file %s as it is not in json format", self._resource_file_path)
