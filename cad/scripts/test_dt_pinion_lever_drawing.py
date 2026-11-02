"""Offline contracts for the pinion-engage-lever drawing."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import _sketch

import build_dt_pinion_lever as lever
import draw_dt_pinion_lever as drawing
import dt_pinion_lever_geometry
import dt_pinion_lever_spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-pinion-lever.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-pinion-lever.pdf")
    assert drawing.PNG.as_posix().endswith("/png/dt-pinion-lever_drawing.png")
    assert DRAWINGS_BY_NAME["dt_pinion_lever"].script == Path(drawing.__file__).resolve()
    assert "draw_dt_pinion_lever.py" in PRECISION_MIGRATED_DRAWINGS


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert lever.DRAWING_DIMENSIONS is dt_pinion_lever_spec.DRAWING_DIMENSIONS
    assert lever.SURFACE_FINISHES is dt_pinion_lever_spec.SURFACE_FINISHES
    marked = set().union(*dt_pinion_lever_spec.DRAWING_DIMENSIONS.values())
    keeps = (drawing.FRONT_KEEP, drawing.TOP_KEEP, drawing.DETAIL_KEEP)
    kept = set().union(*keeps)
    assert kept == marked
    assert sum(len(keep) for keep in keeps) == len(marked)  # each dimension once
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    # The hub's axial stations all read from face B in the one hub detail.
    assert {
        "BoreDepthFromB",
        "OverallFromB",
        "GripFromB",
        "PinHoleFromB",
        "PinHoleDia",
    } == set(drawing.DETAIL_KEEP)


def test_bore_band_is_a_slip_fit_on_the_lift_rod() -> None:
    # U36: the pin carries the torque, so the bore only slides on the h-band
    # rod.  Codex P2 (#844): the repo's REAM_SLIDE band, never line-to-line.
    from _fit_ream_slide import REAM_SLIDE
    from _fit_shaft_h import SHAFT_H
    from dt_pinion_lift_rod_spec import ROD_DIA

    assert dt_pinion_lever_spec.BORE_BAND == REAM_SLIDE
    low, high = (
        dt_pinion_lever_spec.BORE + dt_pinion_lever_spec.BORE_BAND[1],
        dt_pinion_lever_spec.BORE + dt_pinion_lever_spec.BORE_BAND[0],
    )
    assert (round(low, 6), round(high, 6)) == (6.3754, 6.3881)
    min_clearance = low - (ROD_DIA + SHAFT_H[0])
    assert min_clearance > 0.0
    assert round(min_clearance, 6) == 0.0254
    # ENFORCE r1 (#1011): the bore is the one band; the end wall's own
    # +/-0.25 rescued a wall and named no mate, so it went.
    assert model_toleranced_dimensions(lever) == {
        ("BarrelProfile", "HubBore"): "*deviations(BORE_BAND)",
    }
    assert dt_pinion_lever_spec.DRAWING_PRECISION_BY_NAME["HubBore"] == 4
    assert not hasattr(dt_pinion_lever_spec, "END_WALL_TOLERANCE_MM")


def test_end_wall_holds_rule_17_from_the_two_x_baselines() -> None:
    # Bore depth and overall length to the crown apex both print .XX from B;
    # the end wall is what they leave, at the worst of both bands.
    from _inch_wall_limits import WALL_TARGET_MM

    spec = dt_pinion_lever_spec
    assert spec.DRAWING_PRECISION_BY_NAME["BoreDepthFromB"] == 2
    assert spec.DRAWING_PRECISION_BY_NAME["OverallFromB"] == 2
    assert spec.OVERALL_FROM_B == pytest.approx(spec.HUB_LEN + spec.CAP_SAG)
    assert spec.OVERALL_FROM_B == pytest.approx(0.49 * 25.4)
    assert spec.END_WALL_ON_AXIS_WORST == pytest.approx(0.15 * 25.4)
    # ENFORCE r5 (minor): the shallow sagitta once left the floor's corner thin.
    assert spec.END_WALL_AT_FLOOR_CORNER_WORST >= WALL_TARGET_MM


def test_grip_rod_is_a_straight_six() -> None:
    # User ruling 2026-09-24 (ch25 page002_img07): the photo's "6 mm" sits
    # beside the hub and root and tip read the same width -- no taper.
    assert dt_pinion_lever_geometry.ROD_DIA == pytest.approx(0.24 * 25.4)  # #290 .XX
    assert not hasattr(dt_pinion_lever_geometry, "ROD_ROOT_DIA")
    assert not hasattr(dt_pinion_lever_geometry, "ROD_TIP_DIA")
    assert dt_pinion_lever_spec.DRAWING_DIMENSIONS["RodProfile"] == {"RodTipY", "RodDia"}
    assert dt_pinion_lever_spec.DRAWING_PRECISION_BY_NAME["RodDia"] == 2
    # The rod's base stays clear of the bore and the pin hole it rises over.
    assert dt_pinion_lever_geometry.ROD_Y0 > dt_pinion_lever_geometry.BORE / 2.0
    assert dt_pinion_lever_geometry.ROD_Y0 > dt_pinion_lever_geometry.PIN_HOLE_DIA / 2.0
    # The rod's z band stays inside the hub.
    assert dt_pinion_lever_geometry.ROD_DIA < dt_pinion_lever_geometry.HUB_LEN


def test_pin_hole_sits_at_mid_engagement() -> None:
    geometry = dt_pinion_lever_geometry
    assert geometry.PIN_HOLE_DIA == pytest.approx(0.064 * 25.4)  # fit F15
    assert geometry.PIN_HOLE_FROM_MOUTH == geometry.BORE_DEPTH / 2.0
    assert geometry.PIN_HOLE_FROM_MOUTH == pytest.approx(0.16 * 25.4)
    assert geometry.PIN_HOLE_Z == geometry.HUB_LEN / 2.0 - geometry.PIN_HOLE_FROM_MOUTH


def test_sheet_carries_no_gdt_finish_or_literal_precision() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "add_feature_control_frame",
        "add_datum_feature",
        "add_native_axis_datum",
        "add_surface_finish",
        "add_attached_note",
        "SetPrecision3",
    ):
        assert forbidden not in source, forbidden
    assert dt_pinion_lever_spec.SURFACE_FINISHES == ()
    assert "assert_imported_precision" in source
    assert source.count("dimensions_by_feature=DRAWING_DIMENSIONS") == 3


def test_sheet_runs_at_1_to_1_with_a_3_to_1_detail_of_section_a_a() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    assert drawing.SECTION_SCALE == (1, 1)
    assert drawing.DETAIL_SCALE == (3, 1)
    # The cut runs down the grip axis from below the hub to past the tip.
    (x0, y0, z0), (x1, y1, z1) = drawing.SECTION_LINE_MODEL_MM
    assert x0 == x1 == z0 == z1 == 0.0
    assert y0 < -dt_pinion_lever_spec.HUB_OD / 2.0
    assert y1 > dt_pinion_lever_spec.ROD_LEN
    # The detail fence takes the whole hub, crown apex included.
    apex = dt_pinion_lever_spec.HUB_LEN / 2.0 + dt_pinion_lever_spec.CAP_SAG
    assert drawing.DETAIL_RADIUS_MM > apex
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 1)" in source
    assert dt_pinion_lever_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(lever.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    assert "apply_drawing_precision" in source
    import _config

    spec = _config.parts("dt-pinion-lever")
    assert spec["material"] == spec["material_specification"]
    assert spec["material_specification"]
    assert spec["finish"]
    assert "fit_class" not in spec
    assert int(spec["quantity"]) == 1


class _SketchFeature:
    def __init__(self) -> None:
        self.Visible = 2  # swVisibilityState_e: shown


class _PartDoc:
    def __init__(self, names) -> None:
        self.features = {name: _SketchFeature() for name in names}

    def FeatureByName(self, name):  # noqa: N802 - the COM member name
        return self.features.get(name)


def _run_blank(monkeypatch, module, sketches, *, blanks: bool) -> list[str]:
    doc = _PartDoc(sketches)
    blanked: list[str] = []

    def fake_blank(_adapter, name) -> None:
        blanked.append(name)
        if blanks:
            doc.features[name].Visible = 1  # swVisibilityState_e: hidden

    monkeypatch.setattr(module, "blank_sketch", fake_blank)
    monkeypatch.setattr(module, "_early_bound", lambda obj, _interface: obj)
    module.blank_reference_sketches(SimpleNamespace(currentModel=doc), sketches)
    return blanked


def _with_block(source: str, opener: str) -> tuple[str, str]:
    """The header and body of the one ``with`` statement starting ``opener``."""
    lines = source.split("\n")
    (start,) = [i for i, line in enumerate(lines) if line.strip().startswith(opener)]
    indent = len(lines[start]) - len(lines[start].lstrip())
    header = [lines[start]]
    rest = iter(lines[start + 1 :])
    while not header[-1].rstrip().endswith(":"):
        header.append(next(rest))
    body = []
    for line in rest:
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            break
        body.append(line)
    return "\n".join(header), "\n".join(body)


def test_station_reference_sketches_are_saved_hidden() -> None:
    # #880 (Main, via dtrefactor): the lever's two station sketches rendered
    # in the drive-train; the part saves them hidden.
    expected = (
        "GripStationReference",
        "PinHoleStationReference",
        "BoreDepthReference",
        "OverallLengthReference",
    )
    assert dt_pinion_lever_spec.REFERENCE_SKETCHES == expected
    assert set(expected) == {
        name
        for name in dt_pinion_lever_spec.DRAWING_DIMENSIONS
        if name.endswith("Reference")
    }
    source = Path(lever.__file__).read_text(encoding="utf-8")
    assert set(re.findall(r'"(\w+Reference)"', source)) == set(expected)
    blank = "blank_reference_sketches(adapter, REFERENCE_SKETCHES)"
    # One shared helper in _sketch (restricted review), no local copy.
    assert "def _blank_reference_sketches" not in source
    assert source.count(blank) == 1
    assert source.index(blank) < source.rindex(
        "save_part_and_images(adapter, PART_NAME)"
    )


def test_station_reference_blank_reads_every_sketch_back_hidden(monkeypatch) -> None:
    sketches = dt_pinion_lever_spec.REFERENCE_SKETCHES
    assert _run_blank(monkeypatch, _sketch, sketches, blanks=True) == list(sketches)
    with pytest.raises(RuntimeError, match="GripStationReference still visible"):
        _run_blank(monkeypatch, _sketch, sketches, blanks=False)


def test_hub_detail_is_created_and_dimensioned_while_the_part_shows_them() -> None:
    # A detail takes a hidden sketch's visibility from the part when it is
    # created and refuses the per-view override (_drawing_hidden_sketches), so
    # section A-A and its detail are created and curated inside
    # part_sketches_shown.
    source = Path(drawing.__file__).read_text(encoding="utf-8").replace("\r\n", "\n")
    assert "from _drawing_hidden_sketches import" in source
    imports = [
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom)
    ]
    assert any(
        node.module == "_drawing_hidden_sketches"
        and any(alias.name == "curate_view_dimensions" for alias in node.names)
        for node in imports
    )
    assert not any(
        node.module != "_drawing_hidden_sketches"
        and any(alias.name == "curate_view_dimensions" for alias in node.names)
        for node in imports
    )
    assert drawing.REFERENCE_SKETCHES is dt_pinion_lever_spec.REFERENCE_SKETCHES
    opened = source.index("await adapter.open_model(str(SOURCE))")
    captured = source.index("source_model = adapter.currentModel")
    assert opened < captured < source.index("new_project_drawing(")
    header, block = _with_block(source, "with part_sketches_shown(")
    assert "source_model" in header
    assert "REFERENCE_SKETCHES" in header
    # The section's items select through the front view it is cut from, so
    # that view shows them too.
    assert "base_view=front" in header
    assert "_lever_section(adapter, front)" in block
    assert "_hub_detail(adapter, section)" in block
    assert "set_hidden_lines_removed(adapter, detail)" in block
    assert "keep=DETAIL_KEEP" in block
    assert "auto_center_marks" not in block
    # Every sketch the block shows keeps a dimension in the detail; the
    # projected views dimension none of them.
    reference_dims = set().union(
        *(
            dt_pinion_lever_spec.DRAWING_DIMENSIONS[name]
            for name in dt_pinion_lever_spec.REFERENCE_SKETCHES
        )
    )
    assert reference_dims <= set(drawing.DETAIL_KEEP)
    assert not reference_dims & (set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP))


def test_every_projected_view_and_the_section_hide_their_hidden_lines() -> None:
    # PR #1436: the isometric stays in the hidden-lines loop.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "for view in (front, top, iso):" in source
    assert "set_hidden_lines_removed(adapter, section)" in source
    assert '"*Right"' not in source


def test_detail_fence_and_rod_axis_go_straight_to_the_database() -> None:
    # ENFORCE r2 (#1011): an inferred fence snapped to B and the crown apex
    # (a 6 mm detail), and GRIP AXIS had no rod axis to land on.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for name in ("_hub_detail", "_rod_axis_in_detail"):
        body = source[source.index(f"def {name}(") :]
        body = body[: body.index("\ndef ")]
        assert "manager.AddToDB = True" in body, name
    assert "_rod_axis_in_detail(adapter, detail)" in source
    assert "circle.SetLabelPosition(*DETAIL_LETTER_XY)" in source
    # The rod axis runs from inside the hub to just past the fence.
    low, high = drawing.ROD_AXIS_MODEL_Y_MM
    assert low < dt_pinion_lever_spec.HUB_OD / 2.0 < drawing.DETAIL_RADIUS_MM < high


def test_station_references_are_points_and_hub_diameters_near_side() -> None:
    # ENFORCE r3 (#1011): detail B kept the reference lines the part showed
    # while it was dimensioned, and they read as hidden edges across the cut;
    # and both hub diameters crossed at the hub centre.
    import build_dt_pinion_lever

    source = Path(build_dt_pinion_lever.__file__).read_text(encoding="utf-8")
    body = source[source.index("async def _station_reference(") :]
    body = body[: body.index("\nasync def ")]
    assert body.count("_add_reference_point(") == 2
    assert "add_line" not in body
    assert drawing.NEAR_SIDE_DIAMETERS == ("HubOd", "HubBore")
    assert set(drawing.NEAR_SIDE_DIAMETERS) <= set(drawing.FRONT_KEEP)
    draw_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'set_near_side_diameter(matches[0], f"lever {name}")' in draw_source
