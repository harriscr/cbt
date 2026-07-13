"""
A subclass of FioCommand for the rawfio benchmark.

Handles the block-device-specific FIO options:
  - ioengine  (defaults to libaio, configurable)
  - filename  (selected from the block_devices list by target number)

From the FIO documentation:
https://fio.readthedocs.io/en/latest/fio_doc.html
"""

from command.fio_command import FioCommand


class RawFioCommand(FioCommand):
    """
    An FioCommand type that deals specifically with running I/O against raw
    block devices using the libaio (or configurable) I/O engine.
    """

    _RAWFIO_DEFAULT_IOENGINE: str = "libaio"

    @property
    def benchmark(self) -> str:
        return "rawfio"

    def _parse_ioengine_specific_parameters(self, options: dict[str, str]) -> dict[str, str]:
        """
        Parse the rawfio-specific FIO parameters: ioengine and filename.

        The target device is selected from the comma-separated block_devices
        option using modulo on the target number, which matches the round-robin
        selection used by the non-workloads run() path in RawFio.
        """
        raw_options: dict[str, str] = {}

        raw_options["ioengine"] = options.get("ioengine", self._RAWFIO_DEFAULT_IOENGINE)

        block_devices: list[str] = [d.strip() for d in options.get("block_devices", "/dev/vdb").split(",")]
        device_index: int = self._target_number % len(block_devices)
        raw_options["filename"] = block_devices[device_index]

        return raw_options
