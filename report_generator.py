"""
Code to automatically generate a report from a direcotry containing a set of performance
results in the intermediate format in PR 319.

The report will be generated in markdowm format using the create_report() method and the
resulting file saved to the specified output directory.

Optionally the markdown report can be converted to a pdf using pandoc by calling save_as_pdf()
The pdf file will have the same name as the markdown file, and be saved in the same output
directory.
"""
# Note:
# There is some common code here between this module and the code in PR 321, and
# this will be addressed in a future PR

import json
import subprocess
from datetime import datetime
from logging import Logger, getLogger
from os import chdir
from pathlib import Path
from typing import Any

# It seems that the mdutils package doesn't contain library stubs or a py.typed
# marker, which causes an error here. This is an issue that would need to be
# fixed in the mdutils library, so we will have to ignore the error for the
# moment
from mdutils.mdutils import MdUtils  # type:  ignore [import-untyped]

log: Logger = getLogger("cbt")

# TODO: Need to build this on top of the plot generation work. Need to pull out
# common methods into a common file


class ReportGenerator:
    """
    Responsible for generating a report
    """

    # the table headers for the summary table
    TABLE_HEADERS: list[str] = ["Workload Name", "Maximum Throughput", "Latency (ms)"]

    # A conversion between the operation type in the intermediate file format
    # and a human-readable string
    TITLE_CONVERSION: dict[str, str] = {
        "read": "Sequential Read",
        "write": "Sequential Write",
        "randread": "Random Read",
        "randwrite": "Random Write",
        "readwrite": "Sequential Read/Write",
        "randrw": "Random Read/Write",
    }

    def __init__(self, archive_directory: str, output_directory: str) -> None:
        self._data_directory: Path = Path(f"{archive_directory}/visualisation")

        self._output_directory: Path = Path(output_directory)
        self._plots_directory: Path = Path(f"{self._output_directory}/plots")
        # TODO: add date/time stamp to report
        report_name = self._generate_report_name()
        self._report_path = Path(f"{output_directory}/{report_name}")

        self._data_files: list[Path] = self._find_data_files()
        self._plot_files: list[Path] = self._find_plot_files()
        self._configuration_yaml: str = self._find_configuration_yaml_file(archive_directory)

        self._report: MdUtils

    def create_report(self) -> None:
        """
        Read the data files and generate a report from them and the
        """
        if not self._plot_files_exist():
            # TODO: we should add the simple plotter in here, or just raise
            # an error and exit?
            pass

        # Copy all the png files to a plots subrirectory of the output directory
        # specified
        self._create_plots_results_directory()
        self._copy_images()

        self._report = MdUtils(
            file_name=f"{self._report_path}",
            title=f"Performance Report for {self._data_directory.parts[-2]}",
            author="CBT Report Generator",
        )

        self._report.new_header(level=1, title="Performance Report")

        self._add_summary_table()
        self._add_plots()

        # Add a table of contents
        self._report.new_table_of_contents(table_title="Contents", depth=3)

        # Finally, save the report file in markdown format to the specified
        # outupt directory
        self._save_report()

    def save_as_pdf(self) -> int:
        """
        Convert a report in markdown format and save it as a pdf file.
        To do this we use pandoc.

        Unfortunately some older versions of pandoc do not render images correctly
        when converting from markdown to pdf, so we need to do some mangline of the
        original markdown file
        """
        chdir(self._output_directory)
        pdf_file_path: Path = Path(f"{self._output_directory}/{self._report_path.parts[-1][:-2]}pdf")
        return_code: int = subprocess.call(
            f"pandoc -f markdown-implicit_figures -V geometry:margin=1cm --column=50 -o {pdf_file_path} {self._report_path}",
            shell=True,
        )
        if return_code != 0:
            log.error("Unable to convert %s to pdf format", f"{self._report_path}")
        return return_code

    def _find_data_files(self) -> list[Path]:
        """
        find all the data files in the directory
        """
        return list(self._data_directory.glob("*.json"))

    def _find_plot_files(self) -> list[Path]:
        """
        find plot files and return as a list
        """
        return list(self._data_directory.glob("*.png"))

    def _find_configuration_yaml_file(self, archive_directory: str) -> str:
        """
        Find the path to the configuration yaml file in the archive directory
        """
        file_path: list[Path] = list(Path(archive_directory).glob("**/cbt_config.yaml"))

        # Each run should only ever have a single yaml file, so we can always
        # use the first element
        return f"{file_path[0]}"

    def _plot_files_exist(self) -> bool:
        """
        return true if plot files exist for all the data files
        """
        number_of_plot_files: int = len(list(self._plot_files))
        number_of_data_files: int = len(list(self._data_files))

        return number_of_plot_files == number_of_data_files

    def _get_latency_throughput_from_file(self, file_path: Path) -> tuple[str, str]:
        """
        Reads the data stored in the intermediate file format and returns the
        maximum throughput in either iops or MB/s, and the latency in ms recorded
        for that throughput
        """
        data: dict[Any, Any] = {}
        with open(file=file_path, mode="r", encoding="utf8") as file:
            data = json.load(file)

        # The blocksize will be the same for every data point in the file.
        # We can therefore read the blocksize from the first data point
        keys: list[int] = list(data)
        blocksize: int = int(int(data[keys[0]]["blocksize"]) / 1024)
        throughput_key: str = "maximum_iops"
        latency_key: str = "latency_at_max_iops"
        max_throughput: float = float(data[throughput_key])
        throughput_type: str = "IOps"
        if blocksize >= 64:
            throughput_key = "maximum_bandwidth"
            max_throughput = float(float(data[throughput_key]) / (1000 * 1000))
            throughput_type = "MB/s"
            latency_key = "latency_at_max_bandwidth"

        latency_at_maximum_throughput: float = float(data[latency_key])

        return (f"{max_throughput:.4f} {throughput_type}", f"{latency_at_maximum_throughput:.4f}")

    def _get_blocksize_percent_operation_from_filename(self, file_name: str) -> tuple[str, str, str]:
        """ """
        file_parts: list[str] = file_name.split("_")
        operation: str = self.TITLE_CONVERSION[f"{file_parts[-1][:-4]}"]
        blocksize: str = f"{int(int(file_parts[0][:-1]) / 1024)}"
        read_write_percent: str = ""
        if len(file_parts) > 2:
            read_write_percent = f"{file_parts[1]}/{file_parts[2]}"

        return (f"{blocksize}", read_write_percent, operation)

    def _generate_report_name(self) -> str:
        """
        The report name is of the format:
            performance_report_yymmdd_hhmmss.md
        """
        current_datetime: datetime = datetime.now()

        # Convert to string
        datetime_string: str = current_datetime.strftime("%y%m%d_%H%M%S")
        output_file_name: str = f"performance_report_{datetime_string}.md"
        return output_file_name

    def _save_report(self) -> None:
        """
        Save the report file to disk
        """
        self._report.create_md_file()

    def _add_summary_table(self) -> None:
        """
        Add a table that contains a summary of the results from the run in
        the format:

        | workload_name | Maximum Throughput       | Latency (ms)      |
        | <name>        | <iops_or_bw>             | <latency_ms>  |
        """
        self._report.new_header(level=2, title="Summary of results")

        table_data: list[str] = self.TABLE_HEADERS
        rows: int = 1

        for file in self._data_files:
            (max_throughput, latency_ms) = self._get_latency_throughput_from_file(file)
            data: list[str] = [f"{file.parts[-1][:-5]}", f"{max_throughput}", f"{latency_ms}"]
            table_data.extend(data)
            rows += 1

        self._report.new_table(columns=3, rows=rows, text=table_data, text_align="left")

    def _add_plots(self) -> None:
        """
        Add the plots to the report.
        We are using a table to get multiple images on a single line
        """
        self._report.new_header(level=2, title="Response Curves")
        table_data: list[str] = ["", ""]

        for image_file in self._plot_files:
            (blocksize, percent, operation) = self._get_blocksize_percent_operation_from_filename(
                list(image_file.parts)[-1]
            )
            title: str = f"{blocksize}K {percent} {operation}"
            image_line: str = self._report.new_inline_image(text=title, path=f"plots/{image_file.parts[-1]}")
            table_data.append(image_line)

        # We need to calculate the rumber of rows, but new_table() requires the
        # exact number of items to fill the table, so we may need to add a dummy
        # entry at the end
        number_of_rows: int = len(table_data) // 2
        if len(table_data) % 2 > 0:
            number_of_rows += 1
            table_data.append("")
        self._report.new_table(columns=2, rows=number_of_rows, text=table_data, text_align="center")

    def _create_plots_results_directory(self) -> None:
        """
        Create the plots sub-directory in the output directory
        """
        subprocess.call(f"mkdir -p {self._plots_directory}", shell=True)

    def _copy_images(self) -> None:
        """
        Copy the plot files to a 'plots' subdirectory in the output directory
        so the markdown can link to them using a known relative path
        """
        for plot_file in self._plot_files:
            subprocess.call(f"cp {plot_file} {self._plots_directory}/", shell=True)
