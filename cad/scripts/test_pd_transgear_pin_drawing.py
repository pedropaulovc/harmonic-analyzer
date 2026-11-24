"""Offline contracts for the transgear pin (MHA-PD-23) and its drawing."""

from __future__ import annotations

import ast
import math
import re
from pathlib import Path

import pytest

import _config
import build_pd_transgear_pin as part
import draw_pd_transgear_pin as drawing
import pd_transgear_arm_geometry as arm
import pd_transgear_pin_callouts as callouts
import pd_transgear_pin_spec as spec
import pd_vn_transgear_retaining_ring_spec as ring
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DrawingLayout
from _inch_wall_limits import WALL_TARGET_MM
from _printed_tolerance import (
    edge_break_chamfer_mm,
    edge_break_radius_mm,
    printed_band_mm,
)
from _surface_finish import MACHINED_UM
from pd_cluster_stack_band import FIT_LENGTH_BAND_IN


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pd-transgear-pin.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pd-transgear-pin.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pd-transgear-pin_drawing.png")
    row = DRAWINGS_BY_NAME["pd_transgear_pin"]
    assert row.script == Path(drawing.__file__).resolve()
    assert row.layout is DrawingLayout.LANDSCAPE
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_every_marked_dimension_prints_once_with_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.SIDE_KEEP) == marked
    assert {
        (feature, name)
        for feature, names in spec.DRAWING_PRECISION.items()
        for name in names
    } == {
        (feature, name)
        for feature, names in spec.DRAWING_DIMENSIONS.items()
        for name in names
    }


def test_only_the_ring_groove_and_its_station_carry_model_bands() -> None:
    """The groove's catalogue Ø and width, and the groove station (a
    disc-cluster stack term) carry native bands; the shank prints a
    reference Ø with no band (made to fit, fit audit 2026-11-23); the head
    land and the tip apex's station print .XX, and every other size its
    places under the title block."""
    assert model_toleranced_dimensions(part) == {
        ("PinProfile", "GrooveDia"): "*deviations(GROOVE_DIA_BAND)",
        ("PinProfile", "GrooveWidth"): "*deviations(GROOVE_WIDTH_BAND)",
        ("PinProfile", "GrooveStation"): "GROOVE_STATION_BAND",
    }
    assert spec.GROOVE_STATION_BAND == FIT_LENGTH_BAND_IN
    assert spec.DRAWING_PRECISION_BY_NAME["ShankDia"] == 3
    assert spec.DRAWING_PRECISION_BY_NAME["GrooveStation"] == 3
    assert spec.DRAWING_PRECISION_BY_NAME["TipDomeZ"] == 2
    assert spec.DRAWING_PRECISION_BY_NAME["HeadLand"] == 2


def test_the_front_land_holds_the_wall_target_at_the_worst_case() -> None:
    """Review of e0ac6477e (blocker): the land in front of the groove is a
    wall held to the .080 target (three groove depths, .045, is the weaker
    bound).  ENFORCE run 20261024T034648173Z: the land's end at the tip
    dome's junction cannot be picked up, so the tip apex prints from the
    head seat and the land is a reference.  Its worst case is then the apex
    at its printed lower limit, the load wall at its ±band's upper, and the
    deepest dome on the shank: a hemisphere."""
    tip_places = spec.DRAWING_PRECISION_BY_NAME["TipDomeZ"]
    dome_r_places = spec.DRAWING_PRECISION_BY_NAME["TipDomeR"]
    # At its printed lower limit the R is smaller than the rim: the deepest
    # real dome on the largest shank is the hemisphere.
    assert spec.TIP_DOME_R - printed_band_mm(dome_r_places, unit=spec.UNIT) < (
        spec.DIA_MAX / 2.0
    )
    lower = (
        spec.TIP_STATION
        - printed_band_mm(tip_places, unit=spec.UNIT)
        - (spec.GROOVE_STATION + spec.GROOVE_STATION_BAND)
        - spec.DIA_MAX / 2.0
    )
    assert spec.FRONT_LAND_MIN == pytest.approx(lower)
    assert lower >= WALL_TARGET_MM
    assert lower >= spec.EDGE_MARGIN_MIN
    assert spec.LENGTH == spec.TIP_STATION
    assert spec.FRONT_LAND == pytest.approx(
        spec.TIP_STATION - spec.GROOVE_STATION - spec.TIP_DOME_SAG
    )


def test_the_head_land_holds_the_wall_target_at_its_printed_lower_limit() -> None:
    """Review of e0ac6477e (blocker): 1.20 at .XX let the retaining head go
    to 0.69.  At its printed lower limit the land holds the .080 target and
    still keeps a cylindrical rim past the largest edge break on both its
    edges, under the dome on top."""
    places = spec.DRAWING_PRECISION_BY_NAME["HeadLand"]
    lower = spec.HEAD_LAND - printed_band_mm(places, unit=spec.UNIT)
    assert spec.HEAD_LAND_MIN == pytest.approx(lower)
    assert lower >= WALL_TARGET_MM - 1e-9
    edge_break = max(
        edge_break_radius_mm(unit=spec.UNIT), edge_break_chamfer_mm(unit=spec.UNIT)
    )
    assert lower - 2.0 * edge_break > 0.0


def test_the_seat_root_radius_leaves_the_head_a_flat_seat() -> None:
    """Machinist review round 4: the head's seat gets its own root radius,
    well inside the .0375 step, so the head still bears on the arm's rear
    face past the ream mouth's break and its own rim break."""
    step = (spec.HEAD_DIA - spec.DIA_MAX) / 2.0
    assert 0.0 < spec.SEAT_FILLET_R < step / 4.0
    contact = (
        (spec.HEAD_DIA - printed_band_mm(2, unit=spec.UNIT)) / 2.0
        - edge_break_chamfer_mm(unit=spec.UNIT)
        - max(
            arm.PIN_BORE_DIA_MAX / 2.0 + arm.PIN_MOUTH_CHAMFER_LIMITS[1],
            spec.DIA_MAX / 2.0 + spec.SEAT_FILLET_R,
        )
    )
    assert spec.SEAT_CONTACT_WIDTH_MIN == pytest.approx(contact)
    assert contact > 0.0


def test_the_arm_rear_mouth_clears_the_seat_root_at_every_limit() -> None:
    # Codjiflo (#2124): a 45-degree mouth with a leg of at least R contains
    # the fillet's whole spandrel (it reaches R up the shank and R out on the
    # seat), so the head lands on the face; the title block's break has no
    # minimum, so the arm models and prints one.
    low, high = arm.PIN_MOUTH_CHAMFER_LIMITS
    assert low >= spec.SEAT_FILLET_R
    assert low < arm.PIN_MOUTH_CHAMFER < high
    assert high == pytest.approx(edge_break_chamfer_mm(unit=spec.UNIT))


def test_the_groove_holds_the_ring_at_every_printed_limit() -> None:
    """The ring grips at the groove's largest Ø and still clears the shank;
    the ring's thickness never binds in the narrowest groove."""
    groove_max = spec.GROOVE_DIA + spec.GROOVE_DIA_BAND[0]
    groove_min = spec.GROOVE_DIA + spec.GROOVE_DIA_BAND[1]
    assert ring.FREE_DIA < groove_min
    assert groove_max < spec.DIA_MIN
    assert spec.GROOVE_WIDTH + spec.GROOVE_WIDTH_BAND[1] > (
        ring.THICKNESS + ring.THICKNESS_TOL
    )


def _below(name: str) -> str:
    return callouts.callouts_by_lane(callouts.CALLOUT_BELOW)[name]


def test_the_groove_names_its_ring_once_in_a_note_both_bands_link() -> None:
    """Rule 4: the groove's Ø and width name their ring once, in a numbered
    note linked from both; an above-callout with a line break never prints."""
    (text,) = callouts.CALLOUTS[callouts.CALLOUT_ABOVE].values()
    assert text == callouts.GROOVE_CALLOUT == f"SEE NOTE {callouts.RING_GROOVE_NOTE}"
    assert _below("GrooveWidth") == callouts.GROOVE_CALLOUT
    assert callouts.DRAWING_NOTES.count(spec.RING_NUMBER) == 1
    assert ring.SKU in callouts.DRAWING_NOTES


def test_the_part_authors_every_callout_on_a_marked_dimension() -> None:
    """The builder writes each lane on its source dimension and the drawing
    only reads it back (#1942): every authored dimension is one the part
    marks for the drawing and the sheet places."""
    marked = {
        (feature, name)
        for feature, names in spec.DRAWING_DIMENSIONS.items()
        for name in names
    }
    authored = {
        (feature, name)
        for feature, by_name in callouts.authored_text().items()
        for name in by_name
    }
    assert authored <= marked
    assert set(callouts.authored_by_name()) <= set(drawing.SIDE_KEEP)
    calls = _calls(drawing.__file__)
    assert "set_dimension_callouts" not in calls
    assert "set_dimension_text" not in calls
    assert "author_dimension_callouts" in _calls(part.__file__)


def test_the_groove_width_band_stands_clear_of_its_extension_lines() -> None:
    """Rule 14: the width's text centre stands far enough toward the head
    that the rear wall's and the load wall's extension lines miss the text
    block."""
    x, _ = drawing.SIDE_KEEP["GrooveWidth"]
    assert x - 0.028 > drawing.GROOVE_REAR_X > drawing.LOAD_WALL_X
    # The shank Ø's dimension line (and its arrow below the shank) passes
    # right of the width's text and ring callout, not through its limits.
    shank_x, _ = drawing.SIDE_KEEP["ShankDia"]
    assert shank_x > x + 0.035


def test_the_part_notes_carry_no_assembly_step() -> None:
    """The press into the arm is the assembly's pin-pressed step (rule 24)."""
    assert "PRESSED" not in callouts.DRAWING_NOTES


@pytest.mark.parametrize(
    ("station", "machine_z"),
    [
        (0.0, -114.888),
        (spec.GROOVE_STATION, -163.7322),
        (spec.LENGTH, -167.72),
    ],
)
def test_the_pin_sits_at_its_machine_stations(station: float, machine_z: float) -> None:
    assert spec.HEAD_SEAT_MACHINE_Z - station == pytest.approx(machine_z, abs=1e-9)


def test_the_functional_station_runs_from_the_head_seat_to_the_load_wall() -> None:
    """The station's extension lines rise from the seat and the groove's
    FRONT wall (paper-left of the rear wall), not from its rear wall."""
    x, _ = drawing.SIDE_KEEP["GrooveStation"]
    assert x == pytest.approx((drawing.SEAT_X + drawing.LOAD_WALL_X) / 2.0)
    assert drawing.LOAD_WALL_X < drawing.GROOVE_REAR_X < drawing.SEAT_X


def test_the_station_names_the_stack_it_sets() -> None:
    """Rule 4: the station's ±band names the stack it serves by drawing number."""
    import transgear_cluster_fit as fit

    callout = _below("GrooveStation")
    assert callout == callouts.GROOVE_STATION_CALLOUT
    assert "\n" not in callout and spec.FRONT_BUSHING_NUMBER in callout
    assert spec.DRAWING_PRECISION_BY_NAME["GrooveStation"] == 3
    assert fit.GS[1:] == (spec.GROOVE_STATION, spec.GROOVE_STATION_BAND)


def test_the_dome_heights_and_the_overall_print_as_references() -> None:
    """Rule 10: the overall and both dome heights read off the sheet, as
    references the radii and lands already set."""
    assert callouts.REFERENCE_TEXT == {
        **{
            (feature, name): {callouts.TEXT_PREFIX: "(", callouts.TEXT_SUFFIX: ")"}
            for feature, name in (
                ("HeadDomeProfile", "HeadDomeSagDim"),
                ("TipDomeProfile", "TipDomeSagDim"),
                ("PinProfile", "FrontLand"),
            )
        },
        # Fit audit 2026-11-23: the shank is made to fit its mates' reamed
        # bores (note 1); its Ø is a reference.
        ("PinProfile", "ShankDia"): {
            callouts.TEXT_PREFIX: "(<MOD-DIAM>",
            callouts.TEXT_SUFFIX: ")",
        },
    }
    assert spec.DRAWING_PRECISION["HeadDomeProfile"]["HeadDomeSagDim"] == 2
    assert spec.DRAWING_PRECISION["TipDomeProfile"]["TipDomeSagDim"] == 2
    assert spec.DRAWING_REFERENCE_PRECISION == 2
    # The overall's row stands under the station's callout.
    assert drawing.OVERALL_TEXT_XY[1] < drawing.SIDE_KEEP["GrooveStation"][1] - 0.020
    # The land's (.12) ends left of the tip apex's extension line that the
    # 2.02 and the overall share.
    land_x, _ = drawing.SIDE_KEEP["FrontLand"]
    assert land_x + 0.0057 < drawing.TIP_X - 0.001


def test_the_shank_carries_the_one_machined_finish() -> None:
    (shank,) = spec.SURFACE_FINISHES
    assert shank.key == "journal"
    assert shank.roughness_um == MACHINED_UM
    assert shank.face.diameter_mm == spec.DIA
    assert 0.0 < shank.face.contains_z_mm < spec.GROOVE_REAR_STATION


def test_notes_fit_the_sheet_limits() -> None:
    lines = callouts.DRAWING_NOTES.splitlines()
    starts = [index for index, line in enumerate(lines) if not line.startswith(" ")]
    for start, end in zip(starts, [*starts[1:], len(lines)]):
        assert end - start <= 4
    assert all(len(line) <= 70 for line in lines)


def test_the_one_diameter_shank_is_bonded_in_the_arm_and_runs_in_its_mates() -> None:
    """Fit audit 2026-11-23 (pending owner confirmation): the pin has one
    diameter under its head, a slip fit bonded in the arm's ream with the
    retaining compound the note names; nothing presses.  The gap sits inside
    the compound's fill, the bond's derated capacity covers the ring's rated
    thrust and twice its face drag, and the literals are the repository's."""
    import dt_pinion_arbor_geometry as arbor
    import sm_gooseneck_spring_joint as gooseneck

    for name in ("PRESS_INTERFERENCE", "PRESS_LAND_DIA", "PRESS_LAND_LENGTH"):
        assert not hasattr(spec, name), name
    assert "LandDia" not in callouts.authored_by_name()
    least, greatest = spec.BOND_GAP
    assert (least, greatest) == pytest.approx(
        (arm.PIN_BORE_DIA_MIN - spec.DIA_MAX, arm.PIN_BORE_DIA_MAX - spec.DIA_MIN)
    )
    assert 0.0 < least < greatest < spec.LOCTITE_638_GAP_MAX
    assert spec.BOND_LENGTH_MIN == pytest.approx(
        arm.THICKNESS
        - arm.THICKNESS_BAND
        - arm.PIN_MOUTH_CHAMFER_LIMITS[1]
        - edge_break_chamfer_mm(unit=spec.UNIT)
    )
    assert spec.LOCTITE_638_SHEAR_MPA == arbor.LOCTITE_638_SHEAR_MPA == gooseneck.LOCTITE_638_SHEAR_MPA
    assert spec.BOND_TORQUE_MARGIN_MIN == arbor.BOND_TORQUE_MARGIN_MIN == gooseneck.BOND_TORQUE_MARGIN_MIN
    # The gooseneck's steel and clearance factors, with a long land's 0.5.
    assert spec.BOND_FACTOR == pytest.approx(gooseneck.BOND_FACTOR * 0.5)
    assert spec.BOND_AXIAL_CAPACITY_N == pytest.approx(
        spec.LOCTITE_638_SHEAR_MPA * spec.BOND_FACTOR * math.pi * spec.DIA_MIN * spec.BOND_LENGTH_MIN
    )
    assert spec.BOND_AXIAL_CAPACITY_N > spec.BOND_AXIAL_DEMAND_N
    assert spec.BOND_TORQUE_CAPACITY_NMM >= spec.BOND_TORQUE_MARGIN_MIN * spec.BOND_TORQUE_DEMAND_NMM
    assert _below("ShankDia") == callouts.SHANK_CALLOUT == f"SEE NOTE {callouts.SHANK_FIT_NOTE}"
    assert callouts.DRAWING_NOTES.startswith(f"{callouts.SHANK_FIT_NOTE}. ")
    notes = " ".join(line.strip() for line in callouts.DRAWING_NOTES.splitlines())
    assert (
        f"BONDED SLIP FIT IN {spec.ARM_NUMBER}, {spec.RETAINING_COMPOUND}: SLIDES IN BY HAND."
    ) in notes
    assert all(number in callouts.DRAWING_NOTES for number in spec.RUNNING_MATES)
    assert "PRESS" not in callouts.DRAWING_NOTES
    assert "GROUND" not in callouts.DRAWING_NOTES


def test_the_shank_is_made_to_fit_and_prints_no_limits() -> None:
    """Fit audit 2026-11-23 (rule 4, made to fit): the shank's sentence in
    note 1 names the three mates and the acceptance by feel, and carries no
    size and no reason (machinist review r1 of the fit batch, rule 7: the
    reference size has no band to answer for; the bores' REAM callouts
    carry the necessity answers); the modelled clearance is an analysis
    result the stacks read, not a printed limit."""
    import pd_transgear_feed_pinion_spec as sleeve

    notes = " ".join(line.strip() for line in callouts.DRAWING_NOTES.splitlines())
    shank = notes[notes.index("SHANK:") : notes.index(" BONDED SLIP FIT")]
    assert shank == (
        "SHANK: TURN LAST TO BORES OF MHA-PD-10, MHA-PD-24, MHA-PD-25: "
        "EACH TURNS FREE, NO SHAKE; SHIM MHA-PD-VN-68 SLIDES ON."
    )
    assert not re.search(r"\d*\.\d", shank)
    assert "KEEPS" not in callouts.DRAWING_NOTES
    assert not hasattr(callouts, "SHANK_NECESSITY")
    assert not hasattr(callouts, "RUNNING_CLEARANCE")
    # The analysis result: the modelled shank in the reamer's modelled bore.
    assert sleeve.BORE_DIAMETRAL_CLEARANCE == pytest.approx(
        (0.0010 * 25.4, 0.0017 * 25.4)
    )
    # Its top is the bought shims' smallest bore.
    assert spec.DIA_MAX == pytest.approx(0.1250 * 25.4)


def test_registry_row_is_the_turned_steel_mha_179() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == spec.PIN_NUMBER
    assert int(row["quantity"]) == 1
    assert row["material"] == part.MATERIAL
    assert row["tolerance_class"] == "machined_block"
    # No grinding is assumed (rule 4): the shank is turned to its band.
    assert row["finish"] == "oiled"
    assert "grind" not in row["process"]


def _calls(path: str) -> dict[str, ast.Call]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return {
        node.func.id: node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
