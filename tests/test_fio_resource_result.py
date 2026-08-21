"""
Unit tests for the post_processing FIO resource result module class
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
from unittest import mock

from post_processing.run_results.resources.fio_resource import FIOResource


class TestFIOResource(unittest.TestCase):
    """Test cases for FIOResource class"""

    def setUp(self) -> None:
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "fio_output.json"

        self.test_data = {"jobs": [{"sys_cpu": 25.5, "usr_cpu": 30.2}]}

        with open(self.test_file, "w") as f:
            json.dump(self.test_data, f)

    def tearDown(self) -> None:
        """Clean up test fixtures"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_source_property(self) -> None:
        """Test source property returns 'fio'"""
        resource = FIOResource(self.test_file)

        self.assertEqual(resource.source, "fio")

    def test_get_resource_output_file_from_file_path(self) -> None:
        """Test that resource file path is same as input path"""
        resource = FIOResource(self.test_file)

        self.assertEqual(resource._resource_file_path, self.test_file)

    def test_parse_cpu_usage_single_job(self) -> None:
        """Test CPU usage is normalised by cpu_count for a single job.

        sys_cpu (25.5) + usr_cpu (30.2) = 55.7 per-core; averaged across 1
        job = 55.7; divided by 4 cpus = 13.925, formatted to 2 d.p. = 13.93.
        """
        with mock.patch("post_processing.run_results.resources.fio_resource.os.cpu_count", return_value=4):
            resource = FIOResource(self.test_file)
            cpu = resource.cpu

        self.assertEqual(cpu, "13.93")

    def test_parse_cpu_usage_multi_job(self) -> None:
        """Test CPU usage is averaged across multiple jobs then normalised.

        Two jobs: job0 (sys=20, usr=20 → 40), job1 (sys=40, usr=40 → 80).
        Average per-job cpu = (40 + 80) / 2 = 60.
        Divided by 4 cpus = 15.0.
        """
        multi_job_data = {
            "jobs": [
                {"sys_cpu": 20.0, "usr_cpu": 20.0},
                {"sys_cpu": 40.0, "usr_cpu": 40.0},
            ]
        }
        multi_job_file = Path(self.temp_dir) / "multi_job.json"
        with open(multi_job_file, "w") as f:
            json.dump(multi_job_data, f)

        with mock.patch("post_processing.run_results.resources.fio_resource.os.cpu_count", return_value=4):
            resource = FIOResource(multi_job_file)
            cpu = resource.cpu

        self.assertEqual(cpu, "15.00")

    def test_parse_cpu_usage_multi_job_all_jobs_counted(self) -> None:
        """Test that all numjobs entries contribute to the average, not just jobs[0].

        With the old buggy code (reading only jobs[0]), sys_cpu=10, usr_cpu=10
        would give (10+10)/4 = 5.0.  The correct result averages both jobs:
        ((10+10) + (90+90)) / 2 / 4 = 100/4 = 25.0.
        """
        multi_job_data = {
            "jobs": [
                {"sys_cpu": 10.0, "usr_cpu": 10.0},
                {"sys_cpu": 90.0, "usr_cpu": 90.0},
            ]
        }
        multi_job_file = Path(self.temp_dir) / "multi_job2.json"
        with open(multi_job_file, "w") as f:
            json.dump(multi_job_data, f)

        with mock.patch("post_processing.run_results.resources.fio_resource.os.cpu_count", return_value=4):
            resource = FIOResource(multi_job_file)
            cpu = resource.cpu

        # Old buggy result would have been "5.00"; correct multi-job result is "25.00"
        self.assertEqual(cpu, "25.00")
        self.assertNotEqual(cpu, "5.00")

    def test_parse_empty_jobs_list_returns_zero(self) -> None:
        """Test that an empty jobs list results in '0.00' CPU, not an IndexError."""
        empty_jobs_data: dict = {"jobs": []}
        empty_jobs_file = Path(self.temp_dir) / "empty_jobs.json"
        with open(empty_jobs_file, "w") as f:
            json.dump(empty_jobs_data, f)

        resource = FIOResource(empty_jobs_file)
        cpu = resource.cpu

        self.assertEqual(cpu, "0.00")
        self.assertEqual(resource.memory, "0.00")

    def test_parse_missing_jobs_key_returns_zero(self) -> None:
        """Test that missing 'jobs' key results in '0.00' CPU, not a KeyError."""
        no_jobs_data: dict = {"global options": {"bs": "4096"}}
        no_jobs_file = Path(self.temp_dir) / "no_jobs.json"
        with open(no_jobs_file, "w") as f:
            json.dump(no_jobs_data, f)

        resource = FIOResource(no_jobs_file)
        cpu = resource.cpu

        self.assertEqual(cpu, "0.00")

    def test_cpu_format_is_two_decimal_places(self) -> None:
        """Test that CPU result is formatted to exactly 2 decimal places."""
        with mock.patch("post_processing.run_results.resources.fio_resource.os.cpu_count", return_value=1):
            resource = FIOResource(self.test_file)
            cpu = resource.cpu

        # Should have exactly 2 decimal places
        parts = cpu.split(".")
        self.assertEqual(len(parts), 2)
        self.assertEqual(len(parts[1]), 2)

    def test_parse_memory_usage(self) -> None:
        """Test parsing memory usage (currently returns 0)"""
        resource = FIOResource(self.test_file)

        memory = resource.memory

        # Memory is not currently extracted from FIO output
        self.assertEqual(float(memory), 0.0)

    def test_get_method(self) -> None:
        """Test get method returns formatted resource data with correct keys."""
        with mock.patch("post_processing.run_results.resources.fio_resource.os.cpu_count", return_value=4):
            resource = FIOResource(self.test_file)
            data = resource.get()

        self.assertEqual(data["source"], "fio")
        self.assertIn("cpu", data)
        self.assertIn("memory", data)
        # 25.5 + 30.2 = 55.7 / 4 = 13.925, rounded to 2 d.p. → 13.93
        self.assertEqual(data["cpu"], "13.93")


# Made with Bob
