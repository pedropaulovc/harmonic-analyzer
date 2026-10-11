"""Offline contracts for the transgear disc hub (MHA-PD-017) and its drawing."""

from __future__ import annotations

import ast
import asyncio
import importlib.util
import itertools
import math
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import _appearance
import _bore_axis
import _check
import _part_properties
import _part_save
import _rebuild
import _sketch
import _sketch_chains
import _sketch_circle
import _sketch_rectangle
import _config
import _drawing_common
import _gtol_face
import _printed_tolerance
import build_pd_transgear_disc_hub as part
import draw_pd_transgear_disc_hub as drawing
import pd_paper_drive_assembly_steps as steps
import transgear_cluster_fit as cluster_fit
import pd_transgear_disc_hub_geometry as joint
import pd_transgear_disc_hub_spec as spec
from _assembly_contract import assembly_contract
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _layout_geometry import Box, estimate_text_box

WALL_FLOOR = 2.0
DRILL_PLUS = _config.title_block("drilled_hole")["plus_mm"]


def _row(places: int) -> float:
    """The ± the title block prints for a dimension shown at ``places``."""
    return float(str(_config.title_block(f"linear_{places}pl")["display"]).lstrip("±"))


def _places(name: str) -> int:
    return spec.DRAWING_PRECISION_BY_NAME[name]


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pd-transgear-disc-hub.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pd-transgear-disc-hub.pdf")
    assert (
        DRAWINGS_BY_NAME["pd_transgear_disc_hub"].script
        == Path(drawing.__file__).resolve()
    )
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    views = (drawing.END_KEEP, drawing.SIDE_KEEP)
    assert set().union(*map(set, views)) == marked
    for a, b in itertools.combinations(views, 2):
        assert not set(a) & set(b)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    # Each callout rides a dimension the sheet keeps.
    assert set(drawing.DIMENSION_CALLOUTS_BELOW) <= marked
    assert set(drawing.DIMENSION_CALLOUTS_ABOVE) <= marked


def test_the_sheet_prints_the_faced_overall_and_the_flange_never_the_hub_body() -> None:
    """R9-5 / R9-68: the overall (spigot end to hub front) is faced to fit,
    so it prints as a reference at the model's 13.70; the flange 2.400 and
    the spigot 3.650 are functional .XXX lengths; the hub body is their
    remainder and is not printed.  No oil-hole station prints either: the
    hole is centred on the hub body when it is match-drilled (R9-60)."""
    diameters = {
        "FlangeDia",
        "HubDia",
        "SpigotDia",
        "BoreDia",
        "BoltCircleDia",
        "ScrewHoleDia",
    }
    lengths = (
        set(spec.DRAWING_PRECISION_BY_NAME) - diameters - {"OilHoleDia", "FlatToAxis"}
    )
    assert lengths == {"HubLength", "FlangeThick", "SpigotLength"}
    assert spec.REFERENCE_DIMENSIONS == {"HubLength"} < set(drawing.SIDE_KEEP)
    assert spec.HUB_LENGTH == cluster_fit.HUB_LENGTH_MODEL == pytest.approx(13.70)
    assert spec.FLANGE_THICK == pytest.approx(2.4) and _places("FlangeThick") == 3
    assert spec.SPIGOT_LENGTH == pytest.approx(3.65) and _places("SpigotLength") == 3
    assert spec.BORE_DIA == spec.SLEEVE.BOSS_DIA and _places("BoreDia") == 3
    assert spec.FLAT_TO_AXIS == spec.SLEEVE.FLAT_TO_AXIS
    assert _places("FlatToAxis") == 3
    assert spec.HUB_DIA == pytest.approx(13.2) and _places("HubDia") == 3
    assert spec.SPIGOT_DIA == pytest.approx(13.1) and _places("SpigotDia") == 3
    assert spec.FLANGE_DIA == pytest.approx(25.1) and _places("FlangeDia") == 3
    assert joint.BOLT_CIRCLE_DIA == pytest.approx(19.0)
    assert spec.HUB_BODY_LENGTH == pytest.approx(7.65)


def test_the_hub_front_is_faced_into_the_nose_window_at_its_own_step() -> None:
    """R9-68: no print stack holds the hub front face 0.00-0.10 behind the
    sleeve's nose, so it is faced at fit-up, right after the cluster is put
    together and before the disc's taps are spotted through the flange.  The
    sheet prints the fitted band and the step; the blank leaves a finishing
    cut over the longest fit."""
    sleeve = cluster_fit.SLEEVE
    # The hub's room runs from the 12T's step, the spigot's seat, to the nose.
    room = (
        (sleeve.OVERALL_LENGTH - sleeve.STATION_TOL)
        - (sleeve.FACE_WIDTH + sleeve.FACE_WIDTH_BAND),
        (sleeve.OVERALL_LENGTH + sleeve.STATION_TOL)
        - (sleeve.FACE_WIDTH - sleeve.FACE_WIDTH_BAND),
    )
    window = cluster_fit.HUB_NOSE_WINDOW
    assert window == (0.0, 0.10)
    assert cluster_fit.HUB_NOSE_WINDOW_TEXT == "0.00-0.10"
    assert (spec.HUB_LENGTH_FITTED_MIN, spec.HUB_LENGTH_FITTED_MAX) == pytest.approx(
        (room[0] - window[1], room[1] - window[0])
    )
    assert (spec.HUB_LENGTH_FITTED_MIN, spec.HUB_LENGTH_FITTED_MAX) == pytest.approx(
        (13.47, 13.93)
    )
    assert cluster_fit.STEP_Z - cluster_fit.HUB_FRONT_Z == pytest.approx(
        spec.HUB_LENGTH
    )
    assert spec.BLANK_LENGTH_MIN == pytest.approx(14.05)
    # The model: hub front face at the window's centre behind the nose.
    assert cluster_fit.HUB_FRONT_Z - cluster_fit.NOSE_Z == pytest.approx(
        sum(window) / 2.0
    )
    assert spec.BLANK_LENGTH_MIN >= spec.HUB_LENGTH_FITTED_MAX + spec.FACING_ALLOWANCE
    assert f"SUPPLY {spec.BLANK_LENGTH_MIN:.2f} MIN" in spec.DRAWING_NOTES
    sequence = list(steps.SEQUENCE)
    at = sequence.index(drawing.FIT_STEP_KEY)
    assert drawing.FIT_STEP_KEY == "hub-faced-to-nose"
    assert sequence[at - 1 : at + 2] == [
        "disc-cluster-assembled",
        "hub-faced-to-nose",
        "disc-taps-transferred",
    ]
    callout = drawing.DIMENSION_CALLOUTS_BELOW["HubLength"]
    assert callout.startswith(
        f"SET AT ASSEMBLY {spec.HUB_LENGTH_FITTED_MIN:.2f}-"
        f"{spec.HUB_LENGTH_FITTED_MAX:.2f}\nFACED TO FIT"
    )
    assert callout.endswith(f"PER {steps.step_ref(drawing.FIT_STEP_KEY)}")


def test_only_the_bore_and_the_spigot_carry_model_bands() -> None:
    """Every other size is governed by its printed places and the holes by
    the title block's DRILLED HOLES row."""
    assert model_toleranced_dimensions(part) == {
        ("BoreProfile", "BoreDia"): "*BORE_DEVIATIONS",
        ("BoreProfile", "FlatToAxis"): "*FLAT_TO_AXIS_DEVIATIONS",
        ("HubProfile", "SpigotDia"): "*SPIGOT_DIA_DEVIATIONS",
    }


def _printed_limits(build, spec_module, feature: str, name: str, nominal: float):
    """(least, greatest) size the sheet prints: the model band the build
    applies, else the title block's row for the dimension's places."""
    expr = model_toleranced_dimensions(build).get((feature, name))
    if expr is None:
        row = _row(spec_module.DRAWING_PRECISION_BY_NAME[name])
        return nominal - row, nominal + row
    lower, upper = getattr(build, expr.lstrip("*"))
    return nominal + lower, nominal + upper


def test_the_d_bore_slides_on_the_sleeve_boss_and_flat_at_every_printed_limit() -> None:
    """The D drives the disc's torque; the two parts are made apart, each to
    its own sheet, so the round part and the flat each keep a clearance
    (never a bind) at every printed limit, and the callouts state the
    clearances the limits give."""
    import build_pd_transgear_feed_pinion as sleeve_part
    import pd_transgear_feed_pinion_spec as sleeve

    assert spec.BORE_DIA == sleeve.BOSS_DIA
    assert spec.BORE_BAND == (0.015, 0.0)  # H7 in the mating boss's 6-10 mm group
    assert spec.FLAT_TO_AXIS == sleeve.FLAT_TO_AXIS
    assert part.BORE_DIA == drawing.BORE_DIA == spec.BORE_DIA
    assert part.BORE_R == pytest.approx(sleeve.BOSS_DIA / 2.0)
    assert part.FLAT_TO_AXIS == spec.FLAT_TO_AXIS
    assert part.BORE_DEVIATIONS == spec.BORE_DEVIATIONS

    bore = _printed_limits(part, spec, "BoreProfile", "BoreDia", spec.BORE_DIA)
    boss = _printed_limits(
        sleeve_part, sleeve, "SleeveProfile", "BossDia", sleeve.BOSS_DIA
    )
    round_fit = (bore[0] - boss[1], bore[1] - boss[0])
    hub_flat = _printed_limits(
        part, spec, "BoreProfile", "FlatToAxis", spec.FLAT_TO_AXIS
    )
    shaft_flat = _printed_limits(
        sleeve_part, sleeve, "FlatProfile", "FlatToAxis", sleeve.FLAT_TO_AXIS
    )
    flat_fit = (hub_flat[0] - shaft_flat[1], hub_flat[1] - shaft_flat[0])
    assert round_fit[0] >= -1e-9 and flat_fit[0] > 0.0
    assert round_fit == pytest.approx(spec.BOSS_CLEARANCE_LIMITS, abs=5e-4)
    assert spec.BOSS_CLEARANCE == spec.BOSS_CLEARANCE_LIMITS[1]
    assert flat_fit == pytest.approx(spec.FLAT_CLEARANCE, abs=5e-4)
    bore_callout = " ".join(drawing.DIMENSION_CALLOUTS_BELOW["BoreDia"].split())
    assert f"(DIA CLR {round_fit[0]:.3f}-{round_fit[1]:.3f} ON" in bore_callout
    flat_callout = " ".join(drawing.DIMENSION_CALLOUTS_BELOW["FlatToAxis"].split())
    assert f"(CLR {flat_fit[0]:.3f}-{flat_fit[1]:.3f} ON" in flat_callout


def test_boss_round_engagement_and_available_flat_face_follow_the_live_sleeve() -> None:
    """The retained axial stack keeps the finite cutter end behind the
    locating round and the sleeve flat's end behind the hub flat. The
    available D-flat face is geometry, not a certified torque capacity."""
    sleeve = spec.SLEEVE
    engagement = (
        sleeve.OVERALL_LENGTH
        - sleeve.STATION_TOL
        - cluster_fit.HUB_NOSE_WINDOW[1]
        - max(
            sleeve.FACE_WIDTH + sleeve.FACE_WIDTH_BAND,
            sleeve.CUTTER_RUNOUT_END_WORST,
        )
    )
    assert spec.ROUND_ENGAGEMENT_MIN == pytest.approx(engagement)
    assert engagement > 0.0
    assert spec.FLAT_END_CLEARANCE_WORST > 0.0
    width = 2.0 * math.sqrt(
        (sleeve.BOSS_DIA / 2.0) ** 2 - sleeve.FLAT_TO_AXIS**2
    )
    width_min = 2.0 * math.sqrt(
        ((sleeve.BOSS_DIA + sleeve.BOSS_DIA_BAND[1]) / 2.0) ** 2
        - (sleeve.FLAT_TO_AXIS + sleeve.FLAT_TO_AXIS_BAND[0]) ** 2
    )
    length_min = (
        sleeve.OVERALL_LENGTH
        - sleeve.STATION_TOL
        - cluster_fit.HUB_NOSE_WINDOW[1]
        - (sleeve.FACE_WIDTH + sleeve.FACE_WIDTH_BAND + spec.SPIGOT_LENGTH_MAX)
    )
    assert spec.FLAT_DRIVE_WIDTH == pytest.approx(width)
    assert spec.FLAT_DRIVE_WIDTH_MIN == pytest.approx(width_min)
    assert spec.FLAT_DRIVE_LENGTH_MIN == pytest.approx(length_min)
    assert spec.FLAT_DRIVE_FACE_AREA_MIN == pytest.approx(width_min * length_min)
    # The existing named flat-wall floor is unchanged, with the new G7 bore.
    flat_wall = (
        sleeve.FLAT_TO_AXIS
        + sleeve.FLAT_TO_AXIS_BAND[1]
        - (sleeve.BORE_DIA + sleeve.BORE_DIA_BAND[0]) / 2.0
    )
    assert sleeve.FLAT_WALL_WORST == pytest.approx(flat_wall)
    assert flat_wall >= sleeve.WALL_FLOOR


def test_the_spigot_seats_on_the_step_square_and_clear_of_the_disc() -> None:
    """R9-68: the spigot pilots the disc's bore and seats on the 12T's step.
    Its end and the flange's rear face are square to the bore (datum A) on
    the sheet; the disc's tilt reads both, the step's and the hub's rock on
    the boss, and its rear face stays in air ahead of the step."""
    import pd_rack_pinion_spec as disc
    import pd_transgear_feed_pinion_spec as sleeve

    # The spigot pilots the disc: the two printed bands never bind.
    spigot = (
        spec.SPIGOT_DIA + spec.SPIGOT_DIA_BAND[1],
        spec.SPIGOT_DIA + spec.SPIGOT_DIA_BAND[0],
    )
    disc_bore = (disc.BORE_DIA + disc.BORE_BAND[1], disc.BORE_DIA + disc.BORE_BAND[0])
    fit = (disc_bore[0] - spigot[1], disc_bore[1] - spigot[0])
    assert fit == pytest.approx(disc.SPIGOT_DIAMETRAL_CLEARANCE)
    assert fit[0] >= 0.0
    callout = " ".join(drawing.DIMENSION_CALLOUTS_BELOW["SpigotDia"].split())
    assert f"(DIA CLR {fit[0]:.3f}-{fit[1]:.3f} IN" in callout
    # The common seat annulus at the actual partial-depth cutter end, with
    # every printed radial/tip/step/full-depth corner bounded by its owner.
    assert spec.SEAT_CONTACT_R == pytest.approx(
        (sleeve.OUTSIDE_DIA + sleeve.OUTSIDE_DIA_BAND[1]) / 2.0
    )
    assert spec.SEAT_INNER_R == pytest.approx(
        (spec.BORE_DIA + spec.BORE_BAND[0]) / 2.0 + spec.EDGE_BREAK_MAX
    )
    lower, upper = spec.SEAT_CONTACT_AREA_BOUNDS
    assert 0.0 < lower <= upper < spec.SEAT_ANNULUS_AREA
    assert spec.SEAT_CONTACT_AREA == lower
    assert len(spec._SEAT_AREA_BOUNDS) == 4 * len(sleeve.manufactured_profiles())
    assert (lower, upper) == (
        min(bounds[0] for bounds in spec._SEAT_AREA_BOUNDS),
        min(bounds[1] for bounds in spec._SEAT_AREA_BOUNDS),
    )
    # Geometric control: the frames print the spec's values against A.
    assert spec.BORE_DATUM == sleeve.BORE_DATUM == "A"
    assert spec.GEOMETRIC_TOLERANCES_MM == {
        "flange rear face perpendicularity to bore": "0.03",
        "spigot end perpendicularity to bore": "0.005",
    }
    tilt = (
        sleeve.STEP_FACE_PERPENDICULARITY / sleeve.STEP_FACE_PERPENDICULARITY_ZONE_DIA
        + spec.SPIGOT_END_PERPENDICULARITY / spec.SPIGOT_END_PERPENDICULARITY_ZONE_DIA
        + spec.FLANGE_FACE_PERPENDICULARITY / spec.FLANGE_DIA
        + spec.BOSS_CLEARANCE / spec.ROUND_ENGAGEMENT_MIN
    )
    assert spec.DISC_TILT_MAX == pytest.approx(tilt)
    gap = (
        spec.SPIGOT_LENGTH_MIN
        - disc.FACE_WIDTH_MAX
        - float(disc.GEOMETRIC_TOLERANCES_MM["disc rear face parallelism to front"])
        - tilt * disc.BORE_DIA_MAX / 2.0
    )
    assert spec.DISC_STEP_GAP_WORST == pytest.approx(gap)
    assert spec.DISC_STEP_GAP_WORST > 0.0
    # The disc's bore chamfer clears the spigot's corner radius.
    assert spec.CORNER_RADIUS_MAX < disc.BORE_FRONT_CHAMFER_LIMITS[0]


def _side_view_model_point(sheet_xy: tuple[float, float]) -> tuple[float, float]:
    """Model (x, z) under a sheet point on the edge view: ``*Top`` shows model
    +X right and -Z up, the view turns SIDE_VIEW_ANGLE counter-clockwise, and
    it centres on the part's z span."""
    angle = drawing.SIDE_VIEW_ANGLE
    x_dir = (math.cos(angle), math.sin(angle))
    z_dir = (math.sin(angle), -math.cos(angle))
    z_mid = (spec.HUB_FRONT_Z + spec.SPIGOT_LENGTH) / 2.0
    dx = (sheet_xy[0] - drawing.SIDE_CENTER[0]) / drawing._S
    dy = (sheet_xy[1] - drawing.SIDE_CENTER[1]) / drawing._S
    return dx * x_dir[0] + dy * x_dir[1], z_mid + dx * z_dir[0] + dy * z_dir[1]


# The frames as the farm drew them (run 20261002T180658288Z): the 0.005
# frame's box 29.29 wide on the sheet, the 0.03 frame's 26.75, and a
# leader's arrowhead 3.13 long.
_FRAME_WIDTH = {
    drawing.SPIGOT_END_FRAME.label: 0.02929,
    drawing.FLANGE_FACE_FRAME.label: 0.02675,
}
_ARROWHEAD = 0.00313


def _nominal_landing(frame) -> tuple[float, float]:
    """Where ``frame``'s leader lands on the laid-out edge view: on its face's
    line, at its model x (model +X up)."""
    return (
        drawing._side_x(frame.face_z_mm),
        drawing.AXIS_Y + frame.landing_x_mm * drawing._S,
    )


def _frame_box(frame) -> Box:
    x, top = drawing.frame_position(_nominal_landing(frame))
    return Box(x, top - drawing.FRAME_HEIGHT, x + _FRAME_WIDTH[frame.label], top)


def test_each_frame_lands_square_on_its_face_clear_of_corners_and_text() -> None:
    """MR #1166: the spigot end's leader ran down at a slant onto the end's
    line 3 sheet mm from its corner with the spigot's O.D., and read as
    controlling the cylinder.  Each leader now runs level from its frame's
    middle onto its face's line (square to the face, the way a leader to a
    surface reads), lands on the face's annulus at the view's mid-depth, an
    arrowhead and a millimetre or more from every corner the face shares with
    a turned diameter, off the screw holes' edges (farm run
    20261002T153039266Z missed a sheet pick over the 0-degree hole's edge on
    the rear face) and on the side of the axis no extension line rises from.
    Each frame and leader stays clear of every dimension's text; the spigot
    end's frame inside the spigot's extension lines and left of its
    diameter's dimension line, the flange's between the spigot's and the
    flange's extension lines."""
    s = drawing._S
    flange, spigot = drawing.FLANGE_FACE_FRAME, drawing.SPIGOT_END_FRAME
    spigot_r, flange_r = spec.SPIGOT_DIA / 2.0, spec.FLANGE_DIA / 2.0
    # Each face's annulus, and the radii where its line meets a turned
    # diameter's on the sheet: the spigot's end from its round bore (hidden
    # inside the spigot) out to the spigot's O.D.; the flange's rear face
    # from the spigot's root out to the flange's O.D.
    annulus = {
        flange.label: (spigot_r, flange_r),
        spigot.label: (spec.BORE_DIA / 2.0, spigot_r),
    }
    corners = {flange.label: (spigot_r, flange_r), spigot.label: (spigot_r,)}
    boxes = {
        name: _printed_box(name, anchor) for name, anchor in drawing.SIDE_KEEP.items()
    }
    for frame in (flange, spigot):
        landing = _nominal_landing(frame)
        assert _side_view_model_point(landing) == pytest.approx(
            (frame.landing_x_mm, frame.face_z_mm)
        )
        r = abs(frame.landing_x_mm)
        assert annulus[frame.label][0] < r < annulus[frame.label][1]
        for corner in corners[frame.label]:
            assert abs(corner - r) * s >= _ARROWHEAD + 0.001, (frame.label, corner)
        x, top = drawing.frame_position(landing)
        assert top - drawing.FRAME_HEIGHT / 2.0 == pytest.approx(landing[1], abs=1e-12)
        assert x - landing[0] >= _ARROWHEAD + 0.003
        frame_box = _frame_box(frame)
        leader = Box(landing[0], landing[1], x, landing[1])
        for name, text in boxes.items():
            assert frame_box.gap(text) >= 0.002, (frame.label, name)
            assert leader.gap(text) >= 0.002, (frame.label, name)
    for centre_x, _centre_y in joint.screw_centres():
        gap = abs(flange.landing_x_mm - centre_x) - joint.SCREW_HOLE_DIA / 2.0
        assert gap * s >= 0.001
    # The spigot's length and the overall end at the spigot end's +X corner
    # and print above the part, so their extension lines rise off the spigot
    # end's line; the spigot length's other one rises from the spigot's +X
    # corner at the flange, along the rear face's +X stretch.
    for name in ("SpigotLength", "HubLength"):
        text_x, _text_z = _side_view_model_point(drawing.SIDE_KEEP[name])
        assert text_x > flange_r, name
    assert flange.landing_x_mm < 0.0 < spigot.landing_x_mm
    axis_y = drawing.AXIS_Y
    spigot_box, flange_box = _frame_box(spigot), _frame_box(flange)
    assert spigot_box.xmin > drawing.SPIGOT_END_X
    assert spigot_box.ymin > axis_y
    assert spigot_box.ymax <= axis_y + spigot_r * s - drawing.FRAME_AIR + 1e-12
    assert spigot_box.xmax <= drawing.SIDE_KEEP["SpigotDia"][0] - 0.002
    assert axis_y - flange_r * s + 0.002 <= flange_box.ymin
    assert flange_box.ymax <= axis_y - spigot_r * s - 0.002
    assert flange_box.xmin > drawing.SPIGOT_END_X


def _circle(radius: float, z: float, *, x: float = 0.0, axis_z: float = 1.0):
    return _drawing_common.ViewEdge(
        edge=object(),
        line=None,
        circle=(x, 0.0, z, 0.0, 0.0, axis_z, radius),
        vertices=None,
    )


def test_face_rim_resolves_exactly_one_circle_on_the_hub_axis() -> None:
    """The rim is the one circle at its station and radius on the hub's axis,
    either normal sign; a neighbour at another station, radius or centre
    never stands in for it, and none or two fail listing every circle."""
    frame = drawing.FLANGE_FACE_FRAME
    radius = frame.rim_radius_mm
    rim = _circle(radius, 0.0, axis_z=-1.0)
    neighbours = (
        _circle(radius, -spec.FLANGE_THICK),  # the flange's front rim
        _circle(spec.SPIGOT_DIA / 2.0, 0.0),  # the spigot's root
        _circle(spec.SCREW_HOLE_DIA / 2.0, 0.0, x=spec.BOLT_CIRCLE_DIA / 2.0),
        _circle(radius + 0.001, 0.0),
    )
    edges = _drawing_common.ViewEdges(label="edge", edges=(*neighbours, rim))
    assert drawing.face_rim(edges, frame) is rim
    lone = _drawing_common.ViewEdges(label="edge", edges=neighbours)
    with pytest.raises(RuntimeError, match=r"matched 0 of 4 circles: .*r 12\.5510 at"):
        drawing.face_rim(lone, frame)
    split = _drawing_common.ViewEdges(label="edge", edges=(rim, _circle(radius, 0.0)))
    with pytest.raises(RuntimeError, match="matched 2 of 2"):
        drawing.face_rim(split, frame)
    with pytest.raises(RuntimeError, match="matched 0 of 0 circles: none"):
        drawing.face_rim(_drawing_common.ViewEdges(label="edge", edges=()), frame)


def _surface_face(
    identity: int, parameters: tuple[float, ...], *, flipped: bool = False
):
    """A model face as ``_gtol_face_read.face_geometry`` reads it (metres)."""
    surface = SimpleNamespace(
        Identity=identity, PlaneParams=parameters, CylinderParams=parameters
    )
    return SimpleNamespace(
        GetSurface=lambda: surface,
        FaceInSurfaceSense=lambda: flipped,
        GetBox=lambda: (),
    )


def _plane(z_mm: float, *, facing: float = 1.0):
    """The plane square to the hub axis at ``z_mm``, its outward normal +Z
    (or -Z)."""
    return _surface_face(
        _gtol_face.SURFACE_PLANE,
        (0.0, 0.0, 1.0, 0.0, 0.0, z_mm / 1000.0),
        flipped=facing < 0.0,
    )


def _cylinder(radius_mm: float):
    return _surface_face(
        _gtol_face.SURFACE_CYLINDER, (0.0, 0.0, 0.0, 0.0, 0.0, 1.0, radius_mm / 1000.0)
    )


def _rim_between(*faces):
    edge = SimpleNamespace(GetTwoAdjacentFaces2=lambda: faces)
    return _drawing_common.ViewEdge(edge=edge, line=None, circle=None, vertices=None)


@pytest.mark.parametrize("plane_first", [False, True])
def test_each_frame_attaches_to_the_plane_its_rim_bounds_never_the_cylinder(
    plane_first: bool,
) -> None:
    """MR #1166: the spigot end's frame, left on the rim the end shares with
    the spigot's O.D., read as controlling the cylinder.  Each frame takes,
    of its rim's two faces, the one plane square to the hub axis at its
    station facing +Z -- the spigot's end at z 3.65, the flange's rear face
    at z 0 -- whichever face the rim reports first.  A plane at another
    station or facing the other way never stands in for it, and two such
    planes, or fewer than two faces, fail naming each face."""
    spigot, flange = drawing.SPIGOT_END_FRAME, drawing.FLANGE_FACE_FRAME
    assert spec.SPIGOT_LENGTH == pytest.approx(3.65)
    for frame, z, radius in (
        (spigot, spec.SPIGOT_LENGTH, spec.SPIGOT_DIA / 2.0),
        (flange, 0.0, spec.FLANGE_DIA / 2.0),
    ):
        cylinder, plane = _cylinder(radius), _plane(z)
        pair = (plane, cylinder) if plane_first else (cylinder, plane)
        assert drawing.controlled_face(_rim_between(*pair), frame) is plane
    cylinder = _cylinder(spec.SPIGOT_DIA / 2.0)
    for wrong in (
        _plane(0.0),  # the flange's rear face
        _plane(spec.SPIGOT_LENGTH + 0.1),
        _plane(spec.SPIGOT_LENGTH, facing=-1.0),
    ):
        with pytest.raises(
            RuntimeError, match=r"matched 0 of 2 faces: surface 4002 .*; surface 4001 "
        ):
            drawing.controlled_face(_rim_between(cylinder, wrong), spigot)
    end = _plane(spec.SPIGOT_LENGTH)
    with pytest.raises(RuntimeError, match="matched 2 of 2 faces"):
        drawing.controlled_face(_rim_between(end, _plane(spec.SPIGOT_LENGTH)), spigot)
    with pytest.raises(RuntimeError, match="matched 1 of 1 faces"):
        drawing.controlled_face(_rim_between(None, end), spigot)
    with pytest.raises(RuntimeError, match="matched 0 of 0 faces: none"):
        drawing.controlled_face(_rim_between(), spigot)


@pytest.mark.parametrize("turn", [1.0, -1.0])
def test_face_landing_puts_the_leader_at_its_model_x_on_the_projected_line(
    turn: float,
) -> None:
    """The landing sits at the frame's model x between the rim's projected
    -X and +X ends, whichever way the view turns them."""
    for frame in (drawing.FLANGE_FACE_FRAME, drawing.SPIGOT_END_FRAME):
        r = frame.rim_radius_mm * drawing._S
        minus_end = (0.2346, drawing.AXIS_Y - turn * r)
        plus_end = (0.2346, drawing.AXIS_Y + turn * r)
        landing = drawing.face_landing(frame, minus_end, plus_end)
        assert landing == pytest.approx(
            (0.2346, drawing.AXIS_Y + turn * frame.landing_x_mm * drawing._S)
        )


def _sheet_text() -> str:
    return "\n".join(
        (
            spec.DRAWING_NOTES,
            *drawing.DIMENSION_CALLOUTS_BELOW.values(),
            *drawing.DIMENSION_CALLOUTS_ABOVE.values(),
        )
    )


def test_every_mate_the_sheet_cites_is_named_with_its_own_number() -> None:
    """Policy rule 2: every part number the sheet cites is a mate's, printed
    after that mate's name, and is the number the mate's own sheet carries."""
    name_by_number: dict[str, str] = {}
    for stem, name in (
        ("pd-transgear-feed-pinion", spec.SLEEVE_NAME),
        ("vn-transgear-disc-screw", spec.SCREW_NAME),
        ("pd-rack-pinion", spec.DISC_NAME),
    ):
        name_by_number[_config.parts(stem)["number"]] = name
    printed = " ".join(_sheet_text().split())
    cited = re.findall(r"MHA-[A-Z]{2}-\d{3}(?:-T\d{3})?", printed)
    assert set(cited) == set(name_by_number) | {
        assembly_contract("pd-paper-drive").number
    }
    for number, name in name_by_number.items():
        assert printed.count(f"{name} {number}") == printed.count(number), number


def test_walls_hold_at_the_worst_case_the_sheet_prints() -> None:
    """Policy rule 12, recomputed from the title block's rows."""
    hub_wall = (
        (spec.HUB_DIA - _row(_places("HubDia"))) - (spec.BORE_DIA + spec.BORE_BAND[0])
    ) / 2.0
    oil_r = (spec.OIL_HOLE_DIA + DRILL_PLUS) / 2.0
    # The oil hole is centred on the shortest hub body the fitted overall,
    # the printed spigot and the printed flange leave, give or take the
    # centring at fit-up: the same ligament to the hub front face and to the
    # flange face.
    body_min = (
        spec.HUB_LENGTH_FITTED_MIN
        - (spec.SPIGOT_LENGTH + _row(_places("SpigotLength")))
        - (spec.FLANGE_THICK + _row(_places("FlangeThick")))
    )
    oil_ligament = body_min / 2.0 - spec.OIL_HOLE_CENTRING_TOL - oil_r
    spigot_wall = (
        spec.SPIGOT_DIA + spec.SPIGOT_DIA_BAND[1] - (spec.BORE_DIA + spec.BORE_BAND[0])
    ) / 2.0
    screw_r = (spec.SCREW_HOLE_DIA + DRILL_PLUS) / 2.0
    bc_r_min = joint.BOLT_CIRCLE_DIA / 2.0 - joint.BOLT_CIRCLE_POSITION_TOL
    hole_to_bore = bc_r_min - screw_r - (spec.BORE_DIA + spec.BORE_BAND[0]) / 2.0
    hole_to_rim = (
        (spec.FLANGE_DIA - _row(_places("FlangeDia"))) / 2.0
        - (joint.BOLT_CIRCLE_DIA / 2.0 + joint.BOLT_CIRCLE_POSITION_TOL)
        - screw_r
    )
    flat_wall = (spec.HUB_DIA - _row(_places("HubDia"))) / 2.0 - (
        spec.FLAT_TO_AXIS + spec.FLAT_TO_AXIS_BAND[0]
    )

    assert oil_ligament == pytest.approx(2.68, abs=0.005)
    assert hole_to_rim == pytest.approx(2.02, abs=0.005)
    assert not any("RIM" in line for line in spec.DRAWING_NOTES.splitlines())
    for wall in (
        hub_wall,
        oil_ligament,
        hole_to_bore,
        hole_to_rim,
        flat_wall,
        spigot_wall,
    ):
        assert wall >= WALL_FLOOR - 1e-9
    assert spec.SPIGOT_WALL_WORST == pytest.approx(spigot_wall, abs=1e-9)
    assert spec.HUB_WALL_WORST == pytest.approx(hub_wall, abs=1e-9)
    assert spec.OIL_HOLE_LIGAMENT_WORST == pytest.approx(oil_ligament, abs=1e-9)
    assert spec.HOLE_TO_RIM_WORST == pytest.approx(hole_to_rim, abs=1e-9)
    assert spec.FLAT_WALL_WORST == pytest.approx(flat_wall, abs=1e-9)


def test_screw_heads_keep_a_millimetre_of_air_to_the_hub_body() -> None:
    head = spec.SCREW_HEAD_DIA + spec.SCREW_HEAD_DIA_ALLOWANCE
    bc_r_min = joint.BOLT_CIRCLE_DIA / 2.0 - joint.BOLT_CIRCLE_POSITION_TOL
    clearance = bc_r_min - head / 2.0 - (spec.HUB_DIA + _row(_places("HubDia"))) / 2.0
    assert clearance >= 1.0
    assert spec.HEAD_TO_HUB_WORST == pytest.approx(clearance, abs=1e-9)


def test_retained_outer_envelope_keeps_wall_driver_air_and_screw_margins() -> None:
    """The smaller sleeve-matched bore does not resize the R9-68 envelope:
    the hub body and spigot retain their diameters, while the screw joint's
    circle and flange retain the original printed worst-case margins."""
    import pd_rack_pinion_spec as disc

    assert spec.HUB_DIA == pytest.approx(13.2)
    assert spec.SPIGOT_DIA == pytest.approx(13.1)
    assert spec.FLANGE_DIA == pytest.approx(25.1)
    assert joint.BOLT_CIRCLE_DIA == pytest.approx(19.0)
    round_wall, flat_wall = spec.body_walls_worst(spec.HUB_DIA)
    assert min(round_wall, flat_wall, spec.SPIGOT_WALL_WORST) >= spec.WALL_FLOOR
    bc = joint.BOLT_CIRCLE_DIA
    assert spec.head_air_worst(bc, spec.HUB_DIA) >= spec.HEAD_AIR_MIN
    assert disc.TAP_TO_BORE_WALL_WORST >= disc.WALL_FLOOR
    assert disc.TAP_TO_BORE_WALL_WORST - 0.1 / 2.0 < disc.WALL_FLOOR
    assert spec.head_air_worst(16.4, 12.4) < spec.HEAD_AIR_MIN
    assert spec.hole_to_rim_worst(spec.FLANGE_DIA, bc) >= spec.WALL_FLOOR
    assert spec.hole_to_rim_worst(spec.FLANGE_DIA - 0.1, bc) < spec.WALL_FLOOR
    assert spec.hole_to_rim_worst(21.0, 16.4) < spec.WALL_FLOOR


def _spec_fresh():
    fresh_spec = importlib.util.spec_from_file_location("_hub_perturbed", spec.__file__)
    fresh = importlib.util.module_from_spec(fresh_spec)
    fresh_spec.loader.exec_module(fresh)
    return fresh


def test_the_native_bore_follows_the_feed_boss_instead_of_an_old_literal(
    monkeypatch,
) -> None:
    old_boss = spec.SLEEVE.BOSS_DIA
    monkeypatch.setattr(spec.SLEEVE, "BOSS_DIA", old_boss - 0.1)
    fresh = _spec_fresh()
    assert fresh.BORE_DIA == pytest.approx(old_boss - 0.1)
    assert fresh.BORE_BAND == spec.BORE_BAND
    assert fresh.FLAT_TO_AXIS == spec.SLEEVE.FLAT_TO_AXIS
    assert fresh.HUB_DIA == spec.HUB_DIA
    assert fresh.SPIGOT_DIA == spec.SPIGOT_DIA
    assert fresh.FLANGE_DIA == spec.FLANGE_DIA
    assert fresh.HUB_WALL_WORST > spec.HUB_WALL_WORST



def test_the_wall_gate_refuses_a_coarser_printed_row(monkeypatch) -> None:
    # Positive control: the title block as it is.
    assert _spec_fresh().OIL_HOLE_LIGAMENT_WORST == pytest.approx(
        spec.OIL_HOLE_LIGAMENT_WORST
    )
    # Negative control: rows loose enough to thin a wall under 2.0.
    monkeypatch.setattr(_printed_tolerance, "printed_band_mm", lambda _places: 1.0)
    with pytest.raises(AssertionError, match="floor"):
        _spec_fresh()


def test_the_oil_hole_is_centred_on_the_hub_body_the_lengths_leave() -> None:
    """R9-8 / R9-60: Ø1.2 on the drilled row, match-drilled through hub and
    sleeve with the hub seated and faced, centred on the hub body, so its
    station behind the hub front face follows the fitted overall and the
    printed flange, not a band of its own."""
    assert spec.OIL_HOLE_DIA == pytest.approx(1.2)
    assert spec.OIL_HOLE_STATION == pytest.approx(3.825)
    assert spec.OIL_HOLE_Z == pytest.approx(-6.225)
    body = (
        spec.HUB_LENGTH_FITTED_MIN
        - (spec.SPIGOT_LENGTH + _row(_places("SpigotLength")))
        - (spec.FLANGE_THICK + _row(_places("FlangeThick"))),
        spec.HUB_LENGTH_FITTED_MAX
        - (spec.SPIGOT_LENGTH - _row(_places("SpigotLength")))
        - (spec.FLANGE_THICK - _row(_places("FlangeThick"))),
    )
    assert spec.HUB_BODY_LENGTH_RANGE == pytest.approx(body)
    assert spec.OIL_HOLE_STATION_RANGE == pytest.approx(
        (
            body[0] / 2.0 - spec.OIL_HOLE_CENTRING_TOL,
            body[1] / 2.0 + spec.OIL_HOLE_CENTRING_TOL,
        )
    )
    # The sleeve drills the same hole: the spigot's end on the step, the
    # hole its station behind the hub front face, over the flat.
    sleeve = cluster_fit.SLEEVE
    assert spec.OIL_HOLE_SLEEVE_Z == pytest.approx(
        sleeve.FACE_WIDTH + spec.HUB_LENGTH - spec.OIL_HOLE_STATION
    )
    assert sleeve.FLAT_END_STATION < spec.OIL_HOLE_SLEEVE_Z < sleeve.OVERALL_LENGTH
    # Its ligament to the nose holds the sleeve's 2.0 target with the hub
    # front face at the window's nearest.
    nose_worst = (
        cluster_fit.HUB_NOSE_WINDOW[0]
        + spec.OIL_HOLE_STATION_RANGE[0]
        - (spec.OIL_HOLE_DIA + DRILL_PLUS) / 2.0
    )
    assert nose_worst >= sleeve.WALL_TARGET
    assert spec.OIL_HOLE_TO_NOSE_WORST == pytest.approx(nose_worst)


def test_sheet_text_states_facts_not_governance() -> None:
    for word in ("EXCEPTION", "ACCEPTED", "RULING", "POLICY", "BOOK FIDELITY"):
        assert word not in _sheet_text().upper()
    notes = spec.DRAWING_NOTES.splitlines()
    assert len(notes) <= 4
    assert [line for line in notes if len(line) > 70] == []


# Dimension text as the fleet's sheets print it: 3.5 mm caps, the advance and
# line pitch measured on the arbor-pedestal sheet (test_arbor_pedestal_drawing).
_CAP_M = 0.0035
_ADVANCE = 109.7 / (42 * 3.5)
_LINE_SPACING = 16.8 * 25.4 / 72.0 / 3.5
_NOMINAL = {
    "FlangeDia": spec.FLANGE_DIA,
    "HubDia": spec.HUB_DIA,
    "SpigotDia": spec.SPIGOT_DIA,
    "HubLength": spec.HUB_LENGTH,
    "FlangeThick": spec.FLANGE_THICK,
    "SpigotLength": spec.SPIGOT_LENGTH,
    "BoreDia": spec.BORE_DIA,
    "FlatToAxis": spec.FLAT_TO_AXIS,
    "BoltCircleDia": joint.BOLT_CIRCLE_DIA,
    "ScrewHoleDia": spec.SCREW_HOLE_DIA,
    "OilHoleDia": spec.OIL_HOLE_DIA,
}
# The bore's and the spigot's native bands print beside their values.
_BANDS = {
    "BoreDia": spec.BORE_BAND,
    "FlatToAxis": spec.FLAT_TO_AXIS_BAND,
    "SpigotDia": spec.SPIGOT_DIA_BAND,
}


def _printed_box(name: str, anchor: tuple[float, float]) -> Box:
    """The estimated box of a kept dimension's whole text, centred on its
    text point: value (the D-bore's with its upper limit) and callouts."""
    value = f"{_NOMINAL[name]:.{_places(name)}f}"
    if name.endswith("Dia"):
        value = f"\u00d8{value}"
    if name in _BANDS:
        value += f" +{_BANDS[name][0]:.3f}"
    if name in spec.REFERENCE_DIMENSIONS:
        value = f"({value})"
    lines = [
        drawing.DIMENSION_CALLOUTS_ABOVE.get(name),
        value,
        drawing.DIMENSION_CALLOUTS_BELOW.get(name),
    ]
    box = estimate_text_box(
        "\n".join(line for line in lines if line),
        anchor=anchor,
        height=_CAP_M,
        reference=2,
        advance_ratio=_ADVANCE,
        line_spacing=_LINE_SPACING,
    )
    assert box is not None
    return box


def test_turned_diameters_print_inline_beside_their_own_step_on_the_edge_view() -> None:
    """Policy rule 7: the turned diameters sit on the edge view, not leader-
    piled through the face view's centre, each inline between its own
    extension lines and off the part; the face view keeps the bore and the
    holes; no two texts on the sheet print over each other."""
    s = drawing._S
    axis_y = drawing.SIDE_CENTER[1]
    edge = Box(
        drawing.HUB_FRONT_X,
        axis_y - spec.FLANGE_DIA / 2.0 * s,
        drawing.SPIGOT_END_X,
        axis_y + spec.FLANGE_DIA / 2.0 * s,
    )
    flange_r = spec.FLANGE_DIA / 2.0 * s

    def face_gap(box: Box) -> float:
        """Clearance from ``box`` to the face view's flange circle."""
        cx, cy = drawing.END_CENTER
        nearest_x = min(max(cx, box.xmin), box.xmax)
        nearest_y = min(max(cy, box.ymin), box.ymax)
        return math.hypot(nearest_x - cx, nearest_y - cy) - flange_r

    assert set(drawing.END_KEEP) == {
        "BoreDia",
        "FlatToAxis",
        "BoltCircleDia",
        "ScrewHoleDia",
    }
    boxes = {
        name: _printed_box(name, anchor)
        for keep in (drawing.END_KEEP, drawing.SIDE_KEEP)
        for name, anchor in keep.items()
    }
    for name, diameter in (
        ("HubDia", spec.HUB_DIA),
        ("SpigotDia", spec.SPIGOT_DIA),
        ("FlangeDia", spec.FLANGE_DIA),
    ):
        half = diameter / 2.0 * s
        assert axis_y - half < boxes[name].ymin, name
        assert boxes[name].ymax < axis_y + half, name
    for name in drawing.SIDE_KEEP:
        assert boxes[name].gap(edge) >= 0.004, name
    for name in drawing.END_KEEP:
        assert face_gap(boxes[name]) >= 0.004, name
    # The oil hole's callout stands above the flange's O.D. extension line,
    # its text ending left of the hub front, where the overall's extension
    # line rises to its row; the overall stands a row above the two lengths,
    # which share a row, its text right of the spigot's end.
    assert boxes["OilHoleDia"].ymin > edge.ymax
    assert boxes["OilHoleDia"].xmax < drawing.HUB_FRONT_X
    assert boxes["HubLength"].ymin > boxes["SpigotLength"].ymax
    assert boxes["HubLength"].xmin > drawing.SPIGOT_END_X
    assert drawing.SIDE_KEEP["FlangeThick"][1] == drawing.SIDE_KEEP["SpigotLength"][1]
    # The spigot's text and callout end clear of the flange's dimension line.
    assert boxes["SpigotDia"].xmax < drawing.SIDE_KEEP["FlangeDia"][0] - 0.004
    clashes = [
        (a, b)
        for a, b in itertools.combinations(sorted(boxes), 2)
        if boxes[a].overlaps(boxes[b], tol=0.0)
    ]
    assert clashes == []


class _FakeSketchManager:
    AddToDB = False


class _FakeSolidWorks:
    """Just enough of the adapter for the recipe's own calls; it keeps the
    lines, arcs and circles the recipe draws, by sketch in creation order."""

    def __init__(self) -> None:
        self.currentSketchManager = _FakeSketchManager()
        self._n = 0
        self.sketch = 0
        self.lines: dict[str, tuple[float, ...]] = {}
        self.sketch_lines: dict[int, list[str]] = {}
        self.arcs: list[tuple[float, ...]] = []
        self.circles: list[tuple[float, ...]] = []

    async def _entity(self, *_args, **_kwargs) -> str:
        self._n += 1
        return f"Entity{self._n}"

    async def create_sketch(self, _plane) -> str:
        self.sketch += 1
        return await self._entity()

    async def add_line(self, *args) -> str:
        line = await self._entity()
        self.lines[line] = args
        self.sketch_lines.setdefault(self.sketch, []).append(line)
        return line

    async def add_arc(self, *args) -> str:
        self.arcs.append(args)
        return await self._entity()

    async def add_circle(self, *args) -> str:
        self.circles.append(args)
        return await self._entity()

    create_part = exit_sketch = create_plane = _entity
    create_extrusion = create_cut_extrude = create_revolve = add_chamfer = _entity
    add_centerline = add_sketch_constraint = add_sketch_dimension = _entity


def _drive_value(expr: str, globals_mm: dict[str, float]) -> float:
    text = re.sub(r'"(\w+)"', lambda m: repr(globals_mm[m.group(1)]), expr)
    return float(eval(text, {"__builtins__": {}}, {}))  # noqa: S307 -- test-local arithmetic


def test_every_drive_equation_reproduces_the_modelled_geometry(monkeypatch) -> None:
    """Every drive equation (bolt-circle factors included) evaluates to the
    size, centre or length the recipe draws, so a rebuild after the drives
    moves nothing: the screw holes stay on the joint's shared pattern, the
    turned profile on its printed sizes, the D-bore on its two sizes and the
    oil hole centred on the body."""
    globals_mm: dict[str, float] = {}
    circles: list[tuple] = []
    chains: list[list[str]] = []
    diametric: dict[str, str] = {}
    rows: dict[int, list[tuple[str | None, str | None]]] = {}
    drives: dict[str, dict[str | None, str | None]] = {}
    driven: dict[str, str] = {}

    async def set_global(_adapter, name, value):
        globals_mm[name] = float(value.removesuffix("mm"))

    async def define_circle(_adapter, x, y, radius, label, *, dims, names, drives):
        circles.append((label, x, y, radius, names, drives))
        return label

    real_chain = part.add_line_chain

    async def add_line_chain(adapter, points, close=True):
        chains.append(await real_chain(adapter, points, close))
        return chains[-1]

    async def add_diametric(_adapter, _axis, line, _text_xy, label):
        diametric[label] = line

    def record(self, name, drive=None):
        rows.setdefault(id(self), []).append((name, drive))

    def apply(self, _adapter, feature):
        drives[feature] = dict(rows.get(id(self), []))
        return []

    async def quiet(*_args, **_kwargs):
        return None

    async def drive_dimension(_adapter, dim_name, expr):
        driven[dim_name] = expr

    def names(_adapter, feature, dim_names):
        return [f"{name}@{feature}" for name in dim_names]

    monkeypatch.setattr(part, "set_global", set_global)
    monkeypatch.setattr(part, "define_circle", define_circle)
    monkeypatch.setattr(part, "add_line_chain", add_line_chain)
    monkeypatch.setattr(part, "add_diametric_linear_dimension", add_diametric)
    monkeypatch.setattr(_sketch.SketchDims, "record", record)
    monkeypatch.setattr(_sketch.SketchDims, "apply", apply)
    monkeypatch.setattr(_appearance, "check", lambda _label, result: result)
    monkeypatch.setattr(_bore_axis, "check", lambda _label, result: result)
    monkeypatch.setattr(_check, "check", lambda _label, result: result)
    monkeypatch.setattr(_part_save, "check", lambda _label, result: result)
    monkeypatch.setattr(_rebuild, "check", lambda _label, result: result)
    monkeypatch.setattr(_sketch, "check", lambda _label, result: result)
    monkeypatch.setattr(_sketch_chains, "check", lambda _label, result: result)
    monkeypatch.setattr(_sketch_circle, "check", lambda _label, result: result)
    monkeypatch.setattr(_sketch_rectangle, "check", lambda _label, result: result)
    monkeypatch.setattr(part, "check", lambda _label, result: result)
    monkeypatch.setattr(part, "name_dimensions", names)
    monkeypatch.setattr(part, "name_bore_axis", lambda *a, **k: _async("Axis1"))
    monkeypatch.setattr(part, "drive_dimension", drive_dimension)
    monkeypatch.setattr(part, "_early_bound", lambda obj, _iface: obj)
    for helper in (
        "volume_check",
        "bbox_extent_check",
        "ensure_fully_defined",
        "anchor_point_to_origin",
        "dimension_between",
        "force_rebuild",
        "apply_material",
        "report_mass_properties",
        "save_part_and_images",
    ):
        monkeypatch.setattr(part, helper, quiet)
    for helper in (
        "name_last_feature",
        "set_sketch_direct_db",
        "_as_construction",
        "_check_z_span",
        "set_dimension_bilateral_tolerance",
        "apply_drawing_precision",
        "clear_dimensions_for_drawing",
        "mark_dimensions_for_drawing",
        "apply_drawing_properties",
    ):
        monkeypatch.setattr(part, helper, lambda *a, **k: None)

    fake = _FakeSolidWorks()
    asyncio.run(part.build(fake))

    def value(feature: str, name: str) -> float:
        return _drive_value(drives[feature][name], globals_mm)

    # Turned profile: each diameter twice its step's radius, the flange's
    # thickness the run of its O.D., the overall the profile's reach.
    (profile,) = chains
    flange_u, flange_v0, _u, flange_v1 = fake.lines[diametric["FlangeDia"]]
    hub_u, *_hub = fake.lines[diametric["HubDia"]]
    spigot_u, spigot_v0, _su, spigot_v1 = fake.lines[diametric["SpigotDia"]]
    profile_v = [v for line in profile for v in fake.lines[line][1::2]]
    drawn = {
        "FlangeDia": 2.0 * flange_u,
        "HubDia": 2.0 * hub_u,
        "SpigotDia": 2.0 * spigot_u,
        "FlangeThick": abs(flange_v1 - flange_v0),
        "SpigotLength": abs(spigot_v1 - spigot_v0),
        "HubLength": max(profile_v) - min(profile_v),
    }
    assert set(drives["HubProfile"]) == set(drawn)
    for name, size in drawn.items():
        assert value("HubProfile", name) == pytest.approx(size, abs=1e-9), name
    assert drawn["FlangeDia"] == pytest.approx(spec.FLANGE_DIA)
    assert drawn["HubLength"] == pytest.approx(spec.HUB_LENGTH)
    assert drawn["SpigotLength"] == pytest.approx(spec.SPIGOT_LENGTH)
    # The spigot's bore runs the spigot's length, driven by it.
    assert _drive_value(
        driven["SpigotBoreDepth@SpigotBore"], globals_mm
    ) == pytest.approx(spec.SPIGOT_LENGTH)

    # D-bore: the arc's radius is half the bore, centred on the axis; the
    # witness runs from the axis to the flat, square to it.
    ((cx, cy, sx, sy, ex, ey),) = fake.arcs
    flat, witness = fake.sketch_lines[2]
    _fx0, flat_y0, _fx1, flat_y1 = fake.lines[flat]
    wx0, wy0, wx1, wy1 = fake.lines[witness]
    assert (cx, cy, wx0, wy0, wx1) == pytest.approx((0.0, 0.0, 0.0, 0.0, 0.0))
    assert math.hypot(sx, sy) == pytest.approx(math.hypot(ex, ey))
    assert sy == ey == flat_y0 == flat_y1 == wy1
    assert set(drives["BoreProfile"]) == {"BoreDia", "FlatToAxis"}
    assert value("BoreProfile", "BoreDia") == pytest.approx(2.0 * math.hypot(sx, sy))
    assert value("BoreProfile", "FlatToAxis") == pytest.approx(abs(wy1 - wy0))
    assert wy1 == pytest.approx(-spec.FLAT_TO_AXIS)

    # Oil hole: the station line runs from the hub front face to the hole's
    # centre, half the hub body behind it.
    (station,) = fake.sketch_lines[5]
    _u0, front_v, _u1, hole_v = fake.lines[station]
    ((_cu, centre_v, oil_r),) = fake.circles
    assert centre_v == pytest.approx(hole_v)
    assert value("OilHoleProfile", "OilHoleDatum") == pytest.approx(front_v)
    assert value("OilHoleProfile", "OilHoleStation") == pytest.approx(front_v - hole_v)
    assert value("OilHoleProfile", "OilHoleStation") == pytest.approx(
        spec.HUB_BODY_LENGTH / 2.0
    )
    assert value("OilHoleProfile", "OilHoleDia") == pytest.approx(2.0 * oil_r)
    # The one-wall cut runs a body's width deep.
    assert _drive_value(driven["OilHoleDepth@OilHole"], globals_mm) == spec.HUB_DIA
    holes = [c for c in circles if c[0].startswith("screw hole")]
    drawn_holes = [v for _label, x, y, *_rest in holes for v in (x, y)]
    assert drawn_holes == pytest.approx([v for xy in joint.screw_centres() for v in xy])
    checked = 0
    for label, x, y, radius, _names, (d_x, d_y, d_size) in circles:
        for emitted, drive in ((abs(x), d_x), (abs(y), d_y), (2.0 * radius, d_size)):
            if emitted < 1e-9:
                continue
            assert drive is not None, (label, emitted)
            assert _drive_value(drive, globals_mm) == pytest.approx(
                emitted, abs=1e-9
            ), (
                label,
                drive,
            )
            checked += 1
    # The bolt circle's diameter, three hole sizes, five non-zero hole
    # centres and the spigot bore's size.
    assert checked == 1 + 3 + 5 + 1


async def _async(value):
    return value


def test_registry_row_is_the_turned_brass_mha_159() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-PD-017"
    assert int(row["quantity"]) == 1
    assert "C36000" in row["material_specification"]
    assert row["material"] == part.MATERIAL
    assert row["tolerance_class"] == "machined_block"


def _calls(path: str) -> dict[str, ast.Call]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return {
        node.func.id: node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_the_part_carries_every_property_its_drawing_requires(monkeypatch) -> None:
    """The drawing refuses a source part missing a required property; every
    one must be carried and non-blank."""
    import _drawing_marks

    required = ast.literal_eval(
        next(
            k.value
            for k in _calls(drawing.__file__)["read_required_properties"].keywords
            if k.arg == "required"
        )
    )
    carried = dict(_part_properties.part_properties(part.PART_NAME))
    stamp = _calls(part.__file__)["apply_drawing_properties"]
    extra = ast.literal_eval(
        ast.unparse(stamp.args[2]).replace("DRAWING_NOTES", repr(spec.DRAWING_NOTES))
    )
    stamped: dict[str, str] = {}
    monkeypatch.setattr(
        _drawing_marks,
        "apply_custom_properties",
        lambda _adapter, props: stamped.update(props),
    )
    _drawing_marks.apply_drawing_properties(None, part.PART_NAME, extra)
    carried.update(stamped)
    assert [name for name in required if not str(carried.get(name) or "").strip()] == []
