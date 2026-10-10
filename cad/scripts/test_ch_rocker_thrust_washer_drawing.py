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


def test_only_the_bore_is_banded() -> None:
    """The south ear is blade-set off this washer (#948 ruling R), so its thickness sits in
    no datum chain: it is the stock's, judged at the mill's band by the bar
    clearance (test_rocker_bank_layout)."""
    assert model_toleranced_dimensions(part) == {
        ("RingProfile", "BoreDia"): "*deviations(BORE_BAND)",
    }
    assert spec.BORE_BAND[1] == 0.0
    assert spec.BORE_DIA - 6.35 > 0.0


def test_thickness_is_the_one_sixteenth_stock() -> None:
    """User ruling 2026-09-26: cut from 1/16 in stock, modelled at 1.59 and
    printed "1/16 (1.59) STOCK" so the stock's tolerance governs."""
    assert spec.STOCK_THICKNESS_IN == Fraction(1, 16)
    assert spec.STOCK_THICKNESS == pytest.approx(1.5875)
    assert spec.THICKNESS == 1.59
    assert part.DISC_THICK == spec.THICKNESS
    places = spec.DRAWING_PRECISION["Disc"]["DiscThick"]
    printed = (
        f"{spec.STOCK_TEXT_PREFIX}{spec.THICKNESS:.{places}f}{spec.STOCK_TEXT_SUFFIX}"
    )
    assert printed == "1/16 (1.59) STOCK"
    lo, hi = spec.STOCK_THICKNESS_RANGE
    assert hi - lo == pytest.approx(2 * 0.005 * 25.4)
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


def test_registry_row_is_the_one_sixteenth_stock_mha_148() -> None:
    row = _config.parts("ch-rocker-thrust-washer")
    assert row["number"] == "MHA-CH-009"
    assert int(row["quantity"]) == 1
    assert row["material_specification"] == spec.MATERIAL_SPECIFICATION
    assert "1/16 in" in str(row["process"])


def test_title_block_material_prints_the_ruled_sheet() -> None:
    """Main (r743-4 eye pass): the MATERIAL cell printed the SolidWorks
    library name "Plain Carbon Steel". The cell reads the part's "Material"
    property, which part_properties takes from the registry row's material;
    that is now the ruled 1008 CR sheet, short enough for the cell."""
    import _part_properties

    row = _config.parts("ch-rocker-thrust-washer")
    assert row["material"] == spec.MATERIAL_TITLE
    assert dict(_part_properties.part_properties(part.PART_NAME))["Material"] == (
        spec.MATERIAL_TITLE
    )
    assert "1008" in spec.MATERIAL_TITLE and "A1008" in spec.MATERIAL_TITLE
    assert "Plain Carbon Steel" not in spec.MATERIAL_TITLE
    assert len(spec.MATERIAL_TITLE) <= 30


def test_od_is_the_hub_od_over_its_own_wall_floor() -> None:
    """Main 2026-09-26: one O10.20 for hub and washer, each over its own
    rule-12 floor (bore max + 2 x 1.5 + the .XX band), computed in its spec."""
    band = _config.title_block("linear_2pl")["value_in"] * 25.4
    assert ch_rocker_arm_spec.LINEAR_2PL == pytest.approx(band)
    assert spec.OD == ch_rocker_arm_spec.HUB_DIA
    assert spec.OD_MIN == pytest.approx(10.11)
    assert ch_rocker_arm_spec.HUB_DIA_MIN == pytest.approx(10.04)
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
        assert [ast.unparse(a) for a in stamp.args] == ["adapter", "PART_NAME"]
        assert stamp.lineno < build_calls["save_part_and_images"].lineno
        stamped = {}
        monkeypatch.setattr(
            _drawing_marks,
            "apply_custom_properties",
            lambda _adapter, props: stamped.update(props),
        )
        _drawing_marks.apply_drawing_properties(None, part.PART_NAME)
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
    """Main 2026-09-26 (r743-3 eye pass): the faces are the 1/16 sheet's as
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
