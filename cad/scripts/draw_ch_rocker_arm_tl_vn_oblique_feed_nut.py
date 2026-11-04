"""Create the four-view purchased-reference sheet for the ReliaBot Tr8x2 brass flange nut, as fitted (MHA-CH-06-TL-VN-82).

Identification and the listing's nominal size references, with its stock,
ordering SKU and the fit-up note; no fabrication controls. The orthographic
views are 1:1 in the ``tall_top`` cells (see the spec's lane budget).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping
from typing import Any

import _telemetry
from _com import _early_bound
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import _SW_HLR
from _machinist_review_mode import MachinistReviewMode
from _purchased_fastener_drawing import NumberFit
from _purchased_part_drawing import build_purchased_part_drawing
from _supplier_screw_dimensions import annotate_supplier_screw
from _supplier_screw_layout import supplier_screw_margins
from _supplier_text_shelf import assert_supplier_shelves, shelve_supplier_text
import ch_rocker_arm_tl_vn_oblique_feed_nut_spec as supplier


MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_feed_nut"]
PART_STEM = SPEC.artifact_stem
# The footer's ITEM row: the listing's designation in plain text.
ITEM = "TR8X2 BRASS FLANGE NUT, SPIGOT FACED OFF"
VIEW_LAYOUT = "tall_top"
# The retired TL-VN-55 sheet's shelves for the same nut: every chord's
# horizontal text is wider than its span or crosses its own vertical
# dimension line, so each text slides sideways, just past all of its own line
# ink on its free side; the native tips, witnesses and lines stay put.
SHELVES = {
    name: (orientation == "horizontal", side)
    for (name, _value, orientation), side in zip(
        supplier.SUPPLIER_REFERENCE_DIMENSIONS,
        ("right", "left", "right", "right", "right", "left"),
        strict=True,
    )
}


def projection_margins(
    margins: Mapping[str, tuple[float, float, float, float]],
) -> dict[str, tuple[float, float, float, float]]:
    """Refuse lane reserves that would move a view off its projection axis.

    The builder centres each view in its cell less its reserves. Front shares
    its vertical axis with Top and its horizontal axis with the unannotated
    (cell-centred) Right, so Front's reserves must match left/right and
    bottom/top, and Top's left/right. The spec authors balanced lanes; any
    other arrangement is refused here rather than costing the 1:1 Front row.
    """
    pairs = {"*Front": ((0, 2), (1, 3)), "*Top": ((0, 2),)}
    for name, lanes in margins.items():
        for a, b in pairs.get(name, ()):
            if abs(lanes[a] - lanes[b]) > 1e-12:
                raise ValueError(
                    f"{name}: supplier lane reserves {lanes!r} leave the projection axis"
                )
    return dict(margins)


SUPPLIER_MARGINS = projection_margins(
    supplier_screw_margins(
        supplier.SUPPLIER_REFERENCE_DIMENSIONS,
        planes=supplier.SUPPLIER_REFERENCE_PLANES,
        sides=supplier.SUPPLIER_REFERENCE_SIDES,
    )
)


def _assert_hidden_lines_removed(views: Mapping[str, Any]) -> None:
    """The orthographic views print no hidden edges after the final rebuild.

    The reference chords show in their views as construction lines; they lie
    on the axis or on visible edges, never as dashed edges across a face.
    """
    for name in ("*Front", "*Top", "*Right"):
        mode = int(_early_bound(views[name], "IView").GetDisplayMode2())
        if mode != _SW_HLR:
            raise RuntimeError(f"{name}: nut view is not hidden-lines-removed ({mode})")


async def build(adapter: Any) -> dict[str, str]:
    proofs = []

    def supplier_dimensions(adapter: Any, views: Any) -> None:
        if proofs:
            raise RuntimeError("supplier reference callback repeated")
        checks = []
        displays = annotate_supplier_screw(
            adapter,
            views,
            dimensions=supplier.SUPPLIER_REFERENCE_DIMENSIONS,
            formats=supplier.SUPPLIER_REFERENCE_FORMATS,
            starts=supplier.SUPPLIER_REFERENCE_STARTS,
            planes=supplier.SUPPLIER_REFERENCE_PLANES,
            sides=supplier.SUPPLIER_REFERENCE_SIDES,
            units=supplier.SUPPLIER_REFERENCE_UNITS,
            settled_checks=checks,
        )
        stations = shelve_supplier_text(adapter, displays, SHELVES)
        [settled_references] = checks
        settled_views = dict(views)

        def assert_references() -> None:
            # The final check reacquires every native reference, then
            # re-proves the shelves against the stations measured here.
            assert_supplier_shelves(adapter, settled_references(), SHELVES, stations)
            _assert_hidden_lines_removed(settled_views)

        proofs.append(assert_references)

    def assert_supplier_dimensions() -> None:
        if len(proofs) != 1:
            raise RuntimeError("supplier references omitted or repeated")
        proofs[0]()

    # The 18-character registry number overruns the template's DWG. NO.
    # cell into REV; fit it there, measured. The footer note is fit-up work,
    # so the general line reads cut at assembly per it, as for the carriage
    # screws.
    return await build_purchased_part_drawing(
        adapter,
        SPEC,
        item=ITEM,
        cut_to_suit=True,
        number_fit=NumberFit.SHRINK_TO_CELL,
        supplier_dimensions=supplier_dimensions,
        supplier_margins=SUPPLIER_MARGINS,
        settled_checks=(assert_supplier_dimensions,),
        view_layout=VIEW_LAYOUT,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
