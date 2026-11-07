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
    assert len(spec.TABLE_HOLES) == 14
    assert set(spec.TABLE_HOLES) == {
        "A1", "B1", "A2", "B2", "CL", "CR", "LEFT", "HUB",
        "R1", "R2", "R3", "R4", "L1", "L2",
    }
    assert set(table.TAG_OFFSETS) == set(spec.TABLE_HOLES)
    assert set(drawing.TOP_KEEP) == {
        "PlateLength", "PlateWidth", "PlateNearY", "EdgeX", "PinHoleDia", "SpotDia",
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
    assert spec.PIN_RELATIVE_ALLOWANCE == pytest.approx(.005 * I)
    assert spec.PIN_RELATIVE_ERROR == {
        name: max(abs(v) for v in spec.PIN_ROUNDED_BUDGET[name])
        for name in ("inner", "outer")
    }
    assert max(spec.PIN_RELATIVE_ERROR.values()) < spec.PIN_RELATIVE_ALLOWANCE
    assert spec.HUB_RADIAL_STACK <= .005 * I


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
    assert max(abs(v) for v in loose["outer"]) > spec.PIN_RELATIVE_ALLOWANCE
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


def test_native_table_uses_documented_manual_tags_and_real_edge_reattachment():
    signature = inspect.signature(insert_hole_table)
    assert signature.parameters["manual_tags"].default is None
    source = inspect.getsource(table.create_carrier_hole_table)
    assert 'edges["A1"]' in source and "origin.Reattach()" in source
    assert "datum_point=" not in source
    assert "manual_tags=order" in source
    assert "cells[:4] != generated[tag]" in source
    assert "GetCorrespondingEntity2" in inspect.getsource(table._source_edges)
    assert "GetAttachedEntities3" in inspect.getsource(table._tags)
    assert "table_settled" in inspect.getsource(drawing.build)


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
