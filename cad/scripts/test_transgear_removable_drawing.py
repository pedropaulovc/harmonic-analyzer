"""Offline contracts for the removable #25 sprocket (MHA-081) drawing."""

from __future__ import annotations

import ast
import math
import re
from collections.abc import Callable
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
Curve = Callable[[float], Point]


def _sind(degrees: float) -> float:
    return math.sin(math.radians(degrees))


def _cosd(degrees: float) -> float:
    return math.cos(math.radians(degrees))


def _equation(expression: str, values: dict[str, float], *, degrees: bool, t=0.0):
    """One SolidWorks equation: quoted globals, ``sqr``, ``atn`` in radians;
    the equation manager's trig takes degrees, an equation curve's radians."""
    names = {"_v": values, "t": t, "sqr": math.sqrt, "atn": math.atan}
    if degrees:
        names.update(sin=_sind, cos=_cosd, tan=lambda d: math.tan(math.radians(d)))
    else:
        names.update(sin=math.sin, cos=math.cos, tan=math.tan)
    code = re.sub(r'"(\w+)"', r'_v["\1"]', expression)
    return eval(code, {"__builtins__": {}}, names)


def _solved_globals(teeth: int) -> list[tuple[str, float, float]]:
    """``(name, solved, spec value)`` of each global the equation manager
    solves at ``teeth`` (the build writes them once; each configuration
    re-solves them from its own ToothCount)."""
    values: dict[str, float] = {}
    solved = []
    for name, expression, expected in part.gap_globals("atn(%s)", teeth):
        values[name] = _equation(expression, values, degrees=True)
        solved.append((name, values[name], expected))
    return solved


def _constructed_gap(teeth: int) -> dict[str, Curve]:
    """The seed gap the build cuts at ``teeth`` (mm), in loop order: the
    in-disc profile curve sliced at its solved breaks into its seven pieces
    (each over s in [0, 1]), then the clearance curves."""
    values = {name: value for name, value, _expected in _solved_globals(teeth)}

    def curve(x: str, y: str) -> Curve:
        return lambda t: (
            _equation(x, values, degrees=False, t=t) * _IN,
            _equation(y, values, degrees=False, t=t) * _IN,
        )

    loop = {label: curve(x, y) for label, x, y in part.gap_curves()}
    profile = loop.pop("in-disc profile")
    ends = [
        _equation(end, values, degrees=False) for _label, end in part.PROFILE_PIECES
    ]
    pieces = {
        label: (lambda s, a=a, b=b: profile(a + s * (b - a)))
        for (label, _end), a, b in zip(
            part.PROFILE_PIECES, [0.0, *ends[:-1]], ends, strict=True
        )
    }
    return pieces | loop


def _profile_curve(teeth: int) -> tuple[Curve, float]:
    """The in-disc profile curve (mm) and its solved length ``LProfile``."""
    values = {name: value for name, value, _expected in _solved_globals(teeth)}
    x, y = {label: (x, y) for label, x, y in part.gap_curves()}["in-disc profile"]
    return (
        lambda t: (
            _equation(x, values, degrees=False, t=t) * _IN,
            _equation(y, values, degrees=False, t=t) * _IN,
        ),
        values["LProfile"] * _IN,
    )


def _fitted_radius(curve: Curve) -> float:
    """Radius of the circle through the curve's ends and midpoint."""
    p, q, r = curve(0.0), curve(0.5), curve(1.0)
    cross = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return math.dist(p, q) * math.dist(q, r) * math.dist(r, p) / (2.0 * abs(cross))


_TEETH = [teeth for _name, teeth in spec.CONFIGS]


@pytest.mark.parametrize("teeth", _TEETH)
def test_every_configuration_solves_the_gap_the_spec_defines(teeth: int) -> None:
    """The build round-trips its globals only at T24; T12 and T18 re-solve
    the same equations in their configurations."""
    for name, solved, expected in _solved_globals(teeth):
        assert solved == pytest.approx(expected, rel=1e-9, abs=1e-12), name


@pytest.mark.parametrize("teeth", _TEETH)
def test_the_cut_gap_is_the_ansi_b29_1_standard_form(teeth: int) -> None:
    gap = _constructed_gap(teeth)
    labels = list(gap)
    for here, after in zip(labels, labels[1:] + labels[:1], strict=True):
        assert math.dist(gap[here](1.0), gap[after](0.0)) < 1e-6, (here, after)

    half = 180.0 / teeth
    pitch_dia = _P / _sind(half) * _IN
    # Seating curve R = Ds / 2 = 0.5025 Dr + 0.0015 in.
    seat_r = (0.5025 * _DR + 0.0015) * _IN
    assert _fitted_radius(gap["seating arc"]) == pytest.approx(seat_r, abs=0.005)
    # Bottom diameter PD - Dr, minus-only 0.002 P sqrt(N) + 0.006 in.
    inside_od = [label for label in labels if "clearance" not in label]
    bottom = 2.0 * min(
        math.hypot(*gap[label](k / 200.0)) for label in inside_od for k in range(201)
    )
    shortfall = pitch_dia - _DR * _IN - bottom
    assert 0.0 <= shortfall <= (0.002 * _P * math.sqrt(teeth) + 0.006) * _IN

    a_deg, b_deg = 35.0 + 60.0 / teeth, 18.0 - 56.0 / teeth
    working_r = (1.3025 * _DR + 0.0015) * _IN
    xy = (2.605 * _DR + 0.003) * _sind(9.0 - 28.0 / teeth) * _IN
    yz = _DR * (1.4 * _sind(17.0 - 64.0 / teeth) - 0.8 * _sind(b_deg)) * _IN
    topping = _DR * (0.8 * _cosd(b_deg) + 1.4 * _cosd(17.0 - 64.0 / teeth) - 1.3025)
    topping_r = (topping - 0.0015) * _IN
    for side, x_at in (("upper", 0.0), ("lower", 1.0)):
        working = gap[f"{side} working arc"]
        flank = gap[f"{side} flank"]
        # Working curve E about c; its arc x-y is B long about c.
        assert _fitted_radius(working) == pytest.approx(working_r, abs=0.005)
        x, y = working(x_at), working(1.0 - x_at)
        assert math.dist(x, y) == pytest.approx(xy, abs=0.005)
        assert math.dist(flank(0.0), flank(1.0)) == pytest.approx(yz, abs=0.005)
        topping_arc = gap[f"{side} topping arc"]
        assert _fitted_radius(topping_arc) == pytest.approx(topping_r, abs=0.005)
    # The seat meets the working curve at x, A below the pitch-circle tangent
    # at the pocket centre a: at 90 + A from the outward radial about a.
    centre = (pitch_dia / 2.0 * _cosd(half), pitch_dia / 2.0 * _sind(half))
    x_upper = gap["seating arc"](1.0)
    bearing = math.atan2(x_upper[1] - centre[1], x_upper[0] - centre[0])
    assert math.degrees(bearing) - half == pytest.approx(90.0 + a_deg, abs=1e-6)
    # The tips are turned to the OD p (0.6 + cot(180/N)).
    outside = _P * (0.6 + _cosd(half) / _sind(half)) * _IN
    for corner in (gap["lower topping arc"](0.0), gap["upper topping arc"](1.0)):
        assert 2.0 * math.hypot(*corner) == pytest.approx(outside, abs=0.005)


@pytest.mark.parametrize("teeth", _TEETH)
def test_the_profile_is_one_tangent_continuous_curve(teeth: int) -> None:
    """The in-disc profile is one curve with no corner between the OD
    corners: it runs at one speed (its length per unit t) and its direction
    turns smoothly across every junction of seat, working, flank and
    topping."""
    profile, length = _profile_curve(teeth)
    h = 1e-6

    def velocity(t: float) -> Point:
        p, q = profile(t - h), profile(t + h)
        return ((q[0] - p[0]) / (2 * h), (q[1] - p[1]) / (2 * h))

    for k in range(1, 1000):
        assert math.hypot(*velocity(k / 1000.0)) == pytest.approx(length, rel=1e-6)
    values = {name: value for name, value, _expected in _solved_globals(teeth)}
    for _label, end in part.PROFILE_PIECES[:-1]:
        at = _equation(end, values, degrees=False)
        before, after = velocity(at - 1e-4), velocity(at + 1e-4)
        turn = math.atan2(
            before[0] * after[1] - before[1] * after[0],
            before[0] * after[0] + before[1] * after[1],
        )
        # +/-1e-4 of t is under 2 um of profile: on arcs of R >= 1.69 mm a
        # smooth turn stays under 2e-3 rad, where a corner shows in full.
        assert abs(turn) < 1e-2, end


def test_the_published_30_tooth_example_constructs() -> None:
    """GEARS-IDS worked example, #25 x 30T: R .0668, E .1708, F .1050 in."""
    gap = _constructed_gap(30)
    for label, published in (
        ("seating arc", 0.0668),
        ("upper working arc", 0.1708),
        ("upper topping arc", 0.1050),
    ):
        assert _fitted_radius(gap[label]) / _IN == pytest.approx(published, abs=2e-4)


@pytest.mark.parametrize("teeth", _TEETH)
def test_the_volume_check_reads_the_area_the_curves_cut(teeth: int) -> None:
    """The build's per-configuration volume check uses ``spec.gap_area``:
    the cut loop's area inside the OD (the loop less its clearance sector)."""
    gap = _constructed_gap(teeth)
    points = [gap[label](k / 2000.0) for label in gap for k in range(2000)]
    shifted = points[1:] + points[:1]
    loop = 0.5 * abs(
        sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(points, shifted, strict=True))
    )
    ra = spec.outside_dia(teeth) / 2.0
    corner_x, corner_y = gap["upper topping arc"](1.0)
    corner = math.atan2(corner_y, corner_x) - math.pi / teeth
    in_disc = loop - corner * ((2.0 * ra) ** 2 - ra**2)
    assert in_disc == pytest.approx(spec.gap_area(teeth), rel=1e-4)


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
