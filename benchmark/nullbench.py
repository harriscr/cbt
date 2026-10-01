"""Nullbench benchmark — no-op placeholder for testing the CBT framework."""

from benchmark.benchmark import Benchmark


class Nullbench(Benchmark):
    """Null benchmark that performs no actual I/O operations.

    Delegates entirely to :class:`~benchmark.benchmark.Benchmark` for lifecycle
    management.  Useful for exercising the CBT orchestration pipeline without
    requiring a live Ceph cluster or benchmark binary.
    """

    @property
    def benchmark_type(self) -> str:
        return "nullbench"

    def setup_targets(self) -> None:
        """Nullbench has no targets to set up."""

    def cleanup_targets(self) -> None:
        """Nullbench has no targets to clean up."""

    def __str__(self) -> str:  # pylint: disable=useless-parent-delegation
        return super().__str__()
