"""Offline contracts for the magnifying-wheel drum (MHA-MG-10) drawing."""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

import _config
import build_mg_wheel_drum as part
import draw_mg_wheel_drum as drawing
import mg_magnifying_wheel_geom as wheel_geom
import mg_wheel_drum_geom
import mg_wheel_drum_spec as spec
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/mg-wheel-drum.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/mg-wheel-drum.pdf")
    assert DRAWINGS_BY_NAME["mg_wheel_drum"].script == Path(drawing.__file__).resolve()


def test_dimension_transfer_uses_shared_helper() -> None:
    from _drawing_dimensions import move_model_dimension

    assert drawing.move_model_dimension is move_model_dimension


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.RIGHT_KEEP)
    assert set(drawing.DIMENSION_CALLOUTS) <= marked
    assert {
        (feature, name)
        for feature, names in spec.DRAWING_PRECISION.items()
        for name in names
    } == {
        (feature, name)
        for feature, names in spec.DRAWING_DIMENSIONS.items()
        for name in names
    }
    assert drawing.DRAWING_PRECISION_BY_NAME == {
        name: digits
        for names in spec.DRAWING_PRECISION.values()
        for name, digits in names.items()
    }


def test_every_size_carries_its_band_on_the_model() -> None:
    # The O.D. has no fit: it takes the title block's .XX row.
    assert model_toleranced_dimensions(part) == {
        ("RingProfile", "DrumBore"): "*deviations(DRUM_BORE_BAND)",
        ("Drum", "DrumLen"): "*deviations(DRUM_LEN_BAND)",
    }
    # drawing-guidelines.md rule 17 (walls and webs) at the worst printed
    # corner: the O.D. printed .74 -.01 over the .4990 +.0005 reamed bore.
    assert mg_wheel_drum_geom.WALL_WORST == pytest.approx((0.73 - 0.4995) * 25.4 / 2.0)
    assert mg_wheel_drum_geom.WALL_WORST >= mg_wheel_drum_geom.MIN_WALL


def test_drum_presses_on_the_wheel_spigot_never_proud() -> None:
    # Reamed bore, made first; the spigot is turned to the stated interference in it.
    assert spec.DRUM_BORE == pytest.approx(0.499 * 25.4)
    assert spec.DRUM_BORE == wheel_geom.SPIGOT_DIA
    assert wheel_geom.DRUM_PRESS == pytest.approx((0.0002 * 25.4, 0.0013 * 25.4))
    # The drum's .354 on the inch grid; the spigot keeps its 9.0 hub station,
    # each model inside its printed band, and the drum's minus-only length
    # against the spigot's plus-only length keeps its face under the spigot's.
    assert spec.DRUM_LEN == pytest.approx(0.354 * 25.4)
    assert spec.DRUM_LEN <= wheel_geom.SPIGOT_LEN
    assert spec.DRUM_LEN_BAND == pytest.approx((0.0, -0.004 * 25.4))
    assert wheel_geom.SPIGOT_LEN_BAND == pytest.approx((0.004 * 25.4, 0.0))
    assert wheel_geom.DRUM_RECESS == pytest.approx((0.0, 0.008 * 25.4), abs=1e-9)
    assert (
        part.V_DRUM
        == math.pi
        * ((spec.DRUM_OD / 2.0) ** 2 - (spec.DRUM_BORE / 2.0) ** 2)
        * spec.DRUM_LEN
    )


def test_registry_row() -> None:
    row = _config.parts("mg-wheel-drum")
    assert row["number"] == "MHA-MG-10"
    assert int(row["quantity"]) == 1
    assert "C36000" in str(row["material_specification"])
    assert part.MATERIAL == "Brass"


def _calls(path: str) -> dict[str, ast.Call]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return {
        node.func.id: node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_the_part_carries_every_property_its_drawing_requires(monkeypatch) -> None:
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
    stamp = build_calls["apply_drawing_properties"]
    assert [ast.unparse(a) for a in stamp.args] == ["adapter", "PART_NAME"]
    assert stamp.lineno < build_calls["save_part_and_images"].lineno
    stamped: dict[str, str] = {}
    monkeypatch.setattr(
        _drawing_marks,
        "apply_custom_properties",
        lambda _adapter, props: stamped.update(props),
    )
    _drawing_marks.apply_drawing_properties(None, part.PART_NAME)
    carried.update(stamped)
    missing = [name for name in required if not str(carried.get(name) or "").strip()]
    assert missing == []


def test_pressed_bore_carries_no_finish_and_no_gdt() -> None:
    # drawing-guidelines.md rule 6: a pressed bore neither runs nor slides.
    names = set(_calls(drawing.__file__))
    assert not names & {
        "add_datum_feature",
        "add_feature_control_frame",
        "add_surface_finish",
    }
    assert spec.SURFACE_FINISHES == ()
