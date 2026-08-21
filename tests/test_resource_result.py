"""
Unit tests for the post_processing/run_results resource result class
"""

# pyright: strict, reportPrivateUsage=false
#
# We are OK to ignore private use in unit tests as the whole point of the tests
# is to validate the functions contained in the module

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from post_processing.run_results.resource_result import ResourceResult


class ConcreteResourceResult(ResourceResult):
    """Concrete implementation of ResourceResult for testing"""

    @property
    def source(self) -> str:
        return "test_resource"

    def _get_resource_output_file_from_file_path(self, file_path: Path) -> Path:
        return file_path

    def _parse(self) -> None:
        self._cpu = "50.0"
        self._memory = "1024.0"
        self._has_been_parsed = True


class TestResourceResult(unittest.TestCase):
    """Test cases for ResourceResult base class"""

    def setUp(self) -> None:
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "resource_output.json"

        self.test_data = {"cpu_usage": 50.5, "memory_usage": 2048}

        with open(self.test_file, "w") as f:
            json.dump(self.test_data, f)

    def tearDown(self) -> None:
        """Clean up test fixtures"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initialization(self) -> None:
        """Test ResourceResult initialization"""
        result = ConcreteResourceResult(self.test_file)

        self.assertEqual(result._resource_file_path, self.test_file)
        self.assertFalse(result._has_been_parsed)

    def test_cpu_property(self) -> None:
        """Test CPU property triggers parsing"""
        result = ConcreteResourceResult(self.test_file)

        cpu = result.cpu

        self.assertEqual(cpu, "50.0")
        self.assertTrue(result._has_been_parsed)

    def test_memory_property(self) -> None:
        """Test memory property triggers parsing"""
        result = ConcreteResourceResult(self.test_file)

        memory = result.memory

        self.assertEqual(memory, "1024.0")
        self.assertTrue(result._has_been_parsed)

    def test_get_method(self) -> None:
        """Test get method returns formatted dict"""
        result = ConcreteResourceResult(self.test_file)

        data = result.get()

        self.assertIn("source", data)
        self.assertIn("cpu", data)
        self.assertIn("memory", data)
        self.assertEqual(data["source"], "test_resource")
        self.assertEqual(data["cpu"], "50.0")
        self.assertEqual(data["memory"], "1024.0")

    def test_read_results_from_empty_file(self) -> None:
        """Test reading from empty file"""
        empty_file = Path(self.temp_dir) / "empty.json"
        empty_file.touch()

        result = ConcreteResourceResult(empty_file)
        data = result._read_results_from_file()

        self.assertEqual(data, {})


class TestResourceResultEnsureParsed(unittest.TestCase):
    """Tests for the _ensure_parsed() helper (W5) and the no-data-argument _parse() contract (I4).

    W5: Previously cpu, memory, and get() each contained an independent
    'if not self._has_been_parsed: self._parse(...)' guard, duplicating the
    lazy-initialisation logic three times. The fix introduces a single
    _ensure_parsed() method that all three delegates call.

    I4: _parse() no longer accepts a data argument; each subclass reads its
    own source file internally.
    """

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "resource.json"
        import json as _json

        _json.dump({"cpu_usage": 50.5}, self.test_file.open("w"))

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_ensure_parsed_calls_parse_exactly_once(self) -> None:
        """_ensure_parsed() only triggers _parse() on the first call."""
        call_count = 0

        class CountingResource(ConcreteResourceResult):
            def _parse(self) -> None:
                nonlocal call_count
                call_count += 1
                self._cpu = "1.0"
                self._memory = "0.0"
                self._has_been_parsed = True

        resource = CountingResource(self.test_file)
        resource._ensure_parsed()
        resource._ensure_parsed()
        resource._ensure_parsed()

        self.assertEqual(call_count, 1, "_parse() should be called exactly once")

    def test_cpu_memory_get_all_use_same_parse_call(self) -> None:
        """Accessing cpu, memory, and get() in sequence triggers _parse() only once."""
        call_count = 0

        class CountingResource(ConcreteResourceResult):
            def _parse(self) -> None:
                nonlocal call_count
                call_count += 1
                self._cpu = "42.0"
                self._memory = "8.0"
                self._has_been_parsed = True

        resource = CountingResource(self.test_file)
        _ = resource.cpu
        _ = resource.memory
        _ = resource.get()

        self.assertEqual(call_count, 1, "All three accessors should share one parse call")

    def test_parse_takes_no_data_argument(self) -> None:
        """_parse() is callable with no arguments (I4 contract)."""
        resource = ConcreteResourceResult(self.test_file)
        # Must not raise TypeError about unexpected argument
        try:
            resource._parse()  # pylint: disable=protected-access
        except TypeError as e:
            self.fail(f"_parse() raised TypeError: {e}")

    def test_parse_signature_rejects_positional_data_argument(self) -> None:
        """Passing a positional data dict to _parse() raises TypeError (old API is gone)."""
        resource = ConcreteResourceResult(self.test_file)
        with self.assertRaises(TypeError):
            resource._parse({})  # type: ignore[call-arg]  # pylint: disable=protected-access


# Made with Bob
