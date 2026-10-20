"""Source-derived #25 stock identification, separate from installed clearance links.

6261K281 is the 6261K171 family's configurable one-foot CAD option. Its
component contours/sections and 6261K108's own native sketches/STEP were
inspected on 2026-10-19; see the out-of-tree chain-audit.md source hashes.
Only a two-pitch stock segment is needed here, not the one-foot body pattern.
Cosmetic plate edge rounds and rivet/end blends are deliberately omitted;
none supplies a printed dimension. This is not a full vendor BRep replica.
All installed bodies, path axes, configurations and cut quantities are untouched.
"""

from __future__ import annotations

from collections.abc import Sequence
import math
from typing import Any

from _check import check
from _com import _early_bound
from _drawing_marks import mark_dimensions_for_drawing
from _extrude import extrude_at_offset
from _feature_tree import name_last_feature
from _rebuild import active_configuration_name
from _sketch import (
    SketchDims,
    anchor_point_to_origin,
    blank_reference_sketches,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from _supplier_spring_reference import (
    ReferenceState,
    SUPPLIER_FREE_CONFIGURATION,
    add_supplier_reference_configurations,
)
from diagnostics.diag_mcmaster_lib import assert_profile_closed, draw_closed_profile
from diagnostics.sketch_profile import Arc, Line, Segment, minor_arc

PITCH = 6.35
PIN_DIAMETER = 2.2987  # Native .0905 in: supplier prints .091, not exact .091 in.
ROLLER_DIAMETER = 3.302
ROLLER_WIDTH = 3.175
PLATE_THICKNESS = 0.762
BUSH_RADIUS = 1.494155
BUSH_HALF_LENGTH = 2.3495
CHAIN_PIN_HALF_LENGTH = 3.81
CONNECTING_PIN_START = -3.81
CONNECTING_PIN_END = 4.699
CONNECTING_PIN_LENGTH = CONNECTING_PIN_END - CONNECTING_PIN_START
CLIP_START = 3.1115
CLIP_END = 4.0005  # Actual source solid; not stale Boss-Extrude4's .6985 parameter.
GROOVE_RADIUS = PIN_DIAMETER / 2 * 0.85
INNER_PLATE_RADIUS = 2.9972
OUTER_PLATE_RADIUS = 2.637536
INNER_WAIST_CENTER_Y = 10.986368192090403
OUTER_WAIST_CENTER_Y = 10.611477112256871

FRONT_FEATURE = "SupplierChainNominalFront"
SECTION_FEATURE = "SupplierChainNominalSections"
PIN_DIMENSION = "SupplierPinDiameter"
ROLLER_DIMENSION = "SupplierRollerDiameter"
WIDTH_DIMENSION = "SupplierRollerWidth"
PLATE_DIMENSION = "SupplierPlateThickness"
LENGTH_DIMENSION = "SupplierOverallPinLength"
DIMENSIONS_BY_FEATURE = {
    FRONT_FEATURE: {PIN_DIMENSION, ROLLER_DIMENSION},
    SECTION_FEATURE: {WIDTH_DIMENSION, PLATE_DIMENSION, LENGTH_DIMENSION},
}


def plate_profile(*, inner: bool, center_x: float) -> tuple[Segment, ...]:
    """Actual source waisted contour, not the installed obround outline."""
    radius = INNER_PLATE_RADIUS if inner else OUTER_PLATE_RADIUS
    height = INNER_WAIST_CENTER_Y if inner else OUTER_WAIST_CENTER_Y
    half_pitch = PITCH / 2
    distance = math.hypot(half_pitch, height)
    dx, y = radius * half_pitch / distance, radius * height / distance
    left, right = (center_x - half_pitch, 0.0), (center_x + half_pitch, 0.0)
    tl, bl = (left[0] + dx, y), (left[0] + dx, -y)
    tr, br = (right[0] - dx, y), (right[0] - dx, -y)
    return (
        Arc(left, tl, bl),  # Major arc, around the outside of the left end.
        minor_arc((center_x, -height), bl, br),
        Arc(right, br, tr),
        minor_arc((center_x, height), tr, tl),
    )


def connecting_fixed_plate_profile() -> tuple[Segment, ...]:
    """6261K108 Sketch3's straight-sided fixed plate, before cosmetic rounds."""
    a, r = PITCH / 2, OUTER_PLATE_RADIUS
    tl, bl, tr, br = (-a, r), (-a, -r), (a, r), (a, -r)
    return Arc((-a, 0.0), tl, bl), Line(bl, br), Arc((a, 0.0), br, tr), Line(tr, tl)


def clip_profile() -> tuple[Segment, ...]:
    """6261K108 spring clip: full-precision source planar wire, rigidly reoriented.

    Source frame (X,Y,Z) maps to (-Z,Y,X). Shared endpoint objects preserve
    exact closure; no sketch coordinate is rounded to the supplier's ink.
    """
    a = (3.175, -2.038096)
    b = (-4.329074554850771, -2.038096)
    c = (-4.5881268806432365, -1.4126883617075277)
    d = (-3.8660254267850016, -0.6905869078492978)
    e = (-2.4839745732149963, -0.6905869078492979)
    f = (-1.3561021848618533, -0.8020192113846334)
    g = (-0.47514934787619234, -1.2345764132403254)
    h = (3.2431484126331394, -0.9745677049912083)
    (
        h_reflected,
        g_reflected,
        f_reflected,
        e_reflected,
        d_reflected,
        c_reflected,
        b_reflected,
        a_reflected,
    ) = tuple((x, -y) for x, y in (h, g, f, e, d, c, b, a))
    return (
        Line(a, b),
        minor_arc((-4.329074554850771, -1.6717406874999967), b, c),
        Line(c, d),
        minor_arc((-3.175, 0.0), d, e),
        minor_arc((-1.9657055031262445, -1.208527088736271), e, f),
        minor_arc((-0.5432977605093329, -0.2600087082491161), f, g),
        Line(g, h),
        minor_arc((3.175, 0.0), h, h_reflected),
        Line(h_reflected, g_reflected),
        minor_arc((-0.5432977605093329, 0.2600087082491161), g_reflected, f_reflected),
        minor_arc((-1.9657055031262445, 1.208527088736271), f_reflected, e_reflected),
        minor_arc((-3.175, 0.0), e_reflected, d_reflected),
        Line(d_reflected, c_reflected),
        minor_arc((-4.329074554850771, 1.6717406874999967), c_reflected, b_reflected),
        Line(b_reflected, a_reflected),
        Arc((3.175, 0.0), a, a_reflected),
    )


async def _plate(
    adapter: Any,
    name: str,
    profile: tuple[Segment, ...],
    *,
    stations: Sequence[float],
    hole_radius: float,
    offset: float,
) -> None:
    check(f"create {name}", await adapter.create_sketch("Front"))
    await draw_closed_profile(adapter, profile, label=name, loops=1)
    set_sketch_direct_db(adapter, True)
    try:
        for x in stations:
            check(f"{name} source hole", await adapter.add_circle(x, 0.0, hole_radius))
    finally:
        set_sketch_direct_db(adapter, False)
    check(f"exit {name}", await adapter.exit_sketch())
    name_last_feature(adapter, f"{name}Profile")
    assert_profile_closed(adapter, name, loops=3, feature=f"{name}Profile")
    extrude_at_offset(adapter, PLATE_THICKNESS, offset, merge_result=False)
    name_last_feature(adapter, name)


async def _round_pair(
    adapter: Any,
    name: str,
    *,
    stations: Sequence[float],
    radius: float,
    start: float,
    end: float,
    bore: float | None = None,
    merge: bool = False,
) -> None:
    check(f"create {name}", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    try:
        for index, x in enumerate(stations):
            await define_circle(adapter, x, 0.0, radius, f"{name} outer {index}")
            if bore is not None:
                await define_circle(adapter, x, 0.0, bore, f"{name} bore {index}")
    finally:
        set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, name)
    check(f"exit {name}", await adapter.exit_sketch())
    name_last_feature(adapter, f"{name}Profile")
    extrude_at_offset(adapter, end - start, start, merge_result=merge)
    name_last_feature(adapter, name)


async def author_chain_stock(adapter: Any) -> None:
    """One actual inner/outer component pair, including rollers and bushings."""
    inner, outer = (0.0, PITCH), (PITCH, 2 * PITCH)
    await _round_pair(
        adapter,
        "StockPins",
        stations=outer,
        radius=PIN_DIAMETER / 2,
        start=-CHAIN_PIN_HALF_LENGTH,
        end=CHAIN_PIN_HALF_LENGTH,
    )
    await _round_pair(
        adapter,
        "StockBushings",
        stations=inner,
        radius=BUSH_RADIUS,
        bore=PIN_DIAMETER / 2,
        start=-BUSH_HALF_LENGTH,
        end=BUSH_HALF_LENGTH,
    )
    await _round_pair(
        adapter,
        "StockRollers",
        stations=inner,
        radius=ROLLER_DIAMETER / 2,
        bore=BUSH_RADIUS,
        start=-ROLLER_WIDTH / 2,
        end=ROLLER_WIDTH / 2,
    )
    for side, inner_offset, outer_offset in (
        ("Back", -BUSH_HALF_LENGTH, -CLIP_START),
        ("Front", ROLLER_WIDTH / 2, BUSH_HALF_LENGTH),
    ):
        await _plate(
            adapter,
            f"StockInnerPlate{side}",
            plate_profile(inner=True, center_x=PITCH / 2),
            stations=inner,
            hole_radius=BUSH_RADIUS,
            offset=inner_offset,
        )
        await _plate(
            adapter,
            f"StockOuterPlate{side}",
            plate_profile(inner=False, center_x=1.5 * PITCH),
            stations=outer,
            hole_radius=PIN_DIAMETER / 2,
            offset=outer_offset,
        )


async def author_connecting_stock(adapter: Any) -> None:
    """The sourced five-body connector, including its spring clip and pin grooves."""
    stations = (-PITCH / 2, PITCH / 2)
    # Author pins first: later touching plate/clip bodies must never be merged.
    for name, radius, start, end, merge in (
        ("StockPinShanks", PIN_DIAMETER / 2, CONNECTING_PIN_START, CLIP_START, False),
        ("StockPinGrooves", GROOVE_RADIUS, CLIP_START, CLIP_END, True),
        ("StockPinEnds", PIN_DIAMETER / 2, CLIP_END, CONNECTING_PIN_END, True),
    ):
        await _round_pair(
            adapter,
            name,
            stations=stations,
            radius=radius,
            start=start,
            end=end,
            merge=merge,
        )
    await _plate(
        adapter,
        "StockConnectingFixedPlate",
        connecting_fixed_plate_profile(),
        stations=stations,
        hole_radius=PIN_DIAMETER / 2,
        offset=BUSH_HALF_LENGTH,
    )
    await _plate(
        adapter,
        "StockConnectingLoosePlate",
        plate_profile(inner=False, center_x=0.0),
        stations=stations,
        hole_radius=PIN_DIAMETER / 2,
        offset=-CLIP_START,
    )
    check("create source spring clip", await adapter.create_sketch("Front"))
    await draw_closed_profile(
        adapter, clip_profile(), label="source spring clip", loops=1
    )
    check("exit source spring clip", await adapter.exit_sketch())
    name_last_feature(adapter, "StockSpringClipProfile")
    assert_profile_closed(
        adapter, "source spring clip", loops=1, feature="StockSpringClipProfile"
    )
    extrude_at_offset(adapter, CLIP_END - CLIP_START, CLIP_START, merge_result=False)
    name_last_feature(adapter, "StockSpringClip")


def _require_circle(
    adapter: Any, center: tuple[float, float, float], radius: float
) -> None:
    """Prove nominal sections coincide with the authored physical stock features."""
    for body in (
        _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    ):
        for edge in _early_bound(body, "IBody2").GetEdges() or ():
            curve = _early_bound(_early_bound(edge, "IEdge").GetCurve(), "ICurve")
            if not curve.IsCircle():
                continue
            values = tuple(float(value) for value in curve.CircleParams)
            if (
                len(values) == 7
                and all(
                    abs(values[index] * 1000 - target) < 1e-6
                    for index, target in enumerate(center)
                )
                and abs(values[6] * 1000 - radius) < 1e-6
                and abs(abs(values[5]) - 1.0) < 1e-10
            ):
                return
    raise RuntimeError(
        f"source stock section has no physical circle at {center}, radius {radius}"
    )


async def _reference_front(adapter: Any, *, connecting: bool) -> str:
    # The connector's FOR roller circle is its supplier's native Sketch1 gauge,
    # not the smaller physical pin with a forced nominal text/value override.
    rows = (
        (PIN_DIMENSION, PIN_DIAMETER, PITCH / 2 if connecting else 2 * PITCH),
        (ROLLER_DIMENSION, ROLLER_DIAMETER, -PITCH / 2 if connecting else 0.0),
    )
    check("create supplier chain nominal front", await adapter.create_sketch("Front"))
    dims = SketchDims()
    for name, diameter, x in rows:
        entity = await define_circle(
            adapter,
            x,
            0.0,
            diameter / 2,
            name,
            dims=dims,
            names=(f"{name}CenterX", f"{name}CenterY", name),
        )
        segment = _early_bound(adapter._sketch_entities[entity], "ISketchSegment")
        segment.ConstructionGeometry = True
        if not segment.ConstructionGeometry:
            raise RuntimeError(
                f"{name}: supplier section must be construction geometry"
            )
    await ensure_fully_defined(adapter, FRONT_FEATURE)
    check("exit supplier chain nominal front", await adapter.exit_sketch())
    name_last_feature(adapter, FRONT_FEATURE)
    dims.apply(adapter, FRONT_FEATURE)
    mark_dimensions_for_drawing(adapter, FRONT_FEATURE, {name for name, _, _ in rows})
    blank_reference_sketches(adapter, (FRONT_FEATURE,))
    return FRONT_FEATURE


async def _reference_sections(adapter: Any, *, connecting: bool) -> str:
    # Top-plane sketch +Y is model -Z. Each chord is the actual source section
    # span. FOR roller width on the connector is the source's application gauge.
    rows = [
        (
            WIDTH_DIMENSION,
            -PITCH / 2 if connecting else 0.0,
            -ROLLER_WIDTH / 2,
            ROLLER_WIDTH / 2,
        ),
    ]
    if connecting:
        rows.extend(
            (
                (PLATE_DIMENSION, 0.0, -CLIP_START, -BUSH_HALF_LENGTH),
                (
                    LENGTH_DIMENSION,
                    PITCH / 2,
                    -CONNECTING_PIN_END,
                    -CONNECTING_PIN_START,
                ),
            )
        )
    check("create supplier chain nominal sections", await adapter.create_sketch("Top"))
    dims = SketchDims()
    for name, x, y0, y1 in rows:
        set_sketch_direct_db(adapter, True)
        try:
            line = check(name, await adapter.add_line(x, y0, x, y1))
        finally:
            set_sketch_direct_db(adapter, False)
        segment = _early_bound(adapter._sketch_entities[line], "ISketchSegment")
        segment.ConstructionGeometry = True
        if not segment.ConstructionGeometry:
            raise RuntimeError(
                f"{name}: supplier section must be construction geometry"
            )
        check(
            f"vertical {name}",
            await adapter.add_sketch_constraint(line, None, "vertical"),
        )
        await dimension_between(
            adapter, f"{line}.start", f"{line}.end", "vertical_distance", y1 - y0, name
        )
        dims.record(name)
        await anchor_point_to_origin(adapter, f"{line}.start", x, y0, name)
        if x != 0.0:
            dims.record(f"{name}StartX")
        if y0 != 0.0:
            dims.record(f"{name}StartY")
    await ensure_fully_defined(adapter, SECTION_FEATURE)
    check("exit supplier chain nominal sections", await adapter.exit_sketch())
    name_last_feature(adapter, SECTION_FEATURE)
    dims.apply(adapter, SECTION_FEATURE)
    mark_dimensions_for_drawing(adapter, SECTION_FEATURE, {name for name, *_ in rows})
    blank_reference_sketches(adapter, (SECTION_FEATURE,))
    return SECTION_FEATURE


async def add_chain_stock_references(adapter: Any, *, connecting: bool = False) -> None:
    original_model = adapter.currentModel
    installed = active_configuration_name(adapter, original_model)
    if not installed:
        raise RuntimeError("chain stock source has no original installed configuration")

    async def references(target: Any) -> tuple[str, ...]:
        station = PITCH / 2 if connecting else 2 * PITCH
        end = CONNECTING_PIN_END if connecting else CHAIN_PIN_HALF_LENGTH
        _require_circle(target, (station, 0.0, end), PIN_DIAMETER / 2)
        _require_circle(
            target,
            (station, 0.0, CONNECTING_PIN_START if connecting else -end),
            PIN_DIAMETER / 2,
        )
        plate_station = PITCH / 2 if connecting else 2 * PITCH
        for z in (BUSH_HALF_LENGTH, CLIP_START):
            _require_circle(target, (plate_station, 0.0, z), OUTER_PLATE_RADIUS)
        if not connecting:
            for z in (-ROLLER_WIDTH / 2, ROLLER_WIDTH / 2):
                _require_circle(target, (0.0, 0.0, z), ROLLER_DIAMETER / 2)
        return await _reference_front(
            target, connecting=connecting
        ), await _reference_sections(target, connecting=connecting)

    await add_supplier_reference_configurations(
        adapter,
        (
            ReferenceState(
                SUPPLIER_FREE_CONFIGURATION,
                author_connecting_stock if connecting else author_chain_stock,
                references,
                body_count=5 if connecting else 10,
            ),
        ),
        body_count=4,
    )
    model = adapter.currentModel
    if (
        int(adapter.swApp.IsSame(model, original_model)) != 1
        or active_configuration_name(adapter, model) != installed
    ):
        raise RuntimeError(
            "chain stock source changed the original installed document/configuration"
        )
    try:
        for name in model.GetConfigurationNames() or ():
            if not model.ShowConfiguration2(str(name)):
                raise RuntimeError(
                    f"cannot inspect chain source sketch visibility in {name}"
                )
            part = _early_bound(model, "IPartDoc")
            for feature in (FRONT_FEATURE, SECTION_FEATURE):
                if (
                    int(_early_bound(part.FeatureByName(feature), "IFeature").Visible)
                    != 1
                ):
                    raise RuntimeError(
                        f"{feature}: source reference sketch is shown in {name}"
                    )
    finally:
        if not model.ShowConfiguration2(installed):
            raise RuntimeError(
                "cannot restore installed chain configuration after source visibility proof"
            )
