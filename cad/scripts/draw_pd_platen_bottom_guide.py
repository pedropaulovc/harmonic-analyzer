r"""Create the machinist drawing for MHA-PD-27, the platen's bottom guide.

The 1:1 front view carries the rail's length, height and the four printed
lock taps' stations; the top view above it shows the four rack-screw
counterbores; the right view carries the depth's native LIMITs. Each hole
family has one native Hole Wizard callout: the lock taps plain, the five
platen-screw taps transferred from MHA-PD-02 and the four rack-screw holes
struck from MHA-PD-26, both at MHA-PD-00 (owner rulings 2026-11-13 and
delegated rulings 2026-11-14, #2410). The sheet prints decimal inch (#290).

Run with SolidWorks open::

    uv run python cad\scripts\draw_pd_platen_bottom_guide.py pd-platen-bottom-guide
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
    remove_notes_matching,
)

import _config
from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_edges import visible_view_entities
from _drawing_hole_callout import add_native_hole_callout
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _drawing_view_display import set_hidden_lines_removed
from _hole_callout_thread_class import omit_title_block_thread_class
from _hole_spec import blind_cut_dia_mm
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _part_properties import part_drawing_unit
from _printed_limits import drilled_limits, limits
from _session import run_build
import _telemetry
from pd_platen_bottom_guide_spec import (
    BAND,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    GUIDE_DEPTH,
    GUIDE_DEPTH_BAND,
    GUIDE_DEPTH_CALLOUT,
    GUIDE_HEIGHT,
    GUIDE_LENGTH,
    LOCK_TAP_SPEC,
    LOCK_TAP_X,
    LOCK_TAP_Y,
    PLATEN_TAP_SPEC,
    PLATEN_TAP_X,
    PLATEN_TAP_Y,
    SCREW_CBORE_DEPTH,
    SCREW_CBORE_DEPTH_BAND,
    SCREW_CBORE_DIA,
    SCREW_CBORE_DIA_BAND,
    SCREW_CBORE_FRONT_WALL_TEXT,
    SCREW_HOLE_DIA,
    SCREW_HOLE_X,
    SCREW_HOLE_Z,
    UNIT,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pd_platen_bottom_guide"]
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

# The 1:1 front view centred at sheet x 0.190 (the 10.62 rail spans
# ~0.055..0.325); the top view stands over it (third angle), the right view
# beside it, the isometric at 1:2 in the field over the right view.
FRONT_CENTER = (0.190, 0.120)
TOP_CENTER = (FRONT_CENTER[0], 0.160)
RIGHT_CENTER = (0.390, 0.120)
ISO_CENTER = (0.355, 0.215)
ISO_SCALE = (1, 2)
ISO_NOTE_XY = (0.3245, 0.180)
_LEFT_X = FRONT_CENTER[0] - GUIDE_LENGTH / 2000.0
FRONT_KEEP = {
    "Length": (FRONT_CENTER[0], 0.080),
    # The value and its two-line reason (~15 mm with the shelf) hang right of
    # the dimension line, its left end on the given x, the block centred on
    # the given y with the shelf 8.4 mm under it.  Between the extension
    # lines the lower one struck the last line (r5); below the rail the line
    # ran down beside every row to the shelf and touched the flush widest one
    # (R5 full build).  So the text stands above the rail's top extension
    # line (~0.128), the line carried up only to its shelf (~0.131), the
    # rows x ~0.337..0.380: right of the rail and left of the right view.
    "Height": (0.337, 0.139),
    # The lock taps' stations stack under the view, the row left of it.
    "LockTap1X": (_LEFT_X + LOCK_TAP_X[0] / 2000.0, 0.104),
    "LockTap2X": (_LEFT_X + LOCK_TAP_X[1] / 2000.0, 0.098),
    "LockTap3X": (_LEFT_X + LOCK_TAP_X[2] / 2000.0, 0.092),
    "LockTap4X": (_LEFT_X + LOCK_TAP_X[3] / 2000.0, 0.086),
    "LockTapY": (_LEFT_X - 0.012, FRONT_CENTER[1]),
}
# The depth's limits and clearance text are wider than the 10 mm right view:
# centred over it (r3, r4) both extension lines ran up into CLEAR MHA-PD-19,
# so the text stands left of the left extension line, the dimension line
# carried out, clear right of the top view and over the height's text (its
# shelf ~0.151, 5 mm over the height's top row, the block under the
# isometric's caption).
RIGHT_KEEP = {"Depth": (0.358, 0.161)}
# The height's .XXX band is half of the counterbore floor's band, which the
# rack screws' worst engagement pays (pd_feed_rack_spec.SCREW_FLOOR_BAND); the
# band names its mate by number (rule 4, r4), two lines that fit between the
# front and right views.
SCREW_NUMBER = _config.parts("sh-vn-fillister-screw-91794a055")["number"]
HEIGHT_CALLOUT = f"SETS ENGAGEMENT\nOF {SCREW_NUMBER}"
# Both front-view tap callouts sit between the views, clear under the top
# view (its underside ~0.155) so the counterbore leader into it runs past
# them; the platen-tap leader takes the middle hole, right of the lock taps,
# so the two leaders never cross (first farm render, r2).
LOCK_CALLOUT_XY = (0.090, 0.1435)
PLATEN_CALLOUT_XY = (0.215, 0.1435)
PLATEN_CALLOUT_HOLE = len(PLATEN_TAP_X) // 2
SCREW_CALLOUT_XY = (0.150, 0.200)
PLATEN_NUMBER = _config.parts("pd-platen")["number"]
RACK_NUMBER = _config.parts("pd-feed-rack")["number"]
LOCK_NUMBER = _config.parts("pd-guide-lock")["number"]
LOCK_CALLOUT_BELOW = f"FOR {LOCK_NUMBER} LOCKS"
PLATEN_CALLOUT_BELOW = f"TRANSFER FROM {PLATEN_NUMBER} AT ASSEMBLY"
SCREW_CALLOUT_BELOW = (
    f"TRANSFER FROM {RACK_NUMBER} AT ASSEMBLY\n{SCREW_CBORE_FRONT_WALL_TEXT}"
)
# The counterbore prints its own bands (owner ruling 2026-11-25, #3620: "b:
# Ø.110 +.004/−0 and depth .469 ±.005"; build_pd_platen_bottom_guide puts them
# on the Hole Wizard feature, _print_counterbore_bands their places). It names
# no function: a dimension with its own band needs none (rule 3), the floor's
# reason is already the height's (HEIGHT_CALLOUT: the floor is the height less
# this depth), and one reason on two dimensions is narration (rule 7). Its two
# word lines are the transfer and the stated wall (rule 7: at most two).
# The callout's three places print the bands' deviations too.
SCREW_CBORE_PLACES = {"hw-cbdia": 3, "hw-cbdepth": 3}
TAPPED_HOLE_NOTE = "Tapped Hole"
_TAP_DRILL = blind_cut_dia_mm(LOCK_TAP_SPEC)

# Feature-export declarations (export_features; cad/docs/pipeline/
# features-travelers.md): what this sheet prints, beside the constants of the
# code that prints it, in the part frame (pd_platen_bottom_guide_spec: length
# +X from the left end, height +Y from the underside, depth -Z from the
# platen-mating front face). Bands are the title block's rows at the places
# the sheet prints (DRAWING_PRECISION_BY_NAME), the depth its native one-sided
# LIMITs, the tap drills the DRILLED HOLES row at the callout's three places.
# The five platen-screw taps and the four rack-screw holes print no location:
# they are struck at MHA-PD-00 (made_at = "assembly"), so a traveler that
# makes the rail leaves them. The declarations print nothing.
_P = DRAWING_PRECISION_BY_NAME
_SELF = "draw_pd_platen_bottom_guide"
_FRAME = "__frame__"
_CALLOUT = ((_SELF, "build"),)
# The callout prints the tap drill at the sheet's three places (decimals=3).
_HOLE_PLACES = 3


def _plane(axis: str, value: float) -> dict[str, Any]:
    return {"frame": "model", "axis": axis, "value": value}


part_metadata(
    model_sources=("GUIDE_LENGTH", "GUIDE_HEIGHT", "GUIDE_DEPTH"),
    precision_sources=(
        "DRAWING_PRECISION",
        "DRAWING_PRECISION_BY_NAME",
        (_SELF, "SCREW_CBORE_PLACES"),
        (_SELF, "build"),
    ),
)
requirement(
    "left_end",
    kind="face",
    faces=(PlanarFace((-1.0, 0.0, 0.0), 0.0),),
    requirements=("plane",),
    fields={"plane": (_plane("x", 0.0), (_FRAME,))},
)
# The length 10.62 (FRONT_KEEP "Length"), from the left end.
requirement(
    "right_end",
    kind="face",
    faces=(PlanarFace((1.0, 0.0, 0.0), GUIDE_LENGTH),),
    requirements=("length",),
    fields={
        "plane": (_plane("x", GUIDE_LENGTH), ("GUIDE_LENGTH",)),
        "length": (
            limits(GUIDE_LENGTH, _P["Length"], unit=UNIT),
            ("GUIDE_LENGTH", "UNIT", (_SELF, "FRONT_KEEP")),
        ),
        "length_nominal": (GUIDE_LENGTH, ("GUIDE_LENGTH",)),
        "length_from": ("left_end", ((_SELF, "FRONT_KEEP"),)),
    },
    precision={"length": _P["Length"]},
)
requirement(
    "underside",
    kind="face",
    faces=(PlanarFace((0.0, -1.0, 0.0), 0.0),),
    requirements=("plane",),
    fields={"plane": (_plane("y", 0.0), (_FRAME,))},
)
# The height .624 from the underside (FRONT_KEEP "Height") with its callout.
requirement(
    "top_face",
    kind="face",
    faces=(PlanarFace((0.0, 1.0, 0.0), GUIDE_HEIGHT),),
    requirements=("height",),
    fields={
        "plane": (_plane("y", GUIDE_HEIGHT), ("GUIDE_HEIGHT",)),
        "height": (
            limits(GUIDE_HEIGHT, _P["Height"], unit=UNIT),
            ("GUIDE_HEIGHT", "UNIT", (_SELF, "FRONT_KEEP")),
        ),
        "height_nominal": (GUIDE_HEIGHT, ("GUIDE_HEIGHT",)),
        "height_from": ("underside", ((_SELF, "FRONT_KEEP"),)),
        "callout": (HEIGHT_CALLOUT, ((_SELF, "HEIGHT_CALLOUT"),)),
    },
    precision={"height": _P["Height"]},
)
requirement(
    "front_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), 0.0),),
    requirements=("plane",),
    fields={"plane": (_plane("z", 0.0), (_FRAME,))},
)
# The depth .40/.39 from the front face: native LIMITs (RIGHT_KEEP "Depth").
requirement(
    "rear_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), GUIDE_DEPTH),),
    requirements=("depth",),
    fields={
        "plane": (_plane("z", -GUIDE_DEPTH), ("GUIDE_DEPTH",)),
        "depth": (
            limits(GUIDE_DEPTH, _P["Depth"], GUIDE_DEPTH_BAND, unit=UNIT),
            ("GUIDE_DEPTH", "GUIDE_DEPTH_BAND", (_SELF, "RIGHT_KEEP")),
        ),
        "depth_nominal": (GUIDE_DEPTH, ("GUIDE_DEPTH",)),
        "depth_from": ("front_face", ((_SELF, "RIGHT_KEEP"),)),
        "callout": (GUIDE_DEPTH_CALLOUT, ("GUIDE_DEPTH_CALLOUT",)),
    },
    precision={"depth": _P["Depth"]},
)
_THREAD = (f"{LOCK_TAP_SPEC.size} UNC-2B", ("LOCK_TAP_SPEC", *_CALLOUT))
_TAP_DRILL_BAND = (
    drilled_limits(_TAP_DRILL, _HOLE_PLACES, unit=UNIT),
    ((_SELF, "_TAP_DRILL"), "UNIT", *_CALLOUT),
)
# The four lock taps, THRU from the rear face: one native callout (4X Ø.089
# THRU ALL, 4-40 UNC THRU ALL, FOR MHA-PD-12 LOCKS), each station from the
# left end and the shared row from the underside (FRONT_KEEP LockTap*).
for _index, _x in enumerate(LOCK_TAP_X, 1):
    requirement(
        f"lock_tap_{_index}",
        kind="threaded_hole",
        faces=(CylinderFace(_TAP_DRILL, contains_x_mm=_x),),
        requirements=("thread", "dia", "thru", "station", "height"),
        fields={
            "at": (
                [_x, LOCK_TAP_Y, -GUIDE_DEPTH],
                ("LOCK_TAP_X", "LOCK_TAP_Y", "GUIDE_DEPTH"),
            ),
            "axis": ((0.0, 0.0, 1.0), ("LOCK_TAP_SPEC", _FRAME)),
            "thread": _THREAD,
            "dia": _TAP_DRILL_BAND,
            "nominal_dia": (_TAP_DRILL, ((_SELF, "_TAP_DRILL"),)),
            "thru": (True, ("LOCK_TAP_SPEC", *_CALLOUT)),
            "station": (
                limits(_x, _P[f"LockTap{_index}X"], unit=UNIT),
                ("LOCK_TAP_X", "UNIT", (_SELF, "FRONT_KEEP")),
            ),
            "station_nominal": (_x, ("LOCK_TAP_X",)),
            "station_from": ("left_end", ((_SELF, "FRONT_KEEP"),)),
            "height": (
                limits(LOCK_TAP_Y, _P["LockTapY"], (BAND, -BAND), unit=UNIT),
                ("LOCK_TAP_Y", "BAND", (_SELF, "FRONT_KEEP")),
            ),
            "height_nominal": (LOCK_TAP_Y, ("LOCK_TAP_Y",)),
            "height_from": ("underside", ((_SELF, "FRONT_KEEP"),)),
            "mates": (LOCK_CALLOUT_BELOW, ((_SELF, "LOCK_CALLOUT_BELOW"),)),
        },
        precision={
            "dia": _HOLE_PLACES,
            "station": _P[f"LockTap{_index}X"],
            "height": _P["LockTapY"],
        },
    )
# The five platen-screw taps, THRU from the front face, transferred from
# MHA-PD-02 at assembly: their callout prints size only, no location.
for _index, _x in enumerate(PLATEN_TAP_X, 1):
    requirement(
        f"platen_tap_{_index}",
        kind="threaded_hole",
        faces=(CylinderFace(blind_cut_dia_mm(PLATEN_TAP_SPEC), contains_x_mm=_x),),
        requirements=("thread", "dia", "thru"),
        fields={
            "at": ([_x, PLATEN_TAP_Y, 0.0], ("PLATEN_TAP_X", "PLATEN_TAP_Y")),
            "axis": ((0.0, 0.0, -1.0), ("PLATEN_TAP_SPEC", _FRAME)),
            "thread": (
                f"{PLATEN_TAP_SPEC.size} UNC-2B",
                ("PLATEN_TAP_SPEC", *_CALLOUT),
            ),
            "dia": (
                drilled_limits(
                    blind_cut_dia_mm(PLATEN_TAP_SPEC), _HOLE_PLACES, unit=UNIT
                ),
                ("PLATEN_TAP_SPEC", "UNIT", *_CALLOUT),
            ),
            "nominal_dia": (blind_cut_dia_mm(PLATEN_TAP_SPEC), ("PLATEN_TAP_SPEC",)),
            "thru": (True, ("PLATEN_TAP_SPEC", *_CALLOUT)),
            "made_at": ("assembly", ((_SELF, "PLATEN_CALLOUT_BELOW"),)),
            "transfer": (PLATEN_CALLOUT_BELOW, ((_SELF, "PLATEN_CALLOUT_BELOW"),)),
        },
        precision={"dia": _HOLE_PLACES},
    )
# The four rack-screw holes down from the top face, #51 THRU with a Ø.110
# counterbore, struck from MHA-PD-26 at assembly; size, depth and wall only.
for _index, _x in enumerate(SCREW_HOLE_X, 1):
    requirement(
        f"rack_screw_hole_{_index}",
        kind="hole",
        faces=(
            CylinderFace(SCREW_HOLE_DIA, contains_x_mm=_x),
            CylinderFace(SCREW_CBORE_DIA, contains_x_mm=_x),
        ),
        requirements=("dia", "thru", "cbore_dia", "cbore_depth"),
        fields={
            "at": (
                [_x, GUIDE_HEIGHT, -SCREW_HOLE_Z],
                ("SCREW_HOLE_X", "GUIDE_HEIGHT", "SCREW_HOLE_Z"),
            ),
            "axis": ((0.0, -1.0, 0.0), ("SCREW_HOLE_SPEC", _FRAME)),
            "dia": (
                drilled_limits(SCREW_HOLE_DIA, _HOLE_PLACES, unit=UNIT),
                ("SCREW_HOLE_DIA", "UNIT", *_CALLOUT),
            ),
            "nominal_dia": (SCREW_HOLE_DIA, ("SCREW_HOLE_DIA",)),
            "thru": (True, ("SCREW_HOLE_SPEC", *_CALLOUT)),
            "cbore_dia": (
                limits(SCREW_CBORE_DIA, SCREW_CBORE_PLACES["hw-cbdia"], SCREW_CBORE_DIA_BAND, unit=UNIT),
                ("SCREW_CBORE_DIA", "SCREW_CBORE_DIA_BAND", "UNIT", (_SELF, "SCREW_CBORE_PLACES"),
                 (_SELF, "_print_counterbore_bands"), *_CALLOUT),
            ),
            "cbore_depth": (
                limits(SCREW_CBORE_DEPTH, SCREW_CBORE_PLACES["hw-cbdepth"], SCREW_CBORE_DEPTH_BAND, unit=UNIT),
                ("SCREW_CBORE_DEPTH", "SCREW_CBORE_DEPTH_BAND", "UNIT", (_SELF, "SCREW_CBORE_PLACES"),
                 (_SELF, "_print_counterbore_bands"), *_CALLOUT),
            ),
            "made_at": ("assembly", ((_SELF, "SCREW_CALLOUT_BELOW"),)),
            "transfer": (SCREW_CALLOUT_BELOW, ((_SELF, "SCREW_CALLOUT_BELOW"),)),
        },
        precision={
            "dia": _HOLE_PLACES,
            "cbore_dia": SCREW_CBORE_PLACES["hw-cbdia"],
            "cbore_depth": SCREW_CBORE_PLACES["hw-cbdepth"],
        },
    )


def _rim(view: Any, station: float, diameter: float, *, label: str) -> Any:
    """The one visible circular rim of ``diameter`` at model-X ``station``
    (draw_pd_platen_guide._hole_rim_entities)."""
    matches = []
    for raw_edge in visible_view_entities(view, 1, label=label):
        edge = _early_bound(raw_edge, "IEdge")
        raw_curve = edge.GetCurve()
        if raw_curve is None:
            continue
        curve = _early_bound(raw_curve, "ICurve")
        if not curve.IsCircle():
            continue
        parameters = tuple(float(value) * 1000.0 for value in curve.CircleParams)
        if abs(parameters[0] - station) <= 0.02 and abs(parameters[6] - diameter / 2.0) <= 0.02:
            matches.append(edge)
    if len(matches) != 1:
        raise RuntimeError(f"{label}: {len(matches)} rims at {station:g} mm; expected 1")
    return matches[0]


@_telemetry.traced("drawing.hole_callout_below")
def _set_callout_below(display: Any, text: str, *, label: str) -> None:
    """Write ``text`` under a native hole callout and read it back
    (draw_sm_gooseneck_end_plug._set_tap_callout_below)."""
    definitions = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    below = definitions[8].replace("\r", "").rstrip()
    updated = f"{below}\n{text}" if below else text
    display.SetText(4, updated)
    if str(display.GetText(8) or "").replace("\r", "") != updated or any(
        str(display.GetText(part) or "") != definitions[part] for part in (5, 6, 7)
    ):
        raise RuntimeError(f"{label} callout rows did not persist")


_TOL_BILATERAL = 2  # swTolType_e.swTolBILAT


@_telemetry.traced("drawing.bottom_guide.counterbore_bands")
def _print_counterbore_bands(display: Any) -> None:
    """Print the rack-screw counterbore's own bands (owner ruling 2026-11-25,
    #3620: Ø.110 +.004/-.000, depth .469 ±.005) on its native callout. The
    bands live on the part's RackScrewHoles Hole Wizard feature
    (build_pd_platen_bottom_guide._band_rack_screw_counterbores) and
    ``<hw-cbdia>`` / ``<hw-cbdepth>`` display them; this sets only their
    tolerance places (SCREW_CBORE_PLACES), as
    draw_ch_fulcrum_keeper._print_counterbore_band does, and reads each
    displayed band back so a band that did not reach the callout fails here."""
    from win32com.client.dynamic import Dispatch as dynamic_dispatch  # noqa: PLC0415

    wanted = {
        "hw-cbdia": (SCREW_CBORE_DIA, SCREW_CBORE_DIA_BAND),
        "hw-cbdepth": (SCREW_CBORE_DEPTH, SCREW_CBORE_DEPTH_BAND),
    }
    found: dict[str, list[tuple[Any, Any]]] = {name: [] for name in wanted}
    for raw in display.GetHoleCalloutVariables() or ():
        variable = dynamic_dispatch(raw._oleobj_)
        name = str(variable.VariableName)
        if name in found:
            found[name].append((raw, variable))
    for name, (nominal, band) in wanted.items():
        if len(found[name]) != 1:
            raise RuntimeError(
                f"rack-screw callout carries {len(found[name])} {name} variables, not 1"
            )
        raw, variable = found[name][0]
        length = _early_bound(raw, "ICalloutLengthVariable")
        actual = float(length.Length) * 1000.0
        if abs(actual - nominal) > 1e-5:
            raise RuntimeError(
                f"rack-screw callout {name} reads {actual:g}, expected {nominal:g} mm"
            )
        places = SCREW_CBORE_PLACES[name]
        length.TolerancePrecision = places
        upper, lower = band
        if (
            int(variable.ToleranceType) != _TOL_BILATERAL
            or abs(float(variable.ToleranceMin) * 1000.0 - lower) > 1e-5
            or abs(float(variable.ToleranceMax) * 1000.0 - upper) > 1e-5
            or int(length.TolerancePrecision) != places
        ):
            raise RuntimeError(
                f"rack-screw callout {name} does not display the part's band: wanted "
                f"swTolBILAT, deviations {(lower, upper)} mm at {places} places; read "
                f"{int(variable.ToleranceType)}, {float(variable.ToleranceMin)!r}, "
                f"{float(variable.ToleranceMax)!r}, {int(length.TolerancePrecision)}"
            )
        _telemetry.info(f"rack-screw callout {name} {nominal:g} mm, band {band} mm")


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open bottom-guide source", adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Isometric View Note",
            "Quantity",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        layout=SPEC.layout,
        decimals=3,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Platen Bottom Guide Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "platen bottom guide; manufacturing drawing; #4-40 UNC; #0 rack screws",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (front, top, right, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = [
        *curate_view_dimensions(
            adapter,
            front,
            keep=FRONT_KEEP,
            view_label="front",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            right,
            keep=RIGHT_KEEP,
            view_label="right",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    # The depth's one-sided band and the height's .XXX band name what they
    # protect (rule 4).
    set_dimension_callouts(
        adapter, annotations, {"Depth": GUIDE_DEPTH_CALLOUT, "Height": HEIGHT_CALLOUT}
    )
    for view, label in ((front, "front"), (top, "top")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to the {label} view")

    for view, station, diameter, xy, below, label in (
        (front, LOCK_TAP_X[0], _TAP_DRILL, LOCK_CALLOUT_XY, LOCK_CALLOUT_BELOW,
         f"lock taps ({LOCK_TAP_SPEC.size})"),
        (front, PLATEN_TAP_X[PLATEN_CALLOUT_HOLE], _TAP_DRILL, PLATEN_CALLOUT_XY,
         PLATEN_CALLOUT_BELOW,
         f"platen-screw taps ({PLATEN_TAP_SPEC.size})"),
        (top, SCREW_HOLE_X[0], SCREW_CBORE_DIA, SCREW_CALLOUT_XY,
         SCREW_CALLOUT_BELOW,
         "rack-screw counterbores"),
    ):
        callout = add_native_hole_callout(
            adapter,
            view,
            edge=_rim(view, station, diameter, label=label),
            callout_xy=xy,
            label=label,
        )
        if "tap" in label:
            omit_title_block_thread_class(callout, label=label)
        else:
            _print_counterbore_bands(callout)
        _set_callout_below(callout, below, label=label)
    rebuild_drawing(adapter, label="bottom-guide hole callouts")
    removed = remove_notes_matching(adapter, TAPPED_HOLE_NOTE)
    _telemetry.info(f"removed {removed} automatic tapped-hole label(s)")
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Platen Bottom Guide Manufacturing Drawing",
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
