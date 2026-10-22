"""Build the installed McMaster-Carr 9432K31 channel spring.

The supplier-native recipe is authored in its vendor frame: spring axis +X,
origin at mid-length, hook-eye axes +Z.  ``INSTALLED_LENGTH_MM`` is the actual
mount pose's catalogue inside-hook length.  The production body is not rotated;
assembly placement owns the vendor-to-machine transform.

Run with SolidWorks open::

    uv run python cad\\scripts\\build_ch_vn_channel_spring_installed.py
"""

from __future__ import annotations

import sys

from _session import run_build
from _saved_part_guard import require_saved_drawing_properties
from _spring import build_spring
from ch_vn_channel_spring_installed_notes import DRAWING_NOTES
import ch_vn_channel_spring_installed_spec as spec
from _supplier_extension_spring import add_extension_spring_references


PART_NAME = "ch-vn-channel-spring-installed"


async def _add_supplier_references(adapter) -> None:
    await add_extension_spring_references(
        adapter, free_length_mm=spec.FREE_LENGTH_MM, max_length_mm=spec.MAX_LENGTH_MM,
        coil_od_mm=spec.SUPPLIER_COIL_OD_MM, wire_dia_mm=spec.SUPPLIER_WIRE_DIA_MM,
        body_count=1, od_tolerance_mm=spec.SUPPLIER_COIL_OD_TOLERANCE_MM,
        od_tolerance_precision=spec.SUPPLIER_COIL_OD_TOLERANCE_PRECISION,
    )


async def build(adapter) -> dict[str, str]:
    artefacts = await build_spring(
        adapter,
        PART_NAME,
        spec.INSTALLED_LENGTH_MM,
        drawing_properties={
            "Manufacturing Notes": DRAWING_NOTES,
        },
        before_save=_add_supplier_references,
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
