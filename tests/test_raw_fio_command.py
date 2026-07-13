"""Unit tests for the RawFioCommand class"""

# pyright: strict, reportPrivateUsage=false
#
# We are OK to ignore private use in unit tests as the whole point of the tests
# is to validate the functions contained in the module

import unittest

from command.raw_fio_command import RawFioCommand


def _make_options(**overrides: str) -> dict[str, str]:
    """Return a minimal set of valid options, with any overrides applied."""
    base: dict[str, str] = {
        "name": "test_workload",
        "target_number": "0",
        "iodepth": "16",
        "numjobs": "1",
        "mode": "write",
    }
    base.update(overrides)
    return base


class TestRawFioCommandBenchmarkProperty(unittest.TestCase):
    """Tests for the benchmark property"""

    def test_benchmark_returns_rawfio(self) -> None:
        """benchmark property must return 'rawfio' so the output directory is correct"""
        cmd = RawFioCommand(_make_options(), "/tmp/workload/")
        self.assertEqual(cmd.benchmark, "rawfio")


class TestRawFioCommandDeviceSelection(unittest.TestCase):
    """Tests for block-device selection via target_number"""

    def test_single_device_target_zero(self) -> None:
        """Single device: target 0 should select the only device"""
        cmd = RawFioCommand(_make_options(block_devices="/dev/vdb", target_number="0"), "/tmp/workload/")
        self.assertEqual(cmd._options["filename"], "/dev/vdb")

    def test_single_device_target_nonzero_wraps(self) -> None:
        """Single device: any target number wraps back to the only device"""
        cmd = RawFioCommand(_make_options(block_devices="/dev/vdb", target_number="5"), "/tmp/workload/")
        self.assertEqual(cmd._options["filename"], "/dev/vdb")

    def test_multi_device_target_zero(self) -> None:
        """Multi-device: target 0 selects the first device"""
        cmd = RawFioCommand(
            _make_options(block_devices="/dev/vdb,/dev/vdc,/dev/vdd", target_number="0"), "/tmp/workload/"
        )
        self.assertEqual(cmd._options["filename"], "/dev/vdb")

    def test_multi_device_target_one(self) -> None:
        """Multi-device: target 1 selects the second device"""
        cmd = RawFioCommand(
            _make_options(block_devices="/dev/vdb,/dev/vdc,/dev/vdd", target_number="1"), "/tmp/workload/"
        )
        self.assertEqual(cmd._options["filename"], "/dev/vdc")

    def test_multi_device_target_two(self) -> None:
        """Multi-device: target 2 selects the third device"""
        cmd = RawFioCommand(
            _make_options(block_devices="/dev/vdb,/dev/vdc,/dev/vdd", target_number="2"), "/tmp/workload/"
        )
        self.assertEqual(cmd._options["filename"], "/dev/vdd")

    def test_multi_device_round_robin(self) -> None:
        """Multi-device: target number wraps around via modulo"""
        cmd = RawFioCommand(_make_options(block_devices="/dev/vdb,/dev/vdc", target_number="3"), "/tmp/workload/")
        # target 3 % 2 devices = index 1 -> /dev/vdc
        self.assertEqual(cmd._options["filename"], "/dev/vdc")

    def test_device_whitespace_stripped(self) -> None:
        """Whitespace around device names in the comma-separated list is stripped"""
        cmd = RawFioCommand(_make_options(block_devices=" /dev/vdb , /dev/vdc ", target_number="1"), "/tmp/workload/")
        self.assertEqual(cmd._options["filename"], "/dev/vdc")

    def test_default_device_when_not_specified(self) -> None:
        """When block_devices is not set the default /dev/vdb is used"""
        options = _make_options()
        options.pop("block_devices", None)
        cmd = RawFioCommand(options, "/tmp/workload/")
        self.assertEqual(cmd._options["filename"], "/dev/vdb")


class TestRawFioCommandIoengine(unittest.TestCase):
    """Tests for ioengine selection"""

    def test_default_ioengine_is_libaio(self) -> None:
        """ioengine defaults to libaio when not specified"""
        options = _make_options()
        options.pop("ioengine", None)
        cmd = RawFioCommand(options, "/tmp/workload/")
        self.assertEqual(cmd._options["ioengine"], "libaio")

    def test_custom_ioengine_is_used(self) -> None:
        """ioengine option from config overrides the default"""
        cmd = RawFioCommand(_make_options(ioengine="io_uring"), "/tmp/workload/")
        self.assertEqual(cmd._options["ioengine"], "io_uring")


class TestRawFioCommandOutputDirectory(unittest.TestCase):
    """Tests for output directory path generation"""

    def test_output_directory_contains_benchmark_name(self) -> None:
        """Output directory path must include 'rawfio' (from self.benchmark)"""
        cmd = RawFioCommand(_make_options(), "/tmp/workload/test_workload/")
        self.assertIn("rawfio", cmd.output_directory)

    def test_output_directory_contains_workload_base(self) -> None:
        """Output directory is rooted under the workload output directory"""
        cmd = RawFioCommand(_make_options(), "/tmp/workload/test_workload/")
        self.assertTrue(cmd.output_directory.startswith("/tmp/workload/test_workload/"))

    def test_output_directory_contains_iodepth(self) -> None:
        """Output directory path encodes the iodepth"""
        cmd = RawFioCommand(_make_options(iodepth="32"), "/tmp/workload/test_workload/")
        self.assertIn("iodepth-000032", cmd.output_directory)

    def test_output_directory_contains_numjobs(self) -> None:
        """Output directory path encodes the numjobs"""
        cmd = RawFioCommand(_make_options(numjobs="4"), "/tmp/workload/test_workload/")
        self.assertIn("numjobs-004", cmd.output_directory)


class TestRawFioCommandFullCommand(unittest.TestCase):
    """Tests for the full generated CLI string"""

    def test_get_requires_executable_set(self) -> None:
        """get() returns empty string when no executable has been set"""
        cmd = RawFioCommand(_make_options(), "/tmp/workload/test_workload/")
        self.assertEqual(cmd.get(), "")

    def test_get_includes_executable(self) -> None:
        """get() includes the executable path"""
        cmd = RawFioCommand(_make_options(), "/tmp/workload/test_workload/")
        cmd.set_executable("/usr/bin/fio")
        self.assertIn("/usr/bin/fio", cmd.get())

    def test_get_includes_filename(self) -> None:
        """get() includes --filename= pointing at the selected device"""
        cmd = RawFioCommand(_make_options(block_devices="/dev/vdb"), "/tmp/workload/test_workload/")
        cmd.set_executable("/usr/bin/fio")
        self.assertIn("--filename=/dev/vdb", cmd.get())

    def test_get_includes_ioengine(self) -> None:
        """get() includes --ioengine="""
        cmd = RawFioCommand(_make_options(), "/tmp/workload/test_workload/")
        cmd.set_executable("/usr/bin/fio")
        self.assertIn("--ioengine=libaio", cmd.get())

    def test_get_includes_rw_mode(self) -> None:
        """get() includes --rw= with the configured mode"""
        cmd = RawFioCommand(_make_options(mode="randread"), "/tmp/workload/test_workload/")
        cmd.set_executable("/usr/bin/fio")
        self.assertIn("--rw=randread", cmd.get())

    def test_get_redirects_to_output_file(self) -> None:
        """get() ends with a redirect to the per-target output file"""
        cmd = RawFioCommand(_make_options(target_number="2"), "/tmp/workload/test_workload/")
        cmd.set_executable("/usr/bin/fio")
        result = cmd.get()
        self.assertIn("> ", result)
        self.assertIn("output.2", result)

    def test_get_includes_sudo_by_default(self) -> None:
        """get() is prefixed with 'sudo' when no_sudo is not set"""
        cmd = RawFioCommand(_make_options(), "/tmp/workload/test_workload/")
        cmd.set_executable("/usr/bin/fio")
        self.assertTrue(cmd.get().startswith("sudo "))

    def test_get_no_sudo_when_requested(self) -> None:
        """get() omits 'sudo' when no_sudo is set"""
        cmd = RawFioCommand(_make_options(no_sudo="True"), "/tmp/workload/test_workload/")
        cmd.set_executable("/usr/bin/fio")
        self.assertFalse(cmd.get().startswith("sudo "))


if __name__ == "__main__":
    unittest.main()
