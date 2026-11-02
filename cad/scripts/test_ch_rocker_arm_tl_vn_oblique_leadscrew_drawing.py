"""ZYLtech HW-SC-T8x2-600 feed leadscrew (MHA-CH-06-TL-VN-54) contracts, SolidWorks-free."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

import _config
import _drawing_common as drawing_common
import _purchased_title_fit as title_fit
import _supplier_screw_dimensions as supplier_dimensions
import _supplier_spring_drawing as supplier_drawing
import _stock_trim_drawing as trim_drawing
import build_ch_rocker_arm_tl_vn_oblique_leadscrew as part
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as feed
import ch_rocker_arm_tl_vn_oblique_leadscrew_stock_spec as spec
import draw_ch_rocker_arm_tl_vn_oblique_leadscrew as draw
from _drawing_contract import drawing_specification_violations
from _drawing_notes import property_link
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout
from _printed_tolerance import printed_band_mm

STEM = "ch-rocker-arm-tl-vn-oblique-leadscrew"
NAME = "ch_rocker_arm_tl_vn_oblique_leadscrew"
ROW = _config.parts(STEM)


def test_registry_row_is_the_purchased_zyltech_screw() -> None:
    assert ROW["number"] == "MHA-CH-06-TL-VN-54"
    assert ROW["process"] == "purchased"
    assert ROW["supplier"] == spec.SUPPLIER
    assert ROW["supplier_skus"] == [spec.SKU] == ["HW-SC-T8x2-600"]
    assert ROW["material"] == spec.MATERIAL
    assert int(ROW["quantity"]) == spec.QUANTITY == 1
    # One line in the title block's MATERIAL cell; the provenance is the spec's.
    assert len(ROW["material_specification"]) <= 36
    assert spec.SKU in (spec.__doc__ or "")
    assert "Datasheet-built" in (spec.__doc__ or "")
    assert part.STOCK_PROPERTIES == {
        "Stock Name": ROW["stock_name"],
        "Supplier": spec.SUPPLIER,
        "Supplier SKUs": spec.SKU,
    }
    assert spec.INVENTORY_ID == "fixtures.trammel-tr8-leadscrew"


def test_c4_values_are_imported_not_retyped() -> None:
    assert spec.MAJOR_DIA == feed.SCREW_MAJOR_DIA
    assert spec.LEAD == feed.SCREW_LEAD
    assert spec.STOCK_LENGTH == feed.SCREW_STOCK_LENGTH
    assert spec.LENGTH == feed.SCREW_LENGTH
    assert spec.LENGTH == pytest.approx(feed.SCREW_FAR_END_S - feed.SCREW_NEAR_END_S)
    source = Path(spec.__file__).read_text(encoding="utf-8")
    for name in ("MAJOR_DIA", "LEAD", "STOCK_LENGTH", "LENGTH"):
        assert re.search(rf"^{name} = feed\.", source, re.MULTILINE), name


def test_profile_is_an_edge_broken_major_diameter_cylinder() -> None:
    assert spec.PROFILE[0] == (0.0, 0.0) and spec.PROFILE[-1] == (0.0, spec.LENGTH)
    r = spec.MAJOR_DIA / 2.0
    assert max(radius for radius, _ in spec.PROFILE) == r
    # Each end broken 45° at the title block's chamfer limit, so no callout.
    edge_break = _config.title_block("edge_break")
    assert spec.END_CHAMFER == float(edge_break["chamfer_max_mm"]) == 0.25
    assert spec.PROFILE[1] == (r - spec.END_CHAMFER, 0.0)
    assert spec.PROFILE[2] == (r, spec.END_CHAMFER)
    assert spec.PROFILE[-2] == (r - spec.END_CHAMFER, spec.LENGTH)
    assert spec.LENGTH + spec.LENGTH_TOLERANCE <= spec.STOCK_LENGTH


def test_volume_is_the_blank_less_five_flat_segments() -> None:
    r, c = spec.MAJOR_DIA / 2.0, spec.END_CHAMFER
    ring = 2.0 * math.pi * (r - c / 3.0) * c * c / 2.0  # Pappus on the 45° triangle
    assert spec.BLANK_VOLUME_MM3 == pytest.approx(
        math.pi * r * r * spec.LENGTH - 2.0 * ring, rel=1e-12
    )
    # A circular segment by its subtended angle: R^2 (theta - sin theta) / 2.
    theta = 2.0 * math.acos((r - spec.FLAT_DEPTH) / r)
    segment = r * r * (theta - math.sin(theta)) / 2.0
    assert spec.FLAT_SEGMENT_AREA == pytest.approx(segment, rel=1e-12)
    assert spec.FLAT_VOLUME_MM3 == pytest.approx(segment * 8.0, rel=1e-12)
    assert spec.FLAT_CHORD == pytest.approx(2.0 * r * math.sin(theta / 2.0))
    assert spec.VOLUME_MM3 == pytest.approx(
        spec.BLANK_VOLUME_MM3 - 5 * spec.FLAT_VOLUME_MM3, rel=1e-12
    )
    # The groove allowance the plain cylinder overstates (Ooznest STEP: 10.9/mm).
    assert spec.THREAD_GROOVE_MM3_PER_MM == pytest.approx(10.9, rel=0.02)


def test_build_sketches_the_spec_profile() -> None:
    points = part.profile_points()
    # The same outline, walked up the axis from the origin vertex first.
    assert sorted(points) == sorted(spec.PROFILE)
    assert points[:2] == [(0.0, 0.0), (0.0, spec.LENGTH)]
    assert spec.revolved_volume(tuple(points)) == pytest.approx(spec.BLANK_VOLUME_MM3)
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'volume_check(adapter, "leadscrew", VOLUME_MM3' in source
    assert "publish_screw_axis(adapter)" in source
    assert 'name_last_feature(adapter, "ScrewProfile")' in source
    assert 'name_last_feature(adapter, "Screw")' in source
    assert 'name_last_feature(adapter, "FlatProfile")' in source
    assert 'name_last_feature(adapter, "Flats")' in source
    # Every cut is proved by its own faces as well as its volume step.
    assert '_flat_faces_readback(adapter, "Flats"' in source
    assert 'f"{name}ClockFlat"' in source


def test_flat_stations_are_c4s_set_screw_positions() -> None:
    """One flat under each set screw, stationed from the near end on C4's
    layout: each KP08's axial centre and the handwheel's set screw."""
    near = feed.SCREW_NEAR_END_S
    assert spec.FLAT_STATIONS == {
        "NearKP08": feed.KP08_S[0] - near,
        "FarKP08": feed.KP08_S[1] - near,
        "Handwheel": feed.HUB_END_S + feed.HANDWHEEL_GRUB_FROM_HUB - near,
    }
    assert spec.FLAT_STATIONS == pytest.approx(
        {"NearKP08": 8.5, "FarKP08": 379.5, "Handwheel": 398.5}
    )
    # Each KP08 locks with two set screws 120° apart; the handwheel with one.
    assert spec.CLOCKED_FLATS == ("NearKP08", "FarKP08")
    assert spec.KP08_SET_SCREW_SPACING_DEG == 120.0
    assert spec.FLAT_COUNT == 5
    assert spec.HANDWHEEL_SET_SCREW_MAJOR == 5.0
    # Review bought-r15 (rule 10): the print stations each flat's near edge.
    assert spec.FLAT_STARTS == pytest.approx(
        {"NearKP08": 4.5, "FarKP08": 375.5, "Handwheel": 394.5}
    )
    for name, start in spec.FLAT_STARTS.items():
        lo, hi = (s - near for s in spec.FLAT_HOUSINGS[name])
        assert lo <= start - spec.FLAT_TOLERANCE
        end_max = start + spec.FLAT_LENGTH + spec.FLAT_TOLERANCE
        assert end_max + spec.FLAT_LENGTH_TOLERANCE <= hi


def test_flats_hold_the_set_screws_at_the_band_limits() -> None:
    r = spec.MAJOR_DIA / 2.0
    assert (spec.FLAT_DEPTH, spec.FLAT_LENGTH) == (0.72, 8.0)
    assert spec.FLAT_AF == pytest.approx(7.28)
    assert spec.FLAT_AF_TOLERANCE == printed_band_mm(2) == pytest.approx(0.51)
    assert spec.FLAT_TOLERANCE == printed_band_mm(1) == pytest.approx(0.8)
    assert spec.FLAT_LENGTH_TOLERANCE == printed_band_mm(2) == pytest.approx(0.51)
    assert spec.CLOCK_TOLERANCE_DEG == 1.0
    # ISO 2904: the Tr8x2 external root d3 = d - 2 (P/2 + ac), ac = 0.25.
    assert spec.SCREW_ROOT_DIA == spec.MAJOR_DIA - 2.0 * (spec.PITCH / 2.0 + 0.25)
    assert spec.MINOR_DIA == 6.0  # the modelled nut bore, not the flats' limit

    def holds(af: float) -> bool:
        depth = spec.MAJOR_DIA - af
        deepest = depth + spec.FLAT_AF_TOLERANCE
        shallowest = depth - spec.FLAT_AF_TOLERANCE
        return (
            spec.flat_offset(deepest) > spec.SCREW_ROOT_DIA / 2.0
            and spec.flat_chord(shallowest) >= spec.SET_SCREW_POINT_DIA
        )

    # The ±0.51 band fits only AF 7.26..7.289; 7.28 is inside it.
    assert holds(spec.FLAT_AF) and holds(7.261) and holds(7.289)
    assert not holds(7.25) and not holds(7.29)
    deepest = spec.FLAT_DEPTH + spec.FLAT_AF_TOLERANCE
    shallowest = spec.FLAT_DEPTH - spec.FLAT_AF_TOLERANCE
    # In the crests, clear of the Ø5.5 root.
    assert r - deepest == pytest.approx(2.77)
    # Wider than an M5 cup point, and past the screw both sides off station.
    assert spec.flat_chord(shallowest) == pytest.approx(2.558, abs=1e-3)
    # The far side takes the near edge's band and the length's.
    far_side = spec.FLAT_LENGTH / 2.0 - spec.FLAT_TOLERANCE - spec.FLAT_LENGTH_TOLERANCE
    assert far_side >= 2.5
    # At one place the length's band would leave the screw's far side on the
    # thread.
    assert spec.FLAT_LENGTH / 2.0 - 2.0 * spec.FLAT_TOLERANCE < 2.5
    # A KP08's two flats never meet.
    assert 2.0 * spec.flat_half_angle_deg(deepest) < 120.0 - 1.0


def test_flats_sketch_records_every_dimension_it_emits(monkeypatch) -> None:
    """One Front sketch, a rectangle and across-flat line per station: the
    printed FlatLength and FlatAF on the handwheel's, each station from the
    origin, every emitted dimension named in creation order."""
    emitted, chains, applied = [], [], {}
    ok = SimpleNamespace(is_success=True, data="D", error=None)

    class Adapter:
        async def create_sketch(self, plane):
            assert plane == "Front"
            return ok

        async def add_sketch_constraint(self, *_args):
            return ok

        async def add_sketch_dimension(self, ref1, ref2, kind, value):
            emitted.append((ref1, ref2, kind, value))
            return ok

        async def exit_sketch(self):
            return ok

        async def create_cut_extrude(self, params):
            assert params.both_directions and params.depth == spec.MAJOR_DIA + 2.0
            return ok

    async def chain(_adapter, points, close=True):
        chains.append(list(points))
        return [f"L{len(chains)}_{i}" for i in range(len(points) if close else 1)]

    async def defined(*_args, **_kwargs):
        return None

    def apply(self, _adapter, feature):
        applied[feature] = [name for name, _ in self._rows]
        return []

    monkeypatch.setattr(part, "add_line_chain", chain)
    monkeypatch.setattr(part, "_as_construction", lambda *_args: None)
    monkeypatch.setattr(part, "ensure_fully_defined", defined)
    monkeypatch.setattr(part, "name_last_feature", lambda *_args: None)
    monkeypatch.setattr(part.SketchDims, "apply", apply)
    asyncio.run(part._flats(Adapter()))
    names = applied["FlatProfile"]
    assert len(names) == len(emitted) == 15 == len(set(names))
    by_name = dict(zip(names, emitted, strict=True))
    assert spec.DRAWING_DIMENSIONS["FlatProfile"] <= set(names)
    assert by_name["FlatLength"][2:] == ("vertical_distance", 8.0)
    assert by_name["FlatAF"][2:] == ("horizontal_distance", pytest.approx(7.28))
    for name, start in spec.FLAT_STARTS.items():
        station = by_name[f"{name}FlatStation"]
        assert station[1:] == ("origin", "vertical_distance", start)
        # From the flat's near end: the rectangle's first vertex.
        assert station[0].endswith("_0.start")
    # The printed pair is on the handwheel's rectangle: its station's chains.
    handwheel = [points for points in chains if points[0][1] == 398.5 - 4.0]
    assert handwheel and by_name["FlatLength"][0].startswith(
        f"L{chains.index(handwheel[0]) + 1}_"
    )
    offset = spec.MAJOR_DIA / 2.0 - spec.FLAT_DEPTH  # 3.28
    assert [(offset, 394.5), (offset, 402.5), (5.0, 402.5), (5.0, 394.5)] in chains


def test_clock_flat_sketch_is_defined_by_its_angle(monkeypatch) -> None:
    """The clock flat's sketch: its station plane, the 120° flat at 3.28 from
    the axis, its across-flat and angle the printed pair, the angle last."""
    emitted, chains, applied, planes, angles = [], [], {}, [], []
    ok = SimpleNamespace(is_success=True, data="D", error=None)

    class Adapter:
        async def create_plane(self, params):
            planes.append((params.mode, params.base_plane, params.offset))
            return ok

        async def create_sketch(self, _plane):
            return ok

        async def add_sketch_constraint(self, *_args):
            return ok

        async def add_sketch_dimension(self, ref1, ref2, kind, value):
            emitted.append((ref1, ref2, kind, value))
            return ok

        async def exit_sketch(self):
            return ok

        async def create_cut_extrude(self, params):
            assert params.both_directions and params.depth == spec.FLAT_LENGTH
            return ok

    async def chain(_adapter, points, close=True):
        chains.append(list(points))
        count = len(points) if close else len(points) - 1
        return [f"L{len(chains)}_{i}" for i in range(count)]

    async def defined(*_args, **_kwargs):
        return None

    def apply(self, _adapter, feature):
        applied[feature] = [name for name, _ in self._rows]
        return []

    monkeypatch.setattr(part, "add_line_chain", chain)
    monkeypatch.setattr(part, "_as_construction", lambda *_args: None)
    monkeypatch.setattr(part, "ensure_fully_defined", defined)
    monkeypatch.setattr(part, "name_last_feature", lambda *_args: None)
    monkeypatch.setattr(part, "_sketch_z_per_model_z", lambda _adapter: -1.0)
    monkeypatch.setattr(part, "_clock_angle", lambda *args: angles.append(args[1:]))
    monkeypatch.setattr(part.SketchDims, "apply", apply)
    plane = asyncio.run(part._clock_flat(Adapter(), "FarKP08"))
    assert plane == "FarKP08ClockPlane"
    assert planes == [("offset", "Top Plane", 379.5)]
    names = applied["FarKP08ClockProfile"]
    # The angle is authored natively, outside the adapter's dimension call.
    assert names[-1] == "FarKP08ClockAngle" and len(emitted) == len(names) - 1
    assert len(set(names)) == len(names)
    assert spec.DRAWING_DIMENSIONS["FarKP08ClockProfile"] <= set(names)
    by_name = dict(zip(names, emitted, strict=False))
    assert by_name["FarKP08ClockAF"][2:] == ("distance", pytest.approx(7.28))
    assert angles == [("FarKP08", "L1_0", "L1_1", -1.0)]
    # Clock 0 along +X, the flat's midpoint 3.28 out at 120° toward +Z, which
    # this frame's sketch y reads as -Z.
    (reach, zero), origin, mid = chains[0]
    assert (reach, zero, origin) == (5.0, 0.0, (0.0, 0.0))
    offset = spec.MAJOR_DIA / 2.0 - spec.FLAT_DEPTH
    assert mid == pytest.approx(
        (
            offset * math.cos(math.radians(120.0)),
            -offset * math.sin(math.radians(120.0)),
        )
    )
    assert chains[1][1] == mid


def test_flat_face_readback_refuses_a_wrong_cut(monkeypatch) -> None:
    """The flats are proved by their own planar faces: one flat per station
    square to the clock's radial 3.28 from the axis, two end walls each."""
    monkeypatch.setattr(part, "_early_bound", lambda value, _kind: value)

    def face(normal, root, area_mm2=0.0):
        surface = SimpleNamespace(
            IsPlane=lambda: True,
            PlaneParams=(*normal, *(v / 1000.0 for v in root)),
        )
        return SimpleNamespace(
            GetSurface=lambda: surface, GetArea=lambda: area_mm2 / 1e6
        )

    def adapter(faces):
        feature = SimpleNamespace(
            GetErrorCode2=lambda: (0, False), GetFaces=lambda: faces
        )
        doc = SimpleNamespace(FeatureByName=lambda _name: feature)
        return SimpleNamespace(currentModel=doc)

    area = spec.FLAT_CHORD * spec.FLAT_LENGTH
    offset = spec.MAJOR_DIA / 2.0 - spec.FLAT_DEPTH
    c, s = math.cos(math.radians(120.0)), math.sin(math.radians(120.0))
    good = [
        face((c, 0.0, s), (offset * c, 379.5, offset * s), area),
        face((0.0, 1.0, 0.0), (0.0, 375.5, 0.0)),
        face((0.0, -1.0, 0.0), (0.0, 383.5, 0.0)),
    ]
    part._flat_faces_readback(adapter(good), "FarKP08ClockFlat", 120.0, (379.5,))
    deep = offset + 0.1
    shallow = [face((c, 0.0, s), (deep * c, 379.5, deep * s), area), *good[1:]]
    off_station = [good[0], good[1], face((0.0, -1.0, 0.0), (0.0, 384.5, 0.0))]
    for faces in (shallow, off_station, good[:2]):
        with pytest.raises(RuntimeError):
            part._flat_faces_readback(
                adapter(faces), "FarKP08ClockFlat", 120.0, (379.5,)
            )
    with pytest.raises(RuntimeError):  # a clock-0 flat where the 120° one belongs
        part._flat_faces_readback(adapter(good), "FarKP08ClockFlat", 0.0, (379.5,))


def test_cut_length_is_the_axis_edge_driving_dimension() -> None:
    """The emitted dimensions match the recorded names one for one, and the
    410 is a driving dimension of its own: the axis edge, emitted first."""
    emitted = []
    ok = SimpleNamespace(is_success=True, data="D", error=None)

    class Adapter:
        async def add_sketch_constraint(self, *_args):
            return ok

        async def add_sketch_dimension(self, ref1, ref2, kind, value):
            emitted.append((ref1, ref2, kind, value))
            return ok

    lines = [f"L{i}" for i in range(len(spec.PROFILE))]
    dims = asyncio.run(part.define_profile(Adapter(), lines))
    names = [name for name, _drive in dims._rows]
    assert names == list(part.PROFILE_DIMENSIONS)
    assert len(emitted) == len(names)
    by_name = dict(zip(names, emitted, strict=True))
    assert by_name["CutLength"] == (
        "L0.start",
        "L0.end",
        "vertical_distance",
        spec.LENGTH,
    )
    assert by_name["ShankLength"][3] == spec.LENGTH - 2.0 * spec.END_CHAMFER
    for end in ("Far", "Near"):
        assert by_name[f"{end}ChamferRadial"][3] == spec.END_CHAMFER
        assert by_name[f"{end}ChamferAxial"][3] == spec.END_CHAMFER
    # The near end face closes on the origin vertex: dimensioning it as well
    # would over-define the sketch.
    assert not any(ref1.startswith("L5.") for ref1, *_ in emitted)
    assert "CutLength" in spec.DRAWING_DIMENSIONS["ScrewProfile"]


def test_controls_print_at_the_title_block_rows() -> None:
    assert spec.LENGTH_TOLERANCE == printed_band_mm(1) == pytest.approx(0.8)
    stations = {f"{name}FlatStation" for name in spec.FLAT_STATIONS}
    assert spec.DRAWING_DIMENSIONS == {
        "ScrewProfile": {"CutLength"},
        "FlatProfile": {"FlatLength", "FlatAF", *stations},
        "NearKP08ClockProfile": {"NearKP08ClockAF", "NearKP08ClockAngle"},
        "FarKP08ClockProfile": {"FarKP08ClockAF", "FarKP08ClockAngle"},
    }
    places = {
        "CutLength": 1,
        "FlatLength": 2,
        "FlatAF": 2,
        **dict.fromkeys(stations, 1),
        "NearKP08ClockAF": 2,
        "FarKP08ClockAF": 2,
        "NearKP08ClockAngle": 0,
        "FarKP08ClockAngle": 0,
    }
    assert spec.DIMENSION_PRECISION == places
    assert spec.DRAWING_PRECISION == {
        feature: {name: places[name] for name in names}
        for feature, names in spec.DRAWING_DIMENSIONS.items()
    }
    # swTolGeneral: no band of its own, the title block's row in force.
    assert spec.DIMENSION_TOLERANCE_TYPES == dict.fromkeys(places, 11)
    for name, (_nominal, band, digits) in spec.DIMENSION_CONTROLS.items():
        if name in spec.ANGULAR_DIMENSIONS:
            assert band == 1.0 and spec.control_si(name)[1] == math.radians(1.0)
        else:
            assert band == printed_band_mm(digits)
            assert spec.control_si(name)[1] == band / 1000.0
    # Every flat is one size; the printed one says how many.
    assert (spec.FLAT_LENGTH_CALLOUT, spec.FLAT_AF_CALLOUT) == ("5X", "3X")
    assert draw.FLAT_CALLOUTS == {
        "FlatLength": "5X, ALL FLATS",
        "FlatAF": "3X\nC, D, E",
    }
    # The feed absorbs the band at either limit.
    short_margin = (feed.NEAR_STUB - feed.NEAR_STUB_MIN) + (
        feed.HANDWHEEL_ENGAGEMENT - feed.HANDWHEEL_ENGAGEMENT_MIN
    )
    assert short_margin >= spec.LENGTH_TOLERANCE
    assert feed.SCREW_FAR_END_S + spec.LENGTH_TOLERANCE < feed.WHEEL_S[1]


def test_spec_is_pure_data() -> None:
    source = Path(spec.__file__).read_text(encoding="utf-8")
    imports = re.findall(r"^(?:from|import) (\S+)", source, re.MULTILINE)
    assert set(imports) <= {
        "__future__",
        "math",
        "_printed_tolerance",
        "ch_rocker_arm_tl_vn_oblique_leadscrew_spec",
    }


def test_sheet_is_the_registered_modified_stock_drawing() -> None:
    sheet = DRAWINGS_BY_NAME[NAME]
    assert (sheet.part, sheet.artifact_stem, sheet.script_name) == (
        NAME,
        STEM,
        f"draw_{NAME}.py",
    )
    assert sheet.layout is DrawingLayout.LANDSCAPE
    assert sheet.artifact_stem == part.PART_NAME
    source = Path(draw.__file__).read_text(encoding="utf-8")
    assert "build_purchased_part_drawing" not in source
    assert drawing_specification_violations(source) == ()


def test_one_axis_horizontal_view_at_the_largest_fitting_scale() -> None:
    usable = draw.BORDER[2] - draw.BORDER[0]
    assert usable == pytest.approx(0.4064)
    # 1:1 overruns the border; 1:2 is the next project scale down.
    assert spec.LENGTH / 1000 > usable
    assert draw.SHEET_SCALE == draw.ISO_SCALE == (1.0, 2.0)
    assert draw.SCREW_SHEET_LENGTH == pytest.approx(0.205)
    # *Front looks at the profile sketch; -90 deg lays model +Y to sheet right.
    assert draw.MAIN_VIEW_ANGLE == -math.pi / 2.0
    half = draw.SCREW_SHEET_LENGTH / 2.0
    radius = draw.SCREW_SHEET_DIA / 2.0
    main = (
        draw.MAIN_CENTER[0] - half,
        draw.MAIN_CENTER[1] - radius,
        draw.MAIN_CENTER[0] + half,
        draw.MAIN_CENTER[1] + radius,
    )
    # The isometric stands the axis up: 410 cos 35.26 deg plus the end ellipses.
    iso_half_height = (
        (spec.LENGTH * math.sqrt(2.0 / 3.0) + spec.MAJOR_DIA)
        * draw._SHEET_PER_MODEL_MM
        / 2.0
    )
    iso = (
        draw.ISO_CENTER[0] - radius * 1.5,
        draw.ISO_CENTER[1] - iso_half_height,
        draw.ISO_CENTER[0] + radius * 1.5,
        draw.ISO_CENTER[1] + iso_half_height,
    )
    for box in (main, iso):
        assert draw._inside_sheet(box), box
    assert main[2] < iso[0]
    assert not draw._inside_sheet(draw.TITLE_BLOCK)
    # The cut length stands over the screw, inside its span; the far two
    # flats' stations under it, each in its own row. The near station, the
    # flats' length and across-flat are the details'.
    details = [set(detail.keep) for detail in draw.END_DETAILS]
    assert set(draw.MAIN_KEEP).union(*details) == (
        spec.DRAWING_DIMENSIONS["ScrewProfile"] | spec.DRAWING_DIMENSIONS["FlatProfile"]
    )
    assert sum(map(len, details)) + len(draw.MAIN_KEEP) == len(
        set(draw.MAIN_KEEP).union(*details)
    )
    text_x, text_y = draw.MAIN_KEEP["CutLength"]
    assert main[0] < text_x < main[2] and text_y > main[3]
    rows = [
        draw.MAIN_KEEP[f"{name}FlatStation"][1] for name in ("FarKP08", "Handwheel")
    ]
    assert len(set(rows)) == 2 and max(rows) < main[1] - 0.015
    assert draw.sheet_x(spec.FLAT_STATIONS["Handwheel"]) == pytest.approx(0.29175)
    # The cut length's dimension line (its text about 2.7 mm over it) stands
    # over the sections' letters, 1.7 .. 7.9 mm past the cutting lines' reach.
    assert text_y - 0.0027 > draw.MAIN_CENTER[1] + draw.SECTION_REACH + 0.0079 + 0.004
    # Each section's face and texts within the border, over the main view: the
    # across-flat's text above the axis, the angle's below it (clock 0 points
    # to the sheet's bottom, the angle's bisector 60° off it).
    scale = draw.SECTION_SCALE[0] / draw.SECTION_SCALE[1] / 1000.0
    af_reach = draw.CLOCK_AF_TEXT_RADIUS_MM * scale + 0.006
    angle_reach = draw.CLOCK_ANGLE_TEXT_RADIUS_MM * scale + 0.006
    assert spec.MAJOR_DIA / 2.0 < draw.CLOCK_ANGLE_ARC_RADIUS_MM
    assert draw.CLOCK_ANGLE_ARC_RADIUS_MM < draw.CLOCK_ANGLE_TEXT_RADIUS_MM
    half_clock = math.radians(spec.KP08_SET_SCREW_SPACING_DEG / 2.0)
    drop = max(
        spec.MAJOR_DIA / 2.0 * scale,
        draw.CLOCK_ANGLE_TEXT_RADIUS_MM * scale * math.cos(half_clock)
        + draw.TEXT_HALF_HEIGHT,
        draw.CLOCK_ANGLE_ARC_RADIUS_MM * scale + draw.EXTENSION_OVERSHOOT,
    )
    for section in draw.CLOCK_SECTIONS:
        x, y = section.centre
        box = (x - angle_reach, y - angle_reach, x + angle_reach, y + af_reach)
        assert draw._inside_sheet(box), (section.label, box)
        # The two-row caption (about 13 mm) hangs between the section's
        # lowest ink and the cut length's text.
        caption_bottom = y - drop - draw.SECTION_CAPTION_GAP - 0.013
        assert caption_bottom > text_y + draw.TEXT_HALF_HEIGHT, section.label
        # The cutting line crosses its station's flat, 2.5 clear of both of
        # its ends: the far flat's start prints the 375.5 station's extension
        # line (machinist review: 0.5 off it, the two lines merged).
        start = spec.FLAT_STARTS[section.flat]
        assert start + 2.5 <= section.cut_mm <= start + spec.FLAT_LENGTH - 2.5
        assert section.cut_mm != spec.FLAT_STATIONS[section.flat]
    assert [s.flat for s in draw.CLOCK_SECTIONS] == list(spec.CLOCKED_FLATS)
    # The note block (four rows about 18 mm tall, top-left anchored; its
    # widest printed row, the stock's, at about 2.7 mm a glyph as farm run
    # 20261101T232956371Z printed it, under 135 mm) stands under the main
    # view's lowest text, right of the details and over the title block,
    # left of the isometric.
    printed = draw.STOCK_REFERENCE.replace("<MOD-DIAM>", "Ø")
    assert len(printed) * 0.0027 <= 0.135
    notes = (
        draw.NOTES_XY[0],
        draw.NOTES_XY[1] - 0.018,
        draw.NOTES_XY[0] + 0.135,
        draw.NOTES_XY[1],
    )
    assert draw._inside_sheet(notes)
    assert notes[3] < min(rows) - draw.TEXT_HALF_HEIGHT - 0.005
    assert notes[2] < iso[0]
    detail_right = max(
        x for detail in draw.END_DETAILS for x, _y in detail.keep.values()
    )
    assert notes[0] > detail_right + 0.015


@pytest.fixture
def number_title_native(monkeypatch):
    """Native-shaped notes/rules and the real canonical fitter, without COM.

    Only the initial horizontal envelope is seeded from bb179's measured PDF.
    Font heights and height-to-width response below are synthetic controls,
    not evidence that a particular native rung will repair the actual sheet.
    """
    state = SimpleNamespace(
        properties={"Number": ROW["number"], "Material": "ALLOY STEEL"},
        notes=[], fit_calls=[], writes=[], rebuilds=[], measurements=[],
        bindings=[], walks=[], closed=False, rows=1, width=0.061989821,
        initial_height=0.0048, extent_override=None,
    )

    def live():
        assert not state.closed, "Number check touched closed native handles"

    class Annotation:
        def __init__(self):
            self.position = (0.310763482, 0.028775844, 0.0)
            self.format = SimpleNamespace(
                CharHeight=state.initial_height, TypeFaceName="Arial", LineLength=0.2,
            )
            self.use_doc = True

        def GetPosition(self):
            live()
            return self.position

        def GetTextFormat(self, index):
            live()
            assert index == 0
            return SimpleNamespace(**vars(self.format))

        def SetTextFormat(self, index, use_doc, text_format):
            live()
            assert index == 0 and use_doc is False
            self.format = SimpleNamespace(**vars(text_format))
            self.use_doc = use_doc
            state.writes.append(vars(self.format).copy())
            return True

        def GetUseDocTextFormat(self, index):
            live()
            assert index == 0
            return self.use_doc

    class Note:
        def __init__(self, key, link, text):
            self.key, self.link, self.text = key, link, text
            self.annotation = Annotation() if key == "Number" else None

        @property
        def PropertyLinkedText(self):
            live()
            return self.link

        def GetText(self):
            live()
            assert self.key == "Number", "non-Number resolved text was inspected"
            return self.text

        def GetNext(self):
            live()
            state.walks.append(self.key)
            index = state.notes.index(self) + 1
            return state.notes[index] if index < len(state.notes) else None

        def GetAnnotation(self):
            live()
            assert self.key == "Number", "non-Number note was fitted"
            return self.annotation

        def GetExtent(self):
            live()
            if state.extent_override is not None:
                return state.extent_override
            x, y, z = self.annotation.position
            height = self.annotation.format.CharHeight
            return (
                x, y - height, z,
                x + state.width * height / state.initial_height, y, z,
            )

    # Material deliberately uses this drawing's property, not the all-fields
    # fitter's Material Specification contract. Equal literal text is a decoy.
    state.notes = [
        Note("Name", property_link("SW-Title(Title)"), STEM),
        Note("Material", property_link("Material"), state.properties["Material"]),
        Note("literal", state.properties["Number"], state.properties["Number"]),
        Note("Number", property_link("Number"), state.properties["Number"]),
        Note("REV", property_link("Revision"), "44"),
    ]
    state.number = state.notes[3]
    state.new_number = lambda: Note(
        "Number", property_link("Number"), state.properties["Number"],
    )
    state.rule_points = (
        ((0.3083506, 0.021), (0.372310091, 0.021)),
        ((0.3083506, 0.035906), (0.372310091, 0.035906)),
        ((0.3083506, 0.021), (0.3083506, 0.035906)),
        ((0.372310091, 0.021), (0.372310091, 0.035906)),
    )

    def line(start, end):
        return SimpleNamespace(
            GetType=lambda: 0,
            GetStartPoint2=lambda: SimpleNamespace(X=start[0], Y=start[1]),
            GetEndPoint2=lambda: SimpleNamespace(X=end[0], Y=end[1]),
        )

    segments = tuple(line(*points) for points in state.rule_points)
    state.sheet = SimpleNamespace(
        name="ActualLeadSheet",
        GetTemplateSketch=lambda: SimpleNamespace(GetSketchSegments=lambda: segments),
    )
    state.sheet.GetName = lambda: state.sheet.name
    state.current_sheet = state.sheet
    state.sheet_view = SimpleNamespace(
        GetFirstNote2=lambda: state.notes[0] if state.notes else None,
    )

    def rebuild():
        live()
        state.rebuilds.append(state.number.annotation.format.CharHeight)
        return True

    state.drawing = SimpleNamespace(
        GetCurrentSheet=lambda: state.current_sheet,
        GetFirstView=lambda: state.sheet_view, EditRebuild3=rebuild,
    )
    state.adapter = SimpleNamespace(currentModel=state.drawing)

    def early_bound(value, kind):
        state.bindings.append((value, kind))
        return value

    def display(adapter, annotation):
        live()
        assert adapter is state.adapter and annotation is state.number.annotation
        state.measurements.append(annotation.format.CharHeight)
        return {
            "texts": [{"pos": (0.0, row * 0.004)} for row in range(state.rows)],
        }, []

    def fit(adapter, drawing, sheet, note, **kwargs):
        state.fit_calls.append((adapter, drawing, sheet, note, kwargs))
        return title_fit._fit_title_note(adapter, drawing, sheet, note, **kwargs)

    monkeypatch.setattr(draw, "_early_bound", early_bound)
    monkeypatch.setattr(title_fit, "_early_bound", early_bound)
    monkeypatch.setattr(title_fit, "_zoomed_on", lambda *_args: nullcontext())
    monkeypatch.setattr(title_fit, "annotation_display", display)
    monkeypatch.setattr(title_fit, "_number_state", lambda *_args: "synthetic native state")
    monkeypatch.setattr(title_fit._telemetry, "event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(title_fit._telemetry, "info", lambda *_args: None)
    monkeypatch.setattr(draw, "_fit_title_note", fit)
    state.run = lambda: draw._fit_number_title_note(
        state.adapter, expected_number=state.properties["Number"],
    )
    return state


@pytest.mark.parametrize("font_prefix", ("", "<FONT size=15PTS>"))
def test_number_title_fits_only_existing_number_with_canonical_contract(
    number_title_native, font_prefix,
):
    state = number_title_native
    state.number.link = font_prefix + property_link("Number")
    properties, rules = state.properties.copy(), state.rule_points
    links = tuple((note.link, note.text) for note in state.notes)
    assert state.number.GetExtent()[3] > rules[3][0][0]
    settled = state.run()
    assert state.fit_calls == [(
        state.adapter, state.drawing, state.sheet, state.number,
        {"label": "Number", "minimum": 0.003},
    )]
    assert state.walks == ["Name", "Material", "literal", "Number", "REV"]
    assert (state.number, "INote") in state.bindings
    assert [row["CharHeight"] for row in state.writes] == pytest.approx([0.0048, 0.0047])
    assert state.number.GetExtent()[3] <= rules[3][0][0] - 0.0006
    expected_length = rules[3][0][0] - 0.0006 - state.number.annotation.position[0] - 0.0003
    assert all(row["LineLength"] == pytest.approx(expected_length) for row in state.writes)
    assert all(row["TypeFaceName"] == "Arial" for row in state.writes)
    authored = (len(state.writes), len(state.rebuilds))
    for _ in range(4):
        settled()
    assert (len(state.writes), len(state.rebuilds)) == authored
    assert state.properties == properties and state.rule_points == rules
    assert tuple((note.link, note.text) for note in state.notes) == links
    assert state.current_sheet is state.sheet


def test_number_title_uses_already_read_full_source_value_not_literal_identity(
    number_title_native,
):
    state = number_title_native
    state.number.text = state.properties["Number"] = "COMPLETE-ALTERNATE-SOURCE-NUMBER"
    state.run()()
    assert state.number.text == "COMPLETE-ALTERNATE-SOURCE-NUMBER"
    assert len(state.fit_calls) == 1


@pytest.mark.parametrize("fault", ("missing", "duplicate"))
def test_number_title_requires_exactly_one_owned_property_note(number_title_native, fault):
    state = number_title_native
    if fault == "missing":
        state.notes.remove(state.number)
    else:
        state.notes.append(state.new_number())
    with pytest.raises(RuntimeError, match="requires exactly one source-linked note"):
        state.run()
    assert state.fit_calls == state.writes == state.rebuilds == []


@pytest.mark.parametrize("link", (
    '$PRP:"Number"', '$PRPSHEET:"Other"', 'NUMBER $PRPSHEET:"Number"',
    '$PRPSHEET:"Number" suffix', '$PRPSHEET:"Number"$PRPSHEET:"Material"',
    '<FONT size=0PTS>$PRPSHEET:"Number"', ROW["number"],
))
def test_number_title_rejects_wrong_expression_even_with_exact_resolved_number(
    number_title_native, link,
):
    state = number_title_native
    state.number.link = link
    with pytest.raises(RuntimeError, match="requires exactly one source-linked note"):
        state.run()
    assert state.fit_calls == state.writes == []


@pytest.mark.parametrize("value", (
    "MHA-CH-06-TL-VN-5", "MHA-CH-06-TL-VN-54 ", "mha-ch-06-tl-vn-54", "",
))
def test_number_title_rejects_incomplete_or_changed_resolved_value(number_title_native, value):
    state = number_title_native
    state.number.text = value
    with pytest.raises(RuntimeError, match="source property expression or complete value changed"):
        state.run()
    assert state.fit_calls == state.writes == []


@pytest.mark.parametrize("fault", ("sheet", "view", "sheet_name", "null_sheet_name"))
def test_number_title_refuses_missing_native_context(number_title_native, fault):
    state = number_title_native
    if fault == "sheet":
        state.current_sheet = None
    elif fault == "view":
        state.sheet_view = None
    elif fault == "sheet_name":
        state.sheet.name = ""
    else:
        state.sheet.name = None
    with pytest.raises(RuntimeError, match="has no native sheet"):
        state.run()
    assert state.fit_calls == state.writes == []


@pytest.mark.parametrize("missing", (False, True))
def test_number_title_settled_refuses_wrong_sheet_before_reading_number(
    number_title_native, missing,
):
    state = number_title_native
    settled = state.run()
    state.current_sheet = None if missing else SimpleNamespace(GetName=lambda: "OtherSheet")
    counts = (len(state.measurements), len(state.writes), len(state.rebuilds))
    with pytest.raises(RuntimeError, match="current sheet changed"):
        settled()
    assert (len(state.measurements), len(state.writes), len(state.rebuilds)) == counts
    assert state.current_sheet is not state.sheet  # No silent activation.


@pytest.mark.parametrize("fault", (
    "expression", "resolved", "height", "line_length", "face", "doc_format",
    "anchor", "overflow", "rows",
))
def test_number_title_canonical_settled_check_is_pure_and_rejects_drift(
    number_title_native, fault,
):
    state = number_title_native
    settled = state.run()
    annotation = state.number.annotation
    if fault == "expression":
        state.number.link = '$PRP:"Number"'
    elif fault == "resolved":
        state.number.text = state.number.text[:-1]
    elif fault == "height":
        annotation.format.CharHeight = 0.003
    elif fault == "line_length":
        annotation.format.LineLength = 0.2
    elif fault == "face":
        annotation.format.TypeFaceName = "Other Face"
    elif fault == "doc_format":
        annotation.use_doc = True
    elif fault == "anchor":
        annotation.position = (0.310863482, 0.028775844, 0.0)
    elif fault == "overflow":
        state.extent_override = (0.311, 0.024, 0.0, 0.3724, 0.029, 0.0)
    else:
        state.rows = 2
    authored = (len(state.writes), len(state.rebuilds))
    with pytest.raises(RuntimeError, match=(
        "source property expression or complete value changed"
        if fault in ("expression", "resolved") else "linked title-cell fit did not persist"
    )):
        settled()
    assert (len(state.writes), len(state.rebuilds)) == authored


def test_number_title_cannot_fit_below_unchanged_three_mm_floor(number_title_native):
    state = number_title_native
    state.width = 0.1
    properties, rules = state.properties.copy(), state.rule_points
    with pytest.raises(RuntimeError, match="readable floor 0.003"):
        state.run()
    assert state.writes[-1]["CharHeight"] == 0.003
    assert min(row["CharHeight"] for row in state.writes) == 0.003
    assert state.properties == properties and state.rule_points == rules
    assert state.number.link == property_link("Number")
    assert state.number.text == properties["Number"]


@pytest.fixture
def leadscrew_lifecycle(monkeypatch):
    """Drive the real builder through a native-shaped finalizer; spy the Number."""
    state = SimpleNamespace(
        lifecycle=[], number_calls=[], notes=[], number_mutate_at=None,
        number_changed=False, save_failure=None, closed=False,
        primary=RuntimeError("native save primary"),
        properties={
            "Number": ROW["number"], "Supplier": "supplier", "Supplier SKUs": "sku",
        },
    )
    source = SimpleNamespace(
        GetSaveFlag=lambda: False,
        GetPathName=lambda: str(draw.SOURCE),
        IsOpenedReadOnly=lambda: True,
    )
    drawing = SimpleNamespace(EditRebuild3=lambda: True)
    adapter = SimpleNamespace(currentModel=drawing)

    def mutate(stage):
        if state.number_mutate_at == stage:
            state.number_changed = True

    def step(name):
        def record(*_args, **_kwargs):
            state.lifecycle.append(name)
            return []

        return record

    def note(_adapter, text, *xy):
        state.notes.append((text, xy))
        printed = text.replace(property_link("Supplier SKUs"), "sku").replace(
            property_link("Supplier"), "supplier"
        )
        return SimpleNamespace(GetText=lambda: printed.replace("\n", "\r\n"))

    def fit_number(actual, *, expected_number):
        assert actual is adapter
        assert expected_number == state.properties["Number"]
        state.number_calls.append(("fit", tuple(state.lifecycle)))

        def pure():
            assert not state.closed, "Number check touched closed COM"
            state.number_calls.append(("check", tuple(state.lifecycle)))
            if state.number_changed:
                raise RuntimeError("Number presentation drift")

        return pure

    async def finalize(_adapter, outputs, *, settled_checks, checkpoint, **_kwargs):
        state.lifecycle.append("finalizer")
        mutate("finalizer")
        for check in settled_checks:
            check()
        for kind in ("drawing", "pdf"):
            with drawing_common._drawing_checkpoint(checkpoint, f"{kind}_save"):
                state.lifecycle.append(f"{kind} save")
                mutate(kind)
                if state.save_failure == kind:
                    raise state.primary
        mutate("beforeclose")
        with drawing_common._drawing_checkpoint(checkpoint, "drawing_close"):
            state.lifecycle.append("close")
            state.closed = True
        return {"drawing": str(outputs.slddrw), "pdf": str(outputs.pdf), "png": str(outputs.png)}

    monkeypatch.setattr(draw, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(draw, "active_configuration_name", lambda *_args: "Installed")
    monkeypatch.setattr(
        draw, "read_required_properties", lambda *_args, **_kwargs: state.properties,
    )
    monkeypatch.setattr(draw, "new_project_drawing", lambda *_args, **_kwargs: (
        drawing, object(),
    ))
    monkeypatch.setattr(draw, "stamp_drawing_summary", lambda *_args: None)
    monkeypatch.setattr(
        draw, "place_view", lambda *_args, **_kwargs: SimpleNamespace(Angle=0.0),
    )
    monkeypatch.setattr(draw, "_center_view", lambda *_args: None)
    monkeypatch.setattr(draw, "set_hidden_lines_removed", lambda *_args: None)
    monkeypatch.setattr(draw, "curate_view_dimensions", step("main controls"))
    monkeypatch.setattr(draw, "_add_clock_sections", step("sections"))
    monkeypatch.setattr(draw, "_add_end_details", step("details"))
    monkeypatch.setattr(draw, "verify_machining_controls", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(draw, "set_dimension_callouts", lambda *_args: None)
    monkeypatch.setattr(draw, "add_view_centerline", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(draw, "add_note", note)
    monkeypatch.setattr(draw, "add_leader_note", lambda *_args, **_kwargs: SimpleNamespace(
        GetText=lambda: draw.THREAD_CALLOUT,
    ))
    monkeypatch.setattr(draw, "_fit_number_title_note", fit_number)
    monkeypatch.setattr(draw, "finalize_drawing", finalize)
    state.run = lambda: asyncio.run(
        draw._build_read_only_source(adapter, source, "Installed")
    )
    return state


def test_builder_prints_the_note_block_with_the_stock_reference_line(
    leadscrew_lifecycle,
) -> None:
    state = leadscrew_lifecycle
    assert set(state.run()) == {"drawing", "pdf", "png"}
    assert state.notes == [(draw.NOTES, draw.NOTES_XY)]
    assert draw.NOTES.splitlines()[-1] == draw.STOCK_REFERENCE


def test_builder_fits_the_number_once_and_checks_only_live_boundaries(
    leadscrew_lifecycle,
) -> None:
    state = leadscrew_lifecycle
    state.run()
    assert [kind for kind, _events in state.number_calls] == ["fit"] + ["check"] * 5
    assert state.number_calls[0][1] == ("main controls", "sections", "details")
    snapshots = [events for kind, events in state.number_calls if kind == "check"]
    # The settled check, before and after the drawing save, after the PDF
    # save and before close; never once the drawing is closed.
    assert [events[-1] for events in snapshots] == [
        "finalizer", "finalizer", "drawing save", "pdf save", "pdf save",
    ]
    assert all("close" not in events for events in snapshots)
    assert state.closed and state.lifecycle[-1] == "close"


@pytest.mark.parametrize("stage", ("finalizer", "drawing", "pdf", "beforeclose"))
def test_number_drift_refuses_at_each_boundary_without_refit(
    leadscrew_lifecycle, stage,
) -> None:
    state = leadscrew_lifecycle
    state.number_mutate_at = stage
    with pytest.raises(RuntimeError, match="Number presentation drift"):
        state.run()
    assert [kind for kind, _events in state.number_calls].count("fit") == 1
    assert "close" not in state.lifecycle


@pytest.mark.parametrize("kind", ("drawing", "pdf"))
def test_number_after_save_refusal_keeps_primary_native_failure(
    leadscrew_lifecycle, kind,
) -> None:
    state = leadscrew_lifecycle
    state.save_failure = state.number_mutate_at = kind
    with pytest.raises(RuntimeError) as refused:
        state.run()
    assert refused.value is state.primary
    assert any(
        f"after_{kind}_save checkpoint also failed" in note
        and "Number presentation drift" in note
        for note in refused.value.__notes__
    )
    assert [event for event, _events in state.number_calls].count("fit") == 1
    assert "close" not in state.lifecycle


def test_note_block_that_does_not_resolve_is_refused(leadscrew_lifecycle, monkeypatch) -> None:
    state = leadscrew_lifecycle
    monkeypatch.setattr(draw, "add_note", lambda *_args: SimpleNamespace(
        GetText=lambda: f"ITEM: {draw.ITEM}\nSUPPLIER: supplier\nSKU: sku",
    ))
    with pytest.raises(RuntimeError, match="note block did not resolve"):
        state.run()
    assert state.number_calls == []


@pytest.fixture
def readonly_leadscrew_build(monkeypatch, tmp_path):
    """Only run the real build as far as its first main-dimension import."""
    source_path = tmp_path / "leadscrew-source.SLDPRT"
    source_path.write_bytes(b"original leadscrew source")
    state = SimpleNamespace(
        configuration="Installed", dirty=False, read_only=True,
        path=str(source_path), events=[], presentation_hook=None,
        primary=RuntimeError("stop at first main formatting"),
    )
    source = SimpleNamespace(
        GetSaveFlag=lambda: state.dirty,
        GetPathName=lambda: state.path,
        IsOpenedReadOnly=lambda: state.read_only,
    )
    drawing = SimpleNamespace(EditRebuild3=lambda: True)
    adapter = SimpleNamespace(currentModel=None)

    def sha256(path):
        assert path == source_path
        value = hashlib.sha256(path.read_bytes()).hexdigest()
        state.events.append(("hash", value))
        return value

    def opened(actual_adapter, path, **_kwargs):
        assert actual_adapter is adapter and path == source_path
        state.events.append(("open",))
        adapter.currentModel = source
        return source

    def new_drawing(actual_adapter, **_kwargs):
        assert actual_adapter.currentModel is source
        state.events.append(("drawing",))
        adapter.currentModel = drawing
        return drawing, object()

    def placed(_adapter, path, orientation, *_args, **_kwargs):
        assert path == str(source_path) and not state.dirty
        assert state.configuration == "Installed"
        state.events.append(("view", orientation))
        return SimpleNamespace(Angle=0.0)

    def first_format(_adapter, _view, **_kwargs):
        assert not state.dirty
        state.events.append(("main format",))
        state.dirty = True
        if state.presentation_hook is not None:
            state.presentation_hook()
        raise state.primary

    monkeypatch.setattr(draw, "SOURCE", source_path)
    monkeypatch.setattr(draw, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        draw, "active_configuration_name", lambda *_args: state.configuration
    )
    monkeypatch.setattr(draw._telemetry, "info", lambda _message: None)
    monkeypatch.setattr(draw, "_source_file_sha256", sha256)
    monkeypatch.setattr(supplier_drawing, "_source_file_sha256", sha256)
    monkeypatch.setattr(draw, "_open_supplier_source_read_only", opened)
    monkeypatch.setattr(draw, "read_required_properties", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(draw, "new_project_drawing", new_drawing)
    monkeypatch.setattr(draw, "stamp_drawing_summary", lambda *_args: None)
    monkeypatch.setattr(draw, "place_view", placed)
    monkeypatch.setattr(draw, "_center_view", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(draw, "set_hidden_lines_removed", lambda *_args: None)
    monkeypatch.setattr(draw, "curate_view_dimensions", first_format)
    return SimpleNamespace(
        adapter=adapter, state=state, source=source, path=source_path,
    )


def test_leadscrew_build_creates_views_from_the_clean_source_before_formatting(
    readonly_leadscrew_build,
) -> None:
    seat = readonly_leadscrew_build
    with pytest.raises(RuntimeError, match="stop at first main formatting") as error:
        asyncio.run(draw.build(seat.adapter))
    assert error.value is seat.state.primary
    assert [event[0] for event in seat.state.events] == [
        "hash", "open", "drawing", "view", "view", "main format", "hash"
    ]
    assert seat.state.events[0] == seat.state.events[-1]


def test_leadscrew_refuses_noninstalled_saved_source_before_creating_views(
    readonly_leadscrew_build,
) -> None:
    seat = readonly_leadscrew_build
    seat.state.configuration = ""
    with pytest.raises(RuntimeError, match="without an installed configuration active"):
        asyncio.run(draw.build(seat.adapter))
    assert [event[0] for event in seat.state.events] == ["hash", "open", "hash"]


def test_leadscrew_refuses_dirty_source_before_view_creation(
    readonly_leadscrew_build,
) -> None:
    seat = readonly_leadscrew_build
    seat.state.dirty = True
    with pytest.raises(RuntimeError, match="must be clean before view creation"):
        asyncio.run(draw.build(seat.adapter))
    assert [event[0] for event in seat.state.events] == ["hash", "open", "hash"]


@pytest.mark.parametrize("fault", ("configuration", "read_only", "path", "bytes"))
def test_leadscrew_source_exit_guards_preserve_primary_refusal(
    readonly_leadscrew_build, fault,
) -> None:
    seat = readonly_leadscrew_build

    def changed():
        if fault == "configuration":
            seat.state.configuration = "OtherConfiguration"
        elif fault == "read_only":
            seat.state.read_only = False
        elif fault == "path":
            seat.state.path = str(seat.path.with_name("wrong-source.SLDPRT"))
        else:
            seat.path.write_bytes(b"mutated source bytes")

    seat.state.presentation_hook = changed
    with pytest.raises(RuntimeError, match="stop at first main formatting") as error:
        asyncio.run(draw.build(seat.adapter))
    assert error.value is seat.state.primary
    notes = error.value.__notes__
    assert any(
        ("source file preservation also failed" if fault == "bytes"
         else "source integrity check also failed") in note
        for note in notes
    )
    assert seat.state.events[-1][0] == "hash"


@pytest.mark.parametrize("fault", (None, "configuration", "bytes"))
def test_leadscrew_success_path_still_checks_source_on_lifecycle_exit(
    readonly_leadscrew_build, monkeypatch, fault,
) -> None:
    seat = readonly_leadscrew_build

    async def completed(_adapter, source_model, installed_configuration):
        assert source_model is seat.source and installed_configuration == "Installed"
        if fault == "configuration":
            seat.state.configuration = "OtherConfiguration"
        elif fault == "bytes":
            seat.path.write_bytes(b"mutated source on success")
        return {"drawing": "complete"}

    monkeypatch.setattr(draw, "_build_read_only_source", completed)
    if fault is None:
        assert asyncio.run(draw.build(seat.adapter)) == {"drawing": "complete"}
    else:
        with pytest.raises(RuntimeError, match=(
            "installed source state changed" if fault == "configuration"
            else "source part bytes changed"
        )):
            asyncio.run(draw.build(seat.adapter))
    assert seat.state.events[-1][0] == "hash"


def test_leadscrew_hash_guard_covers_read_only_open_failure(
    readonly_leadscrew_build, monkeypatch,
) -> None:
    seat = readonly_leadscrew_build

    def failed_open(*_args, **_kwargs):
        seat.path.write_bytes(b"mutated during failed source open")
        raise seat.state.primary

    monkeypatch.setattr(draw, "_open_supplier_source_read_only", failed_open)
    with pytest.raises(RuntimeError, match="stop at first main formatting") as error:
        asyncio.run(draw.build(seat.adapter))
    assert error.value is seat.state.primary
    assert any(
        "source file preservation also failed" in note
        for note in error.value.__notes__
    )
    assert [event[0] for event in seat.state.events] == ["hash", "hash"]


def test_notes_name_the_item_not_its_length_or_material() -> None:
    # The cut length is the dimension's, the material the title block's, and
    # no line prescribes a method (rule 7).
    assert draw.ITEM == "TR8X2 LEAD SCREW"
    assert "STAINLESS" not in draw.NOTES.upper()
    assert f"{spec.LENGTH:.0f}" not in draw.NOTES
    for name in ("Supplier", "Supplier SKUs"):
        assert property_link(name) in draw.NOTES
    # Then the bought stock's sizes as one millimetre reference row (machinist
    # review: they replaced a confusing 1:10 gauge sketch), from the spec, the
    # block within rule 7's four lines.
    assert draw.NOTES.splitlines()[3:] == [
        f"STOCK: ({spec.STOCK_LENGTH:g} mm) LONG, (<MOD-DIAM>{spec.MAJOR_DIA:g} mm) MAJOR,"
        f" ({spec.PITCH:g} mm) PITCH",
    ]
    assert len(draw.NOTES.splitlines()) == 4
    assert (spec.STOCK_LENGTH, spec.MAJOR_DIA, spec.PITCH) == (600.0, 8.0, 2.0)
    assert not hasattr(draw, "SUPPLIER_STOCK_CAPTION")
    assert not hasattr(spec, "SUPPLIER_REFERENCE_DIMENSIONS")
    assert "Manufacturing Notes" not in draw.NOTES
    assert not hasattr(spec, "DRAWING_NOTES")
    assert "Manufacturing Notes" not in part.SAVED_PROPERTIES_NO_NOTE
    assert set(part.SAVED_PROPERTIES) - set(part.SAVED_PROPERTIES_NO_NOTE) == {
        "Manufacturing Notes"
    }
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties(adapter, PART_NAME)\n" in source.replace(
        "\r\n", "\n"
    )


def test_sections_print_hidden_lines_removed_and_text_off_their_lines() -> None:
    """Precision display on every view (a section left at draft prints
    faceted), and the across-flat's and angles' texts offset off their lines."""
    source = Path(draw.__file__).read_text(encoding="utf-8")
    sections = source[source.index("def _add_clock_sections") :]
    assert "set_hidden_lines_removed(adapter, view)" in sections
    assert "for view in (main, iso):" in source
    assert "_offset_angle_text(adapter, view_annotations, angle, arc, angle_text)" in (
        sections
    )
    details = source[source.index("def _add_end_details") :]
    assert "set_hidden_lines_removed(adapter, view)" in details
    build = source[source.index("async def build") :]
    assert "FLAT_AF_TEXT_XY" not in source
    assert build.index("_add_end_details(adapter, main)") < build.index(
        "verify_machining_controls("
    )


def _fence_box(detail) -> tuple[float, float, float, float]:
    half = detail.radius_mm * draw._DETAIL_PER_MODEL_MM
    x, y = detail.centre
    return (x - half, y - half, x + half, y + half)


def test_details_show_every_flat_at_the_sections_scale() -> None:
    """The 1:2 view draws a flat 0.36 mm deep: each station's flats, and the
    screw's ends, stand whole in one 3:1 detail fence (review r9, rule 15)."""
    assert draw.DETAIL_SCALE == draw.SECTION_SCALE == (3, 1)
    labels = [detail.label for detail in draw.END_DETAILS]
    assert labels == ["C", "D", "E"]
    assert not set(labels) & {section.label for section in draw.CLOCK_SECTIONS}
    radius = spec.MAJOR_DIA / 2.0

    def fences(station: float, offset: float) -> list[str]:
        return [
            detail.label
            for detail in draw.END_DETAILS
            if math.hypot(station - detail.centre_mm, offset) < detail.radius_mm
        ]

    for name, station in spec.FLAT_STATIONS.items():
        corners = [
            fences(station + along * spec.FLAT_LENGTH / 2.0, across * radius)
            for along in (-1.0, 1.0)
            for across in (-1.0, 1.0)
        ]
        assert all(found == corners[0] and len(found) == 1 for found in corners), name
    for end in (0.0, spec.LENGTH):
        assert all(len(fences(end, across * radius)) == 1 for across in (-1.0, 1.0))
    assert [fences(station, 0.0)[0] for station in spec.FLAT_STATIONS.values()] == [
        "C",
        "D",
        "E",
    ]
    # The fences stand apart on the main view, and so do the details, in a
    # row under its lowest text, left of the title block and in the border.
    spans = sorted(
        (detail.centre_mm - detail.radius_mm, detail.centre_mm + detail.radius_mm)
        for detail in draw.END_DETAILS
    )
    assert all(left[1] < right[0] for left, right in zip(spans, spans[1:]))
    boxes = [_fence_box(detail) for detail in draw.END_DETAILS]
    lowest_main_text = min(y for _x, y in draw.MAIN_KEEP.values())
    for box in boxes:
        assert draw._inside_sheet(box), box
        assert box[3] < lowest_main_text - draw.TEXT_HALF_HEIGHT - 0.010
    assert all(left[2] + 0.004 < right[0] for left, right in zip(boxes, boxes[1:]))


def test_details_carry_the_near_station_and_the_printed_flat() -> None:
    """C prints the near station from the near end's centre; E the printed
    flat's length and across-flat, the 5X and 3X callouts; every text off its
    fence and over the captions' row."""
    by_label = {detail.label: detail for detail in draw.END_DETAILS}
    assert set(by_label["C"].keep) == {"NearKP08FlatStation"}
    assert set(by_label["D"].keep) == set()
    assert set(by_label["E"].keep) == {"FlatLength", "FlatAF"}
    assert spec.PRINTED_FLAT == "Handwheel"
    assert draw.FLAT_CALLOUTS == {
        "FlatLength": "5X, ALL FLATS",
        "FlatAF": "3X\nC, D, E",
    }
    for detail in draw.END_DETAILS:
        fence = detail.radius_mm * draw._DETAIL_PER_MODEL_MM
        for name, (x, y) in detail.keep.items():
            assert math.dist((x, y), detail.centre) > fence + 0.004, name
            assert y - draw.TEXT_HALF_HEIGHT - 0.006 > draw.DETAIL_CAPTION_TOP
            assert draw.BORDER[0] < x < draw.TITLE_BLOCK[0]
    # The flat's length and the near station hang under their spans.
    near, wheel = by_label["C"], by_label["E"]
    x, _y = near.keep["NearKP08FlatStation"]
    assert draw.detail_xy(near.centre_mm, near.centre, 0.0)[0] < x
    assert (
        x
        < draw.detail_xy(near.centre_mm, near.centre, spec.FLAT_STATIONS["NearKP08"])[0]
    )
    # The flat length's text stands right of the flat's far-end extension line
    # (review jbf-r17, rule 14), its widest row clear of the line and of the
    # title block.
    flat_end = draw.detail_xy(
        wheel.centre_mm,
        wheel.centre,
        spec.FLAT_STATIONS["Handwheel"] + spec.FLAT_LENGTH / 2.0,
    )[0]
    text_x = wheel.keep["FlatLength"][0]
    assert text_x - draw.FLAT_LENGTH_TEXT_HALF_WIDTH > flat_end
    assert text_x + draw.FLAT_LENGTH_TEXT_HALF_WIDTH < draw.TITLE_BLOCK[0]
    assert draw.FLAT_LENGTH_TEXT_HALF_WIDTH * 2 > 0.0022 * len(
        draw.FLAT_CALLOUTS["FlatLength"]
    )
    # The across-flat's dimension line stands left of E's fence, short of the
    # flat's start (so its extension line leaves the fence over the flat, not
    # along the thread to the far end), its text (widest row "C, D, E", about
    # 15 mm) clear of both fences and between the far crest and the flat.
    af_x, af_y = wheel.keep["FlatAF"]
    flat_start = spec.FLAT_STATIONS["Handwheel"] - spec.FLAT_LENGTH / 2.0
    assert wheel.centre_mm - wheel.radius_mm < flat_start
    assert af_x + 0.0075 < _fence_box(wheel)[0]
    assert af_x - 0.0075 > _fence_box(by_label["D"])[2] + 0.004
    radius = spec.MAJOR_DIA / 2.0
    crest = draw.detail_xy(wheel.centre_mm, wheel.centre, 0.0, -radius)[1]
    flat = draw.detail_xy(wheel.centre_mm, wheel.centre, 0.0, spec.FLAT_AF - radius)[1]
    assert flat < af_y < crest


def test_details_letters_stand_off_the_screw() -> None:
    letters = [detail.letter for detail in draw.END_DETAILS]
    for x, y in letters:
        assert abs(y - draw.MAIN_CENTER[1]) > draw.SCREW_SHEET_DIA / 2.0 or (
            x > draw.sheet_x(spec.LENGTH) + 0.004 or x < draw.NEAR_END_X - 0.004
        )
    assert all(math.dist(a, b) > 0.010 for a in letters for b in letters if a != b)


def test_thread_is_called_out_on_the_main_view() -> None:
    """The bought thread is named by a leadered callout touching the screw,
    a designation and its extent, no size or method (rule 7)."""
    assert draw.THREAD_CALLOUT.splitlines()[0] == "TR8X2 THREAD FULL LENGTH"
    assert re.findall(r"\d", draw.THREAD_CALLOUT.replace("TR8X2", "")) == []
    tip_x, tip_y = draw.THREAD_LEADER_TIP
    assert draw.NEAR_END_X < tip_x < draw.sheet_x(spec.LENGTH)
    assert tip_y == pytest.approx(draw.MAIN_CENTER[1] + draw.SCREW_SHEET_DIA / 2.0)
    text_x, text_top = draw.THREAD_CALLOUT_XY
    # Under the cut length's dimension line, over the screw, clear of the
    # sections' letters 4.8 .. 6.3 mm in from the cutting lines' ends.
    assert text_top < draw.MAIN_KEEP["CutLength"][1] - 0.006
    assert text_top - 0.009 > tip_y + 0.005
    cuts = [draw.sheet_x(section.cut_mm) for section in draw.CLOCK_SECTIONS]
    assert min(cuts) + 0.025 < text_x and text_x + 0.060 < max(cuts) - 0.015
    source = Path(draw.__file__).read_text(encoding="utf-8")
    build = source[source.index("async def build") :]
    assert "add_leader_note(" in build and "view=main," in build


@pytest.mark.parametrize("target", sorted(spec.DIMENSION_CONTROLS))
@pytest.mark.parametrize(
    "fault",
    [None, "reference", "nominal", "tolerance_type", "widened", "precision", "missing"],
)
def test_drawing_requires_every_control(monkeypatch, fault, target) -> None:
    """A reference-only, moved, banded or re-placed control is a regression."""
    monkeypatch.setattr(trim_drawing, "_early_bound", lambda value, _kind: value)
    assert draw.EXPECTED_CONTROLS["CutLength"] == (
        pytest.approx(0.410),
        pytest.approx(-0.0008),
        pytest.approx(0.0008),
    )
    assert draw.EXPECTED_CONTROLS["FlatAF"] == (
        pytest.approx(0.00728),
        pytest.approx(-0.00051),
        pytest.approx(0.00051),
    )
    assert draw.EXPECTED_CONTROLS["NearKP08ClockAngle"] == (
        pytest.approx(math.radians(120.0)),
        pytest.approx(-math.radians(1.0)),
        pytest.approx(math.radians(1.0)),
    )
    annotations = []
    parts = {}
    for name, (nominal, lower, upper) in draw.EXPECTED_CONTROLS.items():
        tolerance = SimpleNamespace(
            Type=spec.DIMENSION_TOLERANCE_TYPES[name],
            GetMinValue=lambda value=lower: value,
            GetMaxValue=lambda value=upper: value,
        )
        dimension = SimpleNamespace(
            Name=name, DrivenState=2, SystemValue=nominal, Tolerance=tolerance
        )
        display = SimpleNamespace(
            GetDimension2=lambda _configuration, value=dimension: value,
            GetText=lambda _index: "",
            GetPrimaryPrecision2=lambda value=spec.DIMENSION_PRECISION[name]: value,
        )
        annotations.append(
            SimpleNamespace(
                name=name, GetSpecificAnnotation=lambda value=display: value
            )
        )
        parts[name] = (tolerance, dimension, display, upper)
    tolerance, dimension, display, upper = parts[target]
    if fault == "reference":
        dimension.DrivenState = 1
    elif fault == "nominal":
        dimension.SystemValue += 0.001
    elif fault == "tolerance_type":
        tolerance.Type = 4  # swTolSYMMETRIC prints a band the title block carries.
    elif fault == "widened":
        tolerance.GetMaxValue = lambda: upper + 0.001
    elif fault == "precision":
        display.GetPrimaryPrecision2 = lambda: (
            2 if spec.DIMENSION_PRECISION[target] != 2 else 3
        )
    elif fault == "missing":
        annotations = [a for a in annotations if a.name != target]

    def verify() -> None:
        trim_drawing.verify_machining_controls(
            annotations,
            expected=draw.EXPECTED_CONTROLS,
            tolerance_types=spec.DIMENSION_TOLERANCE_TYPES,
            precision=spec.DIMENSION_PRECISION,
        )

    if fault is None:
        verify()
    else:
        with pytest.raises(RuntimeError):
            verify()


@pytest.fixture
def supplier_attachment_state(monkeypatch):
    """Stateful native identities: equal coordinates never imply IsSame."""
    state = SimpleNamespace(
        reads=[], messages=[], captures=[], faults={}, log_fault=None,
        capture_fault=None, warning_fault=None, warnings=[], bound_points=[],
        id_read_objects=[], predicate_point_objects={},
    )
    frame = SimpleNamespace(ArrayData=(
        1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0,
        0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0,
    ))

    def read(token, member, value):
        state.reads.append((token, member))
        fault = state.faults.get((token, member))
        if isinstance(fault, Exception):
            raise fault
        return value if fault is None else fault

    class Sketch:
        def __init__(self, token):
            self.token = token
            self.ModelToSketchTransform = frame
            self.points = []
            self.segments = []
            self.inventory_reads = {11: 0, 10: 0}

        def inventory(self, kind, objects):
            self.inventory_reads[kind] += 1
            if self.inventory_reads[kind] > 1:
                raise AssertionError("diagnostics must not replace the refused inventory")
            return objects

        def GetSketchPoints2(self):
            return self.inventory(11, self.points)

        def GetSketchSegments(self):
            return self.inventory(10, self.segments)

    class Point:
        Type = 0

        def __init__(self, token, index, xyz, owner, generation=0):
            self.token, self.index, self.xyz, self.owner = token, index, xyz, owner
            self.generation = generation

        def GetID(self):
            # A newly rebound wrapper exposes a different context-local ID.
            state.id_read_objects.append(self)
            return read(self.token, "GetID", (self.index, self.generation))

        def GetSketch(self):
            return read(self.token, "GetSketch", self.owner)

        @property
        def X(self):
            return read(self.token, "X", self.xyz[0])

        @property
        def Y(self):
            return read(self.token, "Y", self.xyz[1])

        @property
        def Z(self):
            return read(self.token, "Z", self.xyz[2])

    class Segment:
        def __init__(self, token, index, endpoints, owner):
            self.token, self.index, self.endpoints, self.owner = token, index, endpoints, owner

        def GetType(self):
            return 0  # swSketchLINE

        def GetID(self):
            return read(self.token, "GetID", (self.index, 1))

        @property
        def ConstructionGeometry(self):
            return read(self.token, "ConstructionGeometry", True)

        def GetStartPoint2(self):
            return read(self.token, "GetStartPoint2", self.endpoints[0])

        def GetEndPoint2(self):
            return read(self.token, "GetEndPoint2", self.endpoints[1])

        def GetSketch(self):
            return read(self.token, "GetSketch", self.owner)

    def typed(value, interface):
        if interface == "ISketchPoint" and isinstance(value, Point):
            value = Point(value.token, value.index, value.xyz, value.owner, value.generation + 1)
            state.bound_points.append(value)
        return value

    monkeypatch.setattr(supplier_dimensions, "_early_bound", typed)

    source_sketch, view_sketch = Sketch("source-sketch"), Sketch("view-sketch")
    source_points = [
        Point(f"source-{index}", index, (index * 0.002, 0.004, 0.0), source_sketch)
        for index in range(6)
    ]
    mapped_points = [
        Point(f"mapped-{index}", index, point.xyz, view_sketch)
        for index, point in enumerate(source_points)
    ]
    attached = [
        Point(f"attached-{index}", index, mapped_points[index].xyz, view_sketch)
        for index in (0, 5)
    ]
    source_sketch.points = source_points
    source_segments = [
        Segment(f"source-line-{index}", index, source_points[2 * index:2 * index + 2], source_sketch)
        for index in range(3)
    ]
    mapped_segments = [
        Segment(f"mapped-line-{index}", index, mapped_points[2 * index:2 * index + 2], view_sketch)
        for index in range(3)
    ]
    source_sketch.segments = source_segments
    feature_reads = []

    def source_specific():
        feature_reads.append("source-sketch")
        if len(feature_reads) > 1:
            raise AssertionError("diagnostics must retain the actual source sketch")
        return source_sketch

    source_feature = SimpleNamespace(
        token="source-feature", Name="SupplierReference",
        GetTypeName2=lambda: "ProfileFeature", GetSpecificFeature2=source_specific,
    )
    source_model = SimpleNamespace(
        GetPathName=lambda: "supplier-source.SLDPRT",
        ConfigurationManager=SimpleNamespace(
            ActiveConfiguration=SimpleNamespace(Name="SupplierStock"),
        ),
        SketchManager=SimpleNamespace(ActiveSketch=None),
    )
    def system_values(which_configurations, config_names):
        # gen_py declares (VT_I4, VT_VARIANT); the documented variant accepts
        # either one BSTR or a BSTR array, not arbitrary configuration objects.
        if type(which_configurations) is not int or which_configurations != 3:
            raise TypeError("GetSystemValue3 requires swSpecifyConfiguration here")
        if isinstance(config_names, str):
            names = (config_names,)
        elif isinstance(config_names, (tuple, list)) and all(type(name) is str for name in config_names):
            names = tuple(config_names)
        else:
            raise TypeError("Config_names must be a BSTR or BSTR array")
        if names != ("SupplierStock",):
            raise ValueError("dimension readback requested a different configuration")
        return (0.600,)

    native_dimension = SimpleNamespace(
        token="native-dimension", FullName="SupplierStockLength@SupplierReference@supplier-source.SLDPRT",
        DrivenState=2, GetSystemValue3=system_values,
        GetFeatureOwner=lambda: source_feature,
    )
    mapping_reads = {}

    def corresponding(point):
        mapping_reads[point.token] = mapping_reads.get(point.token, 0) + 1
        if mapping_reads[point.token] > 1:
            raise AssertionError("diagnostics must not replace the refused mapping")
        return state.mapping[point.token]

    view = SimpleNamespace(
        token="view", ReferencedDocument=source_model,
        ReferencedConfiguration="SupplierStock", ModelToViewTransform=frame,
        GetSketch=lambda: view_sketch, GetCorresponding=corresponding,
        GetReferencedModelName=lambda: "supplier-source.SLDPRT",
        GetOrientationName=lambda: "*Front",
        GetName2=lambda: "SupplierStock",
    )
    attachment_reads = []

    def entities():
        attachment_reads.append("entities")
        if attachment_reads.count("entities") > 1:
            raise AssertionError("diagnostics must retain the actual attachments")
        return state.attached

    def types():
        attachment_reads.append("types")
        if attachment_reads.count("types") > 1:
            raise AssertionError("diagnostics must retain the actual attachment types")
        return (state.kind,) * len(state.attached)

    annotation = SimpleNamespace(GetAttachedEntities3=entities, GetAttachedEntityTypes=types)

    def dimension(_index):
        state.reads.append(("display", "GetDimension2"))
        return native_dimension

    display = SimpleNamespace(GetAnnotation=lambda: annotation, GetDimension2=dimension)
    drawing = SimpleNamespace(
        GetPathName=lambda: "refused.SLDDRW", GetEditSheet=lambda: True,
        ActiveDrawingView=view, SketchManager=SimpleNamespace(ActiveSketch=None),
    )
    def native_same(left, right):
        if not state.reads:
            for obj in (left, right):
                if isinstance(obj, Point):
                    state.predicate_point_objects[id(obj)] = obj
        return int(left.token == right.token)


    adapter = SimpleNamespace(
        currentModel=drawing,
        swApp=SimpleNamespace(IsSame=native_same),
    )

    def log(message):
        if state.log_fault is not None:
            raise state.log_fault
        state.messages.append(message)

    def warn(message):
        state.warnings.append(message)
        if state.warning_fault is not None:
            raise state.warning_fault

    def capture(_adapter, _label, _message, **kwargs):
        state.captures.append(kwargs)
        if state.capture_fault is not None:
            raise state.capture_fault
        raise kwargs["exception"]

    actual_correspondence = supplier_dimensions._attachment_correspondence

    def observed_correspondence(*args, **kwargs):
        result = actual_correspondence(*args, **kwargs)
        state.returned_proof = result
        state.private_cache = result.get("_failure_native_objects")
        return result

    monkeypatch.setattr(supplier_dimensions, "_attachment_correspondence", observed_correspondence)
    monkeypatch.setattr(supplier_dimensions, "_assert_dimension_source", lambda *_args, **_kwargs: source_feature)
    monkeypatch.setattr(supplier_dimensions._telemetry, "info", log)
    monkeypatch.setattr(supplier_dimensions._telemetry, "warn", warn)
    monkeypatch.setattr(supplier_dimensions._seat_forensics, "capture_com_failure", capture)
    state.adapter, state.view, state.display = adapter, view, display
    state.source_sketch, state.view_sketch = source_sketch, view_sketch
    state.source_points, state.mapped_points, state.attached = source_points, mapped_points, attached
    state.kind = 11
    state.mapping = dict(zip(
        (point.token for point in source_points), mapped_points, strict=True,
    ))
    state.source_segments, state.mapped_segments = source_segments, mapped_segments
    state.segment_type = Segment
    state.native_dimension = native_dimension
    state.mapping_reads, state.attachment_reads = mapping_reads, attachment_reads

    def verify():
        supplier_dimensions._assert_source(
            adapter, view, display, name="SupplierStockLength", feature="SupplierReference",
        )

    state.verify = verify
    return state


def test_supplier_attachment_equal_xyz_different_identity_still_refuses(
    supplier_attachment_state,
) -> None:
    state = supplier_attachment_state
    assert state.attached[0].xyz == state.mapped_points[0].xyz
    assert state.attached[0].token != state.mapped_points[0].token
    with pytest.raises(RuntimeError, match="nominal supplier attachment changed source sketch") as refused:
        state.verify()
    capture = state.captures[0]
    assert capture["exception"] is refused.value
    context = capture["attachment_context"]
    assert context["attachment_correspondence"]["proven"] is False
    assert "_failure_native_objects" not in context["attachment_correspondence"]
    batch = context["failure_native_readback"]
    assert "read_error" not in batch
    assert batch["context"]["drawing_edit_sheet"] is True
    assert batch["context"]["view_name"] == "SupplierStock"
    assert len(batch["predicate_inventory"]["source"]) == 6
    assert len(batch["predicate_inventory"]["mapped"]) == 6
    assert batch["predicate_inventory"]["uncaptured_kinds"]["10"]["status"] == "unavailable"
    assert {
        id(point) for point in state.id_read_objects
    } == set(state.predicate_point_objects)
    assert all(point.generation == 1 for point in state.id_read_objects)
    assert state.private_cache == {}
    point = batch["predicate_inventory"]["source"][0]
    assert point["id"] == [0, 1]
    assert point["xyz_native_m"] == {"X": 0.0, "Y": 0.004, "Z": 0.0}
    assert point["sketch_owner"]["is_same"]["source"] == {
        "left_to_right": 1, "right_to_left": 1,
    }
    comparison = next(
        row for row in batch["member_comparisons"]
        if row["left"] == "mapped:11:0" and row["right"] == "attached:0"
    )
    assert comparison["is_same"] == {"left_to_right": 0, "right_to_left": 0}
    assert comparison["sketch_owner_is_same"] == {"left_to_right": 1, "right_to_left": 1}
    assert batch["native_dimension"]["system_values"] == [0.600]
    assert batch["native_dimension"]["driven_state"] == 2
    assert state.source_sketch.inventory_reads == {11: 1, 10: 0}
    assert set(state.mapping_reads.values()) == {1}
    assert state.attachment_reads == ["entities", "types"]
    logged = json.loads(state.messages[0].split(": ", 1)[1])
    assert logged == json.loads(json.dumps(context, allow_nan=False))


@pytest.mark.parametrize("getter_fails", [False, True])
def test_supplier_attachment_failure_early_binds_actual_source_feature_type(
    supplier_attachment_state, monkeypatch, getter_fails,
) -> None:
    """Late dispatch can expose the no-argument method as an already-read string."""
    state = supplier_attachment_state
    raw_feature = supplier_dimensions._assert_dimension_source()
    raw_feature.GetTypeName2 = "ProfileFeature"
    original_early_bound = supplier_dimensions._early_bound

    def feature_type():
        if getter_fails:
            raise OSError("typed feature type getter failed")
        return "ProfileFeature"

    bound_feature = SimpleNamespace(
        token=raw_feature.token,
        Name=raw_feature.Name,
        GetSpecificFeature2=raw_feature.GetSpecificFeature2,
        GetTypeName2=feature_type,
    )

    def early_bound(value, interface):
        if value is raw_feature and interface == "IFeature":
            return bound_feature
        return original_early_bound(value, interface)

    monkeypatch.setattr(supplier_dimensions, "_early_bound", early_bound)
    with pytest.raises(
        RuntimeError, match="nominal supplier attachment changed source sketch",
    ) as refused:
        state.verify()
    capture = state.captures[0]
    assert capture["exception"] is refused.value
    batch = capture["attachment_context"]["failure_native_readback"]
    actual_type = batch["context"]["source_feature_type"]
    if getter_fails:
        assert actual_type == {
            "member": "IFeature.GetTypeName2",
            "error_type": "OSError",
            "message": "typed feature type getter failed",
        }
    else:
        assert actual_type == "ProfileFeature"
    assert batch["attachments"]["members"][0]["id"] == [0, 1]
    assert batch["native_dimension"]["system_values"] == [0.600]
    assert state.source_sketch.inventory_reads == {11: 1, 10: 0}
    assert set(state.mapping_reads.values()) == {1}
    assert state.attachment_reads == ["entities", "types"]
    assert state.private_cache == {}


@pytest.mark.parametrize(
    "member,fault,field",
    [
        ("GetID", RuntimeError("native ID read failed"), "id"),
        ("GetID", AttributeError("GetID is unavailable"), "id"),
        ("X", math.nan, "xyz_native_m"),
        ("GetSketch", RuntimeError("owner read failed"), "sketch_owner"),
    ],
)
def test_supplier_attachment_optional_getter_failure_keeps_refusal_and_other_fields(
    supplier_attachment_state, member, fault, field,
) -> None:
    state = supplier_attachment_state
    state.faults[("source-0", member)] = fault
    with pytest.raises(RuntimeError, match="nominal supplier attachment changed source sketch") as refused:
        state.verify()
    assert state.captures[0]["exception"] is refused.value
    batch = state.captures[0]["attachment_context"]["failure_native_readback"]
    assert "read_error" not in batch
    first = batch["predicate_inventory"]["source"][0]
    failed_field = first[field]["X"] if member == "X" else first[field]
    assert failed_field["member"] == f"ISketchPoint.{member}"
    assert "error_type" in failed_field
    assert first["xyz_native_m"]["Y"] == 0.004
    assert batch["predicate_inventory"]["mapped"][0]["id"] == [0, 1]
    assert batch["attachments"]["members"][0]["id"] == [0, 1]
    assert batch["native_dimension"]["driven_state"] == 2
    json.dumps(batch, allow_nan=False)
    assert state.private_cache == {}


@pytest.mark.parametrize("fault", ["logging", "capture_and_warning"])
def test_supplier_attachment_diagnostic_delivery_failure_preserves_original_refusal(
    supplier_attachment_state, fault,
) -> None:
    state = supplier_attachment_state
    if fault == "logging":
        state.log_fault = OSError("diagnostic log sink failed")
    else:
        state.capture_fault = OSError("forensic capture failed")
        state.warning_fault = OSError("warning sink failed")
    with pytest.raises(RuntimeError, match="nominal supplier attachment changed source sketch") as refused:
        state.verify()
    capture = state.captures[0]
    assert capture["exception"] is refused.value
    assert capture["attachment_context"]["failure_native_readback"]["native_dimension"]["driven_state"] == 2
    assert state.private_cache == {}
    if fault == "logging":
        assert capture["attachment_context"]["diagnostic_log_error"]["error_type"] == "OSError"
    else:
        assert len(state.warnings) == 1


def test_supplier_attachment_success_does_not_read_failure_diagnostics(
    supplier_attachment_state,
) -> None:
    state = supplier_attachment_state
    state.attached = (state.mapped_points[0], state.mapped_points[5])
    state.faults[("source-0", "GetID")] = AssertionError("failure-only getter was read on success")
    state.verify()
    assert state.reads == []
    assert state.captures == []
    assert len(state.messages) == 1
    assert state.messages[0].startswith("supplier_source_attachment_proof ")
    assert state.private_cache is None
    assert "_failure_native_objects" not in state.returned_proof


def test_supplier_attachment_cached_segments_keep_independent_endpoint_and_flag_fields(
    supplier_attachment_state,
) -> None:
    state = supplier_attachment_state
    state.kind = 10
    state.mapping = dict(zip(
        (segment.token for segment in state.source_segments), state.mapped_segments, strict=True,
    ))
    state.attached = [
        state.segment_type("attached-line", 0, state.mapped_segments[0].endpoints, state.view_sketch),
    ]
    state.faults[("source-line-0", "GetStartPoint2")] = OSError("start point getter failed")
    with pytest.raises(RuntimeError, match="nominal supplier attachment changed source sketch") as refused:
        state.verify()
    assert state.captures[0]["exception"] is refused.value
    batch = state.captures[0]["attachment_context"]["failure_native_readback"]
    first = batch["predicate_inventory"]["source"][0]
    assert first["construction"] is True
    assert first["start"]["native"]["member"] == "ISketchLine.GetStartPoint2"
    assert first["start"]["native"]["error_type"] == "OSError"
    assert first["end"]["id"] == [1, 1]
    assert first["end"]["xyz_native_m"] == {"X": 0.002, "Y": 0.004, "Z": 0.0}
    assert batch["predicate_inventory"]["mapped"][0]["start"]["id"] == [0, 1]
    assert state.source_sketch.inventory_reads == {11: 0, 10: 1}
    assert set(state.mapping_reads.values()) == {1}
    assert batch["native_dimension"]["driven_state"] == 2


def test_supplier_attachment_readback_records_both_native_comparison_directions(
    supplier_attachment_state,
) -> None:
    state = supplier_attachment_state
    ordinary_same = state.adapter.swApp.IsSame

    def asymmetric_same(left, right):
        if left.token == "mapped-0" and right.token == "attached-0":
            return 2  # Unsupported only in this direction; never an acceptance shortcut.
        return ordinary_same(left, right)

    state.adapter.swApp.IsSame = asymmetric_same
    with pytest.raises(RuntimeError, match="nominal supplier attachment changed source sketch"):
        state.verify()
    batch = state.captures[0]["attachment_context"]["failure_native_readback"]
    comparison = next(
        row for row in batch["member_comparisons"]
        if row["left"] == "mapped:11:0" and row["right"] == "attached:0"
    )
    assert comparison["is_same"] == {"left_to_right": 2, "right_to_left": 0}


@pytest.mark.parametrize("full_name", [None, object()])
def test_supplier_attachment_non_json_scalar_is_labelled_without_hiding_refusal(
    supplier_attachment_state, full_name,
) -> None:
    state = supplier_attachment_state
    state.native_dimension.FullName = full_name
    with pytest.raises(RuntimeError, match="nominal supplier attachment changed source sketch") as refused:
        state.verify()
    capture = state.captures[0]
    assert capture["exception"] is refused.value
    batch = capture["attachment_context"]["failure_native_readback"]
    identity = batch["native_dimension"]["full_name"]
    assert identity["member"] == "IDimension.FullName"
    assert "error_type" in identity
    assert batch["native_dimension"]["system_values"] == [0.600]
    assert batch["attachments"]["members"][0]["id"] == [0, 1]
    assert state.private_cache == {}
    json.dumps(capture["attachment_context"], allow_nan=False)


@pytest.mark.parametrize(
    ("fault", "message"),
    [
        (None, None),
        ("name", "invalid, duplicate or unexpected machining control name"),
        ("nominal", "native dimension nominal changed"),
    ],
)
def test_untyped_native_annotation_keeps_control_identity_and_value_guards(
    monkeypatch, fault, message
) -> None:
    """A dynamic property result is not the generated zero-argument method."""
    name = "CutLength"
    nominal, lower, upper = draw.EXPECTED_CONTROLS[name]
    dimension = SimpleNamespace(
        Name=name if fault != "name" else "UnrelatedControl",
        DrivenState=2,
        SystemValue=nominal + (0.001 if fault == "nominal" else 0.0),
        Tolerance=SimpleNamespace(
            Type=spec.DIMENSION_TOLERANCE_TYPES[name],
            GetMinValue=lambda: lower,
            GetMaxValue=lambda: upper,
        ),
    )
    display = SimpleNamespace(
        GetDimension2=lambda _configuration: dimension,
        GetText=lambda _index: "",
        GetPrimaryPrecision2=lambda: spec.DIMENSION_PRECISION[name],
    )

    class SpecificDispatch:
        def __init__(self, specific):
            self.specific = specific

        def __call__(self):
            raise RuntimeError("returned dispatch has no default member")

    class DynamicAnnotation:
        def __init__(self, specific):
            self.specific = specific

        @property
        def GetSpecificAnnotation(self):
            # Dynamic attribute lookup has already invoked the property.
            return SpecificDispatch(self.specific)

    class TypedAnnotation:
        def __init__(self, specific):
            self.specific = specific

        def GetSpecificAnnotation(self):
            return self.specific

    def early_bound(value, interface):
        if isinstance(value, DynamicAnnotation):
            if interface != "IAnnotation":
                raise TypeError("native annotation requires IAnnotation")
            return TypedAnnotation(value.specific)
        return value

    annotation = DynamicAnnotation(display)
    with pytest.raises(RuntimeError, match="no default member"):
        annotation.GetSpecificAnnotation()
    monkeypatch.setattr(trim_drawing, "_early_bound", early_bound)

    def verify():
        trim_drawing.verify_machining_controls(
            [annotation],
            expected={name: (nominal, lower, upper)},
            tolerance_types=spec.DIMENSION_TOLERANCE_TYPES,
            precision=spec.DIMENSION_PRECISION,
        )

    if fault is None:
        verify()
    else:
        with pytest.raises(RuntimeError, match=message):
            verify()
