"""Offline contracts for the MHA-SM-VN-55 counter-anchor jam nut (McMaster 90760A140)."""

from __future__ import annotations

import asyncio
import contextlib
import math
import re
from pathlib import Path

import pytest

import _config
import build_sm_vn_boss_hook_jam_nut as part
import sm_vn_boss_hook_jam_nut_spec as spec
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _test_stock_recipes import discovered_recipes
from diagnostics import diag_build_90760A140 as recipe

STEM = "sm-vn-boss-hook-jam-nut"
SHEET = "sm_vn_boss_hook_jam_nut"
NUMBER = "MHA-SM-VN-55"
STOCK_NAME = "#10-24 Zinc-Plated Steel Narrow-Profile Hex Nut"
BUILD = "build_90760A140"
IN = 25.4


def test_catalogue_row_is_the_registered_mcmaster_part() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,) == ("90760A140",)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"] == STOCK_NAME
    assert stock.material == row["material"] == part.MATERIAL == "Plain Carbon Steel"
    assert row["finish"] == "zinc plated"
    assert row["number"] == NUMBER
    assert row["process"] == "purchased"
    assert int(row["quantity"]) == 1
    metadata = discovered_recipes()[spec.SKU]
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is getattr(recipe, BUILD)
    assert metadata.threaded is False


def test_spec_carries_the_live_catalogue_facts() -> None:
    """McMaster 10-24 narrow-profile hex-nut listing (90760A140 row), read live 2026-10-16."""
    assert spec.THREAD == "#10-24"
    assert spec.ACROSS_FLATS == pytest.approx(5.0 / 16.0 * IN)
    assert spec.THICKNESS == pytest.approx(7.0 / 64.0 * IN)
    # The thread is not modelled: the bore is the #10-24 basic major.
    assert spec.BORE_DIA == pytest.approx(0.190 * IN, abs=0.001)
    assert spec.ACROSS_CORNERS == pytest.approx(
        spec.ACROSS_FLATS / math.cos(math.pi / 6)
    )
    assert spec.MASS_G == pytest.approx(spec.nut_volume() * 7.8e-3)


class _Recorder:
    """A fake SolidWorks that records every call a recipe makes."""

    def __init__(self) -> None:
        self.events: list[tuple] = []

    def log(self, name: str, args=(), kwargs=None) -> None:
        self.events.append((name, tuple(args), dict(kwargs or {})))

    async def create_sketch(self, *args):
        self.log("create_sketch", args)
        return "ok"

    async def exit_sketch(self, *args):
        self.log("exit_sketch", args)
        return "ok"

    async def create_extrusion(self, *args):
        self.log("create_extrusion", args)
        return "ok"


def _record(monkeypatch) -> list[tuple]:
    adapter = _Recorder()

    async def define_circle(_adapter, x, y, radius, label, **kwargs):
        adapter.log("circle", (x, y, radius, label))
        return label

    async def volume_check(_adapter, label, expected, tol):
        adapter.log("volume_check", (label, expected, tol))
        return expected

    @contextlib.contextmanager
    def no_inference(_adapter):
        adapter.log("no_inference_enter")
        yield
        adapter.log("no_inference_exit")

    async def add_line_chain(_adapter, points, close=True):
        adapter.log("lines", (tuple(points),))
        return [f"L{i}" for i in range(len(points))]

    monkeypatch.setattr(recipe, "check", lambda *a, **k: True)
    monkeypatch.setattr(
        recipe, "name_last_feature", lambda _a, name: adapter.log("name", (name,))
    )
    monkeypatch.setattr(recipe, "volume_check", volume_check)
    monkeypatch.setattr(recipe, "define_circle", define_circle)
    monkeypatch.setattr(recipe, "no_sketch_inference", no_inference)
    monkeypatch.setattr(recipe, "add_line_chain", add_line_chain)
    asyncio.run(getattr(recipe, BUILD)(adapter))
    return adapter.events


def test_recipe_is_the_hex_with_a_plain_major_bore(monkeypatch) -> None:
    calls = _record(monkeypatch)
    names = [c[0] for c in calls]
    assert calls[0] == ("create_sketch", ("Top",), {})
    (lines,) = [c[1][0] for c in calls if c[0] == "lines"]
    assert len(lines) == 6
    assert all(
        math.hypot(x, y) == pytest.approx(spec.ACROSS_CORNERS / 2.0) for x, y in lines
    )
    assert max(x for x, _ in lines) - min(x for x, _ in lines) == pytest.approx(
        spec.ACROSS_FLATS
    )
    (circle,) = [c[1] for c in calls if c[0] == "circle"]
    assert circle[:3] == pytest.approx((0.0, 0.0, spec.BORE_DIA / 2.0))
    enter, leave = names.index("no_inference_enter"), names.index("no_inference_exit")
    assert enter < names.index("circle") < leave
    assert names.index("lines") < names.index("exit_sketch")
    (extrude,) = [c for c in calls if c[0] == "create_extrusion"]
    assert extrude[1][0].depth == pytest.approx(spec.THICKNESS)
    assert not extrude[1][0].both_directions
    assert [c[1][0] for c in calls if c[0] == "name"] == ["NutProfile", "NutBody"]
    (volume,) = [c for c in calls if c[0] == "volume_check"]
    hexagon = math.sqrt(3.0) / 2.0 * spec.ACROSS_FLATS**2
    assert volume[1][1] == pytest.approx(
        (hexagon - math.pi / 4.0 * spec.BORE_DIA**2) * spec.THICKNESS
    )


def test_stock_build_turns_the_recipe_axis_onto_part_z(monkeypatch) -> None:
    seen: dict = {}

    async def fake_build(adapter, **kwargs):
        seen.update(kwargs)
        return {}

    monkeypatch.setattr(part, "build_stock_fastener", fake_build)
    asyncio.run(part.build(None))
    (component,) = seen["components"]
    assert component.sku == spec.SKU
    assert component.author is getattr(recipe, BUILD)
    assert component.transform.rotation_radians == pytest.approx(
        (math.pi / 2.0, 0.0, 0.0)
    )
    assert component.transform.translation_mm == (0.0, 0.0, 0.0)
    assert seen["material"] == part.SPEC.material
    assert seen.get("color") is None
    assert seen["screw_axis_planes"] == ("Top Plane", "Right Plane")


def test_standalone_recipe_run_is_catalog_only(monkeypatch, tmp_path) -> None:
    from diagnostics import diag_mcmaster_lib as lib

    assert not hasattr(recipe, "replica_main")
    saved: list[str] = []
    built: list = []

    class _Adapter:
        async def create_part(self):
            return "ok"

        async def save_file(self, path):
            saved.append(path)
            return "ok"

    async def fake_recipe(adapter, truth=None):
        built.append(adapter)

    async def no_views(_adapter, _stem):
        return {}

    async def no_close(_adapter):
        return None

    monkeypatch.setattr(recipe, "check", lambda *a, **k: True)
    monkeypatch.setattr(recipe, BUILD, fake_recipe)
    monkeypatch.setattr(lib, "OUT_DIR", tmp_path)
    monkeypatch.setattr(lib, "assert_seat_sketch_baseline", lambda *a: None)
    monkeypatch.setattr(lib, "mass_properties", lambda _a: {"volume_mm3": 300.0})
    monkeypatch.setattr(lib, "export_views", no_views)
    monkeypatch.setattr(lib, "close_all", no_close)
    adapter = _Adapter()
    artefacts = asyncio.run(recipe.build_catalog(adapter))
    assert built == [adapter]
    assert saved == [str((tmp_path / f"{spec.SKU}-catalog.SLDPRT").resolve())]
    assert artefacts["sldprt"] == str(tmp_path / f"{spec.SKU}-catalog.SLDPRT")


def test_no_vendor_model_is_tracked() -> None:
    root = Path(__file__).resolve().parents[2]
    assert not list(root.glob(f"cad/references/**/{spec.SKU}*.SLDPRT"))


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_sm_vn_boss_hook_jam_nut as drawing

    sheet = DRAWINGS_BY_NAME[SHEET]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
    assert (
        drawing.build.__code__.co_names.count("build_purchased_fastener_drawing") == 1
    )


@pytest.mark.parametrize("stem", [STEM])
def test_installation_note_fits_the_sheet(stem: str) -> None:
    lines = _config.parts(stem)["installation_notes"].splitlines()
    assert len(lines) <= 3
    assert all(len(line) <= 70 for line in lines), lines
    notes = " ".join(lines)
    assert notes == (
        "1 INSTALLATION - ON THE MHA-SM-VN-50 COUNTER ANCHOR, BEARING ON THE "
        "MHA-SM-03 BOSS TOP FACE. HOLD THE EYE CLOCKED AND JAM THIS NUT "
        "AGAINST THE BOSS."
    )
    assert not re.search(r"\d+\.\d|\+/-|±|Ø|MAX|MIN| MM\b", notes)


@pytest.fixture
def boss_installation_native(monkeypatch):
    """Real selection/attachment/ink math; replace only native COM access."""
    from types import SimpleNamespace

    import draw_sm_vn_boss_hook_jam_nut as drawing
    import _drawing_layout_audit as collector
    from _drawing_edges import ViewEdge, ViewEdges
    from test_purchased_fastener_drawing import (
        _KitFlagNativeEdge as Edge,
        _KitFlagNativeNote as NativeNote,
        _KitFlagNativeWrapper as Wrapper,
    )

    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(collector, "_early_bound", lambda value, _kind: value)
    notes_text = _config.parts(STEM)["installation_notes"]
    cells = drawing.fastener_view_cells(
        drawing.view_band_bottom(notes_text, label=STEM)
    )
    _, center, cell = next(row for row in cells if row[0] == "*Right")
    state = SimpleNamespace(
        drawing=drawing, cell=cell, center=center, note=None, projections=[],
        authored=[], inventory_reads=0, repeat_wrappers=False, text_fault=None,
        notes_text=notes_text, Edge=Edge, Wrapper=Wrapper,
    )

    class View:
        def __init__(self, name):
            self.name = name
            self.native_identity = object()
            self.notes = []
            self.refreshes = 0
            self.scans = 0
            self.outline = (
                center[0] - 0.004, center[1] - 0.004,
                center[0] + 0.004, center[1] + 0.004,
            )

        def GetName2(self):
            return self.name

        def GetOutline(self):
            return self.outline

        def UpdateViewDisplayGeometry(self):
            self.refreshes += 1  # Native VT_VOID, not a success boolean.

        def GetNotes(self):
            state.inventory_reads += 1
            rows = [Wrapper(note) for note in self.notes]
            return rows * (2 if state.repeat_wrappers else 1)

    state.right = View("Right")
    state.sheet = View("Sheet")
    state.foreign = View("OtherSheetRight")
    half_af = spec.ACROSS_FLATS / 2000
    half_flat = spec.ACROSS_FLATS * math.tan(math.pi / 6) / 2000
    endpoints = ((half_af, -half_flat, 0.0), (half_af, half_flat, 0.0))
    state.target = Edge(endpoints=endpoints)
    # Same flat at the opposite end, opposite flat, and a trimmed segment
    # that omits the physical midpoint must not masquerade as the z=0 edge.
    state.decoys = [
        Edge(endpoints=tuple((x, y, spec.THICKNESS / 1000) for x, y, z in endpoints)),
        Edge(endpoints=tuple((-x, y, z) for x, y, z in endpoints)),
        Edge(endpoints=((half_af, half_flat / 2, 0.0), endpoints[1])),
    ]
    state.edges = [*state.decoys, state.target]

    def same(first, second):
        return int(
            getattr(first, "native_identity", first)
            is getattr(second, "native_identity", second)
        )

    state.adapter = SimpleNamespace(
        currentModel=SimpleNamespace(
            GetViews=lambda: ((state.foreign,), (state.sheet, state.right))
        ),
        swApp=SimpleNamespace(IsSame=same),
    )

    def scan(view, *, label):
        assert view is state.right
        assert view.refreshes > view.scans, "selection must refresh native geometry"
        view.scans += 1
        return ViewEdges(label, tuple(
            ViewEdge(
                Wrapper(edge),
                tuple(tuple(value * 1000 for value in p) for p in edge.endpoints),
                None, None,
            )
            for edge in state.edges
        ))

    def project(_adapter, view, points, *, label):
        assert view is state.right
        state.projections.append(tuple(points))
        # Synthetic COM projection oracle, not an actual Right orientation:
        # screen X uses model Y and screen Y uses model Z.
        return [(center[0] + y, center[1] + z) for x, y, z in points]

    class Note(NativeNote):
        def GetDisplayData(self):
            if state.text_fault == "unreadable-display":
                return None
            data = super().GetDisplayData()
            # The complete native collector requires all primitive counts,
            # even when an annotation has no such primitive.
            for name in (
                "GetLineCount", "GetArcCount", "GetArrowHeadCount",
                "GetPolyLineCount", "GetPolygonCount", "GetTriangleCount",
                "GetEllipseCount",
            ):
                setattr(data, name, lambda: 0)
            data.GetTextFontAtIndex = lambda _i: "Arial"
            data.GetTextLineSpacingAtIndex = lambda _i: 1.0
            if state.text_fault == "empty-text":
                data.GetTextCount = lambda: 0
            elif state.text_fault == "unreadable-width":
                def refused_width(_i):
                    raise RuntimeError("native width read refused")
                data.GetTextInBoxWidthAtIndex = refused_width
            elif state.text_fault == "nonfinite-position":
                data.GetTextPositionAtIndex = lambda _i: (math.nan, center[1], 0.0)
            return data

    def author(
        adapter, view, *, text, entity, attached_to,
        leader_attach_xy, note_xy, label,
    ):
        assert adapter is state.adapter and view is state.right
        assert entity is attached_to
        assert same(entity, state.target)
        assert text == "1"
        assert leader_attach_xy == pytest.approx(center)
        assert note_xy == pytest.approx((center[0] + 0.012, center[1] + 0.010))
        note = Note(text, view, entity, leader_attach_xy)
        note.annotation.position = (*note_xy, 0.0)
        state.note = note
        state.authored.append(note)
        view.notes.append(note)
        return note

    def add_legend(text=None):
        legend = Note(
            '$PRP:"Installation Notes"', state.sheet, state.target, center,
        )
        legend.resolved_text = notes_text if text is None else text
        state.sheet.notes.append(legend)
        return legend

    def extra_key(view):
        note = Note("1", view, state.target, center)
        view.notes.append(note)
        return note

    state.add_legend = add_legend
    state.extra_key = extra_key
    monkeypatch.setattr(drawing, "scan_view_edges", scan)
    monkeypatch.setattr(drawing, "model_points_in_view", project)
    monkeypatch.setattr(drawing, "add_attached_note", author)
    return state


def test_boss_flag_targets_actual_z0_and_checks_settled_readonly(
    boss_installation_native,
):
    state = boss_installation_native
    settled = state.drawing._installation_flag(state.adapter, state.right)
    assert callable(settled)
    assert state.inventory_reads == 0  # Footer is not authored yet.
    assert state.projections == [((spec.ACROSS_FLATS / 2000, 0.0, 0.0),)]
    state.add_legend(state.notes_text.replace("\n", "\r\n"))
    # Dispatch wrappers can repeat without representing competing notes.
    state.repeat_wrappers = True
    note = state.note
    # A native note extent can include its leader. Only text primitives may
    # determine the 2 mm text/view gap, not that leader-inclusive extent.
    note.extent_includes_leader = True
    before = (
        note.annotation.position, tuple(note.annotation.moves),
        tuple(note.annotation.leader_set_calls), note.GetText(),
        note.PropertyLinkedText, note.GetExtent(),
    )
    settled()
    settled()
    assert len(state.authored) == 1
    assert state.right.scans == state.right.refreshes == 3
    assert before == (
        note.annotation.position, tuple(note.annotation.moves),
        tuple(note.annotation.leader_set_calls), note.GetText(),
        note.PropertyLinkedText, note.GetExtent(),
    )


def test_boss_flag_distinguishes_template_border_zone_from_authored_key(
    boss_installation_native,
):
    state = boss_installation_native
    settled = state.drawing._installation_flag(state.adapter, state.right)
    state.add_legend()
    zone = state.extra_key(state.sheet)
    zone.annotation.OwnerType = 2  # swAnnotationOwner_DrawingTemplate.
    settled()
    # The same visible format zone cannot stand in for the authored flag.
    state.right.notes.remove(state.note)
    with pytest.raises(RuntimeError, match="native_key_count=0, template_key_count=1"):
        settled()


@pytest.mark.parametrize("owner_type", [0, 1])
def test_boss_flag_rejects_competing_key_beside_template_zone(
    boss_installation_native, owner_type,
):
    state = boss_installation_native
    settled = state.drawing._installation_flag(state.adapter, state.right)
    state.add_legend()
    zone = state.extra_key(state.sheet)
    zone.annotation.OwnerType = 2
    duplicate = state.extra_key(state.foreign if owner_type == 0 else state.sheet)
    duplicate.annotation.OwnerType = owner_type
    with pytest.raises(RuntimeError, match="native_key_count=2, template_key_count=1"):
        settled()


@pytest.mark.parametrize("geometry", ["missing", "wrong-end", "trimmed"])
def test_boss_flag_rejects_nonbearing_geometry(boss_installation_native, geometry):
    state = boss_installation_native
    state.edges = {
        "missing": [], "wrong-end": [state.decoys[0]], "trimmed": [state.decoys[2]],
    }[geometry]
    with pytest.raises(RuntimeError):
        state.drawing._installation_flag(state.adapter, state.right)
    assert not state.authored


@pytest.mark.parametrize("fault", [
    "edge-identity", "wrong-owner", "wrong-owner-type", "wrong-text",
    "wrong-property-text", "hidden", "attachment-lost", "attachment-wrong-edge",
    "attachment-wrong-type", "dangling", "missing-leader", "shifted-tip",
    "short-leader", "nonfinite-leader", "leader-outside-cell",
    "text-outside-cell", "extent-outside-cell", "view-gap",
    "unreadable-display", "empty-text", "unreadable-width", "zero-width",
    "negative-width", "nonfinite-width", "zero-height", "nonfinite-height",
    "nonfinite-position", "duplicate-key", "foreign-key", "replaced-key",
    "missing-legend", "changed-legend", "unlinked-legend", "duplicate-legend",
    "duplicate-literal-instruction", "duplicate-unkeyed-instruction",
    "duplicate-template-legend", "duplicate-template-instruction",
])
def test_boss_flag_rejects_settled_native_drift(boss_installation_native, fault):
    state = boss_installation_native
    settled = state.drawing._installation_flag(state.adapter, state.right)
    legend = state.add_legend()
    note, annotation = state.note, state.note.annotation
    if fault == "edge-identity":
        # Coordinates remain identical, but this is a different native edge.
        state.edges[-1] = state.Edge(endpoints=state.target.endpoints)
    elif fault == "wrong-owner":
        annotation.Owner = state.foreign
    elif fault == "wrong-owner-type":
        annotation.OwnerType = 2
    elif fault == "wrong-text":
        note.resolved_text = "2"
    elif fault == "wrong-property-text":
        note.PropertyLinkedText = "2"
    elif fault == "hidden":
        annotation.Visible = 3
    elif fault == "attachment-lost":
        annotation.entities, annotation.entity_count = (), 0
    elif fault == "attachment-wrong-edge":
        annotation.entities = (state.decoys[0],)
    elif fault == "attachment-wrong-type":
        annotation.entity_types = (2,)
    elif fault == "dangling":
        annotation.dangling = True
    elif fault == "missing-leader":
        annotation.leader_count = 0
    elif fault == "shifted-tip":
        x, y, z = annotation.landing
        annotation.landing = (x + 0.002, y, z)
    elif fault == "short-leader":
        annotation.leader_override = annotation.position
    elif fault == "nonfinite-leader":
        annotation.leader_override = (*annotation.position, math.nan, 0.1, 0.0)
    elif fault == "leader-outside-cell":
        # A remote intermediate elbow with the correct final attachment.
        annotation.leader_override = (
            *annotation.position, state.cell[2] + 0.001, state.center[1], 0.0,
            *annotation.landing,
        )
    elif fault == "text-outside-cell":
        # Insertion point remains inside; native ink extends beyond the cell.
        note.width = state.cell[2] - annotation.position[0] + 0.003
        # Keep the independent extent valid: rejection must use native ink,
        # not merely an insertion point or GetExtent.
        x0, y0, x1, y1 = state.right.outline
        note.extent_override = (
            x1 + 0.003, y1 + 0.003, 0.0, x1 + 0.007, y1 + 0.006, 0.0,
        )
    elif fault == "extent-outside-cell":
        note.extent_override = (
            state.cell[0] - 0.001, state.center[1], 0.0,
            state.center[0], state.center[1] + 0.003, 0.0,
        )
    elif fault == "view-gap":
        # Correct attachment, readable ink, and a fully in-cell annotation,
        # but the actual text-to-outline gap is 1 mm, not the required 2 mm.
        x0, y0, x1, y1 = note._text_bounds()
        state.right.outline = (x0 - 0.005, y0, x0 - 0.001, y1)
    elif fault in (
        "unreadable-display", "empty-text", "unreadable-width", "nonfinite-position",
    ):
        state.text_fault = fault
    elif fault in ("zero-width", "negative-width", "nonfinite-width"):
        note.width = {"zero-width": 0.0, "negative-width": -0.001,
                      "nonfinite-width": math.nan}[fault]
    elif fault in ("zero-height", "nonfinite-height"):
        note.height = 0.0 if fault == "zero-height" else math.inf
    elif fault == "duplicate-key":
        state.extra_key(state.right)
    elif fault == "foreign-key":
        state.extra_key(state.foreign)
    elif fault == "replaced-key":
        state.right.notes.remove(note)
        state.extra_key(state.right)
    elif fault == "missing-legend":
        state.sheet.notes.remove(legend)
    elif fault == "changed-legend":
        legend.resolved_text += " CHANGED"
    elif fault == "unlinked-legend":
        legend.PropertyLinkedText = state.notes_text
    elif fault == "duplicate-legend":
        state.add_legend()
    elif fault == "duplicate-literal-instruction":
        duplicate = state.add_legend()
        duplicate.PropertyLinkedText = state.notes_text
    elif fault == "duplicate-unkeyed-instruction":
        duplicate = state.add_legend(state.notes_text.removeprefix("1 "))
        duplicate.PropertyLinkedText = duplicate.resolved_text
    elif fault == "duplicate-template-legend":
        state.add_legend().annotation.OwnerType = 2
    elif fault == "duplicate-template-instruction":
        duplicate = state.add_legend()
        duplicate.PropertyLinkedText = state.notes_text
        duplicate.annotation.OwnerType = 2
    else:
        raise AssertionError(f"unowned boss flag drift: {fault}")
    with pytest.raises(RuntimeError):
        settled()


def test_boss_flag_legend_is_captured_not_reread(
    boss_installation_native, monkeypatch,
):
    state = boss_installation_native
    settled = state.drawing._installation_flag(state.adapter, state.right)
    changed = state.notes_text + " CHANGED"
    state.add_legend(changed)
    monkeypatch.setattr(state.drawing._config, "parts", lambda _stem: {
        "installation_notes": changed,
    })
    with pytest.raises(RuntimeError):
        settled()


def test_boss_supplier_dimension_closure_keeps_both_consumers(
    boss_installation_native, monkeypatch,
):
    state = boss_installation_native
    dimension = {"valid": True}

    def dimensions(_adapter, views, **kwargs):
        assert _adapter is state.adapter
        assert views["*Right"] is state.right
        assert kwargs["thickness_mm"] == spec.THICKNESS

        def settled_dimensions():
            if not dimension["valid"]:
                raise RuntimeError("native supplier dimension changed")

        return settled_dimensions

    monkeypatch.setattr(state.drawing, "add_supplier_nut_dimensions", dimensions)
    settled = state.drawing._supplier_dimensions(
        state.adapter, {"*Right": state.right},
    )
    state.add_legend()
    settled()
    dimension["valid"] = False
    with pytest.raises(RuntimeError, match="native supplier dimension changed"):
        settled()
    dimension["valid"] = True
    state.note.annotation.dangling = True
    with pytest.raises(RuntimeError, match="attachment"):
        settled()
