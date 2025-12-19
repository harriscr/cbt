"""
A file containing the classes and code required to read a file stored in the common
intermediate format introduced in PR 319 (https://github.com/ceph/cbt/pull/319) and produce a hockey-stick curve graph
"""

from abc import ABC, abstractmethod
from logging import Logger, getLogger
from pathlib import Path

# the ModuleType does exists in the types module, so no idea why pylint is
# flagging this
from types import ModuleType  # pylint: disable=[no-name-in-module]
from typing import Optional

from matplotlib.axes import Axes
from matplotlib.figure import Figure

from post_processing.common import (
    DATA_FILE_EXTENSION_WITH_DOT,
    PLOT_FILE_EXTENSION,
    get_blocksize_percentage_operation_from_file_name,
)
from post_processing.plotter.cpu_plotter import CPUPlotter
from post_processing.plotter.io_plotter import IOPlotter
from post_processing.post_processing_types import CommonFormatDataType, PlotDataType

log: Logger = getLogger("plotter")

CPU_PLOT_DEFAULT_COLOUR: str = "#5ca904"


# pylint: disable=too-few-public-methods, too-many-locals
class CommonFormatPlotter(ABC):
    """
    The base class for plotting results curves
    """

    def __init__(self, plotter: ModuleType) -> None:
        self._plotter = plotter

    @abstractmethod
    def draw_and_save(self) -> None:
        """
        Produce the plot file(s) for each of the intermediate data files in the
        given directory and save them to disk
        """

    @abstractmethod
    def _generate_output_file_name(self, files: list[Path]) -> str:
        """
        Generate the name for the file the plot will be saved to.
        """

    def _add_title(self, source_files: list[Path]) -> None:
        """
        Given the source file full path, generate the title for the
        data plot and add it to the plot
        """

        title: str = ""

        if len(source_files) == 1:
            title = self._construct_title_from_file_name(source_files[0].parts[-1])
        else:
            title = self._construct_title_from_list_of_file_names(source_files)

        self._plotter.title(title)

    def _construct_title_from_list_of_file_names(self, file_paths: list[Path]) -> str:
        """
        Given a list of file paths construct a plot title.

        If there is a common element then the title will be
        '<common_element> comparison'
        e.g if all files had a blocksize = 16K the title would be
        '16k blocksize comparison'
        """
        titles: list[tuple[str, str, str]] = []
        blocksizes: list[str] = []
        read_percents: list[str] = []
        operations: list[str] = []

        for file in file_paths:
            (blocksize, read_percent, operation) = get_blocksize_percentage_operation_from_file_name(file.stem)
            titles.append((blocksize, read_percent, operation))

            if blocksize not in blocksizes:
                blocksizes.append(blocksize)
            if read_percent not in read_percents:
                read_percents.append(read_percent)
            if operation not in operations:
                operations.append(operation)

        if len(blocksizes) == 1:
            return f"{blocksizes[0]} blocksize comparison"

        if len(operations) == 1 and len(read_percents) == 1:
            return f"{read_percents[0]} {operations[0]} comparison"

        if len(operations) == 1:
            return f"{operations[0]} comparison"

        title: str = " ".join(titles.pop(0))
        for details in titles:
            title += "\nVs "
            title += " ".join(details)

        return title

    def _construct_title_from_file_name(self, file_name: str) -> str:
        """
        given a single file name construct a plot title from the blocksize,
        read percent and operation contained in the title
        """
        (blocksize, read_percent, operation) = get_blocksize_percentage_operation_from_file_name(
            file_name[: -len(DATA_FILE_EXTENSION_WITH_DOT)]
        )

        return f"{blocksize} {read_percent} {operation}"

    def _set_axis(self, maximum_values: Optional[tuple[int, int]] = None) -> None:
        """
        Set the range for the plot axes.

        maximum_values is a

        This will start from 0, with a maximum
        """
        maximum_x: Optional[int] = None
        maximum_y: Optional[int] = None

        if maximum_values is not None:
            maximum_x = maximum_values[0]
            maximum_y = maximum_values[1]

        self._plotter.xlim(0, maximum_x)
        self._plotter.ylim(0, maximum_y)

    def _sort_plot_data(self, unsorted_data: CommonFormatDataType) -> PlotDataType:
        """
        Sort the data read from the file by queue depth
        """
        keys: list[str] = [key for key in unsorted_data.keys() if isinstance(unsorted_data[key], dict)]
        plot_data: PlotDataType = {}
        sorted_plot_data: PlotDataType = {}
        for key, data in unsorted_data.items():
            if isinstance(data, dict):
                plot_data[key] = data

        sorted_keys: list[str] = sorted(keys, key=int)
        for key in sorted_keys:
            sorted_plot_data[key] = plot_data[key]

        return sorted_plot_data

    def _add_single_file_data_with_optional_errorbars(
        self,
        file_data: CommonFormatDataType,
        plot_error_bars: bool = False,
        plot_resource_usage: bool = False,
        label: Optional[str] = None,
    ) -> Figure:
        """
        Add the data from a single file to a plot. Include error bars. Each point
        in the plot is the latency vs IOPs or bandwidth for a given queue depth.

        The plot will have red error bars with a blue plot line
        """
        io_plot_label: str = label if label else "IO Details"

        figure: Figure
        io_axis: Axes
        figure, io_axis = self._plotter.subplots()

        cpu_plotter: CPUPlotter = CPUPlotter(main_axis=io_axis)
        io_plotter: IOPlotter = IOPlotter(main_axis=io_axis)
        io_plotter.y_label = "Latency (ms)"
        io_plotter.plot_label = io_plot_label

        sorted_plot_data: PlotDataType = self._sort_plot_data(file_data)

        x_data: list[float] = []
        error_bars: list[float] = []
        capsize: int = 0

        for _, data in sorted_plot_data.items():
            # for blocksize less than 64K we want to use the bandwidth to plot the graphs,
            # otherwise we should use iops.
            blocksize: int = int(int(data["blocksize"]) / 1024)
            if blocksize >= 64:
                # convert bytes to Mb, not Mib, so use 1000s rather than 1024
                x_data.append(float(data["bandwidth_bytes"]) / (1000 * 1000))
                io_axis.set_xlabel("Bandwidth (MB/s)")  # pyright: ignore[reportUnknownMemberType]
            else:
                x_data.append(float(data["iops"]))
                io_axis.set_xlabel("IOps")  # pyright: ignore[reportUnknownMemberType]
                # The stored values are in ns, we want to convert to ms

            io_plotter.add_y_data(data["latency"])

            # If we don't have CPU data in the intermediate files, then there's
            # no point in trying to plot a CPU line
            if data.get("cpu", None) is None and plot_resource_usage:
                log.warning("Unable to plot CPU usage as the CPU data does not exist")
                plot_resource_usage = False

            if plot_resource_usage:
                cpu_plotter.add_y_data(data.get("cpu", ""))
                plot_error_bars = False

            if plot_error_bars:
                error_bars.append(float(data["std_deviation"]) / (1000 * 1000))
                capsize = 3
            else:
                error_bars.append(0)
                capsize = 0

        io_plotter.plot_with_error_bars(x_data=x_data, error_data=error_bars, cap_size=capsize)

        if plot_resource_usage:
            cpu_plotter.plot(x_data=x_data)

        return figure

    def _save_plot(self, file_path: str) -> None:
        """
        save the plot to disk as a svg file

        The bbox_inches="tight" option makes sure that the legend is included
        in the plot and not cut off
        """
        self._plotter.savefig(file_path, format=f"{PLOT_FILE_EXTENSION}", bbox_inches="tight")

    def _clear_plot(self) -> None:
        """
        Clear the plot data
        """
        self._plotter.close()
        self._plotter.clf()
