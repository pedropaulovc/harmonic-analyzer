"""Create the purchased reference drawing for the oblique-trammel riser screw."""

from __future__ import annotations

import argparse
import sys
from functools import partial
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _part_properties import part_drawing_unit
from _purchased_fastener_drawing import NumberFit, build_purchased_fastener_drawing
from _supplier_screw_dimensions import annotate_supplier_screw
from _supplier_screw_layout import supplier_screw_margins
import ch_rocker_arm_tl_vn_oblique_riser_screw_spec as supplier


SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_riser_screw"]
# The footer's ITEM row: the fastener table's callout for the bought screw.
ITEM = "#4-40 X 5/8 B18.6.3 FLAT HEAD"
# Only the sizes needed to buy a replacement: length, head diameter (the
# riser countersink's fit) and thread. The 82 deg head angle and head height
# follow from the B18.6.3 flat head in ITEM. The part's reference sketch still
# authors the unprinted rows by design; the targeted import deletes them.
PRINTED_REFERENCES = ("SupplierLength", "SupplierHeadDiameter", "SupplierThreadDiameter")


def _printed_rows() -> tuple[tuple[str, float, str], ...]:
    rows = {row[0]: row for row in supplier.SUPPLIER_REFERENCE_DIMENSIONS}
    missing = [name for name in PRINTED_REFERENCES if name not in rows]
    if missing:
        raise ValueError(f"printed supplier references are not authored: {missing}")
    return tuple(rows[name] for name in PRINTED_REFERENCES)


def _printed(settings: dict[str, Any]) -> dict[str, Any]:
    return {name: value for name, value in settings.items() if name in PRINTED_REFERENCES}


def _aligned_margins(
    margins: dict[str, tuple[float, float, float, float]],
) -> dict[str, tuple[float, float, float, float]]:
    """Keep each view centred in its cell so the views stay in ASME projection.

    The builder centres every view in its cell less these lane reserves. One
    lane on one side (length right, thread below) shifted FRONT about .12 off the
    TOP axis and the RIGHT row. Reserving the larger lane on both sides of the
    axis a view shares with FRONT only adds room; it never shrinks a lane.
    """
    aligned = {}
    for name, (left, bottom, right, top) in margins.items():
        across = max(left, right) if name in ("*Front", "*Top") else None
        along = max(bottom, top) if name in ("*Front", "*Right") else None
        aligned[name] = (
            left if across is None else across,
            bottom if along is None else along,
            right if across is None else across,
            top if along is None else along,
        )
    return aligned


async def build(adapter: Any) -> dict[str, str]:
    # The .112 in thread and .212 in head chords are narrower than their text:
    # shelve it beside the arrows instead of between the extension lines.
    view_layout = "supplier_top"
    checks = []
    dimensions = _printed_rows()
    planes = _printed(supplier.SUPPLIER_REFERENCE_PLANES)
    sides = _printed(supplier.SUPPLIER_REFERENCE_SIDES)
    # The 18-character registry number overruns the template's DWG. NO.
    # cell into REV; fit it there, measured.
    return await build_purchased_fastener_drawing(
        adapter,
        SPEC,
        item=ITEM,
        number_fit=NumberFit.SHRINK_TO_CELL,
        view_layout=view_layout,
        supplier_dimensions=partial(
            annotate_supplier_screw,
            dimensions=dimensions,
            formats=_printed(supplier.SUPPLIER_REFERENCE_FORMATS),
            starts=_printed(supplier.SUPPLIER_REFERENCE_STARTS),
            planes=planes,
            sides=sides,
            settled_checks=checks,
            layout=view_layout,
        ),
        supplier_margins=_aligned_margins(
            supplier_screw_margins(dimensions, planes=planes, sides=sides)
        ),
        settled_checks=checks,
        unit=part_drawing_unit("ch-rocker-arm-tl-vn-oblique-riser-screw"),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
