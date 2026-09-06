"""Read native drawing annotation footprints, never locate model features.

``annotation_box(adapter, annotation)`` returns absolute sheet-metre rectangles.
``body`` excludes open dimension/datum/GTol leaders; ``envelope`` includes their
native stroke endpoints. Text boxes are conservative *logical font cells*, not
tight glyph-ink boxes. Native frame and symbol geometry is included separately.
No annotation, view, font, document preference, or model entity is changed.

The initial font calibration is deliberately bounded: regular Century Gothic,
metre-height text, LOWER_LEFT reference and native drawing display data. The
copy-only ``probe_drawing_annotation_bounds.py`` records the native metadata and
matching PDF. On SW2026, CharHeight=.0035 has CharHeightInPts=13 (rounded), while
the PDF font transform is 13.2283497pt = .004666667m em: 4/3 of CharHeight.
GDI's logical cell matches the native basic-dimension frame, within 0.01mm.
Other font/reference modes fail explicitly instead of inheriting this calibration.
IEnvironment validates symbol definitions, but its unit-text-height geometry is
NOT directly translated from the display-data character-cell origin. Symbol
cells use actual native frame bounds, or (unframed diameter only) the measured
advance to the immediately following value and the calibrated logical cell.
Tokens such as <MOD-DIAM> are never measured as their literal character strings.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import math
import re
from typing import Any, Callable

from _common import _early_bound
from _drawing_view_packing import Rect


Point = tuple[float, float]
_GEOMETRY_EPSILON_M = 1e-8  # Native duplicate frame vertices differ by ~0.7nm.
_FONT_EM_PIXELS = 10000
_SW2026_CENTURY_GOTHIC_EM_PER_HEIGHT = 4 / 3
_SYMBOL = re.compile(r"<[^<>]+-[^<>]+>\Z")
_KINDS = frozenset({2, 4, 5, 6, 7, 13, 15})


@dataclass(frozen=True)
class Segment:
    start: Point
    end: Point
    width_m: float = 0.0


@dataclass(frozen=True)
class TextRun:
    value: str
    position: Point
    height_m: float
    font: str
    angle_rad: float
    reference: int
    inverted: int


@dataclass(frozen=True)
class NativeSnapshot:
    name: str
    kind: int
    anchor: Point
    text_runs: tuple[TextRun, ...]
    lines: tuple[Segment, ...]
    leaders: tuple[Segment, ...]
    primitive_boxes: tuple[Rect, ...]
    note_extent: tuple[float, float, float, float] | None
    format_signature: tuple[Any, ...]
    leader_boxes: tuple[Rect, ...] = ()


@dataclass(frozen=True)
class AnnotationBounds:
    name: str
    kind: int
    anchor: Point
    body: Rect
    envelope: Rect
    text_boxes: tuple[Rect, ...]
    text_runs: tuple[TextRun, ...]
    leader_segments: tuple[Segment, ...]
    format_signature: tuple[Any, ...]
    native_strokes: tuple[Segment, ...]


def _rectangle(points: list[Point]) -> Rect:
    if not points or not all(math.isfinite(v) for point in points for v in point):
        raise ValueError("annotation bounds require finite native geometry")
    return Rect(
        min(p[0] for p in points),
        min(p[1] for p in points),
        max(p[0] for p in points),
        max(p[1] for p in points),
    )


def _corners(rect: Rect) -> list[Point]:
    return [
        (rect.xmin, rect.ymin),
        (rect.xmax, rect.ymin),
        (rect.xmax, rect.ymax),
        (rect.xmin, rect.ymax),
    ]


def _stroke_points(line: Segment) -> list[Point]:
    if line.width_m == 0:
        return [line.start, line.end]
    if not math.isfinite(line.width_m) or line.width_m < 0:
        raise ValueError("native stroke width must be finite and nonnegative")
    radius = line.width_m / 2
    return [
        (
            min(line.start[0], line.end[0]) - radius,
            min(line.start[1], line.end[1]) - radius,
        ),
        (
            max(line.start[0], line.end[0]) + radius,
            max(line.start[1], line.end[1]) + radius,
        ),
    ]


def _coincident(a: Point, b: Point) -> bool:
    return math.dist(a, b) <= _GEOMETRY_EPSILON_M


def _same_segment(a: Segment, b: Segment) -> bool:
    return (_coincident(a.start, b.start) and _coincident(a.end, b.end)) or (
        _coincident(a.start, b.end) and _coincident(a.end, b.start)
    )


def _frame_lines(lines: tuple[Segment, ...]) -> tuple[Segment, ...]:
    """Keep edges belonging to actual closed four-edge native frame cells.

    This also handles rotated rectangular frames. It does not infer a frame
    from annotation type/nominal height or mistake an open datum stem for one.
    """
    edges: list[Segment] = []
    for line in lines:
        if not any(_same_segment(line, prior) for prior in edges):
            edges.append(line)
    frame: set[int] = set()
    for first, edge in enumerate(edges):
        stack = [(edge.end, (first,), (edge.start, edge.end))]
        while stack:
            point, path, vertices = stack.pop()
            if len(path) == 4:
                if _coincident(point, edge.start):
                    # Rectangles have perpendicular adjacent edges; exclude
                    # triangular arrowheads plus a repeated/degenerate edge.
                    vectors = [
                        (
                            vertices[i + 1][0] - vertices[i][0],
                            vertices[i + 1][1] - vertices[i][1],
                        )
                        for i in range(4)
                    ]
                    if all(
                        abs(
                            sum(a * b for a, b in zip(vectors[i], vectors[(i + 1) % 4]))
                        )
                        <= 1e-5
                        * math.hypot(*vectors[i])
                        * math.hypot(*vectors[(i + 1) % 4])
                        for i in range(4)
                    ):
                        frame.update(path)
                continue
            for index, candidate in enumerate(edges):
                if index in path:
                    continue
                following = (
                    candidate.end
                    if _coincident(point, candidate.start)
                    else candidate.start
                    if _coincident(point, candidate.end)
                    else None
                )
                if following is not None:
                    stack.append((following, (*path, index), (*vertices, following)))
    return tuple(edges[index] for index in sorted(frame))


@lru_cache(maxsize=1024)
def _gdi_cell(font: str, text: str) -> Rect:
    """Actual installed-font advances and cell height; no substitution accepted."""
    import win32ui
    import ctypes
    from ctypes import wintypes

    class ABC(ctypes.Structure):
        _fields_ = [("a", wintypes.INT), ("b", wintypes.UINT), ("c", wintypes.INT)]

    dc = win32ui.CreateDC().CreateCompatibleDC()
    face = win32ui.CreateFont({"name": font, "height": -_FONT_EM_PIXELS, "weight": 400})
    previous = dc.SelectObject(face)
    try:
        if dc.GetTextFace().casefold() != font.casefold():
            raise ValueError(f"GDI substituted {dc.GetTextFace()!r} for {font!r}")
        metrics = dc.GetTextMetrics()
        if metrics["tmWeight"] != 400 or metrics["tmItalic"]:
            raise ValueError("GDI returned an uncalibrated font style")
        width, height = dc.GetTextExtent(text)
        if width <= 0 or height <= 0:
            raise ValueError("GDI returned an empty text cell")
        abc_widths = ctypes.WinDLL("gdi32", use_last_error=True).GetCharABCWidthsW
        abc_widths.argtypes = (
            wintypes.HDC,
            wintypes.UINT,
            wintypes.UINT,
            ctypes.POINTER(ABC),
        )
        abc_widths.restype = wintypes.BOOL
        first, last = ABC(), ABC()
        if not abc_widths(
            dc.GetSafeHdc(), ord(text[0]), ord(text[0]), ctypes.byref(first)
        ) or not abc_widths(
            dc.GetSafeHdc(), ord(text[-1]), ord(text[-1]), ctypes.byref(last)
        ):
            raise ValueError("GDI rejected TrueType side-bearing measurement")
        return Rect(
            min(0, first.a) / _FONT_EM_PIXELS,
            0.0,
            (width - min(0, last.c)) / _FONT_EM_PIXELS,
            height / _FONT_EM_PIXELS,
        )
    finally:
        dc.SelectObject(previous)
        dc.DeleteDC()


def font_cell_extent(run: TextRun, signature: tuple[Any, ...]) -> Rect:
    font, height, points, in_points, width_factor, bold, italic = signature
    if font != "Century Gothic" or run.font != font or bold or italic or in_points:
        raise ValueError(f"uncalibrated native text font/style: {signature}")
    expected_points = float(height) * _SW2026_CENTURY_GOTHIC_EM_PER_HEIGHT * 72 / 0.0254
    if abs(float(points) - expected_points) >= 1:
        raise ValueError(
            "native font height mapping differs from calibrated SW2026 profile"
        )
    if not math.isfinite(width_factor) or width_factor <= 0:
        raise ValueError("native font width factor must be positive and finite")
    cell = _gdi_cell(run.font, run.value)
    em = run.height_m * _SW2026_CENTURY_GOTHIC_EM_PER_HEIGHT
    # One-sided 0.01mm allowance covers observed native/GDI grid quantization
    # (<0.005mm on the saved basic-dimension positive control), not layout space.
    return Rect(
        cell.xmin * em * width_factor - 0.00001,
        cell.ymin * em - 0.00001,
        cell.xmax * em * width_factor + 0.00001,
        cell.ymax * em + 0.00001,
    )


def _text_box(
    run: TextRun,
    signature: tuple[Any, ...],
    text_extent: Callable,
    symbol_extent: Callable | None,
) -> Rect:
    if run.reference != 1 or run.inverted != 0:
        raise ValueError("uncalibrated native text reference/mirroring")
    if (
        not all(math.isfinite(v) for v in (*run.position, run.height_m, run.angle_rad))
        or run.height_m <= 0
    ):
        raise ValueError("native text geometry must be finite with positive height")
    if "<" in run.value or ">" in run.value:
        raise ValueError(
            "native symbol cells require the enclosing annotation snapshot"
        )
    local = text_extent(run, signature)
    cosine, sine = math.cos(run.angle_rad), math.sin(run.angle_rad)
    return _rectangle(
        [
            (
                run.position[0] + x * cosine - y * sine,
                run.position[1] + x * sine + y * cosine,
            )
            for x, y in _corners(local)
        ]
    )


def _symbol_cell(
    snapshot: NativeSnapshot,
    index: int,
    frames: tuple[Segment, ...],
    text_extent: Callable,
    symbol_extent: Callable | None,
) -> Rect:
    run = snapshot.text_runs[index]
    if not _SYMBOL.fullmatch(run.value) or symbol_extent is None:
        raise ValueError(f"native symbol definition required: {run.value!r}")
    symbol_extent(run.value)  # Fail unknown definitions; do not guess a font glyph.
    if run.reference != 1 or run.inverted or not math.isfinite(run.angle_rad):
        raise ValueError("uncalibrated native symbol cell reference")
    if frames:
        frame = _rectangle([p for edge in frames for p in (edge.start, edge.end)])
        if (
            frame.xmin <= run.position[0] <= frame.xmax
            and frame.ymin <= run.position[1] <= frame.ymax
        ):
            return frame
    if (
        snapshot.kind != 4
        or run.value != "<MOD-DIAM>"
        or index + 1 >= len(snapshot.text_runs)
    ):
        raise ValueError(f"unframed native symbol cell is uncalibrated: {run.value}")
    following = snapshot.text_runs[index + 1]
    if (
        "<" in following.value
        or following.height_m != run.height_m
        or abs(following.angle_rad - run.angle_rad) > 1e-12
    ):
        raise ValueError(
            "diameter symbol must precede a same-height, same-angle native value"
        )
    cosine, sine = math.cos(run.angle_rad), math.sin(run.angle_rad)
    x, y = (
        following.position[0] - run.position[0],
        following.position[1] - run.position[1],
    )
    advance, offset = x * cosine + y * sine, -x * sine + y * cosine
    if advance <= 0 or abs(offset) > run.height_m / 4:
        raise ValueError("diameter native value is not on the symbol's text baseline")
    cell = text_extent(following, snapshot.format_signature)
    local = Rect(
        0.0,
        min(0.0, cell.ymin, offset + cell.ymin),
        advance,
        max(cell.ymax, offset + cell.ymax),
    )
    return _rectangle(
        [
            (
                run.position[0] + x * cosine - y * sine,
                run.position[1] + x * sine + y * cosine,
            )
            for x, y in _corners(local)
        ]
    )


def bounds_from_snapshot(
    snapshot: NativeSnapshot,
    *,
    text_extent: Callable = font_cell_extent,
    symbol_extent: Callable | None = None,
) -> AnnotationBounds:
    if snapshot.kind not in _KINDS:
        raise ValueError(
            f"unsupported annotation kind {snapshot.kind}: {snapshot.name}"
        )
    if not all(math.isfinite(value) for value in snapshot.anchor):
        raise ValueError("annotation anchor must be finite")
    frames = (
        _frame_lines(snapshot.lines) if snapshot.kind in {2, 4, 5} else snapshot.lines
    )
    # INote.GetExtent already measures native rich/multifont text in sheet
    # space; do not approximate it using the annotation's single base format.
    text_boxes = (
        ()
        if snapshot.kind == 6
        else tuple(
            _symbol_cell(snapshot, index, frames, text_extent, symbol_extent)
            if "<" in run.value or ">" in run.value
            else _text_box(run, snapshot.format_signature, text_extent, symbol_extent)
            for index, run in enumerate(snapshot.text_runs)
            if run.value
        )
    )
    body_lines = tuple(
        line
        for line in frames
        if not any(_same_segment(line, leader) for leader in snapshot.leaders)
    )
    body_points = [
        point
        for box in (*text_boxes, *snapshot.primitive_boxes)
        for point in _corners(box)
    ]
    body_points.extend(point for line in body_lines for point in _stroke_points(line))
    if snapshot.kind == 6:
        if snapshot.note_extent is None:
            raise ValueError("native note GetExtent is required")
        body_points.extend(_corners(Rect(*snapshot.note_extent)))
    body = _rectangle(body_points)
    envelope_points = [
        *_corners(body),
        *(point for box in snapshot.leader_boxes for point in _corners(box)),
        *(
            point
            for line in (*snapshot.lines, *snapshot.leaders)
            for point in _stroke_points(line)
        ),
    ]
    envelope = _rectangle(envelope_points)
    leaders = tuple(
        line
        for line in snapshot.lines
        if not any(_same_segment(line, edge) for edge in body_lines)
    )
    return AnnotationBounds(
        snapshot.name,
        snapshot.kind,
        snapshot.anchor,
        body,
        envelope,
        text_boxes,
        snapshot.text_runs,
        leaders,
        snapshot.format_signature,
        snapshot.lines,
    )


def _native_symbol_extent(
    environment: Any, token: str
) -> tuple[float, float, float, float]:
    counts = tuple(environment.GetSymEdgeCounts(token) or ())
    if len(counts) != 5 or not any(counts) or counts[3]:
        raise ValueError(
            f"unsupported or unknown native symbol geometry: {token}, {counts}"
        )
    points: list[Point] = []
    for index, stride, method in ((0, 6, "GetSymLines"), (4, 11, "GetSymTriangles")):
        raw = tuple(getattr(environment, method)(token) or ()) if counts[index] else ()
        if len(raw) != counts[index] * stride:
            raise ValueError(f"native symbol {token} {method} count mismatch")
        for start in range(0, len(raw), stride):
            points.extend(
                (raw[start + i], raw[start + i + 1])
                for i in range(0, 6 if index == 0 else 9, 3)
            )
    circles = tuple(environment.GetSymCircles(token) or ()) if counts[2] else ()
    arcs = tuple(environment.GetSymArcs(token) or ()) if counts[1] else ()
    if len(circles) != counts[2] * 4 or len(arcs) != counts[1] * 9:
        raise ValueError(f"native symbol {token} curve count mismatch")
    for index in range(0, len(circles), 4):
        radius, x, y, _z = circles[index : index + 4]
        points.extend(((x - radius, y - radius), (x + radius, y + radius)))
    for index in range(0, len(arcs), 9):
        x, y, _z, sx, sy = arcs[index : index + 5]
        radius = math.hypot(sx - x, sy - y)
        # Native arc2 does not expose winding. The full parent circle is an
        # explicit conservative bound; never assume the shorter sweep.
        points.extend(((x - radius, y - radius), (x + radius, y + radius)))
    return _rectangle(points).bounds


@lru_cache(maxsize=1)
def _line_weight_preferences() -> tuple[int, ...]:
    """Read installed swconst values; documentation lists names, not integers."""
    import pythoncom
    from win32com.client import gencache
    from solidworks_mcp.adapters import sw_type_info

    path = sw_type_info._find_aux_tlb("swconst.tlb")
    if path is None:
        raise ValueError("installed swconst is required for native line weights")
    iid, lcid, _system, major, minor, _flags = pythoncom.LoadTypeLib(
        str(path)
    ).GetLibAttr()
    constants = gencache.EnsureModule(str(iid), lcid, major, minor).constants
    return tuple(
        int(getattr(constants, f"swPageSetupPrinter{name}LineWeight"))
        for name in (
            "Thin",
            "Normal",
            "Thick",
            "Thick2",
            "Thick3",
            "Thick4",
            "Thick5",
            "Thick6",
        )
    )


def _native_snapshot(annotation: Any, extension: Any = None) -> NativeSnapshot:
    kind = int(annotation.GetType())
    if kind not in _KINDS:
        raise ValueError(f"unsupported annotation kind {kind}: {annotation.GetName()}")
    data = _early_bound(annotation.GetDisplayData(), "IDisplayData")
    runs = []
    for index in range(int(data.GetTextCount())):
        if tuple(data.GetTextPlaneAtIndex(index) or ()):
            raise ValueError("uncalibrated nonempty native drawing text plane")
        runs.append(
            TextRun(
                str(data.GetTextAtIndex(index)),
                tuple(data.GetTextPositionAtIndex(index))[:2],
                float(data.GetTextHeightAtIndex(index)),
                str(data.GetTextFontAtIndex(index)),
                float(data.GetTextAngleAtIndex(index)),
                int(data.GetTextRefPositionAtIndex(index)),
                int(data.GetTextInvertAtIndex(index)),
            )
        )
    lines = []
    widths: dict[int, float] = {}
    for index in range(int(data.GetLineCount())):
        raw = tuple(data.GetLineAtIndex3(index))
        if len(raw) != 10:
            raise ValueError("native line array must contain ten values")
        width = 0.0
        if kind in {13, 15}:
            weight = int(raw[3])
            if weight not in range(8) or extension is None:
                raise ValueError(f"uncalibrated native centerline/mark weight {weight}")
            if weight not in widths:
                widths[weight] = float(
                    extension.GetUserPreferenceDouble(
                        _line_weight_preferences()[weight], 0
                    )
                )
            width = widths[weight]
            if not math.isfinite(width) or width <= 0:
                raise ValueError("native print line weight must be positive")
        lines.append(Segment(raw[4:6], raw[7:9], width))
    boxes = []
    for index in range(int(data.GetArcCount())):
        raw = tuple(data.GetArcAtIndex2(index))
        if len(raw) != 17 or abs(raw[13]) > 1e-8 or abs(raw[14]) > 1e-8:
            raise ValueError("native arc is not in the drawing sheet plane")
        radius = math.dist(raw[4:6], raw[10:12])
        boxes.append(
            Rect(raw[10] - radius, raw[11] - radius, raw[10] + radius, raw[11] + radius)
        )
    for index in range(int(data.GetPolyLineCount())):
        raw = tuple(data.GetPolylineAtIndex2(index))
        count = int(raw[6])
        if len(raw) != 7 + count * 3:
            raise ValueError("native polyline point count mismatch")
        points = tuple((raw[7 + i * 3], raw[8 + i * 3]) for i in range(count))
        lines.extend(Segment(a, b) for a, b in zip(points, points[1:]))
    leaders = []
    for index in range(int(annotation.GetLeaderCount())):
        raw = tuple(annotation.GetLeaderPointsAtIndex(index) or ())
        if len(raw) not in {6, 9}:
            raise ValueError("native leader must expose two or three XYZ points")
        points = tuple((raw[i], raw[i + 1]) for i in range(0, len(raw), 3))
        leaders.extend(Segment(a, b) for a, b in zip(points, points[1:]))
    leader_boxes = []
    for index in range(int(data.GetTriangleCount())):
        raw = tuple(data.GetTriangleAtIndex(index))
        if len(raw) != 11:
            raise ValueError("native triangle must contain eleven values")
        leader_boxes.append(_rectangle([(raw[i], raw[i + 1]) for i in (0, 3, 6)]))
    for index in range(int(data.GetArrowHeadCount())):
        raw = tuple(data.GetArrowHeadAtIndex2(index))
        if (
            len(raw) != 12
            or not all(math.isfinite(v) for v in raw)
            or raw[6] < 0
            or raw[7] < 0
        ):
            raise ValueError("native arrowhead geometry is invalid")
        # Full native-size radius conservatively encloses every arrow style
        # and projected direction; no guessed arrow dimensions or winding.
        radius = math.hypot(raw[6], raw[7])
        if radius:
            leader_boxes.append(
                Rect(raw[0] - radius, raw[1] - radius, raw[0] + radius, raw[1] + radius)
            )
    for index in range(int(data.GetPolygonCount())):
        raw = tuple(data.GetPolygonAtIndex(index))
        count = int(raw[4])
        if len(raw) != 5 + count * 3:
            raise ValueError("native polygon point count mismatch")
        leader_boxes.append(
            _rectangle([(raw[5 + i * 3], raw[6 + i * 3]) for i in range(count)])
        )
    signature: tuple[Any, ...] = ()
    if runs:
        fmt = _early_bound(annotation.GetTextFormat(0), "ITextFormat")
        signature = (
            str(fmt.TypeFaceName),
            float(fmt.CharHeight),
            int(fmt.CharHeightInPts),
            bool(fmt.IsHeightSpecifiedInPts()),
            float(fmt.WidthFactor),
            bool(fmt.Bold),
            bool(fmt.Italic),
        )
    extent = None
    if kind == 6:
        raw = tuple(
            _early_bound(annotation.GetSpecificAnnotation(), "INote").GetExtent()
        )
        if len(raw) != 6:
            raise ValueError("native note extent must expose two XYZ points")
        extent = raw[0], raw[1], raw[3], raw[4]
    position = tuple(annotation.GetPosition() or ())
    if not position and kind in {13, 15}:
        # CenterLine.GetAnnotation().GetPosition returned None in the saved
        # screw positive control. This is a derived witness anchor only, never
        # an annotation SetPosition target; its parent view owns movement.
        measured = _rectangle([p for line in lines for p in _stroke_points(line)])
        position = (
            (measured.xmin + measured.xmax) / 2,
            (measured.ymin + measured.ymax) / 2,
        )
    if len(position) not in {2, 3}:
        raise ValueError(
            f"native annotation has no supported anchor: {annotation.GetName()}"
        )
    return NativeSnapshot(
        str(annotation.GetName()),
        kind,
        position[:2],
        tuple(runs),
        tuple(lines),
        tuple(leaders),
        tuple(boxes),
        extent,
        signature,
        tuple(leader_boxes),
    )


def annotation_box(adapter: Any, annotation: Any) -> AnnotationBounds:
    """Read one native annotation after all annotation edits/rebuilds complete."""
    if int(adapter.currentModel.GetType()) != 3:  # swDocDRAWING
        raise ValueError("annotation bounds require the active drawing document")
    revision = str(_early_bound(adapter.swApp, "ISldWorks").RevisionNumber())
    if revision.split(".", 1)[0] != "34":
        raise ValueError(
            f"uncalibrated SolidWorks annotation font revision: {revision}"
        )
    annotation = _early_bound(annotation, "IAnnotation")
    snapshot = _native_snapshot(
        annotation, _early_bound(adapter.currentModel.Extension, "IModelDocExtension")
    )
    definitions: dict[str, tuple[float, float, float, float]] = {}
    tokens = {
        run.value
        for run in snapshot.text_runs
        if snapshot.kind != 6 and _SYMBOL.fullmatch(run.value)
    }
    if tokens:
        environment = _early_bound(adapter.swApp.GetEnvironment(), "IEnvironment")
        definitions = {
            token: _native_symbol_extent(environment, token) for token in tokens
        }
    return bounds_from_snapshot(snapshot, symbol_extent=definitions.__getitem__)
