"""
Unit tests for the post_processing/reports module classes
"""

# pyright: strict, reportPrivateUsage=false
#
# We are OK to ignore private use in unit tests as the whole point of the tests
# is to validate the functions contained in the module

import shutil
import tempfile
import unittest
from pathlib import Path

from post_processing.reports.report_generator import ReportGenerator
from post_processing.reports.simple_report_generator import SimpleReportGenerator


class TestReportGenerator(unittest.TestCase):
    """Test cases for ReportGenerator base class"""

    def setUp(self) -> None:
        """Set up test fixtures with new nested structure"""
        self.temp_dir = tempfile.mkdtemp()
        self.archive_dir = Path(self.temp_dir) / "archive"

        # Create new nested structure: operation/visualisation/
        read_vis_dir = self.archive_dir / "read" / "visualisation"
        write_vis_dir = self.archive_dir / "write" / "visualisation"
        read_vis_dir.mkdir(parents=True)
        write_vis_dir.mkdir(parents=True)

        # Also create top-level visualisation for SVG files
        self.vis_dir = self.archive_dir / "visualisation"
        self.vis_dir.mkdir(parents=True)

        # Create some test data files in nested structure
        # Format: {blocksize}_{numjobs}_{operation}.json
        (read_vis_dir / "4096_1_read.json").touch()
        (write_vis_dir / "8192_1_write.json").touch()

    def tearDown(self) -> None:
        """Clean up test fixtures"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initialization(self) -> None:
        """Test ReportGenerator initialization"""
        output_dir = f"{self.temp_dir}/output"

        generator = SimpleReportGenerator(
            archive_directories=[str(self.archive_dir)],
            output_directory=output_dir,
            no_error_bars=False,
            force_refresh=False,
            plot_resources=False,
        )

        self.assertTrue(generator._plot_error_bars)
        self.assertFalse(generator._force_refresh)
        self.assertFalse(generator._plot_resources)
        self.assertEqual(len(generator._archive_directories), 1)
        # With new nested structure, we have 2 operation directories (read and write)
        self.assertEqual(len(generator._data_directories), 2)

    def test_initialization_with_no_error_bars(self) -> None:
        """Test initialization with no_error_bars=True"""
        output_dir = f"{self.temp_dir}/output"

        generator = SimpleReportGenerator(
            archive_directories=[str(self.archive_dir)],
            output_directory=output_dir,
            no_error_bars=True,
            force_refresh=False,
            plot_resources=False,
        )

        self.assertFalse(generator._plot_error_bars)

    def test_initialization_with_plot_resources(self) -> None:
        """Test initialization with plot_resources=True"""
        output_dir = f"{self.temp_dir}/output"

        generator = SimpleReportGenerator(
            archive_directories=[str(self.archive_dir)],
            output_directory=output_dir,
            no_error_bars=False,
            force_refresh=False,
            plot_resources=True,
        )

        self.assertTrue(generator._plot_resources)

    def test_build_strings_replace_underscores(self) -> None:
        """Test that build strings replace underscores with hyphens"""
        archive_with_underscores = Path(self.temp_dir) / "test_archive_name"

        # Create new nested structure
        read_vis_dir = archive_with_underscores / "read" / "visualisation"
        read_vis_dir.mkdir(parents=True)
        # Format: {blocksize}_{numjobs}_{operation}.json
        (read_vis_dir / "4096_1_read.json").touch()

        # Also create top-level visualisation for SVG files
        top_vis_dir = archive_with_underscores / "visualisation"
        top_vis_dir.mkdir(parents=True)

        output_dir = f"{self.temp_dir}/output"

        generator = SimpleReportGenerator(
            archive_directories=[str(archive_with_underscores)],
            output_directory=output_dir,
        )

        self.assertEqual(generator._build_strings[0], "test-archive-name")
        self.assertNotIn("_", generator._build_strings[0])

    def test_find_files_with_filename(self) -> None:
        """Test finding files with specific filename"""
        output_dir = f"{self.temp_dir}/output"

        generator = SimpleReportGenerator(
            archive_directories=[str(self.archive_dir)],
            output_directory=output_dir,
        )

        files = generator._find_files_with_filename("4096_1_read")

        self.assertEqual(len(files), 1)
        self.assertTrue(str(files[0]).endswith("4096_1_read.json"))

    def test_sort_list_of_paths(self) -> None:
        """Test sorting paths by numeric blocksize"""
        # Create files with different blocksizes in new nested structure
        # Format: {blocksize}_{numjobs}_{operation}.json
        read_vis_dir = self.archive_dir / "read" / "visualisation"
        read_vis_dir.mkdir(parents=True, exist_ok=True)
        (read_vis_dir / "16384_1_read.json").touch()
        (read_vis_dir / "1024_1_read.json").touch()

        output_dir = f"{self.temp_dir}/output"

        generator = SimpleReportGenerator(
            archive_directories=[str(self.archive_dir)],
            output_directory=output_dir,
        )

        paths = list(read_vis_dir.glob("*.json"))
        sorted_paths = generator._sort_list_of_paths(paths, index=0)

        # Should be sorted by blocksize: 1024, 4096, 8192, 16384
        self.assertTrue(str(sorted_paths[0]).endswith("1024_1_read.json"))
        self.assertTrue(str(sorted_paths[-1]).endswith("16384_1_read.json"))

    def test_generate_plot_directory_name(self) -> None:
        """Test generating unique plot directory name"""
        output_dir = f"{self.temp_dir}/output"

        generator = SimpleReportGenerator(
            archive_directories=[str(self.archive_dir)],
            output_directory=output_dir,
        )

        plot_dir_name = generator._generate_plot_directory_name()

        self.assertTrue(plot_dir_name.startswith(f"{output_dir}/plots."))
        # Should have timestamp appended
        self.assertGreater(len(plot_dir_name), len(f"{output_dir}/plots."))

    def test_force_refresh_allows_legacy_visualisation_directory(self) -> None:
        """Test that force_refresh bypasses legacy visualisation directory rejection"""
        legacy_archive = Path(self.temp_dir) / "legacy_archive"
        legacy_vis_dir = legacy_archive / "visualisation"
        legacy_vis_dir.mkdir(parents=True)
        (legacy_vis_dir / "4096_1_read.json").touch()

        output_dir = f"{self.temp_dir}/output"

        generator = SimpleReportGenerator(
            archive_directories=[str(legacy_archive)],
            output_directory=output_dir,
            force_refresh=True,
        )

        self.assertTrue(generator._force_refresh)
        self.assertEqual(generator._data_directories, [legacy_vis_dir])

    def test_constants(self) -> None:
        """Test ReportGenerator constants"""
        self.assertEqual(ReportGenerator.MARKDOWN_FILE_EXTENSION, "md")
        self.assertEqual(ReportGenerator.PDF_FILE_EXTENSION, "pdf")
        self.assertEqual(ReportGenerator.BASE_HEADER_FILE_PATH, "include/performance_report.tex")


class TestSortKeyRobustness(unittest.TestCase):
    """Tests that sort helpers do not raise on unexpected file name formats.

    Previously both _data_file_sort_key and _sort_list_of_paths used bare int()
    conversions that raised ValueError/IndexError for any file name not matching
    the strict BLOCKSIZE_NUMJOBS_OPERATION pattern.
    """

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.archive_dir = Path(self.temp_dir) / "archive"
        vis_dir = self.archive_dir / "read" / "visualisation"
        vis_dir.mkdir(parents=True)
        (vis_dir / "4096_1_read.json").touch()
        (self.archive_dir / "visualisation").mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _make_generator(self) -> SimpleReportGenerator:
        return SimpleReportGenerator(
            archive_directories=[str(self.archive_dir)],
            output_directory=f"{self.temp_dir}/output",
        )

    # --- _data_file_sort_key ---

    def test_data_file_sort_key_well_formed_name(self) -> None:
        """Standard BLOCKSIZE_NUMJOBS_OPERATION.json name sorts by (blocksize, numjobs)."""
        key = ReportGenerator._data_file_sort_key("4096_2_randread.json")
        self.assertEqual(key, (4096, 2))

    def test_data_file_sort_key_unparseable_returns_zero_tuple(self) -> None:
        """A file name that does not match the expected pattern returns (0, 0).

        Previously this raised ValueError; now it falls back gracefully.
        """
        key = ReportGenerator._data_file_sort_key("unexpected_file_name.json")
        self.assertEqual(key, (0, 0))

    def test_data_file_sort_key_single_token_returns_zero_tuple(self) -> None:
        """A name with only one underscore-separated token returns (0, 0)."""
        key = ReportGenerator._data_file_sort_key("nounderscores")
        self.assertEqual(key, (0, 0))

    def test_data_file_sort_key_non_numeric_token_returns_zero_tuple(self) -> None:
        """A name whose first token is non-numeric returns (0, 0), not ValueError."""
        key = ReportGenerator._data_file_sort_key("K_2_read.json")
        self.assertEqual(key, (0, 0))

    def test_data_file_sort_key_sorts_mixed_valid_and_invalid(self) -> None:
        """Sorting a list containing both valid and invalid names does not raise."""
        names = ["8192_1_read.json", "unexpected.json", "4096_2_write.json", "also_bad"]
        result = sorted(names, key=ReportGenerator._data_file_sort_key)
        # Invalid names sort to (0,0) and appear first; valid names sort numerically
        self.assertIn("4096_2_write.json", result)
        self.assertIn("8192_1_read.json", result)

    # --- _sort_list_of_paths ---

    def test_sort_list_of_paths_well_formed(self) -> None:
        """Paths whose stem matches BLOCKSIZE_NUMJOBS_OPERATION sort correctly."""
        generator = self._make_generator()
        paths = [
            Path("/vis/16K_1_read.json"),
            Path("/vis/4K_1_read.json"),
            Path("/vis/8K_1_read.json"),
        ]
        sorted_paths = generator._sort_list_of_paths(paths, index=0)
        stems = [p.stem for p in sorted_paths]
        self.assertEqual(stems, ["4K_1_read", "8K_1_read", "16K_1_read"])

    def test_sort_list_of_paths_unparseable_stem_does_not_raise(self) -> None:
        """A path whose stem cannot be parsed returns sort key 0, not ValueError."""
        generator = self._make_generator()
        paths = [
            Path("/vis/8K_1_read.json"),
            Path("/vis/unexpected_file.json"),  # token[:-1] = "unexpecte" → int() fails
        ]
        # Must not raise
        result = generator._sort_list_of_paths(paths, index=0)
        self.assertEqual(len(result), 2)

    def test_sort_list_of_paths_index_out_of_range_does_not_raise(self) -> None:
        """A stem with fewer tokens than index does not raise IndexError."""
        generator = self._make_generator()
        paths = [Path("/vis/only_one.json")]
        # index=2 is out of range for a stem with 2 underscore-tokens
        result = generator._sort_list_of_paths(paths, index=5)
        self.assertEqual(len(result), 1)


class TestFindAndSortFilePathsSignature(unittest.TestCase):
    """Tests that _find_and_sort_file_paths no longer accepts Optional[int].

    Previously the abstract declaration and both concrete implementations
    typed index as Optional[int] = 0, then immediately asserted it was not
    None — a contradiction.  The fix changes the type to int = 0 throughout
    and removes the vacuous assert.
    """

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.archive_dir = Path(self.temp_dir) / "archive"
        vis_dir = self.archive_dir / "read" / "visualisation"
        vis_dir.mkdir(parents=True)
        (vis_dir / "4096_1_read.json").touch()
        (self.archive_dir / "visualisation").mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _make_simple_generator(self) -> SimpleReportGenerator:
        return SimpleReportGenerator(
            archive_directories=[str(self.archive_dir)],
            output_directory=f"{self.temp_dir}/output",
        )

    def test_simple_generator_index_defaults_to_zero(self) -> None:
        """SimpleReportGenerator._find_and_sort_file_paths works with the default index."""
        gen = self._make_simple_generator()
        vis_dir = self.archive_dir / "read" / "visualisation"
        result = gen._find_and_sort_file_paths([vis_dir], "*.json")
        self.assertIsInstance(result, list)

    def test_simple_generator_explicit_int_index_accepted(self) -> None:
        """SimpleReportGenerator._find_and_sort_file_paths accepts an explicit int index."""
        gen = self._make_simple_generator()
        vis_dir = self.archive_dir / "read" / "visualisation"
        result = gen._find_and_sort_file_paths([vis_dir], "*.json", index=0)
        self.assertIsInstance(result, list)

    def test_none_is_not_a_valid_index(self) -> None:
        """Passing None as index is rejected by the type system and raises at runtime.

        Previously None was nominally accepted (Optional[int]) and then
        immediately asserted away.  Now the parameter is typed as int so
        mypy catches this statically; at runtime sorted() would receive a
        None index and raise a TypeError.
        """
        gen = self._make_simple_generator()
        vis_dir = self.archive_dir / "read" / "visualisation"
        with self.assertRaises((TypeError, AssertionError)):
            gen._find_and_sort_file_paths([vis_dir], "*.json", index=None)  # type: ignore[arg-type]


class TestPackageInitFile(unittest.TestCase):
    """Tests that post_processing has a correctly named __init__.py (W6).

    Previously the file was named ___init___.py (three underscores each side)
    which Python ignores.  The fix deletes that file and creates the standard
    __init__.py.
    """

    def test_correct_init_file_exists(self) -> None:
        """post_processing/__init__.py (two underscores) exists."""
        import post_processing

        init_path = (
            Path(post_processing.__file__)
            if hasattr(post_processing, "__file__") and post_processing.__file__
            else None
        )
        # The package must have been found by Python — __file__ points to __init__.py
        self.assertIsNotNone(init_path, "post_processing should be importable as a package")

    def test_triple_underscore_init_does_not_exist(self) -> None:
        """post_processing/___init___.py (three underscores) must not exist."""
        import post_processing

        package_dir = Path(post_processing.__file__).parent  # type: ignore[arg-type]
        bad_init = package_dir / "___init___.py"
        self.assertFalse(
            bad_init.exists(),
            f"Found {bad_init} — this file is silently ignored by Python and should be deleted.",
        )

    def test_post_processing_is_a_proper_package(self) -> None:
        """post_processing is importable and exposes __path__ as a real package."""
        import post_processing

        self.assertTrue(hasattr(post_processing, "__path__"), "post_processing must be a package, not a plain module")


# Made with Bob
