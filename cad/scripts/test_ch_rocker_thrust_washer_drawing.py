"""Offline contracts for the rocker-bank thrust washer (MHA-CH-009) drawing."""

from __future__ import annotations

import ast
from fractions import Fraction
from pathlib import Path

import pytest

import _config
import build_ch_rocker_thrust_washer as part
import draw_ch_rocker_thrust_washer as drawing
import ch_rocker_arm_spec
import ch_rocker_thrust_washer_spec as spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/ch-rocker-thrust-washer.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/ch-rocker-thrust-washer.pdf")
    assert (
        DRAWINGS_BY_NAME["ch_rocker_thrust_washer"].script
        == Path(drawing.__file__).resolve()
    )


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.RIGHT_KEEP)
    assert {
        (feature, name)
        for feature, names in spec.DRAWING_PRECISION.items()
        for name in names
    } == {
        (feature, name)
        for feature, names in spec.DRAWING_DIMENSIONS.items()
        for name in names
    }


def test_nothing_is_banded_on_the_model() -> None:
    """The south ear is blade-set off its washer (#948 ruling R) and the north
    washer is miced into the datum ear's DRO target, so its thickness sits in
    no datum chain: it is the stock's, judged at the mill's band by the bar
    clearance (test_rocker_bank_layout). The bore prints DRILL THRU, so the
    title block's DRILLED HOLES row is its band (PR #1317 machinist review:
    a model +0.1/0 restated it, against drawing-guidelines.md rule 2 (the title block is the general specification))."""
    from _printed_tolerance import drilled_oversize_mm

    assert model_toleranced_dimensions(part) == {}
    assert spec.BORE_BAND == (drilled_oversize_mm(), 0.0)
    assert spec.BORE_DIA - 6.35 > 0.0


def test_thickness_is_the_one_thirty_second_stock() -> None:
    """User, 2026-10-10 (was 1/16, ruling 2026-09-26): cut from 1/32 in
    stock, modelled at 0.79 and printed "1/32 (0.79) STOCK" so the stock's
    tolerance governs."""
    assert spec.STOCK_THICKNESS_IN == Fraction(1, 32)
    assert spec.STOCK_THICKNESS == pytest.approx(0.79375)
    assert spec.THICKNESS == 0.79
    assert part.DISC_THICK == spec.THICKNESS
    places = spec.DRAWING_PRECISION["Disc"]["DiscThick"]
    printed = (
        f"{spec.STOCK_TEXT_PREFIX}{spec.THICKNESS:.{places}f}{spec.STOCK_TEXT_SUFFIX}"
    )
    assert printed == "1/32 (0.79) STOCK"
    lo, hi = spec.STOCK_THICKNESS_RANGE
    assert hi - lo == pytest.approx(2 * spec.STOCK_THICKNESS_TOL_IN * 25.4)
    assert spec.STOCK_THICKNESS_TOL_IN == 0.003
    assert drawing.STOCK_TEXT_PREFIX is spec.STOCK_TEXT_PREFIX
    assert drawing.STOCK_TEXT_SUFFIX is spec.STOCK_TEXT_SUFFIX
    build_calls = [
        node.func.id
        for node in ast.walk(
            ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
        )
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    assert "_set_stock_text" in build_calls


def test_bore_callout_states_its_process() -> None:
    """PR #1317 machinist review: the banded bore printed no DRILL/REAM.
    drawing-guidelines.md rule 12 (hole and slot callouts say what to do): a hole callout states the process; the bore is a drilled-class
    running clearance on the shaft."""
    assert drawing.BORE_CALLOUT == "DRILL THRU"
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'set_dimension_callouts(adapter, annotations, {"BoreDia": BORE_CALLOUT})' in source


def test_registry_row_is_two_of_the_one_thirty_second_stock() -> None:
    row = _config.parts("ch-rocker-thrust-washer")
    assert row["number"] == "MHA-CH-009"
    # One at each end of the rocker stack (user, 2026-10-10).
    assert int(row["quantity"]) == 2
    assert row["material_specification"] == spec.MATERIAL_SPECIFICATION
    assert "1/32 in" in str(row["process"])


def test_title_block_material_names_the_acceptable_families() -> None:
    """Opus #1022 baseline over-specification: the MATERIAL cell named one
    grade to one spec (1008 CR sheet, ASTM A1008 CS) that nothing on the
    sheet needs. drawing-guidelines.md rule 2 (the title block is the general
    specification): name the acceptable families as alternatives. The cell
    reads the part's "Material" property, which part_properties takes from
    the registry row's material; never the SolidWorks library name (r743-4)."""
    import _part_properties

    row = _config.parts("ch-rocker-thrust-washer")
    assert row["material"] == spec.MATERIAL_TITLE
    assert dict(_part_properties.part_properties(part.PART_NAME))["Material"] == (
        spec.MATERIAL_TITLE
    )
    assert spec.MATERIAL_TITLE == "LOW-CARBON STEEL SHEET OR SHIM STOCK"
    assert " OR " in spec.MATERIAL_TITLE
    assert "1008" not in spec.MATERIAL_TITLE and "ASTM" not in spec.MATERIAL_TITLE
    assert "Plain Carbon Steel" not in spec.MATERIAL_TITLE
    # The thickness prints on the view ("1/32 (0.79) STOCK"), not in the cell;
    # registry cells of 50 characters print in this cell.
    assert "1/32" not in spec.MATERIAL_TITLE
    assert len(spec.MATERIAL_TITLE) <= 40


def test_sheet_states_the_worst_case_wall() -> None:
    """drawing-guidelines.md rule 20 (state a known shortfall as a plain
    fact): the OD is held to the hub's O10.20 by the amplitude-bar foot cheeks
    (test_rocker_bank_layout), so the washer falls short of rule 17's 2.0
    target and says so, in the part's only manufacturing note."""
    from _printed_tolerance import drilled_oversize_mm, printed_band_mm

    worst = (spec.OD - printed_band_mm(2) - (spec.BORE_DIA + drilled_oversize_mm())) / 2.0
    assert worst == pytest.approx(1.545)
    assert spec.WALL_MIN == 1.54 <= worst
    assert ch_rocker_arm_spec.RULE12_WALL_FLOOR <= spec.WALL_MIN < 2.0
    assert spec.DRAWING_NOTES == spec.WALL_NOTE == "WALL 1.54 MIN"
    assert "Pending exception ruling: MHA-CH-009 wall 1.54 MIN (#1022)." in Path(
        spec.__file__
    ).read_text(encoding="utf-8")
    assert part.DRAWING_NOTES is spec.DRAWING_NOTES
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)' in source


def test_face_view_diameters_take_their_near_rims() -> None:
    """Opus #1022 baseline clarity, drawing-guidelines.md rule 14 (keep text
    off the part): both diameter lines ran through the centre and crossed.
    Each is restyled to one arrow on its near rim, and the build proves the
    ink lands on its own rim, stays out of the centre and crosses nothing."""
    assert drawing.NEAR_SIDE_DIAMETERS == ("DiscDia", "BoreDia")
    assert set(drawing.NEAR_SIDE_DIAMETERS) == set(drawing.FRONT_KEEP)
    assert drawing.OD_SHEET_RADIUS == pytest.approx(0.0204)
    assert drawing.BORE_SHEET_RADIUS == pytest.approx(0.013)
    od_low, od_high = drawing.LEADER_LANDING["DiscDia"]
    bore_low, bore_high = drawing.LEADER_LANDING["BoreDia"]
    # The bands cannot mistake one rim for the other.
    assert bore_high < od_low
    assert drawing.LEADER_KEEP_OUT["DiscDia"] <= od_low
    assert drawing.LEADER_KEEP_OUT["BoreDia"] < bore_low
    # The OD text stands left of the centre and the bore's right of it, both
    # above the view, so the near rims face away from each other.
    centre_x, centre_y = drawing.FRONT_CENTER
    assert drawing.FRONT_KEEP["DiscDia"][0] < centre_x < drawing.FRONT_KEEP["BoreDia"][0]
    assert min(y for _x, y in drawing.FRONT_KEEP.values()) > centre_y + drawing.OD_SHEET_RADIUS
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "_near_side_diameters_clear(adapter, front, annotations)" in source
    assert 'set_near_side_diameter(annotation, f"washer {name}")' in source


def test_od_is_the_hub_od_over_its_own_wall_floor() -> None:
    """Hub and washer retain O10.20 over their own rule-12 floors; the hub's
    floor also includes coaxial eccentricity (PR #1354), unlike the washer's."""
    band = _config.title_block("linear_2pl")["value_in"] * 25.4
    assert ch_rocker_arm_spec.LINEAR_2PL == pytest.approx(band)
    assert spec.OD == ch_rocker_arm_spec.HUB_DIA
    assert spec.OD_MIN == pytest.approx(10.11)
    hub_required_od = (
        ch_rocker_arm_spec.PIVOT_HOLE_DIA
        + ch_rocker_arm_spec.PIVOT_HOLE_BAND[0]
        + 2.0 * (
            ch_rocker_arm_spec.RULE12_WALL_FLOOR
            + ch_rocker_arm_spec.HUB_COAXIALITY_DIA / 2.0
        )
        + band
    )
    assert ch_rocker_arm_spec.HUB_DIA_MIN >= hub_required_od
    assert ch_rocker_arm_spec.HUB_DIA_MIN == pytest.approx(10.14)
    wall = (spec.OD - band - (spec.BORE_DIA + spec.BORE_BAND[0])) / 2.0
    assert wall >= ch_rocker_arm_spec.RULE12_WALL_FLOOR


def _calls(path: str) -> dict[str, ast.Call]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return {
        node.func.id: node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_the_part_carries_every_property_its_drawing_requires(monkeypatch) -> None:
    """r743-p1s-A: the MHA-CH-009 drawing refused its source part, which carried
    no Material Specification, Finish or Quantity: the build never stamped
    them. The properties the part carries are the save's own set
    (part_properties) plus, when the build calls it before saving,
    apply_drawing_properties' set; every property the drawing requires must be
    among them and non-blank."""
    import _part_properties
    import _drawing_marks

    required = ast.literal_eval(
        next(
            k.value
            for k in _calls(drawing.__file__)["read_required_properties"].keywords
            if k.arg == "required"
        )
    )
    carried = dict(_part_properties.part_properties(part.PART_NAME))
    build_calls = _calls(part.__file__)
    stamp = build_calls.get("apply_drawing_properties")
    if stamp is not None:
        assert [ast.unparse(a) for a in stamp.args] == [
            "adapter",
            "PART_NAME",
            "{'Manufacturing Notes': DRAWING_NOTES}",
        ]
        assert stamp.lineno < build_calls["save_part_and_images"].lineno
        stamped = {}
        monkeypatch.setattr(
            _drawing_marks,
            "apply_custom_properties",
            lambda _adapter, props: stamped.update(props),
        )
        _drawing_marks.apply_drawing_properties(
            None, part.PART_NAME, {"Manufacturing Notes": part.DRAWING_NOTES}
        )
        carried.update(stamped)
    missing = [name for name in required if not str(carried.get(name) or "").strip()]
    assert missing == []


def _called_names(path: str) -> set[str]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return {
        node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, (ast.Name, ast.Attribute))
    }


def test_faces_carry_no_roughness_callout() -> None:
    """Main 2026-09-26 (r743-3 eye pass): the faces are the sheet's as
    supplied. A face Ra could only force the facing the stock ruling avoids,
    and a hand-cranked thrust washer does not need one. This supersedes the
    two MACHINED face finishes Codex #936 (PRRT_kwDOPHDy386mRSOM) asked for.
    The part authors no finish PMI and the sheet places no finish symbol; the
    title block's surface row is a process statement, not a number."""
    assert "author_part_pmi" not in _called_names(part.__file__)
    assert "add_surface_finish" not in _called_names(drawing.__file__)
    assert not (
        Path(spec.__file__).parent / "rocker_thrust_washer_drawing_spec.py"
    ).exists()
    assert not hasattr(spec, "SURFACE_FINISHES")


def test_imported_places_are_the_part_authored_ones() -> None:
    """Codex #936 PRRT_kwDOPHDy386mTMXz: the sheet proves each imported
    dimension kept the places the part authors, and never sets its own."""
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS
    assert drawing.DRAWING_PRECISION_BY_NAME == {
        name: digits
        for names in spec.DRAWING_PRECISION.values()
        for name, digits in names.items()
    }
    assert set(drawing.DRAWING_PRECISION_BY_NAME) == set(drawing.FRONT_KEEP) | set(
        drawing.RIGHT_KEEP
    )
