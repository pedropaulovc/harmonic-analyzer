"""Offline contracts for the transgear stud (MHA-082) and its drawing."""

from __future__ import annotations

import ast
import importlib.util
import re
from pathlib import Path

import pytest

import _config
import build_transgear_stub as part
import draw_transgear_stub as drawing
import transgear_arm_geometry as arm
import transgear_stub_spec as spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout
from _fit_limits import SHAFT_H
from _hole_spec import THREAD_MAJOR_MM
from _printed_tolerance import drilled_oversize_mm, printed_band_mm
from _surface_finish import MACHINED_UM

SW_TOL_MAX = 6  # swTolType_e.swTolMAX


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/transgear-stub.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/transgear-stub.pdf")
    assert drawing.PNG.as_posix().endswith("/png/transgear-stub_drawing.png")
    row = DRAWINGS_BY_NAME["transgear_stub"]
    assert row.script == Path(drawing.__file__).resolve()
    assert row.layout is DrawingLayout.LANDSCAPE
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_every_marked_dimension_prints_once_with_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.SIDE_KEEP) == marked
    assert {
        (feature, name)
        for feature, names in spec.DRAWING_PRECISION.items()
        for name in names
    } == {
        (feature, name)
        for feature, names in spec.DRAWING_DIMENSIONS.items()
        for name in names
    }


def test_only_the_functional_sizes_carry_model_bands() -> None:
    """The journal's running fit, its length (the cluster float) and the
    relief width (the 1.0-1.2 window) carry native bands from the spec; every
    other size prints its places and the title block governs it."""
    assert model_toleranced_dimensions(part) == {
        ("StudProfile", "JournalDia"): "*deviations(JOURNAL_DIA_BAND)",
        ("StudProfile", "JournalLength"): "JOURNAL_LENGTH_TOL",
        ("StudProfile", "ReliefWidth"): "RELIEF_WIDTH_TOL",
    }
    assert spec.JOURNAL_DIA_BAND == SHAFT_H
    assert spec.DRAWING_PRECISION_BY_NAME["JournalDia"] == 3
    assert spec.DRAWING_PRECISION_BY_NAME["JournalLength"] == 2


def test_thread_relief_prints_a_max_under_the_thread_root() -> None:
    """swTolMAX prints the nominal then MAX, so the nominal is the band's top;
    that top stays under the #6-32 basic root and the 2A minor, and the width
    window charges the cap engagement at most 1.2."""
    assert spec.RELIEF_DIA_TOL_TYPE == SW_TOL_MAX
    assert spec.RELIEF_DIA == spec.RELIEF_DIA_MAX
    assert spec.RELIEF_DIA_MAX < spec.FRONT_THREAD_ROOT_BASIC
    assert spec.RELIEF_DIA_MAX < spec.FRONT_THREAD_MINOR_UNR_2A
    assert 1.0 <= spec.RELIEF_WIDTH_MIN < spec.RELIEF_WIDTH_MAX <= 1.2


@pytest.mark.parametrize(
    ("station", "machine_z"),
    [
        (0.0, -124.4),
        (spec.SLEEVE_THRUST_STATION, -134.9),
        (spec.CAP_SHOULDER_STATION, -157.8),
        (spec.TIP_STATION, -166.1),
    ],
)
def test_cluster_interfaces_sit_at_their_machine_stations(
    station: float, machine_z: float
) -> None:
    assert spec.ARM_SEAT_MACHINE_Z - station == pytest.approx(machine_z, abs=1e-9)


def test_journal_length_is_the_step_to_shoulder_span() -> None:
    assert spec.CAP_SHOULDER_STATION - spec.SLEEVE_THRUST_STATION == pytest.approx(
        spec.JOURNAL_LENGTH
    )
    assert spec.JOURNAL_LENGTH_MAX - spec.JOURNAL_LENGTH_MIN == pytest.approx(
        2.0 * spec.JOURNAL_LENGTH_TOL
    )


def test_rear_thread_engages_the_arm_at_least_one_and_a_half_diameters() -> None:
    assert spec.REAR_ENGAGEMENT_WORST_D >= spec.ENGAGEMENT_RULE_D
    assert spec.REAR_ENGAGEMENT_WORST <= spec.REAR_ENGAGEMENT_NOMINAL
    # The face relief lets the thread run to the collar face without cutting
    # through the collar wall.
    assert spec.FACE_RELIEF_DIA_MIN > spec.REAR_THREAD_MAJOR
    assert spec.COLLAR_WALL_WORST >= 2.0


# R9-5: the screw-cutting run-out at 32 tpi.
_RUNOUT = 1.0


def _rear_engagement_corner(relief_depth: float) -> tuple[float, float]:
    """(relief depth minimum, worst #10-32 engagement) from the printed rows:
    the relief depth and thread length at their sheet places, the arm's
    5/16 stock band, and its Ø5.0 countersinks at the drilled-hole plus."""
    places = spec.DRAWING_PRECISION["StudProfile"]
    depth_min = relief_depth - printed_band_mm(places["FaceReliefDepth"])
    thread_min = spec.REAR_THREAD_LENGTH - printed_band_mm(places["RearThreadLength"])
    major = THREAD_MAJOR_MM["#10-32"]
    csk = (arm.STUD_TAP_CSK_DIA + drilled_oversize_mm() - major) / 2.0
    run_out_in_arm = max(0.0, _RUNOUT - depth_min)
    arm_min = arm.THICKNESS - arm.THICKNESS_BAND
    return depth_min, min(thread_min, arm_min - csk) - max(csk, run_out_in_arm)


def test_face_relief_holds_the_run_out_and_full_thread_keeps_one_and_a_half_d() -> None:
    major = THREAD_MAJOR_MM["#10-32"]
    depth_min, worst = _rear_engagement_corner(spec.FACE_RELIEF_DEPTH)
    assert depth_min >= _RUNOUT
    assert worst >= 1.5 * major
    assert worst == pytest.approx(spec.REAR_ENGAGEMENT_WORST, abs=1e-6)
    # The 1.00 relief left 0.51 of run-out in the arm's tap at its 0.49
    # minimum: 6.98 = 1.45D of full thread.
    old_min, old_worst = _rear_engagement_corner(1.00)
    assert old_min < _RUNOUT
    assert old_worst < 1.5 * major


@pytest.mark.parametrize(
    ("depth", "refusal"),
    [
        # The old relief: its run-out overflow outgrows the countersink.
        ("1.00", r"engagement in the arm 6\.980 = 1\.446D"),
        # Engagement survives (0.11 overflow < 0.137 csk) but the run-out
        # still stands proud of the seat face.
        ("1.40", r"0\.89 minimum does not hold the 1\.0 run-out"),
    ],
)
def test_spec_refuses_a_relief_too_shallow_for_the_run_out(
    depth: str, refusal: str
) -> None:
    source = Path(spec.__file__).read_text(encoding="utf-8")
    shallow, count = re.subn(
        r"^FACE_RELIEF_DEPTH = .*$", f"FACE_RELIEF_DEPTH = {depth}", source, flags=re.M
    )
    assert count == 1
    module = importlib.util.module_from_spec(
        importlib.util.spec_from_loader("_stub_spec_shallow", loader=None)
    )
    with pytest.raises(AssertionError, match=refusal):
        exec(compile(shallow, spec.__file__, "exec"), module.__dict__)


def test_the_journal_carries_the_one_machined_finish() -> None:
    (journal,) = spec.SURFACE_FINISHES
    assert journal.key == "journal"
    assert journal.roughness_um == MACHINED_UM
    assert journal.face.diameter_mm == spec.JOURNAL_DIA
    assert (
        spec.SLEEVE_THRUST_STATION
        < journal.face.contains_z_mm
        < spec.CAP_SHOULDER_STATION
    )


def test_registry_row_is_the_turned_steel_mha_082() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-082"
    assert int(row["quantity"]) == 1
    assert "12L14" in row["material_specification"]
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
    import _common
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
    assert [ast.unparse(a) for a in stamp.args[:2]] == ["adapter", "PART_NAME"]
    extra = {
        ast.literal_eval(key): getattr(part, value.id)
        for key, value in zip(stamp.args[2].keys, stamp.args[2].values, strict=True)
    }
    stamped: dict[str, str] = {}
    monkeypatch.setattr(
        _drawing_marks,
        "apply_custom_properties",
        lambda _adapter, props: stamped.update(props),
    )
    _drawing_marks.apply_drawing_properties(None, part.PART_NAME, extra)
    carried.update(stamped)
    assert [name for name in required if not str(carried.get(name) or "").strip()] == []
    assert carried["Manufacturing Notes"] == spec.DRAWING_NOTES
    assert carried["Isometric View Note"] == spec.ISOMETRIC_VIEW_NOTE
