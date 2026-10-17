"""Offline contracts for the rocker strap (MHA-CH-013) drawing."""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

import _config
import build_ch_rocker_arm as rocker_part
import build_ch_rocker_strap as part
import ch_rocker_arm_notes as rocker_notes
import ch_rocker_arm_spec as rocker
import ch_rocker_strap_notes as notes
import ch_rocker_strap_spec as spec
import draw_ch_rocker_strap as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _calls(path: str) -> dict[str, ast.Call]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return {
        node.func.id: node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/ch-rocker-strap.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/ch-rocker-strap.pdf")
    assert (
        DRAWINGS_BY_NAME["ch_rocker_strap"].script == Path(drawing.__file__).resolve()
    )
    assert "draw_ch_rocker_strap.py" in PRECISION_MIGRATED_DRAWINGS


def test_outline_is_the_finished_rocker_strap() -> None:
    # Same frame and the same vertices as MHA-CH-006's strap profile.
    assert spec.HOLE_DIA == rocker.HUB_DIA
    assert spec.PIVOT_MID_Y == rocker.PIVOT_MID_Y
    assert spec.ROD_TIP_X == rocker.ROD_TIP_X
    assert spec.BOT_END_X == rocker.BOT_END_X
    assert spec.BOT_END_Y == pytest.approx(
        rocker.CENTER_Y - math.sqrt(rocker.R_BOTTOM**2 - rocker.BOT_END_X**2)
    )
    assert spec.ROD_TIP_Y < spec.TOP_END_Y
    # The tip land runs along the top arc's radius.
    tip_radius = math.hypot(spec.ROD_TIP_X, spec.ROD_TIP_Y - spec.CENTER_Y)
    assert tip_radius == pytest.approx(rocker.R_TOP + rocker.TIP_FACE)
    assert spec.strap_area() == pytest.approx(rocker_part._strap_area(), rel=1e-9)
    assert part.V_STRAP == pytest.approx(
        (spec.strap_area() - math.pi * (spec.HOLE_DIA / 2.0) ** 2)
        * rocker.ARM_THICKNESS
    )
    # The hub hole's walls (rule 17), each edge at the worst end of its band
    # against the H7 hole's top limit: both edges are held from the hole, so
    # the radii never stack into the wall (r1 machinist review: 0.79).
    hole_radius_max = (spec.HOLE_DIA + 0.018) / 2.0
    top_wall = spec.TOP_EDGE_ABOVE_PIVOT + spec.TOP_EDGE_BAND[1] - hole_radius_max
    bottom_wall = (
        spec.BOTTOM_EDGE_BELOW_PIVOT + spec.BOTTOM_EDGE_BAND[1] - hole_radius_max
    )
    assert min(top_wall, bottom_wall) >= 2.0
    # The bottom edge sits where MHA-CH-006's R816 puts it on the axis.
    assert spec.BOTTOM_EDGE_BELOW_PIVOT == pytest.approx(
        rocker.PIVOT_MID_Y - (rocker.CENTER_Y - rocker.R_BOTTOM)
    )


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*notes.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.RIGHT_KEEP)
    assert set(notes.DIMENSION_CALLOUTS) <= marked
    assert notes.DRAWING_PRECISION_BY_NAME["HoleDia"] == 3
    assert notes.DRAWING_PRECISION_BY_NAME["StrapThickness"] == 3
    assert notes.DRAWING_PRECISION_BY_NAME["TopAbovePivot"] == 2
    assert notes.DRAWING_PRECISION_BY_NAME["BottomBelowPivot"] == 2
    # The R816 follows from the R800 and both edges: never a stacking size.
    assert "BottomRadius" not in marked
    # TailTipLen is the RodTipLen's mirror: it prints once, as 2X.
    assert "TailTipLen" not in marked
    assert notes.TIP_LAND_PREFIX == "2X "
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "set_dimension_precision" not in source
    assert "assert_imported_precision(" in source


def test_every_band_is_native_and_names_its_mate() -> None:
    assert model_toleranced_dimensions(part) == {
        ("Strap", "StrapThickness"): "strap_upper",
        ("StrapProfile", "HoleDia"): "*deviations(STRAP_HOLE_BAND)",
        ("StrapProfile", "TopAbovePivot"): "*deviations(TOP_EDGE_BAND)",
        ("StrapProfile", "BottomBelowPivot"): "*deviations(BOTTOM_EDGE_BAND)",
    }
    assert spec.ARM_THICKNESS_BAND == rocker.ARM_THICKNESS_BAND == (0.025, -0.025)
    assert spec.TOP_EDGE_BAND == rocker.TOP_EDGE_BAND
    # The bottom edge's band mirrors the top's: the finished part's lower
    # profile zone, wholly in material.
    assert spec.BOTTOM_EDGE_BAND == (0.0, -0.5)
    assert notes.HOLE_CALLOUT.splitlines() == [
        "REAM THRU",
        "PRESS FIT ON MHA-CH-012 HUB",
        "0.005-0.034 DIAMETRAL INTERFERENCE",
    ]
    # The finished part's mates, worded as on its own print.
    assert (
        notes.DIMENSION_CALLOUTS["TopAbovePivot"] == rocker_notes.TOP_EDGE_MATE_CALLOUT
    )
    assert notes.DIMENSION_CALLOUTS["StrapThickness"] == rocker_notes.STRAP_FIT_CALLOUT
    assert notes.DIMENSION_CALLOUTS["BottomBelowPivot"].splitlines() == [
        "MHA-CH-006 PROFILE",
        "CONCENTRIC WITH R800",
    ]
    # The arc centre and the lands' direction ride on their own dimensions,
    # not in a general note.
    assert notes.DIMENSION_CALLOUTS["TopRadius"] == "CENTRE ABOVE HOLE"
    assert notes.DIMENSION_CALLOUTS["RodTipLen"] == "RADIAL"


def test_no_rod_pin_hole_and_no_finished_bore_on_the_strap() -> None:
    build = Path(part.__file__).read_text(encoding="utf-8")
    assert "ROD_PIN" not in build and "PIVOT_HOLE" not in build
    printed = " ".join((notes.DRAWING_NOTES, *notes.DIMENSION_CALLOUTS.values()))
    assert "#47" not in printed
    assert f"{rocker.PIVOT_HOLE_DIA:.2f}" not in printed


def test_drawing_quality_and_no_gdt() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert (
        "for view in (front, right, iso):\n        set_hidden_lines_removed" in source
    )
    names = set(_calls(drawing.__file__))
    assert not names & {
        "add_datum_feature",
        "add_feature_control_frame",
        "add_surface_finish",
    }
    assert notes.DRAWING_NOTES.splitlines() == [
        "1. JOINED TO HUB MHA-CH-012 AS MHA-CH-006.",
    ]
    assert notes.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:2"
    assert drawing.ISO_SCALE == (1, 2)


def test_registry_row() -> None:
    row = _config.parts("ch-rocker-strap")
    assert row["number"] == spec.NUMBER == "MHA-CH-013"
    assert row["component_of"] == "ch-rocker-arm"
    assert int(row["quantity"]) == int(_config.parts("ch-rocker-arm")["quantity"])
    assert "1018" in str(row["material_specification"])
    assert len(str(row["material_specification"])) <= 36
    assert len(str(row["finish"])) <= 36
    assert "22381" in str(row["process"])
    assert part.MATERIAL == "Plain Carbon Steel"


def test_the_part_carries_every_property_its_drawing_requires(monkeypatch) -> None:
    import _drawing_marks
    import _part_properties

    required = ast.literal_eval(
        next(
            k.value
            for k in _calls(drawing.__file__)["read_required_properties"].keywords
            if k.arg == "required"
        )
    )
    carried = dict(_part_properties.part_properties(part.PART_NAME))
    stamped: dict[str, str] = {}
    monkeypatch.setattr(
        _drawing_marks,
        "apply_custom_properties",
        lambda _adapter, props: stamped.update(props),
    )
    _drawing_marks.apply_drawing_properties(
        None,
        part.PART_NAME,
        {
            "Manufacturing Notes": notes.DRAWING_NOTES,
            "Isometric View Note": notes.ISOMETRIC_VIEW_NOTE,
        },
    )
    carried.update(stamped)
    missing = [name for name in required if not str(carried.get(name) or "").strip()]
    assert missing == []
    assert set(required) <= set(part._SAVED_DRAWING_PROPERTIES)
