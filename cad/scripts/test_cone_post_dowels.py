"""#917 S1: the MHA-016 / MHA-091 dowel pair and the swing-platform fit-up range.

SolidWorks-free.  The fit-up process (user ruling via Main, 2026-09-26) sets
the post on finger-tight screws, then match-drills a Ø1/8 dowel pair through
the platform into the post foot.  A7 (``POST_DOWEL_WEBS``) proves every wall
round those holes, the pins' engagement in both parts at the plate-stock
limits, and that nothing stands proud of the base-slide face.  The expected
values in the plan (C:/src/dt-logs/917-fitup-process-budget-20260926.md
section 3) are quoted beside each computed one; a mismatch is reported, not
bent into the test.
"""

from __future__ import annotations

import math
from pathlib import Path

import build_cone_lock_knob
import build_cone_pivot_post as post_part
import build_cone_swing_platform as part
import cone_pivot_post_installation
import cone_pivot_post_spec as post_spec
import cone_post_dowel_spec as dowel
import cone_swing_platform_spec as spec
import pytest
from _fit_limits import deviations

MM_PER_IN = 25.4
TARGET = 2.0  # rule 12 web target
FLOOR = 1.5  # rule 12 hard floor
MIN_ENGAGEMENT_D = 1.5


def _plate_hole_max() -> float:
    return dowel.PLATE_DOWEL_REAM_LIMITS[1]


def _post_hole_max() -> float:
    return dowel.POST_DOWEL_REAM_LIMITS[1]


def _edge_distance(point, start, end) -> float:
    """Normal distance from a plan point to the line through start and end."""
    (px, pz), (ax, az), (bx, bz) = point, start, end
    return abs((bx - ax) * (az - pz) - (ax - px) * (bz - az)) / math.hypot(bx - ax, bz - az)


def post_dowel_webs() -> dict[str, float]:
    """Every wall round the dowel pair, each at the largest reamed hole."""
    plate_r = _plate_hole_max() / 2.0
    post_r = _post_hole_max() / 2.0
    dowels = dowel.POST_DOWEL_PLATE_XZ
    south_z = part.NORTH_OVERHANG - part.PLATE_LEN
    east = ((-part.HALF_WIDTH_N, part.NORTH_OVERHANG), (-part.EAST_HALF_S, south_z))
    west = ((part.WEST_HALF_N, part.NORTH_OVERHANG), (part.WEST_HALF_S, south_z))
    screws = post_spec.ATTACHMENT_X
    return {
        "foot rim": post_spec.BLOCK_DIA / 2.0 - post_spec.POST_DOWEL_RADIUS - post_r,
        "post through-hole": min(
            math.dist(d, (sx, 0.0))
            for d in post_spec.POST_DOWEL_XZ
            for sx in (-screws, screws)
        )
        - post_spec.ATTACHMENT_THRU_DIA / 2.0
        - post_r,
        "plate tap major": min(
            math.dist(d, tap)
            for d in dowels
            for tap in (part.POST_MOUNT_WEST_XZ, part.POST_MOUNT_EAST_XZ)
        )
        - spec.POST_MOUNT_THREAD_DIA / 2.0
        - plate_r,
        "plate south edge": min(z for _x, z in dowels) - south_z - plate_r,
        "east edge": min(_edge_distance(d, *east) for d in dowels) - plate_r,
        "west edge": min(_edge_distance(d, *west) for d in dowels) - plate_r,
        "notch cap E": min(math.dist(d, part.NOTCH_CAP_E_XZ) for d in dowels)
        - part.SLOT_W / 2.0
        - plate_r,
        "knob collar in plan": min(math.dist(d, (part.SLOT_E_X, part.SLOT_E_Z)) for d in dowels)
        - build_cone_lock_knob.COLLAR_DIA / 2.0
        - plate_r,
        "journal bore vertical": post_spec.BORE_HEIGHT
        - (post_spec.BORE_DIA + deviations(post_spec.RUNNING_BORE_BAND)[1]) / 2.0
        - dowel.POST_DOWEL_BLIND_DEPTH,
    }


# The plan's section 3 table.  East/west are quoted there as lower bounds.
PLAN_WEBS = {
    "foot rim": 5.97,
    "post through-hole": 13.85,
    "plate tap major": 14.25,
    "plate south edge": 9.47,
    "east edge": 18.2,
    "west edge": 30.8,
    "notch cap E": 24.5,
    "knob collar in plan": 22.2,
    "journal bore vertical": 19.0,
}


def test_the_dowel_constants_are_the_ruled_ones_and_platform_spec_exports_them() -> None:
    """The names are fixed: conegear's C2 imports them from the platform spec."""
    assert dowel.POST_DOWEL_PLATE_XZ == ((-2.914, -179.050), (2.914, -205.298))
    assert dowel.POST_DOWEL_DIA == pytest.approx(0.125 * MM_PER_IN)
    assert dowel.POST_DOWEL_LENGTH == pytest.approx(0.5 * MM_PER_IN)
    assert dowel.POST_DOWEL_BLIND_DEPTH == 8.5
    assert dowel.POST_DOWEL_RECESS == 0.25
    assert dowel.POST_DOWEL_PART_NUMBER == "MHA-151"
    assert dowel.POST_DOWEL_SKU == "98381A304"
    for name in (
        "POST_DOWEL_PLATE_XZ",
        "POST_DOWEL_DIA",
        "POST_DOWEL_BLIND_DEPTH",
        "POST_DOWEL_RECESS",
    ):
        assert getattr(spec, name) is getattr(dowel, name), name


def test_the_pattern_is_the_posts_crank_axis_diameter_90_deg_from_the_screws() -> None:
    """On the post's crank-axis diameter at the screws' pitch radius."""
    i = math.radians(post_spec.INCLINE_DEG)
    r = spec.POST_ATTACHMENT_SPACING / 2.0
    for (x, z), sign in zip(dowel.POST_DOWEL_PLATE_XZ, (1.0, -1.0), strict=True):
        assert x == pytest.approx(sign * r * -math.sin(i), abs=6e-4)
        assert z == pytest.approx(part.POST_LOCAL_Z + sign * r * math.cos(i), abs=6e-4)
    # 90 deg from the tapped pair.
    (nx, nz), (sx, sz) = dowel.POST_DOWEL_PLATE_XZ
    (wx, wz), (ex, ez) = part.POST_MOUNT_WEST_XZ, part.POST_MOUNT_EAST_XZ
    dot = (nx - sx) * (wx - ex) + (nz - sz) * (wz - ez)
    assert abs(dot) / (math.dist((nx, nz), (sx, sz)) * spec.POST_ATTACHMENT_SPACING) < 1e-4
    assert part.POST_DOWEL_PATTERN_ERROR <= 6e-4


def test_the_post_reads_the_platform_pattern_through_its_installation() -> None:
    """Plate local -> machine (Ry +incline) -> post local (Ry 180 undone)."""
    assert cone_pivot_post_installation.POST_ROTATION_Y_DEG == 180.0
    north, south = post_spec.POST_DOWEL_XZ
    assert north == (0.0, -13.444)
    assert south == (0.0, 13.444)
    assert post_spec.POST_DOWEL_RADIUS == pytest.approx(post_spec.ATTACHMENT_X, abs=1e-3)
    # The platform drive-train machine check: both dowels at the post's x,
    # the north one 13.444 toward machine +z.
    i = math.radians(post_spec.INCLINE_DEG)
    cx, cz = post_spec.POST_DOWEL_CENTRE_PLATE_XZ
    for (x, z), (px, pz) in zip(dowel.POST_DOWEL_PLATE_XZ, post_spec.POST_DOWEL_XZ, strict=True):
        dx, dz = x - cx, z - cz
        mx, mz = dx * math.cos(i) + dz * math.sin(i), -dx * math.sin(i) + dz * math.cos(i)
        assert (-mx, -mz) == pytest.approx((px, pz), abs=6e-4)


def test_press_fit_in_the_plate_slip_fit_in_the_post() -> None:
    """MHA-151, 98381A304: Ø0.1251-0.1253 in.  Plate Ø.1245 +.0002/0 (press),
    post Ø.1255 +.0002/0 (slip), never looser than .1257."""
    pin_min, pin_max = dowel.POST_DOWEL_PIN_DIA_RANGE
    assert (pin_min, pin_max) == pytest.approx((0.1251 * MM_PER_IN, 0.1253 * MM_PER_IN))
    assert dowel.DOWEL_REAM_BAND == pytest.approx((0.0002 * MM_PER_IN, 0.0))
    assert dowel.PLATE_DOWEL_REAM_DIA == pytest.approx(0.1245 * MM_PER_IN)
    assert dowel.POST_DOWEL_REAM_DIA == pytest.approx(0.1255 * MM_PER_IN)
    plate_min, plate_max = dowel.PLATE_DOWEL_REAM_LIMITS
    post_min, post_max = dowel.POST_DOWEL_REAM_LIMITS
    assert pin_min - plate_max > 0.0  # always interference
    assert post_min - pin_max >= 0.0  # always clearance
    assert post_max <= 0.1257 * MM_PER_IN + 1e-9
    assert dowel.PLATE_DOWEL_INTERFERENCE == pytest.approx((0.0102, 0.0203), abs=1e-4)
    assert dowel.POST_DOWEL_CLEARANCE == pytest.approx((0.0051, 0.0152), abs=1e-4)


def test_callouts_name_the_mating_part_and_the_reamer() -> None:
    assert dowel.PLATE_DOWEL_CALLOUT == "MATCH-DRILL/REAM WITH\nMHA-016 AT ASSEMBLY;\nREAM (.1245 IN)"
    assert dowel.POST_DOWEL_CALLOUT == (
        "MATCH-DRILL/REAM WITH\nMHA-091 AT ASSEMBLY;\nREAM (.1255 IN) FROM FOOT"
    )


def test_a7_post_dowel_webs() -> None:
    """Every web >= 2.0 (floor 1.5)."""
    webs = post_dowel_webs()
    assert set(webs) == set(PLAN_WEBS)
    for name, web in webs.items():
        assert web >= TARGET, f"{name}: {web:.3f}"
    # Pinned so a geometry move shows here (computed, not the plan's).
    assert webs == pytest.approx(
        {
            "foot rim": 5.965,
            "post through-hole": 13.845,
            "plate tap major": 14.253,
            "plate south edge": 9.472,
            "east edge": 18.153,
            "west edge": 31.028,
            "notch cap E": 24.212,
            "knob collar in plan": 22.157,
            "journal bore vertical": 18.725,
        },
        abs=1e-3,
    )


def test_a7_engagement_in_both_parts_at_the_plate_stock_limits() -> None:
    d = dowel.POST_DOWEL_DIA
    thin = spec.PLATE_THICKNESS - spec.PLATE_STOCK_BAND
    thick = spec.PLATE_THICKNESS + spec.PLATE_STOCK_BAND
    plate = (thin - dowel.POST_DOWEL_RECESS, thick - dowel.POST_DOWEL_RECESS)
    post = tuple(dowel.POST_DOWEL_LENGTH - e for e in reversed(plate))
    assert plate == pytest.approx((5.97, 6.23))
    assert post == pytest.approx((6.47, 6.73))
    assert min(plate) / d >= MIN_ENGAGEMENT_D
    assert min(post) / d >= MIN_ENGAGEMENT_D
    # The pin never bottoms in the blind hole, even with the depth at its .X
    # short limit, so the press depth sets the recess.
    assert dowel.POST_DOWEL_BLIND_DEPTH - spec.TITLE_BLOCK_BAND_BY_PLACES[1] > max(post)


def test_a7_blind_depth_clears_the_cone_journal_bore() -> None:
    bore_floor = (
        post_spec.BORE_HEIGHT
        - (post_spec.BORE_DIA + deviations(post_spec.RUNNING_BORE_BAND)[1]) / 2.0
    )
    assert dowel.POST_DOWEL_BLIND_DEPTH + TARGET <= bore_floor
    # Worst case: the .X depth band and the drill point beyond it.
    point = _post_hole_max() / 2.0 * 0.60086
    worst = bore_floor - (dowel.POST_DOWEL_BLIND_DEPTH + spec.TITLE_BLOCK_BAND_BY_PLACES[1] + point)
    assert worst >= TARGET


def test_a7_nothing_stands_proud_of_the_base_slide_face() -> None:
    pin_end = -dowel.POST_DOWEL_RECESS  # from the slide face, + is proud
    assert pin_end <= -0.25


def test_both_parts_model_the_holes_at_nominal() -> None:
    plate = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name="PostDowelHoles"' in plate
    assert "POST_DOWEL_PLATE_XZ" in plate
    assert part.PLATE_DOWEL_HOLE_SPEC.kind == "drilled_fractional"
    assert part.PLATE_DOWEL_HOLE_SPEC.end == "through_all"
    assert part.PLATE_DOWEL_HOLE_SPEC.overrides_mm == {"HoleDiameter": dowel.PLATE_DOWEL_REAM_DIA}
    post = Path(post_part.__file__).read_text(encoding="utf-8")
    assert 'name="PostDowelHoles"' in post
    assert post_part.POST_DOWEL_HOLE_SPEC.kind == "drilled_fractional"
    assert post_part.POST_DOWEL_HOLE_SPEC.end == "blind"
    assert post_part.POST_DOWEL_HOLE_SPEC.depth_mm == dowel.POST_DOWEL_BLIND_DEPTH
    assert post_part.POST_DOWEL_HOLE_SPEC.overrides_mm == {"HoleDiameter": dowel.POST_DOWEL_REAM_DIA}
    # The post's analytic volume carries the two blind holes.
    assert post_part.POST_DOWEL_HOLES_MM3 == pytest.approx(
        2.0
        * (
            math.pi * (dowel.POST_DOWEL_REAM_DIA / 2.0) ** 2 * dowel.POST_DOWEL_BLIND_DEPTH
            + math.pi / 3.0 * (dowel.POST_DOWEL_REAM_DIA / 2.0) ** 3 * 0.60086
        )
    )
    # Each ream band rides the hole feature, set through deviations().
    for source in (plate, post):
        assert "dia_tolerance_mm=DOWEL_REAM_TOLERANCE_MM" in source
    assert dowel.DOWEL_REAM_TOLERANCE_MM == (
        -deviations(dowel.DOWEL_REAM_BAND)[0],
        deviations(dowel.DOWEL_REAM_BAND)[1],
    )
