"""Offline contracts for the transgear disc hub (MHA-159) and its drawing."""

from __future__ import annotations

import ast
import asyncio
import importlib.util
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
    not printed.  The only other axial size is the oil-hole station."""
    diameters = {"FlangeDia", "HubDia", "BoreDia", "BoltCircleDia", "ScrewHoleDia"}
    lengths = set(spec.DRAWING_PRECISION_BY_NAME) - diameters - {"OilHoleDia"}
    assert lengths == {"HubLength", "FlangeThick", "OilHoleStation"}
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
    callout = drawing.DIMENSION_CALLOUTS_BELOW["BoreDia"]
    assert f"{least:.3f}-{greatest:.3f} DIAMETRAL INTERFERENCE" in callout
    assert f"PRESS ON {sleeve.SLEEVE_NUMBER} SHANK" in callout


def test_walls_hold_at_the_worst_case_the_sheet_prints() -> None:
    """Policy rule 12, recomputed from the title block's rows."""
    hub_wall = (
        (spec.HUB_DIA - _row(_places("HubDia"))) - (spec.BORE_DIA + spec.BORE_BAND[0])
    ) / 2.0
    oil_r = (spec.OIL_HOLE_DIA + DRILL_PLUS) / 2.0
    station_band = _row(_places("OilHoleStation"))
    oil_to_front = spec.OIL_HOLE_STATION - station_band - oil_r
    oil_to_flange = (
        (spec.HUB_LENGTH - _row(_places("HubLength")))
        - (spec.FLANGE_THICK + _row(_places("FlangeThick")))
        - (spec.OIL_HOLE_STATION + station_band)
        - oil_r
    )
    screw_r = (spec.SCREW_HOLE_DIA + DRILL_PLUS) / 2.0
    bc_r_min = joint.BOLT_CIRCLE_DIA / 2.0 - joint.BOLT_CIRCLE_POSITION_TOL
    hole_to_bore = bc_r_min - screw_r - (spec.BORE_DIA + spec.BORE_BAND[0]) / 2.0

    assert hub_wall == pytest.approx(2.0875, abs=0.005) and hub_wall >= WALL_FLOOR
    assert oil_to_front == pytest.approx(2.05, abs=0.005) and oil_to_front >= WALL_FLOOR
    assert hole_to_bore >= WALL_FLOOR
    # Toward the flange the hole edge meets the flange face: an edge
    # distance, but the hole must never break into the flange.
    assert oil_to_flange > 0.0
    assert spec.HUB_WALL_WORST == pytest.approx(hub_wall, abs=1e-9)
    assert spec.OIL_HOLE_TO_FRONT_WORST == pytest.approx(oil_to_front, abs=1e-9)
    assert spec.OIL_HOLE_TO_FLANGE_WORST == pytest.approx(oil_to_flange, abs=1e-9)


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
    assert _spec_fresh().OIL_HOLE_TO_FRONT_WORST == pytest.approx(
        spec.OIL_HOLE_TO_FRONT_WORST
    )
    # Negative control: rows loose enough to thin a wall under 2.0.
    monkeypatch.setattr(_printed_tolerance, "printed_band_mm", lambda _places: 1.0)
    with pytest.raises(AssertionError, match="floor"):
        _spec_fresh()


def test_oil_hole_is_match_drilled_through_the_pressed_sleeve() -> None:
    """R9-8: Ø1.2 on the drilled row, 3.5 at .X from the hub front face,
    drilled through hub and sleeve together after pressing."""
    assert spec.OIL_HOLE_DIA == pytest.approx(1.2)
    assert spec.OIL_HOLE_STATION == pytest.approx(3.5)
    assert _places("OilHoleStation") == 1
    lines = spec.OIL_HOLE_CALLOUT_BELOW.splitlines()
    assert lines[0] == f"MATCH DRILL AT ASSY WITH {spec.SLEEVE_NUMBER}"
    assert spec.SLEEVE_NUMBER == "MHA-110"
    assert "SLEEVE" in lines[1] and "AFTER PRESSING" in lines[1]
    assert drawing.DIMENSION_CALLOUTS_BELOW["OilHoleDia"] == spec.OIL_HOLE_CALLOUT_BELOW


def test_sheet_text_states_facts_not_governance() -> None:
    printed = "\n".join(
        (
            spec.DRAWING_NOTES,
            *drawing.DIMENSION_CALLOUTS_BELOW.values(),
            *drawing.DIMENSION_CALLOUTS_ABOVE.values(),
        )
    )
    for word in ("EXCEPTION", "ACCEPTED", "RULING", "POLICY", "BOOK FIDELITY"):
        assert word not in printed.upper()


class _FakeSketchManager:
    AddToDB = False


class _FakeSolidWorks:
    """Just enough of the adapter for the recipe's own calls."""

    def __init__(self) -> None:
        self.currentSketchManager = _FakeSketchManager()
        self._n = 0

    async def _entity(self, *_args, **_kwargs) -> str:
        self._n += 1
        return f"Entity{self._n}"

    create_part = create_sketch = exit_sketch = _entity
    create_extrusion = create_cut_extrude = _entity
    add_line = add_circle = add_sketch_constraint = add_sketch_dimension = _entity


def _drive_value(expr: str, globals_mm: dict[str, float]) -> float:
    text = re.sub(r'"(\w+)"', lambda m: repr(globals_mm[m.group(1)]), expr)
    return float(eval(text, {"__builtins__": {}}, {}))  # noqa: S307 -- test-local arithmetic


def test_hole_and_diameter_equations_reproduce_the_modelled_geometry(
    monkeypatch,
) -> None:
    """Every circle's drive equation (bolt-circle factors included) evaluates
    to the size and centre the recipe draws, so a rebuild after the drives
    moves nothing -- the screw holes stay on the joint's shared pattern."""
    globals_mm: dict[str, float] = {}
    circles: list[tuple] = []

    async def set_global(_adapter, name, value):
        globals_mm[name] = float(value.removesuffix("mm"))

    async def define_circle(_adapter, x, y, radius, label, *, dims, names, drives):
        circles.append((label, x, y, radius, names, drives))
        return label

    async def quiet(*_args, **_kwargs):
        return None

    def names(_adapter, feature, dim_names):
        return [f"{name}@{feature}" for name in dim_names]

    monkeypatch.setattr(part, "set_global", set_global)
    monkeypatch.setattr(part, "define_circle", define_circle)
    monkeypatch.setattr(_common.SketchDims, "apply", lambda self, _a, _f: [])
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

    asyncio.run(part.build(_FakeSolidWorks()))

    holes = [c for c in circles if c[0].startswith("screw hole")]
    drawn = [v for _label, x, y, *_rest in holes for v in (x, y)]
    assert drawn == pytest.approx([v for xy in joint.screw_centres() for v in xy])
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
    # Four on-axis diameters, three hole sizes, five non-zero hole centres.
    assert checked == 4 + 3 + 5


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
