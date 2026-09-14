"""Build the installed McMaster-Carr 9432K31 channel spring.

The supplier-native recipe is authored in its vendor frame: spring axis +X,
origin at mid-length, hook-eye axes +Z.  ``INSTALLED_LENGTH_MM`` is the actual
mount pose's catalogue inside-hook length.  The production body is not rotated;
assembly placement owns the vendor-to-machine transform.

Run with SolidWorks open::

    uv run python cad\\scripts\\build_channel_spring_installed.py
"""

from __future__ import annotations

import sys

from _common import run_build
from _saved_part_guard import require_saved_drawing_properties
from _spring import build_spring
from channel_spring_installed_notes import DRAWING_NOTES
from channel_spring_installed_spec import INSTALLED_LENGTH_MM


PART_NAME = "channel-spring-installed"


async def build(adapter) -> dict[str, str]:
    artefacts = await build_spring(
        adapter,
        PART_NAME,
        INSTALLED_LENGTH_MM,
        drawing_properties={
            "Manufacturing Notes": DRAWING_NOTES,
        },
    )
    require_saved_drawing_properties(
        adapter,
        (
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Stock Name",
            "Supplier",
            "Supplier SKUs",
            "Manufacturing Notes",
        ),
    )
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
