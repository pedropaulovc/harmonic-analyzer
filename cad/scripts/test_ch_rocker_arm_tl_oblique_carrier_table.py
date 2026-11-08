"""#2151 carrier table and correlated pin-budget contracts (no COM seat)."""
from __future__ import annotations

import ast
import inspect
import itertools
import math
import re
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

import _oblique_carrier_hole_table as table
import ch_rocker_arm_tl_oblique_carrier_spec as spec
import ch_rocker_arm_tl_oblique_jig_assembly_spec as assembly
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import draw_ch_rocker_arm_tl_oblique_carrier as drawing
from _drawing_tables import insert_hole_table

I = trammel.INCH


TABLED = table.TABLED_HOLES


def test_table_inventory_is_complete_and_replaces_location_dimensions():
    assert len(spec.TABLE_HOLES) == 13
    assert set(spec.TABLE_HOLES) == {
        "A1", "B1", "A2", "B2", "CL", "CR", "HUB",
        "R1", "R2", "R3", "R4", "L1", "L2",
    }
    # Farm 82129 review: the in-situ HUB is drilled and tapped at assembly,
    # so it is a physical source hole but never a table row or tag.
    assert table.IN_SITU_HOLES == ("HUB",)
    assert TABLED == {tag: hole for tag, hole in spec.TABLE_HOLES.items() if tag != "HUB"}
    assert len(TABLED) == 12
    assert set(table.TAG_OFFSETS) == set(TABLED)
    assert table.COLUMNS[table.SIZE_COLUMN] == "SIZE"
    assert set(drawing.TOP_KEEP) == {
        "PlateLength", "PlateWidth", "PlateNearY", "EdgeX", "PinHoleDia",
    }
    assert drawing.SECTION_NOTE.startswith("A1 ONLY")
    assert "SECTION_NOTE" in inspect.getsource(drawing._pin_section)
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
    # R4/P1-A: no stud or nose float locates the strap; the in-situ HUB setting
    # stack, correlated pin error and accepted carriage play are counted once.
    for retired in ("PIN_RELATIVE_ALLOWANCE", "HUB_SHANK_RADIAL_FLOAT",
                    "HUB_NOSE_RADIAL_FLOAT", "NOSE_FLOAT_ALLOWANCE",
                    "require_pin_relative_budget", "hub_stud"):
        assert not hasattr(spec, retired), retired
    half = spec._TOP_EDGE_HALF_BAND
    assert half == pytest.approx(.010 * I)
    assert spec.PIN_RELATIVE_STACK == pytest.approx({
        name: spec.HUB_RADIAL_STACK + error + trammel.CARRIAGE_PLAY_RADIUS
        for name, error in spec.PIN_RELATIVE_ERROR.items()
    })
    assert spec.HUB_RADIAL_STACK == pytest.approx(.12588, abs=5e-6)
    assert trammel.RADIUS_FROM_SHOULDER_CLEARANCE == pytest.approx(.11218, abs=5e-6)
    assert spec.PIN_RELATIVE_STACK["inner"] == pytest.approx(.14971, abs=5e-6)
    assert spec.PIN_RELATIVE_STACK["outer"] == pytest.approx(.24419, abs=5e-6)
    assert spec.PIN_RELATIVE_REMAINING == pytest.approx({
        name: half - stack for name, stack in spec.PIN_RELATIVE_STACK.items()
    })
    assert min(spec.PIN_RELATIVE_REMAINING.values()) > 0
    assert spec.HUB_RADIAL_STACK <= .005 * I


@pytest.mark.parametrize("hub_stack_in,fits", [(.004956, True), (.0053, True), (.0061, False), (.0065, False)])
def test_pin_relative_stack_is_functional_in_the_hub_setting(hub_stack_in, fits):
    if fits:
        stack = spec.pin_relative_stack(hub_stack_in * I)
        assert stack["outer"] == pytest.approx(
            hub_stack_in * I + spec.PIN_RELATIVE_ERROR["outer"] + trammel.CARRIAGE_PLAY_RADIUS
        )
    else:
        with pytest.raises(AssertionError, match="radial band"):
            spec.pin_relative_stack(hub_stack_in * I)
    for bad in (-1e-9, math.inf, math.nan):
        with pytest.raises(ValueError):
            spec.pin_relative_stack(bad)


def test_carriage_play_is_charged_once_and_old_acceptance_is_rejected(monkeypatch):
    accepted = spec.pin_relative_stack()
    monkeypatch.setattr(trammel, "CARRIAGE_PLAY_RADIUS", 0.0)
    without_play = spec.pin_relative_stack()
    for name in accepted:
        assert accepted[name] - without_play[name] == pytest.approx(.02)
    # PR #2236 P1: the old .05 acceptance exceeds the unchanged .254 half-band.
    monkeypatch.setattr(trammel, "CARRIAGE_PLAY_RADIUS", .05)
    with pytest.raises(AssertionError, match="radial band"):
        spec.pin_relative_stack()


@pytest.mark.parametrize("pass_name", ["inner", "outer"])
def test_station_cut_and_sweep_consumers_charge_carriage_play_once(monkeypatch, pass_name):
    point = trammel.CL
    cut = spec.station_cut_error(point, pass_name)
    sweep = spec.station_sweep_error(point, pass_name)
    monkeypatch.setattr(trammel, "CARRIAGE_PLAY_RADIUS", 0.0)
    assert cut - spec.station_cut_error(point, pass_name) == pytest.approx(.02)
    assert sweep - spec.station_sweep_error(point, pass_name) == pytest.approx(.02)


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
    assert max(abs(v) for v in loose["outer"]) > (
        spec._TOP_EDGE_HALF_BAND - spec.HUB_RADIAL_STACK - trammel.CARRIAGE_PLAY_RADIUS
    )
    zero = spec.correlated_pin_budget(0, 0, include_rounding=False)
    assert zero["inner"] == pytest.approx((0, 0), abs=1e-9)
    assert zero["outer"] == pytest.approx((0, 0), abs=1e-9)
    for band, row in ((-1, .002 * I), (.005 * I, -1)):
        with pytest.raises(ValueError):
            spec.correlated_pin_budget(band, row)


class NativeCells:
    """A generated hole table: physical rows/columns (``Total*Count``), the
    native ``ColumnHidden``/``SetColumnHidden`` visibility, and
    ``DisplayedText2``'s IncludeHidden index domain: with False, hidden
    columns are skipped, so a reader in the wrong domain gets the wrong cell."""

    def __init__(self):
        a1x, a1y = spec.PIN_HOLES["A1"]
        self.cells = [list(table.COLUMNS)] + [
            [tag, f"{(x-a1x)/I:.3f}", f"{(y-a1y)/I:.3f}", "native size", spec.TABLE_ROW_NOTES[tag]]
            for tag, (x, y, _dia) in TABLED.items()
        ]
        self.TotalRowCount = len(self.cells)
        self.TotalColumnCount = len(table.COLUMNS)
        self.hidden = {}

    def _physical(self, col, include_hidden):
        if include_hidden:
            return col
        return [c for c in range(self.TotalColumnCount) if not self.hidden.get(c, False)][col]

    def DisplayedText2(self, row, col, include_hidden):
        return self.cells[row][self._physical(col, include_hidden)]

    def ColumnHidden(self, col):
        return self.hidden.get(col, False)

    def SetColumnHidden(self, col, hidden):
        self.hidden[col] = hidden

    def RowHidden(self, _row):
        return False


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


def _round_away_a_place(cells):
    """Round a location cell to two places where that CHANGES its value."""
    row, column = next((r, c) for r, row_cells in enumerate(cells[1:], 1)
                       for c in (1, 2) if not row_cells[c].endswith("0"))
    cells[row][column] = cells[row][column][:-1]


def test_native_rows_require_exact_tag_axis_and_values():
    cells = NativeCells()
    assert set(table._rows(cells)) == set(TABLED)
    trailing = NativeCells()
    trailing.cells[2][1] += "0"  # same value: display only, accepted
    assert set(table._rows(trailing)) == set(TABLED)
    for mutation in ("wrong_axis", "wrong_tag", "duplicate_tag", "rounded", "empty_size", "missing"):
        bad = NativeCells()
        if mutation == "wrong_axis":
            bad.cells[2][1] = "17.723"
        elif mutation == "wrong_tag":
            bad.cells[1][0], bad.cells[2][0] = bad.cells[2][0], bad.cells[1][0]
        elif mutation == "duplicate_tag":
            bad.cells[2][0] = bad.cells[1][0]
        elif mutation == "rounded":
            _round_away_a_place(bad.cells)
        elif mutation == "empty_size":
            bad.cells[2][3] = ""
        else:
            bad.TotalRowCount -= 1
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
    # NOTE text goes into each tag's row as re-read AFTER the column rebuild,
    # every void SetText2 put is read back, and settle compares whole rows,
    # all in the physical (IncludeHidden=True) column domain.
    assert (source.index('label="carrier NOTE column"')
            < source.index('_frozen_rows(table, generated, notes=None')
            < source.index("table.SetText2(row, 4, True, note)")
            < source.index("table.Text2(row, 4, True)")
            < source.index('_frozen_rows(table, generated, notes=spec.TABLE_ROW_NOTES'))
    assert "DisplayedText2(row, column, True)" in inspect.getsource(table._cell)
    assert "GetCorrespondingEntity2" in inspect.getsource(table._source_edges)
    assert "GetAttachedEntities3" in inspect.getsource(table._tags)
    assert "table_settled" in inspect.getsource(drawing.build)
    assert "_owned_table(adapter, view, feature, table)" in source
    assert "view.GetTableAnnotations" not in source


def _ownership_fakes(fault):
    """A sheet (root) view, the tagged Top view and one other model view."""
    expected = SimpleNamespace(GetName=lambda: "Hole Table1")
    other = SimpleNamespace(GetName=lambda: "Hole Table2")
    undetermined = SimpleNamespace(GetName=lambda: "Hole Table1")

    def hole_table(annotation, kind=1):
        return SimpleNamespace(Type=kind, GetAnnotation=lambda: annotation)

    native = SimpleNamespace(Name="Hole Table1", GetTypeName2=lambda: "HoleTableFeat")
    feature = SimpleNamespace(
        GetFeature=lambda: native,
        GetTableAnnotations=lambda: [hole_table(undetermined if fault == "undetermined" else expected)],
    )
    subs = [SimpleNamespace(Name="DetailItem1", GetTypeName2=lambda: "DetailItem"), native]
    if fault == "second_feature":
        subs.append(SimpleNamespace(Name="Hole Table2", GetTypeName2=lambda: "HoleTableFeat"))
    for item, following in zip(subs, [*subs[1:], None]):
        item.GetNextSubFeature = lambda following=following: following
    view_feature = SimpleNamespace(GetFirstSubFeature=lambda: subs[0])
    root_tables = [hole_table(expected), hole_table(other, kind=2)]  # BOM-type table ignored
    top_tables = []
    if fault == "view_listed":
        root_tables, top_tables = [hole_table(other, kind=2)], [hole_table(expected)]
    elif fault == "other_hole_table":
        top_tables = [hole_table(other)]
    elif fault == "not_listed":
        root_tables = []
    top = SimpleNamespace(GetName2=lambda: "Drawing View1", GetTableAnnotations=lambda: top_tables)
    side = SimpleNamespace(GetName2=lambda: "Drawing View2", GetTableAnnotations=lambda: [],
                           GetNextView=lambda: None)
    top.GetNextView = lambda: side
    sheet = SimpleNamespace(GetName2=lambda: "Sheet2", GetTableAnnotations=lambda: root_tables,
                            GetNextView=lambda: top)
    names = {"Drawing View1": None if fault == "no_view_feature" else view_feature}

    def is_same(left, right):
        return -1 if undetermined in (left, right) else int(left is right)

    adapter = SimpleNamespace(
        swApp=SimpleNamespace(IsSame=is_same),
        currentModel=SimpleNamespace(FeatureByName=names.get, GetFirstView=lambda: sheet),
    )
    return adapter, top, feature, SimpleNamespace(GetAnnotation=lambda: expected)


@pytest.mark.parametrize("fault", [
    None, "view_listed", "other_hole_table", "not_listed", "second_feature",
    "no_view_feature", "undetermined",
])
def test_table_ownership_is_the_view_feature_and_the_sheets_only_hole_table(monkeypatch, fault):
    monkeypatch.setattr(table, "_early_bound", lambda value, _interface: value)
    adapter, view, feature, inserted = _ownership_fakes(fault)
    if fault in (None, "view_listed"):  # root- or view-listed enumeration both accepted
        table._owned_table(adapter, view, feature, inserted)
        return
    with pytest.raises(RuntimeError, match="exactly this one native table") as failure:
        table._owned_table(adapter, view, feature, inserted)
    message = str(failure.value)
    assert "view='Drawing View1'" in message and "expected='Hole Table1'" in message
    assert "sheet_views=[('Drawing View1', 1), ('Drawing View2', 0)]" in message
    if fault == "other_hole_table":
        assert "('Drawing View1', 'Hole Table2', 0)" in message
    elif fault == "undetermined":
        assert "feature_annotations=[('Hole Table1', -1)]" in message


def test_hole_table_native_calls_are_declared_on_their_bound_interfaces():
    # Farm 114c1622: _early_bound(drawing, "IModelDoc2").FeatureByName raised
    # natively; the adapter census never reads this helper module. Parse the
    # pinned generated typelib as data (no COM, no imports of the wrapper).
    from test_mg_threaded_adapter_contract import _native_declaration, _undeclared_bound_calls

    tree = ast.parse(inspect.getsource(table))
    assert not _undeclared_bound_calls(tree)
    owned = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_owned_table")
    bound = {
        node.targets[0].id: node.value.args[1].value for node in ast.walk(owned)
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name) and node.value.func.id == "_early_bound"
        and isinstance(node.targets[0], ast.Name)
    }
    # Every parameter and document the census follows is explicitly bound.
    assert {name: bound[name] for name in ("view", "feature", "table", "drawing")} == {
        "view": "IView", "feature": "IHoleTable", "table": "ITableAnnotation", "drawing": "IDrawingDoc",
    }
    # Mutation control: the 114c binding is caught by the same census.
    binding = next(
        node.value for node in ast.walk(owned)
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "drawing"
    )
    binding.args[1] = ast.Constant("IModelDoc2")
    assert "IModelDoc2.FeatureByName" in _undeclared_bound_calls(tree)
    # Members reached through comprehension items or property reads, which
    # the named-binding walker does not follow.
    for interface, member in (
        ("IAnnotation", "GetName"), ("ITableAnnotation", "GetAnnotation"),
        ("IHoleTable", "GetFeature"), ("IHoleTable", "GetTableAnnotations"),
        ("IHoleTable", "HoleTag"), ("IHoleTable", "SetHoleTag"),
        ("ITableAnnotation", "Text2"), ("ITableAnnotation", "DisplayedText2"),
        ("ITableAnnotation", "SetText2"), ("IFeature", "GetNextSubFeature"),
        # _hole_table_format dispatches these by name on IModelDocExtension.
        ("IModelDocExtension", "SetUserPreferenceInteger"), ("IModelDocExtension", "GetUserPreferenceInteger"),
        ("IModelDocExtension", "SetUserPreferenceToggle"), ("IModelDocExtension", "GetUserPreferenceToggle"),
        # The hidden SIZE column: indexed BOOL get/put and row visibility.
        ("ITableAnnotation", "ColumnHidden"), ("ITableAnnotation", "SetColumnHidden"),
        ("ITableAnnotation", "RowHidden"),
    ):
        assert member in _native_declaration(interface)[0], f"{interface}.{member}"
    for interface, member in (
        ("ITableAnnotation", "Type"), ("IFeature", "Name"), ("IHoleTable", "EnableUpdate"),
        ("ITableAnnotation", "TotalRowCount"), ("ITableAnnotation", "TotalColumnCount"),
    ):
        assert member in _native_declaration(interface)[1]["_prop_map_get_"], f"{interface}.{member}"


@pytest.mark.parametrize("fault", [None, "integer_rejected", "integer_not_persisted", "dual_stays_on"])
def test_hole_table_format_is_set_and_read_back_on_the_drawing(monkeypatch, fault):
    names = iter(range(100, 200))
    ids = {}
    monkeypatch.setattr(table, "constant", lambda name: ids.setdefault(name, next(names)))
    monkeypatch.setattr(table, "_early_bound", lambda value, _interface: value)
    prefs, calls = {}, []

    def set_integer(pref, option, value):
        calls.append(("Integer", pref, option, value))
        if fault == "integer_rejected":
            return False
        prefs[pref, option] = value + (1 if fault == "integer_not_persisted" else 0)
        return True

    def set_toggle(pref, option, value):
        calls.append(("Toggle", pref, option, value))
        prefs[pref, option] = True if fault == "dual_stays_on" else value
        return prefs[pref, option]  # the resulting state, not a success flag

    extension = SimpleNamespace(
        SetUserPreferenceInteger=set_integer, GetUserPreferenceInteger=lambda p, o: prefs.get((p, o), -1),
        SetUserPreferenceToggle=set_toggle, GetUserPreferenceToggle=lambda p, o: prefs.get((p, o), True),
    )
    adapter = SimpleNamespace(currentModel=SimpleNamespace(Extension=extension))
    if fault is None:
        table._hole_table_format(adapter)
        assert calls == [
            ("Integer", ids["swDetailingLeadingZero"], ids["swDetailingHoleTable"], ids["swLeadingZero_DoNotShow"]),
            ("Integer", ids["swDetailingDimTrailingZero"], ids["swDetailingHoleTable"], ids["swDimShowTrailingZeroes"]),
            ("Toggle", ids["swTableHoleDualDimensionDisplay"], ids["swDetailingNoOptionSpecified"], False),
        ]
    else:
        with pytest.raises(RuntimeError, match="did not take: expected="):
            table._hole_table_format(adapter)
    # Names, never literal ints: constant() resolves them from the seat's
    # installed swconst.tlb at run time (native-only; draw_fr_rocker_arm_support).
    source = inspect.getsource(table.create_carrier_hole_table)
    assert source.index("_hole_table_format(adapter)") < source.index("insert_hole_table(")


@pytest.mark.parametrize("fault", [None, "size", "note", "moved_note", "columns"])
def test_frozen_rows_name_the_row_and_both_values(fault):
    native = NativeCells()
    generated = {tag: cells[:4] for tag, (_row, cells) in table._rows(native).items()}
    if fault == "size":
        native.cells[2][3] = "other size"
    elif fault == "note":
        native.cells[2][4] = ""
    elif fault == "moved_note":
        native.cells[1][4], native.cells[2][4] = native.cells[2][4], native.cells[1][4]
    elif fault == "columns":
        native.TotalColumnCount = 4
    if fault is None:
        rows = table._frozen_rows(native, generated, notes=spec.TABLE_ROW_NOTES, stage="now")
        assert set(rows) == set(TABLED)
        return
    with pytest.raises(RuntimeError) as failure:
        table._frozen_rows(native, generated, notes=spec.TABLE_ROW_NOTES, stage="now")
    message = str(failure.value)
    if fault == "columns":
        assert "has 4 columns now" in message
    else:
        row = 1 if fault == "moved_note" else 2  # rows are checked in table order
        tag = native.cells[row][0]
        assert f"changed now: {tag} (row {row})" in message
        assert "expected=" in message and "actual=" in message
        assert repr(native.cells[row][3 if fault == "size" else 4]) in message


def _strip_leading_zero(text):
    return re.sub(r"^(-?)0\.", r"\1.", text)


def test_location_value_is_the_exact_printed_number():
    zero = {table._location_value(t) for t in (".000", "0.000", "-0.000", "-.000", "00.000", "0", "0.0")}
    assert zero == {0}
    assert table._location_value("0.12") == table._location_value(".120") == table._location_value("0.1200")
    assert table._location_value("-0.181") == table._location_value("-.1810")
    assert table._location_value("-0.181") != table._location_value("0.181")
    assert table._location_value("1.250") != table._location_value("1.251")
    assert table._location_value("0.123") != table._location_value("0.12")  # rounding is a value
    for text in ("", "1,250", "+.181", ".", "-", "1.2.3", "<MOD-DIAM>"):
        with pytest.raises(RuntimeError, match="location is not a number"):
            table._location_value(text)


def _trimmed(text):
    """The same value with every leading/trailing zero dropped (0 -> '0')."""
    return format(Decimal(text).normalize(), "f")


@pytest.mark.parametrize("style", ["leading_zero", "zero_sign"])
@pytest.mark.parametrize("side", ["table", "generated"])
def test_frozen_location_cells_ignore_zero_style_only(side, style):
    # Farm 957501d1: generated '.000' redisplayed as '0.000' after the column insert.
    native = NativeCells()
    assert native.cells[1][:3] == ["A1", "0.000", "0.000"]
    generated = {tag: cells[:4] for tag, (_row, cells) in table._rows(native).items()}
    if style == "leading_zero":
        restyled = {tag: (cells[0], *map(_strip_leading_zero, cells[1:3]), cells[3])
                    for tag, cells in generated.items()}
        assert restyled["A1"][1:3] == (".000", ".000")
    else:
        restyled = {**generated, "A1": ("A1", "-0.000", "-.000", generated["A1"][3])}
    if side == "table":
        for row in native.cells[1:]:
            row[:4] = restyled[row[0]]
    else:
        generated = restyled
    assert set(table._frozen_rows(native, generated, notes=spec.TABLE_ROW_NOTES, stage="now")) \
        == set(TABLED)


@pytest.mark.parametrize("drift", ["last_place", "sign", "rounded"])
def test_frozen_location_cells_still_refuse_real_drift(drift):
    native = NativeCells()
    generated = {tag: cells[:4] for tag, (_row, cells) in table._rows(native).items()}
    b1 = native.cells[2]
    assert b1[0] == "B1" and table._location_value(b1[1]) != 0  # nonzero coordinate
    if drift == "last_place":
        generated["B1"] = ("B1", b1[1][:-1] + str((int(b1[1][-1]) + 1) % 10), *generated["B1"][2:])
        match = "changed now: B1 \\(row 2\\)"
    elif drift == "sign":
        flipped = b1[1][1:] if b1[1].startswith("-") else "-" + b1[1]
        generated["B1"] = ("B1", flipped, *generated["B1"][2:])
        match = "changed now: B1 \\(row 2\\)"
    else:
        # A cell rounded to fewer places that CHANGES its value (.123 -> .12).
        row, column = next((r, c) for r, cells in enumerate(native.cells[1:], 1)
                           for c in (1, 2) if not cells[c].endswith("0"))
        native.cells[row][column] = native.cells[row][column][:-1]
        match = "is not measured from A1"
    with pytest.raises(RuntimeError, match=match):
        table._frozen_rows(native, generated, notes=spec.TABLE_ROW_NOTES, stage="now")


@pytest.mark.parametrize("side", ["table", "generated"])
def test_frozen_location_cells_accept_value_equal_leading_and_trailing_zeros(side):
    # 0 vs .000, 0.12 vs .120: display format, logged, never a refusal.
    native = NativeCells()
    generated = {tag: cells[:4] for tag, (_row, cells) in table._rows(native).items()}
    padded = {tag: (cells[0], *(text + "0" for text in cells[1:3]), cells[3])
              for tag, cells in generated.items()}
    trimmed = {tag: (cells[0], *map(_trimmed, cells[1:3]), cells[3]) for tag, cells in generated.items()}
    assert trimmed["A1"][1:3] == ("0", "0")
    assert any(not cells[c].endswith("0") for cells in trimmed.values() for c in (1, 2))
    for restyled in (padded, trimmed):
        table_cells = NativeCells()
        expected = generated
        if side == "table":
            for row in table_cells.cells[1:]:
                row[:4] = restyled[row[0]]
        else:
            expected = restyled
        assert set(table._frozen_rows(table_cells, expected, notes=spec.TABLE_ROW_NOTES, stage="now")) \
            == set(TABLED)
        assert set(table._row_holes(table_cells).values()) == set(TABLED)


# A1's generated SIZE as two farm runs actually serialized it.
_SIZE_957_PLAIN = "<MOD-DIAM>.38<HOLE-DEPTH>.46"  # 957501d1, before and after NOTE
_SIZE_A754_BEFORE = (
    "<MOD-DIAM>.38 <STACK divider=DIM valign=BOTTOM>+<OVER>+</STACK>"
    "<STACK divider=DIM valign=BOTTOM halign=LEFT>.00<OVER>.00</STACK><HOLE-DEPTH>.46"
)
_SIZE_A754_AFTER = "<MOD-DIAM>.38<STACK divider=no>+ .00<OVER>- .00</STACK><HOLE-DEPTH>.46"


def test_size_semantics_compare_printed_values_not_serialization():
    plain = table._size_semantics("A1", _SIZE_957_PLAIN)
    assert plain == ("<MOD-DIAM>", Decimal(".38"), "<HOLE-DEPTH>", Decimal(".46"))
    # Leading/trailing zeros and whitespace are format: one value.
    for same in ("<MOD-DIAM>0.38 <HOLE-DEPTH> .46", "<MOD-DIAM>.380<HOLE-DEPTH>.460"):
        assert table._size_semantics("A1", same) == plain, same
    for changed in (
        "<MOD-DIAM>.4<HOLE-DEPTH>.46",  # another value at fewer places
        "<MOD-DIAM>.39<HOLE-DEPTH>.46",  # another size
        "<MOD-DIAM>.38<HOLE-DEPTH>.47",  # another depth
        ".38<HOLE-DEPTH>.46",  # no diameter symbol
        "<MOD-DIAM>.38 THRU",  # another form
    ):
        assert table._size_semantics("A1", changed) != plain, changed
    # Both a7547069 zero-band serializations ARE the plain size: accepted.
    for stacked in (_SIZE_A754_BEFORE, _SIZE_A754_AFTER):
        assert table._size_semantics("A1", stacked) == plain, stacked
    # A nonzero band is data: kept, and any changed value differs.
    band = "<MOD-DIAM>.376<STACK divider=no>+ .0015<OVER>+ .0010</STACK><HOLE-DEPTH>.46"
    split = ("<MOD-DIAM>.376 <STACK divider=DIM>+<OVER>+</STACK>"
             "<STACK divider=DIM halign=LEFT>.0015<OVER>.0010</STACK><HOLE-DEPTH>.46")
    kept = table._size_semantics("A1", band)
    assert kept == table._size_semantics("A1", split)
    assert ("TOL", Decimal(".0015"), Decimal(".0010")) in kept
    for changed in (
        band.replace("+ .0010", "- .0010"),  # nonzero sign flip
        band.replace(".0015", ".0016"),  # value
        band.replace(".0015", ".002"),  # value at fewer places
        "<MOD-DIAM>.376<HOLE-DEPTH>.46",  # band dropped
    ):
        assert table._size_semantics("A1", changed) != kept, changed
    # A stack of another shape is kept as data, not refused.
    odd = table._size_semantics("A1", "<MOD-DIAM>.38<STACK>H7</STACK>")
    assert ("STACK", "<STACK>H7</STACK>") in odd and odd != plain
    with pytest.raises(RuntimeError, match="A1 has no native SIZE"):
        table._size_semantics("A1", "")


@pytest.mark.parametrize("generated_size,actual_size", [
    (_SIZE_957_PLAIN, _SIZE_957_PLAIN),  # 957501d1 (with the '.000' -> '0.000' flip)
    (_SIZE_A754_BEFORE, _SIZE_A754_AFTER),  # a7547069 (with the '0.000' -> '.000' flip)
    (_SIZE_957_PLAIN, _SIZE_A754_AFTER),  # zero band appears
    (_SIZE_A754_BEFORE, _SIZE_957_PLAIN),  # zero band disappears
])
def test_observed_size_serializations_pass_and_real_changes_still_fail(generated_size, actual_size):
    native = NativeCells()
    native.cells[1][3] = generated_size
    generated = {tag: cells[:4] for tag, (_row, cells) in table._rows(native).items()}
    # Each run's observed location style flip across the NOTE column.
    before, after = (".000", "0.000") if generated_size == _SIZE_957_PLAIN else ("0.000", ".000")
    generated["A1"] = ("A1", before, before, generated_size)
    native.cells[1][1:4] = [after, after, actual_size]
    assert set(table._frozen_rows(native, generated, notes=spec.TABLE_ROW_NOTES, stage="now")) \
        == set(TABLED)
    # Real changes on the same row still fail: size, depth, coordinate, note,
    # another hole's identity, and a missing row.
    for mutate, match in (
        (lambda cells: cells[1].__setitem__(3, actual_size.replace(".38", ".39")), r"changed now: A1 \(row 1\)"),
        (lambda cells: cells[1].__setitem__(3, actual_size.replace(".46", ".47")), r"changed now: A1 \(row 1\)"),
        (lambda cells: cells[1].__setitem__(4, spec.TABLE_ROW_NOTES["B1"]), r"changed now: A1 \(row 1\)"),
        (lambda cells: cells[2].__setitem__(1, "1.000"), "not measured from A1"),
        (lambda cells: cells[2].__setitem__(0, "A1"), "extra/duplicate"),
    ):
        bad = NativeCells()
        bad.cells[1][3] = actual_size
        mutate(bad.cells)
        with pytest.raises(RuntimeError, match=match):
            table._frozen_rows(bad, generated, notes=spec.TABLE_ROW_NOTES, stage="now")
    missing = NativeCells()
    missing.TotalRowCount -= 1
    with pytest.raises(RuntimeError, match="row/column inventory"):
        table._frozen_rows(missing, generated, notes=spec.TABLE_ROW_NOTES, stage="now")


def test_freshly_inserted_note_cells_must_be_empty_before_writing():
    native = NativeCells()
    generated = {tag: cells[:4] for tag, (_row, cells) in table._rows(native).items()}
    with pytest.raises(RuntimeError, match="expected=.*actual="):
        table._frozen_rows(native, generated, notes=None, stage="after the NOTE column")
    for row in native.cells[1:]:
        row[4] = ""
    assert set(table._frozen_rows(native, generated, notes=None, stage="x")) == set(TABLED)


class DefaultTagTable(NativeCells):
    """SolidWorks' default A1..A13 tags in its XY order, rows not in spec order."""

    def __init__(self, *, base=0, refuse=False):
        super().__init__()
        body = self.cells[1:]
        body.reverse()
        xy_order = sorted(TABLED, key=lambda tag: TABLED[tag][:2])
        for row in body:
            row[0] = f"A{xy_order.index(row[0]) + 1}"
        self.cells[1:] = body
        self.base, self.refuse, self.EnableUpdate, self.writes = base, refuse, True, []

    # IHoleTable.HoleTag/SetHoleTag over the same rows (``base`` 0 or 1).
    def HoleTag(self, index):
        row = index + 1 - self.base
        if not 1 <= row < self.TotalRowCount:
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
    assert set(table._rows(native)) == set(TABLED)
    assert len(native.writes) == 2 * len(TABLED)
    assert all(name.startswith("TMP") for name in native.writes[:len(TABLED)])
    # A single-phase rename would be refused by the live default tags.
    # Compare per row against the captured pre-state: a refused A1/A2 swap
    # leaves the same SET of names, just on the wrong holes.
    direct = DefaultTagTable(base=base)
    holes = table._row_holes(direct)
    before = {row: direct.cells[row][0] for row in holes}
    direct.EnableUpdate = False
    for row, tag in holes.items():
        direct.SetHoleTag(row - 1 + base, tag)
    after = {row: direct.cells[row][0] for row in holes}
    refused = {row for row, tag in holes.items() if after[row] != tag}
    assert refused, (before, after)
    assert all(after[row] == before[row] for row in refused), (before, after)
    with pytest.raises(RuntimeError, match="not measured from A1|extra/duplicate"):
        table._rows(direct)


@pytest.mark.parametrize("fault", ["refused", "unreadable", "ambiguous_row", "rounded"])
def test_tag_assignment_refuses_unproven_rows_and_writes(monkeypatch, fault):
    native = DefaultTagTable(refuse=fault == "refused")
    if fault == "unreadable":
        monkeypatch.setattr(native, "HoleTag", lambda _index: "A99")
    elif fault == "ambiguous_row":
        native.cells[2][1:3] = native.cells[1][1:3]
    elif fault == "rounded":
        _round_away_a_place(native.cells)
    with pytest.raises(RuntimeError):
        table._assign_tags(native, native)
    assert native.EnableUpdate is True


@pytest.mark.parametrize("fault", ["wrong_edge", "missing", "duplicate", "orphan", "hub_tag", "dangling"])
def test_complete_view_tag_identity_refuses_every_inventory_failure(monkeypatch, fault):
    monkeypatch.setattr(table, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(table, "_point", lambda *_args: (.1, .2))
    edges = {tag: object() for tag in TABLED}

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
    elif fault == "hub_tag":  # the in-situ HUB is never tagged on the table sheet
        annotations.append(annotation("HUB", object()))
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
        ("_owned_table", "drawing.carrier_hole_table.ownership"),
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


# Each hidden model driver the R4 sheet no longer imports -> the native table
# (row, axis) cells that print the location it drives (axis 0 = X LOC from A1,
# 1 = Y LOC from the A1-B1 line). Build: _PIN_AXIS_DRIVES, _origin_x
# baselines from A1, SharedCoordinate(0/2) for the R2/R4 Y, LeverX on both
# lever taps. A2DY/B2DY additionally own the flagged OUTER_Y_NOTE limits.
TABLE_SUPERSEDED_DRIVERS = {
    "PinSpacing": (("B1", 0),),
    "A2DX": (("A2", 0),), "A2DY": (("A2", 1),),
    "B2DX": (("B2", 0),), "B2DY": (("B2", 1),),
    "ClX": (("CL", 0),), "ClY": (("CL", 1),),
    "CrX": (("CR", 0),), "CrY": (("CR", 1),),
    "LeverX": (("L1", 0), ("L2", 0)), "LeverY1": (("L1", 1),), "LeverY2": (("L2", 1),),
    "RiserX1": (("R1", 0),), "RiserX1R": (("R2", 0),),
    "RiserX2": (("R3", 0),), "RiserX2R": (("R4", 0),),
    "RiserY1": (("R1", 1), ("R2", 1)), "RiserY2": (("R3", 1), ("R4", 1)),
}


def _imported(monkeypatch, places_by_name):
    """Contract-faithful fakes for the production assert_imported_precision:
    IAnnotation -> IDisplayDimension.GetPrimaryPrecision2, named by the
    patched dimension_name (native naming is not exercised here)."""
    import _drawing_dimensions
    from solidworks_mcp.adapters import sw_type_info

    monkeypatch.setattr(sw_type_info, "early_bound_or_flag", lambda native, *_names: native)
    monkeypatch.setattr(_drawing_dimensions, "dimension_name", lambda _adapter, item: item.name)
    annotations = [
        SimpleNamespace(
            name=name,
            GetSpecificAnnotation=lambda places=places: SimpleNamespace(GetPrimaryPrecision2=lambda: places),
        )
        for name, places in places_by_name.items()
    ]
    return _drawing_dimensions, SimpleNamespace(_attempt=lambda fn: fn()), annotations


def test_imported_precision_contract_is_exactly_what_the_sheet_imports():
    imported = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.IMPORTED_PRECISION) == imported
    assert imported == set(drawing.TOP_KEEP) | set(drawing.SECTION_KEEP_MODEL_MM)
    assert all(drawing.IMPORTED_PRECISION[name] == spec.DRAWING_PRECISION_BY_NAME[name] for name in imported)
    source = inspect.getsource(drawing.build)
    assert "assert_imported_precision(adapter, annotations, IMPORTED_PRECISION)" in source
    assert "DRAWING_PRECISION_BY_NAME)" not in source


@pytest.mark.parametrize("defect", [None, "legacy_contract", "missing", "wrong_places"])
def test_production_precision_guard_takes_the_imported_set_and_refuses_defects(monkeypatch, defect):
    module, adapter, annotations = _imported(monkeypatch, dict(drawing.IMPORTED_PRECISION))
    precision = dict(drawing.IMPORTED_PRECISION)
    if defect is None:
        module.assert_imported_precision(adapter, annotations, precision)
        return
    if defect == "legacy_contract":  # farm 1608aaf0: the whole part map
        precision = dict(spec.DRAWING_PRECISION_BY_NAME)
        match = re.escape(repr(sorted(TABLE_SUPERSEDED_DRIVERS)))
    elif defect == "missing":
        annotations = [item for item in annotations if item.name != "EdgeX"]
        match = re.escape("['EdgeX']")
    else:
        _module, _adapter, annotations = _imported(
            monkeypatch, {**drawing.IMPORTED_PRECISION, "PinHoleDia": drawing.IMPORTED_PRECISION["PinHoleDia"] - 1},
        )
        match = "'PinHoleDia' prints 3 decimal places, but its part authored 4"
    with pytest.raises(RuntimeError, match=match):
        module.assert_imported_precision(adapter, annotations, precision)


def test_every_superseded_driver_prints_in_the_native_table_at_its_places():
    superseded = set(spec.DRAWING_PRECISION_BY_NAME) - set(drawing.IMPORTED_PRECISION)
    assert superseded == set(TABLE_SUPERSEDED_DRIVERS)
    assert all(spec.DRAWING_PRECISION_BY_NAME[name] == spec.TABLE_LOCATION_PLACES for name in superseded)
    assert spec.RISER_STATION_PLACES == spec.TABLE_LOCATION_PLACES
    covered = {cell for cells in TABLE_SUPERSEDED_DRIVERS.values() for cell in cells}
    # Complete: every tabled location cell but A1 (the origin) and B1's Y (the
    # A1-B1 line itself). The HUB is not tabled (drilled at assembly).
    expected = {(tag, axis) for tag in TABLED for axis in (0, 1)} - {
        ("A1", 0), ("A1", 1), ("B1", 1),
    }
    assert covered == expected
    assert spec.PIN_HOLES["A1"][1] == spec.PIN_HOLES["B1"][1]
    assert not {"HubX", "HubY"} & set(spec.DRAWING_PRECISION_BY_NAME)
    # A driver shared by two rows drives one coordinate they share.
    for cells in TABLE_SUPERSEDED_DRIVERS.values():
        assert len({spec.TABLE_HOLES[tag][axis] for tag, axis in cells}) == 1, cells
    # The production row guard reads every covered cell at its .XXX value ...
    native = NativeCells()
    rows = table._rows(native)
    for tag, axis in covered:
        assert re.fullmatch(r"-?\d*\.\d{3}", rows[tag][1][1 + axis]), (tag, axis)
    # ... and refuses any of them rounded to a different value; a dropped
    # trailing zero is the same value (display, logged, not refused).
    for tag, axis in sorted(covered):
        bad = NativeCells()
        row = next(i for i, cells in enumerate(bad.cells) if cells[0] == tag)
        text = bad.cells[row][1 + axis]
        bad.cells[row][1 + axis] = text[:-1]
        if text.endswith("0"):
            assert tag in table._rows(bad)
        else:
            with pytest.raises(RuntimeError, match=f"{tag} is not measured from A1"):
                table._rows(bad)
    # A2DY/B2DY's .964 ±.002 is the model-linked flagged note
    # (test_outer_note_reads_actual_model_limits_and_never_writes_them).
    assert spec.inch_text(spec.OUTER_Y_NOMINAL, spec.TABLE_LOCATION_PLACES) in spec.OUTER_Y_NOTE
    assert spec.inch_text(spec.OUTER_Y_BAND, spec.TABLE_LOCATION_PLACES) in spec.OUTER_Y_NOTE
    assert spec.TABLE_ROW_NOTES["A2"].endswith("NOTE 1") and spec.TABLE_ROW_NOTES["B2"].endswith("NOTE 1")


def _settled_harness(monkeypatch, *, fail_check=False):
    """Run the production create_carrier_hole_table and its settled callback
    over a three-sheet fake drawing. Native table content is NOT exercised
    here (patched readers); only which sheet is active when the settled
    readback runs, since _owned_table walks IDrawingDoc.GetFirstView, the
    ACTIVE sheet's root view."""
    sheets, seen = drawing.SHEET_NAMES, []
    state = {"active": drawing.SHEET_NAMES[1], "refuse": set()}

    def activate(name):
        if name not in sheets or name in state["refuse"]:
            return False
        state["active"] = name
        return True

    current = lambda: SimpleNamespace(GetName=lambda: state["active"])  # noqa: E731
    edges = {tag: SimpleNamespace(Select4=lambda *_: True) for tag in spec.TABLE_HOLES}
    inserted, hidden, notes_added = {}, [], []
    annotation = SimpleNamespace(GetAttachedEntities3=lambda: (edges["A1"],), IsDangling=lambda: False)
    origin = SimpleNamespace(Reattach=lambda: True, GetAnnotation=lambda: annotation)
    feature = SimpleNamespace(
        DatumOrigin=origin, CombineSameSize=False, CombineTags=False,
        GetHoleLocationUseDocPrecision=lambda: False,
        GetHoleLocationPrecision=lambda: spec.TABLE_LOCATION_PLACES,
    )
    notes = {}
    # GetColumnWidth indexes visible positions: hidden SIZE is absent.
    visible_widths = [width for column, width in enumerate(table.TABLE_WIDTHS) if column != table.SIZE_COLUMN]
    native = SimpleNamespace(
        HoleTable=feature, TotalRowCount=len(TABLED) + 1, TotalColumnCount=5,
        InsertColumn2=lambda *_: True, SetColumnTitle2=lambda *_: True,
        IsCellTextEditable=lambda *_: True,
        SetText2=lambda row, _col, _hidden, text: notes.__setitem__(row, text),
        Text2=lambda row, *_: notes[row], DisplayedText2=lambda row, *_: notes[row],
        SetColumnWidth=lambda _col, width, _style: width,
        SetColumnHidden=lambda col, state: hidden.append((col, state)),
        GetRowHeight=lambda _row: .005, GetColumnWidth=lambda col: visible_widths[col],
    )
    rows = {tag: (row, (tag, ".000", ".000", "<MOD-DIAM>.38")) for row, tag in enumerate(TABLED, 1)}
    sheet_doc = SimpleNamespace(
        GetCurrentSheet=current, ActivateSheet=activate, ClearSelection2=lambda *_: None,
        SelectionManager=SimpleNamespace(CreateSelectData=lambda: SimpleNamespace()),
    )
    adapter = SimpleNamespace(currentModel=sheet_doc, swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b)))

    def check(*_args, **_kwargs):
        seen.append(state["active"])
        if fail_check and len(seen) > 1:
            raise RuntimeError("settled readback refused")

    for name, value in {
        "_early_bound": lambda value, _interface: value,
        "_source_edges": lambda *_: edges, "_outer_row_source": lambda _model: None,
        "insert_hole_table": lambda *_a, **kw: inserted.update(kw) or native, "_point": lambda *_: None,
        "rebuild_drawing": lambda *_a, **_k: None, "_assign_tags": lambda *_: None,
        "_rows": lambda _table: rows, "_tags": lambda *_a, **_k: None,
        "_frozen_rows": lambda *_a, **_k: rows, "add_note": lambda _adapter, text, *_: notes_added.append(text),
        "add_property_linked_note": lambda *_: SimpleNamespace(GetText=lambda: spec.OUTER_Y_NOTE),
        "_owned_table": check, "_hole_table_format": lambda _adapter: None,
        "_size_column_hidden": lambda *_: None,
    }.items():
        monkeypatch.setattr(table, name, value)
    state.update(edges=edges, inserted=inserted, hidden=hidden, notes=notes_added, widths=visible_widths)
    return state, seen, lambda: table.create_carrier_hole_table(adapter, None, None, Path("carrier.SLDPRT"))


def test_table_selects_only_the_twelve_tabled_holes_and_hides_size(monkeypatch):
    state, _seen, create = _settled_harness(monkeypatch)
    create()
    entities = state["inserted"]["hole_entities"]
    assert len(entities) == len(state["inserted"]["hole_points"]) == 12
    assert state["edges"]["HUB"] not in entities
    assert {id(edge) for edge in entities} == {id(state["edges"][tag]) for tag in TABLED}
    assert state["hidden"] == [(table.SIZE_COLUMN, True)]
    # 43452045 review: the untagged HUB's size is its sheet-3 callout.
    assert table.HOLE_SIZES_NOTE == "HOLE SIZES PER CALLOUTS, SHEETS 1 AND 3"
    assert table.HOLE_SIZES_NOTE in state["notes"]
    assert not any("HUB" in text for text in state["notes"])
    source = inspect.getsource(table.create_carrier_hole_table)
    assert source.index("SetColumnHidden(SIZE_COLUMN, True)") < source.index(
        '_size_column_hidden(table, "after its rebuild")'
    )
    assert '_size_column_hidden(table, "at settled readback")' in source


def test_settled_widths_are_read_in_visible_positions(monkeypatch):
    # Native BOM evidence: GetColumnWidth indexes visible positions. With
    # SIZE hidden, physical-domain reads (0,1,2,4) would run past the end or
    # read NOTE's width as SIZE's; the settled check reads 0..3 and refuses
    # widths that are not TAG/X/Y/NOTE's.
    state, _seen, create = _settled_harness(monkeypatch)
    settled = create()
    state["widths"][3] = table.TABLE_WIDTHS[table.SIZE_COLUMN]  # SIZE still showing
    with pytest.raises(RuntimeError, match="visible column widths"):
        settled()


@pytest.mark.parametrize("fault", [None, "not_hidden", "wrong_column", "not_bool", "row_hidden", "header"])
def test_size_column_hidden_reads_back_only_size_hidden(fault):
    native = NativeCells()
    native.SetColumnHidden(table.SIZE_COLUMN, True)
    # Physical reads (IncludeHidden=True) still see SIZE and NOTE in place;
    # the visible domain would read NOTE where SIZE was.
    assert native.DisplayedText2(1, 3, False) == native.cells[1][4]
    assert set(table._rows(native)) == set(TABLED)
    if fault == "not_hidden":
        native.SetColumnHidden(table.SIZE_COLUMN, False)
    elif fault == "wrong_column":
        native.SetColumnHidden(4, True)
    elif fault == "not_bool":
        native.hidden[table.SIZE_COLUMN] = 1
    elif fault == "row_hidden":
        native.RowHidden = lambda row: row == 2
    elif fault == "header":
        native.cells[0][3] = "DRILL"
    if fault is None:
        table._size_column_hidden(native, "now")
        return
    with pytest.raises(RuntimeError, match="is not SIZE-only hidden"):
        table._size_column_hidden(native, "now")


@pytest.mark.parametrize("before", ["CARRIER", "HUB CLAMP"])
def test_settled_readback_runs_on_the_table_sheet_from_any_later_sheet(monkeypatch, before):
    # Build: create on HOLE TABLE (_hole_table_sheet), then CARRIER, the HUB
    # sheet and back; finalize_drawing reactivates sheet 0, rebuilds and runs
    # settled_checks once BEFORE its one save -- the path has no reopen.
    state, seen, create = _settled_harness(monkeypatch)
    settled = create()
    assert seen == ["HOLE TABLE"] and state["active"] == "HOLE TABLE"
    state["active"] = before
    settled()
    assert seen == ["HOLE TABLE", "HOLE TABLE"] and state["active"] == before
    finalize = inspect.getsource(drawing.finalize_drawing)
    assert (finalize.index("rebuild_drawing(adapter, label=\"finalize_drawing\")")
            < finalize.index("settled()") < finalize.index("save_drawing("))
    build = inspect.getsource(drawing.build)
    assert (build.index("_hole_table_sheet(adapter, source_model)") < build.index("_hub_sheet(adapter)")
            < build.index("settled_checks=(pin_controls_settled, table_settled, hub_settled)"))


@pytest.mark.parametrize("fault", ["refused_table_sheet", "check_fails", "refused_restore"])
def test_settled_readback_never_reads_or_leaves_the_wrong_sheet(monkeypatch, fault):
    state, seen, create = _settled_harness(monkeypatch, fail_check=fault == "check_fails")
    settled = create()
    state["active"] = "HUB CLAMP"
    state["refuse"] = {"refused_table_sheet": {"HOLE TABLE"}, "refused_restore": {"HUB CLAMP"}}.get(fault, set())
    match = {"refused_table_sheet": "cannot be activated", "check_fails": "settled readback refused",
             "refused_restore": "could not restore"}[fault]
    with pytest.raises(RuntimeError, match=match):
        settled()
    if fault == "refused_table_sheet":
        assert seen == ["HOLE TABLE"] and state["active"] == "HUB CLAMP"  # never read elsewhere
    elif fault == "check_fails":
        assert seen[-1] == "HOLE TABLE" and state["active"] == "HUB CLAMP"  # restored in finally
    else:
        assert seen[-1] == "HOLE TABLE"
