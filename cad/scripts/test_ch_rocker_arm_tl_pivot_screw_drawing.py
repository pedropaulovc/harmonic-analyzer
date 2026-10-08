"""Offline contracts for the rocker arm pivot screw and washer (MHA-CH-006-TL-06/07)."""

from __future__ import annotations

import re

import _config
import ch_rocker_arm_spec as rocker
import ch_rocker_arm_tl_pivot_screw_spec as screw
import ch_rocker_arm_tl_pivot_washer_spec as washer
import draw_ch_rocker_arm_tl_pivot_screw as screw_drawing
import draw_ch_rocker_arm_tl_pivot_washer as washer_drawing
import export_features
from _feature_requirements import limits
from _printed_tolerance import printed_band_mm
from prechips.model import TOLERANCE_REQUIREMENTS

SCREW = "ch_rocker_arm_tl_pivot_screw"
WASHER = "ch_rocker_arm_tl_pivot_washer"


def _features(stem: str) -> dict:
    return export_features.requirement_manifest(stem)["features"]


def test_every_marked_dimension_prints_once() -> None:
    for spec, keeps in (
        (screw, (screw_drawing.SIDE_KEEP, screw_drawing.END_KEEP)),
        (washer, (washer_drawing.FACE_KEEP, washer_drawing.EDGE_KEEP)),
    ):
        marked = set().union(*spec.DRAWING_DIMENSIONS.values())
        assert set(keeps[0]) | set(keeps[1]) == marked
        assert not set(keeps[0]) & set(keeps[1])
        assert set(spec.DRAWING_PRECISION_BY_NAME) == marked


def _band(nominal: float, band: tuple[float, float]) -> tuple[float, float]:
    return (round(nominal + band[1], 6), round(nominal + band[0], 6))


SHOULDER = _band(screw.SHOULDER_DIA, screw.SHOULDER_BAND)
HEAD = _band(screw.HEAD_DIA, screw.HEAD_BAND)


def test_shoulder_slides_into_every_bore_a_the_rocker_allows() -> None:
    smallest_bore_a = rocker.PIVOT_HOLE_DIA + rocker.PIVOT_HOLE_BAND[1]
    largest_bore_a = rocker.PIVOT_HOLE_DIA + rocker.PIVOT_HOLE_BAND[0]
    assert round(smallest_bore_a - SHOULDER[1], 6) >= screw.LOCATING_CLEARANCE_MIN
    # The inventory's worst float in A: 0.045.
    assert round(largest_bore_a - SHOULDER[0], 6) <= 0.045


def test_shoulder_fits_the_plate_bore_and_head_the_template_bush() -> None:
    assert round(screw.PLATE_BORE_LIMITS[0] - SHOULDER[1], 6) >= 0.010
    assert HEAD[1] <= screw.TEMPLATE_BUSH_BORE_LIMITS[0]


def test_match_fit_diameters_export_what_the_print_says() -> None:
    # One fact, one source: no hidden band behind a printed match fit.
    features = _features(SCREW)
    for key, nominal in (("shoulder", screw.SHOULDER_DIA), ("head", screw.HEAD_DIA)):
        assert "dia" not in features[key]
        assert features[key]["dia_nominal"] == nominal
        assert "note" in features[key]["requirements"]
    assert features["head"]["coaxial_to"] == "shoulder"
    assert features["shoulder"]["note"] == " ".join(screw.SHOULDER_FIT_CALLOUT.splitlines())
    assert features["head"]["note"] == " ".join(screw.HEAD_FIT_CALLOUT.splitlines())


def test_fit_callout_names_the_rocker_by_its_registered_number() -> None:
    # The profile plate's config lives on its sibling branch (TL-02).
    assert _config.parts("ch-rocker-arm")["number"] == screw.ROCKER_NUMBER


def _plate_z() -> tuple[tuple[float, float], tuple[float, float]]:
    """(plate top Z, bore floor Z) worst-case ranges in the fixture frame (Z0 =
    upper hub face, +Z up), rebuilt from the rocker and plate prints."""
    xxx, xx = printed_band_mm(3), printed_band_mm(2)
    hub = (rocker.HUB_LENGTH + rocker.HUB_LENGTH_BAND[1], rocker.HUB_LENGTH + rocker.HUB_LENGTH_BAND[0])
    strap = (rocker.ARM_THICKNESS - xx, rocker.ARM_THICKNESS + xx)
    # The strap sits centred on the pads, so the pad tops are half the hub
    # plus strap below the hub face.
    pad_top = (-(hub[1] + strap[1]) / 2.0, -(hub[0] + strap[0]) / 2.0)
    drop = (screw.profile.PLATE_DROP - xxx, screw.profile.PLATE_DROP + xxx)
    depth_band = screw.profile.LOCATING_BORE_DEPTH_BAND
    depth = (screw.profile.LOCATING_BORE_DEPTH - depth_band, screw.profile.LOCATING_BORE_DEPTH + depth_band)
    top = (pad_top[0] - drop[1], pad_top[1] - drop[0])
    floor = (top[0] - depth[1], top[1] - depth[0])
    return top, floor


def test_plate_frame_matches_the_profile_fixture() -> None:
    top, floor = _plate_z()
    # The profile's nominal plate lies inside the rebuilt worst-case ranges
    # (the hub's unilateral band puts it off their centre).
    assert top[0] <= screw.profile.PLATE_TOP_Z <= top[1]
    assert floor[0] <= screw.profile.LOCATING_BORE_FLOOR_Z <= floor[1]


def test_nominal_screw_sits_in_the_plate_in_physical_z() -> None:
    # Exported model stations, no stack arithmetic: the shoulder ends inside
    # the plate's locating bore and the tip lies below its floor.
    features = _features(SCREW)
    underhead_z = features["underhead"]["plane"]["value"]
    shoulder_end_z = features["shoulder"]["at"][2]
    tip_z = features["tip"]["plane"]["value"]
    assert underhead_z == _features(WASHER)["head_face"]["plane"]["value"] > 0.0
    assert screw.profile.LOCATING_BORE_FLOOR_Z < shoulder_end_z < screw.profile.PLATE_TOP_Z - 2.0
    assert tip_z < screw.profile.LOCATING_BORE_FLOOR_Z - 1.5 * screw.THREAD_MODEL_DIA
    assert tip_z > screw.profile.LOCATING_BORE_FLOOR_Z - screw.profile.PIVOT_TAP_DRILL_DEPTH


def test_printed_bands_seat_the_screw_in_the_plate_in_physical_z() -> None:
    """Worst case from the exported bands, in signed Z: the washer stands on
    the hub face, the underhead on the washer, the lengths hang below it."""
    features = _features(SCREW)
    thick = _features(WASHER)["hub_face"]["thickness"]
    shoulder = features["shoulder"]["length"]
    under_head = features["tip"]["station"]
    underhead_z = (thick[0], thick[1])
    shoulder_end_z = (underhead_z[0] - shoulder[1], underhead_z[1] - shoulder[0])
    tip_z = (underhead_z[0] - under_head[1], underhead_z[1] - under_head[0])
    top_z, floor_z = _plate_z()
    # The shoulder enters the plate bore at least 2.0 ...
    assert top_z[0] - shoulder_end_z[1] >= 2.0
    # ... and it and the die run-out stay clear of the bore floor.
    assert shoulder_end_z[0] - floor_z[1] >= screw.THREAD_RUNOUT + 0.1
    # Full thread below the floor, less the chamfer and half a pitch.
    chamfer_loss = screw.TIP_CHAMFER + screw.THREAD_PITCH / 2.0
    assert floor_z[0] - tip_z[1] - chamfer_loss >= 1.5 * screw.THREAD_MODEL_DIA
    # The screw's full thread stays inside the tap's full thread, and the tip
    # inside the tap drill.
    tap_full = screw.profile.PIVOT_TAP_THREAD_DEPTH - printed_band_mm(2)
    assert floor_z[1] - tip_z[0] - screw.TIP_CHAMFER <= tap_full
    drill = screw.profile.PIVOT_TAP_DRILL_DEPTH - printed_band_mm(2)
    assert floor_z[1] - tip_z[0] <= drill - 0.5


def test_tip_chamfer_acceptance_exports_with_the_tip() -> None:
    tip = _features(SCREW)["tip"]
    assert "note" in tip["requirements"]
    assert screw.CHAMFER_CALLOUT in tip["note"]


# Each printed toleranced dimension -> (stem, feature, requirement) owning its
# band at its printed places. The bracketed match-fit diameters and the tip
# chamfer (defined to the thread root) are references and own no band.
PRINTED_OWNERS = {
    SCREW: {
        "HeadLength": ("head", "length"),
        "ShoulderLength": ("shoulder", "length"),
        "UnderHeadLength": ("tip", "station"),
        "SlotWidth": ("driver_slot", "width"),
        "SlotDepth": ("driver_slot", "depth"),
    },
    WASHER: {
        "OuterDia": ("hub_face", "dia"),
        "BoreDia": ("bore", "dia"),
        "Thick": ("hub_face", "thickness"),
    },
}
REFERENCE_DIMENSIONS = {SCREW: {"HeadDia", "ShoulderDia", "TipChamfer"}, WASHER: set()}
# (model nominal, printed places, explicit band or None) per printed dimension.
PRINTED_SIZES = {
    SCREW: {
        "HeadLength": (screw.HEAD_LENGTH, 1, None),
        "ShoulderLength": (screw.SHOULDER_LENGTH, 3, None),
        "UnderHeadLength": (screw.UNDER_HEAD_LENGTH, 3, None),
        "SlotWidth": (screw.SLOT_WIDTH, 1, None),
        "SlotDepth": (screw.SLOT_DEPTH, 1, None),
    },
    WASHER: {
        "OuterDia": (washer.OUTER_DIA, 3, washer.OUTER_BAND),
        "BoreDia": (washer.BORE_DIA, 1, washer.BORE_BAND),
        "Thick": (washer.THICK, 3, None),
    },
}


def test_every_printed_band_has_a_requirement_owner() -> None:
    """One-fact coverage: every printed toleranced dimension reaches prechips
    as a listed requirement band at its printed places."""
    for stem, spec in ((SCREW, screw), (WASHER, washer)):
        owners = PRINTED_OWNERS[stem]
        assert set(owners) | REFERENCE_DIMENSIONS[stem] == set(spec.DRAWING_PRECISION_BY_NAME)
        features = _features(stem)
        for printed, (name, key) in owners.items():
            nominal, places, band = PRINTED_SIZES[stem][printed]
            # The model nominal is exactly the printed value, so the exported
            # endpoints are the printed ones.
            assert round(nominal, places) == nominal, (stem, printed)
            assert spec.DRAWING_PRECISION_BY_NAME[printed] == places, (stem, printed)
            assert key in features[name]["requirements"], (stem, printed)
            assert features[name][key] == limits(nominal, places, band), (stem, printed)


def test_every_exported_nominal_lies_inside_its_band() -> None:
    """prechips rejects a *_nominal outside its requirement band."""
    for stem in (SCREW, WASHER):
        for name, feature in _features(stem).items():
            for key, value in feature.items():
                if not key.endswith("_nominal"):
                    continue
                band = feature.get(key.removesuffix("_nominal"))
                if isinstance(band, list) and len(band) == 2:
                    assert band[0] <= value <= band[1], (stem, name, key)


def test_every_exported_band_is_a_requirement() -> None:
    """One-fact rule: prechips inspects only the bands a feature lists."""
    for stem in (SCREW, WASHER):
        for name, feature in _features(stem).items():
            for key, value in feature.items():
                if key in TOLERANCE_REQUIREMENTS and isinstance(value, list) and len(value) == 2:
                    assert key in feature["requirements"], (stem, name, key)


def test_washer_passes_the_shoulder_and_carries_the_head() -> None:
    bore = _features(WASHER)["bore"]["dia"]
    assert bore[0] > SHOULDER[1]
    assert bore[1] < HEAD[0]
    assert washer.THICK == screw.UNDERHEAD_Z
    assert washer.WALL_MIN >= 1.5


def test_numbers_are_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    for stem, suffix in (("ch-rocker-arm-tl-pivot-screw", "06"), ("ch-rocker-arm-tl-pivot-washer", "07")):
        assert _config.parts(stem)["number"] == f"{parent}-TL-{suffix}"


def test_notes_follow_the_simplicity_policy() -> None:
    for spec in (screw, washer):
        lines = spec.DRAWING_NOTES.splitlines()
        assert 1 <= len(lines) <= 4
        assert not re.search(r"\d", spec.DRAWING_NOTES)
        assert "GROUND" not in spec.DRAWING_NOTES
