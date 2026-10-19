"""Share a bounded CPU-worker budget across local checks and worktrees.

The check owns its OS slot locks, not its doit parent. Pytest's worker count
is reduced to the slots actually granted, so concurrent suites can share
the host without multiplying their independent worker limits.
"""

from __future__ import annotations

import os
from contextlib import ExitStack
from pathlib import Path
import runpy
import sys
import tempfile
import time

from filelock import FileLock, Timeout

import _telemetry


def command(cmd: list[str], task: str) -> list[str]:
    """Wrap a gate's Python argv without starting another supervisor process."""
    return [cmd[0], str(Path(__file__).resolve()), task, *cmd[1:]]


def lock_path() -> Path:
    override = os.environ.get("HARMONIC_LOCAL_CHECK_LOCK")
    if override:
        return Path(override)
    base = os.environ.get("PROGRAMDATA") or tempfile.gettempdir()
    return Path(base) / "harmonic-analyzer" / "local-check.lock"


def cpu_slots() -> int:
    """Reserve roughly 20% of logical CPU capacity for the rest of the host."""
    default = max(1, round((os.cpu_count() or 1) * 0.8))
    capacity = int(os.environ.get("HARMONIC_LOCAL_CHECK_CPU_SLOTS", default))
    if capacity < 1:
        raise ValueError("HARMONIC_LOCAL_CHECK_CPU_SLOTS must be positive")
    return capacity


def _worker_request(args: list[str]) -> tuple[int, slice | None]:
    """Read pytest's last xdist worker option; other entry points use one slot."""
    if args[:2] != ["-m", "pytest"]:
        return 1, None
    value = "0"
    option = None
    for index in range(2, len(args)):
        arg = args[index]
        if arg == "--":
            break
        if arg in ("-n", "--numprocesses"):
            value = args[index + 1]
            option = slice(index, index + 2)
        elif arg.startswith("--numprocesses="):
            value = arg.split("=", 1)[1]
            option = slice(index, index + 1)
        elif arg.startswith("-n") and len(arg) > 2:
            value = arg[2:]
            option = slice(index, index + 1)
    if value in ("auto", "logical"):
        return os.cpu_count() or 1, option
    workers = int(value)
    if workers < 0:
        raise ValueError("pytest worker count must be nonnegative")
    return max(1, workers), option if workers else None


def _execute(args: list[str]) -> None:
    if args[0] == "-m":
        sys.argv = args[1:]
        sys.path[0] = os.getcwd()
        runpy.run_module(args[1], run_name="__main__", alter_sys=True)
        return
    sys.argv = args
    sys.path[0] = str(Path(args[0]).resolve().parent)
    runpy.run_path(args[0], run_name="__main__")


def main() -> None:
    """Admit available worker slots atomically, then execute under their locks."""
    task, *args = sys.argv[1:]
    path = lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    capacity = cpu_slots()
    requested, worker_option = _worker_request(args)
    minimum = (min(requested, capacity) + 1) // 2
    started = time.monotonic()
    next_log = started + 30
    service = _telemetry.BUILD_INFRA_SERVICE
    with ExitStack() as slots:
        granted = 0
        with _telemetry.span(
            "local.check.wait", label=task, lock_path=str(path),
            cpu_slots=capacity, requested_workers=requested,
            minimum_workers=minimum, service=service,
        ):
            _telemetry.info(
                f"[local.check] {task} requesting up to {requested}/{capacity} CPU slots"
            )
            while not granted:
                try:
                    # This lock protects allocation only, never execution.
                    with FileLock(path).acquire(timeout=0):
                        for index in range(capacity):
                            try:
                                slots.enter_context(
                                    FileLock(f"{path}.{index}").acquire(timeout=0)
                                )
                            except Timeout:
                                continue
                            granted += 1
                            if granted == requested:
                                break
                        # Do not strand a long suite at one worker because
                        # short checks temporarily occupy the remaining slots.
                        if granted < minimum:
                            slots.close()
                            granted = 0
                except Timeout:
                    pass
                if granted:
                    break
                if time.monotonic() >= next_log:
                    _telemetry.info(f"[local.check] {task} waiting for CPU slots at {path}")
                    next_log = time.monotonic() + 30
                time.sleep(0.25)
        acquired = time.monotonic()
        if worker_option is not None:
            args[worker_option] = ["-n", str(granted)]
        try:
            _telemetry.info(
                f"[local.check] {task} admitted {granted}/{capacity} CPU slots "
                f"after {acquired - started:.1f}s",
                label=task, wait_s=acquired - started, cpu_slots=capacity,
                requested_workers=requested, granted_workers=granted, service=service,
            )
            # No ambient execution span: preserve process-root telemetry depth.
            _execute(args)
        finally:
            slots.close()
            _telemetry.info(
                f"[local.check] {task} released {granted} CPU slots",
                label=task, held_s=time.monotonic() - acquired,
                granted_workers=granted, service=service,
            )


if __name__ == "__main__":
    try:
        main()
    finally:
        _telemetry.shutdown()
