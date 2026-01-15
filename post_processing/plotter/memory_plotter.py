"""
A file containing the classes and code required to add a memory usage
data line to a plot
"""

from logging import Logger, getLogger
from typing import Union

from post_processing.plotter.axis_plotter import AxisPlotter

log: Logger = getLogger("plotter")

MEMORY_PLOT_DEFAULT_COLOUR: str = "#4b006e"
MEMORY_Y_LABEL: str = "Memory use (Mb)"
MEMORY_PLOT_LABEL: str = "Memory use"


class MemoryPlotter(AxisPlotter):
    """
    A class to add the resource use measurements to a plot as separate axes
    """

    def add_y_data(self, data_value: str) -> None:
        """
        Add a point of memory usage data for this plot

        :param memory_value: A single value for memory usage
        :type memory_value: str
        """
        self._y_data.append(float(data_value))

    def plot(self, x_data: list[Union[int, float]], colour: str = "") -> None:
        memory_axis = self._main_axes.twinx()
        self._label = MEMORY_PLOT_LABEL
        self._y_label = MEMORY_Y_LABEL
        self._plot(x_data=x_data, axis=memory_axis, colour=MEMORY_PLOT_DEFAULT_COLOUR)
