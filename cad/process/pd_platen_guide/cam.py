"""FreeCAD CAM recipe for MHA-PD-11, the platen guide.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The rail's sizes come
from the feature export (its length, height and depth bands and the nine
#4-40 taps A1-A9); the blank, the skims, face levels, end passes, spots,
pecks and the stacks from ``plan.toml`` ``[parameters]`` and
``milling_cuts``; cutter diameters, speeds and feeds from the shop
(``shop/``) and the plan's authored drill settings. Every path is written
here (``rt.custom``): straight lines a recipe can state exactly. Typed here,
because neither record carries them: the #2 centre drill's catalogue
geometry (it sets the spot depth), the twist drills' 118° point, the
machine's Z top for the tap files' retract, the approach, safe and clearance
heights, the face overhang and the vise jaws' depth (keep-out shapes only).

Route (plan text in ``plan.toml``): one 3/8 x 1/2 in 1018 flat blank about
10.8 long, lying along the jaws on parallel stacks, centred, both ends out
past the jaws. Gripped across the 1/2 in faces: PG01 skims the underside U,
PG02 (U down) faces the top to the rough height, .055 over the finished.
Gripped on U and that top: PG03 skims the front face F, PG04 (F down) faces
the rear face R to the depth. One stack then goes under the top's edge
against the moving jaw, clear of the hole exits: PG05 mills both ends to
the length with the cutter's side, spots and drills all nine #43 holes
through from R from one zero; PG06-PG14 bring the tap guide over each for
tapping by hand. The holes come before the finished height: at .29 a
1/8 in parallel under either edge would sit under the hole exits. PG15
(U down, gripped on F and R on the same stacks) faces the top to the
height last, its last level .020 over the jaw tops.

Work frames (G54), each set in its setup; X0 is always the finished left
end (the sawn end plus the left-end skim), +X along the rail:
- PG01: Y0 the fixed jaw (a cold-finished 1/2 in face), Z0 the skimmed
  underside.
- PG02: Y0 the fixed jaw (the same face), Z0 the stacks' top (U), set from
  the miked height.
- PG03: Y0 the fixed jaw (the rough top), Z0 the skimmed front face.
- PG04/PG05: Y0 the fixed jaw (U), Z0 the stacks' top (F), set from the
  miked thickness.
- PG15: Y0 the fixed jaw (R), Z0 the stacks' top (U), set from the miked
  height.

Toolpath rules (owner rulings 2026-11-16): faces zigzag (ball screws),
plunges beside the stock at the cutting feed, real G0 above the stock. The
ends are milled with the cutter's side in one-way conventional passes. The
holes are tapped by hand (FluidNC cannot rigid-tap; owner, Pedro,
2026-11-17), the T-handle wrench's centre hole on the spring point of the
Fisher tap guide in the 1/2 in R8 collet (owner, Pedro, 2026-11-21: "use
https://littlemachineshop.com/products/tap-guide-fisher?variant=45472915226805
on r8 0.5 collet"), spindle off, the operator jogging Z down to push the
point home. FluidNC, like Grbl, refuses jogs while an M0 holds
the program (FluidNC wiki, "Single Block Mode",
http://wiki.fluidnc.com/en/features/single_block_mode), so each tap stop is
a file of its own that ends with M30 over its hole.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "pd_platen_guide"
COMMENT = "MHA-PD-11 platen guide"
# The nine taps the recipe makes, in X order (the export's tags A1-A9).
TAP_COUNT = 9
# Programs in order, each listing its operation keys. A program whose keys
# are grouped in tuples is one section per group (a FreeCAD Job), joined at
# M6 tool changes. A literal: dodo.py reads it with ast.literal_eval.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("PG01_underside", ("underside",)),
    ("PG02_top", ("top_skim",)),
    ("PG03_front", ("front_face",)),
    ("PG04_depth", ("rear_face",)),
    ("PG05_ends_drill", (("ends",), ("tap_spot",), ("tap_drill",))),
    ("PG06_tap_1", ("tap_1",)),
    ("PG07_tap_2", ("tap_2",)),
    ("PG08_tap_3", ("tap_3",)),
    ("PG09_tap_4", ("tap_4",)),
    ("PG10_tap_5", ("tap_5",)),
    ("PG11_tap_6", ("tap_6",)),
    ("PG12_tap_7", ("tap_7",)),
    ("PG13_tap_8", ("tap_8",)),
    ("PG14_tap_9", ("tap_9",)),
    ("PG15_height", ("top_face",)),
)
# The nine tap stops, PG06-PG14, one per tap in X order.
TAP_PROGRAMS = tuple(program for program in PROGRAMS if "_tap_" in program[0])
# Every program loads its own first tool (M6, the tool setter): each setup
# starts on whatever the mill last held, and each tap file before its
# retract (the tap guide).
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (the saw, the tap and the files are not).
CAM_TOOLS = ("em-half", "spot", "drill-43", "tap-guide")
IN = 25.4
# The Fisher tap guide's overall length, 3 1/8 in (its sellers' size,
# cad/config/shop-equipment/ tools.tap-guide-fisher): the most it stands
# below the collet face, taken off the tap stack for the tap's own reach.
TAP_GUIDE_OAL_MM = 3.125 * IN
# ANSI #2 combined drill and countersink, 60° included: the shop record names
# the tool, not its geometry.
CENTRE_DRILL = {
    "pilot_mm": 5 / 64 * IN,
    "pilot_length_mm": 5 / 64 * IN,
    "body_mm": 3 / 16 * IN,
    "point_deg": 60.0,
}
# Jobber drills' point (the shop records give the diameter only).
DRILL_POINT_DEG = 118.0
# A tap file's first motion: G53 G0 to machine Z0, the homed top. FluidNC
# sets an axis's machine position to its homing mpos_mm (default 0) after
# homing, and Z homes up (cad/config/shop-equipment/
# cnc.pm-30mv-controller: switches on all three axes); the owner (Pedro)
# confirmed it, answered in person 2026-11-21 (cnc rulings record): machine
# Z = 0 is the top of travel after homing.
MACHINE_Z_TOP_MM = 0.0
# Face passes start and finish with the cutter this far clear of the part's
# ends, and end passes this far clear of its faces, so every plunge and
# stepover link is in the air beside it.
APPROACH_MM = 2.54
# Faces reach at least this far past the faces the jaws grip.
FACE_OVERHANG_MM = 0.5
# Plunges and drill R planes start this far above the stock top: real G0
# brings the tool down to it.
SAFE_MM = 1.0
# Moves between cuts run this far above the stock top.
CLEAR_MM = 5.0
# Rapid re-entry into a pecked hole stops this far above the last peck.
PECK_REENTRY_MM = 0.5
# Keep-outs: each vise jaw's depth outward from the gripped face; the
# parallels' length (4 in, shop-equipment fixtures.parallels-lms-6745).
JAW_DEPTH_MM = IN
PARALLEL_LENGTH_MM = 4 * IN
# A plan number the recipe recomputes must agree to this (its rounding).
PLAN_TOL_MM = 0.01
# The #43 drill against the tap drill's printed band: the shop records the
# drill's nominal .089 in (2.2606), the band's floor is that size rounded to
# 2.261; anything closer than this is the same size.
SIZE_TOL_MM = 0.001


def _plan_operations(plan: dict[str, Any]):
    for setup in plan["setups"]:
        yield from setup.get("operations", ())


def _op_with_cut(
    plan: dict[str, Any], name: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    for op in _plan_operations(plan):
        for cut in op.get("milling_cuts", ()):
            if cut["name"] == name:
                return op, cut
    raise KeyError(f"plan has no milling cut {name!r}")


def _resolve(plan: dict[str, Any], value: Any, what: str) -> float:
    """A number, or a ``{{process.<parameter>}}`` binding read from [parameters]."""
    if isinstance(value, str):
        match = re.fullmatch(r"\{\{process\.(\w+)\}\}", value.strip())
        if not match:
            raise ValueError(
                f"{what} = {value!r}: only numbers and {{{{process.…}}}} bindings are read"
            )
        value = plan["parameters"][match.group(1)]
    return float(value)


def _cut(plan: dict[str, Any], name: str, key: str) -> float:
    """Field ``key`` of the plan's milling cut ``name``."""
    return _resolve(plan, _op_with_cut(plan, name)[1][key], f"'{name}' {key}")


def _setting(
    plan: dict[str, Any], shop: dict[str, Any], cut: str
) -> tuple[float, float]:
    """(rpm, mm/min) of the operation holding ``cut``: the shop setting it
    names (chip load × flutes × rpm), or, with no setting, the rpm and feed
    the cut itself authors."""
    op, record_cut = _op_with_cut(plan, cut)
    if "settings" not in op:
        return _cut(plan, cut, "rpm"), _cut(plan, cut, "feed_mm_min")
    record = shop["settings"][op["settings"]]
    rpm = float(record["rpm"])
    feed = record["chip_load_mm_per_tooth"] * record["flutes"] * rpm
    for key, expected in (("rpm", rpm), ("feed_mm_min", feed)):
        if key in record_cut and not math.isclose(
            _cut(plan, cut, key), expected, abs_tol=1e-3
        ):
            raise ValueError(
                f"'{cut}' {key} {_cut(plan, cut, key):g} is not its setting's {expected:g}"
            )
    return rpm, feed


def _shop_tool(plan: dict[str, Any], shop: dict[str, Any], tool: str) -> dict[str, Any]:
    ref = next(t["ref"] for t in plan["tools"] if t["id"] == tool)
    return shop["tools"][ref]


def _levels(top: float, bottom: float, max_step: float) -> list[float]:
    """Equal step-down levels no deeper than ``max_step`` from ``top`` to
    ``bottom``, ``bottom`` last."""
    n = math.ceil((top - bottom) / max_step - 1e-9)
    return [top - (top - bottom) * (k + 1) / n for k in range(n - 1)] + [bottom]


def _r(value: float) -> float:
    """A coordinate as the post prints it (3 places)."""
    return round(value + 0.0, 3)


def _box(
    name: str, x: tuple[float, float], y: tuple[float, float], z_top: float
) -> dict[str, Any]:
    return {"name": name, "x": [x[0], x[1]], "y": [y[0], y[1]], "z_top": z_top}


def _agree(plan: dict[str, Any], key: str, value: float) -> None:
    """A plan parameter the recipe recomputes from the export and the shop."""
    stated = plan["parameters"][key]
    if not math.isclose(stated, value, abs_tol=PLAN_TOL_MM):
        raise ValueError(f"process.{key} {stated:g}, the recipe computes {value:.4f}")


def _mid(band: list[float]) -> float:
    return (band[0] + band[1]) / 2


def _spot_depth(dia: float) -> float:
    """Depth below the surface at which the #2 centre drill's 60° countersink
    reaches ``dia``; refused unless it is between the pilot and the body."""
    pilot, body = CENTRE_DRILL["pilot_mm"], CENTRE_DRILL["body_mm"]
    if not pilot < dia <= body:
        raise ValueError(
            f"spot Ø{dia:.3f} is not between the pilot Ø{pilot:.3f} and the body Ø{body:.3f}"
        )
    half = math.radians(CENTRE_DRILL["point_deg"] / 2)
    return CENTRE_DRILL["pilot_length_mm"] + (dia - pilot) / 2 / math.tan(half)


def _point(dia: float) -> float:
    """A twist drill's point length."""
    return dia / 2 / math.tan(math.radians(DRILL_POINT_DEG / 2))


def _frame(
    origin: list[float], y_axis: list[float], z_axis: list[float]
) -> dict[str, Any]:
    """A right-handed setup frame from its Y and Z model axes: X = Y × Z."""
    y, z = y_axis, z_axis
    x = [
        y[1] * z[2] - y[2] * z[1],
        y[2] * z[0] - y[0] * z[2],
        y[0] * z[1] - y[1] * z[0],
    ]
    return {"origin": origin, "axes": [x, y, z]}


def _to(frame: dict[str, Any], p: list[float]) -> list[float]:
    """Model point ``p`` in the setup frame."""
    d = [p[i] - frame["origin"][i] for i in range(3)]
    return [sum(axis[i] * d[i] for i in range(3)) for axis in frame["axes"]]


def _spot(xy: tuple[float, float], top: float, z: float, clear: float) -> list[str]:
    clear, r_plane = _r(clear), _r(top + SAFE_MM)
    return [
        f"G0 Z{clear:.3f}",
        f"G0 X{xy[0]:.3f} Y{xy[1]:.3f}",
        f"G0 Z{r_plane:.3f}",
        f"G1 Z{_r(z):.3f} F{{feed}}",
        f"G0 Z{r_plane:.3f}",
        f"G0 Z{clear:.3f}",
    ]


def _pecked(
    xy: tuple[float, float], top: float, tip: float, peck: float, clear: float
) -> list[str]:
    """Drill from ``top`` to ``tip`` in pecks of ``peck``, each with a full
    retract to the R plane and a rapid back to just above the last peck.
    Moves to and from the hole run at ``clear``."""
    clear, r_plane = _r(clear), _r(top + SAFE_MM)
    depths = []
    depth = top
    while depth - peck > tip + 1e-6:
        depth -= peck
        depths.append(_r(depth))
    depths.append(_r(tip))
    lines = [f"G0 Z{clear:.3f}", f"G0 X{xy[0]:.3f} Y{xy[1]:.3f}", f"G0 Z{r_plane:.3f}"]
    previous = None
    for z in depths:
        if previous is not None:
            lines += [f"G0 Z{r_plane:.3f}", f"G0 Z{_r(previous + PECK_REENTRY_MM):.3f}"]
        lines.append(f"G1 Z{z:.3f} F{{feed}}")
        previous = z
    return lines + [f"G0 Z{r_plane:.3f}", f"G0 Z{clear:.3f}"]


def _stations(y: tuple[float, float], radius: float, max_step: float) -> list[float]:
    """Zigzag pass stations across the face ``y`` (low, high), from its high
    side: each pass takes the same width, at most ``max_step``, and together
    the cutter reaches ``FACE_OVERHANG_MM`` past both edges."""
    span = y[1] - y[0] + FACE_OVERHANG_MM
    n = math.ceil(span / max_step - 1e-9)
    step = span / n
    if 2 * radius - step < FACE_OVERHANG_MM:
        raise ValueError(
            f"a {step:.3f} stepover leaves the first pass short of the edge"
        )
    first = y[1] + radius - step
    return [_r(first - k * step) for k in range(n)]


def _face(
    levels: list[float], top: float, x: tuple[float, float], ys: list[float]
) -> list[str]:
    """Zigzag faces at ``levels``: at each, one X pass per Y in ``ys``
    between the cutter-centre ends ``x``, alternating direction, starting at
    the low X end; every plunge, level change and stepover beside the part."""
    clear = _r(top + CLEAR_MM)
    x0, x1 = _r(x[0]), _r(x[1])
    lines = [
        f"G0 Z{clear:.3f}",
        f"G0 X{x0:.3f} Y{ys[0]:.3f}",
        f"G0 Z{_r(top + SAFE_MM):.3f}",
    ]
    for z in levels:
        lines.append(f"G1 Z{_r(z):.3f} F{{feed}}")
        for k, y in enumerate(ys):
            if k:
                lines.append(f"G1 Y{y:.3f} F{{feed}}")
            lines.append(f"G1 X{x1 if k % 2 == 0 else x0:.3f} F{{feed}}")
        if len(ys) % 2:
            # Back to the low X side, beside the part, for the next level.
            lines.append(f"G1 X{x0:.3f} F{{feed}}")
        if z != levels[-1]:
            lines.append(f"G1 Y{ys[0]:.3f} F{{feed}}")
    return lines + [f"G0 Z{clear:.3f}"]


def _end_stations(raw: float, final: float, max_step: float) -> list[float]:
    """End-face positions from just inside ``raw`` to ``final`` in equal
    radial steps no deeper than ``max_step``, ``final`` last."""
    n = math.ceil(abs(raw - final) / max_step - 1e-9)
    return [raw + (final - raw) * (k + 1) / n for k in range(n)]


def _end(xs: list[float], y: tuple[float, float], z: float, top: float) -> list[str]:
    """One-way side passes at the cutter-centre Xs ``xs``, each from
    ``y[0]`` to ``y[1]`` at depth ``z``: plunged beside the part at feed,
    lifted and rapided back to the start beside it between passes. The
    tool starts at the clearance height above ``top``."""
    clear, safe = _r(top + CLEAR_MM), _r(top + SAFE_MM)
    lines = []
    for x in xs:
        lines += [
            f"G0 X{_r(x):.3f} Y{_r(y[0]):.3f}",
            f"G0 Z{safe:.3f}",
            f"G1 Z{_r(z):.3f} F{{feed}}",
            f"G1 Y{_r(y[1]):.3f} F{{feed}}",
            f"G0 Z{clear:.3f}",
        ]
    return lines


def _geometry(features: dict[str, Any]) -> dict[str, Any]:
    """The rail's bands and its nine taps from the export, each checked
    against the frame the recipe assumes: the left end X0 with the rail
    along +X, the bottom face (U) Y0 with the top at +Y, the front face Z0
    with the rear at -Z; every tap through, the front taps entering the
    front face along -Z, the lock taps the rear face along +Z (the recipe
    drills and taps them all from the rear face: a through hole's thread is
    the same from either side)."""
    f = features["features"]
    if f["left_end"]["plane"]["value"] != 0.0 or f["left_end"]["plane"]["axis"] != "x":
        raise ValueError("left_end: expected at model X0")
    right = f["right_end"]
    if not math.isclose(right["plane"]["value"], right["length_nominal"], abs_tol=1e-3):
        raise ValueError("right_end: its plane is not the length from the left end")
    bottom = f["bottom_face"]
    if bottom["plane"]["value"] != 0.0 or bottom["plane"]["axis"] != "y":
        raise ValueError("bottom_face: expected at model Y0")
    top = f["top_face"]
    if not math.isclose(top["plane"]["value"], top["height_nominal"], abs_tol=1e-3):
        raise ValueError("top_face: its plane is not the height from the bottom face")
    if (
        f["front_face"]["plane"]["value"] != 0.0
        or f["front_face"]["plane"]["axis"] != "z"
    ):
        raise ValueError("front_face: expected at model Z0")
    rear = f["rear_face"]
    if not math.isclose(-rear["plane"]["value"], rear["depth_nominal"], abs_tol=1e-3):
        raise ValueError("rear_face: its plane is not the depth behind the front face")
    entries = {
        (0.0, 0.0, -1.0): f["front_face"]["plane"]["value"],
        (0.0, 0.0, 1.0): rear["plane"]["value"],
    }
    taps = []
    handled = {
        "left_end",
        "right_end",
        "bottom_face",
        "top_face",
        "front_face",
        "rear_face",
    }
    for name, feature in f.items():
        if name in handled:
            continue
        if feature.get("made_at") == "assembly":
            continue
        if not name.startswith("tap_a") or feature["kind"] != "threaded_hole":
            raise ValueError(f"{name}: a feature this recipe does not make")
        entry = entries.get(tuple(feature["axis"]))
        if entry is None or not math.isclose(feature["at"][2], entry, abs_tol=1e-3):
            raise ValueError(f"{name}: expected through the rail along Z from a face")
        if feature.get("thru") is not True:
            raise ValueError(f"{name}: expected a through tap")
        x, y = feature["at"][0], feature["at"][1]
        if not feature["station"][0] <= x <= feature["station"][1]:
            raise ValueError(f"{name}: X {x} is outside its station band")
        if not feature["height"][0] <= y <= feature["height"][1]:
            raise ValueError(f"{name}: Y {y} is outside its height band")
        taps.append(
            {
                "name": name,
                "tag": feature["tag"],
                "x": x,
                "y": y,
                "height": feature["height"],
                "dia": feature["dia"],
                "thread": feature["thread"],
            }
        )
    if len(taps) != TAP_COUNT:
        raise ValueError(
            f"{len(taps)} taps in the export, the programs post {TAP_COUNT}"
        )
    taps.sort(key=lambda tap: tap["x"])
    return {
        "length_band": right["length"],
        "length_nominal": right["length_nominal"],
        "height_band": top["height"],
        "height_nominal": top["height_nominal"],
        "depth_band": rear["depth"],
        "depth_nominal": rear["depth_nominal"],
        "taps": taps,
    }


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    g = _geometry(features)
    p = plan["parameters"]

    # Targets: the middle of each printed band (the length's 10.62 ±.010;
    # the height's .29 ±.01; the depth's .390-.400 LIMIT).
    length = _mid(g["length_band"])
    height = _mid(g["height_band"])
    depth = _mid(g["depth_band"])
    _agree(plan, "length_target_mm", length)
    _agree(plan, "height_target_mm", height)
    _agree(plan, "depth_target_mm", depth)

    # The blank: the flat bar's section (Y the 3/8 in height, Z the 1/2 in
    # depth), sawn to length; skims off the underside, the front face and
    # the left end; the rest of each size off the opposite face or end.
    sec_y, sec_z = p["blank_height_in"] * IN, p["blank_depth_in"] * IN
    _agree(plan, "blank_height_mm", sec_y)
    _agree(plan, "blank_depth_mm", sec_z)
    y_min, y_max = p["blank_height_min_mm"], p["blank_height_max_mm"]
    z_min, z_max = p["blank_depth_min_mm"], p["blank_depth_max_mm"]
    blank_min, blank_max = p["blank_length_min_in"] * IN, p["blank_length_max_in"] * IN
    _agree(plan, "blank_length_min_mm", blank_min)
    _agree(plan, "blank_length_max_mm", blank_max)
    under_skim, front_skim, left_skim = (
        p["underside_skim_mm"],
        p["front_skim_mm"],
        p["left_end_skim_mm"],
    )
    # U to the raw top (the bar less the underside skim), faced in PG02 to
    # the rough height across the jaws in PG03-PG05 (machined faces at both
    # jaws, and the one stack in PG05 at a known distance from U), then to
    # the height in PG15; F to the raw rear: the bar less its skim.
    raw_min, raw_max = y_min - under_skim, y_max - under_skim
    rough = p["rough_height_mm"]
    depth_top = z_max - front_skim
    _agree(plan, "height_raw_min_mm", raw_min)
    _agree(plan, "height_raw_max_mm", raw_max)
    _agree(plan, "depth_raw_max_mm", depth_top)
    if raw_min - rough < p["top_skim_min_mm"]:
        raise ValueError(
            f"the thinnest bar leaves {raw_min - rough:.3f} over the rough height, "
            f"under process.top_skim_min_mm {p['top_skim_min_mm']}"
        )
    if rough <= height or z_min - front_skim <= depth:
        raise ValueError(
            "the thinnest bar leaves nothing to face to the height or the depth"
        )
    _agree(plan, "end_cleanup_min_mm", blank_min - left_skim - length)
    if p["end_cleanup_min_mm"] < 0.5:
        raise ValueError(
            f"the shortest blank less the left-end skim, {blank_min - left_skim:.3f}, "
            f"leaves under 0.5 mm on the right end over the length {length:.3f}"
        )
    _agree(plan, "right_end_station_mm", left_skim + length)
    # The length is read on the work X DRO: the right end touched with the
    # .200 edge finder from the right reads the length plus its radius.
    finder_r = 0.1 * IN
    _agree(plan, "length_dro_min_mm", g["length_band"][0] + finder_r)
    _agree(plan, "length_dro_max_mm", g["length_band"][1] + finder_r)

    em = _shop_tool(plan, shop, "em-half")["diameter_mm"]
    d43 = _shop_tool(plan, shop, "drill-43")["diameter_mm"]
    r = em / 2
    for tap in g["taps"]:
        low, high = tap["dia"]
        if not low - SIZE_TOL_MM <= d43 <= high:
            raise ValueError(f"#43 Ø{d43} is outside {tap['name']}'s band {tap['dia']}")
    step_max = p["face_stepover_max_mm"]
    # The five faces run at one setting and the two ends at another: the
    # ends' depth lies past the faces' measured envelope (plan.toml).
    face_rpm, face_feed = _setting(plan, shop, "underside")
    end_rpm, end_feed = _setting(plan, shop, "left end")
    for names, first, speeds in (
        (
            ("underside", "top skim", "front face", "depth", "height"),
            "underside",
            (face_rpm, face_feed),
        ),
        (("left end", "right end"), "left end", (end_rpm, end_feed)),
    ):
        for name in names:
            if not math.isclose(_cut(plan, name, "cutter_dia_mm"), em, abs_tol=1e-6):
                raise ValueError(
                    f"'{name}' cutter Ø{_cut(plan, name, 'cutter_dia_mm')}, the end mill is Ø{em}"
                )
            if _setting(plan, shop, name) != speeds:
                raise ValueError(f"'{name}' runs at another setting than '{first}'")
    # Each face's own level ceiling: light enough that the long, thin rail's
    # overhang past the jaws bends under its cut force within the finish
    # limit (the cut's axial_doc_mm, the force's depth, is that ceiling).
    level_keys = {
        "underside": "underside_step_max_mm",
        "top skim": "top_step_max_mm",
        "front face": "front_step_max_mm",
        "depth": "depth_step_max_mm",
        "height": "height_step_max_mm",
    }
    for name, key in level_keys.items():
        if not math.isclose(_cut(plan, name, "radial_woc_mm"), step_max, abs_tol=1e-6):
            raise ValueError(
                f"'{name}' radial_woc_mm is not process.face_stepover_max_mm"
            )
        if not math.isclose(_cut(plan, name, "axial_doc_mm"), p[key], abs_tol=1e-6):
            raise ValueError(f"'{name}' axial_doc_mm is not process.{key}")
    under_levels = _levels(under_skim, 0.0, p["underside_step_max_mm"])
    top_levels = _levels(raw_max, rough, p["top_step_max_mm"])
    front_levels = _levels(front_skim, 0.0, p["front_step_max_mm"])
    depth_levels = _levels(depth_top, depth, p["depth_step_max_mm"])
    height_levels = _levels(rough, height, p["height_step_max_mm"])

    # Ends: the cutter's side, one level from the rear face to end_past_mm
    # under the front face (into the air past the stack's ends), in equal
    # radial steps no deeper than end_step_max_mm.
    end_step = p["end_step_max_mm"]
    end_z = -p["end_past_mm"]
    _agree(plan, "end_axial_doc_mm", depth - end_z)
    for name in ("left end", "right end"):
        if not math.isclose(_cut(plan, name, "radial_woc_mm"), end_step, abs_tol=1e-6):
            raise ValueError(f"'{name}' radial_woc_mm is not process.end_step_max_mm")
        if not math.isclose(
            _cut(plan, name, "axial_doc_mm"), depth - end_z, abs_tol=1e-6
        ):
            raise ValueError(f"'{name}' axial_doc_mm is not process.end_axial_doc_mm")
    left_faces = _end_stations(-left_skim, 0.0, end_step)
    right_raw = blank_max - left_skim
    _agree(plan, "right_end_raw_mm", right_raw)
    right_faces = _end_stations(right_raw, length, end_step)

    # Holes: spot under the drill (no chamfer at the mouth; the tap's start
    # is the drill's), then the #43 pecked with full retracts until its full
    # diameter is past the front face, into the air beside the stack.
    spot_rpm, spot_feed = _setting(plan, shop, "tap spot")
    drill_rpm, drill_feed = _setting(plan, shop, "tap drill")
    if not math.isclose(
        _cut(plan, "tap spot", "cutter_dia_mm"), p["spot_dia_mm"], abs_tol=1e-6
    ):
        raise ValueError("'tap spot' cutter_dia_mm is not process.spot_dia_mm")
    if p["spot_dia_mm"] >= d43:
        raise ValueError(
            "the spot is not under the #43 drill: it would chamfer the hole"
        )
    spot_depth = _spot_depth(p["spot_dia_mm"])
    peck = p["peck_mm"]
    op = _op_with_cut(plan, "tap drill")[0]
    if op["peck"] != {"step_mm": peck, "retract": "full"}:
        raise ValueError("'tap drill' peck is not process.peck_mm with full retract")
    if op["hole_depth_mm"] != "{{process.depth_target_mm}}":
        raise ValueError("'tap drill' hole_depth_mm is not {{process.depth_target_mm}}")
    tip = -(p["drill_past_mm"] + _point(d43))
    _agree(plan, "drill_tip_height_mm", tip)

    # Vise: lying on the stacked risers, centred on the jaws. In PG15 the
    # finished .29 rail stands least above the jaw tops: its last level must
    # clear them by jaw_clear_min_mm, the band's floor by more than nothing.
    grip = p["vise_jaw_height_mm"] - p["riser_height_mm"]
    _agree(plan, "lying_grip_mm", grip)
    _agree(plan, "height_jaw_clear_mm", height - grip)
    if height - grip < p["jaw_clear_min_mm"] or g["height_band"][0] <= grip:
        raise ValueError(
            f"PG15's last level stands {height - grip:.3f} over the jaw tops, "
            f"under process.jaw_clear_min_mm {p['jaw_clear_min_mm']}"
        )
    jaw_w = p["vise_jaw_width_mm"]
    _agree(plan, "vise_overhang_mm", (blank_max - jaw_w) / 2)
    _agree(plan, "vise_clamp_end_mm", (blank_max + jaw_w) / 2)
    t = p["parallel_thickness_mm"]
    # The tap stack's ceiling (the tap guide's reach out of its collet plus
    # the tap's in its wrench): spindle-to-table maximum less the tool-change
    # clearance, the vise bed, the stack, the deepest rail the band allows
    # and the collet's gauge, rounded down to .01 in.
    machine = shop["machines"]["pm-30mv"]
    stack = (
        machine["spindle_to_table_mm"][1]
        - shop["limits"]["tool_change_clearance_mm"]
        - p["vise_bed_height_mm"]
        - p["riser_height_mm"]
        - g["depth_band"][1]
        - p["r8_collet_gauge_mm"]
    )
    stack_max = math.floor(stack / 0.254 + 1e-9) * 0.254
    _agree(plan, "tap_stack_max_mm", stack_max)
    # The tap's own reach in its wrench: the stack less the guide's length,
    # rounded down to .01 in.
    _agree(
        plan,
        "tap_wrench_reach_max_mm",
        math.floor((stack_max - TAP_GUIDE_OAL_MM) / 0.254 + 1e-9) * 0.254,
    )

    names = {tool["id"]: tool["name"] for tool in plan["tools"]}
    numbers = {
        tool["id"]: n
        for n, tool in enumerate((x for x in plan["tools"] if x["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    # Frames (model point p -> axes · (p - origin)); X0 the finished left
    # end in every one. Raw faces in the model: the underside's skim below
    # Y0, the front face's skim beyond Z0, each other face the rest of the
    # section beyond them.
    raw_front = front_skim
    raw_rear = front_skim - sec_z
    frames = {
        # Underside up, the raw front face against the fixed jaw.
        "underside": _frame([0.0, 0.0, raw_front], [0, 0, 1], [0, -1, 0]),
        # Turned over: underside down, the raw rear face against the fixed jaw.
        "top": _frame([0.0, 0.0, raw_rear], [0, 0, -1], [0, 1, 0]),
        # Front face up, the rough top against the fixed jaw.
        "front": _frame([0.0, rough, 0.0], [0, 1, 0], [0, 0, 1]),
        # Turned over: front face down, the underside against the fixed jaw.
        "depth": _frame([0.0, 0.0, 0.0], [0, -1, 0], [0, 0, -1]),
        # Underside down, the rear face against the fixed jaw.
        "height": _frame([0.0, 0.0, -depth], [0, 0, -1], [0, 1, 0]),
    }
    run_x = (-left_skim, blank_max - left_skim)
    stocks = {
        "underside": (run_x, (-sec_z, 0.0), (under_skim - sec_y, under_skim)),
        "top": (run_x, (-sec_z, 0.0), (0.0, raw_max)),
        "front": (run_x, (-rough, 0.0), (front_skim - sec_z, front_skim)),
        "depth": (run_x, (-rough, 0.0), (0.0, depth_top)),
        # The rail at the depth, its rear face at the model's (the band's top).
        "ends": (run_x, (-rough, 0.0), (0.0, max(depth, g["depth_nominal"]))),
        "height": (run_x, (-depth, 0.0), (0.0, rough)),
    }
    for key, frame in frames.items():
        corner = _to(frame, [0.0, 0.0, 0.0])
        if not math.isclose(corner[0], 0.0, abs_tol=1e-6):
            raise ValueError(f"{key}: the left end is not at X0")
    holes = []
    for tap in g["taps"]:
        x, y, _z = _to(frames["depth"], [tap["x"], tap["y"], 0.0])
        holes.append([_r(x), _r(y)])
    if not all(0 < x < length and -rough < y < 0 for x, y in holes):
        raise ValueError(f"holes {holes} are not on the rail in the PG05 frame")
    # The one stack under the rough top's edge, against the moving jaw:
    # every hole and the tap through it (its basic major diameter, #N: .060
    # + .013 N in), at the top of its height band, exits clear of it. At the
    # finished height it would not: no stack under either edge clears the
    # exits, so the holes come before PG15.
    major = max(
        (0.060 + 0.013 * int(re.match(r"#(\d+)-", tap["thread"]).group(1))) * IN
        for tap in g["taps"]
    )
    stack_edge = -rough + t
    reach = min(-tap["height"][1] - major / 2 for tap in g["taps"])
    if not reach > stack_edge:
        raise ValueError(
            f"a tap reaches the stack under the rough top ({reach:.3f} <= {stack_edge:.3f})"
        )
    _agree(plan, "stack_exit_clear_mm", reach - stack_edge)
    finished_clear = min(
        min(tap["height"][0], g["height_band"][0] - tap["height"][1]) - major / 2
        for tap in g["taps"]
    )
    if finished_clear >= t:
        raise ValueError(
            "a stack under the finished rail's edge clears the exits: drill after PG15"
        )

    em_tool = {
        "tool": "em-half",
        "dia": em,
        "shape": "endmill",
        "flutes": 3,
        "rpm": face_rpm,
        "feed": face_feed,
        "plunge": face_feed,
    }
    spot_tool = {
        "tool": "spot",
        "dia": CENTRE_DRILL["body_mm"],
        "shape": "drill",
        "tip_angle": CENTRE_DRILL["point_deg"],
        "rpm": spot_rpm,
        "feed": spot_feed,
        "plunge": spot_feed,
    }
    drill_tool = {
        "tool": "drill-43",
        "dia": d43,
        "shape": "drill",
        "tip_angle": DRILL_POINT_DEG,
        "rpm": drill_rpm,
        "feed": drill_feed,
        "plunge": drill_feed,
    }

    # Passes along the rail from beside its left raw end to beside the
    # longest blank's right raw end; across the gripped span from the fixed
    # jaw (Y0) down.
    face_x = (run_x[0] - r - APPROACH_MM, run_x[1] + r + APPROACH_MM)
    faces = {
        "underside": (
            under_levels,
            under_skim,
            _stations((-sec_z, 0.0), r, step_max),
            (-sec_z, 0.0),
            "underside",
        ),
        "top_skim": (
            top_levels,
            raw_max,
            _stations((-sec_z, 0.0), r, step_max),
            (-sec_z, 0.0),
            "top",
        ),
        "front_face": (
            front_levels,
            front_skim,
            _stations((-rough, 0.0), r, step_max),
            (-rough, 0.0),
            "front",
        ),
        "rear_face": (
            depth_levels,
            depth_top,
            _stations((-rough, 0.0), r, step_max),
            (-rough, 0.0),
            "depth",
        ),
        "top_face": (
            height_levels,
            rough,
            _stations((-depth, 0.0), r, step_max),
            (-depth, 0.0),
            "height",
        ),
    }
    # The faces' declared width is the widest pass any of them takes: every
    # pass of a face is one equal width (the first engages its width, the
    # cutter overhanging the edge; the last ends FACE_OVERHANG_MM past the
    # other edge).
    widest = max(
        (y[1] - y[0] + FACE_OVERHANG_MM) / len(ys)
        for _lv, _top, ys, y, _frame in faces.values()
    )
    if not math.isclose(widest, step_max, abs_tol=PLAN_TOL_MM):
        raise ValueError(
            f"the widest face pass is {widest:.4f}, not process.face_stepover_max_mm"
        )
    jobs = []

    def face_job(key: str) -> dict[str, Any]:
        levels, top, ys, _y, frame = faces[key]
        return {
            **em_tool,
            "frame": frame,
            "label": key.replace("_", " "),
            "stock": stocks[frame],
            "ops": [
                [
                    key,
                    f"face the {key.replace('_', ' ')}",
                    _face(levels, top, face_x, ys),
                ]
            ],
        }

    jobs += [
        face_job("underside"),
        face_job("top_skim"),
        face_job("front_face"),
        face_job("rear_face"),
    ]
    # Ends: the left one passes -Y and the right one +Y, the rail on the
    # cutter's left: conventional with the spindle's M3 (the cutter outside
    # each end).
    beside = (-rough - r - APPROACH_MM, r + APPROACH_MM)
    left_xs = [x - r for x in left_faces]
    right_xs = [x + r for x in right_faces]
    jobs.append(
        {
            **em_tool,
            "rpm": end_rpm,
            "feed": end_feed,
            "plunge": end_feed,
            "frame": "depth",
            "label": "ends",
            "stock": stocks["ends"],
            "ops": [
                [
                    "ends",
                    "mill both ends to the length",
                    [f"G0 Z{_r(depth + CLEAR_MM):.3f}"]
                    + _end(left_xs, beside[::-1], end_z, depth)
                    + _end(right_xs, beside, end_z, depth),
                ]
            ],
        }
    )
    clear = depth + CLEAR_MM
    jobs.append(
        {
            **spot_tool,
            "frame": "depth",
            "label": "tap spot",
            "stock": stocks["ends"],
            "ops": [
                [
                    "tap_spot",
                    "spot the nine tap holes",
                    [
                        line
                        for xy in holes
                        for line in _spot(xy, depth, depth - spot_depth, clear)
                    ],
                ]
            ],
        }
    )
    jobs.append(
        {
            **drill_tool,
            "frame": "depth",
            "label": "tap drill",
            "stock": stocks["ends"],
            "ops": [
                [
                    "tap_drill",
                    "drill the nine tap holes #43",
                    [
                        line
                        for xy in holes
                        for line in _pecked(xy, depth, tip, peck, clear)
                    ],
                ]
            ],
        }
    )
    jobs.append(face_job("top_face"))

    # One file per hole to tap: the tap guide loaded by the file's own M6,
    # Z to the machine's top before any XY, over the hole, M30: the
    # controller ends Idle for the operator's jog.
    manual = {}
    for k, (tap, xy) in enumerate(zip(g["taps"], holes), 1):
        what = f"HOLE {tap['tag']}"
        manual[f"tap_{k}"] = {
            "tool": numbers["tap-guide"],
            "label": names["tap-guide"],
            "setting": f"SPINDLE STAYS OFF. NEXT: 4-40 TAP IN {what}",
            "gcode": [
                f"G53 G0 Z{MACHINE_Z_TOP_MM:.3f}",
                f"G0 X{xy[0]:.3f} Y{xy[1]:.3f}",
                f"(4-40 TAP IN {what}. JOG Z DOWN TO PUSH THE GUIDE POINT HOME IN THE WRENCH."
                " TAP BY HAND THROUGH TO THE NOTED DRO Z, PUSHING THE POINT HOME EACH 1/2 IN,"
                " READ WITH THE POINT PUSHED HOME. JOG Z UP CLEAR)",
                "M30",
            ],
            "at": xy,
        }

    # Keep-outs: the jaws beside the gripped span, from the stacks' top to
    # the jaw tops, centred on the finished rail. Where Z0 is a skimmed face
    # (PG01, PG03) the stacks' top is the thinnest bar's seat below it. In
    # PG05 the one stack lies under the rough top's edge.
    mid = length / 2
    span = (mid - jaw_w / 2, mid + jaw_w / 2)

    def jaws(z_top: float, across: float) -> list[dict[str, Any]]:
        return [
            _box("moving jaw", span, (-across - JAW_DEPTH_MM, -across), z_top),
            _box("fixed jaw", span, (0.0, JAW_DEPTH_MM), z_top),
        ]

    keep = {
        "underside": jaws(grip - (y_min - under_skim), sec_z),
        "top_skim": jaws(grip, sec_z),
        "front_face": jaws(grip - (z_min - front_skim), rough),
        "rear_face": jaws(grip, rough),
        "top_face": jaws(grip, depth),
    }
    stack = _box(
        "stack under the rough top",
        (mid - PARALLEL_LENGTH_MM / 2, mid + PARALLEL_LENGTH_MM / 2),
        (-rough, stack_edge),
        0.0,
    )
    pg05_keep = jaws(grip, rough) + [stack]

    tn = numbers
    expect: list[list[Any]] = []

    def face_checks(key: str) -> list[list[Any]]:
        levels, top, _ys, y, _frame_key = faces[key]
        return [
            ["depth", {"z_min": _r(levels[-1])}],
            ["rapids_clear", {"z_top": top}],
            ["air_feed", {"z_top": top}],
            *[
                [
                    "face_passes",
                    {
                        "z": _r(z),
                        "y": list(y),
                        "max_engagement": step_max,
                        "radius": r,
                        "span": blank_min,
                        "overhang": FACE_OVERHANG_MM,
                    },
                ]
                for z in levels
            ],
            ["keep_out", {"radius": r, "boxes": keep[key]}],
        ]

    def hole_checks(bottom: float, radius: float) -> list[list[Any]]:
        return [
            ["holes", {"centres": holes, "z_bottom": _r(bottom)}],
            ["rapids_clear", {"z_top": depth, "open_holes": holes}],
            ["vertical_below_top", {"z_top": depth}],
            ["air_feed", {"z_top": depth}],
            ["keep_out", {"radius": radius, "boxes": pg05_keep}],
        ]

    single = {
        "PG01_underside": "underside",
        "PG02_top": "top_skim",
        "PG03_front": "front_face",
        "PG04_depth": "rear_face",
        "PG15_height": "top_face",
    }
    for name, key in single.items():
        top = faces[key][1]
        expect += [
            [
                name,
                "tool_changes",
                {"z_top": top, "tools": [tn["em-half"]], "loads_first": True},
            ],
            [name, "spindle", {"rpm": [[face_rpm]]}],
            [name, "pauses", {"z_top": top, "count": 0}],
            *[[name, check, kwargs] for check, kwargs in face_checks(key)],
        ]
    name = "PG05_ends_drill"
    expect += [
        [
            name,
            "tool_changes",
            {
                "z_top": depth,
                "tools": [tn["em-half"], tn["spot"], tn["drill-43"]],
                "loads_first": True,
            },
        ],
        [name, "spindle", {"rpm": [[end_rpm], [spot_rpm], [drill_rpm]]}],
        [name, "pauses", {"z_top": depth, "count": 0}],
        [name, "depth", {"z_min": _r(tip)}],
    ]
    end_checks = [
        ["depth", {"z_min": _r(end_z)}],
        ["rapids_clear", {"z_top": depth}],
        ["air_feed", {"z_top": depth}],
        [
            "side_passes",
            {
                "axis": "X",
                "final": _r(-r),
                "raw": _r(-left_skim - r),
                "max_step": end_step,
                "direction": -1.0,
                "cut": "conventional",
                "span": rough,
                "below_z": depth,
            },
        ],
        [
            "side_passes",
            {
                "axis": "X",
                "final": _r(length + r),
                "raw": _r(right_raw + r),
                "max_step": end_step,
                "direction": 1.0,
                "cut": "conventional",
                "span": rough,
                "below_z": depth,
            },
        ],
        ["keep_out", {"radius": r, "boxes": pg05_keep}],
    ]
    for k, checks in enumerate(
        (
            end_checks,
            hole_checks(depth - spot_depth, CENTRE_DRILL["body_mm"] / 2),
            hole_checks(tip, d43 / 2),
        )
    ):
        expect += [[f"{name}@{k}", check, kwargs] for check, kwargs in checks]
    for (program, (key,)), _n in zip(TAP_PROGRAMS, range(TAP_COUNT)):
        expect += [
            [
                program,
                "tap_stop",
                {
                    "tool": tn["tap-guide"],
                    "at": manual[key]["at"],
                    "machine_top": MACHINE_Z_TOP_MM,
                },
            ],
            [program, "air_feed", {"z_top": depth}],
        ]

    return {
        "stem": STEM,
        "step": step_path,
        "comment": COMMENT,
        "frames": {**frames, "ends": frames["depth"]},
        "names": names,
        "numbers": numbers,
        "jobs": jobs,
        "manual": manual,
        "expect": expect,
    }


def expectations(ctx: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    """(program, ``_gcode.check_<name>``, kwargs) for every posted file."""
    return [(program, check, kwargs) for program, check, kwargs in ctx["expect"]]


def build(ctx: dict[str, Any], rt: Any) -> dict[str, Any]:
    """Runs inside freecadcmd with ``rt`` = ``_freecad_cam_runtime``. One Job per
    section; returns {"ops": {operation key: operation or manual section}}."""
    doc = rt.document()
    models = {
        key: rt.import_step(
            doc, f"Platen guide {key}", ctx["step"], frame["origin"], frame["axes"]
        )
        for key, frame in ctx["frames"].items()
        if key != "ends"
    }
    models["ends"] = models["depth"]
    ops: dict[str, Any] = {}
    for section in ctx["jobs"]:
        target = rt.job(
            doc, section["label"], [models[section["frame"]]], section["stock"]
        )
        tc = rt.tool_controller(
            doc,
            ctx["names"][section["tool"]],
            ctx["numbers"][section["tool"]],
            section["shape"],
            section["dia"],
            section["rpm"],
            section["feed"],
            section["plunge"],
            flutes=section.get("flutes"),
            tip_angle=section.get("tip_angle"),
        )
        for key, label, lines in section["ops"]:
            ops[key] = rt.custom(target, tc, label, lines)
    ops.update(ctx["manual"])
    rt.generate(doc)
    return {"ops": ops}
