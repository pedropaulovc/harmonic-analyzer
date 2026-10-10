"""Offline contracts for the removable #25 sprocket (MHA-PD-009) drawing."""

from __future__ import annotations

import ast
import math
import re
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import _config
import build_pd_transgear_removable as part
import draw_pd_transgear_removable as drawing
import pd_transgear_removable_notes as notes
import pd_transgear_removable_spec as spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pd-transgear-removable.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pd-transgear-removable.pdf")
    assert (
        DRAWINGS_BY_NAME["pd_transgear_removable"].script
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
    import dt_crankshaft_spec

    assert dt_crankshaft_spec.DRIVE_PIN_OFFSET_TOL == spec.DRIVE_PIN_OFFSET_TOL
    assert dt_crankshaft_spec.DRIVE_PIN_OFFSET_PLACES == spec.DRIVE_PIN_OFFSET_PLACES


def test_the_bands_live_on_the_model_dimensions() -> None:
    assert model_toleranced_dimensions(part) == {
        ("BlankProfile", "BlankWidth"): "*deviations(spec.PLATE_BAND)",
        ("BorePinsProfile", "PinPosY"): "spec.DRIVE_PIN_OFFSET_TOL",
        ("BorePinsProfile", "PinNegY"): "spec.DRIVE_PIN_OFFSET_TOL",
    }
    # Incoming plate inspection, not a facing-to-thickness operation.
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
    # PD - Dr, Dr = 0.130 in: T12 24.535 - 3.302 = 21.233.
    assert values("BOTTOM DIAMETER (mm, REF)") == ["21.23", "33.27", "45.35"]
    assert rows["CHAIN"] == "ANSI #25 ROLLER, PITCH 6.35, ROLLER Ø3.30"
    assert "AS SUPPLIED" in rows["TOOTH FORM (REF)"]


def test_the_outside_diameter_is_a_model_dimension_not_sheet_text() -> None:
    """The supplied OD remains a part-owned model dimension, but claims no
    turning tolerance or manufacturing operation on any configuration."""
    assert "BlankDia" in spec.DRAWING_DIMENSIONS["BlankProfile"]
    assert spec.DRAWING_REFERENCE_DIMENSIONS == {"BlankDia"}
    assert spec.DRAWING_PRECISION_BY_NAME["BlankDia"] == 1
    assert "OUTSIDE DIAMETER" not in notes.GEAR_DATA
    # p (0.6 + cot(180/N)): T12 6.35 (0.6 + 3.732) = 27.51.
    assert [f"{spec.outside_dia(teeth):.1f}" for _name, teeth in spec.CONFIGS] == [
        "27.5",
        "39.8",
        "52.0",
    ]


def test_every_configuration_prints_its_outside_diameter_once() -> None:
    """T24's prints on the main edge view; T12's and T18's each on a view of
    their own configuration -- one view per configuration, none twice."""
    printed = {spec.DEFAULT_CONFIG: drawing.TOP_KEEP} | {
        configuration: drawing.configuration_keep(configuration)
        for configuration in drawing.CONFIGURATION_VIEW_CENTERS
    }
    assert sorted(printed) == sorted(spec.TEETH)
    assert len(drawing.CONFIGURATION_VIEW_CENTERS) == len(spec.CONFIGS) - 1
    assert all("BlankDia" in keep for keep in printed.values())
    # A configuration view carries nothing but its diameter.
    for configuration in drawing.CONFIGURATION_VIEW_CENTERS:
        assert set(drawing.configuration_keep(configuration)) == {"BlankDia"}
        assert drawing.configuration_label(configuration).startswith(configuration)


def test_sheet_text_lines_are_short_and_carry_no_governance() -> None:
    labels = [
        drawing.configuration_label(configuration)
        for configuration in drawing.CONFIGURATION_VIEW_CENTERS
    ]
    lines = [*notes.GEAR_DATA.splitlines(), *notes.DRAWING_NOTES.splitlines(), *labels]
    assert max(len(line) for line in lines) <= 70
    text = "\n".join(lines).upper()
    for word in ("EXCEPTION", "ACCEPTED", "RULING", "POLICY", "BOOK FIDELITY"):
        assert word not in text


# Measured on the farm render 20260930T232554670Z (sheet metres): the pin
# chain's "7.000 ±0.025" shelves end at x 0.209, the isometric view starts at
# x 0.296 and SPROCKET DATA ends at y 0.231.  GetOutline pads an uncropped
# view ~5.5 mm (draw_cone_gear's T084 front); one character of default text
# is ~2.3 mm wide and ~3.5 mm tall.
_PIN_CHAIN_TEXT_RIGHT = 0.209
_ISO_LEFT = 0.296
_GEAR_DATA_BOTTOM = 0.231
_OUTLINE_PAD = 0.0055
_CHAR_W, _CHAR_H = 0.0023, 0.0035


def _configuration_view_box(configuration: str) -> tuple[float, float, float, float]:
    """A configuration view's padded outline, its dimension and its label."""
    x, y = drawing.CONFIGURATION_VIEW_CENTERS[configuration]
    scale = drawing.CONFIGURATION_VIEW_SCALE[0] / drawing.CONFIGURATION_VIEW_SCALE[1]
    half = spec.outside_dia(spec.TEETH[configuration]) * scale / 2000.0
    label_x, label_top = drawing.configuration_label_xy(configuration)
    label_right = label_x + len(drawing.configuration_label(configuration)) * _CHAR_W
    dimension_top = drawing.configuration_keep(configuration)["BlankDia"][1] + _CHAR_H
    return (
        min(x - half, label_x) - _OUTLINE_PAD,
        label_top - _CHAR_H,
        max(x + half, label_right) + _OUTLINE_PAD,
        dimension_top,
    )


@pytest.mark.parametrize("configuration", ["T12", "T18"])
def test_configuration_view_stands_in_free_sheet_space(configuration: str) -> None:
    left, bottom, right, top = _configuration_view_box(configuration)
    assert left > _PIN_CHAIN_TEXT_RIGHT
    assert right < _ISO_LEFT
    assert top < _GEAR_DATA_BOTTOM
    # The label hangs below its own view's padded outline: a free note the
    # view owns still collides with it.
    _x, y = drawing.CONFIGURATION_VIEW_CENTERS[configuration]
    scale = drawing.CONFIGURATION_VIEW_SCALE[0] / drawing.CONFIGURATION_VIEW_SCALE[1]
    outline_bottom = y - spec.PLATE * scale / 2000.0 - _OUTLINE_PAD
    assert drawing.configuration_label_xy(configuration)[1] < outline_bottom


def test_configuration_views_do_not_meet() -> None:
    upper = _configuration_view_box("T12")
    lower = _configuration_view_box("T18")
    assert lower[3] < upper[1]


class _Dimension:
    def __init__(self, values_m: dict[str, float]) -> None:
        self._values = values_m
        self.Tolerance = SimpleNamespace(Type=0)

    def GetSystemValue3(self, which: int, configuration: str):
        assert which == 3  # swSpecifyConfiguration
        return (self._values[configuration],)


class _Display:
    def __init__(self, places: int, values_m: dict[str, float]) -> None:
        self._places = places
        self._dimension = _Dimension(values_m)
        self._text = {1: "(<MOD-DIAM>", 2: ")"}

    def GetText(self, part: int) -> str:
        return self._text[part]

    def GetPrimaryPrecision2(self) -> int:
        return self._places

    def GetDimension2(self, index: int) -> _Dimension:
        return self._dimension


class _Annotation:
    def __init__(self, name: str, display: _Display) -> None:
        self.name = name
        self._display = display

    def GetSpecificAnnotation(self) -> _Display:
        return self._display


def _od_annotations(monkeypatch, places: int, values_m: dict[str, float]):
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, a: a.name)
    display = _Display(places, values_m)
    return [_Annotation("BlankWidth", display), _Annotation("BlankDia", display)]


_OD_M = {name: spec.outside_dia(teeth) / 1000.0 for name, teeth in spec.CONFIGS}


@pytest.mark.parametrize("configuration", [name for name, _teeth in spec.CONFIGS])
def test_each_view_reads_its_own_configurations_diameter(
    monkeypatch, configuration: str
) -> None:
    annotations = _od_annotations(monkeypatch, 1, _OD_M)
    drawing._assert_outside_diameter(None, annotations, configuration)


def test_a_view_showing_another_configurations_diameter_is_refused(monkeypatch) -> None:
    """One model dimension holds all three values: a T12 view reading T24's
    is the failure the per-view readback exists to catch."""
    values = dict(_OD_M, T12=_OD_M["T24"])
    annotations = _od_annotations(monkeypatch, 1, values)
    with pytest.raises(RuntimeError, match=r"T12: sheet BlankDia reads 52\.04"):
        drawing._assert_outside_diameter(None, annotations, "T12")


def test_a_diameter_that_lost_its_part_places_is_refused(monkeypatch) -> None:
    annotations = _od_annotations(monkeypatch, 2, _OD_M)
    with pytest.raises(RuntimeError, match=r"at 2 places, expected .* at 1"):
        drawing._assert_outside_diameter(None, annotations, "T18")


def test_a_view_without_exactly_one_diameter_is_refused(monkeypatch) -> None:
    annotations = _od_annotations(monkeypatch, 1, _OD_M)
    with pytest.raises(RuntimeError, match="expected one BlankDia"):
        drawing._assert_outside_diameter(None, annotations[:1], "T24")
    with pytest.raises(RuntimeError, match="expected one BlankDia"):
        drawing._assert_outside_diameter(None, annotations * 2, "T24")


@pytest.mark.parametrize("configuration", [name for name, _teeth in spec.CONFIGS])
def test_a_supplied_od_that_lost_its_reference_mark_is_refused(
    monkeypatch, configuration: str
) -> None:
    annotations = _od_annotations(monkeypatch, 1, _OD_M)
    annotations[1]._display._text[1] = "<MOD-DIAM>"
    with pytest.raises(RuntimeError, match="must be reference-only and unbanded"):
        drawing._assert_outside_diameter(None, annotations, configuration)


def test_a_supplied_od_with_a_manufacturing_band_is_refused(monkeypatch) -> None:
    annotations = _od_annotations(monkeypatch, 1, _OD_M)
    annotations[1]._display._dimension.Tolerance.Type = 2
    with pytest.raises(RuntimeError, match="must be reference-only and unbanded"):
        drawing._assert_outside_diameter(None, annotations, "T24")


def test_notes_specify_every_blank_and_the_operations_not_on_the_views() -> None:
    assert tuple(spec.BLANK_SKUS) == tuple(name for name, _teeth in spec.CONFIGS)
    for configuration, sku in spec.BLANK_SKUS.items():
        assert f"{sku} ({configuration})" in notes.DRAWING_NOTES
    assert "1 EACH" in notes.DRAWING_NOTES
    assert "TEETH, O.D. AND PLATE FACES AS SUPPLIED" in notes.DRAWING_NOTES
    assert "TURN HUB OFF FLUSH" in notes.DRAWING_NOTES


def test_notes_stay_within_four_lines_and_never_restate_the_title_block() -> None:
    lines = notes.DRAWING_NOTES.splitlines()
    assert len(lines) <= 4
    text = notes.DRAWING_NOTES.upper()
    assert "DEBUR" not in text and "+0.10" not in text
    assert "DEBUR" not in str(_config.parts("pd-transgear-removable")["finish"]).upper()


def test_the_notes_name_exactly_the_parts_the_drive_pins_press_into() -> None:
    """The holes slip over pins pressed into a host part; the sheet names
    each host by number.  Hosts are the assemblies' press-fit pairs: MHA-VN-044
    in the crankshaft, MHA-VN-038 in the knob's drive collar (not the shaft)."""
    from _interference_contracts import allowed_interference_pairs

    pins = {"vn-crank-seat-drive-pin", "vn-transgear-knob-drive-pin"}
    hosts: set[str] = set()
    for assembly in ("dt-drive-train", "pd-paper-drive"):
        for pair in allowed_interference_pairs(assembly):
            stems = {name.rsplit("-", 1)[0] for name in pair}
            if stems & pins:
                hosts |= stems - pins
    assert hosts == {"dt-crankshaft", "pd-transgear-drive-collar"}
    numbers = {_config.parts(host)["number"] for host in hosts}
    assert set(re.findall(r"MHA-[A-Z]{2}-\d{3}(?:-T\d{3})?", notes.DRAWING_NOTES)) == numbers


def test_gears_carry_no_frames_or_datums() -> None:
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    called = {
        getattr(node.func, "id", getattr(node.func, "attr", ""))
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    assert not called & {"add_feature_control_frame", "add_datum_feature"}


def test_registry_row_is_mha_081_one_of_each() -> None:
    row = _config.parts("pd-transgear-removable")
    assert row["number"] == "MHA-PD-009"
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
    import _part_properties
    import _drawing_marks

    required = ast.literal_eval(
        next(
            k.value
            for k in _calls(drawing.__file__)["read_required_properties"].keywords
            if k.arg == "required"
        )
    )
    carried = dict(_part_properties.part_properties(part.PART_NAME))
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


_AXIS_START = "axis_start"


def _relation_residuals(
    points: dict[str, Point], relation: str, ref: str, other: str
) -> list[float]:
    """A relation as equations on the points: zero when it holds."""
    if relation == "tangent":
        (at,) = set(part.GAP_ENTITIES[ref][1:]) & set(part.GAP_ENTITIES[other][1:])
        (ux, uy), (vx, vy) = _tangent(points, ref, at), _tangent(points, other, at)
        return [ux * vy - uy * vx]
    if relation == "equal":
        radius = part.gap_dimension_value
        return [
            radius(points, "radial", ref, None) - radius(points, "radial", other, None)
        ]
    if relation == "vertical_points":
        return [part.gap_point(points, ref)[0] - part.gap_point(points, other)[0]]
    if relation == "coincident" and ("." in other or other == "origin"):
        (x1, y1), (x2, y2) = part.gap_point(points, ref), part.gap_point(points, other)
        return [x1 - x2, y1 - y2]
    if relation == "coincident":  # a point on a line
        px, py = part.gap_point(points, ref)
        _centre, start, end = part.GAP_ENTITIES[other]
        (x0, y0), (x1, y1) = points[start], points[end]
        return [
            ((x1 - x0) * (py - y0) - (y1 - y0) * (px - x0))
            / math.dist((x0, y0), (x1, y1))
        ]
    raise AssertionError(f"unmodelled relation {relation}")


def _constraint_rank(teeth: int, dimensions, relations) -> tuple[int, int]:
    """(rank of the constraint Jacobian, unknowns) for the gap sketch.

    Every merged end point and arc centre is a free 2-D point; the sketch
    origin is fixed.  Each arc's ends lie on its circle, then the relations
    and dimensions add their equations.  The sketch is fully defined when
    the rank equals the unknowns.  The axis start is drawn at the origin but
    is its own point, held there only by its coincident relation."""
    base = part.gap_points(teeth)
    base[_AXIS_START] = base["origin"]
    names = sorted(name for name in base if name != "origin")

    def residuals(points: dict[str, Point]) -> list[float]:
        out = [
            math.dist(points[centre], points[start])
            - math.dist(points[centre], points[end])
            for centre, start, end in part.GAP_ENTITIES.values()
            if centre is not None
        ]
        for relation, ref, other in relations:
            out += _relation_residuals(points, relation, ref, other)
        out += [
            part.gap_dimension_value(points, kind, ref, other)
            for _name, kind, ref, other, _drive in dimensions
        ]
        return out

    step = 1e-6
    columns = []
    for name in names:
        for axis in (0, 1):
            plus, minus = dict(base), dict(base)
            nudged = list(base[name])
            nudged[axis] += step
            plus[name] = (nudged[0], nudged[1])
            nudged[axis] -= 2.0 * step
            minus[name] = (nudged[0], nudged[1])
            columns.append(
                (np.array(residuals(plus)) - np.array(residuals(minus))) / (2.0 * step)
            )
    jacobian = np.array(columns).T
    singular = np.linalg.svd(jacobian, compute_uv=False)
    return int((singular > 1e-7 * singular[0]).sum()), 2 * len(names)


@pytest.mark.parametrize("teeth", _TEETH)
def test_the_gap_sketch_is_fully_constrained_by_every_row(
    teeth: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The relations and dimensions leave no free motion in any configuration,
    and each row is load-bearing: omitting any one of them frees the sketch.
    Satisfied equations alone cannot show this -- a deleted row leaves every
    remaining one satisfied."""
    centre, _start, end = part.GAP_ENTITIES[part.GAP_AXIS]
    monkeypatch.setitem(part.GAP_ENTITIES, part.GAP_AXIS, (centre, _AXIS_START, end))
    dimensions, relations = part.GAP_DIMENSIONS, part.GAP_RELATIONS
    rank, unknowns = _constraint_rank(teeth, dimensions, relations)
    assert rank == unknowns
    for index, row in enumerate(dimensions):
        omitted = dimensions[:index] + dimensions[index + 1 :]
        assert _constraint_rank(teeth, omitted, relations)[0] < unknowns, row[0]
    for index, row in enumerate(relations):
        omitted = relations[:index] + relations[index + 1 :]
        assert _constraint_rank(teeth, dimensions, omitted)[0] < unknowns, row


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
def test_the_supplied_gap_is_the_ansi_b29_1_standard_form(teeth: int) -> None:
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
    # The supplied tips follow the OD p (0.6 + cot(180/N)).
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


@pytest.mark.parametrize(
    ("teeth", "vendor_plate_mm3"),
    [(12, 1248.331943), (18, 2834.845367), (24, 5065.837369)],
)
def test_chamfered_plate_matches_the_purchased_blank_volume(
    teeth: int, vendor_plate_mm3: float
) -> None:
    """OCP exact slab z=-1.397..1.397 of the pinned 6793K vendor STEPs,
    with the supplied bore/mouth breaks filled, isolates the supplied plate.
    Hub outside-edge breaks are therefore not mistaken for tooth relief.
    The ACA mid-profile is within 0.007 mm of these blanks, not identical;
    its plate volume must agree within 0.2%, independently of the build gate.
    """
    area = math.pi * (spec.outside_dia(teeth) / 2.0) ** 2 - teeth * spec.gap_area(teeth)
    at_vendor_thickness = spec.toothed_volume(teeth) - area * (spec.PLATE - 2.794)
    assert at_vendor_thickness == pytest.approx(vendor_plate_mm3, rel=0.002)
    # Losing either supplied-face chamfer is observable, even with the
    # residual difference between the standard and vendor tooth profiles.
    for missing_faces in (1, 2):
        incomplete = (
            at_vendor_thickness + missing_faces * spec.chamfer_volume(teeth) / 2.0
        )
        assert abs(incomplete - vendor_plate_mm3) > 0.002 * vendor_plate_mm3


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
