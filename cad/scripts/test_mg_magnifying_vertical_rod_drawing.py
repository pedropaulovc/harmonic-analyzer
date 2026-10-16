"""Offline contracts for the magnifying-vertical-rod drawing (#1559)."""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

import build_mg_magnifying_vertical_rod as part
import draw_mg_magnifying_vertical_rod as drawing
import mg_magnifying_vertical_rod_geom as geom
import mg_magnifying_vertical_rod_spec as spec
import mg_rod_clamp_joint as joint
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import MACHINED_UM

_MARKED = {"RodDia", "BodyLength", "DomeR", "ThreadLength", "ReliefWidth", "ReliefDia"}


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/mg-magnifying-vertical-rod.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/mg-magnifying-vertical-rod.pdf")
    assert drawing.PNG.as_posix().endswith("/png/mg-magnifying-vertical-rod_drawing.png")
    assert (
        DRAWINGS_BY_NAME["mg_magnifying_vertical_rod"].script
        == Path(drawing.__file__).resolve()
    )


def test_rod_is_the_threaded_bar_of_the_joint_contract() -> None:
    assert (spec.ROD_DIA, spec.ROD_LENGTH) == (5.0, 132.5)
    assert spec.BODY_LENGTH == 125.0
    assert spec.SHOULDER_X == spec.ROD_THREAD_LEN == joint.ROD_THREAD_LEN == 7.50
    assert spec.ROD_THREAD_LEN_BAND == joint.ROD_THREAD_LEN_BAND == (0.25, -0.25)
    assert (spec.RELIEF_WIDTH, spec.RELIEF_WIDTH_BAND) == (1.40, (0.20, -0.20))
    assert (spec.RELIEF_DIA, spec.RELIEF_DIA_BAND) == (1.75, (0.10, -0.10))
    assert spec.THREAD == "#4-40" and spec.THREAD_CALLOUT == "#4-40 UNC"
    assert spec.THREAD_MAJOR == pytest.approx(2.845, abs=1e-3)
    assert spec.TIP_CHAMFER == pytest.approx(
        (spec.THREAD_MAJOR - spec.THREAD_BASIC_MINOR) / 2.0
    )
    assert spec.RELIEF_START_X == pytest.approx(7.50 - 1.40)
    # Full thread only (rule 18): one pitch at the tip, the run-out in the
    # relief; the worst-case engagement holds 1.5D.
    assert spec.FULL_THREAD_START_X == pytest.approx(0.635)
    assert spec.FULL_THREAD_END_X == pytest.approx(spec.RELIEF_START_X)
    assert joint.ENGAGEMENT_WORST == pytest.approx(5.015)
    assert joint.ENGAGEMENT_WORST >= joint.ENGAGEMENT_MIN == pytest.approx(4.2675)
    assert joint.RELIEF_WIDTH_MIN >= joint.DIE_RUNOUT
    assert joint.RELIEF_DIA_MAX <= joint.THREAD_ROOT_2A_MIN
    assert geom.SEAT_LAND_WORST >= geom.SEAT_LAND_MIN


def test_rod_is_one_front_plane_revolve() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert source.count("create_revolve(") == 1
    assert 'create_sketch("Front")' in source
    assert 'name_last_feature(adapter, "RodProfile")' in source
    assert 'name_last_feature(adapter, "Rod")' in source
    assert "create_extrusion(" not in source
    for name in _MARKED:
        assert re.search(rf'profile\.record\(\s*"{name}"', source), name
    assert "add_thread(" in source
    r, t, m, q = (
        spec.ROD_DIA / 2.0,
        spec.THREAD_MAJOR / 2.0,
        spec.THREAD_BASIC_MINOR / 2.0,
        spec.RELIEF_DIA / 2.0,
    )
    c = spec.TIP_CHAMFER
    v = (
        math.pi * c / 3.0 * (m * m + m * t + t * t)
        + math.pi * t * t * (spec.RELIEF_START_X - c)
        + math.pi * q * q * spec.RELIEF_WIDTH
        + math.pi * r * r * (spec.BODY_LENGTH - r)
        + 2.0 / 3.0 * math.pi * r**3
    )
    assert part.V_TOTAL == pytest.approx(v)


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert marked == _MARKED
    assert set(drawing.SIDE_KEEP).isdisjoint(drawing.DETAIL_KEEP)
    assert set(drawing.SIDE_KEEP) | set(drawing.DETAIL_KEEP) == marked
    assert set(drawing.DETAIL_KEEP) == {"ThreadLength", "ReliefWidth", "ReliefDia"}
    assert set(drawing.DIMENSION_CALLOUTS) <= marked
    assert drawing.DRAWING_PRECISION_BY_NAME == spec.DRAWING_PRECISION["RodProfile"]


def test_tolerances_are_native_on_the_model() -> None:
    assert model_toleranced_dimensions(part) == {
        ("RodProfile", "ThreadLength"): "*deviations(ROD_THREAD_LEN_BAND)",
        ("RodProfile", "ReliefWidth"): "*deviations(RELIEF_WIDTH_BAND)",
        ("RodProfile", "ReliefDia"): "*deviations(RELIEF_DIA_BAND)",
    }
    assert set(spec.DRAWING_BANDS) == {
        ("RodProfile", "ThreadLength"),
        ("RodProfile", "ReliefWidth"),
        ("RodProfile", "ReliefDia"),
    }
    precision = spec.DRAWING_PRECISION["RodProfile"]
    assert (precision["ThreadLength"], precision["ReliefWidth"], precision["ReliefDia"]) == (
        2,
        2,
        2,
    )
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in source
    # Both lengths read from the shoulder, the seating face (rule 10).
    assert drawing.ORIGIN_DIMENSIONS == ("BodyLength", "ThreadLength")
    assert drawing.DIMENSION_CALLOUTS == {
        "BodyLength": "FROM SHOULDER",
        "ThreadLength": "FROM SHOULDER",
    }


def test_notes_are_few_and_flagged() -> None:
    notes = spec.DRAWING_NOTES
    assert 1 <= len(notes.splitlines()) <= 4
    flat = " ".join(notes.splitlines())
    assert "Ø5 ROUND BAR" in flat
    assert "(132.5) REF" in flat
    assert "MHA-MG-002" in flat and "SEATS ON THE SHOULDER" in flat
    assert "BOTTOM END A FULL HEMISPHERE" in flat
    assert "BOTH ENDS" not in flat and "150" not in flat
    assert "BRASS" not in notes and "DEBURR" not in notes and "X.XX" not in notes
    assert "LOCTITE" not in notes and "SET SCREW" not in notes
    assert all(len(line) <= 80 for line in notes.splitlines())
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert drawing.THREAD_NOTE_TEXT.startswith("#4-40 UNC")
    assert source.count("add_attached_note(") == 1


def test_od_finish_and_no_gdt() -> None:
    assert [(c.key, c.roughness_um) for c in spec.SURFACE_FINISHES] == [
        ("mg_vrod_slide", MACHINED_UM)
    ]
    for module in (part, drawing):
        source = Path(module.__file__).read_text(encoding="utf-8")
        for token in ("add_feature_control_frame(", "add_datum_feature("):
            assert token not in source, (module.__name__, token)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_surface_finish(") == 1


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    assert drawing.VIEW_SCALE == (2, 1)
    assert drawing.DETAIL_SCALE == (8, 1)
    assert drawing.ISO_SCALE == (1, 1)
    assert spec.ISO_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Iso View Note"' in source
    # The fence holds the tip face and the shoulder's outer corner.
    fx, fy = drawing.DETAIL_FOCUS_MM
    for x, y in ((0.0, 0.0), (spec.SHOULDER_X, spec.ROD_DIA / 2.0)):
        assert math.hypot(x - fx, y - fy) < drawing.DETAIL_RADIUS_MM


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("mg-magnifying-vertical-rod")
    assert config["material"] == config["material_specification"]
    assert config["finish"]
    assert int(config["quantity"]) == 1
