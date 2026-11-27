"""FreeCAD CAM recipe for MHA-PD-26, the feed rack: its ends and four #0-80 taps.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The strip's length
band, its 3/16 section, the four taps (thread, tap drill, drill and thread
depths, stations, inset from the front face) come from the feature export;
the blank, the skim, the end passes, the holds, the spot, the pecks and the
tap point's depth from ``plan.toml`` ``[parameters]`` and ``milling_cuts``;
cutter diameters, speeds and feeds from the shop (``shop/``). Every path is
written here (``rt.custom``). Typed here, because neither record carries
them: the #1 centre drill's catalogue geometry (it sets the spot depth), the
twist drill's 118° point, the strip's receiving room (the spec's, see
``SECTION_ROOM_MM``), the machine's Z top for the tap file's retract, the
approach, safe and clearance heights and the vise jaws' depth (keep-out
shapes only).

Route (``plan.toml``): a piece of the bought SDP/SI A 1B12-Y324 brass rack,
sawn by hand. Setup 2, teeth up on one parallel stack against the fixed
jaw: FR01 mills the left end with the cutter's side, that end .30 in past
the jaws; re-gripped with the right end .30 in past them, X0 is touched
again on the milled left end and FR02 mills the right end to the length.
(Centred, each end 2.2 in past the jaws, the side pass bends the 3/16
strip about 0.47 mm: prechips' milling_deflection refuses it.) Then the
strip is re-gripped twice more and each tap's tooth is measured from an
end with a rod in the space beside it and the edge finder (no program).
Setup 3, teeth down: each hole is zeroed in X on its own tooth (``G10 L2
P1 X`` from the end the tooth was measured from, as the plan's table
writes it), so FR03 (spot) and FR04 (drill) are one-hole files at X0 Y0,
each run once per hole, all spots then all drills from the same zeros in
one clamping. FR05 loads the tap guide once, at hole 1; the guide reaches
holes 2-4 by MDI with no second M6, so the taps' depth references hold.

Work frames (G54):
- FR01, FR02: X0 the finished left end (the sawn end less the skim), +X
  along the strip; Y0 the front face (against the fixed jaw), +Y toward
  that jaw; Z0 the tooth crests.
- FR03-FR05: X0 the hole's tooth centre, +X toward the right end; Y0 the
  tap's line, the inset from the front face (toward the operator), +Y toward
  the back face; Z0 the flat top.

The taps are tapped by hand under the Fisher spring tap guide in the 1/2 in
R8 collet (owner, Pedro, 2026-11-21): FluidNC refuses jogs in the Hold an M0
leaves, so the tap stop is a file of its own that ends M30 over its hole
(the pd_platen_bottom_guide precedent). It is run once: a second M6 would
probe the spring-loaded guide again and move the tool offset under the
plan's Zp and Zb.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "pd_feed_rack"
COMMENT = "MHA-PD-26 feed rack"
# Programs in order, each listing its operation keys (one section each).
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("FR01_left", ("left_end",)),
    ("FR02_right", ("right_end",)),
    ("FR03_spot", ("spot",)),
    ("FR04_drill", ("drill",)),
    ("FR05_tap", ("tap",)),
)
# Every program loads its own first tool (M6, the tool setter): FR03 and FR04
# run once per hole and each starts on whatever the mill last held.
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (the saw, the rod, the taps and the files are not).
CAM_TOOLS = ("em-quarter", "spot", "drill-3-64", "tap-guide")
IN = 25.4
# The Fisher tap guide's overall length, 3 1/8 in (its sellers' size,
# cad/config/shop-equipment/ tools.tap-guide-fisher).
TAP_GUIDE_OAL_MM = 3.125 * IN
# ANSI #1 combined drill and countersink, 60° included (the carbide set's
# trade size 1, "for 3/64 in drill bit"): the shop record names the set, not
# its geometry.
CENTRE_DRILL = {
    "pilot_mm": 3 / 64 * IN,
    "pilot_length_mm": 3 / 64 * IN,
    "body_mm": 1 / 8 * IN,
    "point_deg": 60.0,
}
# Jobber drills' point (the shop record gives the diameter only).
DRILL_POINT_DEG = 118.0
# The strip's receiving room either side of its 3/16 section, twice drawn
# square brass bar's .003 (pd_feed_rack_spec.PURCHASED_RACK_SECTION_ROOM_IN):
# SDP/SI publishes no section tolerance, and the drawing pays these limits.
SECTION_ROOM_MM = 2 * 0.003 * IN
# A tap file's first motion: G53 G0 to machine Z0, the homed top (owner,
# Pedro, 2026-11-21: machine Z = 0 is the top of travel after homing).
MACHINE_Z_TOP_MM = 0.0
# End passes start and finish with the cutter this far clear of the strip's
# faces, so every plunge is in the air beside it.
APPROACH_MM = 2.54
# Plunges and drill R planes start this far above the stock top.
SAFE_MM = 1.0
# Moves between cuts run this far above the jaw tops.
CLEAR_MM = 5.0
# Rapid re-entry into a pecked hole stops this far above the last peck.
PECK_REENTRY_MM = 0.5
# Keep-outs: each vise jaw's depth outward from the gripped face; the
# parallels' length (4 in, shop-equipment fixtures.parallels-lms-6745).
JAW_DEPTH_MM = IN
PARALLEL_LENGTH_MM = 4 * IN
# The .200 in edge finder's radius (tools.edge-finder): touch-offs and the
# length read on the DRO.
FINDER_R_MM = 0.1 * IN
# A plan number the recipe recomputes must agree to this (its rounding).
PLAN_TOL_MM = 0.01
# The 3/64 drill against the tap drill's printed band: the shop records the
# drill's nominal (1.190625), the band's floor is that size rounded to 1.191.
SIZE_TOL_MM = 0.001
TAPS = ("tap_1", "tap_2", "tap_3", "tap_4")


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
    names (chip load × flutes × rpm), or the rpm and feed the cut authors,
    agreeing with the rpm of the setting (whose feed is printed text)."""
    op, record_cut = _op_with_cut(plan, cut)
    record = shop["settings"][op["settings"]]
    rpm = float(record["rpm"])
    if "chip_load_mm_per_tooth" in record:
        feed = record["chip_load_mm_per_tooth"] * record["flutes"] * rpm
        for key, expected in (("rpm", rpm), ("feed_mm_min", feed)):
            if key in record_cut and not math.isclose(
                _cut(plan, cut, key), expected, abs_tol=1e-3
            ):
                raise ValueError(
                    f"'{cut}' {key} {_cut(plan, cut, key):g} is not its setting's {expected:g}"
                )
        return rpm, feed
    if _cut(plan, cut, "rpm") != rpm:
        raise ValueError(
            f"'{cut}': its setting's rpm is not the cut's {_cut(plan, cut, 'rpm'):g}"
        )
    return rpm, _cut(plan, cut, "feed_mm_min")


def _shop_tool(plan: dict[str, Any], shop: dict[str, Any], tool: str) -> dict[str, Any]:
    ref = next(t["ref"] for t in plan["tools"] if t["id"] == tool)
    return shop["tools"][ref]


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
    """Depth below the top at which the #1 centre drill's 60° countersink
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


def _end_stations(raw: float, final: float, max_step: float) -> list[float]:
    """End-face positions from just inside ``raw`` to ``final`` in equal
    radial steps no deeper than ``max_step``, ``final`` last."""
    n = math.ceil(abs(raw - final) / max_step - 1e-9)
    return [raw + (final - raw) * (k + 1) / n for k in range(n)]


def _end(xs: list[float], y: tuple[float, float], z: float, clear: float) -> list[str]:
    """One-way side passes at the cutter-centre Xs ``xs``, each from
    ``y[0]`` to ``y[1]`` at depth ``z``: plunged beside the strip at feed
    from ``SAFE_MM`` over the crests, lifted to ``clear`` and rapided back
    to the start beside it between passes."""
    safe = _r(SAFE_MM)
    lines = []
    for x in xs:
        lines += [
            f"G0 X{_r(x):.3f} Y{_r(y[0]):.3f}",
            f"G0 Z{safe:.3f}",
            f"G1 Z{_r(z):.3f} F{{feed}}",
            f"G1 Y{_r(y[1]):.3f} F{{feed}}",
            f"G0 Z{_r(clear):.3f}",
        ]
    return lines


def _spot(z: float, clear: float) -> list[str]:
    clear, r_plane = _r(clear), _r(SAFE_MM)
    return [
        f"G0 Z{clear:.3f}",
        "G0 X0.000 Y0.000",
        f"G0 Z{r_plane:.3f}",
        f"G1 Z{_r(z):.3f} F{{feed}}",
        f"G0 Z{r_plane:.3f}",
        f"G0 Z{clear:.3f}",
    ]


def _pecked(tip: float, peck: float, clear: float) -> list[str]:
    """Drill from the top to ``tip`` in pecks of ``peck``, each with a full
    retract to the R plane and a rapid back to just above the last peck.
    Moves to and from the hole run at ``clear``."""
    clear, r_plane = _r(clear), _r(SAFE_MM)
    depths = []
    depth = 0.0
    while depth - peck > tip + 1e-6:
        depth -= peck
        depths.append(_r(depth))
    depths.append(_r(tip))
    lines = [f"G0 Z{clear:.3f}", "G0 X0.000 Y0.000", f"G0 Z{r_plane:.3f}"]
    previous = None
    for z in depths:
        if previous is not None:
            lines += [f"G0 Z{r_plane:.3f}", f"G0 Z{_r(previous + PECK_REENTRY_MM):.3f}"]
        lines.append(f"G1 Z{z:.3f} F{{feed}}")
        previous = z
    return lines + [f"G0 Z{r_plane:.3f}", f"G0 Z{clear:.3f}"]


def _geometry(features: dict[str, Any]) -> dict[str, Any]:
    """The strip and its taps from the export, each checked against the
    frame the recipe assumes: the left end X0 with the strip along +X, the
    flat top Y0 with the teeth at +Y, the front face Z0 with the back face at
    +Z; the taps entering the flat top along +Y, tap_1 stationed from the
    left end and the others from tap_1 along X."""
    f = features["features"]
    if f["left_end"]["plane"] != {"frame": "model", "axis": "x", "value": 0.0}:
        raise ValueError("left_end: expected at model X0")
    right = f["right_end"]
    if right.get("length_from") != "left_end" or not math.isclose(
        right["plane"]["value"], right["length_nominal"], abs_tol=1e-3
    ):
        raise ValueError("right_end: its plane is not the length from the left end")
    if f["flat_top"]["plane"] != {"frame": "model", "axis": "y", "value": 0.0}:
        raise ValueError("flat_top: expected at model Y0")
    teeth = f["teeth"]
    if teeth["plane"]["axis"] != "y" or not math.isclose(
        teeth["plane"]["value"], teeth["height_ref"], abs_tol=1e-6
    ):
        raise ValueError("teeth: the crest plane is not the height from the flat top")
    if f["front_face"]["plane"] != {"frame": "model", "axis": "z", "value": 0.0}:
        raise ValueError("front_face: expected at model Z0")
    back = f["back_face"]
    if back["plane"]["axis"] != "z" or not math.isclose(
        back["plane"]["value"], back["depth_ref"], abs_tol=1e-6
    ):
        raise ValueError("back_face: its plane is not the depth behind the front face")
    handled = {"left_end", "right_end", "flat_top", "teeth", "front_face", "back_face"}
    unknown = sorted(set(f) - handled - set(TAPS))
    if unknown:
        raise ValueError(f"features this recipe does not make: {unknown}")
    taps = [f[name] for name in TAPS]
    first = taps[0]
    shared = (
        "thread",
        "dia",
        "drill_depth",
        "drill_depth_nominal",
        "thread_depth",
        "inset",
    )
    for name, tap in zip(TAPS, taps):
        if tap["kind"] != "threaded_hole" or tap["axis"] != [0.0, 1.0, 0.0]:
            raise ValueError(f"{name}: expected a tap into the flat top along +Y")
        if tap["at"][1] != 0.0 or not math.isclose(
            tap["at"][2], tap["inset_nominal"], abs_tol=1e-6
        ):
            raise ValueError(f"{name}: 'at' is not on the flat top at its inset")
        if tap["inset_from"] != "front_face":
            raise ValueError(f"{name}: expected its inset from the front face")
        if any(tap[key] != first[key] for key in shared):
            raise ValueError(f"{name}: its thread or depths differ from tap_1's")
        if name == "tap_1":
            if tap["station_from"] != "left_end" or not math.isclose(
                tap["at"][0], tap["station_nominal"], abs_tol=1e-6
            ):
                raise ValueError("tap_1: expected stationed from the left end")
        elif (
            tap["station_from"] != "tap_1"
            or tap.get("station_axis") != "x"
            or not math.isclose(
                tap["at"][0] - first["at"][0], tap["station_nominal"], abs_tol=1e-6
            )
        ):
            raise ValueError(f"{name}: expected stationed from tap_1 along X")
    major = (0.060 + 0.013 * int(re.match(r"#(\d+)-", first["thread"]).group(1))) * IN
    return {
        "length_band": right["length"],
        "section": teeth["height_ref"],
        "width": back["depth_ref"],
        "pitch": teeth["pitch_ref"],
        "xs": [tap["at"][0] for tap in taps],
        "stations": [tap["station"] for tap in taps],
        "station_nominals": [tap["station_nominal"] for tap in taps],
        "inset": first["inset_nominal"],
        "inset_band": first["inset"],
        "dia": first["dia"],
        "drill_depth": first["drill_depth"],
        "drill_depth_nominal": first["drill_depth_nominal"],
        "thread_depth": first["thread_depth"],
        "major": major,
    }


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    g = _geometry(features)
    p = plan["parameters"]

    # The strip: the 3/16 square section with the spec's receiving room; the
    # length the middle of its printed 10.62 ±.01.
    if not math.isclose(g["section"], g["width"], abs_tol=1e-6):
        raise ValueError("the strip is not square: height and face width differ")
    _agree(plan, "section_mm", g["section"])
    h_min, h_max = g["section"] - SECTION_ROOM_MM, g["section"] + SECTION_ROOM_MM
    _agree(plan, "section_min_mm", h_min)
    _agree(plan, "section_max_mm", h_max)
    length = _mid(g["length_band"])
    _agree(plan, "length_target_mm", length)
    # The blank, sawn by hand; the left end skimmed to X0, the right end
    # milled from its raw station to the length.
    blank_min, blank_max = p["blank_length_min_in"] * IN, p["blank_length_max_in"] * IN
    _agree(plan, "blank_length_min_mm", blank_min)
    _agree(plan, "blank_length_max_mm", blank_max)
    skim = p["left_end_skim_mm"]
    if blank_min - skim - length < 0.5:
        raise ValueError(
            f"the shortest blank less the skim, {blank_min - skim:.3f}, leaves under "
            f"0.5 mm on the right end over the length {length:.3f}"
        )
    # The length read on the work X DRO: the right end touched with the
    # .200 edge finder from the right, X0 set again on the milled left end.
    _agree(plan, "length_dro_min_mm", g["length_band"][0] + FINDER_R_MM)
    _agree(plan, "length_dro_max_mm", g["length_band"][1] + FINDER_R_MM)

    # Holding: one stack of the parallels against the fixed jaw under the
    # strip (two 1/8 in parallels side by side would not fit a 3/16 strip),
    # the whole section inside the jaws, teeth up and teeth down alike.
    jaw_h, riser, t = (
        p["vise_jaw_height_mm"],
        p["riser_height_mm"],
        p["parallel_thickness_mm"],
    )
    if t >= h_min:
        raise ValueError(
            "the parallel is as wide as the strip: the jaws would close on it"
        )
    if riser + h_max >= jaw_h:
        raise ValueError("the thickest strip stands out of the jaws: the grip is short")
    jaw_top = jaw_h - riser - h_min
    _agree(plan, "jaw_top_over_work_mm", jaw_top)
    jaw_w = p["vise_jaw_width_mm"]
    # The ends, one hold each, the end milled end_overhang_mm past the jaw
    # side: FR01 holds the longest piece from its left end; FR02 the same
    # piece less the left end's skim, from its right end.
    end_overhang = p["end_overhang_mm"]
    _agree(plan, "left_clamp_end_mm", end_overhang + jaw_w)
    right_hold = blank_max - skim
    _agree(plan, "right_hold_length_mm", right_hold)
    _agree(plan, "right_hold_overhang_mm", right_hold - jaw_w - end_overhang)
    _agree(plan, "right_clamp_end_mm", right_hold - end_overhang)
    hole_overhang = (length - jaw_w) / 2
    _agree(plan, "hole_overhang_mm", hole_overhang)
    _agree(plan, "hole_clamp_end_mm", hole_overhang + jaw_w)

    # The tooth measurement (no program): a rod in the space on each tap
    # tooth's left, the edge finder touching both its sides. Holds A and B
    # put the measured end measure_overhang_mm out past the jaws, so the
    # finder, touching the rod's far side at the farthest tooth the window
    # allows, stays clear of the jaw side by at least the finder's radius.
    half_pitch = g["pitch"] / 2
    _agree(plan, "half_pitch_mm", half_pitch)
    rod = _shop_tool(plan, shop, "rod")["diameter_mm"]
    _agree(plan, "rod_dia_mm", rod)
    reach = p["measure_overhang_mm"] - FINDER_R_MM
    far_left = g["stations"][0][1] + g["station_nominals"][1] + half_pitch
    far_right = (
        g["length_band"][1]
        - g["stations"][0][0]
        - g["station_nominals"][2]
        + half_pitch
    )
    # The rod sits in the space on its tooth's left: away from the jaws in
    # hold A (tap 2, the jaws on its right), toward them in hold B (tap 3,
    # the jaws on its left). Its middle's distance from the measured end:
    for middle in (far_left - half_pitch, far_right + half_pitch):
        if middle + rod / 2 + 2 * FINDER_R_MM > reach:
            raise ValueError(
                "process.measure_overhang_mm: the edge finder would reach the jaws"
            )
    # Holds A and B leave the other end inside the jaws by this much.
    _agree(plan, "measure_inset_mm", p["measure_overhang_mm"] + jaw_w - length)
    # The windows the table prints: tap 1's tooth within half a pitch of its
    # nominal station, inside its printed band.
    _agree(plan, "tap_1_window_min_mm", g["station_nominals"][0] - half_pitch)
    _agree(plan, "tap_1_window_max_mm", g["station_nominals"][0] + half_pitch)
    if not (
        g["stations"][0][0] <= p["tap_1_window_min_mm"]
        and p["tap_1_window_max_mm"] <= g["stations"][0][1]
    ):
        raise ValueError("tap 1's window is not inside its printed station band")
    for k, band in enumerate(g["stations"], 1):
        _agree(plan, f"tap_{k}_station_min_mm", band[0])
        _agree(plan, f"tap_{k}_station_max_mm", band[1])
    # Setup 3's Y0 touch: the finder on the front face, its radius plus the
    # printed inset.
    _agree(plan, "y_touch_mm", g["inset"] + FINDER_R_MM)

    # The ends: the 1/4 in end mill's side, one level from SAFE over the
    # crests to end_past_mm under the thickest strip's flat top, in equal
    # radial steps no deeper than end_step_max_mm, one way across the strip.
    em = _shop_tool(plan, shop, "em-quarter")["diameter_mm"]
    r = em / 2
    # Each finished end still stands past its jaw side (the right one from
    # the longest piece's raw end set end_overhang_mm out), so the cutter,
    # outside the end, never comes over a jaw.
    right_off = blank_max - skim - length
    if end_overhang - skim <= 0 or end_overhang - right_off <= 0:
        raise ValueError("process.end_overhang_mm: a finished end lies inside the jaws")
    end_rpm, end_feed = _setting(plan, shop, "left end")
    if _setting(plan, shop, "right end") != (end_rpm, end_feed):
        raise ValueError("'right end' runs at another setting than 'left end'")
    end_step = p["end_step_max_mm"]
    end_z = -(h_max + p["end_past_mm"])
    _agree(plan, "end_axial_doc_mm", -end_z)
    for name in ("left end", "right end"):
        if not math.isclose(_cut(plan, name, "cutter_dia_mm"), em, abs_tol=1e-6):
            raise ValueError(
                f"'{name}' cutter Ø{_cut(plan, name, 'cutter_dia_mm')}, the end mill is Ø{em}"
            )
        if not math.isclose(_cut(plan, name, "radial_woc_mm"), end_step, abs_tol=1e-6):
            raise ValueError(f"'{name}' radial_woc_mm is not process.end_step_max_mm")
        if not math.isclose(_cut(plan, name, "axial_doc_mm"), -end_z, abs_tol=1e-6):
            raise ValueError(f"'{name}' axial_doc_mm is not process.end_axial_doc_mm")
    if p["em_projection_mm"] / em > shop["limits"]["stickout_ld_max"]:
        raise ValueError("process.em_projection_mm: over the shop's stick-out limit")
    if p["em_projection_mm"] < -end_z + jaw_top + CLEAR_MM:
        raise ValueError(
            "process.em_projection_mm: the collet would reach the jaw tops"
        )
    left_faces = _end_stations(-skim, 0.0, end_step)
    right_raw = blank_max - skim
    right_faces = _end_stations(right_raw, length, end_step)

    # The holes: spot to the thread's basic major (a mouth chamfer under the
    # .010 edge break), the 3/64 to the drill depth's nominal in pecks under
    # one diameter; both stay inside the tooth on the shortest strip.
    d364 = _shop_tool(plan, shop, "drill-3-64")["diameter_mm"]
    low, high = g["dia"]
    if not low - SIZE_TOL_MM <= d364 <= high:
        raise ValueError(f"3/64 Ø{d364} is outside the tap drill's band {g['dia']}")
    if not math.isclose(_cut(plan, "hole drill", "cutter_dia_mm"), d364, abs_tol=1e-3):
        raise ValueError("'hole drill' cutter_dia_mm is not the 3/64's")
    spot_dia = p["spot_dia_mm"]
    if not math.isclose(
        _cut(plan, "hole spot", "cutter_dia_mm"), spot_dia, abs_tol=1e-6
    ):
        raise ValueError("'hole spot' cutter_dia_mm is not process.spot_dia_mm")
    if not d364 < spot_dia <= g["major"] + 1e-6:
        raise ValueError("the spot is not between the 3/64 and the thread's major")
    spot_depth = _spot_depth(spot_dia)
    _agree(plan, "spot_depth_mm", spot_depth)
    peck = p["peck_mm"]
    op = _op_with_cut(plan, "hole drill")[0]
    if op["peck"] != {"step_mm": "{{process.peck_mm}}", "retract": "full"}:
        raise ValueError("'hole drill' peck is not process.peck_mm with full retract")
    if peck > d364:
        raise ValueError("process.peck_mm is over one 3/64 diameter")
    tip = -(g["drill_depth_nominal"] + _point(d364))
    _agree(plan, "drill_tip_height_mm", tip)
    _agree(plan, "drill_tip_over_stack_mm", h_min + tip)
    if -tip >= h_min:
        raise ValueError("the drill's point breaks out through the tooth crest")
    # The taps stop with their point at the drill's shallowest shoulder: the
    # bottoming tap's 1-1.5 pitch lead leaves the full thread in its band.
    _agree(plan, "tap_point_depth_mm", g["drill_depth"][0])
    spot_rpm, spot_feed = _setting(plan, shop, "hole spot")
    drill_rpm, drill_feed = _setting(plan, shop, "hole drill")
    for key, depth, oal in (
        ("spot", spot_depth, "centre_drill_oal_mm"),
        ("drill_3_64", -tip, "drill_3_64_oal_mm"),
    ):
        if p[f"{key}_projection_min_mm"] < jaw_top + depth + CLEAR_MM:
            raise ValueError(
                f"{key}_projection_min_mm: the chuck would reach the jaw tops"
            )
        if p[f"{key}_projection_min_mm"] >= p[oal]:
            raise ValueError(f"{key}_projection_min_mm: longer than the tool")

    # The tap stack's ceiling: spindle-to-table maximum less the tool-change
    # clearance, the vise bed, the stack, the thickest strip and the collet's
    # gauge, rounded down to .01 in; the tap's own reach in its wrench that
    # less the guide's length.
    machine = shop["machines"]["pm-30mv"]
    stack = (
        machine["spindle_to_table_mm"][1]
        - shop["limits"]["tool_change_clearance_mm"]
        - p["vise_bed_height_mm"]
        - riser
        - h_max
        - p["r8_collet_gauge_mm"]
    )
    stack_max = math.floor(stack / 0.254 + 1e-9) * 0.254
    _agree(plan, "tap_stack_max_mm", stack_max)
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

    # Frames (model point -> axes · (p - origin)).
    # FR01, FR02: teeth up, the front face against the fixed jaw: X along
    # the strip, Y0 the front face (+Y toward the fixed jaw, model -Z), Z0
    # the crests (model +Y).
    # FR03-FR05: teeth down, the front face toward the operator: Y0 the tap
    # line (+Y toward the back face, model +Z), Z0 the flat top (model -Y),
    # X0 tap 1's tooth (each hole is zeroed on its own tooth alike).
    section = g["section"]
    frames = {
        "ends": _frame([0.0, section, 0.0], [0, 0, -1], [0, 1, 0]),
        "hole": _frame([g["xs"][0], 0.0, g["inset"]], [0, 0, 1], [0, -1, 0]),
    }
    corner = _to(frames["ends"], [0.0, section, 0.0])
    if any(abs(v) > 1e-9 for v in corner):
        raise ValueError("ends: the left end's front crest is not at X0 Y0 Z0")
    entry = _to(frames["hole"], [g["xs"][0], 0.0, g["inset"]])
    if any(abs(v) > 1e-9 for v in entry):
        raise ValueError("hole: the tap's entry is not at X0 Y0 Z0")
    stocks = {
        "ends": ((-skim, blank_max - skim), (-section, 0.0), (-section, 0.0)),
        "hole": (
            (-g["xs"][0], length - g["xs"][0]),
            (-g["inset"], section - g["inset"]),
            (-section, 0.0),
        ),
    }

    em_tool = {
        "tool": "em-quarter",
        "dia": em,
        "shape": "endmill",
        "flutes": 3,
        "rpm": end_rpm,
        "feed": end_feed,
        "plunge": end_feed,
    }
    # Ends: the left one passes -Y and the right one +Y, the strip on the
    # cutter's left: conventional under M3 (the cutter outside each end).
    clear = jaw_top + CLEAR_MM
    beside = (-h_max - r - APPROACH_MM, r + APPROACH_MM)
    left_xs = [x - r for x in left_faces]
    right_xs = [x + r for x in right_faces]
    jobs = [
        {
            **em_tool,
            "frame": "ends",
            "label": "left end",
            "stock": stocks["ends"],
            "ops": [
                [
                    "left_end",
                    "mill the left end",
                    [f"G0 Z{_r(clear):.3f}"]
                    + _end(left_xs, beside[::-1], end_z, clear),
                ]
            ],
        },
        {
            **em_tool,
            "frame": "ends",
            "label": "right end",
            "stock": stocks["ends"],
            "ops": [
                [
                    "right_end",
                    "mill the right end to the length",
                    [f"G0 Z{_r(clear):.3f}"] + _end(right_xs, beside, end_z, clear),
                ]
            ],
        },
        {
            "tool": "spot",
            "dia": CENTRE_DRILL["body_mm"],
            "shape": "drill",
            "tip_angle": CENTRE_DRILL["point_deg"],
            "rpm": spot_rpm,
            "feed": spot_feed,
            "plunge": spot_feed,
            "frame": "hole",
            "label": "hole spot",
            "stock": stocks["hole"],
            "ops": [["spot", "spot the hole at X0 Y0", _spot(-spot_depth, clear)]],
        },
        {
            "tool": "drill-3-64",
            "dia": d364,
            "shape": "drill",
            "tip_angle": DRILL_POINT_DEG,
            "rpm": drill_rpm,
            "feed": drill_feed,
            "plunge": drill_feed,
            "frame": "hole",
            "label": "hole drill",
            "stock": stocks["hole"],
            "ops": [
                ["drill", "peck the 3/64 tap drill at X0 Y0", _pecked(tip, peck, clear)]
            ],
        },
    ]

    # The tap stop (one file, run once, at hole 1): the tap guide loaded by
    # its own M6, Z to the machine's top before any XY, over X0 Y0, M30: the
    # controller ends Idle for the operator's jog.
    thread = features["features"]["tap_1"]["thread"].split()[0]
    manual = {
        "tap": {
            "tool": numbers["tap-guide"],
            "label": names["tap-guide"],
            "setting": f"SPINDLE STAYS OFF. NEXT: {thread} TAPS IN THE HOLE AT X0 Y0",
            "gcode": [
                f"G53 G0 Z{MACHINE_Z_TOP_MM:.3f}",
                "G0 X0.000 Y0.000",
                f"({thread} PLUG TAP IN THE HOLE AT X0 Y0. JOG Z DOWN"
                " TO PUSH THE GUIDE POINT HOME IN THE WRENCH. TAP BY HAND TO THE NOTED DRO Z,"
                " READ WITH THE POINT PUSHED HOME. JOG Z UP CLEAR. NO M6 UNTIL BOTH TAPS ARE DONE)",
                "M30",
            ],
            "at": [0.0, 0.0],
        }
    }

    # Keep-outs. FR01, FR02: the jaws over the piece, the stack under it
    # against the fixed jaw, centred on the jaws; the moving jaw at the
    # narrowest strip. FR03-FR05 run at each of the four holes, so their
    # shapes are the jaws and the stack seen from every hole's zero.
    def end_keep(jaw_left: float) -> list[dict[str, Any]]:
        jaw_x = (jaw_left, jaw_left + jaw_w)
        mid = jaw_left + jaw_w / 2
        return [
            _box("moving jaw", jaw_x, (-h_min - JAW_DEPTH_MM, -h_min), jaw_top),
            _box("fixed jaw", jaw_x, (0.0, JAW_DEPTH_MM), jaw_top),
            _box(
                "stack",
                (mid - PARALLEL_LENGTH_MM / 2, mid + PARALLEL_LENGTH_MM / 2),
                (-t, 0.0),
                -h_min,
            ),
        ]

    left_keep = end_keep(end_overhang - skim)
    right_keep = end_keep(right_hold - jaw_w - end_overhang)
    hole_keep = []
    for k, x in enumerate(g["xs"], 1):
        span = (hole_overhang - x, hole_overhang + jaw_w - x)
        centre = length / 2 - x
        back = h_min - g["inset"]
        hole_keep += [
            _box(
                f"moving jaw {k}",
                span,
                (-g["inset"] - JAW_DEPTH_MM, -g["inset"]),
                jaw_top,
            ),
            _box(f"fixed jaw {k}", span, (back, back + JAW_DEPTH_MM), jaw_top),
            _box(
                f"stack {k}",
                (centre - PARALLEL_LENGTH_MM / 2, centre + PARALLEL_LENGTH_MM / 2),
                (back - t, back),
                -h_min,
            ),
        ]
    # Y0 is the tap's line, the print's inset from the front face (toward the
    # operator): the thread's major stays inside both faces of the narrowest
    # strip, so no tool reaches a jaw.
    if not (g["major"] / 2 < g["inset"] and g["major"] / 2 < h_min - g["inset"]):
        raise ValueError("the tap's major reaches a face of the strip")

    tn = numbers
    hole = [0.0, 0.0]

    def hole_checks(bottom: float, radius: float) -> list[list[Any]]:
        return [
            ["holes", {"centres": [hole], "z_bottom": _r(bottom)}],
            ["rapids_clear", {"z_top": 0.0, "open_holes": [hole]}],
            ["vertical_below_top", {"z_top": 0.0}],
            ["air_feed", {"z_top": 0.0}],
            ["keep_out", {"radius": radius, "boxes": hole_keep}],
        ]

    def end_checks(
        name: str, final: float, raw: float, direction: float, keep: list
    ) -> list:
        return [
            [
                name,
                "tool_changes",
                {"z_top": jaw_top, "tools": [tn["em-quarter"]], "loads_first": True},
            ],
            [name, "spindle", {"rpm": [[end_rpm]]}],
            [name, "pauses", {"z_top": jaw_top, "count": 0}],
            [name, "depth", {"z_min": _r(end_z)}],
            [name, "rapids_clear", {"z_top": 0.0}],
            [name, "air_feed", {"z_top": 0.0}],
            [
                name,
                "side_passes",
                {
                    "axis": "X",
                    "final": _r(final),
                    "raw": _r(raw),
                    "max_step": end_step,
                    "direction": direction,
                    "cut": "conventional",
                    "span": h_max,
                    "below_z": 0.0,
                },
            ],
            [name, "keep_out", {"radius": r, "boxes": keep}],
        ]

    expect: list[list[Any]] = end_checks(
        "FR01_left", -r, -skim - r, -1.0, left_keep
    ) + end_checks("FR02_right", length + r, right_raw + r, 1.0, right_keep)
    for name, tool, rpm, bottom, radius in (
        ("FR03_spot", "spot", spot_rpm, -spot_depth, CENTRE_DRILL["body_mm"] / 2),
        ("FR04_drill", "drill-3-64", drill_rpm, tip, d364 / 2),
    ):
        expect += [
            [
                name,
                "tool_changes",
                {"z_top": jaw_top, "tools": [tn[tool]], "loads_first": True},
            ],
            [name, "spindle", {"rpm": [[rpm]]}],
            [name, "pauses", {"z_top": jaw_top, "count": 0}],
            [name, "depth", {"z_min": _r(bottom)}],
            *[[name, check, kwargs] for check, kwargs in hole_checks(bottom, radius)],
        ]
    expect += [
        [
            "FR05_tap",
            "tap_stop",
            {
                "tool": tn["tap-guide"],
                "at": manual["tap"]["at"],
                "machine_top": MACHINE_Z_TOP_MM,
            },
        ],
        ["FR05_tap", "air_feed", {"z_top": 0.0}],
    ]

    return {
        "stem": STEM,
        "step": step_path,
        "comment": COMMENT,
        "frames": frames,
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
            doc, f"Feed rack {key}", ctx["step"], frame["origin"], frame["axes"]
        )
        for key, frame in ctx["frames"].items()
    }
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


# The as-machined report (``cad/scripts/_as_machined.py``) cannot take this
# part: FR03 and FR04 are one-hole files at X0 Y0, each run four times with
# X0 moved onto a tooth measured in Setup 2 (G10 L2 P1 X), and the report
# runs each file once in one frame.
AS_MACHINED_NOT_COVERED = (
    "FR03_spot and FR04_drill are one-hole files at X0 Y0, each run once per"
    " hole with X0 moved by hand onto a tooth measured in Setup 2 (G10 L2 P1"
    " X), and FR05_tap's guide reaches holes 2-4 by MDI; the report runs each"
    " file once in one frame, and where the teeth fall on a sawn piece is"
    " known only at the machine"
)
