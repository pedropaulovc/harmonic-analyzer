"""Offline contracts for the transgear disc hub (MHA-PD-17) and its drawing."""

from __future__ import annotations

import ast
import asyncio
import importlib.util
import itertools
import math
from pathlib import Path
import re
from types import SimpleNamespace

import pytest

import _appearance
import _bore_axis
import _check
import _config
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
import _drawing_edges
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DRAWING_TEMPLATES
import _gtol_face
from _layout_geometry import Box, estimate_text_box
import _part_properties
import _part_save
import _printed_tolerance
import _rebuild
import _sketch
import _sketch_chains
import _sketch_circle
import _sketch_rectangle
import build_pd_transgear_disc_hub as part
import draw_pd_transgear_disc_hub as drawing
from pd_cluster_stack_band import FIT_LENGTH_BAND_IN, STACK_NAME
import pd_transgear_disc_hub_geometry as joint
import pd_transgear_disc_hub_spec as spec
import transgear_cluster_fit as cluster_fit

WALL_FLOOR = 0.080 * 25.4  # the .080 in wall target
DRILL_PLUS = _printed_tolerance.drilled_oversize_mm(unit="in")
IN = 25.4


def _row(places: int) -> float:
    """The ± the inch title block prints for a dimension shown at ``places``."""
    return _printed_tolerance.printed_band_mm(places, unit="in")


def _clr(text: str) -> tuple[float, float]:
    """A printed inch clearance range ``.0005-.0018`` in millimetres."""
    low, high = text.split("-")
    return float(low) * IN, float(high) * IN


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
    views = (drawing.END_KEEP, drawing.SIDE_KEEP, drawing.SECTION_KEEP)
    assert set().union(*map(set, views)) == marked
    for a, b in itertools.combinations(views, 2):
        assert not set(a) & set(b)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    # Each callout rides a dimension the sheet keeps.
    assert set(drawing.DIMENSION_CALLOUTS_BELOW) <= marked
    assert set(drawing.DIMENSION_CALLOUTS_ABOVE) <= marked
    assert set(drawing.SECTION_CALLOUTS_BELOW) <= set(drawing.SECTION_KEEP)
    # Each view proves only the places of what it keeps, and together they
    # prove every marked dimension's.
    proofs = (
        drawing._precision_of({**drawing.END_KEEP, **drawing.SIDE_KEEP}),
        drawing._precision_of(drawing.SECTION_KEEP),
    )
    assert not set(proofs[0]) & set(proofs[1])
    assert {**proofs[0], **proofs[1]} == spec.DRAWING_PRECISION_BY_NAME


def test_the_sheet_prints_the_overall_and_the_flange_never_the_hub_body() -> None:
    """R9-5: the overall (spigot end to hub front) is a +/-.001 term of the
    disc cluster stack, .539 at 3 places; the flange .094 is a .XXX
    length and the spigot .144 a stack term; the hub body is their
    remainder and is not printed.  The key-pin hole's station, which the oil
    hole shares, prints at .XX from the hub front face (machinist review:
    "centred" located nothing); its ream and knockout at four places and its
    chord offset and stop at three in A-A.  The bore is round: nothing
    locates a flat."""
    diameters = {
        "FlangeDia",
        "HubDia",
        "SpigotDia",
        "BoreDia",
        "BoltCircleDia",
        "ScrewHoleDia",
        "OilHoleDia",
        "KeyPinDia",
        "KeyPinDrillDia",
    }
    lengths = set(spec.DRAWING_PRECISION_BY_NAME) - diameters
    assert lengths == {
        "HubLength",
        "FlangeThick",
        "SpigotLength",
        "KeyPinStation",
        "KeyPinChord",
        "KeyPinStop",
    }
    assert _places("KeyPinStation") == 2
    assert _places("KeyPinDia") == _places("KeyPinDrillDia") == 4
    assert _places("KeyPinChord") == _places("KeyPinStop") == 3
    assert spec.REFERENCE_DIMENSIONS == frozenset()
    assert {"HubLength", "SpigotLength", "KeyPinStation"} < set(drawing.SIDE_KEEP)
    assert set(drawing.SECTION_KEEP) == spec.DRAWING_DIMENSIONS["KeyPinProfile"]
    assert spec.HUB_LENGTH == cluster_fit.HUB_LENGTH == pytest.approx(0.539 * IN)
    assert _places("HubLength") == cluster_fit.LENGTH_PLACES == 3
    assert spec.FLANGE_THICK == pytest.approx(0.094 * IN) and _places("FlangeThick") == 3
    assert spec.SPIGOT_LENGTH == pytest.approx(0.144 * IN) and _places("SpigotLength") == 3
    assert spec.BORE_DIA == spec.SLEEVE.BOSS_DIA and _places("BoreDia") == 4
    assert spec.DRAWING_DIMENSIONS["BoreProfile"] == {"BoreDia"}
    assert spec.HUB_DIA == pytest.approx(0.540 * IN) and _places("HubDia") == 3
    assert spec.SPIGOT_DIA == pytest.approx(0.498 * IN) and _places("SpigotDia") == 4
    assert spec.FLANGE_DIA == pytest.approx(1.05 * IN) and _places("FlangeDia") == 2
    assert joint.BOLT_CIRCLE_DIA == pytest.approx(0.75 * IN)
    assert joint.BOLT_CIRCLE_PLACES == 2
    assert spec.HUB_BODY_LENGTH == pytest.approx(0.301 * IN)


def test_the_overall_and_the_spigot_are_terms_of_the_disc_cluster_stack() -> None:
    """#2124: the overall and the spigot set the collar air and the recess,
    so they print +/-.001 natively, named on the stack."""
    assert spec.HUB_LENGTH_BAND == cluster_fit.LENGTH_BAND == FIT_LENGTH_BAND_IN
    assert joint.SPIGOT_LENGTH_BAND == spec.SPIGOT_LENGTH_BAND == FIT_LENGTH_BAND_IN
    assert (spec.HUB_LENGTH_MIN, spec.HUB_LENGTH_MAX) == pytest.approx(
        (spec.HUB_LENGTH - FIT_LENGTH_BAND_IN, spec.HUB_LENGTH + FIT_LENGTH_BAND_IN)
    )
    assert (spec.SPIGOT_LENGTH_MIN, spec.SPIGOT_LENGTH_MAX) == pytest.approx(
        (
            spec.SPIGOT_LENGTH - FIT_LENGTH_BAND_IN,
            spec.SPIGOT_LENGTH + FIT_LENGTH_BAND_IN,
        )
    )
    assert "HubLength" not in spec.REFERENCE_DIMENSIONS
    callouts = drawing.DIMENSION_CALLOUTS_BELOW
    assert callouts["HubLength"] == callouts["SpigotLength"] == (
        f"SEE NOTE {spec.STACK_NOTE}"
    )
    assert STACK_NAME in spec.STACK_TEXT


def test_the_bore_the_spigot_and_the_stack_lengths_carry_model_bands() -> None:
    """Every other size is governed by its printed places and the holes by
    the title block's DRILLED HOLES row."""
    assert model_toleranced_dimensions(part) == {
        ("BoreProfile", "BoreDia"): "*BORE_DEVIATIONS",
        ("HubProfile", "SpigotDia"): "*SPIGOT_DIA_DEVIATIONS",
        ("HubProfile", "HubLength"): "HUB_LENGTH_BAND",
        ("HubProfile", "SpigotLength"): "SPIGOT_LENGTH_BAND",
        ("KeyPinProfile", "KeyPinDia"): "*KEY_PIN_HOLE_DEVIATIONS",
        ("KeyPinProfile", "KeyPinChord"): "KEY_PIN_LOCATION_BAND",
        ("KeyPinProfile", "KeyPinStop"): "KEY_PIN_LOCATION_BAND",
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


def test_the_round_bore_slides_on_the_sleeve_boss_at_every_printed_limit() -> None:
    """#2409: the bore is plain round and reamed through; the two parts are
    made apart, each to its own sheet, so it keeps a clearance (never a
    bind) at every printed limit, and its callout names the mate it slides
    on (rule 4) and ends on the least finished wall over it (rule 20)."""
    import build_pd_transgear_feed_pinion as sleeve_part
    import pd_transgear_feed_pinion_spec as sleeve

    assert spec.BORE_DIA == sleeve.BOSS_DIA
    assert spec.BORE_BAND == pytest.approx((0.0010 * IN, 0.0005 * IN))  # +.0010/+.0005
    assert part.BORE_DIA == drawing.BORE_DIA == spec.BORE_DIA
    assert part.BORE_R == pytest.approx(sleeve.BOSS_DIA / 2.0)
    assert part.BORE_DEVIATIONS == spec.BORE_DEVIATIONS
    # The reamer's .3135 is the bore's least size.
    assert spec.BORE_DIA + spec.BORE_BAND[1] == pytest.approx(0.3135 * IN)
    # One round cut through the whole part: no flat, no second bore.
    assert part.V_BORE == pytest.approx(math.pi * part.BORE_R**2 * spec.HUB_LENGTH)
    for name in ("FLAT_TO_AXIS", "FLAT_CLEARANCE", "BORE_FIT_TEXT"):
        assert not hasattr(spec, name)

    bore = _printed_limits(part, spec, "BoreProfile", "BoreDia", spec.BORE_DIA)
    boss = _printed_limits(
        sleeve_part, sleeve, "SleeveProfile", "BossDia", sleeve.BOSS_DIA
    )
    round_fit = (bore[0] - boss[1], bore[1] - boss[0])
    assert round_fit[0] >= -1e-9
    assert round_fit == pytest.approx(spec.BOSS_CLEARANCE_LIMITS, abs=1e-6)
    assert spec.BOSS_CLEARANCE == spec.BOSS_CLEARANCE_LIMITS[1]
    callout = drawing.DIMENSION_CALLOUTS_BELOW["BoreDia"].splitlines()
    assert any(spec.SLEEVE_NUMBER in line for line in callout)
    assert callout[-1] == spec.BORE_WALL_TEXT
    assert len(callout) <= 3


def test_boss_round_engagement_follows_the_live_sleeve() -> None:
    """The retained axial stack keeps the finite cutter end behind the
    locating round.  The spigot seats on the step; the engagement still
    allows it to slide forward off the step by up to the whole end float, its
    front face then past the nose."""
    sleeve = spec.SLEEVE
    slide = cluster_fit.END_FLOAT_RANGE[1]
    teeth = (
        sleeve.FACE_WIDTH - sleeve.FACE_WIDTH_BAND,
        sleeve.FACE_WIDTH + sleeve.FACE_WIDTH_BAND,
    )
    sleeve_min = sleeve.OVERALL_LENGTH - sleeve.OVERALL_LENGTH_BAND
    hub_min = spec.HUB_LENGTH - FIT_LENGTH_BAND_IN
    # Seated: hub front face to the boss's first full round; slid forward:
    # the nose to the first full round behind the slid spigot.  Each exposed
    # end of the contact loses the title block's edge break.
    brk = 0.010 * IN
    engagement = min(
        *(
            tooth + hub_min - brk - max(tooth + brk, sleeve.CUTTER_RUNOUT_END_WORST)
            for tooth in teeth
        ),
        sleeve_min - brk - max(teeth[1] + slide + brk, sleeve.CUTTER_RUNOUT_END_WORST),
    )
    assert spec.ROUND_ENGAGEMENT_MIN == pytest.approx(engagement)
    assert engagement > 0.0


def test_the_key_pin_keys_the_hub_on_the_sleeve_flat() -> None:
    """#2409: one MHA-PD-VN-69 1/16 x 5/16 hardened dowel lies on a chord
    of the hub body over the MHA-PD-10 flat, pressed from +X into a .0615
    REAM_H7 hole to its stop: its side keeps air to the flat at every
    printed limit (the hub slides on), so the hub turns a stated play before
    the pin bears; both ends stay under the O.D., each held in at least 1D
    of wall beside the bore's window, gripped at both press extremes, and
    the wall over the ream holds the .060 floor."""
    import pd_vn_transgear_hub_key_pin_spec as pin

    sleeve = spec.SLEEVE
    assert spec.KEY_PIN_NUMBER == _config.parts("pd-vn-transgear-hub-key-pin")["number"]
    assert spec.KEY_PIN is pin
    assert spec.KEY_PIN_HOLE_DIA == pytest.approx(0.0615 * IN)
    hole_max = spec.KEY_PIN_HOLE_DIA + spec.KEY_PIN_HOLE_BAND[0]
    hole_min = spec.KEY_PIN_HOLE_DIA + spec.KEY_PIN_HOLE_BAND[1]
    assert (hole_min, hole_max) == pytest.approx((0.0615 * IN, 0.0620 * IN))
    pin_min, pin_max = pin.DIA_LIMITS_MM
    assert spec.KEY_PIN_INTERFERENCE == pytest.approx((pin_min - hole_max, pin_max - hole_min))
    assert pin_min - hole_max > 0.0
    assert spec.KEY_PIN_STATION == pytest.approx(0.15 * IN)
    assert spec.KEY_PIN_Z == pytest.approx(spec.HUB_FRONT_Z + spec.KEY_PIN_STATION)
    station = (
        spec.KEY_PIN_STATION - _row(2),
        spec.KEY_PIN_STATION + _row(2),
    )
    # The hole's whole section, at the shortest teeth and hub and the
    # greatest station, ahead of the flat's end wall at its worst station.
    teeth_min = sleeve.FACE_WIDTH - sleeve.FACE_WIDTH_BAND
    hub_min = spec.HUB_LENGTH - FIT_LENGTH_BAND_IN
    flat_end = sleeve.FLAT_END_STATION + sleeve.STATION_TOL
    clearance = teeth_min + hub_min - station[1] - hole_max / 2.0 - flat_end
    assert spec.KEY_PIN_FLAT_END_CLEARANCE_WORST == pytest.approx(clearance)
    assert clearance > 0.0
    assert spec.KEY_PIN_SLEEVE_Z == pytest.approx(0.924 * IN)
    assert spec.KEY_PIN_SLEEVE_Z < sleeve.OVERALL_LENGTH
    # The chord and the stop at the reamed-hole location band.
    band = 0.002 * IN
    assert spec.KEY_PIN_LOCATION_BAND == pytest.approx(band)
    chord = (spec.KEY_PIN_CHORD_OFFSET - band, spec.KEY_PIN_CHORD_OFFSET + band)
    stop = (spec.KEY_PIN_STOP - band, spec.KEY_PIN_STOP + band)
    assert chord == pytest.approx((0.172 * IN, 0.176 * IN))
    assert stop == pytest.approx((0.158 * IN, 0.162 * IN))
    assert spec.KEY_PIN_CHORD_RANGE == pytest.approx(chord)
    assert spec.KEY_PIN_STOP_RANGE == pytest.approx(stop)
    assert spec.KEY_PIN_STOP_X == -spec.KEY_PIN_STOP
    # The #56 knockout, drilled through, leaves a step the pin stops on.
    assert spec.KEY_PIN_DRILL_DIA == pytest.approx(0.0465 * IN)
    assert spec.KEY_PIN_DRILL_DIA + DRILL_PLUS < hole_min
    # The pin's side never touches the flat: air at every printed limit.
    flat = (
        sleeve.FLAT_TO_AXIS + sleeve.FLAT_TO_AXIS_BAND[1],
        sleeve.FLAT_TO_AXIS + sleeve.FLAT_TO_AXIS_BAND[0],
    )
    air = (chord[0] - pin_max / 2.0 - flat[1], chord[1] - pin_min / 2.0 - flat[0])
    assert spec.KEY_PIN_FLAT_AIR == pytest.approx(air)
    assert air[0] > 0.0
    # It bears on the flat where it crosses the least bore, along the least
    # flat chord; the play is the greatest air over the shorter lever, lost
    # both ways on reversal at the 12T's pitch radius.
    boss_min_r = (sleeve.BOSS_DIA + sleeve.BOSS_DIA_BAND[1]) / 2.0
    flat_chord = 2.0 * math.sqrt(boss_min_r**2 - flat[1] ** 2)
    assert spec.KEY_PIN_FLAT_CHORD_MIN == pytest.approx(flat_chord)
    bore_min_r = (spec.BORE_DIA + spec.BORE_BAND[1]) / 2.0
    bearing = math.sqrt(bore_min_r**2 - (chord[1] - pin_min / 2.0) ** 2)
    lever = min(flat_chord / 2.0, bearing)
    play = math.degrees(air[1] / lever)
    assert spec.KEY_PIN_PLAY_DEG == pytest.approx(play)
    assert spec.KEY_PIN_PAPER_LOST == pytest.approx(
        2.0 * math.radians(play) * sleeve.PITCH_DIA / 2.0
    )
    # The pin spans x = -stop .. length - stop; both ends, the ream's corner
    # at the deepest stop and the pin's rim at its farthest outer end, stay
    # under the least O.D. on the farthest chord.
    length_min, length_max = pin.LENGTH_LIMITS_MM
    ends = (length_min - stop[1], length_max - stop[0])
    assert spec.KEY_PIN_END_X_RANGE == pytest.approx(ends)
    hub_r_min = (spec.HUB_DIA - _row(_places("HubDia"))) / 2.0
    recess = hub_r_min - max(
        math.hypot(stop[1], chord[1] + hole_max / 2.0),
        math.hypot(ends[1], chord[1] + pin_max / 2.0),
    )
    assert spec.KEY_PIN_END_RECESS_WORST == pytest.approx(recess)
    assert recess > 0.0
    # Each end held in at least 1D of wall beside the largest bore's window.
    bore_max_r = (spec.BORE_DIA + spec.BORE_BAND[0]) / 2.0
    window = math.sqrt(bore_max_r**2 - (chord[0] - hole_max / 2.0) ** 2)
    support = (stop[0] - window, ends[0] - window)
    assert spec.KEY_PIN_SUPPORT_WORST == pytest.approx(support)
    assert min(support) >= pin.DIA
    # The wall over the ream: on the floor, under the target.
    wall = hub_r_min - (chord[1] + hole_max / 2.0)
    assert spec.KEY_PIN_WALL_WORST == pytest.approx(wall)
    assert 0.060 * IN - 1e-9 <= wall < WALL_FLOOR
    # The oil hole is match-drilled at the key pin's station, opposite it.
    assert spec.OIL_HOLE_SLEEVE_Z == spec.KEY_PIN_SLEEVE_Z
    # The sleeve flat's own wall over its bore keeps its floor.
    flat_wall = (
        sleeve.FLAT_TO_AXIS
        + sleeve.FLAT_TO_AXIS_BAND[1]
        - (sleeve.BORE_DIA + sleeve.BORE_DIA_BAND[0]) / 2.0
    )
    assert sleeve.FLAT_WALL_WORST == pytest.approx(flat_wall)
    assert flat_wall >= sleeve.WALL_FLOOR


def test_the_package_declares_the_chord_wall_and_the_key_pin_play() -> None:
    """Round 3: the .060 wall over the chord ream is a delegated minor in the
    owner's thin-wall band (#2144 item 3.2), and the stated play a delegated
    accept pending the owner's review."""
    exceptions = {
        row["id"]: row
        for row in _config.parts(part.PART_NAME)["machinist_exceptions"]
    }
    wall, play = exceptions["RV-03"], exceptions["RV-04"]
    assert wall["kind"] == "minor"
    assert "#2144 item 3.2" in wall["reason"]
    assert play["kind"] == "accept"
    assert play["reason"].startswith(
        "Delegated ruling 2026-11-11 (Main), no precedent; owner review #2144"
    )
    assert f"{spec.KEY_PIN_PLAY_DEG:.1f} deg" in play["finding"]
    assert not any("rule 18" in row["finding"] for row in exceptions.values())


def test_the_spigot_seats_on_the_step_square_and_clear_of_the_disc() -> None:
    """R9-68: the spigot clears the disc's bore and seats on the 12T's step.
    Its end and the flange's rear face are square to the bore (datum A) on
    the sheet; the disc's tilt reads both, the step's and the hub's rock on
    the boss, and its rear face stays in air ahead of the step."""
    import pd_rack_pinion_spec as disc
    import pd_transgear_feed_pinion_spec as sleeve

    # The spigot clears the disc's bore: the two printed bands never bind.
    spigot = (
        spec.SPIGOT_DIA + spec.SPIGOT_DIA_BAND[1],
        spec.SPIGOT_DIA + spec.SPIGOT_DIA_BAND[0],
    )
    disc_bore = (disc.BORE_DIA + disc.BORE_BAND[1], disc.BORE_DIA + disc.BORE_BAND[0])
    fit = (disc_bore[0] - spigot[1], disc_bore[1] - spigot[0])
    assert fit == pytest.approx(disc.SPIGOT_DIAMETRAL_CLEARANCE)
    assert fit[0] >= 0.0
    assert spec.DISC_NUMBER in drawing.DIMENSION_CALLOUTS_BELOW["SpigotDia"].splitlines()[0]
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
    assert spec.GEOMETRIC_TOLERANCES_IN == {
        "flange rear face perpendicularity to bore": ".001",
        "spigot end perpendicularity to bore": ".001",
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
        - disc.REAR_FACE_PARALLELISM_BOUND_MM
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
    # Section A-A's lower letter once stood on the flange's rear face, where
    # the leader ran level through it (r4 layout audit); it now stands under
    # the flange, well below the leader's landing.
    lower_letter = drawing.section_letter_box(drawing.SECTION_LINE[0])
    assert _nominal_landing(flange)[1] >= lower_letter.ymax + 0.006


def _circle(radius: float, z: float, *, x: float = 0.0, axis_z: float = 1.0):
    return _drawing_edges.ViewEdge(
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
    edges = _drawing_edges.ViewEdges(label="edge", edges=(*neighbours, rim))
    assert drawing.face_rim(edges, frame) is rim
    lone = _drawing_edges.ViewEdges(label="edge", edges=neighbours)
    with pytest.raises(
        RuntimeError, match=rf"matched 0 of 4 circles: .*r {radius + 0.001:.4f} at"
    ):
        drawing.face_rim(lone, frame)
    split = _drawing_edges.ViewEdges(label="edge", edges=(rim, _circle(radius, 0.0)))
    with pytest.raises(RuntimeError, match="matched 2 of 2"):
        drawing.face_rim(split, frame)
    with pytest.raises(RuntimeError, match="matched 0 of 0 circles: none"):
        drawing.face_rim(_drawing_edges.ViewEdges(label="edge", edges=()), frame)


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
    return _drawing_edges.ViewEdge(edge=edge, line=None, circle=None, vertices=None)


@pytest.mark.parametrize("plane_first", [False, True])
def test_each_frame_attaches_to_the_plane_its_rim_bounds_never_the_cylinder(
    plane_first: bool,
) -> None:
    """MR #1166: the spigot end's frame, left on the rim the end shares with
    the spigot's O.D., read as controlling the cylinder.  Each frame takes,
    of its rim's two faces, the one plane square to the hub axis at its
    station facing +Z -- the spigot's end at z .144, the flange's rear face
    at z 0 -- whichever face the rim reports first.  A plane at another
    station or facing the other way never stands in for it, and two such
    planes, or fewer than two faces, fail naming each face."""
    spigot, flange = drawing.SPIGOT_END_FRAME, drawing.FLANGE_FACE_FRAME
    assert spec.SPIGOT_LENGTH == pytest.approx(0.144 * IN)
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
            *drawing.DIMENSION_CALLOUTS_BELOW.values(),
            *drawing.DIMENSION_CALLOUTS_ABOVE.values(),
            *drawing.SECTION_CALLOUTS_BELOW.values(),
            drawing.NOTES_TEXT,
        )
    )


def test_every_mate_the_sheet_cites_is_named_with_its_own_number() -> None:
    """drawing-guidelines.md rule 4 (tighten only for function, and name the
    mate): every part number the sheet cites is a mate's own number: the
    sleeve the bore slides on, the key pin pressed into its hole, the disc and its
    screws, the collar the stack sets."""
    cited_mates = {
        _config.parts(stem)["number"]
        for stem in (
            "pd-transgear-feed-pinion",
            "pd-vn-transgear-disc-screw",
            "pd-vn-transgear-hub-key-pin",
            "pd-rack-pinion",
            "pd-transgear-drive-collar",
        )
    }
    printed = " ".join(_sheet_text().split())
    cited = re.findall(r"MHA-(?!VN-)[A-Z]{2}-(?:[0-9]{2}(?:-TL-(?:[0-9]{2}|VN-[5-9][0-9]))?|VN-[5-9][0-9])(?:-T[0-9]{3})?(?![A-Z0-9-])", printed)
    assert set(cited) == cited_mates
    assert spec.KEY_PIN_NUMBER in spec.KEY_PIN_CALLOUT_BELOW


def test_walls_hold_at_the_worst_case_the_sheet_prints() -> None:
    """drawing-guidelines.md rule 17 (walls and webs), recomputed from the title block's rows."""
    hub_wall = (
        (spec.HUB_DIA - _row(_places("HubDia"))) - (spec.BORE_DIA + spec.BORE_BAND[0])
    ) / 2.0
    oil_r = (spec.OIL_HOLE_DIA + DRILL_PLUS) / 2.0
    pin_hole_r = (spec.KEY_PIN_HOLE_DIA + spec.KEY_PIN_HOLE_BAND[0]) / 2.0
    # The key-pin hole and the oil hole share one axis at the printed
    # station, on the shortest hub body the printed overall, the printed
    # spigot and the printed flange leave: each keeps its ligament to the hub
    # front face and to the flange face.
    body_min = (
        spec.HUB_LENGTH
        - FIT_LENGTH_BAND_IN
        - (spec.SPIGOT_LENGTH + FIT_LENGTH_BAND_IN)
        - (spec.FLANGE_THICK + _row(_places("FlangeThick")))
    )
    station = (
        spec.KEY_PIN_STATION - _row(_places("KeyPinStation")),
        spec.KEY_PIN_STATION + _row(_places("KeyPinStation")),
    )
    oil_ligament = min(station[0], body_min - station[1]) - oil_r
    pin_ligament = min(station[0], body_min - station[1]) - pin_hole_r
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
        # Finished: the rim's and the hole mouth's .010 breaks (Codjiflo, #2124).
        - 2.0 * 0.010 * IN
    )

    assert oil_ligament == pytest.approx(2.807, abs=0.005)
    assert oil_ligament == pytest.approx(spec.OIL_HOLE_LIGAMENT_WORST)
    assert pin_ligament == pytest.approx(0.103 * IN, abs=0.005)
    assert hole_to_rim == pytest.approx(2.146, abs=0.005)
    for wall in (
        hub_wall,
        oil_ligament,
        pin_ligament,
        hole_to_bore,
        hole_to_rim,
        spigot_wall,
    ):
        assert wall >= WALL_FLOOR - 1e-9
    assert spec.SPIGOT_WALL_WORST == pytest.approx(spigot_wall, abs=1e-9)
    assert spec.HUB_WALL_WORST == pytest.approx(hub_wall, abs=1e-9)
    assert spec.OIL_HOLE_LIGAMENT_WORST == pytest.approx(oil_ligament, abs=1e-9)
    assert spec.KEY_PIN_LIGAMENT_WORST == pytest.approx(pin_ligament, abs=1e-9)
    assert spec.HOLE_TO_RIM_WORST == pytest.approx(hole_to_rim, abs=1e-9)


def test_finished_walls_over_the_bore_pay_both_end_breaks() -> None:
    """#2168 (Codjiflo on #2124): at the hub front face and at the spigot's
    end the wall over the round bore also loses the OD's and the bore
    mouth's .010 breaks: the Ø.540 body .1105 -> .0905, back over the target,
    the spigot .0931 -> .0731, over the .060 floor (the bore and the spigot
    are the cluster's fits).  The bore's callout states the least (rule
    20)."""
    breaks = 2.0 * 0.010 * IN
    finished = spec.BORE_WALLS_FINISHED
    assert finished == pytest.approx(
        {
            "hub wall over the bore": spec.HUB_WALL_WORST - breaks,
            "spigot wall over the bore": spec.SPIGOT_WALL_WORST - breaks,
        }
    )
    assert finished["hub wall over the bore"] == pytest.approx(0.0905 * IN, abs=1e-3)
    assert finished["hub wall over the bore"] >= WALL_FLOOR
    spigot = finished["spigot wall over the bore"]
    assert spigot == pytest.approx(0.0715 * IN, abs=1e-3)
    assert 0.060 * IN - 1e-9 <= spigot < WALL_FLOOR
    assert not hasattr(spec, "FLAT_WALL_FINISHED")
    assert spec.BORE_WALL_TEXT == "WALL .071 MIN"
    assert drawing.DIMENSION_CALLOUTS_BELOW["BoreDia"].split("\n")[-1] == (
        spec.BORE_WALL_TEXT
    )


def test_the_package_declares_the_bore_wall_the_callout_prints() -> None:
    """#2168: Main's delegated minor (option A, the geometry kept) names the
    generated wall line the bore callout prints last (rule 20)."""
    exceptions = _config.parts("pd-transgear-disc-hub")["machinist_exceptions"]
    (entry,) = [entry for entry in exceptions if entry["id"] == "RV-02"]
    assert entry["kind"] == "minor"
    assert spec.BORE_WALL_TEXT in entry["where"]
    assert entry["reason"].startswith("Owner ruling 2026-11-08 (Pedro)")
    assert "#2144" in entry["reason"]
    assert drawing.DIMENSION_CALLOUTS_BELOW["BoreDia"].split("\n")[-1] == (
        spec.BORE_WALL_TEXT
    )


def test_screw_heads_keep_a_millimetre_of_air_to_the_hub_body() -> None:
    head = spec.SCREW_HEAD_DIA + spec.SCREW_HEAD_DIA_ALLOWANCE
    bc_r_min = joint.BOLT_CIRCLE_DIA / 2.0 - joint.BOLT_CIRCLE_POSITION_TOL
    clearance = bc_r_min - head / 2.0 - (spec.HUB_DIA + _row(_places("HubDia"))) / 2.0
    assert clearance >= 1.0
    assert spec.HEAD_TO_HUB_WORST == pytest.approx(clearance, abs=1e-9)


def test_retained_outer_envelope_keeps_wall_driver_air_and_screw_margins() -> None:
    """The smaller sleeve-matched bore does not resize the R9-68 envelope:
    the spigot retains its diameter; the hub body is Ø.540 (.XXX, the title
    block's +/-.005), which holds the .060 floor over the key pin's chord
    ream where Ø.530 would not (#2409 rounds 3-4); the
    flange is the smallest .XX size whose screw holes keep the wall to its
    rim with the flange and the circle both at .XX (machinist review: no
    .XXX held only to rescue that wall)."""
    import pd_rack_pinion_spec as disc

    assert spec.HUB_DIA == pytest.approx(0.540 * IN)
    ream_out = spec.KEY_PIN_CHORD_RANGE[1] + (
        spec.KEY_PIN_HOLE_DIA + spec.KEY_PIN_HOLE_BAND[0]
    ) / 2.0
    for hub_dia, holds in ((spec.HUB_DIA, True), (spec.HUB_DIA - 0.01 * IN, False)):
        chord_wall = (hub_dia - _row(_places("HubDia"))) / 2.0 - ream_out
        assert (chord_wall >= 0.060 * IN - 1e-9) is holds, hub_dia
    assert spec.SPIGOT_DIA == pytest.approx(0.498 * IN)
    assert spec.FLANGE_DIA == pytest.approx(1.05 * IN)
    assert joint.BOLT_CIRCLE_DIA == pytest.approx(0.75 * IN)
    round_wall = spec.body_wall_worst(spec.HUB_DIA)
    assert min(round_wall, spec.SPIGOT_WALL_WORST) >= spec.WALL_FLOOR
    bc = joint.BOLT_CIRCLE_DIA
    assert spec.head_air_worst(bc, spec.HUB_DIA) >= spec.HEAD_AIR_MIN
    assert disc.TAP_TO_BORE_WALL_WORST >= disc.WALL_FLOOR
    assert spec.head_air_worst(16.4, 12.4) < spec.HEAD_AIR_MIN
    assert spec.hole_to_rim_worst(spec.FLANGE_DIA, bc) >= spec.WALL_FLOOR
    assert spec.hole_to_rim_worst(spec.FLANGE_DIA - 0.01 * IN, bc) < spec.WALL_FLOOR
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
    monkeypatch.setattr(
        _printed_tolerance, "printed_band_mm", lambda _places, **_unit: 1.0
    )
    with pytest.raises(AssertionError, match="floor"):
        _spec_fresh()


def test_the_oil_hole_is_on_the_key_pin_axis_and_clears_both_body_ends() -> None:
    """R9-8: #57 (.043) on the drilled row, match-drilled through hub and
    sleeve with the hub seated, opposite the key pin on its printed .XX
    station behind the hub front face; that band and the printed lengths'
    leave both body ends."""
    assert spec.OIL_HOLE_DIA == pytest.approx(0.043 * IN)
    assert not hasattr(spec, "OIL_HOLE_STATION")
    body = (
        spec.HUB_LENGTH
        - FIT_LENGTH_BAND_IN
        - (spec.SPIGOT_LENGTH + FIT_LENGTH_BAND_IN)
        - (spec.FLANGE_THICK + _row(_places("FlangeThick"))),
        spec.HUB_LENGTH
        + FIT_LENGTH_BAND_IN
        - (spec.SPIGOT_LENGTH - FIT_LENGTH_BAND_IN)
        - (spec.FLANGE_THICK - _row(_places("FlangeThick"))),
    )
    assert spec.HUB_BODY_LENGTH_RANGE == pytest.approx(body)
    band = _row(_places("KeyPinStation"))
    assert spec.KEY_PIN_STATION_RANGE == pytest.approx(
        (spec.KEY_PIN_STATION - band, spec.KEY_PIN_STATION + band)
    )
    oil_r = (spec.OIL_HOLE_DIA + DRILL_PLUS) / 2.0
    assert spec.KEY_PIN_STATION_RANGE[0] - oil_r >= WALL_FLOOR
    assert body[0] - spec.KEY_PIN_STATION_RANGE[1] - oil_r >= WALL_FLOOR
    # The sleeve drills the same hole: the spigot's end on the step, the
    # hole the key pin's station behind the hub front face, over the flat.
    sleeve = cluster_fit.SLEEVE
    assert spec.OIL_HOLE_SLEEVE_Z == pytest.approx(
        sleeve.FACE_WIDTH + spec.HUB_LENGTH - spec.KEY_PIN_STATION
    )
    assert sleeve.FLAT_END_STATION < spec.OIL_HOLE_SLEEVE_Z < sleeve.OVERALL_LENGTH
    # Its ligament to the nose holds the sleeve's 2.0 target with the hub
    # front face at its least recess behind the nose.
    nose_worst = (
        cluster_fit.RECESS_RANGE[0]
        + spec.KEY_PIN_STATION_RANGE[0]
        - (spec.OIL_HOLE_DIA + DRILL_PLUS) / 2.0
    )
    assert nose_worst >= sleeve.WALL_TARGET
    assert spec.OIL_HOLE_TO_NOSE_WORST == pytest.approx(nose_worst)


def test_sheet_text_states_facts_not_governance() -> None:
    for word in ("EXCEPTION", "ACCEPTED", "RULING", "POLICY", "BOOK FIDELITY"):
        assert word not in _sheet_text().upper()
    assert not hasattr(spec, "DRAWING_NOTES")


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
    "BoltCircleDia": joint.BOLT_CIRCLE_DIA,
    "ScrewHoleDia": spec.SCREW_HOLE_DIA,
    "OilHoleDia": spec.OIL_HOLE_DIA,
    "KeyPinStation": spec.KEY_PIN_STATION,
    "KeyPinDia": spec.KEY_PIN_HOLE_DIA,
    "KeyPinDrillDia": spec.KEY_PIN_DRILL_DIA,
    "KeyPinChord": spec.KEY_PIN_CHORD_OFFSET,
    "KeyPinStop": spec.KEY_PIN_STOP,
}
# The bore's and the spigot's native bands print beside their values.
_BANDS = {
    "BoreDia": spec.BORE_BAND,
    "SpigotDia": spec.SPIGOT_DIA_BAND,
    "KeyPinDia": spec.KEY_PIN_HOLE_BAND,
}
# The disc cluster stack's printed lengths and the chord hole's locations
# carry their symmetric band.
_SYMMETRIC = {
    "HubLength": spec.HUB_LENGTH_BAND,
    "SpigotLength": spec.SPIGOT_LENGTH_BAND,
    "KeyPinChord": spec.KEY_PIN_LOCATION_BAND,
    "KeyPinStop": spec.KEY_PIN_LOCATION_BAND,
}


def _printed_box(name: str, anchor: tuple[float, float]) -> Box:
    """The estimated box of a kept dimension's whole text, centred on its
    text point: value (the bore's with its upper limit) and callouts."""
    value = f"{_NOMINAL[name] / IN:.{_places(name)}f}".lstrip("0")
    if name.endswith("Dia"):
        value = f"\u00d8{value}"
    if name in _BANDS:
        value += f" +{_BANDS[name][0] / IN:.4f}".replace("0.", ".", 1)
    if name in _SYMMETRIC:
        value += f"\u00b1{_SYMMETRIC[name] / IN:.{_places(name)}f}".replace("0.", ".", 1)
    lines = [
        drawing.DIMENSION_CALLOUTS_ABOVE.get(name),
        value,
        drawing.DIMENSION_CALLOUTS_BELOW.get(name)
        or drawing.SECTION_CALLOUTS_BELOW.get(name),
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
    """drawing-guidelines.md rule 11 (turned parts read like the lathe): the turned diameters sit on the edge view, not leader-
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
    # The oil hole's size stands below-left of the hole, under the part, its
    # block ending left of the hole, so its leader rises almost straight to
    # the hole from the block's lower-right corner, inside the hub body's
    # length, crossing no dimension line.  The flange thickness and its
    # function stand below the part wholly right of the flange's extension
    # lines.  The key-pin station shares the spigot's row above; the
    # overall stands a row above those, its text right of the spigot's end.
    hole_x = drawing._KEY_PIN_X
    assert hole_x == pytest.approx(drawing._side_x(spec.KEY_PIN_Z))
    shoulder = drawing._OIL_HOLE_SHOULDER
    assert boxes["OilHoleDia"].ymax < edge.ymin
    assert boxes["OilHoleDia"].xmax <= shoulder[0] + 1e-9 < hole_x
    hub_bottom = axis_y - spec.HUB_DIA / 2.0 * s
    t = (hub_bottom - shoulder[1]) / (axis_y - shoulder[1])
    crossing_x = shoulder[0] + t * (hole_x - shoulder[0])
    assert drawing.HUB_FRONT_X + 0.002 < crossing_x < drawing._side_x(-spec.FLANGE_THICK)
    assert boxes["FlangeThick"].xmin > drawing._side_x(0.0) + 0.002
    assert boxes["FlangeThick"].ymax < edge.ymin
    assert boxes["HubLength"].ymin > boxes["SpigotLength"].ymax
    assert boxes["HubLength"].xmin > drawing.SPIGOT_END_X
    assert drawing.SIDE_KEEP["KeyPinStation"][1] == drawing.SIDE_KEEP["SpigotLength"][1]
    # The spigot's text and callout end clear of the flange's dimension line.
    assert boxes["SpigotDia"].xmax < drawing.SIDE_KEEP["FlangeDia"][0] - 0.004
    clashes = [
        (a, b)
        for a, b in itertools.combinations(sorted(boxes), 2)
        if boxes[a].overlaps(boxes[b], tol=0.0)
    ]
    assert clashes == []


def test_section_a_a_cuts_across_the_chord_hole_at_its_station() -> None:
    """drawing-guidelines.md rule 9: the chord hole runs through the wall
    into the bore, internal shape, so SECTION A-A draws it in solid lines.
    Its cutting plane is the hole profile's station plane, through the hub
    body only (clear of the flange), drawn across the edge view at the
    station and past the O.D. each side, so the cut closes and each letter
    stands off the hub."""
    (x0, y0, z0), (x1, y1, z1) = drawing.SECTION_LINE_MODEL
    assert y0 == y1 == 0.0
    assert z0 == z1 == spec.KEY_PIN_Z
    hub_r = spec.HUB_DIA / 2.0
    assert x0 < -hub_r < hub_r < x1
    hole_r = spec.KEY_PIN_HOLE_DIA / 2.0
    assert spec.HUB_FRONT_Z < spec.KEY_PIN_Z - hole_r
    assert spec.KEY_PIN_Z + hole_r < -spec.FLANGE_THICK
    # On the edge view (model -Z left, +X up) the plane is the vertical at
    # the station; drawn bottom to top, its arrows point right, the sight
    # along +Z.
    assert drawing.SIDE_VIEW_ANGLE == pytest.approx(math.pi / 2.0)
    (sx0, sy0), (sx1, sy1) = drawing.SECTION_LINE
    assert sx0 == sx1 == pytest.approx(drawing._KEY_PIN_X)
    s = drawing._S
    assert sy0 < drawing.AXIS_Y - hub_r * s - 0.005
    assert sy1 > drawing.AXIS_Y + hub_r * s + 0.005
    # Laid with model +X up and +Y right, the chord hole on the left and its
    # ream entering from the top.
    xy = drawing._section_xy
    assert xy(0.0, -spec.KEY_PIN_CHORD_OFFSET)[0] < drawing.SECTION_CENTER[0]
    assert xy(hub_r, 0.0)[1] > xy(spec.KEY_PIN_STOP_X, 0.0)[1]
    # The oil hole's leader leans off the cutting line it shares a station
    # with.
    assert drawing._OIL_HOLE_SHOULDER[0] <= drawing._KEY_PIN_X - 0.005


# The r6 layout audit's native readback of A-A's lower arrow and letter
# (IDrSection.GetArrowInfo tail, GetTextInfo upper-left origin, CharHeight).
_R6_LOWER_TAIL = (0.2158941, 0.138426)
_R6_LOWER_LETTER_ORIGIN = (0.2328981, 0.1403323)
_R6_LETTER_HEIGHT = 0.00635
# Ink near the letters outside the recipe's constants (r6 layout audit): the
# overall's dimension line, the spigot length's, the flange thickness's
# (with its outside arrow's tail), and the key-pin station's text.
_OVERALL_LINE = Box(0.2045, 0.2254, 0.3138, 0.2254)
_SPIGOT_LENGTH_LINE = Box(0.2346, 0.2084, 0.2838, 0.2084)
_FLANGE_THICK_LINE = Box(0.2211, 0.1027, 0.2875, 0.1027)
_STATION_TEXT = Box(0.2057, 0.2112, 0.2057 + 0.0090514, 0.2112 + 0.0035)


def test_section_letters_stand_clear_of_the_flange_and_its_dimensions() -> None:
    """r6 machinist review (rule 14): both cutting-plane letters stood on the
    flange's rear-face line.  SolidWorks prints each letter just past its
    arrow's tip, in the column of the rear face and the extension lines off
    it, so the cutting line runs on until each letter clears that ink: the
    upper under the overall's line, the lower under the flange thickness's
    extension lines, neither on another dimension or text."""
    # The letter model reproduces the r6 readback, where the letter struck
    # the rear face (the positive control).
    r6 = drawing.section_letter_box(_R6_LOWER_TAIL)
    assert (r6.xmin, r6.ymax) == pytest.approx(_R6_LOWER_LETTER_ORIGIN, abs=1e-5)
    assert drawing.SECTION_LETTER_HEIGHT == pytest.approx(_R6_LETTER_HEIGHT)
    flange, rear_face_ink = drawing.flange_ink_boxes()
    assert r6.gap(rear_face_ink) == 0.0
    air = drawing.SECTION_LETTER_AIR
    lower, upper = (drawing.section_letter_box(end) for end in drawing.SECTION_LINE)
    neighbours = (_OVERALL_LINE, _SPIGOT_LENGTH_LINE, _FLANGE_THICK_LINE, _STATION_TEXT)
    kept = [
        _printed_box(name, anchor)
        for keep in (drawing.END_KEEP, drawing.SIDE_KEEP)
        for name, anchor in keep.items()
    ]
    for letter in (lower, upper):
        assert letter.gap(flange) >= air - 1e-9, letter
        assert letter.gap(rear_face_ink) >= air - 1e-9, letter
        for box in (*neighbours, *kept):
            assert letter.gap(box) >= 0.003, (letter, box)
    assert lower.ymax < flange.ymin < flange.ymax < upper.ymin
    assert upper.ymax < _OVERALL_LINE.ymin
    title_top = DRAWING_TEMPLATES[drawing.SPEC.layout].title_block_top_m
    assert lower.ymin >= title_top + 0.005
    # The cutting line itself runs clear of the station's text beside it.
    (cut_x, cut_low), (_x, cut_high) = drawing.SECTION_LINE
    assert Box(cut_x, cut_low, cut_x, cut_high).gap(_STATION_TEXT) >= 0.001


def _drawn_section(arrow_tails, letter_origins, height):
    arrows = tuple(
        value
        for x, y in arrow_tails
        for value in (x, y, 0.0, x + drawing.SECTION_ARROW_LENGTH, y, 0.0)
    )
    texts = tuple(value for x, y in letter_origins for value in (x, y, 0.0))
    cut = SimpleNamespace(
        GetArrowInfo=lambda: arrows,
        GetTextInfo=lambda: texts,
        GetTextFormat=lambda: SimpleNamespace(CharHeight=height),
    )
    return SimpleNamespace(GetSection=lambda: cut)


def test_the_build_reads_each_letter_back_clear_of_the_flange(monkeypatch) -> None:
    """The build reads A-A's arrows and letters back and fails unless each
    letter printed where the recipe's letter model puts it, clear of the
    flange's ink: the r6 placement fails, the planned one passes."""
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    tails = drawing.SECTION_LINE
    planned = [
        (box.xmin, box.ymax) for box in map(drawing.section_letter_box, tails)
    ]
    drawing._assert_section_letters_clear(
        _drawn_section(tails, planned, drawing.SECTION_LETTER_HEIGHT)
    )
    r6_tails = (_R6_LOWER_TAIL, (_R6_LOWER_TAIL[0], 0.191574))
    r6_letters = [
        (box.xmin, box.ymax) for box in map(drawing.section_letter_box, r6_tails)
    ]
    with pytest.raises(RuntimeError, match="meets the flange's ink"):
        drawing._assert_section_letters_clear(
            _drawn_section(r6_tails, r6_letters, drawing.SECTION_LETTER_HEIGHT)
        )
    moved = [(x + 0.002, y) for x, y in planned]
    with pytest.raises(RuntimeError, match="printed at"):
        drawing._assert_section_letters_clear(
            _drawn_section(tails, moved, drawing.SECTION_LETTER_HEIGHT)
        )


def test_the_chord_hole_dimensions_print_left_of_the_ring() -> None:
    """The ream's size and fit (two lines of words naming the pin, rules 4
    and 7) and the knockout's stand left of the ring, each dimension line at
    its text's height crossing its own run of the hole; the stop's text
    stands inline between the hub axis's and the stop's extension lines, the
    chord's above the ring right of the axis's extension line."""
    callout = drawing.SECTION_CALLOUTS_BELOW["KeyPinDia"]
    assert spec.KEY_PIN_NUMBER in callout
    assert len(callout.splitlines()) <= 2
    assert len(drawing.SECTION_CALLOUTS_BELOW["KeyPinDrillDia"].splitlines()) <= 2
    assert set(drawing.SECTION_CALLOUTS_BELOW) == {"KeyPinDia", "KeyPinDrillDia"}
    xy = drawing._section_xy
    s = drawing._S
    centre = drawing.SECTION_CENTER
    ring_left = centre[0] - spec.HUB_DIA / 2.0 * s
    ring_top = centre[1] + spec.HUB_DIA / 2.0 * s
    stop_y = xy(spec.KEY_PIN_STOP_X, 0.0)[1]
    reach = drawing._SECTION_REACH_MM
    keep = drawing.SECTION_KEEP
    boxes = {name: _printed_box(name, anchor) for name, anchor in keep.items()}
    # The ream's line crosses the ream, the knockout's the knockout.
    assert stop_y < keep["KeyPinDia"][1] < xy(reach, 0.0)[1]
    assert xy(-reach, 0.0)[1] < keep["KeyPinDrillDia"][1] < stop_y
    # The stop's text between its extension lines, left of the ring.
    assert stop_y < keep["KeyPinStop"][1] < centre[1]
    assert boxes["KeyPinStop"].xmax <= ring_left - 0.002
    # Both sizes left of the ring, clear of it.
    for name in ("KeyPinDia", "KeyPinDrillDia"):
        assert boxes[name].xmax <= ring_left - 0.010, name
    # The chord above the ring, right of the hub axis's extension line.
    assert boxes["KeyPinChord"].ymin >= ring_top + 0.002
    assert boxes["KeyPinChord"].xmin >= centre[0] + 0.002
    clashes = [
        (a, b)
        for a, b in itertools.combinations(sorted(boxes), 2)
        if boxes[a].overlaps(boxes[b], tol=0.001)
    ]
    assert clashes == []


# Ink outside the recipe's own constants, measured on the r4 render (run
# 20261107T180459203Z): the isometric's shaded ink and the end of the
# Ø1.05's lower extension line.
_ISO_INK = Box(0.335, 0.147, 0.408, 0.224)
_FLANGE_DIA_EXTENSION_END = (0.3355, 0.1248)
_INNER_BORDER = Box(0.0127, 0.0127, 0.4191, 0.2667)
# The native section caption's "SECTION" caps, 5.1 mm on the feed pinion's
# B-B (run 20261107T121559938Z), its 11 characters 44 mm wide.
_CAPTION_CAP_M = 0.0055


def test_section_a_a_stands_in_the_free_field_clear_of_every_other_ink() -> None:
    """The removed section, the chord hole's dimensions and the caption stand
    right of the edge view's Ø1.05, under the isometric and over the title
    block, inside the border, clear of every edge- and face-view text; the
    caption under the centrelines' lowest end."""
    s = drawing._S
    centre = drawing.SECTION_CENTER
    reach = drawing._SECTION_REACH_MM * s
    hub_r = spec.HUB_DIA / 2.0 * s
    ring = Box(centre[0] - hub_r, centre[1] - hub_r, centre[0] + hub_r, centre[1] + hub_r)
    centrelines = Box(
        centre[0] - reach, centre[1] - reach, centre[0] + reach, centre[1] + reach
    )
    texts = {
        name: _printed_box(name, anchor)
        for name, anchor in drawing.SECTION_KEEP.items()
    }
    caption = estimate_text_box(
        "SECTION A-A",
        anchor=drawing.SECTION_CAPTION_XY,
        height=_CAPTION_CAP_M,
        reference=5,
        advance_ratio=_ADVANCE,
    )
    assert caption is not None
    section_ink = [ring, centrelines, caption, *texts.values()]
    title_top = DRAWING_TEMPLATES[drawing.SPEC.layout].title_block_top_m
    for box in section_ink:
        assert box.xmin >= _INNER_BORDER.xmin + 0.003, box
        assert box.xmax <= _INNER_BORDER.xmax - 0.003, box
        assert box.ymin >= title_top + 0.003, box
        assert box.gap(_ISO_INK) >= 0.010, box
        if box.xmin < _FLANGE_DIA_EXTENSION_END[0]:
            assert box.ymax <= _FLANGE_DIA_EXTENSION_END[1] - 0.005, box
    kept = {
        name: _printed_box(name, anchor)
        for keep in (drawing.END_KEEP, drawing.SIDE_KEEP)
        for name, anchor in keep.items()
    }
    for name, box in kept.items():
        for ink in section_ink:
            assert box.gap(ink) >= 0.005, (name, ink)
    for name, box in texts.items():
        assert caption.gap(box) >= 0.003, name
    assert caption.gap(ring) >= 0.003
    assert caption.ymax < centrelines.ymin


def test_section_centrelines_end_past_the_ring_clear_of_every_text() -> None:
    """Machinist review r5 (rule 14): the horizontal centreline ran through
    the ream callout's last line and the stop's text, the vertical through
    the caption into the isometric.  Each drawn line ends 1 mm past the O.D.
    and strikes no section text, the caption, the isometric or the title block."""
    s = drawing._S
    xy = drawing._section_xy
    ring_r = spec.HUB_DIA / 2.0 * s
    lines = []
    for start, end in drawing.SECTION_CENTERLINES_MODEL:
        (x0, y0), (x1, y1) = xy(*start), xy(*end)
        lines.append(Box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))
    centre = drawing.SECTION_CENTER
    overrun = drawing.SECTION_CENTERLINE_OVERRUN_MM * s
    for line in lines:
        # Each line is horizontal or vertical: its offset from the centre
        # across it, and its half-length along it past where it meets the O.D.
        vertical = line.xmax - line.xmin < 1e-12
        offset = line.xmin - centre[0] if vertical else line.ymin - centre[1]
        lo, hi = (line.ymin, line.ymax) if vertical else (line.xmin, line.xmax)
        mid = centre[1] if vertical else centre[0]
        crossing = math.sqrt(ring_r**2 - offset**2)
        for half in (mid - lo, hi - mid):
            assert half - crossing == pytest.approx(overrun), line
    texts = {
        name: _printed_box(name, anchor)
        for name, anchor in drawing.SECTION_KEEP.items()
    }
    caption = estimate_text_box(
        "SECTION A-A",
        anchor=drawing.SECTION_CAPTION_XY,
        height=_CAPTION_CAP_M,
        reference=5,
        advance_ratio=_ADVANCE,
    )
    assert caption is not None
    title_top = DRAWING_TEMPLATES[drawing.SPEC.layout].title_block_top_m
    for line in lines:
        for name, box in (*texts.items(), ("caption", caption)):
            assert line.gap(box) >= 0.002, (name, line)
        assert line.gap(_ISO_INK) >= 0.010, line
        assert line.ymin >= title_top + 0.003, line


def _centre_mark_section(marks: list, deletes: bool):
    """A section holding ``marks`` and a drawing whose EditDelete drops the
    selected ones (or, ``deletes=False``, silently keeps them)."""
    events: list = []
    selected: list = []

    def select(mark):
        def _select(append, _data):
            selected.append(mark)
            events.append(("select", append))
            return True

        return _select

    for mark in marks:
        mark.Select2 = select(mark)

    def edit_delete():
        events.append("delete")
        if deletes:
            for mark in selected:
                marks.remove(mark)

    draw = SimpleNamespace(
        ClearSelection2=lambda _all: selected.clear() or True,
        EditDelete=edit_delete,
    )
    view = SimpleNamespace(
        GetAnnotationsByType=lambda kind: (
            tuple(marks) if kind == drawing._CENTER_MARK_ANNOTATION else ()
        )
    )
    return SimpleNamespace(currentModel=draw), view, events


def test_section_a_a_loses_the_centre_marks_it_arrives_with(monkeypatch) -> None:
    """Machinist review r5: the section arrived centre-marked, the mark's
    arms printed far past the ring.  Every mark is deleted in one selection
    and read back gone; a section with none is left alone; a delete that
    does not land fails the build; the deletion runs before the drawn
    centrelines."""
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_k: None)
    marks = [SimpleNamespace(), SimpleNamespace()]
    adapter, view, events = _centre_mark_section(marks, deletes=True)
    drawing._delete_section_centre_marks(adapter, view)
    assert marks == []
    assert events == [("select", False), ("select", True), "delete"]
    adapter, view, events = _centre_mark_section([], deletes=True)
    drawing._delete_section_centre_marks(adapter, view)
    assert events == []
    adapter, view, _events = _centre_mark_section([SimpleNamespace()], deletes=False)
    with pytest.raises(RuntimeError, match="survived deletion"):
        drawing._delete_section_centre_marks(adapter, view)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    body = source[source.index("def _section_a_a(") :]
    assert body.index("_delete_section_centre_marks(") < body.index(
        "_add_section_centerlines("
    )


def test_the_hub_od_callout_states_the_wall_its_third_place_holds() -> None:
    """Machinist review r5 (rule 3): Ø.540 at three places, finer than the
    turned row, states its function under the size: the least wall over the
    key pin's chord ream, floored at three places (rule 20)."""
    callout = drawing.DIMENSION_CALLOUTS_BELOW["HubDia"].splitlines()
    assert _places("HubDia") == 3
    assert len(callout) <= 2
    printed = float(callout[0].split()[1])
    assert printed * IN <= spec.KEY_PIN_WALL_WORST + 1e-9
    assert spec.KEY_PIN_WALL_WORST - printed * IN < 0.001 * IN
    assert printed * IN >= spec.WALL_FLOOR_MM - 1e-9



@pytest.mark.parametrize(
    ("linked", "label_line"),
    [
        ("<VLNAME> <VLLABEL>\r\nSCALE <VLSCALE>", "<VLNAME> <VLLABEL>"),
        (
            "<VLNAME> <FONT size=3.5><VLLABEL>\r\n"
            "<VLSCALE><FONT size=6.35> <FONT size=3.5><VLSCALEV><FONT size=6.35>",
            "<VLNAME> <FONT size=3.5><VLLABEL>",
        ),
        ("<VLNAME> <VLLABEL>\r\nSCALE <VLSCALEV>\r\n", "<VLNAME> <VLLABEL>"),
    ],
)
def test_section_caption_drops_only_its_scale_line(linked, label_line) -> None:
    """Round 5 (rule 9): SECTION A-A is at the sheet's 3:1, so its caption
    keeps its label line and loses the scale line SolidWorks links."""
    assert drawing.VIEW_SCALE == tuple(int(v) for v in drawing.SHEET_SCALE)
    assert drawing.caption_without_scale(linked) == label_line


@pytest.mark.parametrize(
    "linked",
    ["<VLNAME> <VLLABEL> SCALE <VLSCALEV>", "<VLLABEL>\r\nSCALE <VLSCALEV>"],
)
def test_section_caption_of_unforeseen_form_is_left_alone(linked) -> None:
    assert drawing.caption_without_scale(linked) is None


class _CaptionNote:
    def __init__(self, linked: str) -> None:
        self.PropertyLinkedText = linked


class _SectionView:
    def __init__(self, notes, ratio=(3.0, 1.0)) -> None:
        self._notes = notes
        self.ScaleRatio = ratio

    def GetNotes(self):
        return self._notes


def test_section_caption_scale_is_removed_natively(monkeypatch) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _iface: value)
    rebuilds: list[str] = []
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda _a, *, label: rebuilds.append(label))
    caption = _CaptionNote("<VLNAME> <VLLABEL>\r\nSCALE <VLSCALEV>")
    other = _CaptionNote("")
    drawing._drop_sheet_scale_from_caption(None, _SectionView([other, caption]))
    assert caption.PropertyLinkedText == "<VLNAME> <VLLABEL>"
    assert other.PropertyLinkedText == ""
    assert len(rebuilds) == 1
    with pytest.raises(RuntimeError, match="not at the sheet scale"):
        drawing._drop_sheet_scale_from_caption(None, _SectionView([caption], (2.0, 1.0)))


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
        self.planes: dict[int, str] = {}

    async def _entity(self, *_args, **_kwargs) -> str:
        self._n += 1
        return f"Entity{self._n}"

    async def create_sketch(self, plane) -> str:
        self.sketch += 1
        self.planes[self.sketch] = plane
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
    turned profile on its printed sizes, the round bore on its size, the key
    pin's chord hole on its station plane, and its printed station and the
    oil hole opposite it at one station."""
    globals_mm: dict[str, float] = {}
    circles: list[tuple] = []
    chains: list[list[str]] = []
    diametric: dict[str, str] = {}
    rows: dict[int, list[tuple[str | None, str | None]]] = {}
    drives: dict[str, dict[str | None, str | None]] = {}
    driven: dict[str, str] = {}
    blanked: list[tuple[str, ...]] = []
    blanked_geometry: list[tuple[tuple[str, str], ...]] = []
    between: list[tuple[str, str, str, float]] = []

    async def dimension_between(_adapter, ref1, ref2, kind, value, _label):
        between.append((ref1, ref2, kind, value))

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
    monkeypatch.setattr(
        part, "blank_reference_sketches", lambda _a, sketches: blanked.append(sketches)
    )
    monkeypatch.setattr(
        part,
        "blank_reference_geometry",
        lambda _a, references: blanked_geometry.append(references),
    )
    # The station plane's sketch reads (u, v) = model (X, Y).
    monkeypatch.setattr(
        part,
        "_sketch_mapper",
        lambda _a, *, u_axis, v_axis, label: lambda point: (point[0], point[1]),
    )
    monkeypatch.setattr(part, "dimension_between", dimension_between)
    monkeypatch.setattr(part, "drive_dimension", drive_dimension)
    monkeypatch.setattr(part, "_early_bound", lambda obj, _iface: obj)
    for helper in (
        "volume_check",
        "bbox_extent_check",
        "ensure_fully_defined",
        "anchor_point_to_origin",
        "force_rebuild",
        "apply_material",
        "report_mass_properties",
        "save_part_and_images",
    ):
        monkeypatch.setattr(part, helper, quiet)
    for helper in (
        "apply_package_model_units",
        "name_last_feature",
        "set_sketch_direct_db",
        "_as_construction",
        "_check_z_span",
        "set_dimension_bilateral_tolerance",
        "set_dimension_symmetric_tolerance",
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
    profile, pin_hole = chains
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
    # The bore: one round circle on the axis, cut through the whole part.
    (bore,) = [c for c in circles if c[0] == "bore"]
    assert bore[1:4] == pytest.approx((0.0, 0.0, spec.BORE_DIA / 2.0))
    assert not fake.arcs

    # Oil hole: the station line runs from the hub front face to the hole's
    # centre, the key pin's station behind it.
    (station,) = fake.sketch_lines[4]
    _u0, front_v, _u1, hole_v = fake.lines[station]
    ((_cu, centre_v, oil_r),) = fake.circles
    assert centre_v == pytest.approx(hole_v)
    assert value("OilHoleProfile", "OilHoleDatum") == pytest.approx(front_v)
    assert value("OilHoleProfile", "OilHoleStation") == pytest.approx(front_v - hole_v)
    assert value("OilHoleProfile", "OilHoleStation") == pytest.approx(
        spec.KEY_PIN_STATION
    )
    assert value("OilHoleProfile", "OilHoleDia") == pytest.approx(2.0 * oil_r)
    # The one-wall cut runs a body's width deep.
    assert _drive_value(driven["OilHoleDepth@OilHole"], globals_mm) == spec.HUB_DIA

    # The key-pin station's hidden reference: a line on the +X O.D. from
    # the hub front face back to the hole's axis, blanked once drawn.
    (reference,) = fake.sketch_lines[5]
    ru0, rv0, ru1, rv1 = fake.lines[reference]
    assert ru0 == ru1 == pytest.approx(spec.HUB_DIA / 2.0)
    assert (rv0, rv1) == pytest.approx((-spec.HUB_FRONT_Z, -spec.KEY_PIN_Z))
    sketch = spec.REFERENCE_SKETCHES[0]
    for name, size in (
        ("KeyPinStation", rv0 - rv1),
        ("KeyPinStationAnchor1", ru0),
        ("KeyPinStationAnchor2", rv0),
    ):
        assert _drive_value(driven[f"{name}@{sketch}"], globals_mm) == pytest.approx(
            size
        ), name
    assert blanked == [spec.REFERENCE_SKETCHES]
    # The key pin's chord hole: on the hidden station plane, whose offset
    # drives from the printed station, a stepped half profile beside its
    # centreline at y = -chord, revolved: the ream from past the +X O.D. to
    # the stop, the knockout on past the -X O.D.  The chord, the stop and
    # both diameters drive from their globals.
    plane = "KeyPinStationPlane"
    assert fake.planes[6] == plane
    assert blanked_geometry == [((plane, "PLANE"),)]
    assert _drive_value(driven[f"KeyPinZ@{plane}"], globals_mm) == pytest.approx(
        -spec.KEY_PIN_Z
    )
    out_end, ream, stop, drill, in_end, _on_axis = pin_hole
    assert diametric["KeyPinDia"] == ream
    assert diametric["KeyPinDrillDia"] == drill
    out_x, axis_y, _ox, ream_y = fake.lines[out_end]
    _rx, _ry, stop_x, _ry1 = fake.lines[ream]
    _sx, _sy, _sx1, drill_y = fake.lines[stop]
    _dx, _dy, far_x, _dy1 = fake.lines[drill]
    assert fake.lines[in_end][3] == axis_y
    drawn_pin = {
        "KeyPinChord": -axis_y,
        "KeyPinStop": -stop_x,
        "KeyPinDia": 2.0 * (axis_y - ream_y),
        "KeyPinDrillDia": 2.0 * (axis_y - drill_y),
    }
    for name, size in drawn_pin.items():
        assert value("KeyPinProfile", name) == pytest.approx(size), name
    assert drawn_pin == pytest.approx(
        {
            "KeyPinChord": spec.KEY_PIN_CHORD_OFFSET,
            "KeyPinStop": spec.KEY_PIN_STOP,
            "KeyPinDia": spec.KEY_PIN_HOLE_DIA,
            "KeyPinDrillDia": spec.KEY_PIN_DRILL_DIA,
        }
    )
    assert out_x > spec.HUB_DIA / 2.0 and -far_x > spec.HUB_DIA / 2.0
    # The printed chord and stop run from the sketch origin, the hub axis.
    assert (f"{out_end}.start", "origin", "vertical_distance") in {
        row[:3] for row in between
    }
    assert (f"{stop}.start", "origin", "horizontal_distance") in {
        row[:3] for row in between
    }
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
    # centres and the bore's size.
    assert checked == 1 + 3 + 5 + 1


async def _async(value):
    return value


def test_registry_row_is_the_turned_brass_mha_159() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-PD-17"
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
    extra = ast.literal_eval(ast.unparse(stamp.args[2])) if len(stamp.args) > 2 else {}
    stamped: dict[str, str] = {}
    monkeypatch.setattr(
        _drawing_marks,
        "apply_custom_properties",
        lambda _adapter, props: stamped.update(props),
    )
    _drawing_marks.apply_drawing_properties(None, part.PART_NAME, extra)
    carried.update(stamped)
    assert [name for name in required if not str(carried.get(name) or "").strip()] == []


def test_seat_bound_takes_full_depth_to_the_step() -> None:
    """codjiflo P2 (0247213): the sleeve prints only the full depth's MIN and
    the run-out's MAX, so a smaller cutter may cut full depth to the step.
    The seat's lower bound is then the whole form gap at every step corner."""
    sleeve = spec.SLEEVE
    assert sleeve.FULL_DEPTH_MAX >= sleeve.FACE_WIDTH + sleeve.FACE_WIDTH_BAND
    full_gap = [
        sleeve.step_seat_area_bounds_mm2(
            spec.SEAT_INNER_R,
            spec.SEAT_CONTACT_R,
            profile=profile,
            station_mm=station,
            full_depth_mm=station,
        )[0]
        for profile in sleeve.manufactured_profiles()
        for station in (
            sleeve.FACE_WIDTH - sleeve.FACE_WIDTH_BAND,
            sleeve.FACE_WIDTH + sleeve.FACE_WIDTH_BAND,
        )
    ]
    assert spec.SEAT_CONTACT_AREA == min(full_gap)
    assert spec.SEAT_CONTACT_AREA > 0.0
