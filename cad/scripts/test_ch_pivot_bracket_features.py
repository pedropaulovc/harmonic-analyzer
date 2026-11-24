"""Feature-export declarations of the rocker pivot bracket (MHA-CH-08): one
owner per face, the bands the sheet prints, and its (empty) general notes."""

from __future__ import annotations

import pytest

import ch_pivot_bracket_drawing_spec as drawing_spec
import ch_pivot_bracket_notes as notes
import ch_pivot_bracket_spec as spec
import draw_ch_pivot_bracket as drawing
import export_features
from _gtol_face import FaceGeometry
from _hole_spec import blind_cut_dia_mm
from _surface_finish import SEAT_UM
from ch_pivot_bracket_sides import FOOT_Z1, HOLE_Z

_STEM = "ch_pivot_bracket"
_FEATURE_KINDS = {
    "seat": "face",
    "foot_top": "face",
    "west_side": "face",
    "east_side": "face",
    "inboard_face": "face",
    "outboard_face": "face",
    "foot_end": "face",
    "arch": "arc",
    "bore": "hole",
    "hold_down": "hole",
    "apex_tap": "threaded_hole",
    "inside_corner": "fillet",
}
_AXES = {"x": 0, "y": 1, "z": 2}


def _in(value_in: float) -> float:
    """Millimetres of a printed inch value."""
    return value_in * 25.4


def _plane(normal: tuple[float, float, float], offset_mm: float) -> FaceGeometry:
    point = tuple(value * offset_mm / 1000 for value in normal)
    return FaceGeometry(None, 4001, (*normal, *point), normal, ())


def _cylinder(
    dia_mm: float, axis: tuple[float, float, float], box_mm: tuple[float, ...]
) -> FaceGeometry:
    box = tuple(value / 1000 for value in box_mm)
    return FaceGeometry(None, 4002, (0.0, 0.0, 0.0, *axis, dia_mm / 2000), None, box)


def test_the_bracket_is_a_feature_export_part_with_one_owner_per_face() -> None:
    assert _STEM in export_features.SUPPORTED_PARTS
    manifest = export_features.requirement_manifest(_STEM)
    kinds = {name: feature["kind"] for name, feature in manifest["features"].items()}
    assert kinds == _FEATURE_KINDS
    assert manifest["construction"] == "one_piece"
    selectors = export_features.feature_selectors(_STEM)
    w, t = spec.FOOT_W / 2, spec.EAR_T / 2
    arch_r, bore_r = spec.EAR_ARCH_R, spec.BORE_DIA / 2
    arch_y = spec.BORE_H + spec.ARCH_LIFT
    hole_r = spec.HOLE_DIA / 2
    tap_dia = blind_cut_dia_mm(spec.SET_SCREW_HOLE_SPEC)
    tap_r = tap_dia / 2
    corner_r = drawing_spec.CORNER_R_MAX
    expected = {
        "seat": _plane((0.0, -1.0, 0.0), 0.0),
        "foot_top": _plane((0.0, 1.0, 0.0), spec.FOOT_H),
        "west_side": _plane((-1.0, 0.0, 0.0), w),
        "east_side": _plane((1.0, 0.0, 0.0), w),
        "inboard_face": _plane((0.0, 0.0, -1.0), -spec.FOOT_Z0),
        "outboard_face": _plane((0.0, 0.0, 1.0), t),
        "foot_end": _plane((0.0, 0.0, 1.0), FOOT_Z1),
        "arch": _cylinder(
            2 * arch_r, (0.0, 0.0, 1.0), (-w, arch_y, -t, w, spec.EAR_TOP_Y, t)
        ),
        "bore": _cylinder(
            spec.BORE_DIA,
            (0.0, 0.0, 1.0),
            (-bore_r, spec.BORE_H - bore_r, -t, bore_r, spec.BORE_H + bore_r, t),
        ),
        "hold_down": _cylinder(
            spec.HOLE_DIA,
            (0.0, 1.0, 0.0),
            (-hole_r, 0.0, HOLE_Z - hole_r, hole_r, spec.FOOT_H, HOLE_Z + hole_r),
        ),
        "apex_tap": _cylinder(
            tap_dia,
            (0.0, 1.0, 0.0),
            (-tap_r, spec.BORE_H, -tap_r, tap_r, spec.EAR_TOP_Y, tap_r),
        ),
        "inside_corner": _cylinder(
            2 * corner_r,
            (1.0, 0.0, 0.0),
            (-w, spec.FOOT_H, t, w, spec.FOOT_H + corner_r, t + corner_r),
        ),
    }
    assert set(expected) == set(_FEATURE_KINDS)
    for name, face in expected.items():
        owners = [
            owner
            for owner, specs in selectors.items()
            if any(selector.matches(face) for selector in specs)
        ]
        assert owners == [name], name


def test_general_notes_are_the_sheets_none() -> None:
    manifest = export_features.requirement_manifest(_STEM)
    assert notes.DRAWING_NOTES == ""
    assert manifest["notes"]["manufacturing"] == []


def test_bracket_feature_bands_are_the_printed_ones() -> None:
    features = export_features.requirement_manifest(_STEM)["features"]
    seat = features["seat"]
    assert seat["finish_ra"] == SEAT_UM and seat["finish_callout"] == "125"
    assert features["foot_top"]["height"] == pytest.approx([_in(0.23), _in(0.25)])
    assert features["east_side"]["width"] == pytest.approx([_in(0.63), _in(0.65)])
    ear = features["outboard_face"]
    assert ear["thickness"] == pytest.approx([_in(0.316), _in(0.324)])
    assert ear["callout"] == drawing.DIMENSION_CALLOUTS["EarThick"]
    assert features["foot_end"]["length"] == pytest.approx([_in(0.69), _in(0.71)])
    arch = features["arch"]
    assert arch["radius"] == pytest.approx([_in(0.31), _in(0.33)])
    assert arch["overall_height"] == pytest.approx([_in(1.37), _in(1.39)])
    # (.39) REF: the bore axis to the apex, a reference with no band.
    assert arch["apex_above_bore_ref"] == spec.APEX_ABOVE_BORE
    assert round(arch["apex_above_bore_ref"] / 25.4, 2) == 0.39
    assert arch["center"][1] + arch["radius_nominal"] == pytest.approx(spec.EAR_TOP_Y)
    bore = features["bore"]
    assert bore["dia"] == pytest.approx([6.528, 6.6296])  # F, +.004/0
    assert bore["process"] == "F DRILL" and bore["drill"] == "F" and bore["thru"] is True
    assert bore["callout"] == drawing.DIMENSION_CALLOUTS["ShaftBoreDia"]
    assert bore["height"] == pytest.approx([_in(0.98), _in(1.00)])
    assert bore["lateral"] == pytest.approx([_in(0.31), _in(0.33)])
    hold_down = features["hold_down"]
    # The #8 close clearance drill at the title block's DRILLED HOLES +.004/0.
    assert hold_down["dia"] == pytest.approx([_in(0.180), _in(0.184)])
    assert hold_down["process"] == "drill" and hold_down["thru"] is True
    assert hold_down["station"] == pytest.approx([_in(0.49), _in(0.51)])
    assert hold_down["lateral"] == pytest.approx([_in(0.31), _in(0.33)])
    tap = features["apex_tap"]
    assert tap["thread"] == "#4-40 UNC-2B"
    assert tap["dia"] == pytest.approx([_in(0.089), _in(0.093)], abs=1e-3)
    assert tap["into"] == "bore" and tap["extent"] == drawing.SET_SCREW_EXTENT
    assert tap["mates"] == drawing.SET_SCREW_MATE
    assert tap["station"] == pytest.approx([_in(0.15), _in(0.17)])
    corner = features["inside_corner"]
    assert corner["radius"] == pytest.approx([0.0, _in(0.02)])
    assert corner["callout"] == drawing.DIMENSION_CALLOUTS["CornerRadius"]


def _coordinate(feature: dict, axis: int) -> float:
    if feature["kind"] == "face":
        return feature["plane"]["value"]
    return feature["at"][axis]


def test_located_nominals_measure_from_their_faces() -> None:
    """The adapter's `_from` check: the feature's coordinate along its datum
    face's axis lies the nominal off that face; the tap meets the bore."""
    features = export_features.requirement_manifest(_STEM)["features"]
    checked = 0
    for feature in features.values():
        for key, datum in feature.items():
            if not key.endswith("_from"):
                continue
            base = key.removesuffix("_from")
            plane = features[datum]["plane"]
            axis = _AXES[plane["axis"]]
            distance = abs(_coordinate(feature, axis) - plane["value"])
            assert distance == pytest.approx(abs(feature[f"{base}_nominal"]), abs=1e-3)
            low, high = feature[base]
            assert low <= feature[f"{base}_nominal"] <= high
            checked += 1
    assert checked == 9
    tap, bore = features["apex_tap"], features["bore"]
    assert tap["at"][0] == bore["at"][0] and tap["at"][2] == 0.0
    assert tap["axis"] == [0.0, -1.0, 0.0] and bore["axis"] == [0.0, 0.0, -1.0]
