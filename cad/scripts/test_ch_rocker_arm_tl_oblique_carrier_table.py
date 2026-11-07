"""#2151 carrier table and correlated pin-budget contracts (no COM seat)."""
from __future__ import annotations

import ast
import inspect
import itertools
import math
from types import SimpleNamespace

import pytest

import _oblique_carrier_hole_table as table
import ch_rocker_arm_tl_oblique_carrier_spec as spec
import ch_rocker_arm_tl_oblique_jig_assembly_spec as assembly
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import draw_ch_rocker_arm_tl_oblique_carrier as drawing
from _drawing_tables import insert_hole_table

I = trammel.INCH


def test_table_inventory_is_complete_and_replaces_location_dimensions():
    assert len(spec.TABLE_HOLES) == 13
    assert set(spec.TABLE_HOLES) == {
        "A1", "B1", "A2", "B2", "CL", "CR", "HUB",
        "R1", "R2", "R3", "R4", "L1", "L2",
    }
    assert set(table.TAG_OFFSETS) == set(spec.TABLE_HOLES)
    assert set(drawing.TOP_KEEP) == {
        "PlateLength", "PlateWidth", "PlateNearY", "EdgeX", "PinHoleDia",
    }
    assert "A1 ONLY" in inspect.getsource(drawing._pin_section)
    assert "LOCATIONS REF" in spec.TABLE_ROW_NOTES["HUB"]
    assert "station" not in drawing._CHAIN["A1"]
    assert assembly.ALIGNMENT_BAND == pytest.approx(.0008 * I)
    assert "carrier.POSITION_BAND" not in inspect.getsource(assembly)
    assert drawing.MACHINIST_REVIEW.name == "ENFORCE"


def test_owner_pin_only_bounds_and_rounded_budget():
    pin = spec.correlated_pin_budget(include_rounding=False)
    assert max(abs(v) for v in pin["R800"]) / I == pytest.approx(.008833314, abs=1e-8)
    assert .01766 < max(abs(v) for v in pin["R816"]) / I < .0178
    assert .0001 < max(abs(v) for v in pin["inner"]) / I < .0002
    assert .0037 < max(abs(v) for v in pin["outer"]) / I < .0039
    assert spec.PIN_RELATIVE_ERROR == {
        name: max(abs(v) for v in spec.PIN_ROUNDED_BUDGET[name])
        for name in ("inner", "outer")
    }
    # R4: no stud or nose float locates the strap; the in-situ HUB setting
    # stack and each pass's correlated pin error are each counted once.
    for retired in ("PIN_RELATIVE_ALLOWANCE", "HUB_SHANK_RADIAL_FLOAT",
                    "HUB_NOSE_RADIAL_FLOAT", "NOSE_FLOAT_ALLOWANCE",
                    "require_pin_relative_budget", "hub_stud"):
        assert not hasattr(spec, retired), retired
    half = spec._TOP_EDGE_HALF_BAND
    assert half == pytest.approx(.010 * I)
    assert spec.PIN_RELATIVE_STACK == pytest.approx({
        name: spec.HUB_RADIAL_STACK + error for name, error in spec.PIN_RELATIVE_ERROR.items()
    })
    assert spec.PIN_RELATIVE_STACK["inner"] / I == pytest.approx(.005107, abs=2e-6)
    assert spec.PIN_RELATIVE_STACK["outer"] / I == pytest.approx(.008826, abs=2e-6)
    assert spec.PIN_RELATIVE_REMAINING == pytest.approx({
        name: half - stack for name, stack in spec.PIN_RELATIVE_STACK.items()
    })
    assert min(spec.PIN_RELATIVE_REMAINING.values()) > 0
    assert spec.HUB_RADIAL_STACK <= .005 * I


@pytest.mark.parametrize("hub_stack_in,fits", [(.004956, True), (.0061, True), (.0065, False)])
def test_pin_relative_stack_is_functional_in_the_hub_setting(hub_stack_in, fits):
    if fits:
        stack = spec.pin_relative_stack(hub_stack_in * I)
        assert stack["outer"] == pytest.approx(
            hub_stack_in * I + spec.PIN_RELATIVE_ERROR["outer"]
        )
    else:
        with pytest.raises(AssertionError, match="radial band"):
            spec.pin_relative_stack(hub_stack_in * I)
    for bad in (-1e-9, math.inf, math.nan):
        with pytest.raises(ValueError):
            spec.pin_relative_stack(bad)


def _circle(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    h = .5 / math.tan(trammel.ALPHA)
    return ((a[0] + b[0]) / 2 + h * dy,
            (a[1] + b[1]) / 2 - h * dx), math.hypot(dx, dy) / (2 * math.sin(trammel.ALPHA))


def test_enclosure_covers_exact_correlated_circles_and_interior_boxes():
    # Exact circle geometry is independent of the first-order/remainder bound.
    bounds = spec.correlated_pin_budget()
    intervals = spec.pin_coordinate_intervals()
    choices = [(*ends, sum(ends) / 2) for ends in intervals]
    nominal_inner, r1 = _circle((0, 0), (trammel.D1, 0))
    a2 = (trammel.A2[0] - trammel.A1[0], trammel.A2[1])
    b2 = (trammel.B2[0] - trammel.A1[0], trammel.B2[1])
    nominal_outer, r2 = _circle(a2, b2)
    for d, ax, bx, ay, by in itertools.product(*choices):
        ci, ri = _circle((0, 0), (trammel.D1 + d, 0))
        co, ro = _circle((a2[0] + ax, a2[1] + ay), (b2[0] + bx, b2[1] + by))
        hub_shift = (ci[0] - nominal_inner[0], ci[1] + ri - nominal_inner[1] - r1)
        for name, c, r, nominal_c, nominal_r, edge_r in (
            ("inner", ci, ri, nominal_inner, r1, trammel.R_INNER),
            ("outer", co, ro, nominal_outer, r2, trammel.R_OUTER),
        ):
            for fraction in (-1, -.5, 0, .5, 1):
                theta = fraction * trammel.TIP_ANGLE
                p = (nominal_c[0] + edge_r * math.sin(theta) + hub_shift[0],
                     nominal_c[1] + edge_r * math.cos(theta) + hub_shift[1])
                error = math.dist(p, c) - (edge_r + r - nominal_r)
                assert bounds[name][0] - 1e-9 <= error <= bounds[name][1] + 1e-9


def test_local_row_band_is_functional_not_an_unconditional_pass_constant():
    loose = spec.correlated_pin_budget(outer_y_band=.005 * I)
    assert max(abs(v) for v in loose["outer"]) > spec._TOP_EDGE_HALF_BAND - spec.HUB_RADIAL_STACK
    zero = spec.correlated_pin_budget(0, 0, include_rounding=False)
    assert zero["inner"] == pytest.approx((0, 0), abs=1e-9)
    assert zero["outer"] == pytest.approx((0, 0), abs=1e-9)
    for band, row in ((-1, .002 * I), (.005 * I, -1)):
        with pytest.raises(ValueError):
            spec.correlated_pin_budget(band, row)


class NativeCells:
    def __init__(self):
        a1x, a1y = spec.PIN_HOLES["A1"]
        self.cells = [["TAG", "X LOC", "Y LOC", "SIZE", "NOTE"]] + [
            [tag, f"{(x-a1x)/I:.3f}", f"{(y-a1y)/I:.3f}", "native size", spec.TABLE_ROW_NOTES[tag]]
            for tag, (x, y, _dia) in spec.TABLE_HOLES.items()
        ]
        self.RowCount = len(self.cells)
        self.ColumnCount = 5

    def DisplayedText2(self, row, col, _hidden):
        return self.cells[row][col]


# The Hole Wizard cuts the exact inch drill, not _hole_spec's 3-decimal mm
# pin: #29 (.1360) for #8-32, #43 (.0890) for #4-40, F (.2570) for 5/16-18.
# Farm build 26bb read CL at radius 1.7272 mm (.1360 / 2), 2e-7 m off 3.454.
_WIZARD_DRILL_IN = {"CL": .1360, "CR": .1360, "HUB": .1360,
                    **{f"R{i}": .0890 for i in range(1, 5)},
                    **{f"L{i}": .2570 for i in range(1, 3)}}


def _wizard_dia_mm(tag):
    return _WIZARD_DRILL_IN[tag] * I if tag in _WIZARD_DRILL_IN else spec.TABLE_HOLES[tag][2]


_BODY = object()


def _top_circle(x_mm, y_mm, dia_mm, *, top=True):
    curve = SimpleNamespace(IsCircle=lambda: True, CircleParams=(
        x_mm / 1000.0, 0.0 if top else -spec.THICKNESS / 1000.0, -y_mm / 1000.0,
        -0.0, 1.0, -0.0, dia_mm / 2000.0,
    ))
    return SimpleNamespace(GetCurve=lambda: curve, GetBody=lambda: _BODY)


def _census(monkeypatch, tmp_path, edges):
    monkeypatch.setattr(table, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(table, "visible_component_entities", lambda *_args: edges)
    source = tmp_path / "carrier.SLDPRT"
    extension = SimpleNamespace(
        GetUserPreferenceInteger=lambda pref, _option: 3 if pref == 47 else 1,
        GetCorrespondingEntity2=lambda raw: raw,
    )
    model = SimpleNamespace(
        GetPathName=lambda: str(source), GetType=lambda: 1, Extension=extension,
        ConfigurationManager=SimpleNamespace(ActiveConfiguration=SimpleNamespace(Name="Default")),
        GetBodies2=lambda *_args: (_BODY,),
    )
    adapter = SimpleNamespace(
        swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b)),
        currentModel=SimpleNamespace(Extension=extension),
    )
    view = SimpleNamespace(
        ReferencedDocument=model, GetReferencedModelName=lambda: str(source),
        ReferencedConfiguration="Default", GetVisibleComponents=lambda: (object(),),
        GetCorrespondingEntity=lambda edge: edge,
    )
    return table._source_edges(adapter, view, model, source)


def test_pinned_cut_diameters_are_within_their_rounding_of_the_wizard_drills():
    for tag in _WIZARD_DRILL_IN:
        pinned = spec.TABLE_HOLES[tag][2]
        assert pinned != _wizard_dia_mm(tag)
        assert abs(pinned - _wizard_dia_mm(tag)) / 1000.0 <= table.PINNED_DIAMETER_TOLERANCE_M
    sizes = sorted({diameter for *_xy, diameter in spec.TABLE_HOLES.values()})
    assert min(b - a for a, b in itertools.pairwise(sizes)) / 1000.0 > (
        100 * table.PINNED_DIAMETER_TOLERANCE_M
    )


@pytest.mark.parametrize(
    "fault", [None, "extra", "duplicate", "missing", "off_centre", "beyond_rounding", "wrong_size"],
)
def test_source_census_maps_actual_wizard_circles_one_to_one(monkeypatch, tmp_path, fault):
    edges = {
        tag: _top_circle(x, y, _wizard_dia_mm(tag))
        for tag, (x, y, _diameter) in spec.TABLE_HOLES.items()
    }
    raw = [*edges.values(), _top_circle(*spec.CL, _wizard_dia_mm("CL"), top=False)]
    cl_x, cl_y = spec.CL
    if fault == "extra":
        raw.append(_top_circle(cl_x + 5.0, cl_y, _wizard_dia_mm("CL")))
    elif fault == "duplicate":
        raw.append(_top_circle(cl_x, cl_y, _wizard_dia_mm("CL")))
    elif fault == "missing":
        raw.remove(edges["HUB"])
    elif fault == "off_centre":
        raw[raw.index(edges["CL"])] = _top_circle(cl_x + 1e-4, cl_y, _wizard_dia_mm("CL"))
    elif fault == "beyond_rounding":
        raw[raw.index(edges["CL"])] = _top_circle(cl_x, cl_y, spec.CLAMP_TAP_DRILL + 0.002)
    elif fault == "wrong_size":
        raw[raw.index(edges["CL"])] = _top_circle(cl_x, cl_y, _wizard_dia_mm("R1"))
    if fault is None:
        found = _census(monkeypatch, tmp_path, raw)
        assert set(found) == set(spec.TABLE_HOLES)
        assert all(found[tag] is edge for tag, edge in edges.items())
    else:
        with pytest.raises(RuntimeError, match="extra/duplicate/unidentified|missing physical"):
            _census(monkeypatch, tmp_path, raw)


def test_native_rows_require_exact_tag_axis_and_three_places():
    cells = NativeCells()
    assert set(table._rows(cells)) == set(spec.TABLE_HOLES)
    for mutation in ("wrong_axis", "wrong_tag", "duplicate_tag", "precision", "empty_size", "missing"):
        bad = NativeCells()
        if mutation == "wrong_axis":
            bad.cells[2][1] = "17.723"
        elif mutation == "wrong_tag":
            bad.cells[1][0], bad.cells[2][0] = bad.cells[2][0], bad.cells[1][0]
        elif mutation == "duplicate_tag":
            bad.cells[2][0] = bad.cells[1][0]
        elif mutation == "precision":
            bad.cells[2][1] += "0"
        elif mutation == "empty_size":
            bad.cells[2][3] = ""
        else:
            bad.RowCount -= 1
        with pytest.raises(RuntimeError):
            table._rows(bad)


def test_outer_note_reads_actual_model_limits_and_never_writes_them(monkeypatch):
    monkeypatch.setattr(table, "_early_bound", lambda value, _interface: value)
    for shift in (0, .001 * I):
        tolerance = SimpleNamespace(
            Type=2,
            GetMinValue=lambda: (spec.OUTER_Y_DEVIATIONS[0] + shift) / 1000,
            GetMaxValue=lambda: spec.OUTER_Y_DEVIATIONS[1] / 1000,
        )
        model = SimpleNamespace(Parameter=lambda _name: SimpleNamespace(
            SystemValue=spec.A2_DY / 1000, Tolerance=tolerance,
        ))
        if shift:
            with pytest.raises(RuntimeError, match="model|own"):
                table._outer_row_source(model)
        else:
            table._outer_row_source(model)
    source = inspect.getsource(table._outer_row_source)
    assert "SetValues" not in source and "SetPrecision" not in source


def test_native_table_renames_default_tags_and_reattaches_the_real_edge():
    assert "manual_tags" not in inspect.signature(insert_hole_table).parameters
    source = inspect.getsource(table.create_carrier_hole_table)
    assert 'edges["A1"]' in source and "origin.Reattach()" in source
    assert "datum_point=" not in source and "manual_tags" not in source
    # Rename only after the datum is A1 (rows identify by their A1 cells),
    # then rebuild before the generated rows are frozen.
    assert (source.index("origin.Reattach()") < source.index("_assign_tags(feature, table)")
            < source.index('label="carrier owner tags"') < source.index("rows = _rows(table)"))
    assert "cells[:4] != generated[tag]" in source
    assert "GetCorrespondingEntity2" in inspect.getsource(table._source_edges)
    assert "GetAttachedEntities3" in inspect.getsource(table._tags)
    assert "table_settled" in inspect.getsource(drawing.build)


class DefaultTagTable(NativeCells):
    """SolidWorks' default A1..A13 tags in its XY order, rows not in spec order."""

    def __init__(self, *, base=0, refuse=False):
        super().__init__()
        body = self.cells[1:]
        body.reverse()
        xy_order = sorted(spec.TABLE_HOLES, key=lambda tag: spec.TABLE_HOLES[tag][:2])
        for row in body:
            row[0] = f"A{xy_order.index(row[0]) + 1}"
        self.cells[1:] = body
        self.base, self.refuse, self.EnableUpdate, self.writes = base, refuse, True, []

    # IHoleTable.HoleTag/SetHoleTag over the same rows (``base`` 0 or 1).
    def HoleTag(self, index):
        row = index + 1 - self.base
        if not 1 <= row < self.RowCount:
            raise IndexError(index)
        return self.cells[row][0]

    def SetHoleTag(self, index, name):
        assert self.EnableUpdate is False
        self.writes.append(name)
        row = index + 1 - self.base
        held = {cells[0] for i, cells in enumerate(self.cells[1:], 1) if i != row}
        if not self.refuse and name not in held:  # a live duplicate is refused
            self.cells[row][0] = name


@pytest.mark.parametrize("base", [0, 1])
def test_default_tags_are_renamed_two_phase_by_each_rows_a1_cells(base):
    native = DefaultTagTable(base=base)
    assert {cells[0] for cells in native.cells[1:]} >= {"A1", "A2"}  # live collisions
    table._assign_tags(native, native)
    assert native.EnableUpdate is True
    assert set(table._rows(native)) == set(spec.TABLE_HOLES)
    assert len(native.writes) == 2 * len(spec.TABLE_HOLES)
    assert all(name.startswith("TMP") for name in native.writes[:len(spec.TABLE_HOLES)])
    # A single-phase rename would be refused by the live default tags.
    direct = DefaultTagTable(base=base)
    holes = table._row_holes(direct)
    direct.EnableUpdate = False
    for row, tag in holes.items():
        direct.SetHoleTag(row - 1 + base, tag)
    assert {cells[0] for cells in direct.cells[1:]} != set(spec.TABLE_HOLES)


@pytest.mark.parametrize("fault", ["refused", "unreadable", "ambiguous_row", "precision"])
def test_tag_assignment_refuses_unproven_rows_and_writes(monkeypatch, fault):
    native = DefaultTagTable(refuse=fault == "refused")
    if fault == "unreadable":
        monkeypatch.setattr(native, "HoleTag", lambda _index: "A99")
    elif fault == "ambiguous_row":
        native.cells[2][1:3] = native.cells[1][1:3]
    elif fault == "precision":
        native.cells[3][1] += "0"
    with pytest.raises(RuntimeError):
        table._assign_tags(native, native)
    assert native.EnableUpdate is True


@pytest.mark.parametrize("fault", ["wrong_edge", "missing", "duplicate", "orphan", "dangling"])
def test_complete_view_tag_identity_refuses_every_inventory_failure(monkeypatch, fault):
    monkeypatch.setattr(table, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(table, "_point", lambda *_args: (.1, .2))
    edges = {tag: object() for tag in spec.TABLE_HOLES}

    def annotation(tag, edge, dangling=False):
        return SimpleNamespace(
            GetType=lambda: 6,
            GetSpecificAnnotation=lambda: SimpleNamespace(GetText=lambda: tag),
            GetAttachedEntities3=lambda: (edge,),
            IsDangling=lambda: dangling, Visible=1, GetLeaderCount=lambda: 1,
        )

    annotations = [annotation(tag, edge) for tag, edge in edges.items()]
    adapter = SimpleNamespace(swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b)))
    view = SimpleNamespace(GetAnnotations=lambda: annotations)
    table._tags(adapter, view, edges, place=False)
    if fault == "wrong_edge":
        annotations[0] = annotation("A1", edges["B1"])
    elif fault == "missing":
        annotations.pop()
    elif fault == "duplicate":
        annotations.append(annotations[0])
    elif fault == "orphan":
        annotations.append(annotation("Z99", object()))
    else:
        annotations[0] = annotation("A1", edges["A1"], dangling=True)
    with pytest.raises(RuntimeError):
        table._tags(adapter, view, edges, place=False)


def test_table_creation_and_settled_readback_have_operation_spans() -> None:
    source = ast.parse(inspect.getsource(table))
    traced = []
    for function in ast.walk(source):
        if not isinstance(function, ast.FunctionDef):
            continue
        for decorator in function.decorator_list:
            if (
                isinstance(decorator, ast.Call)
                and ast.unparse(decorator.func) == "_telemetry.traced"
            ):
                traced.append((function.name, ast.literal_eval(decorator.args[0])))
    assert sorted(traced) == [
        ("create_carrier_hole_table", "drawing.carrier_hole_table.create"),
        ("settled", "drawing.carrier_hole_table.settled"),
    ]


@pytest.mark.parametrize("failure", [None, "reject", "readback"])
def test_outer_row_authoring_binds_raw_named_dimensions(monkeypatch, failure):
    import _com
    import build_ch_rocker_arm_tl_oblique_carrier as builder

    class RawDispatch:
        def InvokeTypes(self, *_args):
            raise AssertionError("bind the raw dimension before accessing members")

    wrappers = {}
    controls = {}
    selected = []
    for name in ("A2DY", "B2DY"):
        state = {}

        def set_values(lower, upper, state=state):
            state.update(lower=lower, upper=upper)
            return failure != "reject"

        tolerance = SimpleNamespace(
            Type=0, SetValues=set_values,
            GetMinValue=lambda state=state: state["lower"],
            GetMaxValue=lambda state=state: state["upper"] + (
                1e-4 if failure == "readback" else 0.0
            ),
        )
        dimension = SimpleNamespace(
            SystemValue=spec.A2_DY / 1000.0, Tolerance=tolerance,
        )
        raw = RawDispatch()
        assert not hasattr(raw, "_oleobj_") and not hasattr(raw, "Tolerance")
        wrappers[raw] = dimension
        controls[name] = (raw, dimension, state)

    def early_bound(value, interface):
        raw = getattr(value, "_oleobj_", None)
        if raw in wrappers:
            assert interface == "IDimension"
            return wrappers[raw]
        # As in _com._early_bound, a bare raw dispatch passes through.
        # Omitting _bind in the author therefore fails on .Tolerance.
        return value

    def named_dimension(_adapter, feature, name):
        assert feature == "PinHoleProfile"
        selected.append(name)
        return None, controls[name][0]

    monkeypatch.setattr(_com, "_early_bound", early_bound)
    monkeypatch.setattr(builder, "_early_bound", early_bound)
    monkeypatch.setattr(builder, "_named_dimension", named_dimension)
    if failure is not None:
        message = "rejected" if failure == "reject" else "changed"
        with pytest.raises(RuntimeError, match=f"local row limits {message}"):
            builder._author_outer_pin_rows(None)
        return
    builder._author_outer_pin_rows(None)
    assert selected == ["A2DY", "B2DY"]
    for _raw, dimension, state in controls.values():
        assert dimension.SystemValue == spec.A2_DY / 1000.0
        assert dimension.Tolerance.Type == 2
        assert (state["lower"], state["upper"]) == pytest.approx(
            tuple(value / 1000.0 for value in spec.OUTER_Y_DEVIATIONS)
        )
