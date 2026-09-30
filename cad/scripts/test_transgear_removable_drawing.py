"""Offline contracts for the removable #25 sprocket (MHA-081) drawing."""

from __future__ import annotations

import ast
import math
import re
from pathlib import Path

import pytest

import _config
import build_transgear_removable as part
import draw_transgear_removable as drawing
import transgear_removable_notes as notes
import transgear_removable_spec as spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/transgear-removable.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/transgear-removable.pdf")
    assert (
        DRAWINGS_BY_NAME["transgear_removable"].script
        == Path(drawing.__file__).resolve()
    )
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP) == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.TOP_KEEP)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    # The part marks exactly what the sheet imports.
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    # Every callout lands on a dimension the sheet keeps.
    assert set(drawing.CALLOUTS_ABOVE) | set(drawing.CALLOUTS_BELOW) <= marked


def test_pin_locations_hold_the_shared_band_at_three_places() -> None:
    """Each hole is located like the shafts' pins, so the slip clearance
    absorbs both parts' spacing error; the size rows print routine .XX."""
    assert spec.DRAWING_PRECISION_BY_NAME["PinPosY"] == 3
    assert spec.DRAWING_PRECISION_BY_NAME["PinNegY"] == 3
    assert spec.DRAWING_PRECISION_BY_NAME["BoreDiaDim"] == 2
    assert spec.DRAWING_PRECISION_BY_NAME["PinPosDia"] == 2
    import crankshaft_spec

    assert crankshaft_spec.DRIVE_PIN_OFFSET_TOL == spec.DRIVE_PIN_OFFSET_TOL
    assert crankshaft_spec.DRIVE_PIN_OFFSET_PLACES == spec.DRIVE_PIN_OFFSET_PLACES


def test_the_bands_live_on_the_model_dimensions() -> None:
    assert model_toleranced_dimensions(part) == {
        ("BlankProfile", "BlankWidth"): "*deviations(spec.PLATE_BAND)",
        ("BorePinsProfile", "PinPosY"): "spec.DRIVE_PIN_OFFSET_TOL",
        ("BorePinsProfile", "PinNegY"): "spec.DRIVE_PIN_OFFSET_TOL",
    }
    # Faced to thickness, never over nominal.
    assert max(spec.PLATE_BAND) == 0.0 > min(spec.PLATE_BAND)


def test_web_worst_case_is_the_printed_limits() -> None:
    """Both holes at the DRILLED HOLES maximum and the pin centre moved its
    full band toward the bore; floored so the sheet never states more web."""
    drilled = _config.title_block("drilled_hole")
    assert drilled["minus_mm"] == 0.0
    oversize = drilled["plus_mm"]
    web = (
        spec.PIN_CIRCLE_DIA / 2.0
        - spec.DRIVE_PIN_OFFSET_TOL
        - (spec.PIN_HOLE_DIA + oversize) / 2.0
        - (spec.BORE_DIA + oversize) / 2.0
    )
    assert notes.BORE_PIN_WEB_WORST <= web < notes.BORE_PIN_WEB_WORST + 0.01
    assert 0.0 < notes.BORE_PIN_WEB_WORST < spec.BORE_PIN_WEB < 1.5
    assert notes.BORE_PIN_WEB_NOTE == "BORE TO DRIVE-PIN HOLE WEB 0.47 MIN."
    assert notes.BORE_PIN_WEB_NOTE in notes.DRAWING_NOTES.splitlines()


def test_sprocket_data_lists_every_configuration() -> None:
    rows = dict(
        line.split(":  ", 1) for line in notes.GEAR_DATA.splitlines() if ":  " in line
    )

    def values(label: str) -> list[str]:
        return rows[label].split("  /  ")

    assert values("CONFIGURATION") == [name for name, _teeth in spec.CONFIGS]
    assert values("NUMBER OF TEETH") == [str(teeth) for _name, teeth in spec.CONFIGS]
    # T12 hand check: p / sin 15 deg = 6.35 / 0.258819 = 24.535.
    assert values("PITCH DIAMETER (mm, REF)")[0] == "24.53"
    assert values("OUTSIDE DIAMETER (mm)") == ["27.5", "39.8", "52.0"]
    # PD - Dr, Dr = 0.130 in: T12 24.535 - 3.302 = 21.233.
    assert values("BOTTOM DIAMETER (mm, REF)") == ["21.23", "33.27", "45.35"]
    assert rows["CHAIN"] == "ANSI #25 ROLLER, PITCH 6.35, ROLLER Ø3.30"


def test_notes_stay_within_four_lines_and_never_restate_the_title_block() -> None:
    lines = notes.DRAWING_NOTES.splitlines()
    assert len(lines) <= 4
    text = notes.DRAWING_NOTES.upper()
    assert "DEBUR" not in text and "+0.10" not in text
    assert "DEBUR" not in str(_config.parts("transgear-removable")["finish"]).upper()


def test_gears_carry_no_frames_or_datums() -> None:
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    called = {
        getattr(node.func, "id", getattr(node.func, "attr", ""))
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    assert not called & {"add_feature_control_frame", "add_datum_feature"}


def test_registry_row_is_mha_081_one_of_each() -> None:
    row = _config.parts("transgear-removable")
    assert row["number"] == "MHA-081"
    assert int(row["quantity"]) == 1
    assert "1 EACH" in row["description"]


def _calls(path: str) -> dict[str, ast.Call]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return {
        node.func.id: node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_the_part_carries_every_property_its_drawing_requires(monkeypatch) -> None:
    """The drawing refuses a source part missing a required property; every
    one must be carried and non-blank."""
    import _common
    import _drawing_marks

    required = ast.literal_eval(
        next(
            k.value
            for k in _calls(drawing.__file__)["read_required_properties"].keywords
            if k.arg == "required"
        )
    )
    carried = dict(_common.part_properties(part.PART_NAME))
    stamp = _calls(part.__file__)["apply_drawing_properties"]
    assert [ast.unparse(a) for a in stamp.args[:2]] == ["adapter", "PART_NAME"]
    extra = {"Gear Data": notes.GEAR_DATA, "Manufacturing Notes": notes.DRAWING_NOTES}
    stamped: dict[str, str] = {}
    monkeypatch.setattr(
        _drawing_marks,
        "apply_custom_properties",
        lambda _adapter, props: stamped.update(props),
    )
    _drawing_marks.apply_drawing_properties(None, part.PART_NAME, extra)
    carried.update(stamped)
    assert [name for name in required if not str(carried.get(name) or "").strip()] == []


@pytest.mark.parametrize("name", ["PinPosY", "PinNegY"])
def test_pin_chain_sits_right_of_the_teeth(name: str) -> None:
    """The location chain stands clear of the T24 tips on the face view."""
    tip_x = drawing.FRONT_CENTER[0] + spec.outside_dia(24) / 2.0 * drawing._S / 1000.0
    assert drawing.FRONT_KEEP[name][0] > tip_x + 0.005


# ANSI #25 chain: pitch 1/4 in, roller 0.130 in.  The standard (ACA) tooth
# form's formulas are in inches (GEARS-IDS "Designing and Drawing a
# Sprocket" p. 2 Table 1); the bottom diameter and its minus-only commercial
# caliper tolerance are Machinery's Handbook 31st ed. pp. 2621-2623.
_IN = 25.4
_P, _DR = 0.25, 0.130

Point = tuple[float, float]


def _sind(degrees: float) -> float:
    return math.sin(math.radians(degrees))


def _cosd(degrees: float) -> float:
    return math.cos(math.radians(degrees))


def _equation(expression: str, values: dict[str, float]) -> float:
    """One SolidWorks equation: quoted globals, trig in degrees."""
    names = {
        "_v": values,
        "sin": _sind,
        "cos": _cosd,
        "tan": lambda d: math.tan(math.radians(d)),
    }
    code = re.sub(r'"(\w+)"', r'_v["\1"]', expression)
    return eval(code, {"__builtins__": {}}, names)


def _solved_globals(teeth: int) -> list[tuple[str, float, float]]:
    """``(name, solved, spec value)`` of each global the equation manager
    solves at ``teeth`` (the build writes them once; each configuration
    re-solves them from its own ToothCount)."""
    values: dict[str, float] = {}
    solved = []
    for name, expression, expected in part.gap_globals(teeth):
        values[name] = _equation(expression, values)
        solved.append((name, values[name], expected))
    return solved


def _driven(teeth: int) -> dict[str, float]:
    """Each gap sketch dimension (mm) as its drive equation sets it when a
    configuration's ToothCount is ``teeth``."""
    values = {name: value for name, value, _expected in _solved_globals(teeth)}
    return {
        name: _equation(drive, values) * _IN
        for name, _kind, _ref, _other, drive in part.GAP_DIMENSIONS
    }


def _sweep(points: dict[str, Point], name: str) -> float:
    """An arc's CCW sweep from its start to its end (radians, 0..2 pi)."""
    centre, start, end = (points[p] for p in part.GAP_ENTITIES[name])
    a0 = math.atan2(start[1] - centre[1], start[0] - centre[0])
    a1 = math.atan2(end[1] - centre[1], end[0] - centre[0])
    return (a1 - a0) % (2.0 * math.pi)


def _trace(points: dict[str, Point], name: str, n: int) -> list[Point]:
    """``n`` + 1 points along an entity from its start to its end."""
    centre, start, end = part.GAP_ENTITIES[name]
    (x0, y0), (x1, y1) = points[start], points[end]
    if centre is None:
        return [(x0 + k / n * (x1 - x0), y0 + k / n * (y1 - y0)) for k in range(n + 1)]
    cx, cy = points[centre]
    radius = math.hypot(x0 - cx, y0 - cy)
    a0, sweep = math.atan2(y0 - cy, x0 - cx), _sweep(points, name)
    return [
        (
            cx + radius * math.cos(a0 + k / n * sweep),
            cy + radius * math.sin(a0 + k / n * sweep),
        )
        for k in range(n + 1)
    ]


def _loop(points: dict[str, Point], n: int) -> list[Point]:
    """The cut profile walked end to end from x_u, each entity traced in
    whichever direction continues the walk; fails unless it closes."""
    left = [name for name in part.GAP_ENTITIES if name != part.GAP_AXIS]
    at, walk = "x_u", []
    while left:
        name = next(name for name in left if at in part.GAP_ENTITIES[name][1:])
        left.remove(name)
        _centre, start, end = part.GAP_ENTITIES[name]
        trace = _trace(points, name, n)
        walk += (trace if start == at else trace[::-1])[:-1]
        at = end if start == at else start
    assert at == "x_u", "the profile does not close"
    return walk


def _tangent(points: dict[str, Point], name: str, at: str) -> Point:
    """Unit direction of an entity at one of its end points."""
    centre, start, end = part.GAP_ENTITIES[name]
    if centre is None:
        dx, dy = points[end][0] - points[start][0], points[end][1] - points[start][1]
    else:
        dx = -(points[at][1] - points[centre][1])
        dy = points[at][0] - points[centre][0]
    length = math.hypot(dx, dy)
    return dx / length, dy / length


_TEETH = [teeth for _name, teeth in spec.CONFIGS]


@pytest.mark.parametrize("teeth", _TEETH)
def test_every_configuration_solves_the_gap_the_spec_defines(teeth: int) -> None:
    """The build round-trips its globals only at T24; T12 and T18 re-solve
    the same equations in their configurations."""
    for name, solved, expected in _solved_globals(teeth):
        assert solved == pytest.approx(expected, rel=1e-9, abs=1e-12), name


@pytest.mark.parametrize("teeth", _TEETH)
def test_the_driven_dimensions_hold_the_spec_gap(teeth: int) -> None:
    """Every gap dimension's drive equation, solved at a configuration's
    ToothCount, is what that dimension measures on ``spec.gap_geometry``'s
    gap -- so re-solving the sketch there lands on the spec's tooth form."""
    points = part.gap_points(teeth)
    driven = _driven(teeth)
    for name, kind, ref, other, _drive in part.GAP_DIMENSIONS:
        measured = part.gap_dimension_value(points, kind, ref, other)
        assert measured > 1e-3, name  # a zero-valued dimension is invalid
        assert driven[name] == pytest.approx(measured, rel=1e-9), name


@pytest.mark.parametrize("teeth", _TEETH)
def test_the_gap_relations_hold_in_every_configuration(teeth: int) -> None:
    """Each sketch relation is satisfied by the spec gap at every tooth
    count, and every arc's two ends lie on its circle."""
    points = part.gap_points(teeth)
    for name, (centre, start, end) in part.GAP_ENTITIES.items():
        if centre is not None:
            assert math.dist(points[centre], points[start]) == pytest.approx(
                math.dist(points[centre], points[end]), abs=1e-9
            ), name
    for relation, ref, other in part.GAP_RELATIONS:
        if relation == "tangent":
            (at,) = set(part.GAP_ENTITIES[ref][1:]) & set(part.GAP_ENTITIES[other][1:])
            (ux, uy), (vx, vy) = _tangent(points, ref, at), _tangent(points, other, at)
            assert ux * vy - uy * vx == pytest.approx(0.0, abs=1e-9), (ref, other)
        elif relation == "equal":
            radius = part.gap_dimension_value
            assert radius(points, "radial", ref, None) == pytest.approx(
                radius(points, "radial", other, None), abs=1e-9
            ), (ref, other)
        elif relation == "vertical_points":
            x1, _ = part.gap_point(points, ref)
            x2, _ = part.gap_point(points, other)
            assert x1 == pytest.approx(x2, abs=1e-9), (ref, other)
        elif relation == "coincident" and ("." in other or other == "origin"):
            assert part.gap_point(points, ref) == pytest.approx(
                part.gap_point(points, other), abs=1e-9
            ), (ref, other)
        elif relation == "coincident":  # a point on a line
            px, py = part.gap_point(points, ref)
            _centre, start, end = part.GAP_ENTITIES[other]
            (x0, y0), (x1, y1) = points[start], points[end]
            cross = (x1 - x0) * (py - y0) - (y1 - y0) * (px - x0)
            assert cross / math.dist((x0, y0), (x1, y1)) == pytest.approx(0.0, abs=1e-9)
        else:
            raise AssertionError(f"unchecked relation {relation}")


@pytest.mark.parametrize("teeth", _TEETH)
def test_the_gap_draws_as_one_loop_of_minor_arcs_outside_the_disc(teeth: int) -> None:
    """CreateArc runs CCW from start to end, so each arc's start/end order
    must pick the short way round; the profile closes; the clearance lines
    never enter the blank."""
    points = part.gap_points(teeth)
    for name, (centre, _start, _end) in part.GAP_ENTITIES.items():
        if centre is not None:
            assert 0.0 < _sweep(points, name) < math.pi, name
    _loop(points, 4)
    ra = spec.outside_dia(teeth) / 2.0
    for name in ("ClearLower", "ClearUpper"):
        radii = [math.hypot(*p) for p in _trace(points, name, 400)]
        assert min(radii) == pytest.approx(ra, abs=1e-9), name


@pytest.mark.parametrize("teeth", _TEETH)
def test_the_cut_gap_is_the_ansi_b29_1_standard_form(teeth: int) -> None:
    points = part.gap_points(teeth)

    def radius(name: str) -> float:
        return part.gap_dimension_value(points, "radial", name, None)

    half = 180.0 / teeth
    pitch_dia = _P / _sind(half) * _IN
    # Seating curve R = Ds / 2 = 0.5025 Dr + 0.0015 in.
    seat_r = (0.5025 * _DR + 0.0015) * _IN
    assert radius("Seat") == pytest.approx(seat_r, abs=0.005)
    # Bottom diameter PD - Dr, minus-only 0.002 P sqrt(N) + 0.006 in.
    bottom = 2.0 * min(math.hypot(*p) for p in _loop(points, 400))
    shortfall = pitch_dia - _DR * _IN - bottom
    assert 0.0 <= shortfall <= (0.002 * _P * math.sqrt(teeth) + 0.006) * _IN

    a_deg, b_deg = 35.0 + 60.0 / teeth, 18.0 - 56.0 / teeth
    working_r = (1.3025 * _DR + 0.0015) * _IN
    xy = (2.605 * _DR + 0.003) * _sind(9.0 - 28.0 / teeth) * _IN
    yz = _DR * (1.4 * _sind(17.0 - 64.0 / teeth) - 0.8 * _sind(b_deg)) * _IN
    topping = _DR * (0.8 * _cosd(b_deg) + 1.4 * _cosd(17.0 - 64.0 / teeth) - 1.3025)
    topping_r = (topping - 0.0015) * _IN
    # The tips are turned to the OD p (0.6 + cot(180/N)).
    outside = _P * (0.6 + _cosd(half) / _sind(half)) * _IN
    for side, working, topping_arc in (
        ("u", "WorkUpper", "TopUpper"),
        ("l", "WorkLower", "TopLower"),
    ):
        # Working curve E about c; its arc x-y is B long about c.
        assert radius(working) == pytest.approx(working_r, abs=0.005)
        x, y, z = (points[f"{p}_{side}"] for p in "xyz")
        assert math.dist(x, y) == pytest.approx(xy, abs=0.005)
        assert math.dist(y, z) == pytest.approx(yz, abs=0.005)
        assert radius(topping_arc) == pytest.approx(topping_r, abs=0.005)
        assert 2.0 * math.hypot(*points[f"k_{side}"]) == pytest.approx(
            outside, abs=0.005
        )
    # The seat meets the working curve at x, A below the pitch-circle tangent
    # at the pocket centre a: at 90 + A from the outward radial about a.
    centre = points["a"]
    assert 2.0 * math.hypot(*centre) == pytest.approx(pitch_dia, abs=1e-9)
    x_upper = points["x_u"]
    bearing = math.atan2(x_upper[1] - centre[1], x_upper[0] - centre[0])
    assert math.degrees(bearing) - half == pytest.approx(90.0 + a_deg, abs=1e-6)


def test_the_published_30_tooth_example_constructs() -> None:
    """GEARS-IDS worked example, #25 x 30T: R .0668, E .1708, F .1050 in."""
    driven = _driven(30)
    for name, published in (
        ("GapSeatR", 0.0668),
        ("GapWorkR", 0.1708),
        ("GapTopR", 0.1050),
    ):
        assert driven[name] / _IN == pytest.approx(published, abs=2e-4)


@pytest.mark.parametrize("teeth", _TEETH)
def test_the_volume_check_reads_the_area_the_sketch_cuts(teeth: int) -> None:
    """The build's per-configuration volume check uses ``spec.gap_area``:
    the cut loop's area inside the OD (the loop less the region its
    clearance lines close outside the OD)."""
    points = part.gap_points(teeth)
    loop = _loop(points, 2000)
    shifted = loop[1:] + loop[:1]
    area = 0.5 * abs(
        sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(loop, shifted, strict=True))
    )
    ra = spec.outside_dia(teeth) / 2.0
    k_l, q, k_u = points["k_l"], points["q"], points["k_u"]
    # The fan O-k_l-q-k_u less the OD sector between the corners.
    fan = 0.5 * sum(p[0] * r[1] - r[0] * p[1] for p, r in ((k_l, q), (q, k_u)))
    corner = math.atan2(k_u[1], k_u[0]) - math.atan2(k_l[1], k_l[0])
    outside = fan - 0.5 * ra * ra * corner
    assert area - outside == pytest.approx(spec.gap_area(teeth), rel=1e-5)


class _Result:
    is_success = True
    data = None
    error = None


class _Tolerance:
    def __init__(self, kind: int, lower_mm: float, upper_mm: float) -> None:
        self.Type = kind
        self._limits = (lower_mm / 1000.0, upper_mm / 1000.0)

    def GetMinValue(self) -> float:
        return self._limits[0]

    def GetMaxValue(self) -> float:
        return self._limits[1]


class _Configurations:
    """A part whose tolerances are read per active configuration."""

    def __init__(self, bands: dict[str, dict]) -> None:
        self.bands = bands
        self.active = spec.DEFAULT_CONFIG
        self.visited: list[str] = []

    async def set_active_configuration(self, name: str) -> _Result:
        self.active = name
        self.visited.append(name)
        return _Result()


def _readback(monkeypatch, adapter: _Configurations) -> None:
    import asyncio
    from types import SimpleNamespace

    def named(_adapter, feature: str, dimension: str):
        band = adapter.bands[adapter.active][(feature, dimension)]
        return None, SimpleNamespace(Tolerance=_Tolerance(*band))

    monkeypatch.setattr(part, "_named_dimension", named)
    monkeypatch.setattr(part, "_early_bound", lambda obj, _interface: obj)
    asyncio.run(part.assert_bands_in_every_configuration(adapter))


def test_every_configuration_must_read_the_family_bands_back(monkeypatch) -> None:
    """The sheet prints the plate and pin-location bands once for all three
    sprockets, so the build reads them back in each configuration."""
    bands = part.family_bands()
    assert bands[("BlankProfile", "BlankWidth")][1:] == (-0.10, 0.0)
    adapter = _Configurations({name: dict(bands) for name, _teeth in spec.CONFIGS})
    _readback(monkeypatch, adapter)
    assert adapter.visited == [name for name, _teeth in spec.CONFIGS] + [
        spec.DEFAULT_CONFIG
    ]
    # Negative control: a band that stayed in the default configuration only
    # (T12 untoleranced) must stop the build.
    untoleranced = {name: dict(bands) for name, _teeth in spec.CONFIGS}
    untoleranced["T12"][("BlankProfile", "BlankWidth")] = (0, 0.0, 0.0)
    with pytest.raises(RuntimeError, match=r"T12: BlankWidth@BlankProfile"):
        _readback(monkeypatch, _Configurations(untoleranced))
