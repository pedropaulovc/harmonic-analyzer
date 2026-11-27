"""Offline contracts for the transgear disc hub (MHA-PD-17) and its drawing."""

from __future__ import annotations

import importlib.util
import itertools
import math
from pathlib import Path
import re

import pytest

import _config
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
import _drawing_edges
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DRAWING_TEMPLATES
from _layout_geometry import Box, estimate_text_box
import _printed_tolerance
import build_pd_transgear_disc_hub as part
import draw_pd_transgear_disc_hub as drawing
from machinist_exceptions import load_exceptions
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
    assert _places("KeyPinChord") == spec.KEY_PIN_LOCATION_PLACES == 3
    assert spec.REFERENCE_DIMENSIONS == frozenset({"SpigotDia"})
    assert {"HubLength", "SpigotLength", "KeyPinStation"} < set(drawing.SIDE_KEEP)
    assert set(drawing.SECTION_KEEP) == spec.DRAWING_DIMENSIONS["KeyPinProfile"]
    assert spec.HUB_LENGTH == cluster_fit.HUB_LENGTH == pytest.approx(0.539 * IN)
    assert _places("HubLength") == cluster_fit.LENGTH_PLACES == 3
    assert spec.FLANGE_THICK == pytest.approx(0.094 * IN) and _places("FlangeThick") == 3
    assert spec.SPIGOT_LENGTH == pytest.approx(0.144 * IN) and _places("SpigotLength") == 3
    # The bore prints the .3135 reamer's size; the sleeve's boss is turned to it.
    assert spec.BORE_DIA == pytest.approx(0.3135 * IN) and _places("BoreDia") == 4
    assert spec.DRAWING_DIMENSIONS["BoreProfile"] == {"BoreDia"}
    assert spec.HUB_DIA == pytest.approx(0.540 * IN) and _places("HubDia") == 3
    assert spec.SPIGOT_DIA == pytest.approx(0.498 * IN) and _places("SpigotDia") == 3
    assert spec.FLANGE_DIA == pytest.approx(1.05 * IN) and _places("FlangeDia") == 2
    assert joint.BOLT_CIRCLE_DIA == pytest.approx(0.75 * IN)
    assert joint.BOLT_CIRCLE_PLACES == 2
    assert spec.HUB_BODY_LENGTH == pytest.approx(0.301 * IN)


def test_the_overall_and_the_spigot_are_terms_of_the_disc_cluster_stack() -> None:
    """#2124: the overall sets the recess, so it prints +/-.001 natively,
    named on the stack.  The spigot's length, the stack's other term on this
    sheet, prints at the title block's .XXX row with no band of its own
    (delegated ruling D21, 2026-11-25), and links the stack's note: its
    third place is the collar air's (rule 3), below."""
    assert spec.HUB_LENGTH_BAND == cluster_fit.LENGTH_BAND == FIT_LENGTH_BAND_IN
    title_block = _row(_places("SpigotLength"))
    assert title_block == pytest.approx(0.005 * IN)
    assert joint.SPIGOT_LENGTH_BAND == spec.SPIGOT_LENGTH_BAND == title_block
    assert cluster_fit.SP == ("MHA-PD-17 spigot length", spec.SPIGOT_LENGTH, title_block)
    assert (spec.HUB_LENGTH_MIN, spec.HUB_LENGTH_MAX) == pytest.approx(
        (spec.HUB_LENGTH - FIT_LENGTH_BAND_IN, spec.HUB_LENGTH + FIT_LENGTH_BAND_IN)
    )
    assert (spec.SPIGOT_LENGTH_MIN, spec.SPIGOT_LENGTH_MAX) == pytest.approx(
        (spec.SPIGOT_LENGTH - title_block, spec.SPIGOT_LENGTH + title_block)
    )
    assert "HubLength" not in spec.REFERENCE_DIMENSIONS
    assert "SpigotLength" not in spec.REFERENCE_DIMENSIONS
    callouts = drawing.DIMENSION_CALLOUTS_BELOW
    assert callouts["HubLength"] == callouts["SpigotLength"] == (
        f"SEE NOTE {spec.STACK_NOTE}"
    )
    assert "SpigotLength" not in drawing.DIMENSION_CALLOUTS_ABOVE
    assert "SpigotLength" not in drawing._PLUS_MINUS
    assert STACK_NAME in spec.STACK_TEXT
    # The note the third place points to names both parts of the air.
    assert spec.COLLAR_NUMBER in spec.STACK_TEXT and spec.DISC_NUMBER in spec.STACK_TEXT


def test_the_spigot_length_third_place_holds_the_collar_air(monkeypatch) -> None:
    """Rule 3: a three-place length with no band needs a function.  At the
    title block's .XXX row the statistical collar air
    (pd_cluster_air.COLLAR_AIR, its 'MHA-PD-17 spigot length' term the band
    itself) clears its floor; at the .XX row it closes under it, and the
    check that guards it (pd_cluster_air.require_air, run by the paper-drive
    assembly's spec) refuses that stack."""
    import build_pd_paper_drive_assembly as assembly
    import pd_cluster_air as air

    label = cluster_fit.SP[0]
    assert air.COLLAR_AIR.terms[label] == pytest.approx(_row(3))
    assert air.COLLAR_AIR.statistical_mm == pytest.approx(0.1366, abs=5e-5)
    assert air.COLLAR_AIR.statistical_mm >= air.COLLAR_AIR_MIN == pytest.approx(0.1016)
    assert assembly.CLUSTER_AIRS["method"] == "statistical"
    assert assembly.CLUSTER_AIRS["collar_air"] == pytest.approx(
        air.COLLAR_AIR.statistical_mm
    )
    two_place = air.AirStack(
        air.COLLAR_AIR.name,
        air.COLLAR_AIR.nominal_mm,
        {**air.COLLAR_AIR.terms, label: _row(2)},
        air.COLLAR_AIR_MIN,
    )
    assert two_place.statistical_mm == pytest.approx(0.0311, abs=5e-5)
    assert two_place.statistical_mm < air.COLLAR_AIR_MIN
    # Negative control: the guard refuses the .XX stack.
    monkeypatch.setattr(air, "COLLAR_AIR", two_place)
    with pytest.raises(AssertionError, match="collar to MHA-PD-06 disc air"):
        air.require_air(assembly.PLATEN_AIR)


def test_the_overall_and_the_chord_carry_model_bands() -> None:
    """Every other size is governed by its printed places and the holes by
    the title block's DRILLED HOLES row.  The two reamed holes (the bore and
    the key pin's) print their reamers' sizes and no band (rule 4, fit audit
    2026-11-23): their mates are their gauges.  The spigot, made to the
    disc's bore, prints REF with no band, its length and the ream's stop
    take the title block's row."""
    assert model_toleranced_dimensions(part) == {
        ("HubProfile", "HubLength"): "HUB_LENGTH_BAND",
        ("KeyPinProfile", "KeyPinChord"): "KEY_PIN_CHORD_BAND",
    }
    assert not hasattr(part, "SPIGOT_LENGTH_BAND")
    assert not hasattr(spec, "SPIGOT_DIA_DEVIATIONS")
    assert not hasattr(spec, "KEY_PIN_LOCATION_BAND")
    for name in ("BORE_DEVIATIONS", "KEY_PIN_HOLE_DEVIATIONS"):
        assert not hasattr(spec, name) and not hasattr(part, name)


def _printed_limits(build, spec_module, feature: str, name: str, nominal: float):
    """(least, greatest) size the sheet prints: the model band the build
    applies, else the title block's row for the dimension's places."""
    expr = model_toleranced_dimensions(build).get((feature, name))
    if expr is None:
        row = _row(spec_module.DRAWING_PRECISION_BY_NAME[name])
        return nominal - row, nominal + row
    lower, upper = getattr(build, expr.lstrip("*"))
    return nominal + lower, nominal + upper


def test_the_round_bore_is_reamed_and_the_sleeve_boss_made_to_it() -> None:
    """#2409: the bore is plain round and reamed through.  Fit audit
    2026-11-23 (rule 4, made to fit): it prints the .3135 reamer's size and
    no band, and the sleeve's boss prints REF and is turned last to it, so
    neither sheet prints limits; the specs keep analysis bands whose
    clearance (never a bind, .0010 at most) the stacks consume.  The callout
    links the fit's note and ends on the least finished wall over it (rule
    20); the note names the mate, the acceptance by that mate and what the
    fit protects (the necessity answer, six words at most, no dimension in
    it)."""
    import build_pd_transgear_feed_pinion as sleeve_part
    import pd_transgear_feed_pinion_spec as sleeve

    assert spec.BORE_DIA == pytest.approx(sleeve.BOSS_DIA + max(sleeve.BOSS_DIA_BAND))
    assert spec.BORE_BAND == pytest.approx((0.0005 * IN, 0.0))  # analysis: +.0005/0
    assert part.BORE_DIA == drawing.BORE_DIA == spec.BORE_DIA
    assert part.BORE_R == pytest.approx(0.3135 * IN / 2.0)
    # One round cut through the whole part: no flat, no second bore.
    assert part.V_BORE == pytest.approx(math.pi * part.BORE_R**2 * spec.HUB_LENGTH)
    for name in ("FLAT_TO_AXIS", "FLAT_CLEARANCE"):
        assert not hasattr(spec, name)

    # Neither build applies a band to the pair.
    assert ("BoreProfile", "BoreDia") not in model_toleranced_dimensions(part)
    assert ("SleeveProfile", "BossDia") not in model_toleranced_dimensions(sleeve_part)
    bore = (spec.BORE_DIA + spec.BORE_BAND[1], spec.BORE_DIA + spec.BORE_BAND[0])
    boss = (
        sleeve.BOSS_DIA + min(sleeve.BOSS_DIA_BAND),
        sleeve.BOSS_DIA + max(sleeve.BOSS_DIA_BAND),
    )
    assert bore == pytest.approx((0.3135 * IN, 0.3140 * IN))
    round_fit = (bore[0] - boss[1], bore[1] - boss[0])
    assert round_fit[0] >= -1e-9
    assert round_fit == pytest.approx(spec.BOSS_CLEARANCE_LIMITS, abs=1e-6)
    assert round_fit == pytest.approx((0.0, 0.0010 * IN), abs=1e-6)
    assert spec.BOSS_CLEARANCE == spec.BOSS_CLEARANCE_LIMITS[1]
    callout = drawing.DIMENSION_CALLOUTS_BELOW["BoreDia"].splitlines()
    assert callout == ["REAM THRU", f"SEE NOTE {spec.BORE_NOTE}", spec.BORE_WALL_TEXT]
    # Owner ruling 2026-11-24: the reason is the registry's, not the sheet's.
    assert spec.BORE_NOTE_TEXT == f"{spec.SLEEVE_NUMBER} IS TURNED TO THIS BORE."
    assert not re.search(r"\.\d", spec.BORE_NOTE_TEXT)
    assert f"{spec.BORE_NOTE}. {spec.BORE_NOTE_TEXT}" in drawing.NOTES_TEXT


def test_a_looser_boss_fit_closes_the_collar_air() -> None:
    """The necessity answer the bore prints, derived: the hub's rock on the
    boss is the collar air's largest clearance term, and .002 more diametral
    clearance (rule 4's test) closes the air under its floor."""
    import pd_cluster_air as air

    terms = dict(air.COLLAR_AIR.terms)
    label = "hub rock on the sleeve boss"
    assert terms[label] == pytest.approx(
        spec.BOSS_CLEARANCE / spec.ROUND_ENGAGEMENT_MIN * air.DISC_TILT_LEVER
    )
    assert air.COLLAR_AIR.air_mm("statistical") >= air.COLLAR_AIR_MIN
    looser = (spec.BOSS_CLEARANCE + 0.002 * IN) / spec.ROUND_ENGAGEMENT_MIN
    terms[label] = looser * air.DISC_TILT_LEVER
    loose = air.AirStack("looser boss", air.COLLAR_AIR.nominal_mm, terms, air.COLLAR_AIR_MIN)
    assert loose.air_mm("statistical") < air.COLLAR_AIR_MIN


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
    # The chord keeps its own band; the stop takes the title block's row
    # (fit audit 2026-11-23: it printed the chord's +/-.002).
    band = 0.002 * IN
    assert spec.KEY_PIN_CHORD_BAND == pytest.approx(band)
    chord = (spec.KEY_PIN_CHORD_OFFSET - band, spec.KEY_PIN_CHORD_OFFSET + band)
    stop = (spec.KEY_PIN_STOP - _row(3), spec.KEY_PIN_STOP + _row(3))
    assert spec.KEY_PIN_LOCATION_PLACES == 3
    assert chord == pytest.approx((0.172 * IN, 0.176 * IN))
    assert stop == pytest.approx((0.155 * IN, 0.165 * IN))
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
        row.id: row
        for row in load_exceptions(_config.CONFIG_DIR, part.PART_NAME, "part")
    }
    wall, play = exceptions["RV-03"], exceptions["RV-04"]
    assert wall.kind == "minor"
    assert "#2144 item 3.2" in wall.reason
    assert play.kind == "accept"
    assert play.reason.startswith(
        "Delegated ruling 2026-11-11 (Main), no precedent; owner review #2144"
    )
    assert f"{spec.KEY_PIN_PLAY_DEG:.1f} deg" in play.finding
    assert not any("rule 18" in row.finding for row in exceptions.values())


def test_the_spigot_seats_on_the_step_square_and_clear_of_the_disc() -> None:
    """R9-68: the spigot clears the disc's bore and seats on the 12T's step.
    Its end and the flange's rear face are square to the bore (datum A) on
    the sheet; the disc's tilt reads both, the step's and the hub's rock on
    the boss, and its rear face stays in air ahead of the step.  Fit audit
    2026-11-23 (rule 4, made to fit): the spigot is turned to the disc's
    reamed bore, its size REF, and its note prints the clearance, .003-.005,
    with the one reason and the root's limit."""
    import pd_rack_pinion_spec as disc
    import pd_transgear_feed_pinion_spec as sleeve

    # The printed clearance is the requirement; the spigot's analysis band
    # is that clearance under the disc bore's analysis band.
    assert joint.SPIGOT_CLEARANCE == pytest.approx((0.003 * IN, 0.005 * IN))
    assert disc.SPIGOT_DIAMETRAL_CLEARANCE == joint.SPIGOT_CLEARANCE
    spigot = (
        spec.SPIGOT_DIA + spec.SPIGOT_DIA_BAND[1],
        spec.SPIGOT_DIA + spec.SPIGOT_DIA_BAND[0],
    )
    disc_bore = (disc.BORE_DIA + disc.BORE_BAND[1], disc.BORE_DIA + disc.BORE_BAND[0])
    assert spigot == pytest.approx(
        (
            disc_bore[0] - joint.SPIGOT_CLEARANCE[1],
            disc_bore[1] - joint.SPIGOT_CLEARANCE[0],
        )
    )
    assert spigot == pytest.approx((0.496 * IN, 0.500 * IN))
    assert ("HubProfile", "SpigotDia") not in model_toleranced_dimensions(part)
    assert drawing.DIMENSION_CALLOUTS_BELOW["SpigotDia"].splitlines() == [
        f"TURN TO {spec.DISC_NUMBER} BORE",
        f"SEE NOTE {spec.SPIGOT_NOTE}",
    ]
    assert spec.SPIGOT_NOTE_TEXT == f"CLEARANCE .003-.005 IN {spec.DISC_NUMBER} BORE."
    # Rule 16: the root's single limit on a leader to the corner itself, in
    # the air under the spigot and over the flange face's frame.
    assert spec.SPIGOT_ROOT_CALLOUT == "R.004 MAX"
    assert "ROOT" not in drawing.NOTES_TEXT
    corner = drawing.SPIGOT_ROOT_XY
    assert corner == pytest.approx(
        (drawing._side_x(0.0), drawing.AXIS_Y - spec.SPIGOT_DIA / 2.0 * drawing._S)
    )
    text = drawing.SPIGOT_ROOT_TEXT_XY
    assert text[0] > corner[0] + 0.010
    assert corner[1] - 0.009 < text[1] < corner[1] - 0.003
    assert f"{spec.SPIGOT_NOTE}. {spec.SPIGOT_NOTE_TEXT}" in drawing.NOTES_TEXT
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
            "sh-vn-fillister-screw-91794a055",
            "pd-vn-transgear-hub-key-pin",
            "pd-rack-pinion",
            "pd-transgear-drive-collar",
        )
    }
    printed = " ".join(_sheet_text().split())
    cited = re.findall(r"MHA-(?!VN-)[A-Z]{2}-(?:[0-9]{2}(?:-TL-(?:[0-9]{2}|VN-[5-9][0-9]))?|VN-[5-9][0-9])(?:-T[0-9]{3})?(?![A-Z0-9-])", printed)
    assert set(cited) == cited_mates
    # The pin is named once, in its fit note; the ream's callout links it.
    assert spec.KEY_PIN_NUMBER in spec.KEY_PIN_NOTE_TEXT
    assert spec.KEY_PIN_NUMBER not in spec.KEY_PIN_CALLOUT_BELOW


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
        - (spec.SPIGOT_LENGTH + _row(_places("SpigotLength")))
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

    assert oil_ligament == pytest.approx(0.1065 * IN, abs=0.005)
    assert oil_ligament == pytest.approx(spec.OIL_HOLE_LIGAMENT_WORST)
    assert pin_ligament == pytest.approx(0.099 * IN, abs=0.005)
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
    the spigot (.498 +.000/-.002) .0910 -> .0710, over the .060 floor (the bore and the spigot
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
    assert spigot == pytest.approx(0.0710 * IN, abs=1e-4)
    assert 0.060 * IN - 1e-9 <= spigot < WALL_FLOOR
    assert not hasattr(spec, "FLAT_WALL_FINISHED")
    assert spec.BORE_WALL_TEXT == "WALL .071 MIN"
    assert drawing.DIMENSION_CALLOUTS_BELOW["BoreDia"].split("\n")[-1] == (
        spec.BORE_WALL_TEXT
    )


def test_the_package_declares_the_bore_wall_the_callout_prints() -> None:
    """#2168: Main's delegated minor (option A, the geometry kept) names the
    generated wall line the bore callout prints last (rule 20)."""
    exceptions = load_exceptions(_config.CONFIG_DIR, "pd-transgear-disc-hub", "part")
    (entry,) = [entry for entry in exceptions if entry.id == "RV-02"]
    assert entry.kind == "minor"
    assert spec.BORE_WALL_TEXT in entry.where
    assert entry.reason.startswith("Owner ruling 2026-11-08 (Pedro)")
    assert "#2144" in entry.reason
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


def test_the_native_bore_is_the_reamer_over_the_feed_boss(
    monkeypatch,
) -> None:
    """The bore is the .3135 reamer's size, the boss's modelled largest: a
    boss moved without the reamer is refused."""
    assert _spec_fresh().BORE_DIA == pytest.approx(0.3135 * IN)
    old_boss = spec.SLEEVE.BOSS_DIA
    monkeypatch.setattr(spec.SLEEVE, "BOSS_DIA", old_boss - 0.1)
    with pytest.raises(AssertionError, match="reamer is not the sleeve boss"):
        _spec_fresh()


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
        - (spec.SPIGOT_LENGTH + _row(_places("SpigotLength")))
        - (spec.FLANGE_THICK + _row(_places("FlangeThick"))),
        spec.HUB_LENGTH
        + FIT_LENGTH_BAND_IN
        - (spec.SPIGOT_LENGTH - _row(_places("SpigotLength")))
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
# The reamed bore and key-pin hole print their reamers' sizes and no band;
# the spigot prints in parentheses with none.
_REFERENCE = spec.REFERENCE_DIMENSIONS
# The disc cluster stack's printed overall and the chord hole's offset
# carry their symmetric band; the spigot's length prints plain.
_SYMMETRIC = {
    "HubLength": spec.HUB_LENGTH_BAND,
    "KeyPinChord": spec.KEY_PIN_CHORD_BAND,
}


def _printed_box(name: str, anchor: tuple[float, float]) -> Box:
    """The estimated box of a kept dimension's whole text, centred on its
    text point: value (the bore's with its upper limit) and callouts."""
    value = f"{_NOMINAL[name] / IN:.{_places(name)}f}".lstrip("0")
    if name.endswith("Dia"):
        value = f"\u00d8{value}"
    if name in _REFERENCE:
        value = f"({value})"
    if name in _SYMMETRIC:
        value += f"\u00b1{_SYMMETRIC[name] / IN:.{_places(name)}f}".replace("0.", ".", 1)
    value += drawing.SECTION_SUFFIXES.get(name, "")
    lines = [
        drawing.DIMENSION_CALLOUTS_ABOVE.get(name),
        value,
        drawing.DIMENSION_CALLOUTS_BELOW.get(name)
        or drawing.SECTION_CALLOUTS_BELOW.get(name),
    ]
    # SolidWorks prints the <HOLE-DEPTH> token as the one-character ↧.
    text = "\n".join(line for line in lines if line).replace("<HOLE-DEPTH>", "\u21a7")
    box = estimate_text_box(
        text,
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


def _face_view_angle(point: tuple[float, float]) -> float:
    """Sheet direction (degrees counter-clockwise from +X, 0-360) from the
    face view's centre to ``point``."""
    cx, cy = drawing.END_CENTER
    return math.degrees(math.atan2(point[1] - cy, point[0] - cx)) % 360.0


def _ray_gap(a: float, b: float) -> float:
    """Angle between two rays from one point, degrees."""
    diff = abs(a - b) % 360.0
    return min(diff, 360.0 - diff)


def _line_gap(a: float, b: float) -> float:
    """Angle between two lines through one point, degrees."""
    diff = abs(a - b) % 180.0
    return min(diff, 180.0 - diff)


def test_the_bore_leader_runs_well_off_the_bolt_circle_diameter_line() -> None:
    """Machinist review 2026-11-24 (two runs of three; rule 14): hung
    below-right, the Ø.3135 bore's leader left the bore beside the Ø.75
    diameter's line and the two ran almost on top of each other through the
    face view.  SolidWorks lands the bore's arrow on the ray from the bore's
    centre to the block's shoulder, and the diameter's line runs through
    the centre toward its text, so the two, taken as lines, stand at least
    35 degrees apart.  The leader also keeps off both centrelines, the three
    screw holes and their centre marks, and datum A's leader, and its block
    hangs left of the shoulder, inside the border."""
    leader = _face_view_angle(drawing._BORE_SHOULDER)
    assert leader == pytest.approx(drawing._BORE_LEADER_DEG)
    bolt_circle = _face_view_angle(drawing.END_KEEP["BoltCircleDia"])
    assert _line_gap(leader, bolt_circle) >= 35.0
    # Positive control: the r1 shoulder, below-right at (.1235, axis - .108),
    # put the leader within 11 degrees of the diameter's line.
    old = _face_view_angle((0.1235, drawing.AXIS_Y - 0.108))
    assert _line_gap(old, bolt_circle) < 35.0
    for centreline in (0.0, 90.0):
        assert _line_gap(leader, centreline) >= 12.0
    assert _ray_gap(leader, _face_view_angle(drawing.DATUM_A_SYMBOL)) >= 35.0
    # The face view shows model +X up and +Y right: a pattern angle a lands
    # at 90 - a on the sheet (the holes at 90, 330 and 210 degrees).  Each
    # hole's centre stands off the leader's ray by more than its radius and
    # its centre mark's reach.
    s = drawing._S
    bc_r = joint.BOLT_CIRCLE_DIA / 2.0 * s
    for model_deg in joint.SCREW_ANGLES_DEG:
        hole = (90.0 - model_deg) % 360.0
        miss = min(_ray_gap(leader, hole), 90.0)
        offset = bc_r * math.sin(math.radians(miss))
        assert offset >= joint.SCREW_HOLE_DIA / 2.0 * s + 0.010, hole
    # The block's near end is its lower-right corner, the shoulder.
    box = _printed_box("BoreDia", drawing.END_KEEP["BoreDia"])
    assert box.xmax <= drawing._BORE_SHOULDER[0] + 1e-9
    assert box.xmin >= _INNER_BORDER.xmin + 0.003
    title = DRAWING_TEMPLATES[drawing.SPEC.layout]
    assert box.xmax < title.title_block_left_m and box.ymin > title.title_block_top_m


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


def test_the_chord_hole_dimensions_print_left_of_the_ring() -> None:
    """Rule 26: the ream reads size, process, then depth with the Y14.5
    symbol, a REF because the stop's .160 from the hub axis on the section
    controls the floor; then the link to its fit note, which names the pin,
    its press fit and what the stop's third place keeps clear (rules 3, 7).
    The ream's and the knockout's blocks stand left of the ring, each
    dimension line at its text's height crossing its own run of the hole;
    the stop's text between its extension lines, between the two blocks;
    the chord's above the ring right of the axis's extension line."""
    callout = drawing.SECTION_CALLOUTS_BELOW["KeyPinDia"]
    assert drawing.SECTION_SUFFIXES == {
        "KeyPinDia": " REAM",
        "KeyPinStop": f" SEE NOTE {spec.KEY_PIN_NOTE}",
    }
    assert "KeyPinStop" in drawing.SECTION_KEEP
    assert _places("KeyPinStop") == spec.KEY_PIN_LOCATION_PLACES == 3
    # The REF depth: along the hole's axis from where it meets the O.D.
    # (on the chord) to the stop.
    entry = math.sqrt((spec.HUB_DIA / 2.0) ** 2 - spec.KEY_PIN_CHORD_OFFSET**2)
    assert spec.KEY_PIN_ENTRY_X == pytest.approx(entry)
    assert spec.KEY_PIN_DEPTH_REF == pytest.approx(entry + spec.KEY_PIN_STOP)
    assert spec.KEY_PIN_DEPTH_REF == pytest.approx(0.3665 * IN, abs=0.0005 * IN)
    assert callout.splitlines() == [
        "<HOLE-DEPTH> (.366)",
        f"SEE NOTE {spec.KEY_PIN_NOTE}",
    ]
    assert "PAST AXIS" not in _sheet_text()
    # The stop's .160 links the fit note (rule 7); the note keeps to the
    # fit, its mate and its acceptance (an instruction and a reason in it
    # were gated, review of 67b6a3879a).  That the third place keeps the
    # pin's end under the O.D. is the spec's check: it holds at the .XXX row
    # and breaks through at the .XX row's +/-.01.
    assert spec.KEY_PIN_NOTE_TEXT == (
        f"PRESS FIT ON {spec.KEY_PIN_NUMBER}: THE PIN PRESSES IN."
    )
    assert spec.KEY_PIN_END_RECESS_WORST > 0.0
    assert len(f"{spec.KEY_PIN_NOTE}. {spec.KEY_PIN_NOTE_TEXT}") <= drawing._NOTE_WIDTH
    assert not re.search(r"\.\d", spec.KEY_PIN_NOTE_TEXT)
    assert f"{spec.KEY_PIN_NOTE}. {spec.KEY_PIN_NOTE_TEXT}" in drawing.NOTES_TEXT
    assert spec.KEY_PIN_HOLE_BAND == pytest.approx((0.0005 * IN, 0.0))  # analysis
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
    # The stop's text, its note link on the value's row, between its
    # extension lines (the hub axis's level and the floor's), centred on the
    # arrows' column.  Its arrows stand outside (run 20261124T013305458Z), so
    # the ream's dimension line, at its block's foot, passes between the
    # extension lines over the stop's text and under the axis's level; the
    # ream's block ends left of the arrows.
    arrow_x = drawing.SECTION_STOP_ARROW_X
    assert keep["KeyPinStop"] == pytest.approx((arrow_x, (stop_y + centre[1]) / 2.0))
    assert stop_y < boxes["KeyPinStop"].ymin < boxes["KeyPinStop"].ymax < centre[1]
    assert boxes["KeyPinStop"].ymax + 0.002 <= boxes["KeyPinDia"].ymin
    assert boxes["KeyPinDia"].ymin <= centre[1] - 0.0005
    assert boxes["KeyPinDia"].xmax <= arrow_x - 0.002
    assert boxes["KeyPinDrillDia"].ymax < stop_y
    # The stop's lower arrow, 6.3 mm long under the floor's extension line
    # (r 20261124T013305458Z), passes right of the knockout's size row and
    # ends over its DRILL THRU row.
    drill_x, drill_y = keep["KeyPinDrillDia"]
    pitch = _CAP_M * _LINE_SPACING
    size_row = estimate_text_box(
        f"\u00d8{spec.KEY_PIN_DRILL_DIA / IN:.4f}".replace("0.", ".", 1),
        anchor=(drill_x, drill_y + pitch / 2.0),
        height=_CAP_M,
        reference=2,
        advance_ratio=_ADVANCE,
    )
    assert size_row is not None and size_row.xmax <= arrow_x - 0.004
    drill_row_top = drill_y - pitch / 2.0 + _CAP_M / 2.0
    assert drill_row_top <= stop_y - 0.0063 - 0.002
    # Every size left of the ring, clear of it; the stop's row, nearest it,
    # stands off the O.D. itself.
    for name in ("KeyPinDia", "KeyPinDrillDia"):
        assert boxes[name].xmax <= ring_left - 0.010, name
    stop_box = boxes["KeyPinStop"]
    nearest = (
        min(max(centre[0], stop_box.xmin), stop_box.xmax),
        min(max(centre[1], stop_box.ymin), stop_box.ymax),
    )
    assert math.dist(nearest, centre) - spec.HUB_DIA / 2.0 * s >= 0.004
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


def test_registry_row_is_the_turned_brass_mha_159() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-PD-17"
    assert int(row["quantity"]) == 1
    assert "C36000" in row["material_specification"]
    assert row["material"] == part.MATERIAL
    assert row["tolerance_class"] == "machined_block"


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


def _plane_face(normal: tuple[float, float, float], z_mm: float):
    from _gtol_face import FaceGeometry

    return FaceGeometry(None, 4001, (0.0, 0.0, 0.0, 0.0, 0.0, z_mm / 1000), normal, ())


def _cylinder_face(
    dia_mm: float,
    axis: tuple[float, float, float],
    centre_mm: tuple[float, float, float],
    half_length_mm: float,
):
    from _gtol_face import FaceGeometry

    r = dia_mm / 2
    half = [r if not a else half_length_mm for a in axis]
    box = tuple(
        value / 1000
        for value in (
            *(c - h for c, h in zip(centre_mm, half)),
            *(c + h for c, h in zip(centre_mm, half)),
        )
    )
    origin = tuple(c / 1000 for c in centre_mm)
    return FaceGeometry(None, 4002, (*origin, *axis, r / 1000), None, box)


def test_the_hub_declares_one_owner_per_face() -> None:
    """Every face the model carries, synthesised from the spec, has exactly
    the owner its feature names; the chord ream's stop shoulder has none."""
    import export_features

    manifest = export_features.requirement_manifest("pd_transgear_disc_hub")
    names = list(manifest["features"])
    assert names == [
        "front_face",
        "spigot_end",
        "flange_rear_face",
        "flange_front_face",
        "flange",
        "spigot",
        "hub_body",
        "bore",
        "flange_hole_1",
        "flange_hole_2",
        "flange_hole_3",
        "pin_ream",
        "pin_knockout",
        "oil_hole",
    ]
    body_mid = (spec.HUB_FRONT_Z - spec.FLANGE_THICK) / 2
    faces = {
        "front_face": _plane_face((0.0, 0.0, -1.0), spec.HUB_FRONT_Z),
        "spigot_end": _plane_face((0.0, 0.0, 1.0), spec.SPIGOT_LENGTH),
        "flange_rear_face": _plane_face((0.0, 0.0, 1.0), 0.0),
        "flange_front_face": _plane_face((0.0, 0.0, -1.0), -spec.FLANGE_THICK),
        "flange": _cylinder_face(
            spec.FLANGE_DIA,
            (0, 0, 1),
            (0, 0, -spec.FLANGE_THICK / 2),
            spec.FLANGE_THICK / 2,
        ),
        "spigot": _cylinder_face(
            spec.SPIGOT_DIA,
            (0, 0, 1),
            (0, 0, spec.SPIGOT_LENGTH / 2),
            spec.SPIGOT_LENGTH / 2,
        ),
        "hub_body": _cylinder_face(
            spec.HUB_DIA, (0, 0, 1), (0, 0, body_mid), spec.HUB_BODY_LENGTH / 2
        ),
        "bore": _cylinder_face(
            spec.BORE_DIA,
            (0, 0, 1),
            (0, 0, spec.SPIGOT_LENGTH - spec.HUB_LENGTH / 2),
            spec.HUB_LENGTH / 2,
        ),
        "pin_ream": _cylinder_face(
            spec.KEY_PIN_HOLE_DIA,
            (1, 0, 0),
            (0, -spec.KEY_PIN_CHORD_OFFSET, spec.KEY_PIN_Z),
            3.0,
        ),
        "pin_knockout": _cylinder_face(
            spec.KEY_PIN_DRILL_DIA,
            (1, 0, 0),
            (-5.0, -spec.KEY_PIN_CHORD_OFFSET, spec.KEY_PIN_Z),
            1.0,
        ),
        "oil_hole": _cylinder_face(
            spec.OIL_HOLE_DIA, (0, 1, 0), (0, 5.0, spec.KEY_PIN_Z), 1.5
        ),
    }
    for index, (x, y) in enumerate(joint.screw_centres(), 1):
        faces[f"flange_hole_{index}"] = _cylinder_face(
            joint.SCREW_HOLE_DIA,
            (0, 0, 1),
            (x, y, -spec.FLANGE_THICK / 2),
            spec.FLANGE_THICK / 2,
        )
    stop_shoulder = _plane_face((1.0, 0.0, 0.0), -spec.KEY_PIN_STOP)
    selectors = export_features.feature_selectors("pd_transgear_disc_hub")
    for name, face in faces.items():
        owners = [
            owner
            for owner, specs in selectors.items()
            if any(selector.matches(face) for selector in specs)
        ]
        assert owners == [name], name
    assert not any(
        selector.matches(stop_shoulder)
        for specs in selectors.values()
        for selector in specs
    )


def test_hub_feature_bands_are_the_printed_ones() -> None:
    import export_features

    features = export_features.requirement_manifest("pd_transgear_disc_hub")["features"]

    def band(low: float, high: float) -> object:
        return pytest.approx([low * IN, high * IN], abs=1e-6)

    assert features["spigot_end"]["length"] == band(0.538, 0.540)
    assert features["spigot_end"]["length_from"] == "front_face"
    assert features["spigot_end"]["perpendicularity_max"] == pytest.approx(0.001 * IN)
    assert features["flange_rear_face"]["perpendicularity_max"] == pytest.approx(
        0.001 * IN
    )
    assert features["flange_rear_face"]["perpendicularity_datum"] == "A"
    assert features["flange_front_face"]["thickness"] == band(0.089, 0.099)
    assert features["flange"]["dia"] == band(1.04, 1.06)
    assert "dia" not in features["spigot"]
    assert features["spigot"]["dia_ref"] == pytest.approx(0.498 * IN)
    assert features["spigot"]["diametral_clearance"] == pytest.approx(
        [0.003 * IN, 0.005 * IN]
    )
    assert features["spigot"]["fit"] == "clearance"
    assert features["spigot"]["length"] == band(0.139, 0.149)
    assert features["spigot"]["root_radius_max"] == pytest.approx(0.004 * IN)
    assert features["hub_body"]["dia"] == band(0.535, 0.545)
    assert features["hub_body"]["pin_ream_wall_min"] == pytest.approx(0.060 * IN)
    bore = features["bore"]
    # The reamed holes print no band: their bands are marked analysis-only.
    assert bore["dia"] == band(0.3135, 0.3140)
    assert bore["dia_basis"] == features["pin_ream"]["dia_basis"] == "analysis"
    assert (bore["process"], bore["thru"], bore["mate"], bore["datum"]) == (
        "ream",
        True,
        "MHA-PD-10",
        "A",
    )
    assert bore["wall_min"] == pytest.approx(0.071 * IN)
    for index in (1, 2, 3):
        hole = features[f"flange_hole_{index}"]
        assert hole["dia"] == band(0.067, 0.071)
        assert hole["bolt_circle_dia"] == band(0.74, 0.76)
        assert (hole["process"], hole["thru"], hole["count"]) == ("drill", True, 3)
        x, y, z = hole["at"]
        assert math.hypot(x, y) == pytest.approx(0.375 * IN) and z == 0.0
    ream = features["pin_ream"]
    assert ream["dia"] == band(0.0615, 0.0620)
    assert ream["chord"] == band(0.172, 0.176)
    assert ream["stop"] == band(0.155, 0.165)
    assert ream["station"] == band(0.14, 0.16)
    assert (ream["process"], ream["mate"], ream["fit"]) == (
        "ream",
        "MHA-PD-VN-69",
        "press",
    )
    entry = math.sqrt((spec.HUB_DIA / 2) ** 2 - spec.KEY_PIN_CHORD_OFFSET**2)
    assert ream["at"] == pytest.approx(
        [entry, -spec.KEY_PIN_CHORD_OFFSET, spec.KEY_PIN_Z]
    )
    assert ream["depth"] == pytest.approx([entry + 0.155 * IN, entry + 0.165 * IN])
    knockout = features["pin_knockout"]
    assert knockout["dia"] == band(0.0465, 0.0505)
    assert (knockout["drill"], knockout["thru"]) == ("#56", True)
    oil = features["oil_hole"]
    assert oil["dia"] == band(0.043, 0.047)
    assert (oil["made_at"], oil["into"], oil["mate"]) == (
        "assembly",
        "bore",
        "MHA-PD-10",
    )
    assert "process" not in oil


def test_hub_drawing_notes_are_the_four_numbered_notes() -> None:
    """Rule 7: at most four lines of notes, each one line, numbered as the
    callouts link them: the stack, then the bore's, the key pin's and the
    spigot's fit."""
    import export_features

    manifest = export_features.requirement_manifest("pd_transgear_disc_hub")
    lines = drawing.NOTES_TEXT.splitlines()
    assert manifest["notes"]["manufacturing"] == lines
    assert drawing.DRAWING_NOTES == drawing.NOTES_TEXT
    assert lines == [f"{n}. {text}" for n, text in spec.NOTE_TEXTS.items()]
    assert list(spec.NOTE_TEXTS) == [1, 2, 3, 4]
    for name, note in (
        ("BoreDia", spec.BORE_NOTE),
        ("SpigotDia", spec.SPIGOT_NOTE),
        ("HubLength", spec.STACK_NOTE),
    ):
        assert f"SEE NOTE {note}" in drawing.DIMENSION_CALLOUTS_BELOW[name]
    # The spigot's length links the stack's note: it names the air its
    # third place holds (rule 3).
    assert drawing.DIMENSION_CALLOUTS_BELOW["SpigotLength"] == f"SEE NOTE {spec.STACK_NOTE}"
