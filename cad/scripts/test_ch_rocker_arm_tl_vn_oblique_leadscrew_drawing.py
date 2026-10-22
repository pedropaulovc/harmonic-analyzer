"""ZYLtech HW-SC-T8x2-600 feed leadscrew (MHA-CH-06-TL-VN-54) contracts, SolidWorks-free."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import _config
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
from _supplier_screw_layout import supplier_screw_lane_plan

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
        # The cutting line crosses its station's flat, clear of its station.
        station = spec.FLAT_STATIONS[section.flat]
        assert 2.5 < abs(section.cut_mm - station) < spec.FLAT_LENGTH / 2.0
    assert [s.flat for s in draw.CLOCK_SECTIONS] == list(spec.CLOCKED_FLATS)
    # The note block (about 70 x 13 mm, top-left anchored) stands under the
    # main view's lowest text, right of the details and over the title block,
    # left of the isometric.
    notes = (
        draw.NOTES_XY[0],
        draw.NOTES_XY[1] - 0.013,
        draw.NOTES_XY[0] + 0.070,
        draw.NOTES_XY[1],
    )
    assert draw._inside_sheet(notes)
    assert notes[3] < min(rows) - draw.TEXT_HALF_HEIGHT - 0.005
    assert notes[2] < iso[0]
    detail_right = max(
        x for detail in draw.END_DETAILS for x, _y in detail.keep.values()
    )
    assert notes[0] > detail_right + 0.015


class _SupplierStockNativeView:
    """Recorded retained frame; the optional fresh-frame shape is synthetic."""

    def __init__(self, *, fresh=False, move_annotations=True):
        self.Position = (0.183, 0.2626)
        self.refreshes = 0
        self.ReferencedDocument = object()
        self.outline_override = None
        self.curve_offset = 0.0 if fresh else -0.0201
        self.frame_half = (0.035588, 0.006388) if fresh else (0.005988, 0.026088)
        self.annotations = []
        self.move_annotations = move_annotations
        self.moves = []

    def reference_bounds(self):
        x, y = self.Position
        y += self.curve_offset
        return (x - 0.030, y - 0.0008, x + 0.030, y + 0.0008)

    def UpdateViewDisplayGeometry(self):
        self.refreshes += 1

    def GetOutline(self):
        if self.outline_override is not None:
            return self.outline_override
        x, y = self.Position
        half_x, half_y = self.frame_half
        return (x - half_x, y - half_y, x + half_x, y + half_y)

    def SetViewPosition(self, position, move_children):
        assert move_children is False
        self.moves.append((self.Position, tuple(position)))
        dx, dy = position[0] - self.Position[0], position[1] - self.Position[1]
        self.Position = tuple(position)
        if self.move_annotations:
            for annotation in self.annotations:
                annotation.translate(dx, dy)
        return True


def test_supplier_stock_recorded_native_outline_refuses_original_center(
    monkeypatch,
) -> None:
    monkeypatch.setattr(draw, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(draw, "double_array", tuple)
    monkeypatch.setattr(draw._telemetry, "info", lambda _message: None)
    view = _SupplierStockNativeView()
    view.Position = (0.190, 0.243)
    # rolling-ready line 37: the retained frame, not the source sketch.
    assert view.GetOutline() == pytest.approx(
        (0.184012, 0.216912, 0.195988, 0.269088)
    )
    assert view.GetOutline()[3] > draw.BORDER[3]
    assert view.GetOutline()[3] > draw.SUPPLIER_STOCK_FIELD[3]
    with pytest.raises(RuntimeError, match="view leaves the drawable sheet"):
        draw._center_view(
            SimpleNamespace(EditRebuild3=lambda: True),
            view, (0.190, 0.243), "supplier stock gauges",
        )


def test_supplier_stock_centers_recorded_native_frame_not_offset_source_curves(
    monkeypatch,
) -> None:
    monkeypatch.setattr(draw, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(draw, "double_array", tuple)
    view = _SupplierStockNativeView()
    # layout1859 line 41 records BOTH independent bounds after geometry refresh.
    assert view.GetOutline() == pytest.approx(
        (0.177012, 0.236512, 0.188988, 0.288688)
    )
    assert view.reference_bounds() == pytest.approx(
        (0.153, 0.2417, 0.213, 0.2433)
    )
    before = view.GetOutline()
    view.UpdateViewDisplayGeometry()
    assert view.GetOutline() == before  # No invented refresh/shrink behavior.
    draw._center_view(
        SimpleNamespace(EditRebuild3=lambda: True), view,
        draw.SUPPLIER_STOCK_CENTER, "supplier stock gauges",
    )
    assert view.Position == pytest.approx((0.183, 0.2365))
    assert view.GetOutline() == pytest.approx(
        (0.177012, 0.210412, 0.188988, 0.262588)
    )
    assert view.reference_bounds() == pytest.approx(
        (0.153, 0.2156, 0.213, 0.2172)
    )
    assert draw._inside(view.GetOutline(), draw.SUPPLIER_STOCK_FIELD)
    assert draw._inside(view.reference_bounds(), draw.SUPPLIER_STOCK_FIELD)
    x0, y0, x1, y1 = view.reference_bounds()
    assert (x1 - x0, y1 - y0) == pytest.approx((0.060, 0.0016))
    assert (y0 + y1) / 2.0 - view.Position[1] == pytest.approx(-0.0201)
    assert view.refreshes == 1


@pytest.mark.parametrize(
    "fault,reason",
    (
        ("position", "invalid view position"),
        ("set", "failed to position"),
        ("drift", "failed to centre"),
        ("outline", "invalid view outline"),
    ),
)
def test_supplier_stock_center_refusal_records_native_frame_and_target(
    monkeypatch, fault, reason
) -> None:
    messages = []
    monkeypatch.setattr(draw, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(draw, "double_array", tuple)
    monkeypatch.setattr(draw._telemetry, "info", messages.append)
    view = _SupplierStockNativeView()
    if fault == "position":
        view.outline_override = view.GetOutline()
        view.Position = (math.nan, 0.243)
    elif fault == "set":
        view.SetViewPosition = lambda *_args: False
    elif fault == "drift":
        view.SetViewPosition = lambda *_args: True
    elif fault == "outline":
        view.outline_override = (math.nan, 0.0, 1.0, 1.0)
    with pytest.raises(RuntimeError, match=reason):
        draw._center_view(
            SimpleNamespace(EditRebuild3=lambda: True), view,
            draw.SUPPLIER_STOCK_CENTER, "supplier stock gauges",
        )
    assert len(messages) == 1
    assert "native_outline_m=" in messages[0]
    assert f"requested_center_m={draw.SUPPLIER_STOCK_CENTER!r}" in messages[0]
    assert "actual_center_m=" in messages[0]
    assert "failure=RuntimeError(" in messages[0]


@pytest.fixture
def supplier_stock_inset(monkeypatch, request):
    """Recorded frame offset and synthetic two-row native glyph/stroke data."""
    options = getattr(request, "param", {})
    monkeypatch.setattr(draw, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(draw, "double_array", tuple)
    view = _SupplierStockNativeView(
        fresh=options.get("fresh", False),
        move_annotations=options.get("move_annotations", True),
    )
    rebuilds, redraws = [], []
    drawing = SimpleNamespace(
        EditRebuild3=lambda: True,
        GraphicsRedraw2=lambda: redraws.append("redraw"),
        ActivateView=lambda name: name == "",
        GetEditSheet=lambda: True,
        ActiveDrawingView=None,
    )
    adapter = SimpleNamespace(currentModel=drawing)
    events, messages, allowance_reads, annotation_cells = [], [], [], []
    projections, geometry_reads, reacquisitions = [], [], []
    caption_position = [0.140, 0.264, 0.007]
    caption_moves, caption_extents = [], []
    monkeypatch.setattr(draw._telemetry, "info", messages.append)

    def caption_extent():
        x, y, z = caption_position
        extent = (x + 0.0012, y - 0.004, z, x + 0.0732, y + 0.005, z)
        caption_extents.append(extent)
        return extent

    def set_caption_position(*position):
        caption_moves.append(position)
        caption_position[:] = position
        return True

    caption_annotation = SimpleNamespace(
        OwnerType=1, GetPosition=lambda: tuple(caption_position),
        SetPosition2=set_caption_position,
    )
    note = SimpleNamespace(
        GetText=lambda: draw.SUPPLIER_STOCK_CAPTION,
        GetAnnotation=lambda: caption_annotation, GetExtent=caption_extent,
    )

    def source_centers():
        x, y = view.Position
        origin = y + view.curve_offset - 0.0004
        return {
            "SupplierStockLength": (x, origin),
            "SupplierStockDiameter": (x, origin),
            "SupplierThreadPitch": (x, origin + 0.0012),
        }

    class Annotation:
        def __init__(self, display, name):
            self.display, self.name = display, name
            self.position = (1.0, 1.0, 0.0)
            self.line_anchor = None
            self.moves = []
            self.omit_callout = False
            self.extra_lines = []

        def SetPosition2(self, x, y, z):
            self.moves.append((self.display.OffsetText, (x, y, z)))
            self.position = (x, y, z)
            if not self.display.OffsetText:
                self.line_anchor = (x, y)
            return True

        def GetPosition(self):
            return self.position

        def translate(self, dx, dy):
            x, y, z = self.position
            self.position = (x + dx, y + dy, z)
            if self.line_anchor is not None:
                x, y = self.line_anchor
                self.line_anchor = (x + dx, y + dy)

        def texts(self):
            extra = options.get("glyph_extra", 0.0)
            shift_x, shift_y = options.get("glyph_shift", (0.0, 0.0))
            callout = spec.SUPPLIER_REFERENCE_FORMATS[self.name][3]
            if self.name == "SupplierStockDiameter":
                rows = [
                    ("Ø8 mm", 0.004, -0.006, 0.012, math.pi / 2),
                    (callout, 0.0, -0.015 - extra / 2, 0.030 + extra, math.pi / 2),
                ]
            else:
                length = self.name == "SupplierStockLength"
                rows = [
                    ("600 mm" if length else "2 mm",
                     -0.007 if length else -0.004, 0.002, 0.014, 0.0),
                    (callout, -0.015 if length else -0.016,
                     (-0.004 if length else -0.005) - extra,
                     0.030 if length else 0.032, 0.0),
                ]
            x, y, z = self.position
            return [
                {"t": text, "pos": (x + rx + shift_x, y + ry + shift_y, z),
                 "h": 0.003, "w": width, "ang": angle, "ref": 1}
                for text, rx, ry, width, angle in rows[:1 if self.omit_callout else 2]
            ]

        def text_box(self):
            return draw.display_box({"texts": self.texts()})

        def lines(self):
            x, y = source_centers()[self.name]
            ax, ay = self.line_anchor
            text = self.text_box()
            if self.name == "SupplierStockDiameter":
                ends = ((x, y - 0.0004), (x, y + 0.0004))
                arrows = ((ax, ends[0][1]), (ax, ends[1][1]))
                leader = ((ax, y), (text.xmin, text.ymin))
            else:
                half = 0.030 if self.name == "SupplierStockLength" else 0.0001
                ends = ((x - half, y), (x + half, y))
                arrows = ((ends[0][0], ay), (ends[1][0], ay))
                leader = ((x, ay), (text.center()[0], text.ymin))
            segments = [*zip(ends, arrows, strict=True), arrows, leader, *self.extra_lines]
            return [
                [0.0, 0.0, 0.0, 0.0, a[0], a[1], 0.0, b[0], b[1], 0.0]
                for a, b in segments
            ]

    displays, annotations = {}, {}
    for name, _, _ in spec.SUPPLIER_REFERENCE_DIMENSIONS:
        display = SimpleNamespace(OffsetText=False)
        annotation = Annotation(display, name)
        display.GetAnnotation = lambda annotation=annotation: annotation
        displays[name], annotations[name] = display, annotation
    view.annotations = list(annotations.values())

    def annotation_geometry(_adapter, annotation):
        geometry_reads.append(annotation.name)
        return {"texts": annotation.texts(), "lines": annotation.lines()}, []

    def project(_adapter, native_view, points, **_kwargs):
        assert native_view is view
        projections.append(points)
        origin = view.Position[1] + view.curve_offset - 0.0004
        return [(view.Position[0] + x * 0.1, origin + y * 0.1) for x, y, _z in points]

    def placed(_adapter, source, orientation, *center, scale):
        assert source == str(draw.SOURCE) and orientation == "*Front"
        assert center == draw.SUPPLIER_STOCK_CENTER and scale == (1, 10)
        view.Position = center
        return view

    def capture(_adapter, native_draw, views, **kwargs):
        assert native_draw is drawing and views == {"*Front": view}
        assert kwargs["source"] == draw.SOURCE
        assert kwargs["model"] is view.ReferencedDocument
        assert kwargs["features"] == {"*Front": ("SupplierReference",)}
        assert kwargs["configurations"] == {
            "*Front": spec.SUPPLIER_STOCK_CONFIGURATION
        }
        events.append("capture")
        return {"*Front": "native capture"}

    def bounds(_adapter, native_view, **kwargs):
        assert native_view is view and kwargs["capture"] == "native capture"
        allowance_reads.append(kwargs["allow_presentation_dirty"])
        assert ("format" in events) == kwargs["allow_presentation_dirty"]
        view.UpdateViewDisplayGeometry()
        return view.reference_bounds()

    def annotate(_adapter, views, **kwargs):
        assert views == {"*Front": view} and events == ["capture"]
        assert kwargs["dimensions"] is spec.SUPPLIER_REFERENCE_DIMENSIONS
        assert kwargs["formats"] is spec.SUPPLIER_REFERENCE_FORMATS
        assert kwargs["starts"] is spec.SUPPLIER_REFERENCE_STARTS
        assert kwargs["units"] is spec.SUPPLIER_REFERENCE_UNITS
        events.append("format")
        kwargs["settled_checks"].append(lambda: events.append("source check"))
        return displays

    def reacquire(_adapter, views, **kwargs):
        assert views == {"*Front": view}
        assert kwargs["expected"] == {"*Front": {
            name: "SupplierReference" for name in displays
        }}
        assert kwargs["configurations"] == {
            "*Front": spec.SUPPLIER_STOCK_CONFIGURATION
        }
        reacquisitions.append("native inventory")
        return displays

    def add_caption(_adapter, text, *xy):
        assert text == draw.SUPPLIER_STOCK_CAPTION
        assert xy == draw.SUPPLIER_STOCK_CAPTION_XY
        return note

    def annotations_fit(_adapter, native_view, cell, **_kwargs):
        assert native_view is view
        annotation_cells.append(cell)
        for annotation in annotations.values():
            data, _refused = annotation_geometry(adapter, annotation)
            ink = draw.display_box(data)
            if not draw._inside((ink.xmin, ink.ymin, ink.xmax, ink.ymax), cell):
                raise RuntimeError("supplier annotation leaves its caption-free cell")

    monkeypatch.setattr(draw, "place_view", placed)
    monkeypatch.setattr(draw, "set_hidden_lines_removed", lambda *_args: None)
    monkeypatch.setattr(
        draw, "rebuild_drawing", lambda *_args, label: rebuilds.append(label)
    )
    monkeypatch.setattr(
        draw, "_show_hidden_owners",
        lambda _adapter, _view, owners, **_kwargs: list(owners),
    )
    monkeypatch.setattr(draw, "_capture_reference_views", capture)
    monkeypatch.setattr(draw, "_reference_view_bounds", bounds)
    monkeypatch.setattr(draw, "annotate_supplier_screw", annotate)
    monkeypatch.setattr(draw, "reacquire_supplier_dimensions", reacquire)
    monkeypatch.setattr(draw, "model_points_in_view", project)
    monkeypatch.setattr(draw, "annotation_display", annotation_geometry)
    monkeypatch.setattr(draw, "add_note", add_caption)
    monkeypatch.setattr(draw, "assert_supplier_annotations_fit", annotations_fit)
    state = SimpleNamespace(
        view=view, note=note, owner=caption_annotation, events=events,
        messages=messages, allowance_reads=allowance_reads,
        annotations=annotations, displays=displays, projections=projections,
        annotation_cells=annotation_cells, caption_position=caption_position,
        caption_moves=caption_moves, caption_extents=caption_extents,
        redraws=redraws, rebuilds=rebuilds, geometry_reads=geometry_reads,
        reacquisitions=reacquisitions, adapter=adapter,
    )

    def create():
        state.settled = draw._add_supplier_stock_inset(adapter)
        return state.settled

    state.create = create
    if not options.get("defer", False):
        create()
    return state


def test_supplier_stock_caption_seats_complete_extent_not_insertion_point(
    supplier_stock_inset,
) -> None:
    state = supplier_stock_inset
    before = draw._box(state.caption_extents[0], label="before", kind="note")
    after = draw._box(state.caption_extents[1], label="after", kind="note")
    assert before == pytest.approx((0.1412, 0.260, 0.2132, 0.269))
    assert not draw._inside(before, draw.SUPPLIER_STOCK_FIELD)
    assert after == pytest.approx((0.140, 0.255, 0.212, 0.264))
    assert draw._inside(after, draw.SUPPLIER_STOCK_FIELD)
    assert state.caption_moves == [pytest.approx((0.1388, 0.259, 0.007))]
    assert state.caption_moves[0][2] == 0.007
    assert state.note.GetText() == (
        "SUPPLIER NOMINAL STOCK GAUGES\nNOT PART SHAPE — SCALE 1:10"
    )


@pytest.mark.parametrize(
    "supplier_stock_inset",
    [
        {"fresh": fresh, "glyph_extra": extra, "glyph_shift": shift}
        for fresh in (False, True)
        for extra in (0.0, 0.0005, 0.001)
        for shift in ((0.0, 0.0), (0.006, -0.004))
    ],
    indirect=True,
)
def test_supplier_stock_jointly_places_actual_frame_and_complete_measured_glyphs(
    supplier_stock_inset,
) -> None:
    state = supplier_stock_inset
    state.settled()
    records = draw._measure_supplier_stock_dimensions(state.adapter, state.view)
    caption = draw._box(state.caption_extents[-1], label="caption", kind="note")
    ink_field = (0.135, 0.208, 0.245, caption[1] - draw.SUPPLIER_STOCK_CAPTION_GAP)
    assert draw._inside(state.view.GetOutline(), draw.SUPPLIER_STOCK_FIELD)
    assert draw._inside(state.view.reference_bounds(), ink_field)
    for name, record in records.items():
        ink = record["ink"]
        assert draw._inside((ink.xmin, ink.ymin, ink.xmax, ink.ymax), ink_field)
        assert record["display"].OffsetText is True
        assert len(record["data"]["texts"]) == 2  # Includes SetText(4), not just value.
        assert name in state.geometry_reads
    draw._assert_supplier_stock_clearance(records)
    assert len(state.view.moves) == 1  # One joint view translation, no fit/retry.
    assert state.events == ["capture", "format", "source check"]
    assert state.allowance_reads == [False, True, True, True]
    assert len(state.annotation_cells) == 2  # After movement and after final rebuild.
    assert state.redraws == ["redraw"] * 5  # Includes freshness after final rebuild.
    assert len(state.rebuilds) == 7  # Distinct source/format/measurement/move barriers.
    assert "supplier stock captured:" in state.messages[0]
    assert any("joint placement before:" in row for row in state.messages)
    assert "curve_frame_offset_m=" in state.messages[-1]
    frame, curves = state.view.GetOutline(), state.view.reference_bounds()
    offset_y = (curves[1] + curves[3] - frame[1] - frame[3]) / 2
    assert offset_y == pytest.approx(state.view.curve_offset)


def test_supplier_stock_shelves_use_complete_pitch_height_and_length_below_row(
    supplier_stock_inset,
) -> None:
    state = supplier_stock_inset
    records = draw._measure_supplier_stock_dimensions(state.adapter, state.view)
    pitch, length = records["SupplierThreadPitch"], records["SupplierStockLength"]
    diameter = records["SupplierStockDiameter"]
    assert state.projections == [[
        (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.012, 0.0),
    ]]
    assert pitch["text"].height == pytest.approx(0.010)
    assert length["text"].height == pytest.approx(0.009)
    length_line = state.annotations["SupplierStockLength"].line_anchor[1]
    assert length_line - pitch["text"].ymax == pytest.approx(draw.SUPPLIER_STOCK_PLACE_AIR)
    assert length["text"].ymin - length_line == pytest.approx(draw.SUPPLIER_STOCK_PLACE_AIR)
    assert diameter["text"].xmin - state.view.reference_bounds()[2] == pytest.approx(
        draw.SUPPLIER_STOCK_GAUGE_GAP + draw.SUPPLIER_STOCK_PLACE_AIR
    )


@pytest.mark.parametrize(
    "frame,expected",
    (
        # Recorded layout1859 frame and actual captured source bounds below.
        ((0.177012, 0.236512, 0.188988, 0.288688), (0.0, -0.026906)),
        # Synthetic refreshed frame centered on exactly those source curves.
        ((0.147412, 0.236112, 0.218588, 0.248888), (0.002794, -0.026706)),
    ),
)
def test_supplier_stock_joint_translation_uses_midpoint_of_both_actual_constraints(
    monkeypatch, frame, expected,
) -> None:
    monkeypatch.setattr(draw._telemetry, "info", lambda _message: None)
    curves = (0.153, 0.2417, 0.213, 0.2433)
    # Synthetic complete dimension footprints, not after-fix native export proof.
    records = {
        "SupplierStockLength": {"ink": draw.Box(0.153, 0.2421, 0.213, 0.2771)},
        "SupplierStockDiameter": {"ink": draw.Box(0.183, 0.2417, 0.227, 0.2773)},
        "SupplierThreadPitch": {"ink": draw.Box(0.167, 0.2433, 0.199, 0.2603)},
    }
    shift = draw._supplier_stock_translation(
        frame, curves, records, (0.140, 0.255, 0.212, 0.264)
    )
    assert shift == pytest.approx(expected)


def test_supplier_stock_joint_translation_refuses_incompatible_actual_envelopes(
    monkeypatch,
) -> None:
    messages = []
    monkeypatch.setattr(draw._telemetry, "info", messages.append)
    frame = (0.177012, 0.208, 0.188988, 0.265)
    curves = (0.153, 0.220, 0.213, 0.2216)
    # Both boxes individually fit their field sizes; their permitted moves do not intersect.
    records = {"SupplierStockLength": {"ink": draw.Box(0.153, 0.220, 0.213, 0.260)}}
    with pytest.raises(RuntimeError, match="no joint frame/ink translation") as error:
        draw._supplier_stock_translation(frame, curves, records, (0.14, 0.255, 0.212, 0.264))
    for key in (
        "source_curve_bounds_m=", "native_outline_m=", "curve_frame_offset_m=",
        "annotation_ink_m=", "caption_box_m=", "ink_field_m=",
        "permitted_dx_m=", "permitted_dy_m=",
    ):
        assert key in str(error.value) and key in messages[-1]


@pytest.mark.parametrize(
    "supplier_stock_inset", [{"glyph_extra": 0.002, "defer": True}], indirect=True
)
def test_supplier_stock_refuses_infeasible_measured_two_row_glyph_heights(
    supplier_stock_inset,
) -> None:
    state = supplier_stock_inset
    with pytest.raises(RuntimeError, match="no joint frame/ink translation"):
        state.create()
    assert "permitted_dx_m=" in state.messages[-1]
    assert "permitted_dy_m=" in state.messages[-1]
    assert "annotation_ink_m=" in state.messages[-1]


@pytest.mark.parametrize(
    "supplier_stock_inset", [{"move_annotations": False, "defer": True}], indirect=True
)
def test_supplier_stock_refuses_native_annotations_not_moving_with_owned_view(
    supplier_stock_inset,
) -> None:
    state = supplier_stock_inset
    with pytest.raises(RuntimeError, match="did not translate with its view"):
        state.create()
    assert any("joint placement before:" in row for row in state.messages)
    assert "source_curve_bounds_m=" in state.messages[-1]
    assert "curve_frame_offset_m=" in state.messages[-1]


@pytest.mark.parametrize("fault", ("text", "stroke"))
def test_supplier_stock_checks_pairwise_native_glyph_and_stroke_clearance(
    supplier_stock_inset, fault,
) -> None:
    state = supplier_stock_inset
    records = draw._measure_supplier_stock_dimensions(state.adapter, state.view)
    pitch = records["SupplierThreadPitch"]["text"]
    length = records["SupplierStockLength"]
    if fault == "text":
        length["text"] = pitch
        reason = "supplier text clearance"
    else:
        x, y = pitch.center()
        length["data"] = {"lines": [[0, 0, 0, 0, x, y, 0, x + 0.001, y, 0]]}
        reason = "supplier stroke/text clearance"
    with pytest.raises(RuntimeError, match=reason):
        draw._assert_supplier_stock_clearance(records)


def test_supplier_stock_final_stroke_collision_refuses_even_without_box_drift(
    supplier_stock_inset,
) -> None:
    state = supplier_stock_inset
    pitch = state.annotations["SupplierThreadPitch"].text_box()
    x, y = pitch.center()
    state.annotations["SupplierStockLength"].extra_lines.append(
        ((x, y), (x + 0.001, y))
    )
    with pytest.raises(RuntimeError, match="supplier stroke/text clearance"):
        state.settled()


def test_supplier_stock_requires_length_below_callout_native_glyphs(
    supplier_stock_inset,
) -> None:
    state = supplier_stock_inset
    state.annotations["SupplierStockLength"].omit_callout = True
    with pytest.raises(RuntimeError, match="incomplete native supplier text/ink"):
        state.settled()


@pytest.mark.parametrize(
    "fault", ("outline", "annotation", "caption", "text", "owner", "config", "scale")
)
def test_supplier_stock_final_guards_refuse_native_drift_and_caption_changes(
    supplier_stock_inset, fault,
) -> None:
    state = supplier_stock_inset
    if fault == "outline":
        state.view.outline_override = (0.150, 0.210, 0.220, 0.267)
    elif fault == "annotation":
        annotation = state.annotations["SupplierStockLength"]
        annotation.translate(0.001, 0.0)
    elif fault == "caption":
        state.note.GetExtent = lambda: (0.140, 0.260, 0.0, 0.212, 0.269, 0.0)
    elif fault == "text":
        state.note.GetText = lambda: draw.SUPPLIER_STOCK_CAPTION + " "
    elif fault == "owner":
        state.owner.OwnerType = 0
    elif fault == "config":
        state.view.ReferencedConfiguration = "Default"
    elif fault == "scale":
        state.view.ScaleRatio = (1, 20)
    with pytest.raises(RuntimeError) as error:
        state.settled()
    if fault not in ("config", "scale"):
        for key in ("source_curve_bounds_m=", "native_outline_m=", "caption_box_m=", "ink_field_m="):
            assert key in str(error.value) and key in state.messages[-1]


def test_supplier_stock_curve_caption_refusal_is_independent_of_native_outline(
    supplier_stock_inset,
) -> None:
    state = supplier_stock_inset
    curve_box = (0.150, 0.254, 0.210, 0.255)
    state.view.reference_bounds = lambda: curve_box
    assert draw._inside(state.view.GetOutline(), draw.SUPPLIER_STOCK_FIELD)
    with pytest.raises(RuntimeError, match="curves left their caption-free field") as error:
        state.settled()
    assert f"source_curve_bounds_m={curve_box!r}" in str(error.value)
    assert f"native_outline_m={state.view.GetOutline()!r}" in str(error.value)
    assert len(state.annotation_cells) == 1  # Final refusal precedes the annotation guard.


@pytest.fixture
def readonly_leadscrew_build(monkeypatch, tmp_path):
    """Only run the real build as far as its first main-dimension import."""
    source_path = tmp_path / "leadscrew-source.SLDPRT"
    source_path.write_bytes(b"original leadscrew source")
    state = SimpleNamespace(
        configuration="Installed", dirty=False, read_only=True,
        path=str(source_path), events=[], captured=False, presentation_hook=None,
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

    def inset(_adapter):
        assert not state.dirty and not state.captured
        state.events.append(("capture",))
        state.captured = True
        return lambda: None

    def first_format(_adapter, _view, **_kwargs):
        assert state.captured and not state.dirty
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
    monkeypatch.setattr(draw, "_add_supplier_stock_inset", inset)
    monkeypatch.setattr(draw, "curate_view_dimensions", first_format)
    return SimpleNamespace(
        adapter=adapter, state=state, source=source, path=source_path,
    )


def test_supplier_stock_build_captures_clean_before_source_formatting(
    readonly_leadscrew_build,
) -> None:
    seat = readonly_leadscrew_build
    with pytest.raises(RuntimeError, match="stop at first main formatting") as error:
        asyncio.run(draw.build(seat.adapter))
    assert error.value is seat.state.primary
    assert [event[0] for event in seat.state.events] == [
        "hash", "open", "drawing", "view", "view", "capture", "main format", "hash"
    ]
    assert seat.state.events[0] == seat.state.events[-1]
    assert supplier_screw_lane_plan(spec.SUPPLIER_REFERENCE_DIMENSIONS) == {
        "SupplierStockLength": ("top", 0.006),
        "SupplierStockDiameter": ("right", 0.006),
        "SupplierThreadPitch": ("bottom", 0.006),
    }


@pytest.mark.parametrize("configuration", ("", spec.SUPPLIER_STOCK_CONFIGURATION))
def test_leadscrew_refuses_noninstalled_saved_source_before_creating_views(
    readonly_leadscrew_build, configuration,
) -> None:
    seat = readonly_leadscrew_build
    seat.state.configuration = configuration
    with pytest.raises(RuntimeError, match="without an installed configuration active"):
        asyncio.run(draw.build(seat.adapter))
    assert [event[0] for event in seat.state.events] == ["hash", "open", "hash"]
    assert not seat.state.captured


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
            seat.state.configuration = spec.SUPPLIER_STOCK_CONFIGURATION
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
            seat.state.configuration = spec.SUPPLIER_STOCK_CONFIGURATION
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


def test_supplier_stock_field_and_neighbor_views_are_not_layout_escape_hatches() -> None:
    assert draw.SUPPLIER_STOCK_FIELD == (0.135, 0.208, 0.245, 0.265)
    assert draw.SUPPLIER_STOCK_SCALE == (1, 10)
    assert draw.SUPPLIER_STOCK_CENTER == (0.183, 0.2365)
    assert draw.SUPPLIER_STOCK_CAPTION_XY == (0.140, 0.264)
    assert draw.SUPPLIER_STOCK_CAPTION == (
        "SUPPLIER NOMINAL STOCK GAUGES\nNOT PART SHAPE — SCALE 1:10"
    )
    assert draw.MAIN_CENTER == (0.195, 0.160)
    assert [section.centre for section in draw.CLOCK_SECTIONS] == [
        (0.090, 0.235),
        (0.280, 0.235),
    ]
    assert draw._inside_sheet(draw.SUPPLIER_STOCK_FIELD)
    scale = draw.SECTION_SCALE[0] / draw.SECTION_SCALE[1] / 1000.0
    angle_reach = draw.CLOCK_ANGLE_TEXT_RADIUS_MM * scale + 0.006
    af_reach = draw.CLOCK_AF_TEXT_RADIUS_MM * scale + 0.006
    for section in draw.CLOCK_SECTIONS:
        x, y = section.centre
        neighbor = (x - angle_reach, y - angle_reach, x + angle_reach, y + af_reach)
        assert not draw._overlaps(draw.SUPPLIER_STOCK_FIELD, neighbor)
    assert (
        draw.MAIN_KEEP["CutLength"][1] + draw.TEXT_HALF_HEIGHT
        < draw.SUPPLIER_STOCK_FIELD[1]
    )


def test_notes_name_the_item_not_its_length_or_material() -> None:
    # The cut length is the dimension's, the material the title block's, and
    # no line prescribes a method (rule 7).
    assert draw.ITEM == "TR8X2 LEAD SCREW"
    assert "STAINLESS" not in draw.NOTES.upper()
    assert f"{spec.LENGTH:.0f}" not in draw.NOTES
    for name in ("Supplier", "Supplier SKUs"):
        assert property_link(name) in draw.NOTES
    assert len(draw.NOTES.splitlines()) == 3
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
    monkeypatch.setattr(
        trim_drawing, "dimension_name", lambda _adapter, annotation: annotation.name
    )
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
            DrivenState=2, SystemValue=nominal, Tolerance=tolerance
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
            None,
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
