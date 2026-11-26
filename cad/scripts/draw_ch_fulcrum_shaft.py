r"""Create the curated machinist drawing for the lever fulcrum shaft.

The sheet prints decimal inch (the part's ``drawing_unit: in``).
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import dimension_name, place_view

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimensions import set_dimension_callouts
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _part_properties import part_drawing_unit
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from ch_fulcrum_shaft_notes import ACROSS_FLAT_CALLOUT, SHAFT_DIA_CALLOUT
from ch_fulcrum_shaft_spec import (
    ACROSS_FLAT,
    CYLINDER_HALF,
    DOME_R,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    FLAT_BASELINE,
    FLAT_FROM_END,
    FLAT_HEIGHT,
    FLAT_LENGTH,
    FLAT_PITCH,
    SHAFT_DIA,
    SHAFT_DIA_FRACTION_DENOMINATOR,
    SHAFT_LENGTH,
    UNIT,
)
from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _gtol_sphere import SphereFace
from _printed_limits import limits
from _supplier_dimensions import supplier_reference_dimension

# Feature-export declarations (export_features; cad/docs/pipeline/
# features-travelers.md): what this sheet prints, in the part frame
# (ch_fulcrum_shaft_spec: axis Z centred on z = 0, the cylinder
# +-CYLINDER_HALF, a full hemisphere of DOME_R past each end, both flats on
# +Y). The datum end is the -Z dome, the sheet's left tip that the overall
# length and both flat stations run from (each the flat's edge nearer it).
# The dome radius is a printed reference; a full hemisphere's height is its
# radius. The declarations print nothing.
_SHAFT = DRAWING_PRECISION["ShaftProfile"]
_FLAT = DRAWING_PRECISION["FlatProfile"]
_NOTES = "ch_fulcrum_shaft_notes"
_TIP_Z = (-SHAFT_LENGTH / 2.0, SHAFT_LENGTH / 2.0)
part_metadata(
    model_sources=("SHAFT_DIA", "SHAFT_LENGTH", "CYLINDER_HALF"),
    precision_sources=("DRAWING_PRECISION",),
)
_DOME_FIELDS = {
    "radius_ref": (DOME_R, ("DOME_R",)),
    "height_ref": (DOME_R, ("DOME_R",)),
}
requirement(
    "datum_end",
    kind="dome",
    faces=(SphereFace(2.0 * DOME_R, (0.0, 0.0, -CYLINDER_HALF)),),
    requirements=("plane",),
    fields={
        "plane": (
            {"frame": "model", "axis": "z", "value": _TIP_Z[0]},
            ("SHAFT_LENGTH",),
        ),
        "outward": ([0.0, 0.0, -1.0], ("SHAFT_LENGTH",)),
        **_DOME_FIELDS,
    },
)
requirement(
    "far_end",
    kind="dome",
    faces=(SphereFace(2.0 * DOME_R, (0.0, 0.0, CYLINDER_HALF)),),
    requirements=("length",),
    fields={
        "plane": (
            {"frame": "model", "axis": "z", "value": _TIP_Z[1]},
            ("SHAFT_LENGTH",),
        ),
        "outward": ([0.0, 0.0, 1.0], ("SHAFT_LENGTH",)),
        "length": (
            limits(SHAFT_LENGTH, _SHAFT["OverallLength"], unit=UNIT),
            ("SHAFT_LENGTH", "UNIT"),
        ),
        "length_nominal": (SHAFT_LENGTH, ("SHAFT_LENGTH",)),
        "length_from": ("datum_end", ("SHAFT_LENGTH",)),
        **_DOME_FIELDS,
    },
    precision={"length": _SHAFT["OverallLength"]},
)
# The O.D.: the bought 1/4 ground rod as supplied, a fraction reference with
# its stock line (drawing-guidelines.md rule 4); its catalogue band is the
# spec's analysis band, not printed.
requirement(
    "outer",
    kind="diameter",
    faces=(CylinderFace(SHAFT_DIA),),
    requirements=("stock",),
    fields={
        "axis": ([0.0, 0.0, 1.0], ("SHAFT_DIA",)),
        "at": ([0.0, 0.0, 0.0], ("SHAFT_DIA",)),
        "span": ([-CYLINDER_HALF, CYLINDER_HALF], ("CYLINDER_HALF",)),
        "dia_ref": (SHAFT_DIA, ("SHAFT_DIA", "SHAFT_DIA_FRACTION_DENOMINATOR")),
        "stock": (SHAFT_DIA_CALLOUT, ((_NOTES, "SHAFT_DIA_CALLOUT"),)),
        "callout": (SHAFT_DIA_CALLOUT, ((_NOTES, "SHAFT_DIA_CALLOUT"),)),
    },
    precision={"dia_ref": _SHAFT["ShaftDia"]},
)
# (feature, flat centre z, its station from the datum tip, the station's
# printed dimension and spec name)
_FLATS = (
    ("flat_datum", -FLAT_PITCH / 2.0, FLAT_FROM_END, "FlatFromEnd", "FLAT_FROM_END"),
    ("flat_far", FLAT_PITCH / 2.0, FLAT_BASELINE, "FlatBaseline", "FLAT_BASELINE"),
)
for _name, _centre, _station, _station_dim, _station_src in _FLATS:
    requirement(
        _name,
        kind="flat",
        faces=(PlanarFace((0.0, 1.0, 0.0), FLAT_HEIGHT, contains_z_mm=_centre),),
        requirements=("across", "station", "length"),
        fields={
            "normal": ([0.0, 1.0, 0.0], ("FLAT_HEIGHT",)),
            "span": (
                [_centre - FLAT_LENGTH / 2.0, _centre + FLAT_LENGTH / 2.0],
                ("FLAT_PITCH", "FLAT_LENGTH"),
            ),
            "across": (
                limits(ACROSS_FLAT, _FLAT["AcrossFlat"], unit=UNIT),
                ("ACROSS_FLAT", "UNIT"),
            ),
            "across_nominal": (ACROSS_FLAT, ("ACROSS_FLAT",)),
            "station": (
                limits(_station, _FLAT[_station_dim], unit=UNIT),
                (_station_src, "UNIT"),
            ),
            "station_nominal": (_station, (_station_src,)),
            "station_from": ("datum_end", (_station_src,)),
            "length": (
                limits(FLAT_LENGTH, _FLAT["FlatLength"], unit=UNIT),
                ("FLAT_LENGTH", "UNIT"),
            ),
            "length_nominal": (FLAT_LENGTH, ("FLAT_LENGTH",)),
            "callout": (ACROSS_FLAT_CALLOUT, ((_NOTES, "ACROSS_FLAT_CALLOUT"),)),
        },
        precision={
            "across": _FLAT["AcrossFlat"],
            "station": _FLAT[_station_dim],
            "length": _FLAT["FlatLength"],
        },
    )


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_fulcrum_shaft"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

# One side view at 3:2: the .012 flats and their stations read at that size.
# At the .300 pitch (#1038) the 7.01 shaft no longer fits at 2:1 with the
# .24 left of its left tip and the ~45 mm across-flat block right of its
# right tip (356 + 10 + 51 mm against the 406 mm drawable width). No end
# view: from the end the dome hides the flats, so it showed a bare circle
# (machinist review r1).
SHEET_SCALE = (3.0, 2.0)
VIEW_SCALE = SHEET_SCALE[0] / SHEET_SCALE[1]
AXIS_Y = 0.212
# Left of the sheet centre: the across-flat callout block starts at its
# dimension line right of the right tip and runs ~45 mm right (r2 crossed
# the border at 0.216); the left tip's .24 still clears the zone margin.
RIGHT_CENTER = (0.198, AXIS_Y)
# The isometric fills the free band over the title block at 1:1 (under the
# sheet scale, hence its note): the shaft runs lower-left to upper-right
# about 122 x 70 mm, so x 0.257-0.379, y 0.087-0.157.
ISO_CENTER = (0.318, 0.122)
ISO_SCALE = (1, 1)


def _on_sheet(mm: float) -> float:
    """A model length in mm as sheet metres at the view scale."""
    return mm * VIEW_SCALE / 1000.0


# Both profile sketches lie on the Right plane, so every print dimension
# lands in the side view.  The sketch +u axis is model -Z, which the *Right
# view draws to sheet-RIGHT (the build_ch_pivot_shaft mapping): both flat
# stations run from the sheet-LEFT dome tip, the flat length and the
# across-flat witness ride the sheet-right flat, the dome radius the left
# dome.
_LEFT_TIP_X = RIGHT_CENTER[0] - _on_sheet(SHAFT_LENGTH / 2.0)
_RIGHT_TIP_X = RIGHT_CENTER[0] + _on_sheet(SHAFT_LENGTH / 2.0)
_RIGHT_FLAT_INNER_X = _RIGHT_TIP_X - _on_sheet(FLAT_FROM_END + FLAT_LENGTH)
# Rows above the shaft, nearest first; every text stands where no other
# dimension's extension line runs: .24 outboard left of the left tip, the
# flat length left of its flat's inner edge, and the overall length (the
# only dimension off the right tip) on the top row.
_ROW_1 = AXIS_Y + 0.014
_ROW_2 = AXIS_Y + 0.026
_ROW_3 = AXIS_Y + 0.038
_SHAFT_BOTTOM_Y = AXIS_Y - _on_sheet(SHAFT_DIA / 2.0)
_SHAFT_TOP_Y = AXIS_Y + _on_sheet(SHAFT_DIA / 2.0)
# The Ø block hangs left of its own vertical dimension line and SOLIDWORKS
# sets the widest row's last glyph against that line: the v46 re-render
# struck the final E of "DIAMETRAL CLEARANCE" (machinist review, rule 14).
# Two trailing spaces on every row stop the ink short of the line and its
# shelf, as draw_dt_crank_drive_gear does for its chamfer block.
SHAFT_DIA_CALLOUT_ROWS = "\n".join(f"{row}  " for row in SHAFT_DIA_CALLOUT.splitlines())
# The across-flat block hangs right of its dimension line, which drops to the
# shelf at the block's left edge: the S of SETS touched it (machinist review,
# rule 14). A leading space on every row holds the ink off that line.
ACROSS_FLAT_CALLOUT_ROWS = "\n".join(
    f" {row}" for row in ACROSS_FLAT_CALLOUT.splitlines()
)
RIGHT_KEEP = {
    "FlatFromEnd": (_LEFT_TIP_X - 0.0065, _ROW_1),
    "FlatLength": (_RIGHT_FLAT_INNER_X - 0.0105, _ROW_1),
    "FlatBaseline": (RIGHT_CENTER[0] - 0.020, _ROW_2),
    "OverallLength": (RIGHT_CENTER[0], _ROW_3),
    # Under the shaft: the stock Ø with its line under it at mid-length (the
    # callout block hangs left of its dimension line; r1 had it over the
    # dome radius). 0.022 keeps the text ~3 mm below the silhouette (r1
    # printed it inside the outline). The dome's reference radius sits
    # under the left dome.
    "ShaftDia": (RIGHT_CENTER[0], AXIS_Y - 0.022),
    "DomeRadius": (_LEFT_TIP_X + 0.030, AXIS_Y - 0.018),
    # Below and right of the right tip, outside its extension lines, so the
    # dimension line stops at the value instead of running through the
    # callout under it (r1). The parent-vendor identity makes the block and
    # shelf ~45 mm wide; move both 4 mm left from the border-touching layout,
    # retaining 6 mm between the dimension line and the right dome tip.
    "AcrossFlat": (_RIGHT_TIP_X + 0.006, AXIS_Y - 0.022),
}


def _set_dome_reference(adapter: Any, annotations: list[Any]) -> None:
    """Print DomeRadius as ``2X (SR.125)``: both domes, a spherical reference
    (the full hemisphere follows from the toleranced diameter). The display's
    own radius prefix stays behind the ``(S``; the readback proves it stuck."""
    (annotation,) = [
        item for item in annotations if dimension_name(adapter, item) == "DomeRadius"
    ]
    annotation = _early_bound(annotation, "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    existing = str(display.GetText(1) or "")  # swDimensionTextPrefix
    prefix = "2X (S" + existing
    display.SetText(1, prefix)
    display.SetText(2, ")")  # swDimensionTextSuffix
    applied = (str(display.GetText(1) or ""), str(display.GetText(2) or ""))
    _telemetry.info(f"DomeRadius: prefix {existing!r} -> {applied[0]!r}")
    if applied != (prefix, ")"):
        raise RuntimeError(
            f"failed to mark DomeRadius as a spherical reference: {applied}"
        )


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    check("open fulcrum-shaft source", adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Iso View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Iso View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit("ch-fulcrum-shaft"),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Fulcrum Shaft Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "fulcrum shaft; bearing shaft; turned steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(3, 2))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (right, iso):
        set_hidden_lines_removed(adapter, view)

    curated = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Rule 4: the three-place across-flat size names what it sets.
    set_dimension_callouts(adapter, curated, {"AcrossFlat": ACROSS_FLAT_CALLOUT_ROWS})
    _set_dome_reference(adapter, curated)
    # The bought rod's diameter: an untoleranced fraction reference with its
    # stock line (rule 4), as draw_dt_crank_pinion_pin prints its rod.
    (shaft_dia,) = (
        annotation
        for annotation in curated
        if dimension_name(adapter, annotation) == "ShaftDia"
    )
    supplier_reference_dimension(
        adapter,
        _early_bound(shaft_dia, "IAnnotation").GetSpecificAnnotation(),
        label="fulcrum shaft rod diameter",
        units="in",
        precision=_SHAFT["ShaftDia"],
        expected_mm=SHAFT_DIA,
        presentation="diameter",
        fraction_denominator=SHAFT_DIA_FRACTION_DENOMINATOR,
        callout=SHAFT_DIA_CALLOUT_ROWS,
    )

    # 0.020: the note is left-aligned on its anchor, so the ink starts here. The
    # left bound is the 12.7 mm zone margin (~0.0127), which the re-centred frame
    # rule now matches (~0.0126); 0.020 clears both, and the audit enforces it.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.115)
    # The iso renders at 1:1 while the title block reads 2:1, so the pictorial
    # needs its own scale callout; it stands in the empty lower-right corner
    # of the iso's bounding box, clear of the title block.
    add_property_linked_note(
        adapter, "Iso View Note", ISO_CENTER[0] + 0.015, ISO_CENTER[1] - 0.022
    )

    return finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Fulcrum Shaft Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
