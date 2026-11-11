"""The 64T's straight inclined tooth space (owner ruling 2026-11-10, #2332 A)."""

from __future__ import annotations

import math

import pytest

import dt_crank_drive_gear_spec as spec
from straight_gash import StraightGash, midface_gap_azimuth_rad

BETA = math.radians(spec.TOOTH_INCLINATION_DEG)


def _dot(a, b) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_frame_is_orthonormal_and_the_tooth_line_is_right_hand() -> None:
    gash = spec.TOOTH_SPACE
    r, n, d = gash.radial, gash.section_tangential, gash.tooth_line
    for vector in (r, n, d):
        assert _dot(vector, vector) == pytest.approx(1.0)
    for a, b in ((r, n), (r, d), (n, d)):
        assert _dot(a, b) == pytest.approx(0.0, abs=1e-15)
    # Inclined by beta to the axis, leaning along +t: the azimuth of a tooth
    # line advances counter-clockwise as z grows (right hand).
    assert d[2] == pytest.approx(math.cos(BETA))
    assert _dot(d, gash.tangent) == pytest.approx(math.sin(BETA))
    south, north = gash.point(spec.PITCH_DIA / 2.0, 0.0, 0.0), gash.point(
        spec.PITCH_DIA / 2.0, 0.0, spec.FACE_WIDTH
    )
    assert math.atan2(north[1], north[0]) > math.atan2(south[1], south[0])


def test_crossing_is_the_south_quarter_on_the_printed_grid() -> None:
    assert spec.TOOTH_SPACE_CROSSING == pytest.approx(0.07 * 25.4)
    assert spec.TOOTH_SPACE_CROSSING == pytest.approx(spec.FACE_WIDTH / 4.0, abs=0.127)
    band = 0.01 * 25.4
    assert 0.0 < spec.TOOTH_SPACE_CROSSING - band
    assert spec.TOOTH_SPACE_CROSSING + band < spec.FACE_WIDTH / 2.0
    assert spec.TOOTH_SPACE.crossing_z_mm == spec.TOOTH_SPACE_CROSSING


def test_a_tooth_is_centred_on_plus_x_on_the_pitch_circle_at_mid_face() -> None:
    """The assembly phases the 16T against this datum (PINION_SEED_DEG)."""
    gash, radius = spec.TOOTH_SPACE, spec.PITCH_DIA / 2.0
    across = gash.transverse_offset_mm(0.0, spec.FACE_WIDTH / 2.0)
    centre = gash.azimuth_rad + math.asin(across / radius)
    assert centre == pytest.approx(math.pi / spec.TEETH, abs=1e-12)
    # Reproduced without the module: the bisector at mid-face is the
    # crossing bisector moved (F/2 - zc) tan(beta) along its tangent.
    shift = (spec.FACE_WIDTH / 2.0 - spec.TOOTH_SPACE_CROSSING) * math.tan(BETA)
    assert gash.azimuth_rad == pytest.approx(math.pi / spec.TEETH - math.asin(shift / radius))
    with pytest.raises(ValueError, match="integer"):
        midface_gap_azimuth_rad(2, radius, 13.0, 1.0, 7.0)


def test_crossing_section_is_the_printed_screw_section_within_three_microns() -> None:
    """The printed thickness, span and root come from the screw model."""
    form, screw = spec.TOOTH_SPACE_FORM, spec.STOCK_PROFILE
    low = max(form.flank_parameter_min, screw.flank_parameter_min)
    high = min(form.flank_parameter_max, screw.flank_parameter_max)
    deviations = []
    for side in (-1, 1):
        for i in range(41):
            u = low + (high - low) * i / 40
            x, y = form.flank_point(u, side)
            gx, gy = x, y / math.cos(BETA)
            hx, hy = screw.flank_point(u, side)
            nx, ny = screw.flank_normal(u, side)
            deviations.append((gx - hx) * nx + (gy - hy) * ny)
    assert max(abs(value) for value in deviations) < 0.003


def test_removed_volume_matches_a_slice_integral() -> None:
    """The closed form against an independent grid over transverse slices."""
    gash, form = spec.TOOTH_SPACE, spec.TOOTH_SPACE_FORM
    closed = gash.removed_volume_mm3(form)
    ra, face = gash.blank_radius_mm, gash.face_width_mm
    slices, nx, nt = 8, 160, 320
    x0 = form.root_radius_min_mm - 0.05
    dx, dt = (ra - x0) / nx, 7.0 / nt
    total = 0.0
    for k in range(slices):
        z = (k + 0.5) * face / slices
        count = 0
        for i in range(nx):
            x = x0 + (i + 0.5) * dx
            for j in range(nt):
                t = -3.5 + (j + 0.5) * dt
                if x * x + t * t > ra * ra:
                    continue
                # Back along the tooth line to the cutter's plane.
                y = (t - (z - gash.crossing_z_mm) * math.tan(BETA)) * math.cos(BETA)
                if abs(y) < 1.5 and not form.contains_material(x, y):
                    count += 1
        total += count * dx * dt * face / slices
    assert closed == pytest.approx(total, rel=0.004)
    # Not the naive section-area prism, which ignores the cylinder's edge.
    naive = form.gap_area_mm2 * face / math.cos(BETA)
    assert abs(closed - naive) > 0.02 * naive


def test_volume_refuses_a_screw_section_and_a_short_form() -> None:
    gash = spec.TOOTH_SPACE
    with pytest.raises(ValueError, match="own"):
        gash.removed_volume_mm3(spec.STOCK_PROFILE)
    short = StraightGash(
        spec.TOOTH_INCLINATION_DEG,
        spec.TOOTH_SPACE_CROSSING,
        gash.azimuth_rad,
        spec.FACE_WIDTH,
        spec.TOOTH_SPACE_FORM.blank_radius_mm + 0.1,
    )
    with pytest.raises(ValueError, match="reach past"):
        short.removed_volume_mm3(spec.TOOTH_SPACE_FORM)
