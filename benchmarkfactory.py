"""Factory for creating benchmark instances from a YAML benchmark name.

Cosbench and getput have been deprecated and removed.  Selecting either in a
YAML raises :exc:`NotImplementedError` with a clear migration message.
"""

import logging
from typing import Any

import settings
from benchmark.cephtestrados import CephTestRados
from benchmark.elbencho import Elbencho
from benchmark.fio import Fio
from benchmark.hsbench import Hsbench
from benchmark.kvmrbdfio import KvmRbdFio
from benchmark.librbdfio import LibrbdFio
from benchmark.nullbench import Nullbench
from benchmark.radosbench import Radosbench
from benchmark.rawfio import RawFio
from benchmark.rbdfio import RbdFio
from common import all_configs

logger = logging.getLogger("cbt")

_DEPRECATED: dict[str, str] = {
    "cosbench": (
        "The 'cosbench' benchmark type is deprecated and has been removed from CBT. Please use 'hsbench' instead."
    ),
    "getput": (
        "The 'getput' benchmark type is deprecated and has been removed from CBT. Please use 'hsbench' instead."
    ),
}

_BENCHMARKS: dict[str, Any] = {
    "nullbench": Nullbench,
    "radosbench": Radosbench,
    "fio": Fio,
    "hsbench": Hsbench,
    "rbdfio": RbdFio,
    "kvmrbdfio": KvmRbdFio,
    "rawfio": RawFio,
    "librbdfio": LibrbdFio,
    "cephtestrados": CephTestRados,
    "elbencho": Elbencho,
}


def get_all(archive: str, cluster: Any, iteration: Any) -> Any:
    """Yield a benchmark instance for every config entry in ``settings.benchmarks``."""
    for benchmark, config in sorted(settings.benchmarks.items()):
        default = {"benchmark": benchmark, "iteration": iteration}
        for current in all_configs(config):
            current.update(default)
            yield get_object(archive, cluster, benchmark, current)


def get_object(archive: str, cluster: Any, benchmark: str, bconfig: dict[str, Any]) -> Any:
    """Return a benchmark instance for *benchmark*, or raise on unknown/deprecated names.

    Args:
        archive:   Root archive directory.
        cluster:   Ceph cluster handle.
        benchmark: Benchmark type string (as used in the YAML).
        bconfig:   Per-benchmark configuration dict.

    Returns:
        A concrete :class:`~benchmark.benchmark.Benchmark` instance.

    Raises:
        NotImplementedError: If *benchmark* is deprecated (e.g. ``"cosbench"``).
        KeyError: If *benchmark* is not a known benchmark type.
    """
    if benchmark in _DEPRECATED:
        msg = _DEPRECATED[benchmark]
        logger.error(msg)
        raise NotImplementedError(msg)

    return _BENCHMARKS[benchmark](archive, cluster, bconfig)
