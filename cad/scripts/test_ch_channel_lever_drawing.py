"""Offline contracts for the channel-lever drawing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import build_ch_channel_assembly as assembly
import build_ch_channel_lever as lever
import ch_amplitude_bar_spec
import ch_channel_lever_notes as notes
import ch_channel_lever_spec as spec
import draw_ch_channel_lever as drawing
import export_features
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _gtol_face import FaceGeometry
from _hole_spec import blind_cut_dia_mm
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _printed_tolerance import printed_deviations


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/ch-channel-lever.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/ch-channel-lever.pdf")
    assert drawing.PNG.as_posix().endswith("/png/ch-channel-lever_drawing.png")
    assert DRAWINGS_BY_NAME["ch_channel_lever"].script == Path(drawing.__file__).resolve()


def test_kept_dimensions_are_exactly_the_marked_set() -> None:
    assert lever.DRAWING_DIMENSIONS is notes.DRAWING_DIMENSIONS
    assert drawing.DRAWING_DIMENSIONS is notes.DRAWING_DIMENSIONS
    marked = set().union(*notes.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    assert set(drawing.FRONT_KEEP).isdisjoint(drawing.TOP_KEEP)


def test_every_marked_dimension_states_its_places() -> None:
    assert lever.DRAWING_PRECISION is notes.DRAWING_PRECISION
    assert set(notes.DRAWING_PRECISION) == set(notes.DRAWING_DIMENSIONS)
    for feature, names in notes.DRAWING_DIMENSIONS.items():
        assert set(notes.DRAWING_PRECISION[feature]) == names


def test_drawing_is_precision_migrated() -> None:
    assert "draw_ch_channel_lever.py" in PRECISION_MIGRATED_DRAWINGS


def test_bands_are_native_on_the_model_from_named_constants() -> None:
    assert model_toleranced_dimensions(lever) == {
        ("Hub", "HubLength"): "*deviations(HUB_LENGTH_BAND)",
        ("LeverBody", "LeverThick"): "*deviations(LEVER_THICKNESS_BAND)",
        ("PlateOffsetReference", "PlateOffset"): "PLATE_OFFSET_TOLERANCE",
    }
    # The drilled arms print plain, at the title block's .XXX row (Q1-A).
    assert spec.BAR_PIN_X_TOLERANCE == spec.LEVER_SPRING_X_TOLERANCE == pytest.approx(0.127)


def test_every_tight_band_names_its_mate_or_function() -> None:
    callouts = {**drawing.FRONT_CALLOUTS, **drawing.TOP_CALLOUTS}
    for name in ("FulcrumDia", "LeverThick", "HubLength", "PlateOffset"):
        assert callouts[name]
    assert drawing.SHAFT_NUMBER in callouts["FulcrumDia"]
    # Fit audit question 1 (owner ruling 2026-11-24): the bore is drilled F
    # and its callout carries no number; the 63 microinch symbol is gone.
    assert callouts["FulcrumDia"].startswith("F DRILL THRU\n")
    assert "REAM" not in callouts["FulcrumDia"]
    assert not any(ch.isdigit() for ch in callouts["FulcrumDia"].split(drawing.SHAFT_NUMBER)[0])
    assert spec.SURFACE_FINISHES == ()
    assert drawing.BAR_NUMBER in callouts["LeverThick"]
    assert drawing.SHAFT_NUMBER in callouts["HubLength"]
    # The plate's tight offset names the bars it spaces (rule 4), in the
    # numbered note its location dimension flags (rule 7).
    flag = callouts["PlateOffset"]
    assert drawing.BAR_NUMBER not in flag
    assert flag == f"SEE NOTE {drawing.PLATE_OFFSET_NOTE_NUMBER}"
    assert drawing.PLATE_OFFSET_NOTE.startswith(f"{drawing.PLATE_OFFSET_NOTE_NUMBER}. ")
    assert drawing.BAR_NUMBER in drawing.PLATE_OFFSET_NOTE
    # Rule 7: a hole location carries its value and band only.
    for location in ("BarPinCx", "SpringCx"):
        assert location not in callouts
    # F (.257, +.004/0 DRILLED HOLES) on the .250 (.0000/-.0008) shaft: the
    # constant offset the spring takes up is .0070-.0118 in of clearance.
    least = spec.PIVOT_HOLE_DIA + spec.PIVOT_HOLE_BAND[1] - 6.35
    most = spec.PIVOT_HOLE_DIA + spec.PIVOT_HOLE_BAND[0] - (6.35 - 0.02032)
    assert (least / 25.4, most / 25.4) == pytest.approx((0.0070, 0.0118), abs=1e-5)


def test_walls_clear_the_floor_at_worst_case() -> None:
    assert spec.TIP_ARC_CX == spec.LEVER_SPRING_X
    for wall, value in spec.WALL_MIN.items():
        if wall in spec.WALL_SHORTFALL_ACCEPTED:
            assert WALL_FLOOR_MM <= value < WALL_TARGET_MM, wall
            continue
        assert value >= WALL_TARGET_MM, wall
    # The tapered tip's wall is the one owner-accepted shortfall (#3113),
    # and the registry row carries its exception.
    assert spec.WALL_SHORTFALL_ACCEPTED == {"spring hole to tip and edges"}
    import _config

    exceptions = _config.parts("ch-channel-lever")["machinist_exceptions"]
    assert any("#21" in item["where"] and item["kind"] == "minor" for item in exceptions)


def test_root_corners_print_r065_and_judge_r070() -> None:
    """Owner ruling 2026-11-23, tool audit Q9: the two bar-to-hub roots print
    2X R.065 at three places (.060-.070, the title block's .XXX), naming why
    they stand over INSIDE CORNERS R.040 MAX."""
    assert notes.ROOT_CORNER_R == pytest.approx(_in(0.065))
    assert (notes.ROOT_CORNER_R_MIN, notes.ROOT_CORNER_R_MAX) == pytest.approx(
        (_in(0.060), _in(0.070))
    )
    assert notes.DRAWING_DIMENSIONS["RootCorners"] == {"RootCornerR"}
    assert notes.DRAWING_PRECISION["RootCorners"]["RootCornerR"] == 3
    assert notes.ROOT_CORNER_PREFIX == "2X R"
    assert drawing.FRONT_CALLOUTS["RootCornerR"] == "NOTHING SEATS IN\nTHESE CORNERS"
    # The fillet's edges: where the bar's edges meet the hub's round.
    half, hub_r = spec.BAR_TALL / 2.0, spec.HUB_DIA / 2.0
    assert math.hypot(notes.ROOT_CORNER_X, half) == pytest.approx(hub_r)
    assert notes.ROOT_CORNER_ANGLE_DEG == pytest.approx(140.43, abs=0.01)
    # At R.070 each corner stays inside the hub's square: under its top
    # (the calipers still read the .48 across the round) and short of its
    # side, in the plate's own thickness.
    assert (notes.ROOT_CORNER_REACH_X, notes.ROOT_CORNER_REACH_Y) == pytest.approx(
        (4.4775, 5.0145), abs=1e-4
    )
    assert notes.ROOT_CORNER_HUB_TOP_MARGIN == pytest.approx(1.0815, abs=1e-4)
    # The root gains metal on its bisector at every radius in the band over
    # the sharp corner the title block allowed, and over its R.040 MAX.
    gain_min = notes.root_bisector_metal(notes.ROOT_CORNER_R_MIN)
    assert gain_min == pytest.approx(0.0844, abs=1e-4)
    assert gain_min > notes.root_bisector_metal(_in(0.040)) + 0.02
    # Both corners' metal, against the builder's analytic volume.
    assert notes.root_corner_volume(notes.ROOT_CORNER_R) == pytest.approx(
        0.1816, abs=1e-4
    )


def test_the_end_tapers_from_its_own_station_to_a_tangent_tip() -> None:
    """#3113: full depth through the bar pin and the bar's notch to the 5.50
    taper start, outboard of the bar pin, then straight edges tangent to the tip."""
    assert spec.TAPER_START_X - spec.BAR_PIN_X >= ch_amplitude_bar_spec.BAR_DEPTH / 2.0
    assert spec.BAR_TALL == pytest.approx(9.398)
    tip_depth = 2.0 * spec.TIP_RADIUS
    # Owner ruling 2026-11-18: R.167, blunter than the photo's ~0.8, so the
    # finished #21 wall meets the floor.
    assert tip_depth / spec.BAR_TALL == pytest.approx(0.90, abs=0.01)
    x, y = spec.taper_tangent_point()
    # The edge from the taper start meets the tip circle at right angles to
    # its radius there.
    edge = (x - spec.TAPER_START_X, y - spec.BAR_TALL / 2.0)
    radius = (x - spec.TIP_ARC_CX, y)
    assert math.hypot(*radius) == pytest.approx(spec.TIP_RADIUS)
    assert edge[0] * radius[0] + edge[1] * radius[1] == pytest.approx(0.0, abs=1e-9)
    assert spec.TAPER_START_X < x and y < spec.BAR_TALL / 2.0


def test_twenty_long_hubs_still_float_between_the_keepers() -> None:
    stations = drawing.STATIONS
    # The pitch prints .300 (7.62) +.001/.000: each hub may come out the
    # printed maximum, .001 past the model.
    lower, upper = printed_deviations(
        spec.HUB_LENGTH,
        notes.DRAWING_PRECISION["Hub"]["HubLength"],
        (spec.HUB_LENGTH_BAND[1], spec.HUB_LENGTH_BAND[0]),
        unit=spec.UNIT,
    )
    growth = stations * upper
    assert spec.HUB_LENGTH_BAND[1] == 0.0  # sh_vn_pivot_pin_bar_spec's pitch minimum
    assert growth < sum(assembly.KEEPER_HUB_FLOAT)


def test_plate_band_is_the_notch_allowance() -> None:
    # The notch is derived from the plate's maximum only: the -.004 side
    # (D23) leaves MHA-CH-01's .124 +.007/0 where it was.
    assert spec.LEVER_THICKNESS_BAND == pytest.approx((0.002 * 25.4, -0.004 * 25.4))
    assert ch_amplitude_bar_spec.LEVER_THICKNESS_BAND is spec.LEVER_THICKNESS_BAND
    assert ch_amplitude_bar_spec.TOP_NOTCH_WIDTH == pytest.approx(0.124 * 25.4)


def _bowed_margin_in(monkeypatch: pytest.MonkeyPatch, lower: float) -> float:
    """BAR_GAP mid_span_bowed over the bar running floor, inch, with the
    plate's lower deviation at ``lower`` (mm) and everything else as printed."""
    import ch_channel_assembly_spec as asm
    import sh_vn_pivot_pin_bar_spec as pin

    monkeypatch.setattr(spec, "LEVER_THICKNESS_BAND", (spec.LEVER_THICKNESS_BAND[0], lower))
    monkeypatch.setattr(asm, "_PIN_BUDGET", pin.joint_budget())
    bowed = asm.bar_gap_budget()["mid_span_bowed"]
    return (bowed - asm._BAR_RUNNING_FLOOR) / 25.4


def test_each_side_of_the_plate_band_is_earned_by_its_named_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Necessity ch-channel-lever N-02 (delegated ruling 2026-11-25 (Main), no
    precedent, #2144 (rulings.md D23)): the plate prints .118 +.002/-.004.
    Thick side: the narrowest top notch keeps the running floor on the
    thickest plate, and .002 more does not. Thin side: the bowed mid-span bar
    gap keeps the .001 the shop reads over its floor (D14's criterion), and
    .001 less does not. The register quotes these numbers."""
    import ch_amplitude_bar_spec as bar
    import machinist_necessity
    import rocker_bank_layout as bank

    upper, lower = spec.LEVER_THICKNESS_BAND
    notch_min = bar.TOP_NOTCH_WIDTH + bar.TOP_NOTCH_WIDTH_BAND[1]
    air = notch_min - (spec.LEVER_THICKNESS + upper)
    air_loose = air - 0.002 * 25.4
    assert air >= bank.RUNNING_FLOOR - 1e-9
    assert air_loose < bank.RUNNING_FLOOR
    assert air_loose == pytest.approx(0.0508, abs=1e-4)

    reading_unit = 0.001
    margin = _bowed_margin_in(monkeypatch, lower)
    margin_loose = _bowed_margin_in(monkeypatch, lower - 0.001 * 25.4)
    assert margin >= reading_unit
    assert margin_loose < reading_unit
    assert (round(margin, 4), round(margin_loose, 4)) == (0.0011, 0.0006)

    config = Path(__file__).resolve().parents[1] / "config"
    entries = {e.id: e for e in machinist_necessity.load_necessity(config, "ch-channel-lever")}
    source = entries["N-02"].source
    for quoted in (".0508", ".0011", ".0006"):
        assert quoted in source, quoted


def test_plate_is_located_from_one_hub_face() -> None:
    assert spec.PLATE_OFFSET == pytest.approx((spec.HUB_LENGTH - spec.LEVER_THICKNESS) / 2.0)
    assert notes.DRAWING_PRECISION["PlateOffsetReference"] == {"PlateOffset": 3}
    assert lever.PLATE_OFFSET_SKETCH == "PlateOffsetReference"
    # The line runs from the hub face to the plate face on the hub silhouette.
    start, end = lever._PLATE_OFFSET_START, lever._PLATE_OFFSET_END
    assert start[0] == end[0] == spec.HUB_DIA / 2.0
    assert start[1] - end[1] == pytest.approx(spec.PLATE_OFFSET)


def test_draw_view_math_matches_the_spec() -> None:
    assert drawing._BAR_PIN_DIA == blind_cut_dia_mm(spec.BAR_PIN_HOLE_SPEC)
    assert drawing._SPRING_HOLE_DIA == blind_cut_dia_mm(spec.SPRING_EYE_HOLE_SPEC)


def test_sheet_runs_at_1_to_1_with_1_to_2_isometric() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    assert drawing.ISO_SCALE == (1, 2)
    assert notes.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:2"


def test_hub_diameter_lands_on_its_near_rim() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'set_near_side_diameter(hub_dia[0], "hub diameter")' in source
    assert source.index("set_near_side_diameter(") < source.index(
        "set_dimension_callouts(adapter, front_annotations"
    )


def test_one_centreline_joins_the_holes_along_the_bar() -> None:
    """r5 machinist review (clarity): the bore, the #47 and the #21 holes
    lie on the bar's mid-height axis, so one centreline bisecting the two
    long edges prints their cross-bar position and the .37 bar symmetric
    about it. The edges are picked inboard of the bar pin, where the
    full-depth edges run parallel (#3113: outboard they taper)."""
    assert spec.BAR_PIN_X / 2.0 < spec.BAR_PIN_X < spec.TAPER_START_X
    assert spec.NOSE_RADIUS == spec.BAR_TALL / 2.0


def test_part_stamps_make_critical_drawing_properties() -> None:
    import _config

    part = _config.parts("ch-channel-lever")
    # Owner ruling 2026-11-03 (stock order #2173): 1018 steel from the bought
    # 5/16 x 1 in flat supersedes the 2026-10-15 gray cast iron.
    assert part["material_specification"] == "LOW-CARBON STEEL, E.G. 1018 CF"
    assert part["material"] == "LOW-CARBON STEEL, E.G. 1018 CF"
    assert "material_family" not in part
    assert lever.MATERIAL == "Plain Carbon Steel"
    assert "5/16 x 1 in 1018" in part["process"]
    # A conversion coat, not paint: the hub faces, plate faces and bores
    # keep their bands with nothing masked (as the rocker arms, MHA-CH-06).
    assert part["finish"] == "matte black oxide, oil sealed"
    assert int(part["quantity"]) == 20


def test_the_plate_stays_flat_by_its_route_not_by_a_frame() -> None:
    """#2340: the plate's bow is bounded by its thickness and plate-offset
    bands (the bar-to-bar gap spends exactly those), so the sheet carries no
    flatness frame; the
    registry route takes equal stock off both faces of the bought 5/16 flat,
    and the figure it states is the model's."""
    import _config

    process = _config.parts("ch-channel-lever")["process"]
    bar = 0.3125 * 25.4
    per_face = (bar - spec.LEVER_THICKNESS) / 2.0 / 25.4
    assert f"{per_face:.3f}".lstrip("0") in process


_FEATURE_KINDS = {
    "hub_near_face": "face",
    "hub_far_face": "face",
    "plate_near_face": "face",
    "plate_far_face": "face",
    "hub": "boss",
    "outline": "profile",
    "fulcrum_bore": "hole",
    "bar_pin_hole": "hole",
    "spring_hole": "hole",
}


def _in(value_in: float) -> float:
    return value_in * 25.4


def _plane(normal: tuple[float, float, float], offset_mm: float) -> FaceGeometry:
    point = tuple(value * offset_mm / 1000 for value in normal)
    return FaceGeometry(None, 4001, (*normal, *point), normal, ())


def _cylinder(dia_mm: float, x_mm: float) -> FaceGeometry:
    r = dia_mm / 2
    box = tuple(v / 1000 for v in (x_mm - r, -r, -1.0, x_mm + r, r, 1.0))
    return FaceGeometry(None, 4002, (x_mm / 1000, 0.0, 0.0, 0.0, 0.0, 1.0, r / 1000), None, box)


def test_the_lever_is_a_feature_export_part_with_one_owner_per_face() -> None:
    assert "ch_channel_lever" in export_features.SUPPORTED_PARTS
    manifest = export_features.requirement_manifest("ch_channel_lever")
    kinds = {name: feature["kind"] for name, feature in manifest["features"].items()}
    assert kinds == _FEATURE_KINDS
    assert manifest["construction"] == "one_piece"
    assert manifest["notes"]["manufacturing"] == [drawing.PLATE_OFFSET_NOTE]
    selectors = export_features.feature_selectors("ch_channel_lever")
    hub, plate = spec.HUB_LENGTH / 2, spec.LEVER_THICKNESS / 2
    # Each taper edge's outward normal is radial at its tangent point.
    tx, ty = spec.taper_tangent_point()
    nx, ny = (tx - spec.TIP_ARC_CX) / spec.TIP_RADIUS, ty / spec.TIP_RADIUS
    taper = nx * tx + ny * ty
    expected = {
        "hub_near_face": [_plane((0.0, 0.0, -1.0), hub)],
        "hub_far_face": [_plane((0.0, 0.0, 1.0), hub)],
        "plate_near_face": [_plane((0.0, 0.0, -1.0), plate)],
        "plate_far_face": [_plane((0.0, 0.0, 1.0), plate)],
        "hub": [_cylinder(spec.HUB_DIA, 0.0)],
        "outline": [
            _plane((0.0, 1.0, 0.0), spec.BAR_TALL / 2),
            _plane((0.0, -1.0, 0.0), spec.BAR_TALL / 2),
            _plane((nx, ny, 0.0), taper),
            _plane((nx, -ny, 0.0), taper),
            _cylinder(2 * spec.TIP_RADIUS, spec.TIP_ARC_CX),
        ],
        "fulcrum_bore": [_cylinder(spec.PIVOT_HOLE_DIA, 0.0)],
        "bar_pin_hole": [
            _cylinder(blind_cut_dia_mm(spec.BAR_PIN_HOLE_SPEC), spec.BAR_PIN_X)
        ],
        "spring_hole": [
            _cylinder(blind_cut_dia_mm(spec.SPRING_EYE_HOLE_SPEC), spec.LEVER_SPRING_X)
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
    features = export_features.requirement_manifest("ch_channel_lever")["features"]
    assert features["hub_far_face"]["length"] == pytest.approx([_in(0.300), _in(0.301)])
    assert features["plate_near_face"]["offset"] == pytest.approx(
        [_in(0.089), _in(0.093)]
    )
    assert features["plate_near_face"]["offset_from"] == "hub_near_face"
    assert features["plate_far_face"]["thickness"] == pytest.approx(
        [_in(0.114), _in(0.120)]
    )
    assert features["hub"]["dia"] == pytest.approx([_in(0.47), _in(0.49)])
    outline = features["outline"]
    assert outline["bar_height"] == pytest.approx([_in(0.36), _in(0.38)])
    assert outline["taper_start"] == pytest.approx([_in(5.49), _in(5.51)])
    assert outline["tip_radius"] == pytest.approx([_in(0.162), _in(0.172)])
    assert outline["tip_callout"] == drawing.FRONT_CALLOUTS["TipRadius"]
    assert outline["root_corner_r"] == pytest.approx([_in(0.060), _in(0.070)])
    assert outline["root_corner_count"] == 2
    assert outline["root_corner_callout"] == drawing.FRONT_CALLOUTS["RootCornerR"]
    bore = features["fulcrum_bore"]
    assert bore["dia"] == pytest.approx([_in(0.2570), _in(0.2610)], abs=1e-3)
    assert bore["process"] == "F DRILL" and bore["drill"] == "F"
    assert "finish_ra" not in bore
    pin, spring = features["bar_pin_hole"], features["spring_hole"]
    # The model drill diameter is the drill's mm size, .0785 to 1e-3 mm.
    assert pin["dia"] == pytest.approx([_in(0.0785), _in(0.0825)], abs=1e-3)
    assert pin["location"] == pytest.approx([_in(4.995), _in(5.005)])
    assert spring["dia"] == pytest.approx([_in(0.159), _in(0.163)], abs=1e-3)
    assert spring["location"] == pytest.approx([_in(6.887), _in(6.897)])
    assert (pin["drill"], spring["drill"]) == ("#47", "#21")
    assert spring["mate"] == drawing.HOLE_MATES["spring-eye hole"]
