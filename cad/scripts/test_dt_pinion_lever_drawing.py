"""Offline contracts for the pinion-engage-lever drawing."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import _sketch

import build_dt_pinion_lever as lever
import draw_dt_pinion_lever as drawing
import dt_pinion_lever_geometry
import dt_pinion_lever_spec
import export_features
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _gtol_face import SURFACE_CYLINDER, SURFACE_PLANE, SURFACE_SPHERE, FaceGeometry


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


def test_bore_is_the_reamer_and_slips_on_the_lift_rod() -> None:
    # U36: the pin carries the torque, so the bore only slides on the h-band
    # rod.  Fit audit F23: the .2510 reamer's size, no band; BORE_BAND is its
    # ANALYSIS band, never line-to-line.
    from _fit_shaft_h import SHAFT_H
    from dt_pinion_lift_rod_spec import ROD_DIA

    assert dt_pinion_lever_spec.BORE_BAND == (0.0127, 0.0)
    low, high = (
        dt_pinion_lever_spec.BORE + dt_pinion_lever_spec.BORE_BAND[1],
        dt_pinion_lever_spec.BORE + dt_pinion_lever_spec.BORE_BAND[0],
    )
    assert (round(low, 6), round(high, 6)) == (6.3754, 6.3881)
    min_clearance = low - (ROD_DIA + SHAFT_H[0])
    assert min_clearance > 0.0
    assert round(min_clearance, 6) == 0.0254
    assert drawing.BORE_CLEARANCE_IN == (0.001, 0.0023)
    # ENFORCE r1 (#1011): the end wall's own +/-0.25 rescued a wall and named
    # no mate, so it went; F23 took the bore's band off too.
    assert model_toleranced_dimensions(lever) == {}
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
    assert dt_pinion_lever_spec.SURFACE_FINISHES == ()


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


def test_hub_bore_names_its_fit_route_and_depth() -> None:
    import _config

    callout = drawing.DIMENSION_CALLOUTS["HubBore"]
    assert "<HOLE-DEPTH>" in callout.split("\n")[0]
    assert _config.parts("dt-pinion-lift-rod")["number"] in callout
    # Fit audit F23's recommended form: the reamer, the rod as the gauge, no
    # clearance row (rule 4 v2).
    assert callout.splitlines() == [
        "REAM <HOLE-DEPTH> (.32) FLAT BOTTOM;",
        "MHA-DT-17 ROD ENTERS BY HAND",
    ]
    assert "CLEARANCE" not in callout
    # Location and length dimensions carry no words (rule 7).
    assert set(drawing.DIMENSION_CALLOUTS) == {"HubBore", "PinHoleDia"}


def test_part_stamps_make_critical_drawing_properties() -> None:
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
    assert drawing.REFERENCE_SKETCHES is dt_pinion_lever_spec.REFERENCE_SKETCHES
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


def test_detail_fence_and_rod_axis_go_straight_to_the_database() -> None:
    # ENFORCE r2 (#1011): an inferred fence snapped to B and the crown apex
    # (a 6 mm detail), and GRIP AXIS had no rod axis to land on.
    # The rod axis runs from inside the hub to just past the fence.
    low, high = drawing.ROD_AXIS_MODEL_Y_MM
    assert low < dt_pinion_lever_spec.HUB_OD / 2.0 < drawing.DETAIL_RADIUS_MM < high


def test_station_references_are_points_and_hub_diameters_near_side() -> None:
    # ENFORCE r3 (#1011): detail B kept the reference lines the part showed
    # while it was dimensioned, and they read as hidden edges across the cut;
    # and both hub diameters crossed at the hub centre.

    assert drawing.NEAR_SIDE_DIAMETERS == ("HubOd", "HubBore")
    assert set(drawing.NEAR_SIDE_DIAMETERS) <= set(drawing.FRONT_KEEP)


_FEATURE_KINDS = {
    "mouth_face_b": "face",
    "hub": "boss",
    "crown": "profile",
    "grip_rod": "boss",
    "bore": "hole",
    "pin_hole": "hole",
}


def _in(value_in: float) -> float:
    return value_in * 25.4


def _plane(normal: tuple[float, float, float], offset_mm: float) -> FaceGeometry:
    point = tuple(value * offset_mm / 1000 for value in normal)
    return FaceGeometry(None, SURFACE_PLANE, (*normal, *point), normal, ())


def _cylinder(
    dia_mm: float, axis: tuple[float, float, float], box_mm: tuple[float, ...]
) -> FaceGeometry:
    r = dia_mm / 2000
    box = tuple(value / 1000 for value in box_mm)
    return FaceGeometry(None, SURFACE_CYLINDER, (0.0, 0.0, 0.0, *axis, r), None, box)


def test_the_lever_is_a_feature_export_part_with_one_owner_per_face() -> None:
    manifest = export_features.requirement_manifest("dt_pinion_lever")
    kinds = {name: feature["kind"] for name, feature in manifest["features"].items()}
    assert kinds == _FEATURE_KINDS
    assert manifest["construction"] == "one_piece"
    selectors = export_features.feature_selectors("dt_pinion_lever")
    geometry = dt_pinion_lever_geometry
    mouth = geometry.HUB_LEN / 2
    hub_r, rod_r = geometry.HUB_OD / 2, geometry.ROD_DIA / 2
    apex = mouth - geometry.OVERALL_FROM_B
    # The STEP inventory (faces.json): one face per surface below.
    expected = {
        "mouth_face_b": [_plane((0.0, 0.0, 1.0), mouth)],
        "hub": [_cylinder(geometry.HUB_OD, (0.0, 0.0, -1.0), (-hub_r, -hub_r, -mouth, hub_r, hub_r, mouth))],
        "crown": [
            FaceGeometry(
                None,
                SURFACE_SPHERE,
                (0.0, 0.0, (apex + geometry.CAP_RADIUS) / 1000, geometry.CAP_RADIUS / 1000),
                None,
                (),
            )
        ],
        "grip_rod": [
            _cylinder(geometry.ROD_DIA, (0.0, -1.0, 0.0), (-rod_r, 5.5, -rod_r, rod_r, geometry.ROD_LEN, rod_r)),
            _plane((0.0, 1.0, 0.0), geometry.ROD_LEN),
        ],
        "bore": [
            _cylinder(geometry.BORE, (0.0, 0.0, -1.0), (-3.175, -3.175, mouth - geometry.BORE_DEPTH, 3.175, 3.175, mouth)),
            _plane((0.0, 0.0, 1.0), mouth - geometry.BORE_DEPTH),
        ],
        "pin_hole": [
            _cylinder(geometry.PIN_HOLE_DIA, (1.0, 0.0, 0.0), (-hub_r, -0.8, 0.2, -3.0, 0.8, 1.8)),
            _cylinder(geometry.PIN_HOLE_DIA, (1.0, 0.0, 0.0), (3.0, -0.8, 0.2, hub_r, 0.8, 1.8)),
        ],
    }
    for name, faces in expected.items():
        for face in faces:
            owners = [
                owner
                for owner, specs in selectors.items()
                if any(selector.matches(face) for selector in specs)
            ]
            assert owners == [name], name


def test_lever_feature_bands_are_the_printed_ones() -> None:
    features = export_features.requirement_manifest("dt_pinion_lever")["features"]
    assert features["hub"]["dia"] == pytest.approx([_in(0.50), _in(0.52)])
    crown = features["crown"]
    assert crown["overall"] == pytest.approx([_in(0.48), _in(0.50)])
    assert crown["overall_from"] == "mouth_face_b"
    assert crown["radius"][1] - crown["radius"][0] == pytest.approx(_in(0.02))
    rod = features["grip_rod"]
    assert rod["dia"] == pytest.approx([_in(0.23), _in(0.25)])
    assert rod["length"] == pytest.approx([_in(3.38), _in(3.40)])
    assert rod["length_from"] == "hub"
    assert rod["station"] == pytest.approx([_in(0.19), _in(0.21)])
    assert rod["station_from"] == "mouth_face_b"
    assert rod["root_corner_r_max"] == pytest.approx(_in(0.040))
    assert rod["root_corner_exception"] == "RV-01"
    bore = features["bore"]
    assert bore["dia"] == pytest.approx([_in(0.2510), _in(0.2515)])
    assert bore["depth"] == pytest.approx([_in(0.31), _in(0.33)])
    assert bore["depth_from"] == "mouth_face_b"
    assert bore["flat_bottom"] is True and bore["process"] == "ream"
    assert bore["mate"] == dt_pinion_lever_spec.LIFT_ROD_NUMBER
    assert bore["callout"] == drawing.HUB_BORE_CALLOUT
    pin = features["pin_hole"]
    assert pin["dia"] == pytest.approx([_in(0.064), _in(0.068)], abs=1e-3)
    assert pin["station"] == pytest.approx([_in(0.15), _in(0.17)])
    assert pin["station_from"] == "mouth_face_b"
    assert pin["made_at"] == "assembly" and pin["thru"] is True
    assert pin["callout"] == dt_pinion_lever_spec.PIN_HOLE_CALLOUT
