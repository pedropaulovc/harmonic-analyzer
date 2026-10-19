"""Offline native-value/attachment contracts for supplier chain references."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import _drawing_dimensions as drawing_dimensions
import _drawing_edge_dimensions as edge_dimensions
import _supplier_chain_dimensions as refs
import _supplier_dimensions as supplier_dimensions
import _supplier_chain_stock as stock
from _drawing_edges import ViewEdge, ViewEdges
import draw_vn_chain_inner_link as inner
import draw_vn_chain_outer_link as outer
import draw_vn_chain_connecting_link as connecting
import vn_keeper_chain_spec as chain


class Native:
    def __init__(self, mm):
        self.mm = mm
        self.ends = {1: 3, 2: 3}
        self.Name = chain.CATALOGUE_BEAD_DIMENSION
        self.FullName = f"{self.Name}@SeedProfile@vn-keeper-chain.SLDPRT"
        self.Tolerance = SimpleNamespace(Type=0)

    @property
    def SystemValue(self):
        # Deliberately read-only: no numeric setter can rescue a mismatch.
        return self.mm / 1000.0

    def GetArcEndCondition(self, index):
        return self.ends[index]

    def SetArcEndCondition(self, index, condition):
        self.ends[index] = condition
        return 0


class Annotation:
    def __init__(self, attached):
        self.attached = attached
        self.dangling = False

    def GetAttachedEntities3(self):
        return self.attached

    def GetAttachedEntityTypes(self):
        return [1] * len(self.attached)

    def IsDangling(self):
        return self.dangling

    def GetSpecificAnnotation(self):
        return self.display


class Display:
    ShowDimensionValue = True
    ShowParenthesis = False

    def __init__(self, mm, attached, kind=11):
        self.native = Native(mm)
        self.annotation = Annotation(attached)
        self.annotation.display = self
        self.Type2 = kind
        self.text = {}
        self.override = False
        self.units = None
        self.precision = None

    def GetDimension2(self, _index):
        return self.native

    def GetDimension(self):
        return self.native

    def GetAnnotation(self):
        return self.annotation

    def GetOverride(self):
        return self.override

    def SetUnits2(self, use_doc, unit, fraction, denominator, round_fraction, rounding):
        self.units = (use_doc, unit, fraction, denominator, round_fraction)
        return 0

    def SetPrecision3(self, places, *_) -> int:
        self.precision = places
        return 0

    def SetText(self, slot, text):
        assert slot in (1, 2, 4), "numeric dimension replacement is forbidden"
        self.text[slot] = text

    def GetText(self, slot):
        return self.text.get(slot, "")

    def GetUseDocUnits(self):
        return self.units[0]

    def GetUnits(self):
        return self.units[1]

    def GetFractionBase(self):
        return self.units[2]

    def GetFractionValue(self):
        return self.units[3]

    def GetRoundToFraction(self):
        return self.units[4]

    def GetPrimaryPrecision2(self):
        return self.precision


@pytest.fixture
def native_env(monkeypatch):
    for module in (refs, supplier_dimensions, edge_dimensions, drawing_dimensions):
        monkeypatch.setattr(module, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(
        drawing_dimensions._sw_type_info, "early_bound_or_flag", lambda obj, *_: obj
    )

    class View:
        def GetOutline(self):
            return (0.1, 0.1, 0.16, 0.15)

        def GetName2(self):
            return "Front"

        def GetDisplayDimensionCount(self):
            return 1

        @property
        def ScaleDecimal(self):
            return 4.0  # no setter: annotations may not reduce the fitted scale

    view = View()
    selected = []
    model = SimpleNamespace(
        ClearSelection2=lambda _all: selected.clear(),
        ActivateView=lambda name: name == "Front",
        GraphicsRedraw2=lambda: None,
        SelectionManager=SimpleNamespace(
            CreateSelectData=lambda: SimpleNamespace(),
            GetSelectedObjectCount2=lambda _mark: len(selected),
        ),
        EditRebuild3=lambda: True,
    )
    adapter = SimpleNamespace(
        currentModel=model,
        swApp=SimpleNamespace(IsSame=lambda first, second: int(first is second)),
        _get_attr_or_call=lambda obj, member: getattr(obj, member)(),
    )

    class Edge:
        def Select4(self, append, data):
            assert data.View is view
            if not append:
                selected.clear()
            selected.append(self)
            return True

    def prepare(kind):
        radius = stock.PIN_DIAMETER / 2
        z = stock.CONNECTING_PIN_END if kind == "connecting" else stock.CHAIN_PIN_HALF_LENGTH
        stations = (-stock.PITCH / 2, stock.PITCH / 2) if kind == "connecting" else (stock.PITCH, 2 * stock.PITCH)
        edges = (Edge(), Edge())
        circles = tuple(
            ViewEdge(edge, None, (x, 0.0, z, 0.0, 0.0, 1.0, radius), None)
            for x, edge in zip(stations, edges, strict=True)
        )
        # A tempting wrong circle at the same station must not get selected.
        decoy = ViewEdge(Edge(), None, (0.0, 0.0, z, 0.0, 0.0, 1.0, radius + 0.3), None)
        scan = ViewEdges("Front", (decoy, *circles))
        monkeypatch.setattr(refs, "scan_view_edges", lambda *_args, **_kwargs: scan)
        monkeypatch.setattr(
            refs, "model_points_in_view",
            lambda _adapter, _view, points, **_: [(0.12 + 4 * p[0], 0.12 + 4 * p[1]) for p in points],
        )
        display = Display(refs.SUPPLIER_PITCH_MM, edges)

        def horizontal(x, y, z):
            assert tuple(selected) == edges
            assert y == pytest.approx(0.156) and z == 0.0
            return display

        model.AddHorizontalDimension2 = horizontal
        return SimpleNamespace(display=display, edges=edges, circles=circles, scan=scan)

    return SimpleNamespace(adapter=adapter, model=model, view=view, prepare=prepare)


@pytest.mark.parametrize("kind,places", [("inner", 2), ("outer", 2), ("connecting", 3)])
def test_pitch_uses_exact_native_station_circles(native_env, kind, places):
    env = native_env
    source = env.prepare(kind)
    settled = refs.annotate_chain_pitch(env.adapter, {"free_front": env.view}, kind=kind, precision=places)
    assert env.model.EditRebuild3()
    settled()
    display = source.display
    assert display.native.ends == {1: 1, 2: 1}
    assert display.annotation.attached == source.edges
    assert env.view.ScaleDecimal == 4.0


@pytest.mark.parametrize("defect", ["value", "attachment", "dangling", "type", "override", "after_rebuild", "non_arc", "tolerance"])
def test_pitch_refuses_wrong_native_value_or_reference(native_env, defect):
    env = native_env
    source = env.prepare("outer")
    display = source.display
    if defect == "value":
        display.native.mm = 6.36
    elif defect == "attachment":
        display.annotation.attached = (object(), source.edges[1])
    elif defect == "dangling":
        display.annotation.dangling = True
    elif defect == "type":
        display.Type2 = 3
    elif defect == "override":
        display.override = True
    elif defect == "after_rebuild":
        def rebuild():
            display.native.mm = 6.34
            return True
        env.model.EditRebuild3 = rebuild
    elif defect == "non_arc":
        display.native.ends[2] = 0
    elif defect == "tolerance":
        display.native.Tolerance.Type = 4
    with pytest.raises(RuntimeError):
        settled = refs.annotate_chain_pitch(env.adapter, {"free_front": env.view}, kind="outer", precision=2)
        assert env.model.EditRebuild3()
        settled()


def test_pitch_does_not_substitute_a_nearby_clearance_circle(native_env, monkeypatch):
    env = native_env
    source = env.prepare("inner")
    wrong = ViewEdge(object(), None, (12.7001, 0.0, stock.CHAIN_PIN_HALF_LENGTH, 0.0, 0.0, 1.0, stock.PIN_DIAMETER / 2), None)
    scan = ViewEdges("Front", (source.circles[0], wrong))
    monkeypatch.setattr(refs, "scan_view_edges", lambda *_args, **_kwargs: scan)
    with pytest.raises(RuntimeError, match="no visible circle"):
        refs.annotate_chain_pitch(env.adapter, {"free_front": env.view}, kind="inner", precision=2)


@pytest.mark.parametrize("defect", ["owner", "value", "type", "attachment", "tolerance", "count"])
def test_keeper_bead_rejects_corruption_after_final_rebuild(native_env, monkeypatch, defect):
    env = native_env
    display = Display(chain.BEAD_DIA, (object(),), kind=6)
    monkeypatch.setattr(refs, "curate_view_dimensions", lambda *_args, **_kwargs: [display.annotation])
    settled = refs.annotate_keeper_bead(env.adapter, {"*Front": env.view})
    assert env.model.EditRebuild3()
    if defect == "owner":
        display.native.FullName = f"{chain.CATALOGUE_BEAD_DIMENSION}@WrongSketch@part.SLDPRT"
    elif defect == "value":
        display.native.mm = 2.38
    elif defect == "type":
        display.Type2 = 5
    elif defect == "tolerance":
        display.native.Tolerance.Type = 4
    elif defect == "count":
        env.view.GetDisplayDimensionCount = lambda: 2
    else:
        display.annotation.attached = ()
    with pytest.raises(RuntimeError):
        settled()


@pytest.mark.parametrize("kind,mm", [(5, chain.BEAD_R), (6, 2.38), (6, chain.ROD_DIA)])
def test_keeper_bead_rejects_radius_rounding_and_rod_intersection(native_env, monkeypatch, kind, mm):
    env = native_env
    display = Display(mm, (object(),), kind=kind)
    monkeypatch.setattr(refs, "curate_view_dimensions", lambda *_args, **_kwargs: [display.annotation])
    with pytest.raises(RuntimeError):
        refs.annotate_keeper_bead(env.adapter, {"*Front": env.view})




def test_keeper_source_diameter_retains_exact_catalogue_geometry():
    assert chain.BEAD_DIA == pytest.approx(3.0 / 32.0 * 25.4, abs=1e-12)
    assert chain.BEAD_R * 2.0 == chain.BEAD_DIA
    assert chain.CHAIN_PART_BEADS[0] == (0.0, 0.0, 0.0)




@pytest.mark.parametrize("installed", ["Default", "Simplified"])
def test_stock_callback_restores_the_original_installed_configuration(installed):
    import _chain_link as links

    active = SimpleNamespace(Name=installed)
    model = SimpleNamespace(ConfigurationManager=SimpleNamespace(ActiveConfiguration=active))
    adapter = SimpleNamespace(
        currentModel=model,
        swApp=SimpleNamespace(IsSame=lambda first, second: int(first is second)),
    )

    async def author(target):
        target.currentModel = object()  # scratch author may use another document
        target.currentModel = model
        active.Name = "Supplier-Free"
        active.Name = installed

    asyncio.run(links._run_before_save(adapter, author))
    assert adapter.currentModel is model
    assert active.Name == installed


@pytest.mark.parametrize("defect", ["configuration", "document"])
def test_stock_callback_cannot_change_the_canonical_installed_state(defect):
    import _chain_link as links

    active = SimpleNamespace(Name="Default")
    model = SimpleNamespace(ConfigurationManager=SimpleNamespace(ActiveConfiguration=active))
    adapter = SimpleNamespace(
        currentModel=model,
        swApp=SimpleNamespace(IsSame=lambda first, second: int(first is second)),
    )

    async def author(target):
        if defect == "configuration":
            active.Name = "Supplier-Free"
        else:
            target.currentModel = SimpleNamespace(
                ConfigurationManager=SimpleNamespace(ActiveConfiguration=SimpleNamespace(Name="Default"))
            )

    with pytest.raises(RuntimeError, match="changed the installed document/configuration"):
        asyncio.run(links._run_before_save(adapter, author))


@pytest.mark.parametrize("drawing,kind", [(inner, "inner"), (outer, "outer"), (connecting, "connecting")])
def test_stock_dimensions_reject_corruption_after_final_rebuild(native_env, monkeypatch, drawing, kind):
    env = native_env
    env.prepare(kind)
    connector = kind == "connecting"
    counts = {"free_front": 3, "free_top": 3 if connector else 1,
              "free_right": 0, "installed_iso": 0}
    views = {
        key: SimpleNamespace(GetOutline=env.view.GetOutline,
                             GetDisplayDimensionCount=lambda key=key: counts[key])
        for key in counts
    }
    views["free_front"] = env.view
    env.view.GetDisplayDimensionCount = lambda: counts["free_front"]
    values = {
        stock.PIN_DIMENSION: stock.PIN_DIAMETER,
        stock.ROLLER_DIMENSION: stock.ROLLER_DIAMETER,
        stock.WIDTH_DIMENSION: stock.ROLLER_WIDTH,
        stock.PLATE_DIMENSION: stock.PLATE_THICKNESS,
        stock.LENGTH_DIMENSION: stock.CONNECTING_PIN_LENGTH,
    }
    imported = {}

    def curate(_adapter, _view, **options):
        result = []
        for name in options["keep"]:
            diameter = name in (stock.PIN_DIMENSION, stock.ROLLER_DIMENSION)
            display = Display(values[name], (object(),), kind=6 if diameter else 11)
            display.native.Name = name
            owner = stock.FRONT_FEATURE if diameter else stock.SECTION_FEATURE
            display.native.FullName = f"{name}@{owner}@stock.SLDPRT"
            imported[name] = display
            result.append(display.annotation)
        return result

    monkeypatch.setattr(refs, "curate_view_dimensions", curate)
    monkeypatch.setattr(refs, "dimension_name", lambda _adapter, annotation: annotation.display.native.Name)
    checks = drawing.supplier_dimensions(env.adapter, views)
    assert env.model.EditRebuild3()
    for check in checks:
        check()

    imported[stock.PIN_DIMENSION].native.FullName = "SupplierPinDiameter@WrongSketch@stock.SLDPRT"
    with pytest.raises(RuntimeError, match="lost its source section"):
        checks[0]()
    imported[stock.PIN_DIMENSION].native.FullName = f"{stock.PIN_DIMENSION}@{stock.FRONT_FEATURE}@stock.SLDPRT"
    imported[stock.PIN_DIMENSION].native.Tolerance.Type = 4
    with pytest.raises(RuntimeError, match="unprovided supplier tolerance"):
        checks[0]()
    imported[stock.PIN_DIMENSION].native.Tolerance.Type = 0
    imported[stock.PIN_DIMENSION].native.mm = 0.091 * 25.4
    with pytest.raises(RuntimeError, match="exact expected"):
        checks[0]()
    imported[stock.PIN_DIMENSION].native.mm = stock.PIN_DIAMETER
    counts["installed_iso"] = 1
    with pytest.raises(RuntimeError, match="reference count"):
        checks[-1]()


def test_source_stock_profiles_close_without_replacing_installed_geometry():
    from diagnostics.sketch_profile import arc_radii_mm, closed_loops, endpoint_merges
    import _chain

    for profile in (
        stock.plate_profile(inner=True, center_x=stock.PITCH / 2),
        stock.plate_profile(inner=False, center_x=1.5 * stock.PITCH),
        stock.connecting_fixed_plate_profile(), stock.clip_profile(),
    ):
        endpoint_merges(profile)
        assert len(closed_loops(profile)) == 1
        for segment in profile:
            if isinstance(segment, stock.Arc):
                start_radius, end_radius = arc_radii_mm(segment)
                assert start_radius == pytest.approx(end_radius, abs=1e-12)
    assert stock.PIN_DIAMETER != 2 * _chain.PIN_R
    assert stock.ROLLER_DIAMETER != 2 * _chain.ROLLER_R
    assert stock.PLATE_THICKNESS != _chain.PLATE_THICK




def test_nominal_physical_section_requires_the_actual_native_stock_circle(monkeypatch):
    curve = SimpleNamespace(IsCircle=lambda: True, CircleParams=(0.0127, 0.0, 0.00381, 0.0, 0.0, 1.0, 0.00114935))
    body = SimpleNamespace(GetEdges=lambda: (SimpleNamespace(GetCurve=lambda: curve),))
    model = SimpleNamespace(GetBodies2=lambda *_: (body,))
    adapter = SimpleNamespace(currentModel=model)
    monkeypatch.setattr(stock, "_early_bound", lambda obj, _interface: obj)
    stock._require_circle(adapter, (12.7, 0.0, 3.81), stock.PIN_DIAMETER / 2)
    with pytest.raises(RuntimeError, match="no physical circle"):
        stock._require_circle(adapter, (12.7, 0.0, 3.81), 0.091 * 25.4 / 2)




def test_connector_clip_profile_matches_independent_supplier_step_volume():
    """Source STEP solid 2 has no omitted cosmetic blends: its wire is exact."""
    import math
    from diagnostics.sketch_profile import arc_sweep_deg

    pending = list(stock.clip_profile())
    start = cursor = pending[0].start
    integral = 0.0
    while pending:
        index = next(index for index, segment in enumerate(pending)
                     if cursor in (segment.start, segment.end))
        segment = pending.pop(index)
        forward = cursor == segment.start
        end = segment.end if forward else segment.start
        if isinstance(segment, stock.Line):
            integral += cursor[0] * end[1] - end[0] * cursor[1]
        else:
            cx, cy = segment.center
            radius = math.dist(segment.center, segment.start)
            sweep = math.radians(arc_sweep_deg(segment)) * (1 if forward else -1)
            integral += cx * (end[1] - cursor[1]) - cy * (end[0] - cursor[0]) + radius**2 * sweep
        cursor = end
    assert cursor == start
    volume = abs(integral) / 2 * (stock.CLIP_END - stock.CLIP_START)
    # Independent FreeCAD measurement of 6261K108-supplier.STEP, not a copied
    # recipe coefficient. The out-tree audit identifies the immutable source.
    assert volume == pytest.approx(19.064258529439446, abs=1e-8)
