"""
The base class that reads a results file and converts it into the
common data format that can be plotted
"""

from abc import ABC, abstractmethod
from logging import Logger, getLogger
from pathlib import Path

from post_processing.common import file_is_empty, file_is_precondition
from post_processing.post_processing_types import InternalFormattedOutputType

log: Logger = getLogger("formatter")


class RunResult(ABC):
    """
    A result run file that needs processing
    """

    def __init__(self, directory: Path, file_name_root: str) -> None:
        self._path: Path = directory
        self._has_been_processed: bool = False

        self._files: list[Path] = self._find_files_for_testrun(file_name_root=file_name_root)
        self._processed_data: InternalFormattedOutputType = {}

    @abstractmethod
    def _find_files_for_testrun(self, file_name_root: str) -> list[Path]:
        """
        Find the relevant output files for this type of benchmark run

        These will be specific to a benchmark type or data type
        """

    @abstractmethod
    def _convert_file(self, file_path: Path) -> None:
        """
        convert the contents of a single output file from the run into the
        JSON format we want for writing the graphs
        """

    def process(self) -> None:
        """
        Convert the results data from all the individual files that make up this
        result into the standard intermediate format
        """
        number_of_volumes_for_test_run: int = len(self._files)

        if number_of_volumes_for_test_run > 0:
            self._process_test_run_files()
        else:
            log.warning("test run with directory %s has no files - not doing any conversion", self._path)

        self._has_been_processed = True

    def have_been_processed(self) -> bool:
        """
        True if we have already processed the files for this set of results,
        otherwise False
        """
        return self._has_been_processed

    def get(self) -> InternalFormattedOutputType:
        """
        Return the processed results
        """

        if not self._has_been_processed:
            self.process()

        return self._processed_data

    def _process_test_run_files(self) -> None:
        """
        If there is only details for a single volume then we can convert the
        data from the fio output directly into our output format
        """
        for file_path in self._files:
            if not file_is_empty(file_path):
                if not file_is_precondition(file_path):
                    log.debug("Processing file %s", file_path)
                    self._convert_file(file_path)
                else:
                    log.warning("Not processing file %s as it is from a precondition operation", file_path)
                    self._files.remove(file_path)
            else:
                log.warning("Cannot process file %s as it is empty", file_path)
