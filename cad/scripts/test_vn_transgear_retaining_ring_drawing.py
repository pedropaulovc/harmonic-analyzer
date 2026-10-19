"""Offline contracts for the MHA-VN-047 transgear retaining ring (McMaster 97431A260)."""

from __future__ import annotations

import asyncio
import json
import math
import re
from pathlib import Path

import pytest

import _config
import build_vn_transgear_retaining_ring as part
import vn_transgear_retaining_ring_spec as spec
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _test_stock_recipes import discovered_recipes
from diagnostics import diag_build_97431A260 as recipe

STEM = "vn-transgear-retaining-ring"
DUMP = Path(__file__).resolve().parents[1] / "out/reports/mcmaster-97431A260-dump.json"


def test_catalogue_row_is_the_replica_gated_mcmaster_ring() -> None:
    from diagnostics.diag_build_mcmaster import REGISTRY

    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"]
    assert stock.material == row["material"]
    assert row["number"] == "MHA-VN-047"
    assert int(row["quantity"]) == 1
    metadata = discovered_recipes()[spec.SKU]
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is recipe.build_97431A260
    assert metadata.threaded is False
    assert REGISTRY[spec.SKU] is recipe.build_97431A260


def test_outline_is_one_closed_loop_on_the_catalogue_circles() -> None:
    segments = recipe.outline()
    ends = [p for s in segments for p in (s.start, s.end)]
    for point in set(ends):
        assert ends.count(point) == 2, point  # every corner joins two segments
    radii = {
        round(math.hypot(*s.start), 6) for s in segments if type(s).__name__ == "Arc"
    }
    assert round(spec.OD / 2.0, 6) in radii
    assert round(spec.FREE_DIA / 2.0, 6) in radii
    assert max(math.hypot(*p) for p in ends) == pytest.approx(spec.OD / 2.0)
    assert min(math.hypot(*p) for p in ends) == pytest.approx(spec.FREE_DIA / 2.0)


def test_outline_extruded_is_the_vendor_volume_before_its_fillets() -> None:
    """The fillets only trade a few thousandths of a mm^3; a wrong corner or a
    reversed arc moves the extrude by tenths."""
    prism = recipe.outline_area() * spec.THICKNESS
    assert prism == pytest.approx(recipe.VENDOR_VOLUME_MM3, abs=0.01)


def test_gap_opens_toward_plus_x() -> None:
    """The O.D. arc runs the long way round the back (-X): the open side, the
    one pushed over the groove, faces +X as the spec's part frame states."""
    (od,) = [
        s
        for s in recipe.outline()
        if type(s).__name__ == "Arc"
        and math.isclose(math.hypot(*s.start), spec.OD / 2.0)
    ]
    assert od.start[0] > 0.0 and od.end[0] > 0.0
    # Counter-clockwise from start to end passes through 180 deg, not 0 deg.
    start = math.atan2(od.start[1], od.start[0]) % (2.0 * math.pi)
    end = math.atan2(od.end[1], od.end[0]) % (2.0 * math.pi)
    assert start < math.pi < end


def _rx(angle: float, point: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = point
    c, s = math.cos(angle), math.sin(angle)
    return (x, y * c - z * s, y * s + z * c)


def test_part_puts_the_rear_face_on_the_front_plane(monkeypatch) -> None:
    """The assembly seats the part's z = 0 face at the ring's rear station and
    lays it THICKNESS forward, so the recipe's mid-thickness body about +Y must
    land on 0 <= z <= THICKNESS whichever way the quarter turn runs."""
    seen: dict = {}

    async def fake_build(adapter, **kwargs):
        seen.update(kwargs)
        return {}

    monkeypatch.setattr(part, "build_stock_fastener", fake_build)
    asyncio.run(part.build(None))
    (component,) = seen["components"]
    assert component.sku == spec.SKU
    assert not component.parameters
    assert seen["material"] == part.SPEC.material
    rx, ry, rz = component.transform.rotation_radians
    assert ry == rz == 0.0
    tz = component.transform.translation_mm
    for sign in (-1.0, 1.0):
        face = _rx(rx, (0.0, sign * spec.THICKNESS / 2.0, 0.0))
        moved = tuple(a + b for a, b in zip(face, tz, strict=True))
        assert moved[0] == pytest.approx(0.0) and moved[1] == pytest.approx(0.0)
        assert min(abs(moved[2]), abs(moved[2] - spec.THICKNESS)) == pytest.approx(0.0)


@pytest.mark.skipif(not DUMP.is_file(), reason="local-only vendor harvest absent")
def test_recipe_is_pinned_to_the_harvested_vendor_model() -> None:
    recipe._check_truth(json.loads(DUMP.read_text(encoding="utf-8")))


_FORBIDDEN = re.compile(r"EXCEPTION|ACCEPTED|RULING|POLICY|BOOK FIDELITY|THREADLOCK")


def test_installation_note_fits_the_sheet() -> None:
    row = _config.parts(STEM)
    for field in ("title", "supplier", "finish", "stock_name"):
        assert not re.search(r"\d", str(row[field])), (field, row[field])
    lines = row["installation_notes"].splitlines()
    assert 1 <= len(lines) <= 4
    assert all(len(line) <= 70 for line in lines), lines
    assert not _FORBIDDEN.search(row["installation_notes"].upper())
    assert "MHA-PD-023" in lines[0] and "GROOVE" in lines[0]


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_vn_transgear_retaining_ring as drawing

    sheet = DRAWINGS_BY_NAME["vn_transgear_retaining_ring"]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES


def test_supplier_thickness_picks_the_two_real_ring_faces_not_the_pin_groove() -> None:
    from _drawing_edges import ViewEdge, ViewEdges
    import draw_vn_transgear_retaining_ring as drawing

    def line(name, start, end):
        return ViewEdge(name, (start, end), None, None)

    actual = line("ring thickness", (0.0, 3.0, 0.0), (0.0, 3.0, spec.THICKNESS))
    groove = line("pin groove", (0.0, 3.0, 0.0), (0.0, 3.0, spec.GROOVE_WIDTH))
    slant = line("slanted", (0.0, 3.0, 0.0), (0.1, 3.0, spec.THICKNESS))
    shifted = line("wrong face", (0.0, 3.0, 1.0), (0.0, 3.0, 1.0 + spec.THICKNESS))
    assert (
        drawing._thickness_edge(ViewEdges("top", (groove, slant, shifted, actual)))
        == actual.edge
    )
    with pytest.raises(RuntimeError, match="exact ring thickness"):
        drawing._thickness_edge(ViewEdges("top", (groove, slant, shifted)))


def test_ring_settled_guard_rejects_census_attachment_and_thickness_band_drift(
    monkeypatch,
) -> None:
    from types import SimpleNamespace
    from _drawing_edges import ViewEdge, ViewEdges
    import draw_vn_transgear_retaining_ring as drawing

    class View:
        def __init__(self, count):
            self.count = count

        def GetDisplayDimensionCount(self):
            return self.count

        def GetOutline(self):
            return (0.08, 0.11, 0.14, 0.16)

    class SourceTolerance:
        values = (-spec.THICKNESS_TOL / 1000.0, spec.THICKNESS_TOL / 1000.0)

        @property
        def Type(self):
            return 4  # read-only: the drawing cannot author this model-owned band

        def GetMinValue(self):
            return self.values[0]

        def GetMaxValue(self):
            return self.values[1]

    source_sketch = object()
    thickness_attachment = SimpleNamespace(GetSketch=lambda: source_sketch)

    class Display:
        def __init__(self, edge):
            self.edge = edge
            self.tolerance = SourceTolerance()
            self.native = SimpleNamespace(
                Tolerance=self.tolerance,
                DrivenState=1,
                Name=drawing.THICKNESS_DIMENSION,
                FullName=f"{drawing.THICKNESS_DIMENSION}@{drawing.THICKNESS_SKETCH}@Ring",
            )

        def GetDimension2(self, _index):
            return self.native

        def GetAnnotation(self):
            attached = thickness_attachment if self.edge == "thickness" else self.edge
            return SimpleNamespace(
                Visible=1,
                GetAttachedEntities3=lambda: (attached,),
                GetAttachedEntityTypes=lambda: (10,),
                GetSpecificAnnotation=lambda: self,
            )

        def GetPrimaryTolPrecision2(self):
            return 3

    front, top, right = View(2), View(1), View(3)
    source_feature = SimpleNamespace(
        Visible=1, GetSpecificFeature2=lambda: source_sketch
    )
    top.ReferencedDocument = SimpleNamespace(FeatureByName=lambda _: source_feature)
    circles = tuple(
        ViewEdge(
            name, None, (0.0, 0.0, spec.THICKNESS, 0.0, 0.0, 1.0, diameter / 2.0), None
        )
        for name, diameter in (
            ("free", spec.FREE_DIA),
            ("od", spec.OD),
            ("pin groove", spec.GROOVE_DIA),
        )
    )
    thickness = ViewEdge(
        "thickness", ((0.0, 3.0, 0.0), (0.0, 3.0, spec.THICKNESS)), None, None
    )
    scans = {front: ViewEdges("front", circles), top: ViewEdges("top", (thickness,))}
    monkeypatch.setattr(drawing, "scan_view_edges", lambda view, **_: scans[view])
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    displays = {"thickness": Display("thickness")}

    def reference(_adapter, _view, edge, **_kwargs):
        display = Display(edge)
        displays[edge] = display
        return display

    monkeypatch.setattr(drawing, "_edge_reference", reference)
    monkeypatch.setattr(
        drawing,
        "_is_same_attachment",
        lambda _adapter, actual, expected, _kind: actual == expected,
    )
    monkeypatch.setattr(
        drawing, "assert_supplier_reference_dimension", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        drawing, "supplier_reference_dimension", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        drawing,
        "curate_view_dimensions",
        lambda *_args, **_kwargs: [displays["thickness"].GetAnnotation()],
    )
    monkeypatch.setattr(
        drawing, "add_application_gauges", lambda _adapter, _views: lambda: None
    )
    settled = drawing.supplier_dimensions(
        SimpleNamespace(
            currentModel=SimpleNamespace(
                EditRebuild3=lambda: pytest.fail("no per-dimension rebuild")
            ),
            swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b)),
        ),
        {"*Front": front, "*Top": top, "*Right": right, "*Isometric": View(0)},
    )
    settled()
    right.count = 4
    with pytest.raises(RuntimeError, match="expected 3 native references, got 4"):
        settled()
    right.count = 3
    displays["free"].edge = "pin groove"
    with pytest.raises(RuntimeError, match="physical ring attachment"):
        settled()
    displays["free"].edge = "free"
    thickness_attachment.GetSketch = lambda: object()
    with pytest.raises(
        RuntimeError, match="thickness attachment left its actual converted source"
    ):
        settled()
    thickness_attachment.GetSketch = lambda: source_sketch
    displays["thickness"].tolerance.values = (0.0, 0.0)
    with pytest.raises(
        RuntimeError, match="settled model-owned thickness tolerance changed"
    ):
        settled()


@pytest.mark.parametrize("wrong_attachment", [False, True])
def test_ring_native_reference_rejects_a_different_attached_edge(
    monkeypatch, wrong_attachment
) -> None:
    from types import SimpleNamespace
    import draw_vn_transgear_retaining_ring as drawing

    native = SimpleNamespace(DrivenState=0)
    edge, other = object(), object()
    annotation = SimpleNamespace(
        GetAttachedEntities3=lambda: (other if wrong_attachment else edge,)
    )
    display = SimpleNamespace(
        GetDimension2=lambda _: native, GetAnnotation=lambda: annotation
    )
    model = SimpleNamespace(
        AddDiameterDimension2=lambda *_: display,
        AddDimension2=lambda *_: pytest.fail(
            "gripping circle must use a native diameter"
        ),
        ClearSelection2=lambda _: None,
    )
    adapter = SimpleNamespace(currentModel=model)
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _: obj)
    monkeypatch.setattr(drawing, "_select_view_entity", lambda *_, **__: edge)
    monkeypatch.setattr(
        drawing,
        "_is_same_attachment",
        lambda _adapter, actual, expected, _kind: actual is expected,
    )
    monkeypatch.setattr(
        drawing,
        "supplier_reference_dimension",
        lambda _adapter, value, **_kwargs: value,
    )
    if wrong_attachment:
        with pytest.raises(RuntimeError, match="selected ring edge"):
            drawing._edge_reference(
                adapter,
                object(),
                edge,
                label="free gripping diameter",
                expected_mm=spec.FREE_DIA,
                text_xy=(0.15, 0.1),
                diameter=True,
            )
    else:
        drawing._edge_reference(
            adapter,
            object(),
            edge,
            label="free gripping diameter",
            expected_mm=spec.FREE_DIA,
            text_xy=(0.15, 0.1),
            diameter=True,
        )
