"""Feature-export contracts for the rocker-arm support (MHA-FR-05): the
declarations in ``draw_fr_rocker_arm_support`` name their STEP faces, one
owner per face, and carry the bands the sheet prints."""

from __future__ import annotations

from math import hypot

import pytest

import build_fr_rocker_arm_support as build
import draw_fr_rocker_arm_support as drawing
import export_features
import fr_rocker_arm_support_section_spec as section
import fr_rocker_arm_support_spec as spec
import rocker_bracket_seat_layout as seats
from _gtol_face import FaceGeometry
from _hole_spec import blind_cut_dia_mm
from _surface_finish import SEAT_UM

_STEM = "fr_rocker_arm_support"
_MM_PER_IN = 25.4

_FEATURE_KINDS = {
    "foot": "face",
    "top_face": "face",
    "west_end": "face",
    "east_end": "face",
    "slant_minus_z": "tapered_side",
    "slant_plus_z": "tapered_side",
    "web_minus_z": "pocket_floor",
    "web_plus_z": "pocket_floor",
    "pockets": "pocket",
    "cavity": "cavity",
    "foot_hole_a1": "hole",
    "foot_hole_a2": "hole",
    "foot_hole_a3": "hole",
    "foot_hole_a4": "hole",
    "seat_west": "threaded_hole",
    "seat_east": "threaded_hole",
    "rim_chamfer": "chamfer",
}

_HALF_LENGTH = spec.SUPPORT_HALF_MACHINE_Z
_WIDE, _NARROW, _HALF_Y = section.WIDE, section.NARROW, section.HALF_Y
_BIG, _CAV, _WEB = section.BIG, build.CAV, seats.WEB


def _in(value_in: float) -> float:
    return value_in * _MM_PER_IN


def _band(value_in: float, plus_in: float) -> list[float]:
    return [_in(value_in - plus_in), _in(value_in + plus_in)]


def _plane(normal: tuple[float, float, float], offset_mm: float) -> FaceGeometry:
    length = hypot(*normal)
    unit = tuple(value / length for value in normal)
    point = tuple(value * offset_mm / 1000 for value in unit)
    return FaceGeometry(None, 4001, (*unit, *point), unit, ())


def _cylinder(
    dia_mm: float, axis: tuple[float, float, float], box_mm: tuple[float, ...]
) -> FaceGeometry:
    box = tuple(value / 1000 for value in box_mm)
    return FaceGeometry(None, 4002, (0.0, 0.0, 0.0, *axis, dia_mm / 2000), None, box)


def _slant(sign: float) -> FaceGeometry:
    """One slant face as the trapezoid cuts it: the plane through the foot
    edge WIDE off the centre plane and the top-flat edge NARROW off it."""
    run, rise = _WIDE - _NARROW, 2 * _HALF_Y
    length = hypot(run, rise)
    normal = (0.0, run / length, sign * rise / length)
    point = (0.0, -_HALF_Y / 1000, sign * _WIDE / 1000)
    return FaceGeometry(None, 4001, (*normal, *point), normal, ())


def _manifest() -> dict:
    return export_features.requirement_manifest(_STEM)


def _foot_hole(x: float, z: float) -> FaceGeometry:
    r = spec.HOLE_DIA / 2
    box = (x - r, -_HALF_Y, z - r, x + r, -_BIG, z + r)
    return _cylinder(spec.HOLE_DIA, (0.0, 1.0, 0.0), box)


def _seat(x: float) -> FaceGeometry:
    dia = blind_cut_dia_mm(seats.SEAT_SPEC)
    box = (x - dia / 2, _HALF_Y - seats.SEAT_DRILL_DEPTH, -dia / 2, x + dia / 2, _HALF_Y, dia / 2)
    return _cylinder(dia, (0.0, 1.0, 0.0), box)


def test_the_support_is_a_feature_export_part_with_one_owner_per_face() -> None:
    assert _STEM in export_features.SUPPORTED_PARTS
    manifest = _manifest()
    kinds = {name: feature["kind"] for name, feature in manifest["features"].items()}
    assert kinds == _FEATURE_KINDS
    assert manifest["construction"] == "one_piece"
    selectors = export_features.feature_selectors(_STEM)
    x_hole, z_hole = spec.HOLD_DOWN_LOCAL_HALF_X, spec.HOLD_DOWN_LOCAL_HALF_Z
    chamfer = (_HALF_LENGTH + _HALF_Y - build.CHAMFER) / 2**0.5
    pocket_corner = _cylinder(
        2 * build.POCKET_FILLET_R,
        (0.0, 0.0, 1.0),
        (_BIG - 12.7, _BIG - 12.7, _WEB, _BIG, _BIG, 20.0),
    )
    cavity_corner = _cylinder(
        2 * build.FILLET_R,
        (0.0, 0.0, 1.0),
        (_CAV - 25.4, _CAV - 25.4, -_WEB, _CAV, _CAV, _WEB),
    )
    expected = {
        "foot": [_plane((0.0, -1.0, 0.0), _HALF_Y)],
        "top_face": [_plane((0.0, 1.0, 0.0), _HALF_Y)],
        "west_end": [_plane((-1.0, 0.0, 0.0), _HALF_LENGTH)],
        "east_end": [_plane((1.0, 0.0, 0.0), _HALF_LENGTH)],
        "slant_minus_z": [_slant(-1.0)],
        "slant_plus_z": [_slant(1.0)],
        "web_minus_z": [_plane((0.0, 0.0, -1.0), _WEB)],
        "web_plus_z": [_plane((0.0, 0.0, 1.0), _WEB)],
        # The walls face into the pockets: each post's inner face, the foot's
        # top and the top rail's underside.
        "pockets": [
            _plane((-1.0, 0.0, 0.0), -_BIG),
            _plane((1.0, 0.0, 0.0), -_BIG),
            _plane((0.0, 1.0, 0.0), -_BIG),
            _plane((0.0, -1.0, 0.0), -_BIG),
            pocket_corner,
        ],
        "cavity": [
            _plane((-1.0, 0.0, 0.0), -_CAV),
            _plane((1.0, 0.0, 0.0), -_CAV),
            _plane((0.0, 1.0, 0.0), -_CAV),
            _plane((0.0, -1.0, 0.0), -_CAV),
            cavity_corner,
        ],
        "foot_hole_a1": [_foot_hole(-x_hole, -z_hole)],
        "foot_hole_a2": [_foot_hole(-x_hole, z_hole)],
        "foot_hole_a3": [_foot_hole(x_hole, -z_hole)],
        "foot_hole_a4": [_foot_hole(x_hole, z_hole)],
        "seat_west": [_seat(min(seats.SEAT_LOCAL_X))],
        "seat_east": [_seat(max(seats.SEAT_LOCAL_X))],
        "rim_chamfer": [
            _plane((1.0, -1.0, 0.0), chamfer),
            _plane((-1.0, -1.0, 0.0), chamfer),
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
    # Faces no feature owns: the pocket floors' R.040-max corner fillets
    # and the end faces' slant-edge chamfers.
    floor_fillet = _cylinder(
        2 * build.POCKET_FLOOR_R, (1.0, 0.0, 0.0), (-60.0, -83.0, 6.3, 60.0, -82.0, 7.2)
    )
    assert not any(
        selector.matches(floor_fillet) for specs in selectors.values() for selector in specs
    )


def test_support_feature_bands_are_the_printed_ones() -> None:
    features = _manifest()["features"]
    assert features["foot"]["finish_ra"] == SEAT_UM
    assert features["foot"]["thickness"] == pytest.approx(_band(0.25, 0.01))
    assert features["top_face"]["height"] == pytest.approx(_band(7.00, 0.01))
    assert features["east_end"]["length"] == pytest.approx(_band(7.56, 0.01))

    plus, minus = features["slant_plus_z"], features["slant_minus_z"]
    assert plus["width"] == pytest.approx(_band(2.50, 0.01))
    for slant in (plus, minus):
        # .08 BOTH SIDES: each top-flat edge off its nearer web face.
        assert slant["top_flat_station"] == pytest.approx(_band(0.08, 0.01))
        assert slant["callout"] == "BOTH SIDES"
    assert plus["top_flat_station_web_face"] == "web_plus_z"
    assert minus["top_flat_station_web_face"] == "web_minus_z"

    assert features["web_minus_z"]["station"] == pytest.approx(_band(1.00, 0.01))
    assert features["web_plus_z"]["thickness"] == pytest.approx(_band(0.50, 0.01))

    pockets = features["pockets"]
    assert pockets["size"] == pytest.approx(_band(6.50, 0.01))
    assert pockets["corner_radius"] == pytest.approx(_band(0.25, 0.01))
    assert pockets["end_station"] == pytest.approx(_band(0.53, 0.01))
    assert pockets["bottom_station"] == pytest.approx(_band(0.25, 0.01))
    assert pockets["floor_corner_radius_max"] == pytest.approx(_in(0.040))
    assert pockets["both_sides"] is True
    assert pockets["callout"] == "SQ POCKET BOTH SIDES"
    assert pockets["corner_callout"] == "8X"

    cavity = features["cavity"]
    assert cavity["size"] == pytest.approx(_band(5.00, 0.01))
    assert cavity["corner_radius"] == pytest.approx(_band(0.50, 0.01))
    assert cavity["end_station"] == pytest.approx(_band(1.28, 0.01))
    assert cavity["top_station"] == pytest.approx(_band(1.00, 0.01))
    assert cavity["thru"] is True
    assert cavity["callout"] == "SQ CAVITY THRU"
    assert cavity["corner_callout"] == "4X"

    # The hole table: DRILL Ø.313 THRU ALL at the DRILLED HOLES +.004/0,
    # X LOC and Y LOC .XXX (±.005), MATE MHA-FR-01.
    table = {
        "a1": (1.405, 0.563),
        "a2": (1.405, 1.937),
        "a3": (6.155, 0.563),
        "a4": (6.155, 1.937),
    }
    for tag, (x_loc, y_loc) in table.items():
        hole = features[f"foot_hole_{tag}"]
        assert hole["tag"] == tag.upper()
        assert hole["dia"] == pytest.approx([spec.HOLE_DIA, spec.HOLE_DIA + _in(0.004)])
        assert hole["process"] == "drill" and hole["thru"] is True
        assert hole["mates"] == "MHA-FR-01"
        assert hole["station"] == pytest.approx(_band(x_loc, 0.005), abs=1e-3)
        assert hole["lateral"] == pytest.approx(_band(y_loc, 0.005), abs=1e-3)
    assert {
        (features[f"foot_hole_{tag}"]["station_nominal"], features[f"foot_hole_{tag}"]["lateral_nominal"])
        for tag in table
    } == set(drawing.EXPECTED_HOLE_TABLE_LOCATIONS_MM)

    # 2X Ø.136 ↧ .59, TRANSFER FROM MHA-CH-08 AT ASSEMBLY; 8-32 UNC-2B ↧ .46,
    # each with its REF station off its nearer end face: made at assembly, so
    # neither names a process the traveler would run.
    for name, ref_in in (("seat_west", 0.261), ("seat_east", 0.205)):
        seat = features[name]
        assert seat["thread"] == "#8-32 UNC-2B"
        assert seat["dia"] == pytest.approx([_in(0.136), _in(0.140)], abs=1e-3)
        assert seat["drill_depth"] == pytest.approx(_band(0.59, 0.01))
        assert seat["thread_depth"] == pytest.approx(_band(0.46, 0.01))
        assert seat["made_at"] == "assembly" and "process" not in seat
        assert seat["transfer_part"] == "MHA-CH-08"
        assert seat["dimension_type"] == "reference"
        assert seat["station_ref"] == pytest.approx(_in(ref_in), abs=_in(0.0005))

    chamfer = features["rim_chamfer"]
    assert chamfer["leg"] == pytest.approx(_band(0.06, 0.01))
    assert chamfer["angle_deg"] == 45.0
    assert chamfer["note"] == drawing.CHAMFER_NOTE
    assert chamfer["callout"] == drawing.DIMENSION_CALLOUTS["RimChamferSize"]


def test_the_notes_are_the_sheet_note() -> None:
    manifest = _manifest()
    assert drawing.DRAWING_NOTES == drawing.CHAMFER_NOTE
    assert manifest["notes"]["manufacturing"] == drawing.CHAMFER_NOTE.splitlines()


def _coordinate(feature: dict, axis: int) -> float:
    plane = feature.get("plane")
    if plane is not None and "xyz".index(plane["axis"]) == axis:
        return plane["value"]
    return feature["at"][axis]


def test_every_location_closes_on_the_feature_it_is_printed_from() -> None:
    features = _manifest()["features"]
    checked = 0
    for name, feature in features.items():
        for key, target in feature.items():
            stem = key.removesuffix("_from")
            if stem == key or f"{stem}_nominal" not in feature:
                continue
            reference = features[target]
            if "plane" in reference:
                axis = "xyz".index(reference["plane"]["axis"])
            else:
                axis = "xyz".index(feature[f"{stem}_axis"])
            distance = abs(_coordinate(feature, axis) - _coordinate(reference, axis))
            assert distance == pytest.approx(abs(feature[f"{stem}_nominal"])), (name, key)
            checked += 1
    # foot, top, length, width, web station and thickness, pocket x2,
    # cavity x2, four holes x2.
    assert checked == 18
    # Seat REF stations: a reference value, not a nominal-checked band.
    for name in ("seat_west", "seat_east"):
        seat = features[name]
        end = features[seat["station_ref_from"]]
        assert abs(seat["at"][0] - end["plane"]["value"]) == pytest.approx(seat["station_ref"])


def test_each_top_flat_edge_stands_off_its_web_face_and_the_slants_bound_the_part() -> None:
    features = _manifest()["features"]
    for name in ("slant_minus_z", "slant_plus_z"):
        slant = features[name]
        web = features[slant["top_flat_station_web_face"]]
        top_edges = [corner for corner in slant["corners"] if corner[1] == _HALF_Y]
        assert len(top_edges) == 2
        for corner in top_edges:
            assert abs(corner[2] - web["plane"]["value"]) == pytest.approx(
                slant["top_flat_station_nominal"]
            )
        # Every corner lies on the face's plane through its foot line.
        normal, at = slant["normal"], slant["at"]
        for corner in slant["corners"]:
            assert sum(n * (c - a) for n, c, a in zip(normal, corner, at)) == pytest.approx(0.0, abs=1e-9)
    planes = [f["plane"] for f in features.values() if f["kind"] == "face"]
    corners = [c for name in ("slant_minus_z", "slant_plus_z") for c in features[name]["corners"]]
    span = {}
    for index, axis in enumerate("xyz"):
        values = [p["value"] for p in planes if p["axis"] == axis] + [c[index] for c in corners]
        span[axis] = max(values) - min(values)
    assert span == pytest.approx({"x": _in(7.56), "y": _in(7.00), "z": _in(2.50)})
