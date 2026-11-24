"""Offline contracts for the removable #25 sprocket (MHA-PD-09) drawing."""

from __future__ import annotations

import ast
import inspect
import math
import re
import textwrap
from pathlib import Path

import pytest

import _config
import build_pd_transgear_removable as part
import draw_pd_transgear_removable as drawing
import pd_transgear_removable_callouts as callouts
import pd_transgear_removable_notes as notes
import pd_transgear_removable_spec as spec
import _sprocket_seat_geometry as seat_geometry
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
from _drawing_registry import DRAWINGS_BY_NAME


def test_mounted_selections_read_registered_configuration_counts() -> None:
    assert spec.CRANK_TEETH == spec.configuration_teeth(spec.CRANK_CONFIG)
    assert spec.KNOB_TEETH == spec.configuration_teeth(spec.KNOB_CONFIG)


@pytest.mark.parametrize("configuration,teeth", spec.CONFIGS)
def test_configuration_count_reader_uses_the_registered_family(
    configuration: str, teeth: int
) -> None:
    assert spec.configuration_teeth(configuration) == teeth


@pytest.mark.parametrize("configuration", ["t12", "T13", "T012", "", " T12 "])
def test_unregistered_or_nonexact_configuration_is_refused(configuration: str) -> None:
    with pytest.raises(ValueError, match="unknown removable sprocket configuration"):
        spec.configuration_teeth(configuration)


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
    # Every callout row lands on a dimension its feature marks and the sheet
    # keeps.
    for rows in callouts.CALLOUTS.values():
        for feature, name in rows:
            assert name in spec.DRAWING_DIMENSIONS[feature], (feature, name)


def test_pin_locations_print_inside_the_shared_band() -> None:
    """Each hole's offset prints as a REF target (fit audit 2026-11-23); its
    analysis scatter stays inside the band the shafts' pins share, so the
    slip clearance absorbs both parts' spacing error; the drilled sizes print
    their 3-place drill."""
    assert callouts.TARGET_TEXT == {
        ("BorePinsProfile", name): {callouts.TEXT_PREFIX: "(", callouts.TEXT_SUFFIX: ")"}
        for name in ("PinPosY", "PinNegY")
    }
    authored = callouts.authored_text()["BorePinsProfile"]
    assert authored["PinPosY"] == authored["PinNegY"] == {
        callouts.TEXT_PREFIX: "(", callouts.TEXT_SUFFIX: ")"
    }
    # No native band on the offsets: the plate's is the only one.
    assert set(part.family_bands()) == {("BlankProfile", "BlankWidth")}
    assert spec.DRAWING_PRECISION_BY_NAME["PinPosY"] == 4
    assert spec.DRAWING_PRECISION_BY_NAME["PinNegY"] == 4
    assert spec.DRAWING_PRECISION_BY_NAME["BoreDiaDim"] == 3
    assert spec.DRAWING_PRECISION_BY_NAME["PinPosDia"] == 3
    assert spec.PIN_LOCATION_TOL <= seat_geometry.DRIVE_PIN_OFFSET_TOL
    assert spec.PIN_SLIP_CLEARANCE_MIN >= 2.0 * (
        seat_geometry.DRIVE_PIN_OFFSET_TOL + spec.PIN_LOCATION_TOL
    )
    import dt_crankshaft_spec

    # The shaft's pins are located no looser than the wheel's holes.
    assert (
        dt_crankshaft_spec.DRIVE_PIN_SPACING_ERROR_MAX / 2.0
        <= seat_geometry.DRIVE_PIN_OFFSET_TOL + 1e-12
    )


def test_printed_plate_band_stays_inside_the_stacked_plate_band() -> None:
    # Incoming plate inspection, not a facing-to-thickness operation.
    assert max(seat_geometry.PLATE_BAND) == 0.0 > min(seat_geometry.PLATE_BAND)
    low, high = spec._PLATE_PRINTED
    assert seat_geometry.PLATE + min(seat_geometry.PLATE_BAND) <= low < high
    assert high <= seat_geometry.PLATE + max(seat_geometry.PLATE_BAND)


def test_web_worst_case_is_the_printed_limits() -> None:
    """Both holes at the DRILLED HOLES maximum and the pin centre moved its
    full band toward the bore; floored so the sheet never states more web."""
    from _printed_tolerance import drilled_oversize_mm, drilled_undersize_mm

    assert drilled_undersize_mm(unit=spec.UNIT) == 0.0
    oversize = drilled_oversize_mm(unit=spec.UNIT)
    web = (
        seat_geometry.PIN_CIRCLE_DIA / 2.0
        - spec.PIN_LOCATION_TOL
        - (spec.PIN_HOLE_DIA + oversize) / 2.0
        - (spec.BORE_DIA + oversize) / 2.0
    ) / 25.4
    assert notes.BORE_PIN_WEB_WORST_IN <= web < notes.BORE_PIN_WEB_WORST_IN + 0.001
    assert 0.0 < notes.BORE_PIN_WEB_WORST_IN * 25.4 < seat_geometry.BORE_PIN_WEB
    assert notes.BORE_PIN_WEB_NOTE in notes.DRAWING_NOTES.splitlines()
    # A wheel that binds on the pins has one hole drilled #39, the next
    # number size: its web, re-derived the same way, prints beside the #40's.
    assert notes.EASED_HOLE_DRILL == ("#39", 0.0995)
    eased = web - (notes.EASED_HOLE_DRILL[1] - spec.PIN_HOLE_DIA / 25.4) / 2.0
    assert eased == pytest.approx(0.01794, abs=1e-5)
    assert notes.EASED_WEB_WORST_IN <= eased < notes.EASED_WEB_WORST_IN + 0.001
    assert notes.BORE_PIN_WEB_NOTE == (
        "BORE TO DRIVE-PIN HOLE WEB .018 MIN; .017 MIN AT A HOLE DRILLED #39."
    )
    # The acceptance is the trial on the pins, never a reading of the offsets.
    assert notes.TRIAL_NOTE in notes.DRAWING_NOTES.splitlines()
    assert "DROPS ON BOTH SEATS' PINS FREELY" in notes.TRIAL_NOTE
    assert notes.EASED_HOLE_DRILL[0] in notes.TRIAL_NOTE


def test_sprocket_data_lists_every_configuration() -> None:
    rows = dict(
        line.split(":  ", 1) for line in notes.GEAR_DATA.splitlines() if ":  " in line
    )

    def values(label: str) -> list[str]:
        return rows[label].split("  /  ")

    assert values("CONFIGURATION") == [name for name, _teeth in spec.CONFIGS]
    assert values("NUMBER OF TEETH") == [str(teeth) for _name, teeth in spec.CONFIGS]
    # T12 hand check: p / sin 15 deg = .250 / 0.258819 = .9659 in.
    assert values("PITCH DIAMETER (REF)")[0] == ".966"
    assert "AS SUPPLIED" in rows["TOOTH FORM (REF)"]


def test_the_outside_diameter_is_a_model_dimension_not_sheet_text() -> None:
    """The supplied OD remains a part-owned model dimension, but claims no
    turning tolerance or manufacturing operation on any configuration."""
    assert "BlankDia" in spec.DRAWING_DIMENSIONS["BlankProfile"]
    assert spec.DRAWING_REFERENCE_DIMENSIONS == {"BlankDia"}
    assert "OUTSIDE DIAMETER" not in notes.GEAR_DATA
    # p (0.6 + cot(180/N)): T12 .250 (0.6 + 3.732) = 1.083 in.
    assert [
        f"{spec.outside_dia(teeth) / 25.4:.2f}" for _name, teeth in spec.CONFIGS
    ] == ["1.08", "1.57", "2.05"]


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
    outline_bottom = y - seat_geometry.PLATE * scale / 2000.0 - _OUTLINE_PAD
    assert drawing.configuration_label_xy(configuration)[1] < outline_bottom


def test_configuration_views_do_not_meet() -> None:
    upper = _configuration_view_box("T12")
    lower = _configuration_view_box("T18")
    assert lower[3] < upper[1]


def test_notes_specify_every_blank_and_the_operations_not_on_the_views() -> None:
    assert tuple(spec.BLANK_SKUS) == tuple(name for name, _teeth in spec.CONFIGS)
    for configuration, sku in spec.BLANK_SKUS.items():
        assert f"{sku} ({configuration})" in notes.DRAWING_NOTES
    assert "1 EACH" in notes.DRAWING_NOTES
    assert "TEETH, O.D. AND PLATE FACES AS SUPPLIED" in notes.DRAWING_NOTES
    assert "HUB REMOVED FLUSH" in notes.DRAWING_NOTES


def test_notes_stay_within_five_lines_and_never_restate_the_title_block() -> None:
    # Five since the fit audit of 2026-11-23: the wheels' trial on the pins
    # replaces the offsets' printed band and needs its one line.
    lines = notes.DRAWING_NOTES.splitlines()
    assert len(lines) <= 5
    text = notes.DRAWING_NOTES.upper()
    assert "DEBUR" not in text and "+0.10" not in text
    assert "DEBUR" not in str(_config.parts("pd-transgear-removable")["finish"]).upper()


def test_the_pin_locations_name_exactly_the_parts_the_drive_pins_press_into() -> None:
    """The holes slip over pins pressed into a host part; each banded pin
    location names each host by number.  Hosts are the assemblies' press-fit
    pairs: MHA-DT-VN-67 in the crankshaft, MHA-PD-VN-54 in the knob's drive
    collar (not the shaft)."""
    from _dt_drive_train_interference import ALLOWED_PAIRS as drive_train
    from _pd_paper_drive_interference import ALLOWED_PAIRS as paper_drive

    pins = {"dt-vn-crank-seat-drive-pin", "pd-vn-transgear-knob-drive-pin"}
    hosts: set[str] = set()
    for table in (drive_train, paper_drive):
        for pair in table:
            stems = {name.rsplit("-", 1)[0] for name in pair}
            if stems & pins:
                hosts |= stems - pins
    assert hosts == {"dt-crankshaft", "pd-transgear-drive-collar"}
    numbers = {_config.parts(host)["number"] for host in hosts}
    number = re.compile(
        r"MHA-(?!VN-)[A-Z]{2}-(?:[0-9]{2}(?:-TL-(?:[0-9]{2}|VN-[5-9][0-9]))?"
        r"|VN-[5-9][0-9])(?:-T[0-9]{3})?(?![A-Z0-9-])"
    )
    below = callouts.callouts_by_name(callouts.CALLOUT_BELOW)
    # Named once, on the 2X pattern callout; the locations carry no words.
    assert set(number.findall(below["PinPosDia"])) == numbers
    assert "PinPosY" not in below and "PinNegY" not in below
    # The mates print at the band they explain, not in the general notes.
    assert not number.findall(notes.DRAWING_NOTES)


def test_the_plate_band_names_the_chain_it_serves() -> None:
    callout = callouts.callouts_by_name(callouts.CALLOUT_BELOW)["BlankWidth"]
    assert _config.parts("sh-vn-chain-link")["number"] in callout


def test_the_sheet_names_t24_and_covers_what_every_configuration_shares() -> None:
    """The dimensioned views are T24's; one note line covers every
    configuration, and only the supplied OD differs between them (each other
    configuration's view prints nothing else)."""
    assert drawing.MAIN_VIEW_LABEL == spec.DEFAULT_CONFIG
    names = [name for name, _teeth in spec.CONFIGS]
    shared = [
        line
        for line in notes.DRAWING_NOTES.splitlines()
        if all(name in line for name in names) and "BLANK" not in line
    ]
    assert len(shared) == 1
    for configuration in drawing.CONFIGURATION_VIEW_CENTERS:
        assert set(drawing.configuration_keep(configuration)) == {"BlankDia"}
    assert spec.DRAWING_REFERENCE_DIMENSIONS == {"BlankDia"}


def test_the_part_authors_the_reference_mark_of_every_reference_dimension() -> None:
    assert {name for _feature, name in callouts.REFERENCE_TEXT} == set(
        spec.DRAWING_REFERENCE_DIMENSIONS
    )


_SCRIPTS = Path(drawing.__file__).resolve().parent


def _reaches_set_text(function, seen: set) -> bool:
    """Whether ``function``, or a repository function it calls by name
    (followed transitively through ``cad/scripts`` modules), calls ``SetText``."""
    module = inspect.getmodule(function)
    source_file = getattr(module, "__file__", None)
    if function in seen or source_file is None:
        return False
    if Path(source_file).resolve().parent != _SCRIPTS:
        return False
    seen.add(function)
    source = inspect.getsource(function)
    if "SetText(" in source:
        return True
    for node in ast.walk(ast.parse(textwrap.dedent(source))):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            target = getattr(module, node.func.id, None)
            if inspect.isfunction(target) and _reaches_set_text(target, seen):
                return True
    return False


def test_the_drawing_never_writes_dimension_text() -> None:
    """Text set from the drawing writes through to the built part, so no
    function the draw script defines or imports reaches ``SetText``."""
    seen: set = set()
    writers = sorted(
        name
        for name, value in vars(drawing).items()
        if inspect.isfunction(value) and _reaches_set_text(value, seen)
    )
    assert writers == []


def test_the_write_scan_finds_the_shared_dimension_text_writers() -> None:
    import _drawing_dimensions

    for writer in (
        _drawing_dimensions.set_dimension_callouts,
        _drawing_dimensions.set_reference_dimensions,
    ):
        assert _reaches_set_text(writer, set()), writer.__name__


def test_registry_row_is_mha_081_one_of_each() -> None:
    row = _config.parts("pd-transgear-removable")
    assert row["number"] == "MHA-PD-09"
    assert int(row["quantity"]) == 1
    assert "1 EACH" in row["description"]


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
    at_vendor_thickness = spec.toothed_volume(teeth) - area * (seat_geometry.PLATE - 2.794)
    assert at_vendor_thickness == pytest.approx(vendor_plate_mm3, rel=0.002)
    # Losing either supplied-face chamfer is observable, even with the
    # residual difference between the standard and vendor tooth profiles.
    for missing_faces in (1, 2):
        incomplete = (
            at_vendor_thickness + missing_faces * spec.chamfer_volume(teeth) / 2.0
        )
        assert abs(incomplete - vendor_plate_mm3) > 0.002 * vendor_plate_mm3
