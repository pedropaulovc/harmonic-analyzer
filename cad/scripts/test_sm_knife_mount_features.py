"""Feature-export contracts for the knife mount (MHA-SM-02): the declarations
in ``draw_sm_knife_mount`` name one STEP face each and carry the bands, frames
and BASIC locations the sheet prints."""

from __future__ import annotations

import pytest

import draw_sm_knife_mount as drawing
import export_features
import sm_knife_mount_notes as notes
import sm_knife_mount_spec as spec
from _gtol_face import FaceGeometry
from _hole_spec import blind_cut_dia_mm
from _surface_finish import MACHINED_UM, SEAT_UM
from build_sm_knife_mount import BORE_CENTRE_DEPTH

_STEM = "sm_knife_mount"
_MM_PER_IN = 25.4

_FEATURE_KINDS = {
    "top_seat": "face",
    "bottom_face": "face",
    "plus_x_side": "face",
    "minus_x_side": "face",
    "front_face": "face",
    "back_face": "face",
    "knife_bore": "hole",
    "dowel_hole": "hole",
    "stud_tap": "threaded_hole",
}


def _in(value_in: float) -> float:
    return value_in * _MM_PER_IN


def _plane(normal: tuple[float, float, float], offset_mm: float) -> FaceGeometry:
    point = tuple(value * offset_mm / 1000 for value in normal)
    return FaceGeometry(None, 4001, (*normal, *point), normal, ())


def _cylinder(
    dia_mm: float, axis: tuple[float, float, float], box_mm: tuple[float, ...]
) -> FaceGeometry:
    box = tuple(value / 1000 for value in box_mm)
    return FaceGeometry(None, 4002, (0.0, 0.0, 0.0, *axis, dia_mm / 2000), None, box)


def _manifest() -> dict:
    return export_features.requirement_manifest(_STEM)


def test_the_mount_is_a_feature_export_part_with_one_owner_per_face() -> None:
    assert _STEM in export_features.SUPPORTED_PARTS
    manifest = _manifest()
    kinds = {name: feature["kind"] for name, feature in manifest["features"].items()}
    assert kinds == _FEATURE_KINDS
    assert manifest["construction"] == "one_piece"
    assert notes.DRAWING_NOTES == ""
    assert manifest["notes"]["manufacturing"] == notes.DRAWING_NOTES.splitlines()
    selectors = export_features.feature_selectors(_STEM)
    half_x, half_z = spec.BLK_HALF_X, spec.SUPPORT_Z_THICK / 2
    bore_r = spec.R_BORE
    pin_r = spec.PIN_HOLE_DIA / 2
    tap_dia = blind_cut_dia_mm(spec.STUD_TAP_SPEC)
    tap_r = tap_dia / 2
    expected = {
        "top_seat": [_plane((0.0, 1.0, 0.0), spec.BLK_TOP)],
        "bottom_face": [_plane((0.0, -1.0, 0.0), -spec.BLK_BOT)],
        "plus_x_side": [_plane((1.0, 0.0, 0.0), half_x)],
        "minus_x_side": [_plane((-1.0, 0.0, 0.0), half_x)],
        "front_face": [_plane((0.0, 0.0, 1.0), half_z)],
        "back_face": [_plane((0.0, 0.0, -1.0), half_z)],
        "knife_bore": [
            _cylinder(
                2 * bore_r,
                (0.0, 0.0, 1.0),
                (-bore_r, spec.BORE_CY - bore_r, -half_z, bore_r, spec.BORE_CY + bore_r, half_z),
            )
        ],
        "dowel_hole": [
            _cylinder(
                spec.PIN_HOLE_DIA,
                (0.0, 1.0, 0.0),
                (
                    spec.PIN_HOLE_X - pin_r,
                    spec.BLK_TOP - spec.PIN_HOLE_DEPTH,
                    -pin_r,
                    spec.PIN_HOLE_X + pin_r,
                    spec.BLK_TOP,
                    pin_r,
                ),
            )
        ],
        "stud_tap": [
            _cylinder(
                tap_dia,
                (0.0, 1.0, 0.0),
                (
                    -tap_r,
                    spec.BLK_TOP - spec.STUD_TAP_DRILL_DEPTH,
                    -tap_r,
                    tap_r,
                    spec.BLK_TOP,
                    tap_r,
                ),
            )
        ],
    }
    assert set(expected) == set(_FEATURE_KINDS)
    for name, faces in expected.items():
        for face in faces:
            owners = [
                owner
                for owner, specs in selectors.items()
                if any(selector.matches(face) for selector in specs)
            ]
            assert owners == [name], name


def test_mount_feature_bands_are_the_printed_ones() -> None:
    features = _manifest()["features"]
    seat = features["top_seat"]
    assert seat["finish_ra"] == SEAT_UM and seat["datum"] == "A"
    assert features["bottom_face"]["height"] == pytest.approx([_in(1.16), _in(1.18)])
    assert features["minus_x_side"]["width"] == pytest.approx([_in(0.99), _in(1.01)])
    assert features["back_face"]["depth"] == pytest.approx([_in(0.54), _in(0.56)])

    bore = features["knife_bore"]
    # Ø.4985 +.0015/.0000 REAM THRU, RUNNING FIT ON MHA-SM-03 TRUNNION, Ra 63
    # (owner ruling 2026-11-23, tool audit Q13).
    assert bore["dia"] == pytest.approx([_in(0.4985), _in(0.5000)])
    assert bore["precision"]["dia"] == 4
    assert bore["process"] == "ream" and bore["thru"] is True
    assert bore["callout"] == drawing.DIMENSION_CALLOUTS["BoreDia"]
    assert bore["mates"] == drawing.LEVER_NUMBER
    assert bore["finish_ra"] == MACHINED_UM
    assert bore["datum"] == "C"
    # ⌖Ø.008|A|B at BASIC .824 under A and .300 from B; ∥.002|A.
    assert bore["position_dia"] == pytest.approx(_in(0.008))
    assert bore["position_datums"] == ["A", "B"]
    assert bore["basic_from_a"] == pytest.approx(_in(0.824), abs=_in(0.0005))
    assert bore["basic_from_a"] == pytest.approx(BORE_CENTRE_DEPTH)
    assert bore["basic_from_b"] == pytest.approx(_in(0.300))
    assert bore["parallelism"] == pytest.approx(_in(0.002))
    assert bore["parallelism_datums"] == ["A"]

    pin = features["dowel_hole"]
    # Ø.1285 #30 DRILL ↧ (.37), MHA-SM-VN-53 DOWEL (owner ruling 2026-11-24,
    # fit audit OQ19: the DRILLED HOLES row, .1285-.1325); ⊥Ø.001|A.
    assert pin["dia"] == pytest.approx([_in(0.1285), _in(0.1325)])
    assert pin["depth"] == pytest.approx([_in(0.36), _in(0.38)])
    assert pin["process"] == "drill" and pin["drill_point"] is True
    assert pin["callout"] == drawing.DIMENSION_CALLOUTS["PinHoleDia"]
    assert pin["mates"] == drawing.DOWEL_NUMBER
    assert "clearance" not in pin
    assert pin["datum"] == "B"
    assert pin["perpendicularity"] == pytest.approx(_in(0.001))
    assert pin["side"] == pytest.approx([_in(0.19), _in(0.21)])
    assert pin["row"] == pytest.approx([_in(0.265), _in(0.285)])

    tap = features["stud_tap"]
    # #25 DRILL ↧ .438±.002 X 118°, 10-24 UNC ↧ .375; ⌖Ø.005|A|B|C.
    assert tap["thread"] == "#10-24 UNC-2B"
    assert tap["drill"] == "#25" and tap["tap"] == "bottoming"
    assert tap["dia"] == pytest.approx([_in(0.1495), _in(0.1535)])
    assert tap["drill_depth"] == pytest.approx([_in(0.436), _in(0.440)])
    assert tap["thread_depth"] == pytest.approx([_in(0.370), _in(0.380)])
    assert tap["point_angle_deg"] == 118.0 and tap["point_angle_tol_deg"] == 1.0
    assert tap["callout_reason"] == spec.TAP_CALLOUT_REASON
    assert tap["position_dia"] == pytest.approx(_in(0.005))
    assert tap["position_datums"] == ["A", "B", "C"]
    assert tap["basic_from_b"] == pytest.approx(_in(0.300))


def test_the_holes_stand_where_the_frames_put_them() -> None:
    features = _manifest()["features"]
    bore, pin, tap = (features[n] for n in ("knife_bore", "dowel_hole", "stud_tap"))
    top = features["top_seat"]["plane"]["value"]
    # The bore's BASIC depth under A and the tap and bore on one vertical
    # centre plane, BASIC .300 from B's axis.
    assert top - bore["at"][1] == pytest.approx(bore["basic_from_a"])
    assert pin["at"][0] - tap["at"][0] == pytest.approx(tap["basic_from_b"])
    assert pin["at"][0] - bore["at"][0] == pytest.approx(bore["basic_from_b"])
    # B's side and row locations close on the faces they are printed from.
    assert features["plus_x_side"]["plane"]["value"] - pin["at"][0] == pytest.approx(
        pin["side_nominal"]
    )
    assert features["front_face"]["plane"]["value"] - pin["at"][2] == pytest.approx(
        pin["row_nominal"]
    )
    # Both blind holes enter the top seat going down.
    for hole in (pin, tap):
        assert hole["at"][1] == top and hole["axis"] == [0.0, -1.0, 0.0]
