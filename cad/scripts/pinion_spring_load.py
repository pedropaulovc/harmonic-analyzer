r"""Loaded shape of the MHA-114 return leaf: a planar large-rotation elastica.

PURE MATH (numpy), no SolidWorks and no spring-module imports: the geometry
module builds its nominal from :func:`nominal_case`, and the drive train gates
every printed corner through :func:`corner_cases` and :func:`load`.

The leaf is clamped at the foot screw head's WEST rim.  From there to the
contact everything bends: the rest of the pad, the tapered flat, the bend,
the blade and the crest.  The flank contact is frictionless, so past it the
crest remainder and the flick carry no moment and keep their formed shape.
The linear, rigid-at-the-bend-exit cantilever this replaced left out the
root's compliance and the rolling contact's changing arm; for the tapered
foot that approximation misstated yield safety by 2x.

The pad is SET from the actual parked strap (SPRING SET, pinion_rig_fitup):
the fitter slides the free leaf west until its crest nips a touch leaf on the
parked flank, stops the foot's free end there, and pushes the pad a further
gage pin's diameter west before the seat is spotted.  So the free crest's
penetration into the parked flank is the pin less the leaf, whatever the
flank's printed offset or the parked strap's lean; :func:`load` finds each
case's pad station from that set, never from a seat station.

Frame: the leaf's part-local frame (+x machine east, +y up, y 0 the base
top).  The path is the neutral axis, THICK/2 inside the wall from the sketch's
inside surface: at y = t/2 along the foot, radius R + t/2 round each bend.
Heading theta runs from pi (west, at the clamp) down through the bend and the
crest.  The strap is the hull of its two end caps: the pivot cap (radius
half_width + rb) and the arbor cap (half_width + rt, c2c up the axis).  Unequal
caps tilt the straight east flank by tau off the axis; at axis angle a (strap
lean + swing, toward +x from +y) the flank's east normal is
N = (cos(a + tau), -sin(a + tau)) and its up direction U = (sin(a + tau),
cos(a + tau)).  The flank pushes the crest along +N with force F, so
dM/ds = F (U . heading).

Unknowns per case: F, the clamp moment M0 and the crest arc length Lc to the
contact.  Residuals at the contact (the integration's end): M = 0, the
tangent parallel to the flank, and the neutral axis t/2 off it.  Newton with a
forward-difference Jacobian, every case in one vectorised batch; RK4 with a
fixed step count per segment (refining them 4x moves F by < 3e-5 N).
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

import numpy as np

# RK4 steps per segment: foot, bend, blade, crest.
_STEPS = (16, 24, 48, 12)
_NEWTON_ITERATIONS = 40
_FD_STEPS = (1e-6, 1e-5, 1e-6)  # F (N), M0 (N.mm), Lc (mm)
_TOLERANCE = (1e-9, 1e-11, 1e-11)  # moment, angle, offset residuals
_FLICK_SAMPLES = 8


@dataclass(frozen=True)
class LeafDesign:
    """The printed formed profile, its blank and the foot screw that clamps it.

    Lengths in mm, from the foot's free end as the print baselines them.
    """

    screw_east: float  # nominal foot screw axis east of the pivot axis
    hole_from_end: float  # screw hole centre from the free end
    clamp_r: float  # the screw head's radius: its west rim is the clamp edge
    pad_len: float  # PadLen: full pad width this far from the free end
    taper_len: float  # TaperLen: the blank narrows linearly to the strip over it
    foot_len: float  # FootLen: free end to the bend tangent
    r_bend: float
    free_kink_h: float  # FreeKinkH / FreeKinkV: free kink start
    free_kink_v: float
    r_kink: float
    free_tip_h: float  # FreeTipH: the free flick tip
    flat_len: float


@dataclass(frozen=True)
class Strap:
    """The parked strap in the leaf's frame, its nominal outline."""

    pivot: tuple[float, float]
    lean_deg: float  # parked axis lean, toward +x from +y
    half_width: float  # each end cap's nominal radius
    c2c: float  # pivot to the arbor end cap's centre, up the axis


@dataclass(frozen=True)
class Material:
    modulus: float  # MPa
    yield_stress: float  # MPa


@dataclass(frozen=True)
class PadSet:
    """SPRING SET: the touch leaf the crest nips on the parked flank and the
    gage pin the pad is then pushed west by, both mm."""

    touch_leaf: float
    pin: float


@dataclass(frozen=True)
class Loaded:
    """Per-case loaded contact, every array shaped like the cases."""

    force: np.ndarray  # N, along the flank normal
    arm: np.ndarray  # the force's moment arm about the pivot
    station: np.ndarray  # contact up the straight flank from its pivot-cap end
    flank_len: np.ndarray  # the straight flank's length
    stress: np.ndarray  # MPa, peak fibre stress anywhere clamp..contact
    crest_before: np.ndarray  # deg of crest arc between blade and contact
    crest_after: np.ndarray  # deg of crest arc past the contact, least tip case
    second_clear: np.ndarray  # nearest approach elsewhere (outside the contact)
    tip_clear: np.ndarray  # flick tip off the flank, least tip case
    touch_tip_clear: np.ndarray  # free flick tip off the flank at the set's touch
    foot_dip: np.ndarray  # lowest neutral-axis point of the foot above t/2
    shift: np.ndarray  # the set pad's station east of the nominal screw
    contact: tuple[np.ndarray, np.ndarray]  # contact point, crest's west face
    tip: tuple[np.ndarray, np.ndarray]  # flick tip's west face, least clear case


def curved_factor(neutral_r, thick):
    """Winkler's inner-fibre stress over the straight-beam 6M/(b t^2)."""
    inner, outer = neutral_r - thick / 2.0, neutral_r + thick / 2.0
    r_neutral = thick / np.log(outer / inner)
    e = neutral_r - r_neutral
    return (r_neutral - inner) / (thick * e * inner) / (6.0 / thick**2)


_CASE_KEYS = (
    "t", "w", "wp", "pl", "tl", "rb", "rt", "c2c", "park", "swing", "set", "hole",
    "foot_len", "r_b", "fkh", "fkv", "r_k",
)


def corner_cases(
    design: LeafDesign,
    *,
    thick: tuple[float, ...],
    width: tuple[float, ...],
    pad_width: tuple[float, ...],
    pad_len: tuple[float, ...],
    taper_len: tuple[float, ...],
    caps: tuple[tuple[float, float], ...],
    c2c: tuple[float, ...],
    park: tuple[float, ...],
    engage: tuple[float, ...],
    set_error: tuple[float, ...],
    hole: tuple[float, ...],
    formed_band: float,
) -> dict[str, np.ndarray]:
    """Every combination of the given values: FootLen, BendR, FreeKinkH,
    FreeKinkV and KinkR each end of ``formed_band``; stock ``thick``/``width``;
    the blank's ``pad_width``/``pad_len``/``taper_len``; the strap's
    (bottom, top) cap radius deviations ``caps`` and ``c2c`` deviation; its
    parked lean deviation ``park`` (radians), posed parked and at each
    ``engage`` swing past it; the set's pad error ``set_error`` (mm west,
    more penetration); the clamp hole's deviation ``hole`` from its nominal
    distance to the free end.  FreeTipH and FlatLen only end the crest, so
    :func:`load` walks them on the solved shapes."""
    rows = []
    formed = list(itertools.product((-formed_band, formed_band), repeat=5))
    for (foot, bend, kink_h, kink_v, kink_r), t, w, wp, pl, tl, (rb, rt), dc, p, e, dh in (
        itertools.product(
            formed, thick, width, pad_width, pad_len, taper_len, caps, c2c, park,
            set_error, hole,
        )
    ):
        for swing in (p, *(p + phi for phi in engage)):
            rows.append(
                (
                    t, w, wp, pl, tl, rb, rt, dc, p, swing, e, dh,
                    design.foot_len + foot, design.r_bend + bend,
                    design.free_kink_h + kink_h, design.free_kink_v + kink_v,
                    design.r_kink + kink_r,
                )
            )
    return _cases(rows)


def nominal_case(
    design: LeafDesign, *, thick: float, width: float, pad_width: float, swing: float
) -> dict[str, np.ndarray]:
    """The one case at every nominal, posed ``swing`` past the parked lean."""
    return _cases(
        [
            (
                thick, width, pad_width, design.pad_len, design.taper_len,
                0.0, 0.0, 0.0, 0.0, swing, 0.0, 0.0,
                design.foot_len, design.r_bend, design.free_kink_h,
                design.free_kink_v, design.r_kink,
            )
        ]
    )


def _cases(rows) -> dict[str, np.ndarray]:
    table = np.array(rows, dtype=float)
    return {key: table[:, i] for i, key in enumerate(_CASE_KEYS)}


def _flank(strap: Strap, c, swing) -> dict:
    """The straight east flank at ``swing``: its normal, up direction, the
    pivot cap's tangent point and length, and both caps."""
    hb, ht = strap.half_width + c["rb"], strap.half_width + c["rt"]
    c2c = strap.c2c + c["c2c"]
    tau = np.arcsin((ht - hb) / c2c)
    a = math.radians(strap.lean_deg) + swing
    nx, ny = np.cos(a + tau), -np.sin(a + tau)
    ux, uy = np.sin(a + tau), np.cos(a + tau)
    return dict(
        nx=nx, ny=ny, ux=ux, uy=uy, hb=hb, ht=ht, heading=np.pi / 2.0 - (a + tau),
        t1x=strap.pivot[0] + hb * nx, t1y=strap.pivot[1] + hb * ny,
        length=c2c * np.cos(tau),
        ax=strap.pivot[0] + c2c * np.sin(a), ay=strap.pivot[1] + c2c * np.cos(a),
    )


def flank_gap(f: dict, px, py):
    """Clearance of (px, py) east of the strap outline ``f`` (:func:`_flank`,
    every entry broadcastable against the points)."""
    along = (px - f["t1x"]) * f["ux"] + (py - f["t1y"]) * f["uy"]
    side = (px - f["t1x"]) * f["nx"] + (py - f["t1y"]) * f["ny"]
    pivot_cap = np.hypot(px - (f["t1x"] - f["hb"] * f["nx"]), py - (f["t1y"] - f["hb"] * f["ny"]))
    arbor_cap = np.hypot(px - f["ax"], py - f["ay"])
    return np.where(
        along < 0.0,
        pivot_cap - f["hb"],
        np.where(along > f["length"], arbor_cap - f["ht"], side),
    )


def _shape(design: LeafDesign, strap: Strap, c, shift) -> dict:
    """The formed free profile of each case, its free end ``shift`` east of
    the nominal screw's."""
    t, r_b, r_k = c["t"], c["r_b"], c["r_k"]
    fe = strap.pivot[0] + design.screw_east + design.hole_from_end + shift
    x_clamp = fe - design.hole_from_end - c["hole"] - design.clamp_r
    xb = fe - c["foot_len"]
    if np.any(x_clamp <= xb):
        raise AssertionError("spring screw head reaches the bend")
    ksx, ksy = fe - c["fkh"], t + c["fkv"]
    dx, dy = xb - ksx, t + r_b - ksy
    lean = np.arctan2(dy, dx) + np.arccos(r_b / np.hypot(dx, dy))
    blade = np.hypot(ksx - (xb - np.cos(lean) * r_b), ksy - (t + r_b - np.sin(lean) * r_b))
    return dict(
        fe=fe, x_clamp=x_clamp, d0=fe - x_clamp, foot=x_clamp - xb, lean=lean,
        blade=blade, rb_n=r_b + t / 2.0, rk_n=r_k + t / 2.0,
        kcx=ksx + np.cos(lean) * r_k, kcy=ksy + np.sin(lean) * r_k,
    )


def free_crest_deg(c, g, tip_h, flat_len):
    """Formed crest arc of each shape ``g`` whose flat, ``flat_len`` long,
    ends ``tip_h`` west of the free end (FreeTipH).  With b = crest angle -
    lean, the tip's x is kink_cx - R_K cos b + flat sin b."""
    radius = np.hypot(c["r_k"], flat_len)
    arg = (g["fe"] - tip_h - g["kcx"]) / radius
    if np.any(np.abs(arg) > 1.0):
        raise AssertionError("spring flick tip is out of reach of its crest")
    return np.degrees(g["lean"] + np.arctan2(c["r_k"], flat_len) + np.arcsin(arg))


def _free_tip(c, g, crest_deg, flat_len):
    """The free flick tip's outer (west) face."""
    end = g["lean"] - np.radians(crest_deg)  # the crest's end normal, east
    ex = g["kcx"] - (c["r_k"] + c["t"]) * np.cos(end)
    ey = g["kcy"] - (c["r_k"] + c["t"]) * np.sin(end)
    return ex - flat_len * np.sin(end), ey + flat_len * np.cos(end)


def set_shift(design: LeafDesign, strap: Strap, pad_set: PadSet, c):
    """Each case's pad station east of the nominal screw after SPRING SET.

    At the touch the free crest's outer face stands ``touch_leaf`` off the
    parked flank; the pin (plus the case's set error) then moves the pad west,
    so the crest penetrates (pin + error) N_x - touch_leaf."""
    g = _shape(design, strap, c, np.zeros_like(c["t"]))
    f = _flank(strap, c, c["park"])
    reach = (g["kcx"] - f["t1x"]) * f["nx"] + (g["kcy"] - f["t1y"]) * f["ny"] - (c["r_k"] + c["t"])
    return (pad_set.touch_leaf - reach) / f["nx"] - (pad_set.pin + c["set"])


def _width(c, d):
    """Blank width ``d`` along the path from the free end."""
    f = np.clip((d - c["pl"]) / c["tl"], 0.0, 1.0)
    return c["wp"] + (c["w"] - c["wp"]) * f


def _integrate(modulus, c, g, f, force, m0, lc, *, record=False):
    t = c["t"]
    ei_per_w = modulus * t**3 / 12.0
    ux, uy = f["ux"], f["uy"]
    x, y = g["x_clamp"].copy(), t / 2.0
    th = np.full_like(x, math.pi)
    m = m0.copy()
    s = np.zeros_like(x)
    segments = (
        (g["foot"], 0.0),
        (g["rb_n"] * (np.pi / 2.0 - g["lean"]), -1.0 / g["rb_n"]),
        (g["blade"], 0.0),
        (lc, -1.0 / g["rk_n"]),
    )
    nodes = []

    def rate(th_, m_, s_, k0):
        cth, sth = np.cos(th_), np.sin(th_)
        ei = ei_per_w * _width(c, g["d0"] + s_)
        return cth, sth, k0 + m_ / ei, force * (cth * ux + sth * uy)

    for (length, k0), n in zip(segments, _STEPS, strict=True):
        h = length / n
        rows = [(x, y, th, m, s)]
        for _ in range(n):
            a = rate(th, m, s, k0)
            b = rate(th + 0.5 * h * a[2], m + 0.5 * h * a[3], s + 0.5 * h, k0)
            e = rate(th + 0.5 * h * b[2], m + 0.5 * h * b[3], s + 0.5 * h, k0)
            d = rate(th + h * e[2], m + h * e[3], s + h, k0)
            x = x + h / 6.0 * (a[0] + 2.0 * b[0] + 2.0 * e[0] + d[0])
            y = y + h / 6.0 * (a[1] + 2.0 * b[1] + 2.0 * e[1] + d[1])
            th = th + h / 6.0 * (a[2] + 2.0 * b[2] + 2.0 * e[2] + d[2])
            m = m + h / 6.0 * (a[3] + 2.0 * b[3] + 2.0 * e[3] + d[3])
            s = s + h
            if record:
                rows.append((x, y, th, m, s))
        if record:
            nodes.append(tuple(np.stack(v, axis=1) for v in zip(*rows, strict=True)))
    return x, y, th, m, nodes


def _residual(modulus, c, g, f, force, m0, lc):
    x, y, th, m, _ = _integrate(modulus, c, g, f, force, m0, lc)
    offset = (x - f["t1x"]) * f["nx"] + (y - f["t1y"]) * f["ny"]
    return np.stack((m, th - f["heading"], offset - c["t"] / 2.0), axis=1)


def _outside_well(gap, *, toward_end: bool):
    """Least gap outside the contact's own well.  ``gap`` runs along the leaf;
    the contact is its last node (``toward_end``) or its first.  From the
    contact the gap must rise monotonically; any node past the first fall
    back belongs to another approach."""
    g = gap if toward_end else gap[:, ::-1]
    rising = np.diff(g, axis=1) > 1e-12  # rises toward the contact end
    n = g.shape[1]
    last = np.where(rising.any(axis=1), n - 2 - np.argmax(rising[:, ::-1], axis=1), -1)
    outside = np.arange(n)[None, :] <= last[:, None]
    return np.where(outside, g, np.inf).min(axis=1)


def load(
    design: LeafDesign,
    strap: Strap,
    material: Material,
    pad_set: PadSet,
    c: dict[str, np.ndarray],
    *,
    tip_cases: tuple[tuple[float, float], ...],
) -> Loaded:
    """Set, solve and measure every case.  ``tip_cases`` lists the (FreeTipH,
    FlatLen) pairs that end the crest; each result keeps the least of them."""
    shift = set_shift(design, strap, pad_set, c)
    g = _shape(design, strap, c, shift)
    f = _flank(strap, c, c["swing"])
    t, rk_n = c["t"], g["rk_n"]
    # Start from the free crest's penetration on a guessed 0.3 N/mm rate.
    penetration = (c["r_k"] + t) - (
        (g["kcx"] - f["t1x"]) * f["nx"] + (g["kcy"] - f["t1y"]) * f["ny"]
    )
    force = np.maximum(penetration, 0.5) * 0.3
    lc = rk_n * (g["lean"] + np.pi / 2.0 - f["heading"])
    cx, cy = g["kcx"] - f["nx"] * (c["r_k"] + t / 2.0), g["kcy"] - f["ny"] * (c["r_k"] + t / 2.0)
    m0 = force * ((g["x_clamp"] - cx) * f["ux"] + (t / 2.0 - cy) * f["uy"])

    n = force.shape[0]
    c4 = {k: np.concatenate([v] * 4) for k, v in c.items()}
    g4 = {k: np.concatenate([v] * 4) for k, v in g.items()}
    f4 = {k: np.concatenate([v] * 4) for k, v in f.items()}
    for _ in range(_NEWTON_ITERATIONS):
        r = _residual(
            material.modulus, c4, g4, f4,
            np.concatenate([force, force + _FD_STEPS[0], force, force]),
            np.concatenate([m0, m0, m0 + _FD_STEPS[1], m0]),
            np.concatenate([lc, lc, lc, lc + _FD_STEPS[2]]),
        )
        r0 = r[:n]
        if all(np.max(np.abs(r0[:, k])) < _TOLERANCE[k] for k in range(3)):
            break
        jac = np.stack(
            [(r[(k + 1) * n:(k + 2) * n] - r0) / _FD_STEPS[k] for k in range(3)], axis=2
        )
        step = np.linalg.solve(jac, -r0[..., None])[..., 0]
        # Damped: at most 0.5 N and 2 mm of crest per iteration.
        scale = np.minimum(1.0, 0.5 / np.maximum(np.abs(step[:, 0]), 1e-12))
        scale = np.minimum(scale, 2.0 / np.maximum(np.abs(step[:, 2]), 1e-12))
        force, m0, lc = force + scale * step[:, 0], m0 + scale * step[:, 1], lc + scale * step[:, 2]
    else:
        raise AssertionError("spring elastica did not converge")
    if np.any(force <= 0.0):
        raise AssertionError("spring leaf has lost contact with the strap")

    x, y, _, _, nodes = _integrate(material.modulus, c, g, f, force, m0, lc, record=True)

    # Peak stress, Winkler-corrected in both bends.
    stress = np.zeros_like(force)
    for (_, _, _, mm, s), factor in zip(
        nodes, (1.0, curved_factor(g["rb_n"], t), 1.0, curved_factor(rk_n, t)), strict=True
    ):
        width = _width({k: v[:, None] for k, v in c.items()}, g["d0"][:, None] + s)
        peak = 6.0 * np.abs(mm) / (width * t[:, None] ** 2) * np.reshape(factor, (-1, 1))
        stress = np.maximum(stress, peak.max(axis=1))

    # The chain's west (outer) face, clamp .. contact.
    fc = {k: v[:, None] for k, v in f.items()}
    xs = np.concatenate([seg[0] for seg in nodes], axis=1)
    ys = np.concatenate([seg[1] for seg in nodes], axis=1)
    ths = np.concatenate([seg[2] for seg in nodes], axis=1)
    half = t[:, None] / 2.0
    before = flank_gap(fc, xs - half * np.sin(ths), ys + half * np.cos(ths))
    second = _outside_well(before, toward_end=True)

    # Past the contact: the crest remainder and the flick, moment-free.
    th_u = f["heading"]
    kc = (x + rk_n * np.sin(th_u), y - rk_n * np.cos(th_u))
    crest_before = np.degrees(lc / rk_n)
    crest_after = np.full_like(force, np.inf)
    tip_clear = np.full_like(force, np.inf)
    touch_tip_clear = np.full_like(force, np.inf)
    tip = (np.zeros_like(force), np.zeros_like(force))
    frac = np.linspace(0.0, 1.0, _FLICK_SAMPLES + 1)[None, :]
    touch = _shape(design, strap, c, shift + pad_set.pin + c["set"])
    parked = _flank(strap, c, c["park"])
    for tip_h, flat in tip_cases:
        crest_deg = free_crest_deg(c, g, tip_h, flat)
        remainder = np.radians(crest_deg) - lc / rk_n
        heading = th_u[:, None] - remainder[:, None] * frac
        crest_x = kc[0][:, None] - rk_n[:, None] * np.sin(heading)
        crest_y = kc[1][:, None] + rk_n[:, None] * np.cos(heading)
        end = heading[:, -1:]
        flick_x = crest_x[:, -1:] + flat * frac * np.cos(end)
        flick_y = crest_y[:, -1:] + flat * frac * np.sin(end)
        px = np.concatenate([crest_x, flick_x[:, 1:]], axis=1)
        py = np.concatenate([crest_y, flick_y[:, 1:]], axis=1)
        pth = np.concatenate([heading, np.repeat(end, _FLICK_SAMPLES, axis=1)], axis=1)
        ox, oy = px - half * np.sin(pth), py + half * np.cos(pth)
        after = flank_gap(fc, ox, oy)
        second = np.minimum(second, _outside_well(after, toward_end=False))
        crest_after = np.minimum(crest_after, np.degrees(remainder))
        worse = after[:, -1] < tip_clear
        tip_clear = np.where(worse, after[:, -1], tip_clear)
        tip = (np.where(worse, ox[:, -1], tip[0]), np.where(worse, oy[:, -1], tip[1]))
        # The set's touch must be the crest's: the free flick tip, where the
        # crest nips the touch leaf, stands further off the parked flank.
        free_tip = _free_tip(c, touch, crest_deg, flat)
        touch_tip_clear = np.minimum(
            touch_tip_clear, flank_gap(parked, *free_tip) - pad_set.touch_leaf
        )

    face = (x - t / 2.0 * f["nx"], y - t / 2.0 * f["ny"])
    return Loaded(
        force=force,
        arm=(face[0] - strap.pivot[0]) * f["ux"] + (face[1] - strap.pivot[1]) * f["uy"],
        station=(face[0] - f["t1x"]) * f["ux"] + (face[1] - f["t1y"]) * f["uy"],
        flank_len=f["length"],
        stress=stress,
        crest_before=crest_before,
        crest_after=crest_after,
        second_clear=second,
        tip_clear=tip_clear,
        touch_tip_clear=touch_tip_clear,
        foot_dip=(nodes[0][1] - half).min(axis=1),
        shift=shift,
        contact=face,
        tip=tip,
    )
