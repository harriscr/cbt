"""Builds the hsbench command line for a single hsbench instance.

It returns the full executable string that can be used to run a cli command.
It encapsulates CLI argument parsing, option formatting, and output redirection.
"""

import os
from logging import Logger, getLogger
from typing import Any, Optional

import common
from cli_options import CliOptions
from command.command import Command

log: Logger = getLogger("cbt")


class HsbenchCommand(Command):
    """A single hsbench command line for one endpoint process execution."""

    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        options: dict[str, Optional[str]],
        run_dir: str,
        ep_num: int = 0,
        endpoint: Optional[dict[str, Any]] = None,
        prefill: bool = False,
    ) -> None:
        self._run_dir: str = run_dir
        self._ep_num: int = ep_num
        self._endpoint: dict[str, Any] = endpoint or {}
        self._prefill: bool = prefill
        super().__init__(options)

    # ------------------------------------------------------------------
    # Command ABC implementation
    # ------------------------------------------------------------------

    def _parse_options(self, options: dict[str, Optional[str]]) -> CliOptions:
        parsed_options: CliOptions = CliOptions()

        # Extract options with defaults / conversions
        buckets = options.get("buckets")
        parsed_options["buckets"] = str(buckets) if buckets is not None else None

        parsed_options["bucket_prefix"] = options.get("bucket_prefix")

        duration = options.get("duration")
        parsed_options["duration"] = str(duration) if duration is not None else None

        loop = options.get("loop")
        parsed_options["loop"] = str(loop) if loop is not None else None

        parsed_options["modes"] = options.get("modes")
        parsed_options["prefill_modes"] = options.get("prefill_modes") or "cxip"

        max_keys = options.get("max_keys")
        parsed_options["max_keys"] = str(max_keys) if max_keys is not None else None

        objects = options.get("objects")
        parsed_options["objects"] = str(objects) if objects is not None else None

        parsed_options["object_prefix"] = options.get("object_prefix")
        parsed_options["per_client_object_prefix"] = "true" if options.get("per_client_object_prefix", True) else None

        parsed_options["region"] = options.get("region")

        report_intervals = options.get("report_intervals")
        parsed_options["report_intervals"] = str(report_intervals) if report_intervals is not None else None

        threads = options.get("threads")
        parsed_options["threads"] = str(threads) if threads is not None else None

        parsed_options["size"] = options.get("size")

        return parsed_options

    def _parse_global_options(self, options: dict[str, Optional[str]]) -> CliOptions:
        return CliOptions(options)

    def _generate_output_directory_path(self) -> str:
        return self._run_dir

    @property
    def benchmark(self) -> str:
        return "hsbench"

    def _build_object_prefix(self) -> Optional[str]:
        options = self._options
        fqdn_cmd = common.get_fqdn_cmd()  # type: ignore [no-untyped-call]
        per_client = options["per_client_object_prefix"] is not None

        if options["object_prefix"]:
            prefix = options["object_prefix"]
            if per_client:
                prefix += f"-`{fqdn_cmd}`-{self._ep_num}-"
            return prefix
        if per_client:
            return f"`{fqdn_cmd}`-{self._ep_num}-"
        return None

    def _generate_full_command(self) -> str:
        if self._executable is None:
            return ""

        options = self._options
        out_csv = os.path.join(self._run_dir, f"output.{self._ep_num}.csv")
        out_json = os.path.join(self._run_dir, f"output.{self._ep_num}.json")
        if self._prefill:
            out_csv += ".prefill"
            out_json += ".prefill"

        cmd_parts = ["sudo", self._executable]

        simple_flags = [
            ("buckets", "-b"),
            ("bucket_prefix", "-bp"),
            ("duration", "-d"),
            ("loop", "-l"),
            ("max_keys", "-mk"),
            ("objects", "-n"),
            ("region", "-r"),
            ("report_intervals", "-ri"),
            ("threads", "-t"),
            ("size", "-z"),
        ]
        for key, flag in simple_flags:
            if options[key]:
                cmd_parts.append(f"{flag} {options[key]}")

        mode = options["prefill_modes"] if self._prefill else options["modes"]
        if mode:
            cmd_parts.append(f"-m {mode}")

        obj_prefix = self._build_object_prefix()
        if obj_prefix:
            cmd_parts.append(f"-op {obj_prefix}")

        cmd_parts.append(f"-o {out_csv}")
        cmd_parts.append(f"-j {out_json}")

        for key, flag in [("secret_key", "-s"), ("access_key", "-a"), ("url", "-u")]:
            if key in self._endpoint:
                cmd_parts.append(f"{flag} {self._endpoint[key]}")

        return " ".join(cmd_parts)
