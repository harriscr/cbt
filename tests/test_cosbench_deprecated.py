"""Tests for deprecated Cosbench benchmark.

Cosbench is deprecated and must not be constructible.  Selecting it in a YAML
should raise a clear error rather than silently running broken code.

Seams under test:
  - benchmarkfactory.get_object("cosbench", ...) → raises NotImplementedError
  - The error message names "cosbench" and says "deprecated"
  - Cosbench module itself raises NotImplementedError in __init__
"""

import unittest
from typing import Any
from unittest.mock import MagicMock, patch

_FAKE_CLUSTER_SETTINGS: dict[str, Any] = {
    "tmp_dir": "/tmp/cbt-test",
    "osd_ra": "0",
}


def _mock_cluster() -> MagicMock:
    cluster: MagicMock = MagicMock()
    cluster.config = {}
    cluster.tmp_conf = "/etc/ceph/ceph.conf"
    return cluster


class TestCosbenchDeprecatedViaFactory(unittest.TestCase):
    """benchmarkfactory.get_object raises NotImplementedError for cosbench."""

    def test_cosbench_via_factory_raises(self) -> None:
        """get_object('cosbench', ...) raises NotImplementedError."""
        import benchmarkfactory

        with (
            patch("settings.cluster", _FAKE_CLUSTER_SETTINGS),
            patch("settings.getnodes", return_value="fake-client"),
            patch("common.get_osd_ra", return_value="0"),
        ):
            with self.assertRaises(NotImplementedError):
                benchmarkfactory.get_object(
                    "/tmp/archive",
                    _mock_cluster(),
                    "cosbench",
                    {"iteration": 0},
                )

    def test_cosbench_error_message_mentions_cosbench(self) -> None:
        """The error message explicitly names cosbench."""
        import benchmarkfactory

        with (
            patch("settings.cluster", _FAKE_CLUSTER_SETTINGS),
            patch("settings.getnodes", return_value="fake-client"),
            patch("common.get_osd_ra", return_value="0"),
        ):
            try:
                benchmarkfactory.get_object(
                    "/tmp/archive",
                    _mock_cluster(),
                    "cosbench",
                    {"iteration": 0},
                )
                self.fail("Expected NotImplementedError was not raised")
            except NotImplementedError as exc:
                self.assertIn("cosbench", str(exc).lower())

    def test_cosbench_error_message_mentions_deprecated(self) -> None:
        """The error message says the benchmark is deprecated."""
        import benchmarkfactory

        with (
            patch("settings.cluster", _FAKE_CLUSTER_SETTINGS),
            patch("settings.getnodes", return_value="fake-client"),
            patch("common.get_osd_ra", return_value="0"),
        ):
            try:
                benchmarkfactory.get_object(
                    "/tmp/archive",
                    _mock_cluster(),
                    "cosbench",
                    {"iteration": 0},
                )
                self.fail("Expected NotImplementedError was not raised")
            except NotImplementedError as exc:
                self.assertIn("deprecated", str(exc).lower())


class TestCosbenchUnknownBenchmark(unittest.TestCase):
    """get_object with a completely unknown benchmark name raises KeyError."""

    def test_unknown_benchmark_raises_key_error(self) -> None:
        """get_object raises KeyError for an unrecognised benchmark type."""
        import benchmarkfactory

        with (
            patch("settings.cluster", _FAKE_CLUSTER_SETTINGS),
            patch("settings.getnodes", return_value="fake-client"),
            patch("common.get_osd_ra", return_value="0"),
        ):
            with self.assertRaises(KeyError):
                benchmarkfactory.get_object(
                    "/tmp/archive",
                    _mock_cluster(),
                    "nonexistent_benchmark",
                    {"iteration": 0},
                )


if __name__ == "__main__":
    unittest.main()
