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
import re
import subprocess
from datetime import datetime
from logging import Logger, getLogger
from os import chdir
from pathlib import Path
from typing import Union

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

    BASE_HEADER_FILE_PATH: str = "/include/performance_report.tex"

    def __init__(self, archive_directory: str, output_directory: str) -> None:
        self._archive_directory: Path = Path(archive_directory)
        self._data_directory: Path = Path(f"{archive_directory}/visualisation")

        self._output_directory: Path = Path(output_directory)
        self._plots_directory: Path = Path(f"{self._output_directory}/plots")
        # We need to replace all _ characters in the build string as pandoc conversion
        # breaks if there are _ characters in the file anywhere
        self._build_string: str = f"{self._data_directory.parts[-2]}".replace("_", "-")

        report_name = self._generate_report_name()
        self._report_path = Path(f"{output_directory}/{report_name}")

        self._data_files: list[Path] = self._find_data_files()
        self._plot_files: list[Path] = self._find_plot_files()

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
            title=f"{self._generate_report_title()}",
            author="CBT Report Generator",
        )

        self._add_summary_table()
        self._add_plots()
        self._add_configuration_yaml_file()

        # Add a table of contents
        self._report.new_table_of_contents(depth=3)

        # Finally, save the report file in markdown format to the specified
        # outupt directory
        self._save_report()

    def save_as_pdf(self) -> int:
        """
        Convert a report in markdown format and save it as a pdf file.
        To do this we use pandoc.
        """
        # We need to change directory so we can include a relative reference to
        # the plot files
        chdir(self._output_directory)
        header_file: Path = self._create_header_file()

        pdf_file_path: Path = Path(f"{self._output_directory}/{self._report_path.parts[-1][:-2]}pdf")

        pandoc_command: str = (
            f"/usr/bin/env pandoc -H {header_file} -f markdown-implicit_figures "
            + "-V papersize=A4 -V documentclass=report --columns=30 --top-level-division=chapter "
            + f"-o {pdf_file_path} {self._report_path}"
        )

        return_code: int = subprocess.call(
            pandoc_command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
        )
        if return_code != 0:
            log.error("Unable to convert %s to pdf format", f"{self._report_path}")
        else:
            header_file.unlink()

        return return_code

    def _find_data_files(self) -> list[Path]:
        """
        find all the data files in the directory
        """
        unsorted_paths: list[Path] = list(self._data_directory.glob("*.json"))
        return self._sort_list_of_paths(unsorted_paths)

    def _find_plot_files(self) -> list[Path]:
        """
        find plot files and return as a list
        """
        unsorted_paths: list[Path] = list(self._data_directory.glob("*.png"))
        return self._sort_list_of_paths(unsorted_paths)

    def _find_configuration_yaml_file(self) -> Path:
        """
        Find the path to the configuration yaml file in the archive directory
        """
        file_path: list[Path] = list(self._archive_directory.glob("**/cbt_config.yaml"))

        # Each run should only ever have a single yaml file, so we can always
        # use the first element
        return Path(file_path[0])

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
        data: dict[str, Union[str, dict[str, str]]] = {}
        with open(file=file_path, mode="r", encoding="utf8") as file:
            data = json.load(file)

        # The blocksize will be the same for every data point in the file.
        # We can therefore read the blocksize from the first data point
        keys: list[str] = list(data)
        key_data: Union[str, dict[str, str]] = data[keys[0]]
        assert isinstance(key_data, dict)
        blocksize: int = int(int(key_data["blocksize"]) / 1024)
        throughput_key: str = "maximum_iops"
        latency_key: str = "latency_at_max_iops"
        throughput = data[throughput_key]
        assert isinstance(throughput, str)
        max_throughput: float = float(throughput)
        throughput_type: str = "IOps"
        if blocksize >= 64:
            throughput_key = "maximum_bandwidth"
            throughput = data[throughput_key]
            assert isinstance(throughput, str)
            max_throughput = float(float(throughput) / (1000 * 1000))
            throughput_type = "MB/s"
            latency_key = "latency_at_max_bandwidth"

        latency = data[latency_key]
        assert isinstance(latency, str)
        latency_at_maximum_throughput: float = float(latency)

        return (f"{max_throughput:.0f} {throughput_type}", f"{latency_at_maximum_throughput:.1f}")

    def _get_blocksize_percent_operation_from_filename(self, file_name: str) -> tuple[str, str, str]:
        """
        Break down the file name into its constituent parts
        """
        file_parts: list[str] = file_name.split("_")
        operation: str = self.TITLE_CONVERSION[f"{file_parts[-1]}"]
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

    def _generate_report_title(self) -> str:
        """
        Generate the title for the report.

        Any _ must be converted to a - otherwise the pandoc conversion to PDF
        will fail
        """
        title: str = f"Performance Report for {self._build_string}"
        return title

    def _save_report(self) -> None:
        """
        Save the report file to disk
        """
        self._report.create_md_file()

    def _add_summary_table(self) -> None:
        """
        Add a table that contains a summary of the results from the run in
        the format:

        | workload_name | Maximum Throughput |    Latency (ms)|
        | <name>        |       <iops_or_bw> |    <latency_ms>|
        """
        self._report.new_header(level=1, title=f"Summary of results for {self._build_string}")

        # We cannot use the mdutils table object here as it can only justify
        # all the colums in the same way, and we want to justify different
        # columns differently.
        # Therefore we have to build the table ourselves

        self._report.new_line(text="|Workload Name|Maximum Throughput|Latency (ms)|")
        self._report.new_line(text="| :--- | ---: | ---: |")

        data_tables: dict[str, list[str]] = {}
        for _, operation in self.TITLE_CONVERSION.items():
            data_tables[operation] = []

        for file in self._data_files:
            (max_throughput, latency_ms) = self._get_latency_throughput_from_file(file)

            file_root: str = f"{file.parts[-1][:-5]}"
            (_, _, operation) = self._get_blocksize_percent_operation_from_filename(file_root)
            data: str = f"|[{file_root}](#{file_root.replace('_', '-')})|{max_throughput}|{latency_ms}|"

            data_tables[operation].append(data)

        for operation in data_tables.keys():
            for line in data_tables[operation]:
                self._report.new_line(text=line)

    def _add_plots(self) -> None:
        """
        Add the plots to the report.
        We are using a table to get multiple images on a single line
        """
        self._report.new_header(level=1, title="Response Curves")
        empty_table_header: list[str] = ["", ""]
        image_tables: dict[str, list[str]] = {}

        for _, operation in self.TITLE_CONVERSION.items():
            image_tables[operation] = empty_table_header.copy()

        for image_file in self._plot_files:
            (blocksize, percent, operation) = self._get_blocksize_percent_operation_from_filename(
                image_file.parts[-1][:-4]
            )
            title: str = f"{blocksize}K {percent} {operation}"

            image_line: str = self._report.new_inline_image(text=title, path=f"plots/{image_file.parts[-1]}")
            anchor: str = f'<a name="{image_file.parts[-1][:-4].replace("_", "-")}"></a>'

            image_line = f"{anchor}{image_line}"

            image_tables[operation].append(image_line)

        # Create the correct sections and add a table for each section to the report

        for section in image_tables.keys():
            # We don't want to display a section if it doesn't contain any plots
            if len(image_tables[section]) > len(empty_table_header):
                self._report.new_header(level=2, title=section)
                table_images = image_tables[section]

                # We need to calculate the rumber of rows, but new_table() requires the
                # exact number of items to fill the table, so we may need to add a dummy
                # entry at the end
                number_of_rows: int = len(table_images) // 2
                if len(table_images) % 2 > 0:
                    number_of_rows += 1
                    table_images.append("")
                self._report.new_table(columns=2, rows=number_of_rows, text=table_images, text_align="center")

    def _add_configuration_yaml_file(self) -> None:
        """
        Add the configuration yaml file to the report
        """

        self._report.new_header(level=1, title="Configuration yaml")
        yaml_file_path: Path = self._find_configuration_yaml_file()

        file_contents: str = yaml_file_path.read_text()
        safe_contents = self._strip_confidential_data_from_yaml(file_contents)
        markdown_string: str = f"```{safe_contents}```"

        self._report.new_paragraph(markdown_string)

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

    def _sort_list_of_paths(self, paths: list[Path]) -> list[Path]:
        """
        Sort a list of path files into numerical order of the file name
        """
        sorted_paths: list[Path] = []

        # All the files will have the same parent directory
        file_root_dir: Path = paths[0].parent
        file_names: list[str] = [x.parts[-1] for x in paths]
        sorted_filenames: list[str] = sorted(file_names, key=lambda a: int(a.split("_")[0][:-1]))

        for file_name in sorted_filenames:
            sorted_paths.append(Path(f"{file_root_dir}/{file_name}"))

        return sorted_paths

    def _create_header_file(self) -> Path:
        """
        Create the header file in tex format that is used to provide
        headers and footers when the report is created in pdf format.

        Replace any placeholders with the correct values.
        """
        # Note: This currently only enters the build string, but it could be
        # expanded in the future to give more detals
        cbt_directory: Path = Path(__file__).parent
        base_header_file: Path = Path(f"{cbt_directory}/include/performance_report.tex")

        output_path: Path = Path(f"{self._output_directory}/perf_report.tex")

        try:
            contents: str = base_header_file.read_text()
            contents = contents.replace("BUILD", self._build_string)
            output_path.write_text(contents)
        except FileNotFoundError:
            log.error("Unable to read from %s", base_header_file)
        except PermissionError:
            log.error("Unable to write to %s", output_path)

        return output_path

    def _strip_confidential_data_from_yaml(self, yaml_data: str) -> str:
        """
        Remove any confidential data from a string of yaml files

        Currently handles hostnames, IPv4 addresses and IPv6 addresses
        """
        filtered_text: str = yaml_data

        ip_v4_pattern = re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b")
        ip_v6_pattern = re.compile(
            r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}|\s::(?:[0-9a-fA-F]{1,4}:){0,6}[0-9a-fA-F]{1,4}|$"
            + r"\b[0-9a-fA-F]{1,4}::(?:[0-9a-fA-F]{1,4}:){0,5}[0-9a-fA-F]{1,4}|$"
            + r"\b[0-9a-fA-F]{1,4}:[0-9a-fA-F]{1,4}::(?:[0-9a-fA-F]{1,4}:){0,4}[0-9a-fA-F]{1,4}|$"
            + r"\b(?:[0-9a-fA-F]{1,4}:){0,2}[0-9a-fA-F]{1,4}::(?:[0-9a-fA-F]{1,4}:){0,3}[0-9a-fA-F]{1,4}|$"
            + r"\b(?:[0-9a-fA-F]{1,4}:){0,3}[0-9a-fA-F]{1,4}::(?:[0-9a-fA-F]{1,4}:){0,2}[0-9a-fA-F]{1,4}|$"
            + r"\b(?:[0-9a-fA-F]{1,4}:){0,4}[0-9a-fA-F]{1,4}::(?:[0-9a-fA-F]{1,4}:)?[0-9a-fA-F]{1,4}|$"
            + r"\b(?:[0-9a-fA-F]{1,4}:){0,5}[0-9a-fA-F]{1,4}::[0-9a-fA-F]{1,4}|$"
            + r"\b(?:[0-9a-fA-F]{1,4}:){0,6}[0-9a-fA-F]{1,4}::$"
        )
        hostname_pattern = re.compile(r"\s(?:[a-z0-9-]{1,61}\.){1,7}[a-z0-9-]{1,61}", re.IGNORECASE)

        ip_addresses_to_replace: list[str] = ip_v4_pattern.findall(yaml_data)
        ip_addresses_to_replace.extend(ip_v6_pattern.findall(yaml_data))

        unique_ip_addresses_to_replace: list[str] = []
        for item in ip_addresses_to_replace:
            if item.strip() not in unique_ip_addresses_to_replace:
                unique_ip_addresses_to_replace.append(item.strip())

        for item in unique_ip_addresses_to_replace:
            filtered_text = filtered_text.replace(item, "--- IP Address --")

        hostnames_to_replace: list[str] = hostname_pattern.findall(yaml_data)

        unique_host_names_to_replace: list[str] = []
        for item in hostnames_to_replace:
            if item.strip() not in unique_host_names_to_replace:
                unique_host_names_to_replace.append(item.strip())

        count: int = 1
        for value in unique_host_names_to_replace:
            filtered_text = filtered_text.replace(value.strip(), f"--- server{count} ---")
            count += 1

        return filtered_text
