"""Shared result types for benchmark comparison.

``DataAnalyzer`` is the abstract interface for extracting summary metrics from
a single benchmark run directory.  ``Result`` is a single baseline comparison
outcome produced by :meth:`~benchmark.benchmark.Benchmark.evaluate`.

These are kept in their own module so that ``benchmark.benchmark`` does not need
to import them and so that analyzer implementations (e.g. ``RadosBenchAnalyzer``)
can inherit from ``DataAnalyzer`` without creating a circular import.
"""

from abc import ABC, abstractmethod
from typing import Any


class DataAnalyzer(ABC):
    """Abstract interface for extracting summary metrics from a benchmark run."""

    def __init__(self, archive_dir: str, run: str, host: str, proc: int) -> None:  # pylint: disable=unused-argument
        super().__init__()
        self.archive_dir = archive_dir

    @abstractmethod
    def get_cpu_cycles_per_op(self) -> Any:
        """Return the CPU cycles per operation."""

    @abstractmethod
    def get_latency_avg(self) -> Any:
        """Return the average latency."""

    @abstractmethod
    def get_bandwidth(self) -> Any:
        """Return the bandwidth."""

    @abstractmethod
    def get_iops_avg(self) -> Any:
        """Return the average IOPS."""

    @abstractmethod
    def get_iops_stddev(self) -> Any:
        """Return the IOPS standard deviation."""


class Result:  # pylint: disable=too-few-public-methods
    """A single baseline comparison result."""

    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self, run: str, alias: str, result: float, baseline: float, stmt: str, accepted: bool
    ) -> None:
        self.run = run
        self.alias = alias
        self.result = result
        self.baseline = baseline
        self.stmt = stmt
        self.accepted = accepted

    def __str__(self) -> str:
        fmt = "{run}: {alias}: {stmt}:: {result}/{baseline}  => {status}"
        return fmt.format(
            run=self.run,
            alias=self.alias,
            stmt=self.stmt,
            result=self.result,
            baseline=self.baseline,
            status="accepted" if self.accepted else "rejected",
        )
