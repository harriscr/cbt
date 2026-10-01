"""Builds the ceph_test_rados command line for a single CephTestRados instance.

It returns the full executable string that can be used to run a cli command.
It encapsulates CLI argument parsing, option formatting, and output redirection.

Bug fixes from the legacy mkcmd() string builder:
  D4a: The awk pipeline now emits `}' >` (space before `>`), not `}'>`
       (implicit Python string literal concatenation collapsed the space).
  D4b: `append` is a separately addressable weight key; the legacy code had
       `'cache_evict' 'append'` which Python concatenated into `'cache_evictappend'`.
  D4c: `--max-seconds` is suppressed when the value is zero.  The legacy guard
       used `if value:` on a string, so `'0'` was truthy and the flag was always
       emitted.
"""

import os
from logging import Logger, getLogger
from typing import Any, Optional

from cli_options import CliOptions
from command.command import Command

log: Logger = getLogger("cbt")

# Boolean flags that map directly to CLI flags (underscore → hyphen).
_BOOL_FLAGS: tuple[str, ...] = ("ec_pool", "write_fadvise_dontneed", "pool_snaps")

# Variable flags that take a `--name value` form.  Order matches legacy output.
_VARIABLE_FLAGS: tuple[str, ...] = (
    "max_ops",
    "objects",
    "max_in_flight",
    "size",
    "min_stride_size",
    "max_stride_size",
    "max_seconds",
)


class CephTestRadosCommand(Command):
    """A single ceph_test_rados command line for one client execution."""

    def __init__(
        self,
        options: dict[str, Any],
        run_dir: str,
    ) -> None:
        self._run_dir: str = run_dir
        # Weights are a dict[str, float] — extracted before the base __init__
        # processes the rest through CliOptions (which is str-valued only).
        self._weights: dict[str, float] = options.get("weights") or {}
        # Forward only the str-valued subset to the base Command.__init__.
        str_options: dict[str, Optional[str]] = {k: v for k, v in options.items() if k != "weights"}
        super().__init__(str_options)

    # ------------------------------------------------------------------
    # Command ABC implementation
    # ------------------------------------------------------------------

    def _parse_options(self, options: dict[str, Any]) -> CliOptions:
        parsed: CliOptions = CliOptions()

        # Boolean flags — present only when truthy in the config dict.
        for flag in _BOOL_FLAGS:
            parsed[flag] = "true" if options.get(flag) else None

        # Variable flags — stored as strings; None means "absent".
        for var in _VARIABLE_FLAGS:
            raw = options.get(var)
            if raw is not None:
                # D4c: suppress max_seconds when value is zero.
                if var == "max_seconds" and int(raw) == 0:
                    parsed[var] = None
                else:
                    parsed[var] = str(raw)
            else:
                parsed[var] = None

        return parsed

    def _parse_global_options(self, options: dict[str, Any]) -> CliOptions:
        return CliOptions(options)

    def _generate_output_directory_path(self) -> str:
        return self._run_dir

    @property
    def benchmark(self) -> str:
        return "cephtestrados"

    def _generate_full_command(self) -> str:
        if self._executable is None:
            return ""

        options = self._options
        out_file = os.path.join(self._run_dir, "output")

        cmd_parts = [self._executable]

        # Boolean flags (--ec-pool, --write-fadvise-dontneed, --pool-snaps)
        for flag in _BOOL_FLAGS:
            if options.get(flag):
                cmd_parts.append(f"--{flag.replace('_', '-')}")

        # Variable flags (--max-ops N, --objects N, …)
        for var in _VARIABLE_FLAGS:
            value = options.get(var)
            if value is not None:
                cmd_parts.extend([f"--{var.replace('_', '-')}", value])

        # Op weights (--op <name> <weight> …)
        for op, weight in self._weights.items():
            cmd_parts.extend(["--op", op, str(weight)])

        cmd_parts.extend(["--pool", "ceph_test_rados"])

        # D4a fix: emit `}' >` with a proper space before the redirect.
        awk_pipeline = "| awk '{ print strftime(\"%Y-%m-%d %H:%M:%S\"), $0; fflush(); }'"
        cmd_parts.append(awk_pipeline)
        cmd_parts.append(f"> {out_file}")

        return " ".join(cmd_parts)
