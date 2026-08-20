"""Run the doit graph with a human-facing console verbosity flag.

Examples:
    uv run python build.py --verbosity warning -n 4
    uv run python build.py --verbosity debug check:math

The wrapper only consumes ``--verbosity``; every other argument is passed to
``doit`` unchanged. Structured telemetry capture remains full-fidelity.
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence

from doit.doit_cmd import DoitMain

_LEVELS = ("debug", "info", "success", "warning", "error", "critical")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--verbosity", choices=_LEVELS, default="warning")
    options, doit_args = parser.parse_known_args(argv)
    if options.verbosity is not None:
        os.environ["HARMONIC_VERBOSITY"] = options.verbosity
    return DoitMain().run(list(doit_args))


if __name__ == "__main__":
    raise SystemExit(main())
