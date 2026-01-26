"""
A file containing the classes and code required to read a file stored in the common
intermediate format introduced in PR 319 (https://github.com/ceph/cbt/pull/319) and
produce a hockey-stick curve graph
"""

from pathlib import Path

import matplotlib.pyplot as plotter
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from post_processing.common import (
    DATA_FILE_EXTENSION,
    DATA_FILE_EXTENSION_WITH_DOT,
    PLOT_FILE_EXTENSION,
    read_intermediate_file,
)
from post_processing.plotter.common_format_plotter import CommonFormatPlotter
from post_processing.post_processing_types import CommonFormatDataType


# pylint: disable=too-few-public-methods
class SimplePlotter(CommonFormatPlotter):
    """
    Read the intermediate data file in the common json format and produce a hockey-stick
    curve plot that includes standard deviation error bars.
    """

    def __init__(self, archive_directory: str, plot_error_bars: bool, plot_resources: bool) -> None:
        # A Path object for the directory where the data files are stored
        self._path: Path = Path(f"{archive_directory}/visualisation")
        self._plot_error_bars: bool = plot_error_bars
        self._plot_resources: bool = plot_resources
        super().__init__(plotter)

    def draw_and_save(self) -> None:
        for file_path in self._path.glob(f"*{DATA_FILE_EXTENSION_WITH_DOT}"):
            file_data: CommonFormatDataType = read_intermediate_file(f"{file_path}")
            output_file_path: str = self._generate_output_file_name(files=[file_path])

            figure: Figure
            io_axis: Axes
            figure, io_axis = self._plotter.subplots()

            self._add_single_file_data_with_optional_errorbars(
                file_data=file_data,
                main_axes=io_axis,
                plot_error_bars=self._plot_error_bars,
                plot_resource_usage=self._plot_resources,
            )
            self._add_title(source_files=[file_path])
            self._set_axis()

            # make sure we add the legend to the plot
            figure.legend(  # pyright: ignore[reportUnknownMemberType]
                bbox_to_anchor=(0.5, -0.1),
                loc="upper center",
                ncol=2,
            )

            self._save_plot(file_path=output_file_path)
            self._clear_plot()

    def _generate_output_file_name(self, files: list[Path]) -> str:
        # we know we will only ever be passed a single file name
        return f"{str(files[0])[: -len(DATA_FILE_EXTENSION)]}{PLOT_FILE_EXTENSION}"
