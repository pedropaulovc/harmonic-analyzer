"""Run one local Python check at a time across submitters and worktrees.

The check itself owns the OS file lock, not its doit parent: a parent dying
cannot admit another check while this one is still executing. No inherited
"already admitted" flag lets an independent child bypass the host limit.
"""

from __future__ import annotations

import os
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
    task, *args = sys.argv[1:]
    path = lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(path)
    started = time.monotonic()
    service = _telemetry.BUILD_INFRA_SERVICE
    with _telemetry.span("local.check.wait", label=task, lock_path=str(path), service=service):
        _telemetry.info(f"[local.check] {task} waiting for {path}")
        while True:
            try:
                lock.acquire(timeout=30)
                break
            except Timeout:
                _telemetry.info(f"[local.check] {task} still waiting for {path}")
    acquired = time.monotonic()
    try:
        _telemetry.info(
            f"[local.check] {task} admitted after {acquired - started:.1f}s",
            label=task, wait_s=acquired - started, service=service,
        )
        # Preserve the entry point's top-level telemetry context. An ambient
        # wrapper span would change every operation's process-relative depth.
        _execute(args)
    finally:
        lock.release()
        _telemetry.info(
            f"[local.check] {task} released",
            label=task, held_s=time.monotonic() - acquired, service=service,
        )


if __name__ == "__main__":
    try:
        main()
    finally:
        _telemetry.shutdown()
