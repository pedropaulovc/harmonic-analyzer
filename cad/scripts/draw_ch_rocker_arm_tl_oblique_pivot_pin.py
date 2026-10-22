r"""Create the oblique trammel pivot-pin drawing (MHA-CH-06-TL-23).

Layout evidence: the d349b9930 native PDF and layout-audit report from worker
swmaker00000a, drawing leaf 2026-10-21T05:32:39Z. All 20 gating records are
visible paper defects, not collector phantoms: five strike the flange/upper-boss
stack, three strike the bearing-end lead, eight involve the carrier-end lead,
cross-hole size or 6.0 station, three involve the lower-boss/fit/radius group,
and one is the former prose inspection note's right-border overrun.

Keep the 3:1 profile and 2:1 pictorial. The upper-boss block occupies the
90.5..164 mm witness bay; the flange and fitted lower-boss blocks stack in
the 213.5..279.5 mm bay. In particular the lower-boss line is above its
182.05 mm witness origins, so neither witness descends through the native
R0.2 MAX shoulder at Y134.2219 mm or its material-arc leader. The radius
itself, its attachment and the measured (1.15) reference remain unchanged.

The top-end lead has its row outside X90.5; the bearing-end lead
uses clear paper below the pictorial. The obsolete numeric inspection note
is replaced by model-owned, face-attached total axial runout frames. Raising
the bearing-fit block separates it from the flange-diameter block. Of the six
advisory records, the cross-hole diameter crossing its own axis-location witness
is an ordinary dimension intersection, not a text collision; the other five
motivate the same lane repairs. No finding is masked or reclassified here. These are
measured-boundary placement choices, not after-fix native acceptance: the
owner must regenerate the audit/PDF and inspect complete text and leaders.

The review-resume-88c6d PDF (sha256 dd56976a...) showed every upper-left
route to the Ø5 cross hole crossing both the 6.0 station line (Y189.2 mm,
X84.1..114.8) and the top-lead line (Y187.4, X86.9..98.4). The drill
callout therefore sits on the clear paper under the carrier journal, right
of the hole and of the Ø10 dimension line (X94.5), between the Ø10 fit
block (top Y96.3) and the R0.2 MAX row (bottom Y133.8), so its leader
rises from the block's near (left) end into the hole crossing only the
journal outline.
"""

from __future__ import annotations

import argparse
from math import hypot
import sys
from typing import Any, Callable

from solidworks_mcp.adapters.solidworks.drawing import place_view

from _check import check
from _com import _early_bound
from _drawing_attachment import _assert_attached_to, _assert_leader_lands
from _drawing_centerline import add_view_centerline
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_gdt import (
    add_datum_feature,
    add_feature_control_frame,
    assert_datum_landing,
    assert_frame_datums_defined,
)
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
import ch_rocker_arm_tl_oblique_pivot_pin_spec as part_spec
from _feature_requirements import part_metadata, requirement
from _printed_limits import drilled_limits, limits
from _gtol_cylinder import CylinderFace
from _gtol_face_resolve import resolve_faces
from _gtol_frame import gtol_frame_signature
from _gtol_planar import PlanarFace
from ch_rocker_arm_tl_oblique_pivot_pin_spec import (
    BEARING_LENGTH,
    CALLOUTS_ABOVE,
    CARRIER_STATION,
    COLLAR_DIA,
    COLLAR_HEIGHT,
    COLLAR_STATION,
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    OVERALL_LENGTH,
)

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_oblique_pivot_pin"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# The integral flange and transverse cross hole are visible in the Right
# projection. Native model dimensions remain the sole printed size authority.
SHEET_SCALE = (3.0, 1.0)
VIEW_SCALE = (3, 1)
_S = VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0
PROFILE_CENTER = (0.185, 0.164)
ISO_CENTER = (0.355, 0.205)
ISO_SCALE = (2, 1)
ISO_NOTE_XY = (0.325, 0.252)
# b9e4d6b45bbb passed attachment/landing checks but its two native bent
# leaders crossed. Keep the upper route left of its face, and put the
# lower frame's mid-height on its literal landing: its 6.35 mm shoulder
# then ends outside the right face and the final run approaches normally.
# The 28.8 mm width budget is derived from rounded b9e4/native-font evidence,
# not a measured current frame. Keep the full native ink/attachment audit.
STOP_FACE_FRAME_XY = {
    "flange_upper_stop": (0.1625, 0.097),
    "flange_lower_stop": (0.2166, 0.115),
}
# Native BearingDia ink occupies X246.5 mm, not just its lower text block.
# z=6 mm gives X261.5 between that line/arrow and the X278/279.5 chamfer
# witnesses, allowing for the complete datum box, on the same k5 face.
BEARING_DATUM_STATION_MM = 6.0
# Four paper millimetres outside the journal: retain the old Y145 mm lane,
# but derive its normal from the live projection instead of an outboard X.
BEARING_DATUM_STANDOFF_M = 0.004
_ABOVE = PROFILE_CENTER[1] + part_spec.FLANGE_DIA / 2.0 * _S
_BELOW = PROFILE_CENTER[1] - part_spec.FLANGE_DIA / 2.0 * _S


def _x(z_mm: float) -> float:
    """Sheet X of a model station (the view centres on the model box)."""
    return PROFILE_CENTER[0] - (z_mm - OVERALL_LENGTH / 2.0) * _S


def _span_mid(station_mm: float) -> float:
    return (_x(OVERALL_LENGTH) + _x(station_mm)) / 2.0


ROW_Y = (_ABOVE + 0.012, _ABOVE + 0.024, _ABOVE + 0.036)
CHAMFER_Y = _ABOVE - 0.025
PROFILE_KEEP = {
    "CarrierLength": (_span_mid(CARRIER_STATION), ROW_Y[0]),
    "BearingLength": (_x(BEARING_LENGTH / 2.0), ROW_Y[1]),
    "UpperBossHeight": (0.125, 0.211),
    "PinLength": (_span_mid(0.0), ROW_Y[2]),
    "TopChamfer": (0.050, CHAMFER_Y),
    "BottomChamfer": (0.310, 0.130),
    "BearingDia": (_x(BEARING_LENGTH / 2.0), 0.104),
    "CarrierDia": (_x(OVERALL_LENGTH) + 0.004, 0.082),
    "CollarDia": (_x(CARRIER_STATION - 5.0), 0.127),
    "FlangeDia": (_x(part_spec.FLANGE_BOTTOM_STATION + part_spec.FLANGE_THICK / 2.0), 0.079),
    "FlangeThick": (0.249, 0.224),
    # Native text centres the complete value-plus-five-row block on this Y;
    # keep its full glyphs below the 3.0 flange label and between witnesses.
    "LowerBossHeight": (_x(BEARING_LENGTH / 2.0), 0.2025),
    "CarrierFilletR": (_x(CARRIER_STATION) - 0.012, 0.137),
    "SeatFilletR": (_x(COLLAR_STATION) + 0.012, 0.137),
    "CrossHoleDia": (0.1468, 0.111),
    "CrossHoleFromEnd": (_x(OVERALL_LENGTH - part_spec.CROSS_HOLE_FROM_END / 2.0), 0.192),
}
CENTERLINE_PICK = (_x(CARRIER_STATION - 5.0), PROFILE_CENTER[1] + 0.003)


_AXIS = ([0.0, 0.0, 1.0], ("__frame__",))
_FROM_TOP = ("top_face", (("draw_ch_rocker_arm_tl_oblique_pivot_pin", "build"),))
_FROM_BOTTOM = ("bottom_face", (("draw_ch_rocker_arm_tl_oblique_pivot_pin", "build"),))


part_metadata(
    precision_sources=("DRAWING_PRECISION_BY_NAME", "GEOMETRIC_CONTROLS"),
)

requirement(
    "top_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), part_spec.OVERALL_LENGTH),),
    requirements=(),
    fields={
        "normal": ([0.0, 0.0, 1.0], ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "z", "value": part_spec.OVERALL_LENGTH},
            ("OVERALL_LENGTH",),
        ),
    },
)

requirement(
    "collar_top",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), part_spec.CARRIER_STATION),),
    requirements=("station",),
    fields={
        "normal": ([0.0, 0.0, 1.0], ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "z", "value": part_spec.CARRIER_STATION},
            ("CARRIER_STATION",),
        ),
        "station": (
            limits(part_spec.CARRIER_LENGTH, part_spec.LENGTH_PLACES),
            ("CARRIER_LENGTH",),
        ),
        "station_nominal": (part_spec.CARRIER_LENGTH, ("CARRIER_LENGTH",)),
        "height_from": _FROM_TOP,
    },
    precision={"station": part_spec.LENGTH_PLACES},
)

requirement(
    "collar_seat",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), -part_spec.COLLAR_STATION),),
    requirements=("station",),
    fields={
        "normal": ([0.0, 0.0, -1.0], ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "z", "value": part_spec.COLLAR_STATION},
            ("COLLAR_STATION",),
        ),
        "station": (
            limits(part_spec.BEARING_LENGTH, part_spec.LENGTH_PLACES),
            ("BEARING_LENGTH",),
        ),
        "station_nominal": (part_spec.BEARING_LENGTH, ("BEARING_LENGTH",)),
        "height_from": _FROM_BOTTOM,
    },
    precision={"station": part_spec.LENGTH_PLACES},
)

requirement(
    "bottom_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
    requirements=(),
    fields={
        "normal": ([0.0, 0.0, -1.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("__frame__",)),
    },
)

requirement(
    "collar",
    kind="boss",
    faces=(
        CylinderFace(
            part_spec.COLLAR_DIA,
            contains_z_mm=(part_spec.FLANGE_TOP_STATION + part_spec.CARRIER_STATION) / 2.0,
        ),
    ),
    requirements=("dia", "length"),
    fields={
        "axis": _AXIS,
        "dia": (
            limits(part_spec.COLLAR_DIA, part_spec.COLLAR_PLACES),
            ("COLLAR_DIA",),
        ),
        "dia_nominal": (part_spec.COLLAR_DIA, ("COLLAR_DIA",)),
        "length": (
            limits(part_spec.UPPER_BOSS_HEIGHT, part_spec.UPPER_BOSS_PLACES),
            ("UPPER_BOSS_HEIGHT", "UPPER_BOSS_PLACES"),
        ),
        "length_nominal": (part_spec.UPPER_BOSS_HEIGHT, ("UPPER_BOSS_HEIGHT",)),
    },
    precision={"dia": part_spec.COLLAR_PLACES, "length": part_spec.UPPER_BOSS_PLACES},
)

# Rule 4: the k5 press seat in both 6200-2RS inner races.
requirement(
    "bearing_section",
    kind="boss",
    faces=(
        CylinderFace(
            part_spec.BEARING_DIA, contains_z_mm=part_spec.BEARING_LENGTH / 2.0
        ),
    ),
    requirements=("dia", "note"),
    fields={
        "axis": _AXIS,
        "dia": (
            limits(
                part_spec.BEARING_DIA,
                part_spec.FIT_PLACES,
                part_spec.BEARING_PRINT_BAND,
            ),
            ("BEARING_DIA", "BEARING_PRINT_BAND"),
        ),
        "dia_nominal": (part_spec.BEARING_DIA, ("BEARING_DIA",)),
        "note": (
            part_spec.BEARING_NOTE,
            ("BEARING_NOTE", ("_mcmaster_5972k41", "BORE_BAND")),
        ),
        "datum": (part_spec.PART_DATUMS[0].letter, ("PART_DATUMS",)),
    },
    precision={"dia": part_spec.FIT_PLACES},
)

# Rule 4: the h6 locating section in the carrier's Ø10 H7 pin holes.
requirement(
    "carrier_section",
    kind="boss",
    faces=(
        CylinderFace(
            part_spec.FIT_DIA,
            contains_z_mm=part_spec.CARRIER_STATION + part_spec.CARRIER_LENGTH / 2.0,
        ),
    ),
    requirements=("dia", "note"),
    fields={
        "axis": _AXIS,
        "dia": (
            limits(part_spec.FIT_DIA, part_spec.FIT_PLACES, part_spec.CARRIER_BAND),
            ("FIT_DIA", "CARRIER_BAND"),
        ),
        "dia_nominal": (part_spec.FIT_DIA, ("FIT_DIA",)),
        "note": (part_spec.CARRIER_NOTE, ("CARRIER_NOTE", "PIN_HOLE_BAND")),
    },
    precision={"dia": part_spec.FIT_PLACES},
)

requirement(
    "captive_flange",
    kind="boss",
    faces=(CylinderFace(part_spec.FLANGE_DIA),),
    requirements=("dia", "length"),
    fields={
        "axis": _AXIS,
        "dia": (
            limits(part_spec.FLANGE_DIA, 2, part_spec.FLANGE_DIA_BAND),
            ("FLANGE_DIA", "FLANGE_DIA_BAND"),
        ),
        "dia_nominal": (part_spec.FLANGE_DIA, ("FLANGE_DIA",)),
        "length": (
            limits(part_spec.FLANGE_THICK, part_spec.FLANGE_THICK_PLACES),
            ("FLANGE_THICK", "FLANGE_THICK_PLACES"),
        ),
        "length_nominal": (part_spec.FLANGE_THICK, ("FLANGE_THICK",)),
    },
    precision={"dia": 2, "length": part_spec.FLANGE_THICK_PLACES},
)

for _stop_control in part_spec.GEOMETRIC_CONTROLS:
    _normal = _stop_control.face.normal
    _station = _stop_control.face.offset_mm / _normal[2]
    requirement(
        _stop_control.key,
        kind="face",
        faces=(_stop_control.face,),
        requirements=("note",),
        fields={
            "normal": (list(_normal), ("__frame__",)),
            "plane": (
                {"frame": "model", "axis": "z", "value": _station},
                ("FLANGE_BOTTOM_STATION", "FLANGE_TOP_STATION"),
            ),
            # Manifest's text projection of the native frame, not a separate
            # prose inspection authority or an alternative circle-only limit.
            "note": (
                f"TOTAL AXIAL RUNOUT {_stop_control.tolerance} "
                f"TO DATUM {_stop_control.datums[0]}",
                ("GEOMETRIC_CONTROLS", "PART_DATUMS"),
            ),
        },
    )

requirement(
    "lower_inner_race_boss",
    kind="boss",
    faces=(
        CylinderFace(
            part_spec.COLLAR_DIA,
            contains_z_mm=part_spec.COLLAR_STATION + part_spec.LOWER_BOSS_HEIGHT / 2.0,
        ),
    ),
    requirements=("dia", "note"),
    fields={
        "axis": _AXIS,
        # The upper boss's one CollarDia prints "2X": it holds this boss too.
        "dia": (
            limits(part_spec.COLLAR_DIA, part_spec.COLLAR_PLACES),
            ("COLLAR_DIA", "CALLOUTS_ABOVE"),
        ),
        "dia_nominal": (part_spec.COLLAR_DIA, ("COLLAR_DIA",)),
        "note": (
            " ".join(part_spec.DIMENSION_CALLOUTS["LowerBossHeight"].splitlines()),
            ("LOWER_BOSS_HEIGHT", "DIMENSION_CALLOUTS"),
        ),
    },
    precision={"dia": part_spec.COLLAR_PLACES},
)

requirement(
    "clevis_cross_hole",
    kind="hole",
    faces=(CylinderFace(part_spec.CROSS_HOLE_DIA),),
    requirements=("dia", "station", "thru"),
    fields={
        "axis": ([1.0, 0.0, 0.0], ("__frame__",)),
        "at": ([0.0, 0.0, part_spec.CROSS_HOLE_STATION], ("CROSS_HOLE_STATION",)),
        # An ordinary drilled hole: the title block's DRILLED HOLES row.
        "dia": (drilled_limits(part_spec.CROSS_HOLE_DIA, 2), ("CROSS_HOLE_DIA",)),
        "dia_nominal": (part_spec.CROSS_HOLE_DIA, ("CROSS_HOLE_DIA",)),
        "station": (limits(part_spec.CROSS_HOLE_FROM_END, part_spec.LENGTH_PLACES), ("CROSS_HOLE_FROM_END",)),
        "station_nominal": (part_spec.CROSS_HOLE_FROM_END, ("CROSS_HOLE_FROM_END",)),
        "height_from": _FROM_TOP,
        "thru": (True, ("DIMENSION_CALLOUTS",)),
    },
    precision={"dia": 2, "station": part_spec.LENGTH_PLACES},
)


def _stop_faces_in_view(
    adapter: Any, profile: Any, model: Any, source_faces: dict[str, Any],
) -> dict[str, Any]:
    """Reacquire the Pin revolution's exact faces in drawing-view context.

    SDK IEntity::Select4 requires active-document entities. A face resolved
    from ReferencedDocument is not its drawing-context counterpart: the
    695c4b02e native failure rejected that identity before any landing was set.
    Reuse draw_mg_output_fixture._rod_bore_face's feature correspondence path;
    direct IView::GetCorrespondingEntity(source_face) was null on its rotated
    view. IView::GetCorresponding(IFeature) and IFeature::GetFaces supply the
    selectable faces; source IModelDocExtension::GetCorrespondingEntity2 and
    ISldWorks::IsSame prove which exact source face each one represents.
    """
    pin = _early_bound(model, "IPartDoc").FeatureByName("Pin")
    if pin is None:
        raise RuntimeError("pivot stop controls: source has no Pin revolution")
    view_pin = _early_bound(profile, "IView").GetCorresponding(pin)
    if view_pin is None:
        raise RuntimeError("pivot stop controls: Pin has no profile-view correspondence")
    extension = _early_bound(model.Extension, "IModelDocExtension")
    matches: dict[str, list[Any]] = {key: [] for key in source_faces}
    for face in _early_bound(view_pin, "IFeature").GetFaces() or ():
        source = extension.GetCorrespondingEntity2(face)
        if source is None:
            continue
        for key, expected in source_faces.items():
            if int(adapter.swApp.IsSame(source, expected)) == 1:
                matches[key].append(face)
    for key, candidates in matches.items():
        if len(candidates) != 1:
            raise RuntimeError(
                f"{key}: expected one Pin profile-view face corresponding to "
                f"the exact source face, found {len(candidates)}"
            )
    return {key: candidates[0] for key, candidates in matches.items()}


def _bearing_datum_symbol_xy(
    axis_xy: tuple[float, float], landing_xy: tuple[float, float],
) -> tuple[float, float]:
    """Request a straight datum on the literal landing's outward normal.

    SDK IAnnotation::SetPosition2 moves the leader/symbol junction, subject
    to datum constraints. The 7f008ec06 request put it 49.5 mm axially away
    from the requested landing; the closest rendered datum ink missed that
    landing by 28.2841 mm. That readback does not identify the true triangle
    tip or prove a native axial re-solve. Reuse the normal-aligned straight
    datum in draw_ch_rocker_arm._hub_face_datum: the perpendicular foot of
    the symbol request stays on the literal landing, while the existing
    native identity and rendered-landing guards remain authoritative.
    """
    dx, dy = landing_xy[0] - axis_xy[0], landing_xy[1] - axis_xy[1]
    scale = BEARING_DATUM_STANDOFF_M / hypot(dx, dy)
    return (landing_xy[0] + scale * dx, landing_xy[1] + scale * dy)


def _add_stop_face_controls(adapter: Any, profile: Any) -> Callable[[], None]:
    """Attach A to its real cylinder and each native frame to its stop face.

    Reuse the existing native datum/FCF helpers with view-context faces.
    SDK IModelDoc2::InsertGtol derives its attachment from the prior selection;
    set that landing before insertion and verify current-format frame XML.
    No coordinate hit-test, silhouette substitute or post-insertion setter.
    """
    datum = part_spec.PART_DATUMS[0]
    controls = part_spec.GEOMETRIC_CONTROLS
    model = _early_bound(_early_bound(profile, "IView").ReferencedDocument, "IModelDoc2")
    source_faces = resolve_faces(
        model, {datum.key: datum.face, **{row.key: row.face for row in controls}}
    )
    faces = _stop_faces_in_view(adapter, profile, model, source_faces)
    # The lower flank of the reachable k5 journal, well away from its chamfer
    # and shoulder. Stop tips lie on the Ø35 subset of the full annular faces.
    # *Right looks along model X: these are a cylinder tangent and edge-on
    # annular faces. Projection supplies only the landing, never ownership or
    # a visibility/pick proof; the mapped topology and native readbacks do.
    points = (
        (0.0, -part_spec.BEARING_DIA / 2000.0, BEARING_DATUM_STATION_MM / 1000.0),
        (0.0, 0.0, BEARING_DATUM_STATION_MM / 1000.0),
        *(
            (0.0, -part_spec.STOP_FACE_MEASUREMENT_DIAMETER / 2000.0,
             row.face.offset_mm / row.face.normal[2] / 1000.0)
            for row in controls
        ),
    )
    projected = model_points_in_view(adapter, profile, points, label="pivot stop controls")
    datum_landing, journal_axis, *stop_landings = projected
    tag = add_datum_feature(
        adapter, profile, entity=faces[datum.key], entity_type="FACE",
        symbol_xy=_bearing_datum_symbol_xy(journal_axis, datum_landing), datum=datum.letter,
        leader_attach_xy=datum_landing, label="k5 bearing-journal datum axis",
    )
    frames = {}
    for index in range(len(controls)):
        control = controls[index]
        landing = stop_landings[index]
        frames[control.key] = add_feature_control_frame(
            adapter, profile, entity=faces[control.key], entity_type="FACE",
            leader_attach_xy=landing, frame_xy=STOP_FACE_FRAME_XY[control.key],
            characteristic=control.characteristic, tolerance=control.tolerance,
            datums=control.datums, diameter=control.tolerance_zone == "diametral",
            label=control.key,
        )

    def settled() -> None:
        assert_frame_datums_defined((profile,), label="pivot stop controls")
        extension = _early_bound(model.Extension, "IModelDocExtension")
        for key, face in faces.items():
            source = extension.GetCorrespondingEntity2(face)
            if source is None or int(adapter.swApp.IsSame(source, source_faces[key])) != 1:
                raise RuntimeError(f"{key}: settled face lost its exact source correspondence")
        _assert_attached_to(
            adapter, _early_bound(tag.GetAnnotation(), "IAnnotation"), faces[datum.key],
            entity_type="FACE", what="datum feature", label=datum.key, expected_leaders=0,
        )
        assert_datum_landing(
            adapter, tag, expected_xy=datum_landing, label="bearing-journal datum A"
        )
        for index in range(len(controls)):
            control = controls[index]
            landing = stop_landings[index]
            gtol = _early_bound(frames[control.key], "IGtol")
            if int(gtol.GetFrameCount()) != 1:
                raise RuntimeError(f"{control.key}: expected one axial-runout frame")
            frame = _early_bound(gtol.GetFrame(1), "IGtolFrame")
            if gtol_frame_signature(frame.GetSymbolXml()) != gtol_frame_signature(control.frame_xml):
                raise RuntimeError(f"{control.key}: settled frame changed its control")
            annotation = _early_bound(gtol.GetAnnotation(), "IAnnotation")
            _assert_attached_to(
                adapter, annotation, faces[control.key], entity_type="FACE",
                what="feature-control frame", label=control.key,
            )
            _assert_leader_lands(
                annotation, landing, what="feature-control frame", label=control.key
            )

    return settled


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pivot-pin source", await adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Isometric View Note",
    )
    read_required_properties(
        adapter.currentModel, ("Revision", "Title", *required), required=required
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker Oblique Trammel Pivot Pin Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker oblique trammel pivot pin; 1144 stress-proof; MHA-CH-06-TL-23",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    profile = place_view(
        adapter, str(SOURCE), "*Right", *PROFILE_CENTER, scale=VIEW_SCALE
    )
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (profile, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = curate_view_dimensions(
        adapter,
        profile,
        keep=PROFILE_KEEP,
        view_label="turned profile",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Places (and so each fit band) are authored on the part; the sheet only
    # proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    # drawing-guidelines.md rule 4: each fit band names its mate and its fit.
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS, location="below")
    set_dimension_callouts(adapter, annotations, CALLOUTS_ABOVE, location="above")
    add_view_centerline(
        adapter, profile, face_xy=CENTERLINE_PICK, label="pivot pin axis"
    )
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    stop_controls_settled = _add_stop_face_controls(adapter, profile)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Oblique Trammel Pivot Pin Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        settled_checks=(stop_controls_settled,),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
