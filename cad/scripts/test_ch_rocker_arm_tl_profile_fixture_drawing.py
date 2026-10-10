"""Offline contracts for the rocker arm profile fixture (MHA-CH-006-TL-02)."""

from __future__ import annotations

import math
import re
import types
from pathlib import Path

import _config
import _drawing_contract
import ch_rocker_arm_spec as rocker
import ch_rocker_arm_notes as rocker_notes
import ch_rocker_arm_tl_profile_fixture_spec as spec
import draw_ch_rocker_arm_tl_profile_fixture as drawing
import export_features
from _feature_requirements import limits
from _printed_tolerance import printed_band_mm
from prechips.model import TOLERANCE_REQUIREMENTS

STEM = "ch_rocker_arm_tl_profile_fixture"
# Agreed with the MHA-CH-006-TL pivot screw and diamond pin: the screw's ground
# shoulder and the pin's shank, a bonded slip fit (Ø2.97 ±0.02,
# MHA-CH-006-TL-03).
PIVOT_SCREW_SHOULDER = (6.485, 6.490)
DIAMOND_PIN_SHANK = (2.950, 2.990)
# The prechips freeze stations (review/compose-r5 c25b48fc,
# examples/inventory/pedro-shop.toml:2131-2147, frame A = model frame): rest
# pocket centre and length x width from each rail-rest-*-slot's corner and
# size, and each stud-tap-* station, by print tag.
FROZEN_REST_POCKETS = {
    "c1": (30.0, 34.35, 20.0, 4.3),  # rail-rest-ru-slot
    "c2": (-30.0, 34.35, 20.0, 4.3),  # rail-rest-lu-slot
    "c3": (130.0, -25.0, 20.0, 5.0),  # rail-rest-rl-slot
    "c4": (-130.0, -25.0, 20.0, 5.0),  # rail-rest-ll-slot
}
FROZEN_STUD_TAPS = {
    "s1": (-130.0, -36.0),  # stud-tap-ll
    "s2": (130.0, -36.0),  # stud-tap-rl
    "s3": (-70.0, 45.0),  # stud-tap-lu
    "s4": (70.0, 45.0),  # stud-tap-ru
    "s5": (-30.0, 45.0),  # stud-tap-lu4
    "s6": (30.0, 45.0),  # stud-tap-ru4
}


def test_rests_and_stud_taps_stand_at_the_prechips_freeze_stations() -> None:
    """The rail-rest pockets, rests and stud taps that prechips' S3/S4 clamp
    and clearance rows were frozen on: every station, no more, no fewer."""
    features = _features()
    assert {name for name in features if name.startswith("stud_tap_s")} == {
        f"stud_tap_{tag}" for tag in FROZEN_STUD_TAPS
    }
    for tag, (x, y) in FROZEN_STUD_TAPS.items():
        tap = features[f"stud_tap_{tag}"]
        assert (tap["station_nominal"], tap["height_nominal"]) == (x, y), tag
    assert {name for name in features if name.startswith("rest_pocket_c")} == {
        f"rest_pocket_{tag}" for tag in FROZEN_REST_POCKETS
    }
    for tag, (x, y, length, width) in FROZEN_REST_POCKETS.items():
        pocket = features[f"rest_pocket_{tag}"]
        assert (
            pocket["station_nominal"],
            pocket["height_nominal"],
            pocket["length_nominal"],
            pocket["width_nominal"],
        ) == (x, y, length, width), tag
        rest = next(row for row in spec.RESTS if row[0] == tag.upper())
        assert rest[1:3] == (x, y), tag


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    views = (
        drawing.PLAN_KEEP_AT,
        drawing.SECTION_KEEP_AT,
        drawing.DETAIL_KEEP_AT,
        drawing.ELEVATION_KEEP_Z,
    )
    assert sum(len(view) for view in views) == len(marked)
    assert set().union(*views) == marked
    # every schedule number is a model dimension with authored places too,
    # but it prints once, in its schedule, never as a marked dimension
    scheduled = {name for cells in spec.SCHEDULE_CELL_DIMENSIONS.values() for _f, name in cells}
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked | scheduled
    assert not marked & scheduled
    assert {name for _f, name in spec.EXPLICIT_SYMMETRIC_TOLERANCES_MM} == {
        "RodPinHoleX",
        "RodPinHoleY",
    }
    assert set(spec.DIMENSION_CALLOUTS) <= marked


def test_locating_bore_takes_every_pivot_screw_shoulder() -> None:
    bore = _features()["locating_bore"]["dia"]
    assert bore[0] > PIVOT_SCREW_SHOULDER[1]
    # the bore is the rocker's own pivot hole, so the arm drops on the same screw
    assert spec.LOCATING_BORE_DIA == rocker.PIVOT_HOLE_DIA


def test_rod_pin_hole_takes_every_diamond_pin_shank() -> None:
    hole = _features()["rod_pin_hole"]["dia"]
    assert hole[0] > DIAMOND_PIN_SHANK[1]


def _schedule_cells() -> dict[tuple[str, str, str], str]:
    return {
        (schedule, row[0], column): text
        for schedule, header, rows in (
            ("FEATURE", spec.FEATURE_SCHEDULE_HEADER, spec.FEATURE_SCHEDULE),
            ("PART", spec.PART_SCHEDULE_HEADER, spec.PART_SCHEDULE),
        )
        for row in rows
        for column, text in zip(header, row, strict=True)
    }


def test_every_schedule_number_is_a_model_dimension_at_its_places() -> None:
    """Policy rule 2: a schedule cell prints its owners' value at their
    authored places; nothing in a dimension column is unowned."""
    cells = _schedule_cells()
    owned = set(spec.SCHEDULE_CELL_DIMENSIONS)
    for key, text in cells.items():
        if key[2] in {"CENTRE X", "CENTRE Y", "LENGTH X", "WIDTH Y", "DEPTH", "HEIGHT"}:
            assert any(c.isdigit() for c in text) == (key in owned), key
    for key, owners in spec.SCHEDULE_CELL_DIMENSIONS.items():
        number = re.search(r"-?\d+\.(\d+)", cells[key])
        for _feature, name in owners:
            assert len(number.group(1)) == spec.DRAWING_PRECISION_BY_NAME[name], (key, name)


def test_every_exported_band_is_a_requirement() -> None:
    """One-fact rule: prechips inspects only the bands a feature lists."""
    for name, feature in _features().items():
        for key, value in feature.items():
            if key in TOLERANCE_REQUIREMENTS and isinstance(value, list) and len(value) == 2:
                assert key in feature["requirements"], (name, key)


def _pocket_owners(tag: str, feature: str) -> dict[str, tuple[tuple[str, str], ...]]:
    names = spec.pocket_dimension_names(tag)
    keys = ("station", "height", "length", "width")
    return {name: ((feature, key),) for name, key in zip(names, keys, strict=True)}


def _part_owners(tag: str, part: str, feature: str) -> dict[str, tuple[tuple[str, str], ...]]:
    names = spec.part_dimension_names(tag, part)
    return {name: ((feature, key),) for name, key in zip(names, ("length", "width"), strict=True)}


_PAD_TAGS = [row[0] for row in spec.PADS]
_REST_TAGS = [row[0] for row in spec.RESTS]
# Each printed dimension -> every exported (feature, requirement) owning its
# band: a shared depth or height owns one band on each pocket or part.
PRINTED_OWNERS: dict[str, tuple[tuple[str, str], ...]] = {
    "PlateLength": (("plate_outline", "length"),),
    "PlateWidth": (("plate_outline", "width"),),
    "PlateWestX": (("plate_west_end", "station"),),
    "PlateSouthY": (("plate_south_side", "height"),),
    "PlateThick": (("plate_top", "thickness"),),
    "PlateDrop": (("pad_tops", "height"),),
    "StandOD": (("stand_top", "dia"),),
    "StandBore": (("stand_bore", "dia"),),
    "StandHeight": (("stand_foot", "height"),),
    "StandDrop": (("stand_top", "height"),),
    "RestHeight": tuple((f"rest_{tag.lower()}", "height") for tag in _REST_TAGS),
    "RestTopHeight": (("rail_rest_tops", "height"),),
    "StandPocketDia": (("stand_pocket", "dia"),),
    "StandPocketDepth": (("stand_pocket", "depth"),),
    "LocatingBoreDia": (("locating_bore", "dia"),),
    "LocatingBoreDepth": (("locating_bore", "depth"),),
    "RodPinHoleDia": (("rod_pin_hole", "dia"),),
    "RodPinHoleX": (("rod_pin_hole", "station"),),
    "RodPinHoleY": (("rod_pin_hole", "height"),),
    "RodPinHoleDepth": (("rod_pin_hole", "depth"),),
    "PadPocketDepth": tuple((f"pad_pocket_{tag.lower()}", "depth") for tag in _PAD_TAGS),
    "RestPocketDepth": tuple((f"rest_pocket_{tag.lower()}", "depth") for tag in _REST_TAGS),
    "PadHeight": tuple((f"pad_{tag.lower()}", "height") for tag in _PAD_TAGS),
    **{
        name: owners
        for tag in _PAD_TAGS
        for name, owners in _pocket_owners(tag, f"pad_pocket_{tag.lower()}").items()
    },
    **{
        name: owners
        for tag in _REST_TAGS
        for name, owners in _pocket_owners(tag, f"rest_pocket_{tag.lower()}").items()
    },
    **{
        name: owners
        for tag in _PAD_TAGS
        for name, owners in _part_owners(tag, "Pad", f"pad_{tag.lower()}").items()
    },
    **{
        name: owners
        for tag in _REST_TAGS
        for name, owners in _part_owners(tag, "Rest", f"rest_{tag.lower()}").items()
    },
    **{
        f"{prefix}{index}{axis}": ((f"{feature}{index}", key),)
        for prefix, feature, count in (
            ("HoldDown", "hold_down_h", len(spec.HOLD_DOWN_POINTS)),
            ("ClampStud", "stud_tap_s", len(spec.CLAMP_STUD_POINTS)),
        )
        for index in range(1, count + 1)
        for axis, key in (("X", "station"), ("Y", "height"))
    },
}
# The printed bands that are not the general grade at their places.
EXPLICIT_BANDS = {
    "LocatingBoreDia": spec.LOCATING_BORE_BAND,
    "RodPinHoleDia": spec.ROD_PIN_HOLE_BAND,
    "RodPinHoleX": spec.ROD_PIN_XY_BAND,
    "RodPinHoleY": spec.ROD_PIN_XY_BAND,
    "StandBore": spec.DRILLED_BAND,
}


def _nominal(feature: dict, key: str) -> float:
    for field in (f"{key}_nominal", f"nominal_{key}", f"{key}_ref"):
        if field in feature:
            return feature[field]
    raise AssertionError(f"no nominal for {key}")


# The value each marked dimension prints (the sheet imports the model
# dimension, which the build drives with these spec values).
MARKED_SOURCES = {
    "PlateLength": spec.PLATE_LENGTH,
    "PlateWidth": spec.PLATE_WIDTH,
    "PlateWestX": spec.PLATE_WEST_X,
    "PlateSouthY": spec.PLATE_SOUTH_Y,
    "PlateThick": spec.PLATE_THICK,
    "PlateDrop": spec.PLATE_DROP,
    "StandDrop": spec.STAND_DROP,
    "RestTopHeight": spec.REST_TOP_HEIGHT,
    "StandPocketDia": spec.STAND_POCKET_DIA,
    "StandPocketDepth": spec.STAND_POCKET_DEPTH,
    "LocatingBoreDia": spec.LOCATING_BORE_DIA,
    "LocatingBoreDepth": spec.LOCATING_BORE_DEPTH,
    "RodPinHoleDia": spec.ROD_PIN_HOLE_DIA,
}


def _printed_values() -> dict[str, float]:
    """Every printed dimension's value as the sheet states it: a schedule
    cell's own number (signed, as the TAGS plan reads), or a marked
    dimension's spec source at its printed places."""
    cells = _schedule_cells()
    printed = {}
    for key, owners in spec.SCHEDULE_CELL_DIMENSIONS.items():
        value = float(re.search(r"-?\d+\.\d+", cells[key]).group())
        for _feature, name in owners:
            printed[name] = value
    for name, source in MARKED_SOURCES.items():
        places = spec.DRAWING_PRECISION_BY_NAME[name]
        # the model carries the printed value, not a longer derived one
        assert source == round(source, places), name
        printed[name] = round(source, places)
    return printed


def one_fact_violations(features: dict) -> list[tuple]:
    """Each printed dimension whose owners are missing, unlisted, or carry a
    nominal or band other than the printed value and its printed band."""
    printed = _printed_values()
    violations = []
    for name, owners in PRINTED_OWNERS.items():
        places = spec.DRAWING_PRECISION_BY_NAME[name]
        want = limits(printed[name], places, EXPLICIT_BANDS.get(name))
        for feature_name, key in owners:
            feature = features.get(feature_name, {})
            if key not in feature.get("requirements", ()):
                violations.append((name, feature_name, key, "not a requirement"))
            elif _nominal(feature, key) != printed[name] or feature[key] != want:
                violations.append((name, feature_name, key, _nominal(feature, key), feature[key]))
    return violations


def test_every_printed_band_has_a_requirement_owner() -> None:
    """One-fact coverage: every printed dimension reaches prechips as a
    listed requirement band whose nominal is the value the sheet prints and
    whose band is that value's printed band."""
    assert set(PRINTED_OWNERS) == set(spec.DRAWING_PRECISION_BY_NAME)
    assert set(_printed_values()) == set(spec.DRAWING_PRECISION_BY_NAME)
    claimed = [owner for owners in PRINTED_OWNERS.values() for owner in owners]
    assert len(claimed) == len(set(claimed))
    assert one_fact_violations(_features()) == []


def test_hole_callout_bands_are_the_printed_bands() -> None:
    """The hole callouts print at two places; their exported bands are about
    those printed values. A drilled Ø (clearance or tap drill) carries the
    title block's DRILLED HOLES band; the tap drills print 7.94 and 3.80 while
    the taps keep their true drill size as tap_drill_mm."""
    features = _features()
    studs = range(1, len(spec.CLAMP_STUD_POINTS) + 1)
    drilled = (
        *((f"hold_down_h{i}", "dia") for i in range(1, 5)),
        *((f"stud_tap_s{i}", "dia") for i in studs),
        ("pivot_tap", "dia"),
    )
    for name, key in (
        *drilled,
        *((f"hold_down_h{i}_counterbore", key) for i in range(1, 5) for key in ("dia", "depth")),
        *((f"stud_tap_s{i}", "depth") for i in studs),
        ("stud_tap_drills", "depth"),
        ("pivot_tap", "depth"),
        ("pivot_tap_drill", "depth"),
    ):
        feature = features[name]
        nominal = _nominal(feature, key)
        assert nominal == round(nominal, 2), (name, key)
        band = spec.DRILLED_BAND if (name, key) in drilled else None
        assert feature[key] == limits(nominal, 2, band), (name, key)
        assert key in feature["requirements"], (name, key)
    assert features["stud_tap_s1"]["dia_nominal"] == 7.94
    assert features["stud_tap_s1"]["tap_drill_mm"] == spec.CLAMP_STUD_DRILL_DIA
    assert features["pivot_tap"]["dia_nominal"] == 3.80
    assert "dia" not in features["pivot_tap_drill"]
    assert features["pivot_tap"]["tap_drill_mm"] == spec.PIVOT_TAP_DRILL_DIA


def test_every_exported_nominal_lies_in_its_band() -> None:
    """prechips refuses a nominal outside its requirement band: every
    exported nominal is the printed value, inside the printed band."""
    for name, feature in _features().items():
        for field, nominal in feature.items():
            key = field.removesuffix("_nominal") if field.endswith("_nominal") else None
            key = field.removeprefix("nominal_") if field.startswith("nominal_") else key
            if key is None or key not in feature:
                continue
            low, high = feature[key]
            assert low <= nominal <= high, (name, field, nominal, feature[key])


def test_exported_bands_are_the_printed_bands() -> None:
    features = _features()
    for name, nominal, band in (
        ("locating_bore", spec.LOCATING_BORE_DIA, spec.LOCATING_BORE_BAND),
        ("rod_pin_hole", spec.ROD_PIN_HOLE_DIA, spec.ROD_PIN_HOLE_BAND),
    ):
        assert features[name]["dia"] == [round(nominal + band[1], 3), round(nominal + band[0], 3)]
    # StandDrop prints at the general .XXX band, measured from the pad tops
    stand = features["stand_top"]
    band = printed_band_mm(spec.DRAWING_PRECISION_BY_NAME["StandDrop"])
    assert stand["height"] == [round(spec.STAND_DROP - band, 3), round(spec.STAND_DROP + band, 3)]
    assert stand["height_from"] == "pad_tops"
    # the rest tops print once, as RestTopHeight at its authored places, and a
    # rest seated on its floor (two .XXX sizes stacked) stays inside that band
    band = printed_band_mm(spec.DRAWING_PRECISION_BY_NAME["RestTopHeight"])
    rests = features["rail_rest_tops"]["height"]
    assert rests == [round(spec.REST_TOP_HEIGHT - band, 3), round(spec.REST_TOP_HEIGHT + band, 3)]
    stack = 2.0 * printed_band_mm(3)
    assert rests[0] <= spec.REST_HEIGHT - spec.REST_POCKET_DEPTH - stack
    assert rests[1] >= spec.REST_HEIGHT - spec.REST_POCKET_DEPTH + stack
    # the rod-pin ream's coordinates from the bore print with their own band in
    # the schedule, and that band is the exported one (X as station, Y as
    # height, both from the locating bore)
    row = next(row for row in spec.FEATURE_SCHEDULE if row[0] == "P")
    hole = features["rod_pin_hole"]
    assert hole["height_from"] == "locating_bore"
    for key, nominal, printed in zip(("station", "height"), spec.ROD_PIN_HOLE_XY, row[2:4]):
        value, plus = re.fullmatch(r"(-?\d+\.\d{3}) \u00b1(\d\.\d{3})", printed).groups()
        assert float(value) == round(nominal, 3)
        assert hole[key] == [round(nominal - float(plus), 3), round(nominal + float(plus), 3)]
    # its worst corner stays inside a quarter of the rocker rod hole's zone
    zone = float(rocker.GEOMETRIC_TOLERANCES_MM["rod-pin hole position"])
    assert float(plus) * 2**0.5 <= 0.25 * zone / 2.0


def test_hub_stand_carries_the_hub_and_clears_the_strap() -> None:
    # the highest printed stand stays under the lowest accepted hub face: the
    # longest hub on the thinnest strap the rocker print accepts ...
    strap_band = printed_band_mm(rocker_notes.DEFAULT_DRAWING_PRECISION)
    thinnest_strap = rocker.ARM_THICKNESS - strap_band
    longest_step = (rocker.HUB_LENGTH + rocker.HUB_LENGTH_BAND[0] - thinnest_strap) / 2.0
    band = printed_band_mm(spec.DRAWING_PRECISION_BY_NAME["StandDrop"])
    lowest_drop = spec.STAND_DROP - band
    assert lowest_drop >= longest_step
    # ... and 2 mm under the strap where its annulus reaches past the hub
    assert lowest_drop >= 2.0
    # the drilled bore, at its largest, still holds the hub
    assert spec.STAND_BORE + 0.10 < rocker.HUB_DIA


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    number = _config.parts("ch-rocker-arm-tl-profile-fixture")["number"]
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", number)


def test_notes_follow_the_simplicity_policy() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert 1 <= len(lines) <= 4
    assert not re.search(r"\d", spec.DRAWING_NOTES)
    assert spec.BUILT_UP_PERMISSION_NOTE in lines
    assert "GROUND" not in spec.DRAWING_NOTES


def test_draw_script_passes_the_precision_gate() -> None:
    script = Path(drawing.__file__)
    assert script.name in _drawing_contract.PRECISION_MIGRATED_DRAWINGS
    assert not _drawing_contract.drawing_specification_violations(
        script.read_text(encoding="utf-8"), filename=script.name
    )


class _PixelDrawing:
    """The failed section D-D seat: a 738x470 px view window fitted to the
    sheet at 1.649 px/mm; ``ViewZoomTo2`` fits a sheet box into it."""

    WINDOW_PX = (738, 470)
    FIT_PX_PER_M = 1649.0

    def __init__(self) -> None:
        self.px_per_m = self.FIT_PX_PER_M
        self.zooms: list[tuple[float, ...]] = []
        self.rebuilds = 0

    def GetCurrentSheet(self):  # noqa: N802
        return types.SimpleNamespace(SetScale=lambda *_args: True)

    def ViewZoomTo2(self, x0, y0, _z0, x1, y1, _z1):  # noqa: N802
        self.zooms.append((x0, y0, x1, y1))
        self.px_per_m = min(
            self.WINDOW_PX[0] / (x1 - x0), self.WINDOW_PX[1] / (y1 - y0)
        )

    def ViewZoomtofit2(self):  # noqa: N802
        self.px_per_m = self.FIT_PX_PER_M

    def EditRebuild3(self):  # noqa: N802
        self.rebuilds += 1
        return True


class _PixelLabel:
    """A native view label whose ``GetExtent`` floors its true box, a fixed
    offset from its anchor, to the window's current pixel grid."""

    def __init__(self, window: _PixelDrawing, anchor, corner_offset, size) -> None:
        self.window = window
        self.anchor = list(anchor)
        self.corner_offset = corner_offset
        self.size = size
        self.read_px_per_m: list[float] = []

    def true_lower_left(self) -> tuple[float, float]:
        return tuple(a + o for a, o in zip(self.anchor, self.corner_offset))

    def GetExtent(self):  # noqa: N802
        px = self.window.px_per_m
        self.read_px_per_m.append(px)
        x0, y0 = self.true_lower_left()
        corners = (x0, y0, x0 + self.size[0], y0 + self.size[1])
        x0, y0, x1, y1 = (math.floor(value * px) / px for value in corners)
        return (x0, y0, 0.0, x1, y1, 0.0)

    def GetAnnotation(self):  # noqa: N802
        return self

    def GetPosition(self):  # noqa: N802
        return (*self.anchor, 0.0)

    def SetPosition2(self, x, y, _z):  # noqa: N802
        self.anchor = [x, y]
        return True


def test_section_label_is_placed_and_read_zoomed_onto_its_box(monkeypatch) -> None:
    """Section D-D's label lands on its request on a small, fitted window.

    At 1.649 px/mm a pixel is 0.61 mm, so the fitted readback could not
    resolve the 0.5 mm landing check: run 4c569a1fc15f read the box
    0.56/-0.24 mm off after both corrections.  Zoomed onto the box, every
    readback that moves or judges the label resolves about a tenth of a
    millimetre, and the fit is restored afterwards.
    """
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    window = _PixelDrawing()
    target = drawing.SECTION_LABEL_LOWER_LEFT
    # Measured on the green builds: the box's lower-left sits (-23.02, -16.01)
    # mm from the label's anchor and the box is 45.75 x 16.20 mm.
    label = _PixelLabel(
        window,
        anchor=(target[0] + 0.0236, target[1] + 0.0155),
        corner_offset=(-0.02302, -0.01601),
        size=(0.04575, 0.0162),
    )
    view = types.SimpleNamespace(GetNotes=lambda: (label,))
    adapter = types.SimpleNamespace(currentModel=window)

    drawing._position_view_label(adapter, view, target, label="section D-D label")

    assert max(abs(a - b) for a, b in zip(label.true_lower_left(), target)) < 0.0002
    assert window.rebuilds >= 1
    assert len(window.zooms) == 1
    x0, y0, x1, y1 = window.zooms[0]
    assert x0 < target[0] and y0 < target[1]
    assert x1 > target[0] + label.size[0] and y1 > target[1] + label.size[1]
    assert all(px >= 5000.0 for px in label.read_px_per_m[1:])
    assert window.px_per_m == window.FIT_PX_PER_M
