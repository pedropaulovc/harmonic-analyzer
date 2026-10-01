"""Offline contracts for the transgear disc hub (MHA-159) and its drawing."""

from __future__ import annotations

import ast
import asyncio
import importlib.util
import itertools
import math
import re
from pathlib import Path

import pytest

import _common
import _config
import _printed_tolerance
import build_transgear_disc_hub as part
import draw_transgear_disc_hub as drawing
import transgear_disc_hub_geometry as joint
import transgear_disc_hub_spec as spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _layout_geometry import Box, estimate_text_box

WALL_FLOOR = 2.0
DRILL_PLUS = _config.title_block("drilled_hole")["plus_mm"]


def _row(places: int) -> float:
    """The ± the title block prints for a dimension shown at ``places``."""
    return float(str(_config.title_block(f"linear_{places}pl")["display"]).lstrip("±"))


def _places(name: str) -> int:
    return spec.DRAWING_PRECISION_BY_NAME[name]


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/transgear-disc-hub.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/transgear-disc-hub.pdf")
    assert (
        DRAWINGS_BY_NAME["transgear_disc_hub"].script
        == Path(drawing.__file__).resolve()
    )
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.END_KEEP) | set(drawing.SIDE_KEEP) == marked
    assert not set(drawing.END_KEEP) & set(drawing.SIDE_KEEP)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    # Each callout rides a dimension the sheet keeps.
    assert set(drawing.DIMENSION_CALLOUTS_BELOW) <= marked
    assert set(drawing.DIMENSION_CALLOUTS_ABOVE) <= marked


def test_the_sheet_prints_the_overall_and_the_flange_never_the_hub_body() -> None:
    """R9-5: the overall (flange rear to hub front) 9.400 and the flange
    2.400 are functional .XXX lengths; the hub body is their remainder and is
    not printed.  No oil-hole station prints either: the hole is centred on
    the hub body when it is match-drilled (R9-60)."""
    diameters = {"FlangeDia", "HubDia", "BoreDia", "BoltCircleDia", "ScrewHoleDia"}
    lengths = set(spec.DRAWING_PRECISION_BY_NAME) - diameters - {"OilHoleDia"}
    assert lengths == {"HubLength", "FlangeThick"}
    assert spec.HUB_LENGTH == pytest.approx(9.4) and _places("HubLength") == 3
    assert spec.FLANGE_THICK == pytest.approx(2.4) and _places("FlangeThick") == 3
    assert spec.BORE_DIA == pytest.approx(8.2) and _places("BoreDia") == 3
    assert spec.HUB_DIA == pytest.approx(12.9) and _places("HubDia") == 2


def test_only_the_press_bore_carries_a_model_band() -> None:
    """Every other size is governed by its printed places and the holes by
    the title block's DRILLED HOLES row (R9-45)."""
    assert model_toleranced_dimensions(part) == {
        ("BoreProfile", "BoreDia"): "*BORE_DEVIATIONS"
    }


def _printed_limits(build, spec_module, feature: str, name: str, nominal: float):
    """(least, greatest) size the sheet prints: the model band the build
    applies, else the title block's row for the dimension's places."""
    expr = model_toleranced_dimensions(build).get((feature, name))
    if expr is None:
        row = _row(spec_module.DRAWING_PRECISION_BY_NAME[name])
        return nominal - row, nominal + row
    lower, upper = getattr(build, expr.lstrip("*"))
    return nominal + lower, nominal + upper


def test_the_bore_keeps_its_press_on_the_sleeve_shank_at_every_printed_limit() -> None:
    """The flange's clamp on the disc and the disc's torque ride on this
    press alone; the two parts are made apart, each to its own sheet."""
    import build_transgear_feed_pinion as sleeve_part
    import transgear_feed_pinion_spec as sleeve

    bore = _printed_limits(part, spec, "BoreProfile", "BoreDia", spec.BORE_DIA)
    shank = _printed_limits(
        sleeve_part, sleeve, "SleeveProfile", "ShankDia", sleeve.SHANK_DIA
    )
    least, greatest = shank[0] - bore[1], shank[1] - bore[0]
    # Both at .XXX ±0.13 ran from 0.26 clearance to 0.26 interference.
    assert least >= 0.010 - 1e-9
    assert (least, greatest) == pytest.approx(spec.PRESS_INTERFERENCE)
    callout = " ".join(drawing.DIMENSION_CALLOUTS_BELOW["BoreDia"].split())
    assert f"{least:.3f}-{greatest:.3f} DIAMETRAL INTERFERENCE" in callout


def _sheet_text() -> str:
    return "\n".join(
        (
            spec.DRAWING_NOTES,
            *drawing.DIMENSION_CALLOUTS_BELOW.values(),
            *drawing.DIMENSION_CALLOUTS_ABOVE.values(),
        )
    )


def test_every_mate_the_sheet_cites_is_named_with_its_own_number() -> None:
    """Policy rule 2: every part number the sheet cites is a mate's, printed
    after that mate's name, and is the number the mate's own sheet carries."""
    name_by_number: dict[str, str] = {}
    for stem, name, number in (
        ("transgear-feed-pinion", spec.SLEEVE_NAME, spec.SLEEVE_NUMBER),
        ("transgear-disc-screw", spec.SCREW_NAME, spec.SCREW_NUMBER),
    ):
        assert _config.parts(stem)["number"] == number
        name_by_number[number] = name
    printed = " ".join(_sheet_text().split())
    cited = re.findall(r"MHA-\d+", printed)
    assert set(cited) == set(name_by_number)
    for number, name in name_by_number.items():
        assert printed.count(f"{name} {number}") == printed.count(number), number


def test_walls_hold_at_the_worst_case_the_sheet_prints() -> None:
    """Policy rule 12, recomputed from the title block's rows."""
    hub_wall = (
        (spec.HUB_DIA - _row(_places("HubDia"))) - (spec.BORE_DIA + spec.BORE_BAND[0])
    ) / 2.0
    oil_r = (spec.OIL_HOLE_DIA + DRILL_PLUS) / 2.0
    # The oil hole is centred on the shortest hub body the printed lengths
    # leave, give or take the centring at fit-up: the same ligament to the hub
    # front face and to the flange face.
    body_min = (spec.HUB_LENGTH - _row(_places("HubLength"))) - (
        spec.FLANGE_THICK + _row(_places("FlangeThick"))
    )
    oil_ligament = body_min / 2.0 - spec.OIL_HOLE_CENTRING_TOL - oil_r
    screw_r = (spec.SCREW_HOLE_DIA + DRILL_PLUS) / 2.0
    bc_r_min = joint.BOLT_CIRCLE_DIA / 2.0 - joint.BOLT_CIRCLE_POSITION_TOL
    hole_to_bore = bc_r_min - screw_r - (spec.BORE_DIA + spec.BORE_BAND[0]) / 2.0

    assert hub_wall == pytest.approx(2.0875, abs=0.005) and hub_wall >= WALL_FLOOR
    # Printed at .X from the front face it was 2.05 there but 1.79 to the
    # flange; centred, both sides keep 2.47.
    assert oil_ligament == pytest.approx(2.47, abs=0.005)
    assert oil_ligament >= WALL_FLOOR
    assert hole_to_bore >= WALL_FLOOR
    assert spec.HUB_WALL_WORST == pytest.approx(hub_wall, abs=1e-9)
    assert spec.OIL_HOLE_LIGAMENT_WORST == pytest.approx(oil_ligament, abs=1e-9)


def test_the_thin_rim_is_stated_on_the_sheet_at_its_worst_case() -> None:
    """The one shortfall (hole to rim) prints as a MIN note at the value the
    limits give, rounded down, and stays a shortfall."""
    worst = (
        (spec.FLANGE_DIA - _row(_places("FlangeDia"))) / 2.0
        - (joint.BOLT_CIRCLE_DIA / 2.0 + joint.BOLT_CIRCLE_POSITION_TOL)
        - (spec.SCREW_HOLE_DIA + DRILL_PLUS) / 2.0
    )
    printed = math.floor(worst * 100.0 + 1e-9) / 100.0
    assert 0.0 < printed < WALL_FLOOR
    assert f"SCREW HOLE TO RIM {printed:.2f} MIN." in spec.DRAWING_NOTES.splitlines()


def test_screw_heads_clear_the_hub_body() -> None:
    head = spec.SCREW_HEAD_DIA + spec.SCREW_HEAD_DIA_ALLOWANCE
    bc_r_min = joint.BOLT_CIRCLE_DIA / 2.0 - joint.BOLT_CIRCLE_POSITION_TOL
    clearance = bc_r_min - head / 2.0 - (spec.HUB_DIA + _row(_places("HubDia"))) / 2.0
    assert clearance > 0.0


def _spec_fresh():
    fresh_spec = importlib.util.spec_from_file_location("_hub_perturbed", spec.__file__)
    fresh = importlib.util.module_from_spec(fresh_spec)
    fresh_spec.loader.exec_module(fresh)
    return fresh


def test_the_wall_gate_refuses_a_coarser_printed_row(monkeypatch) -> None:
    # Positive control: the title block as it is.
    assert _spec_fresh().OIL_HOLE_LIGAMENT_WORST == pytest.approx(
        spec.OIL_HOLE_LIGAMENT_WORST
    )
    # Negative control: rows loose enough to thin a wall under 2.0.
    monkeypatch.setattr(_printed_tolerance, "printed_band_mm", lambda _places: 1.0)
    with pytest.raises(AssertionError, match="floor"):
        _spec_fresh()


def test_the_oil_hole_is_centred_on_the_hub_body_the_lengths_leave() -> None:
    """R9-8 / R9-60: Ø1.2 on the drilled row, match-drilled through hub and
    sleeve after pressing and centred on the hub body, so its station behind
    the hub front face follows the printed lengths, not a band of its own."""
    assert spec.OIL_HOLE_DIA == pytest.approx(1.2)
    assert spec.OIL_HOLE_STATION == pytest.approx(3.5)
    body = (
        (spec.HUB_LENGTH - _row(_places("HubLength")))
        - (spec.FLANGE_THICK + _row(_places("FlangeThick"))),
        (spec.HUB_LENGTH + _row(_places("HubLength")))
        - (spec.FLANGE_THICK - _row(_places("FlangeThick"))),
    )
    assert spec.OIL_HOLE_STATION == pytest.approx(sum(body) / 4.0)
    assert spec.OIL_HOLE_STATION_RANGE == pytest.approx(
        (
            body[0] / 2.0 - spec.OIL_HOLE_CENTRING_TOL,
            body[1] / 2.0 + spec.OIL_HOLE_CENTRING_TOL,
        )
    )


def test_sheet_text_states_facts_not_governance() -> None:
    for word in ("EXCEPTION", "ACCEPTED", "RULING", "POLICY", "BOOK FIDELITY"):
        assert word not in _sheet_text().upper()
    notes = spec.DRAWING_NOTES.splitlines()
    assert len(notes) <= 4
    assert [line for line in notes if len(line) > 70] == []


# Dimension text as the fleet's sheets print it: 3.5 mm caps, the advance and
# line pitch measured on the arbor-pedestal sheet (test_arbor_pedestal_drawing).
_CAP_M = 0.0035
_ADVANCE = 109.7 / (42 * 3.5)
_LINE_SPACING = 16.8 * 25.4 / 72.0 / 3.5
_NOMINAL = {
    "FlangeDia": spec.FLANGE_DIA,
    "HubDia": spec.HUB_DIA,
    "HubLength": spec.HUB_LENGTH,
    "FlangeThick": spec.FLANGE_THICK,
    "BoreDia": spec.BORE_DIA,
    "BoltCircleDia": joint.BOLT_CIRCLE_DIA,
    "ScrewHoleDia": spec.SCREW_HOLE_DIA,
    "OilHoleDia": spec.OIL_HOLE_DIA,
}


def _printed_box(name: str, anchor: tuple[float, float]) -> Box:
    """The estimated box of a kept dimension's whole text, centred on its
    text point: value (the bore's with its upper limit) and callouts."""
    value = f"{_NOMINAL[name]:.{_places(name)}f}"
    if name.endswith("Dia"):
        value = f"\u00d8{value}"
    if name == "BoreDia":
        value += f" +{spec.BORE_BAND[0]:.3f}"
    lines = [
        drawing.DIMENSION_CALLOUTS_ABOVE.get(name),
        value,
        drawing.DIMENSION_CALLOUTS_BELOW.get(name),
    ]
    box = estimate_text_box(
        "\n".join(line for line in lines if line),
        anchor=anchor,
        height=_CAP_M,
        reference=2,
        advance_ratio=_ADVANCE,
        line_spacing=_LINE_SPACING,
    )
    assert box is not None
    return box


def test_turned_diameters_print_inline_beside_their_own_step_on_the_edge_view() -> None:
    """Policy rule 7: the turned diameters sit on the edge view, not leader-
    piled through the face view's centre, each inline between its own
    extension lines and off the part; the face view keeps the bore and the
    holes; no two texts on the sheet print over each other."""
    s = drawing._S
    axis_y = drawing.SIDE_CENTER[1]
    edge = Box(
        drawing.HUB_FRONT_X,
        axis_y - spec.FLANGE_DIA / 2.0 * s,
        drawing.FLANGE_REAR_X,
        axis_y + spec.FLANGE_DIA / 2.0 * s,
    )
    flange_r = spec.FLANGE_DIA / 2.0 * s

    def face_gap(box: Box) -> float:
        """Clearance from ``box`` to the face view's flange circle."""
        cx, cy = drawing.END_CENTER
        nearest_x = min(max(cx, box.xmin), box.xmax)
        nearest_y = min(max(cy, box.ymin), box.ymax)
        return math.hypot(nearest_x - cx, nearest_y - cy) - flange_r

    assert set(drawing.END_KEEP) == {"BoreDia", "BoltCircleDia", "ScrewHoleDia"}
    boxes = {
        name: _printed_box(name, anchor)
        for keep in (drawing.END_KEEP, drawing.SIDE_KEEP)
        for name, anchor in keep.items()
    }
    for name, diameter in (("HubDia", spec.HUB_DIA), ("FlangeDia", spec.FLANGE_DIA)):
        half = diameter / 2.0 * s
        assert axis_y - half < boxes[name].ymin, name
        assert boxes[name].ymax < axis_y + half, name
    for name in drawing.SIDE_KEEP:
        assert boxes[name].gap(edge) >= 0.004, name
    for name in drawing.END_KEEP:
        assert face_gap(boxes[name]) >= 0.004, name
    # The oil hole's callout stays under the flange's O.D. extension line.
    assert boxes["OilHoleDia"].ymax < edge.ymin
    clashes = [
        (a, b)
        for a, b in itertools.combinations(sorted(boxes), 2)
        if boxes[a].overlaps(boxes[b], tol=0.0)
    ]
    assert clashes == []


class _FakeSketchManager:
    AddToDB = False


class _FakeSolidWorks:
    """Just enough of the adapter for the recipe's own calls; it keeps the
    lines and circles the recipe draws."""

    def __init__(self) -> None:
        self.currentSketchManager = _FakeSketchManager()
        self._n = 0
        self.lines: dict[str, tuple[float, ...]] = {}
        self.circles: list[tuple[float, ...]] = []

    async def _entity(self, *_args, **_kwargs) -> str:
        self._n += 1
        return f"Entity{self._n}"

    async def add_line(self, *args) -> str:
        line = await self._entity()
        self.lines[line] = args
        return line

    async def add_circle(self, *args) -> str:
        self.circles.append(args)
        return await self._entity()

    create_part = create_sketch = exit_sketch = _entity
    create_extrusion = create_cut_extrude = create_revolve = _entity
    add_centerline = add_sketch_constraint = add_sketch_dimension = _entity


def _drive_value(expr: str, globals_mm: dict[str, float]) -> float:
    text = re.sub(r'"(\w+)"', lambda m: repr(globals_mm[m.group(1)]), expr)
    return float(eval(text, {"__builtins__": {}}, {}))  # noqa: S307 -- test-local arithmetic


def test_every_drive_equation_reproduces_the_modelled_geometry(monkeypatch) -> None:
    """Every drive equation (bolt-circle factors included) evaluates to the
    size, centre or length the recipe draws, so a rebuild after the drives
    moves nothing: the screw holes stay on the joint's shared pattern, the
    turned profile on its printed sizes, the oil hole centred on the body."""
    globals_mm: dict[str, float] = {}
    circles: list[tuple] = []
    chains: list[list[str]] = []
    diametric: dict[str, str] = {}
    rows: dict[int, list[tuple[str | None, str | None]]] = {}
    drives: dict[str, dict[str | None, str | None]] = {}

    async def set_global(_adapter, name, value):
        globals_mm[name] = float(value.removesuffix("mm"))

    async def define_circle(_adapter, x, y, radius, label, *, dims, names, drives):
        circles.append((label, x, y, radius, names, drives))
        return label

    real_chain = part.add_line_chain

    async def add_line_chain(adapter, points, close=True):
        chains.append(await real_chain(adapter, points, close))
        return chains[-1]

    async def add_diametric(_adapter, _axis, line, _text_xy, label):
        diametric[label] = line

    def record(self, name, drive=None):
        rows.setdefault(id(self), []).append((name, drive))

    def apply(self, _adapter, feature):
        drives[feature] = dict(rows.get(id(self), []))
        return []

    async def quiet(*_args, **_kwargs):
        return None

    def names(_adapter, feature, dim_names):
        return [f"{name}@{feature}" for name in dim_names]

    monkeypatch.setattr(part, "set_global", set_global)
    monkeypatch.setattr(part, "define_circle", define_circle)
    monkeypatch.setattr(part, "add_line_chain", add_line_chain)
    monkeypatch.setattr(part, "add_diametric_linear_dimension", add_diametric)
    monkeypatch.setattr(_common.SketchDims, "record", record)
    monkeypatch.setattr(_common.SketchDims, "apply", apply)
    monkeypatch.setattr(_common, "check", lambda _label, result: result)
    monkeypatch.setattr(part, "check", lambda _label, result: result)
    monkeypatch.setattr(part, "name_dimensions", names)
    monkeypatch.setattr(part, "name_bore_axis", lambda *a, **k: _async("Axis1"))
    for helper in (
        "volume_check",
        "bbox_extent_check",
        "ensure_fully_defined",
        "anchor_point_to_origin",
        "dimension_between",
        "force_rebuild",
        "drive_dimension",
        "apply_material",
        "report_mass_properties",
        "save_part_and_images",
    ):
        monkeypatch.setattr(part, helper, quiet)
    for helper in (
        "name_last_feature",
        "set_sketch_direct_db",
        "_as_construction",
        "_check_z_span",
        "set_dimension_bilateral_tolerance",
        "apply_drawing_precision",
        "clear_dimensions_for_drawing",
        "mark_dimensions_for_drawing",
        "apply_drawing_properties",
    ):
        monkeypatch.setattr(part, helper, lambda *a, **k: None)

    fake = _FakeSolidWorks()
    asyncio.run(part.build(fake))

    def value(feature: str, name: str) -> float:
        return _drive_value(drives[feature][name], globals_mm)

    # Turned profile: each diameter twice its step's radius, the flange's
    # thickness the run of its O.D., the overall the profile's reach.
    (profile,) = chains
    flange_u, flange_v0, _u, flange_v1 = fake.lines[diametric["FlangeDia"]]
    hub_u, *_hub = fake.lines[diametric["HubDia"]]
    drawn = {
        "FlangeDia": 2.0 * flange_u,
        "HubDia": 2.0 * hub_u,
        "FlangeThick": abs(flange_v1 - flange_v0),
        "HubLength": max(max(fake.lines[line][1::2]) for line in profile),
    }
    assert set(drives["HubProfile"]) == set(drawn)
    for name, size in drawn.items():
        assert value("HubProfile", name) == pytest.approx(size, abs=1e-9), name
    assert drawn["FlangeDia"] == pytest.approx(spec.FLANGE_DIA)
    assert drawn["HubLength"] == pytest.approx(spec.HUB_LENGTH)

    # Oil hole: the station line runs from the hub front face to the hole's
    # centre, half the hub body behind it.
    (station,) = set(fake.lines) - set(profile)
    _u0, front_v, _u1, hole_v = fake.lines[station]
    ((_cu, centre_v, oil_r),) = fake.circles
    assert centre_v == pytest.approx(hole_v)
    assert value("OilHoleProfile", "OilHoleDatum") == pytest.approx(front_v)
    assert value("OilHoleProfile", "OilHoleStation") == pytest.approx(front_v - hole_v)
    assert value("OilHoleProfile", "OilHoleStation") == pytest.approx(
        (spec.HUB_LENGTH - spec.FLANGE_THICK) / 2.0
    )
    assert value("OilHoleProfile", "OilHoleDia") == pytest.approx(2.0 * oil_r)

    holes = [c for c in circles if c[0].startswith("screw hole")]
    drawn_holes = [v for _label, x, y, *_rest in holes for v in (x, y)]
    assert drawn_holes == pytest.approx([v for xy in joint.screw_centres() for v in xy])
    checked = 0
    for label, x, y, radius, _names, (d_x, d_y, d_size) in circles:
        for emitted, drive in ((abs(x), d_x), (abs(y), d_y), (2.0 * radius, d_size)):
            if emitted < 1e-9:
                continue
            assert drive is not None, (label, emitted)
            assert _drive_value(drive, globals_mm) == pytest.approx(
                emitted, abs=1e-9
            ), (
                label,
                drive,
            )
            checked += 1
    # Two on-axis diameters (bore, bolt circle), three hole sizes, five
    # non-zero hole centres.
    assert checked == 2 + 3 + 5


async def _async(value):
    return value


def test_registry_row_is_the_turned_brass_mha_159() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-159"
    assert int(row["quantity"]) == 1
    assert "C36000" in row["material_specification"]
    assert row["material"] == part.MATERIAL
    assert row["tolerance_class"] == "machined_block"


def _calls(path: str) -> dict[str, ast.Call]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return {
        node.func.id: node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_the_part_carries_every_property_its_drawing_requires(monkeypatch) -> None:
    """The drawing refuses a source part missing a required property; every
    one must be carried and non-blank."""
    import _drawing_marks

    required = ast.literal_eval(
        next(
            k.value
            for k in _calls(drawing.__file__)["read_required_properties"].keywords
            if k.arg == "required"
        )
    )
    carried = dict(_common.part_properties(part.PART_NAME))
    stamp = _calls(part.__file__)["apply_drawing_properties"]
    extra = ast.literal_eval(
        ast.unparse(stamp.args[2]).replace("DRAWING_NOTES", repr(spec.DRAWING_NOTES))
    )
    stamped: dict[str, str] = {}
    monkeypatch.setattr(
        _drawing_marks,
        "apply_custom_properties",
        lambda _adapter, props: stamped.update(props),
    )
    _drawing_marks.apply_drawing_properties(None, part.PART_NAME, extra)
    carried.update(stamped)
    assert [name for name in required if not str(carried.get(name) or "").strip()] == []
