"""COM-free positive control for cProfile's thread scope on the installed Python.

Run through ``uv run python cad/scripts/diagnostics/probe_cprofile_thread_scope.py``.
The worker starts before profiling, then makes exactly 1000 calls not made by
the main thread. This reports observation, not a required interpreter behavior.
"""

import cProfile
import json
import pstats
import sys
import threading


def observe():
    started, finished = threading.Event(), threading.Event()

    def background_only():
        sum(range(10))

    def worker():
        started.wait()
        for _ in range(1000):
            background_only()
        finished.set()

    thread = threading.Thread(target=worker)
    thread.start()
    profile = cProfile.Profile()
    profile.enable()
    started.set()
    finished.wait()
    profile.disable()
    thread.join()
    calls = sum(
        row[1]
        for key, row in pstats.Stats(profile).stats.items()
        if key[2] == "background_only"
    )
    return {
        "python": sys.version,
        "actual_worker_calls": 1000,
        "profiled_worker_calls": calls,
        "profile_scope": "includes_worker" if calls else "excludes_worker",
    }


if __name__ == "__main__":
    print(json.dumps(observe(), indent=2))
