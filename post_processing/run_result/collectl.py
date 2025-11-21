"""
A RunResult class that deals with reading copllectl results and parsing them
into the common output format
"""

import re
from logging import Logger, getLogger
from pathlib import Path
from typing import Any

from post_processing.run_result.resource_result import ResourceResult

log: Logger = getLogger("formatter")


class Collectl(ResourceResult):
    """
    Collectl results processing
    """

    def _get_resource_output_file_from_file_path(self, file_path: Path) -> Path:
        # The collectl results are stored in a collectl directory in the
        # <bs_io_type><numjobs>/<total_iodepth>/<iodepth>/ directory so
        # already saved in a helpful directory structure
        resource_directory: Path = Path(f"{file_path.parent}/collectl")
        resource_files: list[Path] = [path for path in resource_directory.glob("**/*.cpu")]
        # There should only ever be one *.cpu file, but if there are more always use the first
        # one anyway
        if len(resource_files) > 1:
            log.warning(
                "More than one *.cpu file found in directory %s, using the first entry only: %s",
                resource_directory,
                resource_files[0],
            )
        return resource_files[0]

    def _parse(self, data: dict[str, Any]) -> tuple[str, str]:
        return super()._parse(data)
        # The data format here is:
        # {'#Date': '20250715','Time': '14:40:08',
        #'[CPU:0]Guest%': '0','[CPU:0]GuestN%': '0','[CPU:0]Idle%': '47',
        #'[CPU:0]Intrpt': '0','[CPU:0]Irq%': '2','[CPU:0]Nice%': '0',
        #'[CPU:0]Soft%': '2','[CPU:0]Steal%': '0','[CPU:0]Sys%': '13',
        #'[CPU:0]Totl%': '53','[CPU:0]User%': '37','[CPU:0]Wait%': '1',
        #
        #'[CPU:100]Guest%': '0','[CPU:100]GuestN%': '0','[CPU:100]Idle%': '50',
        #'[CPU:100]Intrpt': '0','[CPU:100]Irq%': '1','[CPU:100]Nice%': '0',
        #'[CPU:100]Soft%': '1','[CPU:100]Steal%': '0','[CPU:100]Sys%': '12',
        #'[CPU:100]Totl%': '50','[CPU:100]User%': '35','[CPU:100]Wait%': '1',
        #
        # and so on for each CPU in the machine

    def _read_file(self, line_separator: str = ",") -> dict[str, dict[str, str]]:
        # we need to cope with the different collectl output file formats here
        # The ones we know about are:
        # - Summary
        # - Detail file
        # - Others??? Top style, per-process?
        if self._contains_summary_data():
            return self._read_summary_file(line_separator)
        return {}

    def _read_summary_file(self, line_separator: str = ",") -> dict[str, dict[str, str]]:
        """
        If the collectl file contains summary data then this is the method we
        can use to parse the file
        """
        raw_data: dict[str, dict[str, str]] = {}

        filtered_lines: list[str] = [
            line
            for line in self._resource_file_path.read_text(encoding="utf-8").splitlines()
            if not line.startswith("# ") and not line.startswith("##")
        ]

        headings: list[str] = filtered_lines.pop(0).split(line_separator)
        for line in filtered_lines:
            raw_data.update({line[1]: dict(zip(headings, line))})

        return raw_data

    def _contains_summary_data(self) -> bool:
        """
        does the file contain collectl summary data
        """
        summary_data: bool = True
        for line in self._resource_file_path.read_text(encoding="utf-8").splitlines():
            if re.search(r"[CPU\d+]", line):
                summary_data = False
        return summary_data
