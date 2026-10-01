"""Builds the rados bench command line for a single radosbench instance.

It returns the full executable string that can be used to run a cli command.
It encapsulates CLI argument parsing, option formatting, and output redirection.
"""

import os
from logging import Logger, getLogger
from typing import Optional

import common
from cli_options import CliOptions
from command.command import Command

log: Logger = getLogger("cbt")


class RadosbenchCommand(Command):
    """A single rados bench command line for one process execution."""

    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        options: dict[str, Optional[str]],
        run_dir: str,
        proc_id: int = 0,
        pool_name: str = "rados-bench-cbt",
        conf_path: str = "/etc/ceph/ceph.conf",
        runtime: str = "300",
        mode: str = "write",
        concurrent_ops: int = 16,
    ) -> None:
        self._run_dir: str = run_dir
        self._proc_id: int = proc_id
        self._pool_name: str = pool_name
        self._conf_path: str = conf_path
        self._runtime: str = runtime
        self._mode: str = mode
        self._concurrent_ops: int = concurrent_ops
        super().__init__(options)

    # ------------------------------------------------------------------
    # Command ABC implementation
    # ------------------------------------------------------------------

    def _parse_options(self, options: dict[str, Optional[str]]) -> CliOptions:
        parsed_options: CliOptions = CliOptions()

        # Option values
        parsed_options["op_size"] = str(options.get("op_size") or 4194304)
        parsed_options["object_set_id"] = str(options.get("object_set_id") or "")
        parsed_options["pool_per_proc"] = "true" if options.get("pool_per_proc") else None
        parsed_options["write_omap"] = "true" if options.get("write_omap") else None

        max_objects = options.get("max_objects")
        parsed_options["max_objects"] = str(max_objects) if max_objects is not None else None

        return parsed_options

    def _parse_global_options(self, options: dict[str, Optional[str]]) -> CliOptions:
        return CliOptions(options)

    def _generate_output_directory_path(self) -> str:
        return self._run_dir

    @property
    def benchmark(self) -> str:
        return "radosbench"

    def _generate_full_command(self) -> str:
        if self._executable is None:
            return ""

        options = self._options
        op_type = "write" if self._mode == "prefill" else self._mode

        # Determine pool name and run name
        if options["pool_per_proc"]:
            pool_name = f"rados-bench-`{common.get_fqdn_cmd()}`-{self._proc_id}"  # type: ignore [no-untyped-call]
            run_name_arg = ""
        else:
            pool_name = self._pool_name
            object_set_id = options["object_set_id"] or ""
            fqdn_cmd = common.get_fqdn_cmd()  # type: ignore [no-untyped-call]
            run_name_arg = f"--run-name {object_set_id} `{fqdn_cmd}`-{self._proc_id}"

        op_size_arg = f"-b {options['op_size']}" if op_type == "write" else ""
        concurrent_ops_arg = f"--concurrent-ios {self._concurrent_ops}" if self._concurrent_ops else ""
        max_objects_arg = f"--max-objects {options['max_objects']}" if options["max_objects"] else ""
        write_omap_arg = "--write-omap" if options["write_omap"] else ""

        out_file = os.path.join(self._run_dir, f"output.{self._proc_id}")
        objecter_log = os.path.join(self._run_dir, f"objecter.{self._proc_id}.log")

        cmd_parts = [
            self._executable,
            "-c",
            self._conf_path,
            "-p",
            pool_name,
            "bench",
        ]
        if op_size_arg:
            cmd_parts.append(op_size_arg)
        cmd_parts.append(str(self._runtime))
        cmd_parts.append(op_type)
        if concurrent_ops_arg:
            cmd_parts.append(concurrent_ops_arg)
        if max_objects_arg:
            cmd_parts.append(max_objects_arg)
        if write_omap_arg:
            cmd_parts.append(write_omap_arg)
        if run_name_arg:
            cmd_parts.append(run_name_arg)
        cmd_parts.append("--no-cleanup")
        cmd_parts.append(f"2> {objecter_log}")
        cmd_parts.append(f"> {out_file}")

        return " ".join(cmd_parts)
