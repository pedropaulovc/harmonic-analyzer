"""Release every cad/out document SolidWorks still holds -- a COM session whose
only work is the connect-time discard + the teardown close in ``run_build``.

dodo runs this under the seat when a remote-cache restore is refused by a share
lock (``_artifact_cache.RestoreLocked``): a crashed or killed build never reached
``run_build``'s teardown, so its documents stay resident (and locked) across COM
sessions, and extracting the cached artefact over them fails. Building locally
instead would fork the artefact's ``.execution`` token off the fleet's, so the
task must first free the file, then retry the restore.

    uv run cad/scripts/release_seat_documents.py
"""
from __future__ import annotations

import sys
from typing import Any

from _common import run_build


async def build(adapter: Any) -> dict[str, str]:
    return {}


if __name__ == "__main__":
    sys.exit(run_build(build))
