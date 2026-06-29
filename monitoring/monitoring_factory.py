"""Factory class for creating and managing monitoring backends."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, ClassVar, Optional

import settings
from monitoring.base import Monitoring
from monitoring.blktrace_monitoring import BlktraceMonitoring
from monitoring.collectl_monitoring import CollectlMonitoring
from monitoring.perf_monitoring import PerfMonitoring
from monitoring.top_monitoring import TopMonitoring


class MonitoringFactory:
    """Instantiates monitoring backends and owns the lifecycle API."""

    _REGISTRY: ClassVar[dict[str, type[Monitoring]]] = {
        "collectl": CollectlMonitoring,
        "perf": PerfMonitoring,
        "blktrace": BlktraceMonitoring,
        "top": TopMonitoring,
    }

    @classmethod
    def get_object(cls, name: str, mconfig: dict[str, Any]) -> Monitoring:
        """Return a new monitoring instance for the given profile name.

        Raises:
            ValueError: If *name* is not a known monitoring backend key.
        """
        try:
            return cls._REGISTRY[name](mconfig)
        except KeyError as exc:
            raise ValueError(f"Unknown monitoring backend: {name!r}") from exc

    @classmethod
    def get_all(cls) -> Iterator[Monitoring]:
        """Yield one instance for every entry in ``settings.monitoring_profiles``."""
        for name, mconfig in sorted(settings.monitoring_profiles.items()):
            yield cls.get_object(name, mconfig)

    @classmethod
    def start(cls, directory: str) -> None:
        """Start all configured monitoring backends."""
        for monitor in cls.get_all():
            monitor.start(directory)

    @classmethod
    def stop(cls, directory: Optional[str] = None) -> None:
        """Stop all configured monitoring backends."""
        for monitor in cls.get_all():
            monitor.stop(directory)

    @classmethod
    @contextmanager
    def monitor(cls, directory: str) -> Iterator[None]:
        """Context manager: start all monitors, yield, then stop all."""
        monitors = list(cls.get_all())
        for monitor in monitors:
            monitor.start(directory)
        try:
            yield
        finally:
            for monitor in monitors:
                monitor.stop(directory)

    @classmethod
    def get_cpu_cycles(cls, out_dir: str) -> Optional[int]:
        """Return total CPU cycles from perf stat output, if perf is configured.

        Iterates monitoring profiles and delegates to the first
        ``PerfMonitoring`` instance found.  Returns ``None`` when no perf
        profile is configured.
        """
        for monitor in cls.get_all():
            if isinstance(monitor, PerfMonitoring):
                return monitor.get_cpu_cycles(out_dir)
        return None
