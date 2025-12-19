"""
A file containing the classes and code required to add an IO usage
data line to a plot
"""

from logging import Logger, getLogger

from post_processing.plotter.axis_plotter import AxisPlotter

log: Logger = getLogger("plotter")

IO_PLOT_DEFAULT_COLOUR: str = "#5ca904"
IO_Y_LABEL: str = "CPU use (%)"
IO_PLOT_LABEL: str = "CPU use"


class IOPlotter(AxisPlotter):
    """
    A class to add the resource use measurements to a plot as separate axes
    """

    def add_y_data(self, data_value: str) -> None:
        """
        Add a point of CPU data for this plot

        :param cpu_value: A single value for CPU usage
        :type cpu_value: str
        """
        self._y_data.append(float(data_value) / (1000 * 1000))

    def plot(self, x_data: list[float], colour: str = "") -> None:
        """
        This should never be called for an IO plot, so assert if it is
        """
        raise NotImplementedError

    def plot_with_error_bars(self, x_data: list[float], error_data: list[float], cap_size: int) -> None:
        """
        Docstring for plot_with_error_bars

        :param x_data: The data for the x-axis
        :type x_data: list[float]
        :param error_data: the error bar data
        :type error_data: list[float]
        :param colour: The colour for the I/O line
        :type colour: str
        """
        io_axis = self._main_axes
        io_axis.set_ylabel(self._y_label)  # pyright: ignore[reportUnknownMemberType]
        # io_axis.tick_params(axis="y")  # pyright: ignore[reportUnknownMemberType]
        io_axis.errorbar(  # pyright: ignore[reportUnknownMemberType]
            x_data, self._y_data, yerr=error_data, fmt="+-", capsize=cap_size, ecolor="red", label=self._label
        )
