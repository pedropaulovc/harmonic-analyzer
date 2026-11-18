"""Offline contracts for the MHA-PD-VN-57 transgear pivot screw.

Recorded recipe calls are not native geometry proof; the farm build and the
sheet's machinist review own that.
"""

from __future__ import annotations

import contextlib
import math
from pathlib import Path

import pytest

from _column_clamp_interface import BAR_DEPTH
import _config
import _telemetry
import build_pd_vn_transgear_pivot_screw as part
import draw_pd_vn_transgear_pivot_screw as drawing
import pd_support_bar_spec as bar
import transgear_hanger_joints as joints
import pd_vn_transgear_pivot_screw_spec as screw
from _buildgraph import module_deps_of
from _drawing_registry import DRAWINGS_BY_NAME
from _printed_tolerance import angular_band_deg
from diagnostics import diag_build_90325A174 as entry

IN = 25.4
SCRIPTS = Path(__file__).resolve().parent
UNDERHEAD = screw.SHOULDER_LEN + screw.THREAD_LEN


def test_spec_is_the_catalogue_screw() -> None:
    """90325A174 per mcmaster.com (2026-10-14): shoulder Ø3/16 x 1/2,
    8-32 UNC-2A x 3/8, hex-socket head Ø5/16 x 5/32, 3/32 drive."""
    assert screw.SKU == "90325A174"
    assert screw.CATALOG_URL == "https://www.mcmaster.com/90325A174/"
    assert screw.CATALOG_CHECKED_DATE == "2026-10-14"
    assert screw.SHOULDER_DIA == pytest.approx(3.0 / 16.0 * IN)
    assert screw.SHOULDER_LEN == pytest.approx(0.5 * IN)
    assert screw.THREAD == "#8-32"
    assert screw.THREAD_MAJOR == pytest.approx(0.164 * IN)
    assert screw.PITCH == pytest.approx(IN / 32.0)
    assert screw.THREAD_LEN == pytest.approx(3.0 / 8.0 * IN)
    # ASME B18.3-2012 Table 13 note 12: -0.020 in on the thread length.
    assert screw.THREAD_LEN_LIMITS == pytest.approx((-0.020 * IN, 0.0))
    assert screw.STOCK_THREAD_LEN_MIN == pytest.approx(9.017)
    assert screw.HEAD_DIA == pytest.approx(5.0 / 16.0 * IN)
    assert screw.HEAD_H == pytest.approx(5.0 / 32.0 * IN)
    assert screw.SOCKET_AF == pytest.approx(3.0 / 32.0 * IN)


def test_catalogue_inputs_are_pure_and_isolated_from_diagnostics() -> None:
    paths = tuple(
        map(Path, module_deps_of(SCRIPTS / "pd_vn_transgear_pivot_screw_spec.py"))
    )
    assert "_mcmaster_90325a174" in {path.stem for path in paths}
    assert not any("diagnostics" in path.parts for path in paths)
    assert not any(path.stem.startswith("build_") for path in paths)
    assert not any(path.stem in {"_com", "_session"} for path in paths)
    recipe = tuple(
        map(Path, module_deps_of(SCRIPTS / "diagnostics" / "diag_build_90325A174.py"))
    )
    assert "pd_vn_transgear_pivot_screw_spec" not in {path.stem for path in recipe}


def test_fitted_length_is_a_reference_set_by_the_bar() -> None:
    """Rule 19 fit-up: the tip is faced to stand .008-.020 below the bar's
    front face, so the printed length is the nominal bar less the window's
    middle, as a reference."""
    assert screw.TIP_RECESS == pytest.approx((0.008 * 25.4, 0.020 * 25.4))
    assert screw.FITTED_THREAD_LEN == pytest.approx(
        BAR_DEPTH - sum(screw.TIP_RECESS) / 2.0
    )
    assert screw.SHOULDER_END_Y == -screw.SHOULDER_LEN
    assert screw.TIP_Y == pytest.approx(screw.SHOULDER_END_Y - screw.FITTED_THREAD_LEN)
    assert screw.REFERENCE_DIMENSIONS == (("StockTrimProfile", "CutLength"),)
    assert screw.DIMENSION_TOLERANCE_TYPES["CutLength"] == 0
    # The fit-up's mate by name and number lives in linked numbered note 1;
    # the reference length carries only its link (rule 7, machinist review
    # rubric v2: a callout carries at most two lines of words).
    assert drawing.DIMENSION_CALLOUTS["CutLength"] == f"SEE NOTE {drawing.FIT_UP_NOTE}"
    assert drawing.FIT_UP_NOTE_TEXT.startswith(f"{drawing.FIT_UP_NOTE}. ")
    note = " ".join(drawing.FIT_UP_NOTE_TEXT.split())
    assert "TIP FACED AT ASSEMBLY .008-.020 BELOW" in note
    assert "FRONT FACE OF SUPPORT BAR MHA-PD-07." in note
    # Facing only shortens: the nominal fit is inside the catalogue length,
    # and every stock length reaches the thinnest bar's deepest recess.
    assert screw.FITTED_THREAD_LEN < screw.THREAD_LEN
    thin = BAR_DEPTH - bar.BAR_DEPTH_BAND
    assert screw.STOCK_THREAD_LEN_MIN >= thin - screw.TIP_RECESS[1]
    # The corner the fit-up sets aside: ASME-short stock in the thickest bar
    # stops .004 deeper than the .020 max recess.
    thick = BAR_DEPTH + bar.BAR_DEPTH_BAND
    assert joints.PIVOT_STOCK_SHORTFALL_AT_THICKEST_BAR == pytest.approx(
        thick - screw.TIP_RECESS[1] - screw.STOCK_THREAD_LEN_MIN
    )
    assert joints.PIVOT_STOCK_SHORTFALL_AT_THICKEST_BAR == pytest.approx(
        0.1016, abs=1e-3
    )


def test_engagement_charges_one_pitch_and_the_neck() -> None:
    """Worst case: the thinnest bar, the deepest recess, one incomplete pitch
    at the faced tip and the neck before the full thread starts."""
    thin = BAR_DEPTH - bar.BAR_DEPTH_BAND
    assert joints.PIVOT_FITTED_LEN_MIN == pytest.approx(thin - screw.TIP_RECESS[1])
    worst = joints.PIVOT_FITTED_LEN_MIN - screw.PITCH - screw.FULL_THREAD_START
    assert joints.PIVOT_ENGAGEMENT_WORST == pytest.approx(worst)
    assert joints.PIVOT_ENGAGEMENT_WORST_D >= screw.ENGAGEMENT_MIN_D
    # The printed minimum rounds up to the .001 inch grid.
    assert screw.THREAD_LENGTH_MIN == pytest.approx(
        math.ceil((1.5 * screw.THREAD_MAJOR + screw.PITCH) / 0.0254 - 1e-9) * 0.0254
    )


def test_chamfer_max_keeps_the_tip_inside_the_charged_pitch() -> None:
    # The model stands at the printed maximum (swTolMAX prints the nominal).
    assert screw.CHAMFER_WIDTH == screw.CHAMFER_WIDTH_MAX == pytest.approx(0.024 * 25.4)
    assert screw.CHAMFER_ANGLE_TOLERANCE == angular_band_deg(unit=screw.UNIT) == 1.0
    steepest = math.radians(screw.CHAMFER_ANGLE + screw.CHAMFER_ANGLE_TOLERANCE)
    assert screw.CHAMFER_AXIAL_MAX == pytest.approx(screw.CHAMFER_WIDTH * math.tan(steepest))
    assert screw.CHAMFER_AXIAL_MAX <= screw.INCOMPLETE_TIP_LEN_MAX == screw.PITCH
    # "Past the thread root" fits under the maximum: tip Ø 4.1656 - 1.2192 =
    # 2.9464 clears the deepest estimated 2A root Ø3.038.
    screw.require_chamfer_past_root(screw.CHAMFER_WIDTH)
    assert "THREAD ROOT" in drawing.DIMENSION_CALLOUTS["ChamferWidth"]


def test_minor_diameter_is_the_external_2a_root() -> None:
    """#8-32 UNC-2A (Kennametal UN tables): UNR minor max 0.1248 in; the
    deepest root estimate is 0.649519 P under the 0.1399 in PD minimum."""
    # 0.1631 - 1.226869/32 = 0.12476 in, tabled as 0.1248 in.
    assert screw.THREAD_MINOR_UNR_2A_MAX == pytest.approx(3.1689, abs=1e-4)
    assert screw.THREAD_MINOR_2A_MIN_EST == pytest.approx(3.0379, abs=1e-4)
    assert screw.THREAD_MINOR_2A_MIN_EST < screw.THREAD_MINOR_UNR_2A_MAX


@pytest.mark.parametrize(
    "chamfer_width_max",
    [
        0.45,  # tip Ø 3.2656: above even the shallowest root, Ø3.170.
        0.55,  # tip Ø 3.0656: under the shallowest root, above the deepest.
    ],
)
def test_chamfer_that_misses_the_deepest_root_is_refused(
    chamfer_width_max: float,
) -> None:
    with pytest.raises(AssertionError, match="thread root"):
        screw.require_chamfer_past_root(chamfer_width_max)


class _Recorder:
    """A fake SolidWorks that records every call a recipe makes."""

    def __init__(self) -> None:
        self.events: list[tuple] = []
        recorder = self

        class _Obj:
            def __init__(self, name: str) -> None:
                self._name = name

            def __getattr__(self, attr: str):
                if attr.startswith("_"):
                    raise AttributeError(attr)

                def call(*args, **kwargs):
                    recorder.log(f"{self._name}.{attr}", args, kwargs)
                    return _Obj(f"{self._name}.{attr}()")

                return call

        self.currentSketchManager = _Obj("sketch")
        self.currentModel = _Obj("model")

    def log(self, name: str, args=(), kwargs=None) -> None:
        self.events.append((name, tuple(args), dict(kwargs or {})))

    def _async(self, name: str, *args, **kwargs):
        self.log(name, args, kwargs)
        return "ok"

    def create_sketch(self, *args):
        return self._async("create_sketch", *args)

    def exit_sketch(self, *args):
        return self._async("exit_sketch", *args)

    def create_extrusion(self, *args):
        return self._async("create_extrusion", *args)

    def create_cut_extrude(self, *args):
        return self._async("create_cut_extrude", *args)

    def create_revolve(self, *args):
        return self._async("create_revolve", *args)

    def add_chamfer(self, *args):
        return self._async("add_chamfer", *args)


# Two bodies after the split at the neck's land bottom: the head-and-shoulder
# body ends there, the threaded tail runs from there to the tip.
_SPLIT_BODIES = [
    {"name": "Head", "box_mm": [-4.0, entry.Y_LAND_BOT, -4.0, 4.0, 4.0, 4.0]},
    {
        "name": "Tail",
        "box_mm": [-2.1, -UNDERHEAD, -2.1, 2.1, entry.Y_LAND_BOT, 2.1],
    },
]


def _record(monkeypatch, bodies=_SPLIT_BODIES) -> _Recorder:
    adapter = _Recorder()

    def logger(name, result=None):
        def call(*args, **kwargs):
            adapter.log(name, args, kwargs)
            return result

        return call

    def com_logger(name):
        def call(_adapter, *args, **kwargs):
            adapter.log(name, args, kwargs)

        return call

    def adapter_logger(name):
        def call(_adapter, *args, **kwargs):
            adapter.log(name, args, kwargs)

        return call

    def volume_check(_adapter, label, expected, tol):
        adapter.log("volume_check", (label, expected, tol))
        return expected

    @contextlib.contextmanager
    def no_inference(_adapter):
        yield

    def split(_adapter, plane, name):
        adapter.log("split_at_plane", (plane, name))
        return bodies

    monkeypatch.setattr(entry, "check", logger("check", True))
    monkeypatch.setattr(entry, "name_last_feature", com_logger("name_last_feature"))
    monkeypatch.setattr(entry, "volume_check", volume_check)
    monkeypatch.setattr(entry, "define_circle", adapter_logger("define_circle"))
    monkeypatch.setattr(entry, "add_line_chain", adapter_logger("add_line_chain"))
    monkeypatch.setattr(entry, "extrude_at_offset", com_logger("extrude_at_offset"))
    monkeypatch.setattr(entry, "offset_plane", com_logger("offset_plane"))
    monkeypatch.setattr(entry, "insert_helix", com_logger("insert_helix"))
    monkeypatch.setattr(entry, "thread_sweep_cut", com_logger("thread_sweep_cut"))
    monkeypatch.setattr(entry, "combine_union", com_logger("combine_union"))
    monkeypatch.setattr(entry, "split_at_plane", split)
    monkeypatch.setattr(entry, "no_sketch_inference", no_inference)
    monkeypatch.setattr(_telemetry, "info", lambda *a, **k: None)
    entry.build_90325A174(adapter)
    return adapter


def _calls(events, name):
    return [c for c in events if c[0] == name]


def test_recipe_stacks_head_shoulder_and_thread_on_the_shoulder_face(
    monkeypatch,
) -> None:
    calls = _record(monkeypatch).events
    # Head, shoulder and shank circles on the Top Plane (the shoulder face).
    radii = [c[1][2] for c in _calls(calls, "define_circle")]
    assert radii == pytest.approx(
        [screw.HEAD_DIA / 2.0, screw.SHOULDER_DIA / 2.0, screw.THREAD_MAJOR / 2.0]
    )
    head = _calls(calls, "create_extrusion")[0][1][0]
    assert head.depth == pytest.approx(screw.HEAD_H)
    # The shoulder hangs from y = 0 and the thread from the shoulder's end.
    offsets = [c[1] for c in _calls(calls, "extrude_at_offset")]
    assert offsets == [
        pytest.approx((screw.SHOULDER_LEN, -screw.SHOULDER_LEN)),
        pytest.approx((screw.THREAD_LEN, -UNDERHEAD)),
    ]


def test_hex_socket_is_cut_down_from_the_head_top_and_stops_inside_it(
    monkeypatch,
) -> None:
    calls = _record(monkeypatch).events
    assert ("offset_plane", ("HeadTop", pytest.approx(screw.HEAD_H)), {}) in calls
    socket = _calls(calls, "add_line_chain")[1][1][0]
    assert len(socket) == 6
    flats = sorted({round(abs(x), 9) for x, _y in socket})
    assert flats == pytest.approx([0.0, screw.SOCKET_AF / 2.0])
    corner = max(math.hypot(x, y) for x, y in socket)
    assert corner == pytest.approx(screw.SOCKET_AF / math.sqrt(3.0))
    assert corner < screw.HEAD_DIA / 2.0 - screw.HEAD_CHAMFER
    (cut,) = _calls(calls, "create_cut_extrude")
    assert cut[1][0].depth == pytest.approx(screw.SOCKET_DEPTH)
    assert 0.0 < cut[1][0].depth < screw.HEAD_H


def test_neck_regains_the_major_where_the_joint_counts_full_thread(
    monkeypatch,
) -> None:
    """The revolved neck cut: fillet off the shoulder's end face into the
    land, then a 45 deg flank that reaches the thread major exactly
    FULL_THREAD_START below that face -- where the joint starts counting."""
    calls = _record(monkeypatch).events
    (revolve,) = _calls(calls, "create_revolve")
    assert revolve[1][0].is_cut
    assert revolve[1][0].angle == pytest.approx(360.0)
    end_face = -screw.SHOULDER_LEN
    major_r = screw.THREAD_MAJOR / 2.0
    neck_r = screw.NECK_DIA / 2.0
    (arc,) = _calls(calls, "sketch.CreateArc")
    centre, start, stop = ([v * 1000.0 for v in arc[1][i : i + 2]] for i in (0, 3, 6))
    assert start == pytest.approx([major_r, end_face])
    assert stop == pytest.approx([neck_r, end_face - entry.NECK_FILLET_R])
    assert centre == pytest.approx([major_r, end_face - entry.NECK_FILLET_R])
    neck_chain = _calls(calls, "add_line_chain")[0][1][0]
    land_top, land_bot, flank_end = neck_chain[:3]
    assert land_top[0] == land_bot[0] == pytest.approx(neck_r)
    assert land_bot[1] == pytest.approx(end_face - entry.NECK_FLAT_END)
    rise = flank_end[0] - land_bot[0]
    assert land_bot[1] - flank_end[1] == pytest.approx(rise)
    assert flank_end[0] > major_r
    y_at_major = land_bot[1] - (major_r - land_bot[0])
    assert y_at_major == pytest.approx(end_face - screw.FULL_THREAD_START)


def test_thread_is_cut_on_the_tail_below_the_neck_land(monkeypatch) -> None:
    calls = _record(monkeypatch).events
    (helix,) = _calls(calls, "insert_helix")
    pitch, revs = helix[1][0:2]
    assert pitch == pytest.approx(screw.PITCH)
    assert revs * pitch == pytest.approx(screw.THREAD_LEN)
    assert ("offset_plane", ("TipPlane", pytest.approx(-UNDERHEAD)), {}) in calls
    split_plane = next(
        c for c in _calls(calls, "offset_plane") if c[1][0] == "SplitPlane"
    )
    assert split_plane[1][1] == pytest.approx(-screw.SHOULDER_LEN - entry.NECK_FLAT_END)
    assert ("split_at_plane", ("SplitPlane", "TailSplit"), {}) in calls
    (sweep,) = _calls(calls, "thread_sweep_cut")
    assert sweep[1][2:4] == ("Tail", "ThreadGroove")
    assert _calls(calls, "combine_union")


def test_recipe_refuses_a_split_that_leaves_no_single_tail(monkeypatch) -> None:
    whole = [dict(_SPLIT_BODIES[0], box_mm=[-4.0, -UNDERHEAD, -4.0, 4.0, 4.0, 4.0])]
    with pytest.raises(RuntimeError, match="below the neck land"):
        _record(monkeypatch, bodies=whole)


def test_fleet_diagnostic_driver_gates_the_new_sku() -> None:
    from diagnostics.diag_build_mcmaster import REGISTRY

    assert REGISTRY[screw.SKU] is entry.build_90325A174
    assert "91829A205" not in REGISTRY


def test_native_controls_are_owned_and_the_length_prints_as_reference() -> None:
    assert set(drawing.EXPECTED_CONTROLS) == {
        "ChamferWidth",
        "ChamferAngle",
        "ThreadLengthMin",
    }
    assert set(screw.DIMENSION_PRECISION) == {"CutLength", *drawing.EXPECTED_CONTROLS}
    assert set(drawing.FRONT_KEEP) == set(screw.DIMENSION_PRECISION)
    assert drawing.EXPECTED_CONTROLS["ChamferWidth"] == pytest.approx(
        (0.024 * 0.0254, 0.0, 0.0)
    )
    assert drawing.EXPECTED_CONTROLS["ChamferAngle"] == pytest.approx(
        (math.radians(45.0), -math.radians(1.0), math.radians(1.0))
    )
    assert screw.DIMENSION_TOLERANCE_TYPES == {
        "CutLength": 0,
        "ChamferWidth": 6,
        "ChamferAngle": 11,
        "ThreadLengthMin": 5,
    }
    assert "ChamferAngle" not in drawing.DIMENSION_CALLOUTS
    assert all("\\n" not in text for text in drawing.DIMENSION_CALLOUTS.values())
    # Rule 7: size and process lines plus at most two lines of words.
    assert all(len(text.splitlines()) <= 2 for text in drawing.DIMENSION_CALLOUTS.values())
    assert drawing.DIMENSION_CALLOUTS["ThreadLengthMin"].startswith("#8-32 UNC ")
    assert "1 PITCH MAX" in drawing.DIMENSION_CALLOUTS["ThreadLengthMin"]
    assert all("2A" not in text for text in drawing.DIMENSION_CALLOUTS.values())
    reason = drawing.DIMENSION_CALLOUTS["ChamferWidth"].replace("MHA-PD-07", "")
    assert not any(character.isdigit() for character in reason)


def test_registry_row_is_the_faced_stock_without_sheet_instructions() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["title"] == "Transgear Pivot Screw"
    # The title block's break-edge row covers the faced end's deburr.
    assert row["finish"] == "AS SUPPLIED"
    note = row["purchased_note"]
    assert note.startswith(f"PURCHASED SCREW McMASTER {screw.SKU}")
    assert "\n" not in note
    assert not any(character.isdigit() for character in note.replace(screw.SKU, ""))
    # The fit-up is an assembly-sheet step; the joint carries no lock.
    assert "installation_notes" not in row
    spec = DRAWINGS_BY_NAME["pd_vn_transgear_pivot_screw"]
    assert drawing.SPEC is spec
    assert spec.artifact_stem == part.PART_NAME
    assert spec.script == Path(drawing.__file__).resolve()
