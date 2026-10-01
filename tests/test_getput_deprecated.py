"""Tests for deprecated Getput benchmark.

Getput is deprecated and must not be constructible.  Selecting it in a YAML
should raise a clear error pointing users at hsbench.

Seam under test:
  - benchmarkfactory.get_object("getput", ...) → raises NotImplementedError
"""

import unittest
from unittest.mock import MagicMock

import benchmarkfactory


class TestGetputDeprecatedViaFactory(unittest.TestCase):
    """benchmarkfactory.get_object raises NotImplementedError for getput."""

    def test_getput_raises_with_migration_message(self) -> None:
        """The error names getput, says it is deprecated and recommends hsbench."""
        with self.assertRaises(NotImplementedError) as ctx:
            benchmarkfactory.get_object("/tmp/archive", MagicMock(), "getput", {"iteration": 0})

        message = str(ctx.exception).lower()
        self.assertIn("getput", message, "message should name the deprecated benchmark")
        self.assertIn("deprecated", message, "message should say the benchmark is deprecated")
        self.assertIn("hsbench", message, "message should point users at hsbench")


if __name__ == "__main__":
    unittest.main()
