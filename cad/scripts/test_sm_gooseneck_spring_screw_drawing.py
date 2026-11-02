"""Offline release contracts for MHA-SM-04, the gooseneck spring screw."""

from __future__ import annotations

import ast
import inspect
import math
from pathlib import Path

import pytest

import _config
import build_sm_gooseneck_spring_screw as part
import draw_sm_gooseneck_spring_screw as drawing
import sm_gooseneck_spring_joint as joint
import sm_gooseneck_spring_screw_geom as geom
import sm_gooseneck_spring_screw_spec as spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout


def test_registry_paths_and_part_name() -> None:
    registered = DRAWINGS_BY_NAME["sm_gooseneck_spring_screw"]
    assert registered.script == Path(drawing.__file__).resolve()
    assert registered.layout is DrawingLayout.LANDSCAPE
    assert registered.source.as_posix().endswith(
        "/sldprt/sm-gooseneck-spring-screw.SLDPRT"
    )
    assert drawing.SLDDRW.as_posix().endswith(
        "/slddrw/sm-gooseneck-spring-screw.SLDDRW"
    )
    assert drawing.PDF.as_posix().endswith("/pdf/sm-gooseneck-spring-screw.pdf")
    assert drawing.PNG.as_posix().endswith("/png/sm-gooseneck-spring-screw_drawing.png")
    assert part.PART_NAME == registered.artifact_stem


def test_part_registry_row_is_the_made_screw() -> None:
    row = _config.parts("sm-gooseneck-spring-screw")
    assert row["number"] == "MHA-SM-04"
    assert row["title"] == "Gooseneck Spring Screw"
    assert row["description"] == "GOOSENECK SPRING SCREW"
    # A critical grade (rule 2): the clamp's strength case needs hardened
    # 4140's yield (sm_gooseneck_spring_screw_spec.YIELD_MPA, McMaster
    # 6818T53); the print states the strength the SF assumes (codjiflo P2
    # round 4 on #1997), in ksi on the inch sheet.
    ksi = f"{spec.YIELD_MPA / 6.89475729:.0f} ksi"
    for grade in ("4140", "HRC 32", "1/2 in", ksi):
        assert grade in row["material"]
        assert grade in row["material_specification"]
    assert spec.YIELD_MPA == pytest.approx(130_000.0 * 0.00689475729)
    for retired in ("12L14", "1018"):
        assert retired not in row["material"] + row["material_specification"]
    assert int(row["quantity"]) == 1
    # A static clamp, not a running fit.
    assert "fit_class" not in row
    assert row["process"] != "purchased"
    # The library stand-in for 4140's density; the printed grade is the row's.
    assert part.MATERIAL == "Plain Carbon Steel"


def test_printed_material_fits_one_title_block_line() -> None:
    row = _config.parts("sm-gooseneck-spring-screw")
    assert len(str(row["material"])) <= 36
    assert "6818T53" in str(row["material_specification"])
    assert "hardened" in str(row["material_specification"])


def test_stock_turns_the_head() -> None:
    # 1/2-in round cleans up to the Ø11.50 head.
    assert geom.STOCK_DIA == pytest.approx(12.7)
    assert geom.HEAD_DIA < geom.STOCK_DIA


def test_spec_is_the_single_source_of_marked_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.SIDE_KEEP) | set(drawing.END_KEEP) == marked
    assert not set(drawing.SIDE_KEEP) & set(drawing.END_KEEP)
    # The flat-topped head prints its Ø, height and relief chamfer only.
    assert spec.DRAWING_DIMENSIONS["HeadProfile"] == {
        "HeadDia",
        "HeadHeight",
        "HeadReliefChamfer",
    }
    assert spec.DRAWING_DIMENSIONS["ShankProfile"] == {
        "UnderHeadLength",
        "BodyDia",
        "TipChamfer",
        "UnderHeadCornerR",
    }
    assert spec.DRAWING_DIMENSIONS["StationReference"] == {
        "OverallLength",
        "PlainLength",
        "FullThread",
    }
    # The slot width is only true-size in the head-end view.
    assert set(drawing.END_KEEP) == {"SlotWidth"}
    # Each chamfer's rise is held by equation, never printed a second time.
    assert "TipChamferRise" not in marked
    assert "HeadReliefChamferRise" not in marked
    assert set(spec.DRAWING_DIMENSIONS) == {
        "HeadProfile",
        "ShankProfile",
        "SlotProfile",
        "DriverSlot",
        "StationReference",
    }


def test_model_owns_places_and_bands() -> None:
    assert "draw_sm_gooseneck_spring_screw.py" in PRECISION_MIGRATED_DRAWINGS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    # An inch sheet prints no .X band (+/-.1 would swallow every size here).
    assert set(spec.DRAWING_PRECISION_BY_NAME.values()) == {2, 3}
    assert spec.REFERENCE_DIMENSIONS == {"OverallLength"}
    # No mark carries a shared-helper band: the body Ø, the head Ø and the
    # relief chamfer are native LIMIT bands and the plain length, the
    # full-thread station and the under-head corner native single limits, all
    # set by the part (owner rulings 2026-10-27, #1951); every other mark
    # takes the title block's band.
    assert model_toleranced_dimensions(part) == {}
    tree = ast.parse(Path(part.__file__).read_text(encoding="utf-8"))

    def calls(helper: str) -> set[tuple[str, ...]]:
        return {
            tuple(ast.unparse(arg) for arg in node.args[1:])
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == helper
        }

    # "3.60 MIN", "5.71 MAX" and "R0.5 MAX": the model value IS the printed
    # limit (the shared _single_limit_tolerance setter), each band running
    # away from it.
    singles = {
        tuple(ast.unparse(arg) for arg in node.args[1:]): {
            kw.arg: ast.unparse(kw.value) for kw in node.keywords
        }
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", "") == "set_single_limit"
    }
    assert singles == {
        ("'StationReference'", "'PlainLength'"): {
            "limit": "PLAIN_LENGTH_MIN",
            "band": "PLAIN_LENGTH_MIN_BAND",
            "tol_type": "PLAIN_LENGTH_MIN_TOL_TYPE",
        },
        ("'StationReference'", "'FullThread'"): {
            "limit": "FULL_THREAD_STATION_MAX",
            "band": "FULL_THREAD_STATION_MAX_BAND",
            "tol_type": "FULL_THREAD_STATION_MAX_TOL_TYPE",
        },
        ("'ShankProfile'", "'UnderHeadCornerR'"): {
            "limit": "UNDERHEAD_CORNER_R",
            "band": "UNDERHEAD_CORNER_R_BAND",
            "tol_type": "UNDERHEAD_CORNER_R_TOL_TYPE",
        },
    }
    assert calls("_single_limit") == set()
    assert calls("set_dimension_prefix") == set()
    assert geom.BODY_DIA_TOL_TYPE == 3  # swTolLIMIT
    assert geom.HEAD_RELIEF_CHAMFER_TOL_TYPE == 3  # swTolLIMIT
    assert geom.HEAD_DIA_TOL_TYPE == 3  # swTolLIMIT
    assert (geom.HEAD_DIA_LOWER, geom.HEAD_DIA_UPPER) == (-0.10, 0.10)
    assert geom.PLAIN_LENGTH_MIN_TOL_TYPE == 5  # swTolMIN
    assert geom.FULL_THREAD_STATION_MAX_TOL_TYPE == 6  # swTolMAX
    assert geom.UNDERHEAD_CORNER_R == 0.50
    assert geom.UNDERHEAD_CORNER_R_BAND == (0.0, -geom.UNDERHEAD_CORNER_R)
    assert geom.UNDERHEAD_CORNER_R_TOL_TYPE == 6  # swTolMAX
    # The two station limits bound each other: the MIN's band (upper, lower)
    # runs up to the MAX, the MAX's down to the MIN.
    gap = geom.FULL_THREAD_STATION_MAX - geom.PLAIN_LENGTH_MIN
    assert geom.PLAIN_LENGTH_MIN_BAND == pytest.approx((gap, 0.0))
    assert geom.FULL_THREAD_STATION_MAX_BAND == pytest.approx((0.0, -gap))


def test_policy_sheet_carries_no_gdt_or_render_time_precision() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for helper in (
        "add_feature_control_frame",
        "add_datum_feature",
        "set_basic_dimension",
        "set_dimension_precision",
        "SetPrecision3",
        "add_surface_finish",
    ):
        assert helper not in source
    build = Path(part.__file__).read_text(encoding="utf-8")
    assert "author_part_pmi" not in build


def test_geometry_matches_the_settled_design() -> None:
    # Owner rulings 2026-10-27 (#1951): a flat-topped Ø11.50 cheese head over
    # a plain Ø6.35 body, 1/4-28 UNF; the head 6.60 tall under its relief
    # chamfer (ruling (A)).
    assert geom.HEAD_DIA == 11.50
    assert geom.HEAD_H == 6.60
    assert geom.SLOT_WIDTH == 1.60
    assert geom.SLOT_DEPTH == 2.00
    assert geom.SLOT_FLOOR_Z == pytest.approx(4.60)
    assert geom.LENGTH == 19.50
    assert geom.MAJOR_DIA == pytest.approx(0.25 * 25.4)
    assert geom.BODY_DIA == geom.MAJOR_DIA
    assert geom.PITCH == pytest.approx(25.4 / 28)
    assert geom.TIP_CHAMFER == 0.50
    assert geom.OVERALL_LENGTH == pytest.approx(26.10)
    assert geom.HEAD_RELIEF_CHAMFER == 1.45
    assert (geom.HEAD_RELIEF_CHAMFER_MIN, geom.HEAD_RELIEF_CHAMFER_MAX) == (
        pytest.approx((1.40, 1.50))
    )


def test_slot_leaves_the_rule_17_head_web() -> None:
    # Printed shortest head .25, deepest slot .09, largest relief .059.
    assert spec.SLOT_WEB_MIN == pytest.approx((0.25 - 0.09 - 0.059) * 25.4)
    assert spec.SLOT_WEB_MIN >= spec.SLOT_WEB_TARGET == pytest.approx(0.080 * 25.4)


def test_inch_print_stays_inside_the_joint_envelopes() -> None:
    # The joint and the seat checks charge the mm envelopes; the inch LIMIT
    # bands lie inside them, on the .001 grid.
    for name, model, envelope, limits_in in (
        ("HeadDia", geom.HEAD_DIA, (-0.10, 0.10), (0.449, 0.456)),
        ("HeadReliefChamfer", geom.HEAD_RELIEF_CHAMFER, (-0.05, 0.05), (0.056, 0.059)),
        ("BodyDia", geom.BODY_DIA, (-0.15, -0.03), (0.245, 0.248)),
    ):
        lower, upper = spec.PRINTED_BANDS[name]
        assert ((model + lower) / 25.4, (model + upper) / 25.4) == pytest.approx(
            limits_in, abs=1e-9
        )
        assert envelope[0] <= lower < upper <= envelope[1]
    assert geom.THREAD_MAJOR_2A_MIN_IN < 0.245 < 0.248 < geom.THREAD_MAJOR_2A_MAX_IN
    lower, upper = spec.PRINTED_BANDS["UnderHeadLength"]
    assert geom.LENGTH_LOWER < lower < 0.0 < upper < geom.LENGTH_UPPER
    # The single limits print past the joint's mm values; its margins hold at
    # the printed .14 MIN, .225 MAX and R.020 MAX.
    assert spec.PRINTED_LIMITS == pytest.approx(
        {
            "PlainLength": 0.14 * 25.4,
            "FullThread": 0.225 * 25.4,
            "UnderHeadCornerR": 0.508,
        }
    )
    assert spec.PRINTED_LOOP_PLAIN_MARGIN_MIN > 0.4
    assert spec.PRINTED_RUNOUT_MARGIN_MIN >= joint.COUNTERBORE_RUNOUT_MARGIN_MIN
    assert spec.PRINTED_RUNOUT_FLOOR_CORNER_CLEARANCE_MIN > 0.0
    assert spec.PRINTED_LOOP_CORNER_CLEARANCE_MIN > 0.0


_BAND_MODELS = {
    "HeadDia": geom.HEAD_DIA,
    "HeadReliefChamfer": geom.HEAD_RELIEF_CHAMFER,
    "BodyDia": geom.BODY_DIA,
    "HeadHeight": geom.HEAD_H,
    "UnderHeadLength": geom.LENGTH,
    "SlotWidth": geom.SLOT_WIDTH,
    "SlotDepth": geom.SLOT_DEPTH,
    "TipChamfer": geom.TIP_CHAMFER,
}


def test_every_printed_band_resolves_to_its_inch_places() -> None:
    # Every band's limits about its spec model land on the inch grid at the
    # dimension's own places (farm run on fe9b1b219: the head Ø's limits read
    # off a noisy SystemValue needed more than eight).
    from _drawing_tolerances import _tolerance_places

    assert set(_BAND_MODELS) == set(spec.PRINTED_BANDS)
    for name, (lower, upper) in spec.PRINTED_BANDS.items():
        model = _BAND_MODELS[name]
        places = _tolerance_places(model + lower, model + upper, display_unit="in")
        assert places <= spec.DRAWING_PRECISION_BY_NAME[name], name


@pytest.mark.parametrize("name", ["BodyDia", "HeadDia", "HeadReliefChamfer"])
def test_limit_band_sets_places_from_the_spec_model_not_the_readback(
    monkeypatch, name: str
) -> None:
    model = _BAND_MODELS[name]
    lower, upper = spec.PRINTED_BANDS[name]
    stored: dict[str, object] = {}

    class Tolerance:
        Type = 0

        def SetValues(self, low, high):
            stored["values"] = (low, high)
            return True

        def GetMinValue(self):
            return stored["values"][0]

        def GetMaxValue(self):
            return stored["values"][1]

    class Display:
        def SetPrecision3(self, _primary, _dual, tolerance, _dual_tolerance):
            stored["places"] = tolerance

        def GetPrimaryTolPrecision2(self):
            return stored["places"]

    # The inch document reads the mm nominal back with float noise.
    dimension = type(
        "Dimension",
        (),
        {"SystemValue": (model + 1.14e-7) / 1000.0, "Tolerance": Tolerance()},
    )()
    monkeypatch.setattr(part, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        part,
        "_named_dimension",
        lambda _adapter, _feature, _name: (Display(), dimension),
    )
    part._limit_band(object(), "Profile", name, model, (lower, upper), 3)
    assert stored["values"] == (lower / 1000.0, upper / 1000.0)
    assert stored["places"] == spec.DRAWING_PRECISION_BY_NAME[name] == 3
    with pytest.raises(RuntimeError, match="not the spec"):
        part._limit_band(object(), "Profile", name, model + 0.01, (lower, upper), 3)


def test_head_and_relief_bands_name_the_wire_they_clear() -> None:
    # drawing-guidelines.md rule 4: each LIMIT band names what it serves.
    # The head's 0.95 (.037 in) retention under the 1.0 check (owner minor
    # RV-01) prints on the head Ø as a plain fact, floored (rule 20).
    assert spec.HEAD_RETENTION_CALLOUT == "LOOP OVERLAP\n.037 MIN"
    assert math.floor(joint.HEAD_RETENTION_MIN / 25.4 * 1000.0) == 37
    assert spec.DIMENSION_CALLOUTS["HeadProfile"] == {
        "HeadDia": (
            f"{spec.COUNTER_SPRING_NUMBER}\nWIRE CLEARS;\nLOOP OVERLAP\n.037 MIN"
        ),
        "HeadReliefChamfer": f"X 45 DEG;\n{spec.COUNTER_SPRING_NUMBER}\nWIRE CLEARS",
    }
    assert spec.DRAWING_PRECISION_BY_NAME["HeadDia"] == 3
    assert spec.DRAWING_PRECISION_BY_NAME["HeadReliefChamfer"] == 3
    # The head Ø's block stands between the head-end view's slot width and
    # the head's top face, centred on its own dimension line.
    assert drawing.HEAD_DIA_TEXT_HEIGHT == drawing.block_height(2, 4)
    x, y = drawing.SIDE_KEEP["HeadDia"]
    assert y == drawing.SIDE_CENTER[1]
    right = x + drawing.HEAD_DIA_TEXT_WIDTH / 2.0
    left = x - drawing.HEAD_DIA_TEXT_WIDTH / 2.0
    assert right <= drawing.TOP_X - 0.005
    assert left >= drawing.END_KEEP["SlotWidth"][0] + 0.010
    head_half = geom.HEAD_DIA * drawing._S / 2000.0
    assert drawing.HEAD_DIA_TEXT_HEIGHT < 2.0 * head_half


def test_body_limit_band_is_the_thread_blank_inside_the_2a_major() -> None:
    # The LIMIT band 6.32/6.20 sits inside the 1/4-28 UNF-2A major band
    # (0.2490/0.2425 in), so the die cuts a 2A crest on the loop's seat.
    assert (geom.BODY_DIA_LOWER, geom.BODY_DIA_UPPER) == pytest.approx((-0.15, -0.03))
    assert (geom.BODY_DIA_MIN, geom.BODY_DIA_MAX) == pytest.approx((6.20, 6.32))
    assert geom.THREAD_MAJOR_2A_MIN == pytest.approx(6.1595)
    assert geom.THREAD_MAJOR_2A_MAX == pytest.approx(6.3246)
    assert geom.THREAD_MAJOR_2A_MIN < geom.BODY_DIA_MIN < geom.BODY_DIA_MAX
    assert geom.BODY_DIA_MAX < geom.THREAD_MAJOR_2A_MAX
    with pytest.raises(AssertionError, match="2A major band"):
        geom.require_body_form(body_dia_max=geom.THREAD_MAJOR_2A_MAX + 0.01)
    # The band names what it serves (drawing-guidelines.md rule 4).
    assert spec.DIMENSION_CALLOUTS_BY_NAME["BodyDia"].splitlines() == [
        "THREAD BLANK;",
        spec.COUNTER_SPRING_NUMBER,
        "LOOP SEAT",
    ]
    assert spec.CHAMFER_CALLOUT == "X 45 DEG"


def test_plain_length_and_full_thread_limits_print_on_the_part() -> None:
    # "3.60 MIN" plain under the head (the loop's seat), "5.71 MAX" to the
    # first full thread, both from the under-head face, with room between
    # them for the die's chamfered start.
    assert geom.PLAIN_LENGTH_MIN == 3.60
    assert geom.FULL_THREAD_STATION_MAX == 5.71
    assert geom.FULL_THREAD_STATION_MAX - geom.PLAIN_LENGTH_MIN >= (
        geom.FULL_THREAD_DIE_ROOM_MIN
    )
    with pytest.raises(AssertionError, match="no room for its chamfer"):
        geom.require_body_form(
            full_thread_station_max=geom.PLAIN_LENGTH_MIN + geom.PITCH
        )
    # The plain length names its mate below the value; the full-thread limit
    # stands ABOVE its value, which alone takes the dimension line.
    assert spec.DIMENSION_CALLOUTS["StationReference"] == {
        "PlainLength": f"PLAIN;\n{spec.COUNTER_SPRING_NUMBER}\nLOOP SEAT"
    }
    assert spec.DIMENSION_CALLOUTS_ABOVE["StationReference"] == {
        "FullThread": "TO FULL THREAD"
    }
    assert "MHA-SM-01" in spec.DRAWING_NOTES
    assert "FULL THREAD" not in spec.DRAWING_NOTES
    assert "PLAIN" not in spec.DRAWING_NOTES
    # The station sketch's witnesses lie on the outline: the under-head face
    # (from the corner round's tangent point up, under the head's rim) and
    # the body's silhouette from each printed station toward the tip.
    body_r = geom.BODY_DIA / 2.0
    tangent_r = body_r + geom.UNDERHEAD_CORNER_R
    (f0, f1) = part.FACE_WITNESS_LINE
    (p0, p1), (t0, t1) = part.PLAIN_WITNESS_LINE, part.THREAD_WITNESS_LINE
    assert f0 == pytest.approx((0.0, tangent_r))
    assert f1[0] == 0.0 and tangent_r < f1[1] < geom.HEAD_DIA / 2.0
    assert p0 == pytest.approx((geom.PLAIN_LENGTH_MIN, body_r))
    assert t0 == pytest.approx((geom.FULL_THREAD_STATION_MAX, body_r))
    assert p0[0] < p1[0] < t0[0] < t1[0] < geom.LENGTH - geom.TIP_CHAMFER
    assert p1[1] == p0[1] and t1[1] == t0[1]
    build = Path(part.__file__).read_text(encoding="utf-8")
    for record in (
        """stations.record("FaceWitnessRadius", '"BodyDia" / 2 + "UnderHeadCornerR"')""",
        """stations.record(name, f'"{name}"')""",
        """stations.record(f"{name}Drop", '"UnderHeadCornerR"')""",
        '("PlainLength", plain_witness, (pu0, pv0))',
        '("FullThread", thread_witness, (tu0, tv0))',
        '("PlainLength", PLAIN_LENGTH_MIN)',
        '("FullThread", FULL_THREAD_STATION_MAX)',
    ):
        assert record in build


def _shank_profile_points() -> list[tuple[float, float]]:
    """The builder's ShankProfile chain, evaluated in the builder's names."""
    tree = ast.parse(Path(part.__file__).read_text(encoding="utf-8"))
    (node,) = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and [ast.unparse(target) for target in node.targets] == ["points"]
    ]
    return eval(compile(ast.Expression(node.value), "<points>", "eval"), vars(part))


def _shank_tangent_pairs() -> set[frozenset[str]]:
    """Every tangent relation the builder authors in the shank profile.

    Resolved from the AST, so a loop over pairs and separate calls both count
    while a loop that authors nothing counts for nothing: each
    ``add_sketch_constraint(a, b, "tangent")`` between the shank sketch's create
    and exit, its names substituted through any enclosing ``for`` over a
    literal tuple of pairs.
    """
    tree = ast.parse(Path(part.__file__).read_text(encoding="utf-8"))
    marks = {
        node.value: node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and node.value in ("create_sketch shank profile", "exit_sketch shank profile")
    }
    first, last = (
        marks["create_sketch shank profile"],
        marks["exit_sketch shank profile"],
    )
    pairs: set[frozenset[str]] = set()

    def visit(node: ast.AST, names: dict[str, str]) -> None:
        if (
            isinstance(node, ast.For)
            and isinstance(node.target, ast.Tuple)
            and isinstance(node.iter, ast.Tuple | ast.List)
        ):
            targets = [ast.unparse(target) for target in node.target.elts]
            for item in node.iter.elts:
                if isinstance(item, ast.Tuple) and len(item.elts) == len(targets):
                    bound = names | {
                        target: names.get(ast.unparse(value), ast.unparse(value))
                        for target, value in zip(targets, item.elts)
                    }
                    for child in node.body:
                        visit(child, bound)
            return
        if (
            isinstance(node, ast.Call)
            and getattr(node.func, "attr", "") == "add_sketch_constraint"
            and first <= node.lineno <= last
            and len(node.args) == 3
            and isinstance(node.args[2], ast.Constant)
            and node.args[2].value == "tangent"
        ):
            a, b = (
                names.get(ast.unparse(arg), ast.unparse(arg)) for arg in node.args[:2]
            )
            pairs.add(frozenset((a, b)))
        for child in ast.iter_child_nodes(node):
            visit(child, names)

    visit(tree, {})
    return pairs


def test_cosmetic_thread_runs_from_the_tip_chamfer_to_the_full_thread_station():
    # Seeded on the chamfer/body edge, on the body's radius, it ends where the
    # sheet's full-thread limit stands: the thread lines and the station agree.
    x, y, z = part.THREAD_EDGE_POINT
    assert (x, y) == (0.0, geom.BODY_DIA / 2.0)
    assert -z == pytest.approx(geom.LENGTH - geom.TIP_CHAMFER)
    assert -z - part.COSMETIC_THREAD_DEPTH == pytest.approx(
        geom.FULL_THREAD_STATION_MAX
    )
    assert geom.FULL_THREAD_STATION_MAX > geom.PLAIN_LENGTH_MIN


def test_shank_profile_is_corner_plain_body_and_tip() -> None:
    body_r = geom.BODY_DIA / 2.0
    corner_r = geom.UNDERHEAD_CORNER_R
    # The face rises from the axis to the corner round, whose CCW quarter
    # (centre off the face and the body by its radius) turns onto the body.
    assert part.CORNER_FACE_TANGENT == pytest.approx((0.0, body_r + corner_r))
    assert part.CORNER_CENTER == pytest.approx((corner_r, body_r + corner_r))
    assert part.CORNER_BODY_TANGENT == pytest.approx((corner_r, body_r))
    expected = [
        (corner_r, body_r),
        (geom.LENGTH - geom.TIP_CHAMFER, body_r),
        (geom.LENGTH, body_r - geom.TIP_CHAMFER),
        (geom.LENGTH, 0.0),
        (0.0, 0.0),
    ]
    points = _shank_profile_points()
    assert len(points) == len(expected)
    for got, want in zip(points, expected):
        assert got == pytest.approx(want)
    # One plain body at one diameter: no step, no lead, no second Ø.
    assert points[0][1] == points[1][1] == pytest.approx(body_r)
    build = Path(part.__file__).read_text(encoding="utf-8")
    shank = build[
        build.index("create_sketch shank profile") : build.index(
            "exit_sketch shank profile"
        )
    ]
    # The only vertical leg is the tip chamfer's rise, held to its axial leg.
    assert shank.count('"vertical_distance"') == 1
    assert """shank.record("TipChamferRise", '"TipChamfer"')""" in shank
    assert shank.count("add_diametric_linear_dimension(") == 1
    assert """shank.record("BodyDia", '"BodyDia"')""" in shank
    # The round is tangent to both legs and its radius, a sketch dimension,
    # runs from the global; the axial sizes read from the face.
    assert _shank_tangent_pairs() == {
        frozenset(("face", "corner")),
        frozenset(("corner", "body")),
    }
    assert """shank.record("UnderHeadCornerR", '"UnderHeadCornerR"')""" in shank
    assert '("UnderHeadLength", f"{face}.end", f"{tip_chamfer}.end", LENGTH)' in shank
    assert '("UnderHeadCornerR", UNDERHEAD_CORNER_R)' in build
    assert '("BodyDia", BODY_DIA)' in build
    # No hidden reference sketch but StationReference.
    assert build.count("blank_sketch(adapter, ") == 1


def test_head_profile_is_a_flat_topped_cylinder_with_its_relief() -> None:
    build = Path(part.__file__).read_text(encoding="utf-8")
    head = build[
        build.index("create_sketch head profile") : build.index(
            "exit_sketch head profile"
        )
    ]
    # The relief cuts the under-face's outer corner at 45 degrees: its axial
    # leg is the printed size, its radial leg follows by equation.
    assert "(0.0, HEAD_R - relief)," in head
    assert "(-relief, HEAD_R)," in head
    assert "add_arc" not in head
    assert """head.record("HeadHeight", '"HeadHeight"')""" in head
    assert """head.record("HeadDia", '"HeadDia"')""" in head
    assert """head.record("HeadReliefChamfer", '"HeadReliefChamfer"')""" in head
    assert """head.record("HeadReliefChamferRise", '"HeadReliefChamfer"')""" in head
    assert head.count("head.record(") == 4
    assert '("HeadReliefChamfer", HEAD_RELIEF_CHAMFER)' in build


def test_thread_callout_names_the_size_but_not_the_title_block_class() -> None:
    assert spec.THREAD_CALLOUT == "1/4-28 UNF"
    assert "2A" not in spec.THREAD_CALLOUT
    assert drawing.THREAD_CALLOUT is spec.THREAD_CALLOUT


def test_notes_are_short_and_carry_no_dimension_or_method() -> None:
    # The plain length and the full-thread limit print on their features, so
    # one note is left, carrying no figure.
    assert spec.DRAWING_NOTES == "1. THREAD MATES THE TAPPED END PIECE OF MHA-SM-01."
    for line in spec.DRAWING_NOTES.splitlines():
        # Only the mating part's number is quoted.
        text = line.split(". ", 1)[-1].replace("MHA-SM-01", "")
        assert not any(ch.isdigit() for ch in text), line
        for word in ("TORQUE", "LOCTITE", "N-M", "IN-LB"):
            assert word not in line
    assert spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW\nSCALE 2:1"


def test_part_sheet_carries_no_assembly_instruction() -> None:
    # The clamp step (user ruling 2026-09-21: no torque value, no
    # threadlocker) prints in full as MHA-SM-00 step 8.
    notes = " ".join(spec.DRAWING_NOTES.split())
    assert "ASSEMBLY" not in notes
    assert "TIGHTEN" not in notes
    import sm_summing_assembly_sheet as summing

    step = next(s for s in summing.ASSEMBLY_STEPS if s.startswith("8. "))
    assert "MHA-SM-04" in step
    assert "CANNOT SWIVEL" in step
    assert step.endswith("NO THREADLOCKER.")
    for word in ("TORQUE", "N-M", "IN-LB"):
        assert word not in step
    build = Path(part.__file__).read_text(encoding="utf-8")
    assert '"Manufacturing Notes": DRAWING_NOTES' in build


def test_modelled_volume_is_the_turned_body_less_the_slot() -> None:
    r_head, h_head, relief = 5.75, 6.6, 1.45
    r_body, length, chamfer = 0.25 * 25.4 / 2.0, 19.5, 0.5
    # The relief's corner triangle (legs 1.45), by Pappus at its centroid.
    relief_ring = 2.0 * math.pi * (r_head - relief / 3.0) * relief**2 / 2.0
    assert part.V_HEAD == pytest.approx(math.pi * r_head**2 * h_head - relief_ring)
    # The body cylinder less, by Pappus, the tip chamfer's corner triangle
    # (legs 0.5, centroid r_body - 0.5/3), plus the under-head corner round's
    # spandrel ring, integrated on a midpoint grid over (axial u, radius r):
    # material where u, r - r_body in [0, R] and the point stands outside the
    # round's circle.
    tip = 2.0 * math.pi * (r_body - chamfer / 3.0) * chamfer**2 / 2.0
    corner_r, steps = 0.5, 400
    cell = corner_r / steps
    corner = 0.0
    for i in range(steps):
        u = (i + 0.5) * cell
        for j in range(steps):
            r = r_body + (j + 0.5) * cell
            if math.hypot(u - corner_r, r - (r_body + corner_r)) >= corner_r:
                corner += 2.0 * math.pi * r * cell * cell
    assert part.V_CORNER == pytest.approx(corner, rel=2e-3)
    assert part.V_SHANK == pytest.approx(
        math.pi * r_body**2 * length - tip + part.V_CORNER
    )
    assert part.V_TURNED == pytest.approx(part.V_HEAD + part.V_SHANK)
    # Independent slot volume: the flat top's strip, integrated across its
    # width, times the slot depth.
    steps_y, half = 2000, 0.8
    dy = 2.0 * half / steps_y
    strip = sum(
        2.0 * math.sqrt(r_head**2 - (-half + (j + 0.5) * dy) ** 2) * dy
        for j in range(steps_y)
    )
    assert part.V_SLOT == pytest.approx(strip * 2.0, rel=1e-4)
    assert part.V_FINAL == pytest.approx(part.V_TURNED - part.V_SLOT)


def test_side_view_stations_follow_the_model() -> None:
    scale = drawing.SHEET_SCALE[0] / 1000.0
    assert drawing.TIP_X - drawing.TOP_X == pytest.approx(geom.OVERALL_LENGTH * scale)
    assert drawing.UNDERHEAD_X - drawing.TOP_X == pytest.approx(geom.HEAD_H * scale)
    assert drawing.PLAIN_X - drawing.UNDERHEAD_X == pytest.approx(
        geom.PLAIN_LENGTH_MIN * scale
    )
    assert drawing.FULL_THREAD_X - drawing.UNDERHEAD_X == pytest.approx(
        geom.FULL_THREAD_STATION_MAX * scale
    )
    # Model +Z runs paper-left in *Right: head left, tip right.
    assert (
        drawing.TOP_X
        < drawing.SLOT_FLOOR_X
        < drawing.UNDERHEAD_X
        < drawing.PLAIN_X
        < drawing.FULL_THREAD_X
        < drawing.THREAD_START_X
        < drawing.TIP_X
    )
    # The bounding-box centre is the view centre.
    assert (drawing.TOP_X + drawing.TIP_X) / 2.0 == pytest.approx(
        drawing.SIDE_CENTER[0]
    )


def test_head_end_view_is_the_third_angle_left_view() -> None:
    assert drawing.END_CENTER[1] == drawing.SIDE_CENTER[1]
    head_radius = geom.HEAD_DIA * drawing.SHEET_SCALE[0] / 2000.0
    assert drawing.END_CENTER[0] + head_radius < drawing.TOP_X - 0.030
    head_dia_x = drawing.SIDE_KEEP["HeadDia"][0]
    assert drawing.END_CENTER[0] + head_radius + 0.010 < head_dia_x < drawing.TOP_X
    slot_x = drawing.END_KEEP["SlotWidth"][0]
    assert drawing.END_CENTER[0] + head_radius < slot_x < head_dia_x - 0.010


def test_sheet_placements_stay_inside_the_border() -> None:
    inner = (0.0127, 0.0127, 0.4191, 0.2667)  # ASME B landscape inner border
    title_block = (0.218, 0.065)  # x >= and y <=
    points = [
        drawing.SIDE_CENTER,
        drawing.END_CENTER,
        drawing.ISO_CENTER,
        drawing.THREAD_NOTE_XY,
        drawing.ISO_NOTE_XY,
        drawing.NOTES_XY,
        drawing.BODY_DIA_TEXT_XY,
        (drawing.TIP_X, drawing.SIDE_CENTER[1]),
        *drawing.SIDE_KEEP.values(),
        *drawing.END_KEEP.values(),
    ]
    for x, y in points:
        assert inner[0] < x < inner[2] and inner[1] < y < inner[3]
        assert not (x >= title_block[0] and y <= title_block[1])
    # The thread callout's leader lands where the body meets the tip chamfer.
    assert drawing.THREAD_PICK[0] == drawing.THREAD_START_X
    body_half = geom.BODY_DIA * drawing.SHEET_SCALE[0] / 2000.0
    assert abs(drawing.THREAD_PICK[1] - drawing.SIDE_CENTER[1]) < body_half
    assert drawing.THREAD_NOTE_XY[0] - drawing.THREAD_PICK[0] > 0.010
    # Text blocks follow the farm run 20261027T034356887Z render: block
    # centred on its anchor, 5.56 mm per callout line (and value over its
    # callout), 4.53 mm between stacked limits, 4.50 mm of first-line ink.
    assert drawing.block_height(2, 3) == pytest.approx(0.2388337 - 0.2131399, abs=2e-4)
    assert drawing.BODY_DIA_TEXT_HEIGHT == drawing.block_height(2, 3)
    assert drawing.PLAIN_LENGTH_TEXT_HEIGHT == drawing.block_height(1, 3)
    # The body Ø stands on the plain body, past the corner round, its line
    # inside the plain length; its text hangs right of its own dimension line
    # (its leader meets the text's left end, so the leader runs beside the
    # text, not through it), under the body and short of the tip chamfer.
    assert drawing.SIDE_KEEP["BodyDia"][0] == drawing.BODY_DIA_X
    corner_end = drawing.UNDERHEAD_X + drawing.UNDERHEAD_CORNER_R_SHEET
    assert corner_end + 0.002 <= drawing.BODY_DIA_X < drawing.PLAIN_X
    text_x, text_y = drawing.BODY_DIA_TEXT_XY
    left = text_x - drawing.BODY_DIA_TEXT_WIDTH / 2.0
    right = text_x + drawing.BODY_DIA_TEXT_WIDTH / 2.0
    assert left > drawing.BODY_DIA_X + 0.002
    assert right <= drawing.THREAD_START_X - 0.002
    body_top = text_y + drawing.BODY_DIA_TEXT_HEIGHT / 2.0
    assert body_top <= drawing.BODY_BOTTOM_Y - 0.0015
    # Its callout ends well above row 0, and left of the tip chamfer's text.
    block_bottom = text_y - drawing.BODY_DIA_TEXT_HEIGHT / 2.0
    assert block_bottom - drawing.SIDE_KEEP["UnderHeadLength"][1] >= 0.015
    assert right < drawing.SIDE_KEEP["TipChamfer"][0] - 0.010
    # Two rows over the body from the under-head face, the longer outside.
    pl_line, ft_line = drawing.PLAIN_LENGTH_LINE_Y, drawing.FULL_THREAD_LINE_Y
    assert pl_line >= drawing.BODY_TOP_Y + 0.030
    assert ft_line - pl_line >= 0.008
    # The full-thread block centres over its own span, above its line: the
    # value alone takes the line between the extension lines, 0.5 mm a side
    # or more; its one-line callout stands a line above.
    ft_x, ft_y = drawing.SIDE_KEEP["FullThread"]
    assert ft_x == pytest.approx((drawing.UNDERHEAD_X + drawing.FULL_THREAD_X) / 2.0)
    assert ft_y == pytest.approx(ft_line + drawing.FULL_THREAD_TEXT_HEIGHT / 2.0)
    assert drawing.FULL_THREAD_TEXT_HEIGHT == drawing.block_height(1, 1)
    span = drawing.FULL_THREAD_X - drawing.UNDERHEAD_X
    assert (span - drawing.FULL_THREAD_VALUE_WIDTH) / 2.0 >= 0.0005
    ft_left = ft_x - drawing.FULL_THREAD_TEXT_WIDTH / 2.0
    ft_right = ft_x + drawing.FULL_THREAD_TEXT_WIDTH / 2.0
    assert ft_line + drawing.FULL_THREAD_TEXT_HEIGHT <= inner[3] - 0.010
    # The plain station's extension line ends 1 mm past its own line, under
    # the full-thread block, which inks 0.9 mm over its line.
    assert ft_left < drawing.PLAIN_X < ft_right
    assert (ft_line + 0.0009) - (pl_line + 0.001) >= 0.002
    # The plain length's block stands right of the 5.71 station's extension
    # line and of the full-thread block (it shares their height), 3 mm clear
    # of both, so no line strikes its text.
    pl_x, pl_y = drawing.SIDE_KEEP["PlainLength"]
    assert pl_y == pytest.approx(pl_line + drawing.PLAIN_LENGTH_TEXT_HEIGHT / 2.0)
    pl_left = pl_x - drawing.PLAIN_LENGTH_TEXT_WIDTH / 2.0
    pl_right = pl_x + drawing.PLAIN_LENGTH_TEXT_WIDTH / 2.0
    assert pl_left >= drawing.FULL_THREAD_X + 0.003
    assert pl_left >= ft_right + 0.003 - 1e-12
    assert pl_line + drawing.PLAIN_LENGTH_TEXT_HEIGHT <= inner[3] - 0.010
    assert drawing.ISO_CENTER[0] - pl_right > 0.040
    # The thread note stands under and right of the plain length's block.
    assert pl_right < drawing.THREAD_NOTE_XY[0]
    assert pl_line - drawing.THREAD_NOTE_XY[1] >= 0.008
    # The slot depth's text stands left of the top face, over the head and
    # right of the head Ø; nothing over the head reaches the station rows.
    sd_x, sd_y = drawing.SIDE_KEEP["SlotDepth"]
    assert sd_x + drawing.SLOT_DEPTH_TEXT_WIDTH / 2.0 <= drawing.TOP_X - 0.002
    assert sd_x - drawing.SLOT_DEPTH_TEXT_WIDTH / 2.0 > drawing.SIDE_KEEP["HeadDia"][0]
    assert drawing.HEAD_TOP_Y + 0.008 <= sd_y <= ft_line - 0.020
    # The centreline pick lands on the threaded body's face.
    assert drawing.FULL_THREAD_X < drawing.CENTERLINE_PICK[0] < drawing.THREAD_START_X
    assert abs(drawing.CENTERLINE_PICK[1] - drawing.SIDE_CENTER[1]) < body_half
    # The isometric stands clear of the thread note.
    assert drawing.ISO_CENTER[0] - drawing.THREAD_NOTE_XY[0] > 0.040


def test_underhead_corner_radius_reads_in_free_space() -> None:
    """The R0.5 MAX over MHA-SM-VN-51 / LOOP CLEARS stands up-right of the
    upper corner round: its radial leader crosses only extension lines, its
    text no line."""
    scale = drawing._S / 1000.0
    radius = drawing.UNDERHEAD_CORNER_R_SHEET
    assert radius == pytest.approx(geom.UNDERHEAD_CORNER_R * scale)
    cx, cy = drawing.UNDERHEAD_CORNER_CENTER_XY
    # The round's circle touches the face and the body's upper silhouette.
    assert cx - radius == pytest.approx(drawing.UNDERHEAD_X)
    assert cy - radius == pytest.approx(drawing.BODY_TOP_Y)
    # The text stands opposite the arc's down-left quarter, so the arrow
    # lands on the circle at the leader's angle (the vertical rod's recipe),
    # and the tip, the bend and the centre are one radial line.
    angle = drawing.UNDERHEAD_CORNER_LEADER_DEG
    assert 0.0 < angle < 90.0
    tip_x, tip_y = drawing.UNDERHEAD_CORNER_TIP_XY
    assert math.hypot(tip_x - cx, tip_y - cy) == pytest.approx(radius)
    bend_x, bend_y = drawing.UNDERHEAD_CORNER_BEND_X, drawing.UNDERHEAD_CORNER_BEND_Y
    tan = math.tan(math.radians(angle))
    assert bend_y - cy == pytest.approx((bend_x - cx) * tan)
    assert tip_y - cy == pytest.approx((tip_x - cx) * tan)

    def leader_y(x: float) -> float:
        return cy + (x - cx) * tan

    # The leader passes over a 6.35-mm upper arrow stub on the body Ø (as the
    # earlier seat Ø's rendered, farm run 20261027T053051351Z) and crosses
    # only the two stations' extension lines.
    assert leader_y(drawing.BODY_DIA_X) >= drawing.BODY_TOP_Y + 0.00635 + 0.0003
    assert tip_x < drawing.BODY_DIA_X < drawing.PLAIN_X < drawing.FULL_THREAD_X
    # It bends 2 mm or more past the 5.71 station's extension line, under the
    # plain length's dimension line.
    assert bend_x - drawing.FULL_THREAD_X >= 0.002
    assert bend_y <= drawing.PLAIN_LENGTH_LINE_Y - 0.010
    # "R0.5 max." over "MHA-SM-VN-51" over "LOOP CLEARS" (rule 4), below the
    # value since an above-callout line break would not print; the block
    # centres on the anchor, its shoulder under the last row.
    assert spec.DIMENSION_CALLOUTS["ShankProfile"]["UnderHeadCornerR"] == (
        f"{spec.COUNTER_SPRING_NUMBER}\nLOOP CLEARS"
    )
    assert "ShankProfile" not in spec.DIMENSION_CALLOUTS_ABOVE
    assert spec.COUNTER_SPRING_NUMBER == "MHA-SM-VN-51"
    text_x, text_y = drawing.SIDE_KEEP["UnderHeadCornerR"]
    assert (text_x, text_y) == drawing.UNDERHEAD_CORNER_TEXT_XY
    assert text_y - bend_y == pytest.approx(0.0028 + 2.0 * 0.00556 / 2.0)
    left = text_x - drawing.UNDERHEAD_CORNER_TEXT_WIDTH / 2.0
    right = text_x + drawing.UNDERHEAD_CORNER_TEXT_WIDTH / 2.0
    assert bend_x == pytest.approx(left - drawing.RADIAL_BEND_GAP)
    ink_bottom = bend_y + 0.0009
    ink_top = bend_y + drawing.UNDERHEAD_CORNER_TEXT_HEIGHT
    assert drawing.UNDERHEAD_CORNER_TEXT_HEIGHT == pytest.approx(2 * 0.00556 + 0.0045)
    # Clear of the 5.71 station's extension line, under the plain length's
    # dimension line, over the body, and short of the thread note and its
    # leader (whose lowest end is the pick).
    assert left >= drawing.FULL_THREAD_X + 0.003
    assert ink_top <= drawing.PLAIN_LENGTH_LINE_Y - 0.004
    assert ink_bottom >= drawing.BODY_TOP_Y + 0.015
    assert right <= drawing.THREAD_PICK[0] - 0.007
    assert right <= drawing.THREAD_NOTE_XY[0] - 0.015


def test_relief_chamfer_reads_over_the_head_clear_of_its_neighbours() -> None:
    """The relief's '1.50/1.40' over its three callout rows stands left of
    its 5.8-mm span, over the head: above the slot depth's text and left of
    the full-thread block, so no line strikes its text."""
    scale = drawing._S / 1000.0
    assert drawing.UNDERHEAD_X - drawing.HEAD_RELIEF_X == pytest.approx(
        geom.HEAD_RELIEF_CHAMFER * scale
    )
    assert drawing.TOP_X < drawing.SLOT_FLOOR_X < drawing.HEAD_RELIEF_X
    assert drawing.HEAD_RELIEF_TEXT_HEIGHT == drawing.block_height(2, 3)
    x, y = drawing.SIDE_KEEP["HeadReliefChamfer"]
    assert (x, y) == drawing.HEAD_RELIEF_TEXT_XY
    left = x - drawing.HEAD_RELIEF_TEXT_WIDTH / 2.0
    right = x + drawing.HEAD_RELIEF_TEXT_WIDTH / 2.0
    bottom = drawing.HEAD_RELIEF_LINE_Y
    top = bottom + drawing.HEAD_RELIEF_TEXT_HEIGHT
    assert y == pytest.approx((bottom + top) / 2.0)
    assert right <= drawing.HEAD_RELIEF_X - 0.003 + 1e-12
    # Over the slot depth's text (centred on its anchor, 4.5 mm of ink).
    sd_x, sd_y = drawing.SIDE_KEEP["SlotDepth"]
    assert bottom - (sd_y + 0.0045 / 2.0) >= 0.005
    # Left of the full-thread block, whose height it shares.
    ft_x, _ft_y = drawing.SIDE_KEEP["FullThread"]
    assert ft_x - drawing.FULL_THREAD_TEXT_WIDTH / 2.0 - right >= 0.002
    # Right of the head Ø's text and inside the border's top.
    assert left > drawing.SIDE_KEEP["HeadDia"][0] + 0.002
    assert top <= 0.2667 - 0.010


def test_station_reference_is_saved_hidden_and_imported_per_view() -> None:
    build = Path(part.__file__).read_text(encoding="utf-8")
    blank = 'blank_sketch(adapter, "StationReference")'
    assert blank in build
    assert build.index(blank) < build.rindex("save_part_and_images(adapter, PART_NAME)")
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "from _drawing_hidden_sketches import curate_view_dimensions" in source
    assert "StationReference" in spec.DRAWING_DIMENSIONS


def test_readback_contract_mirrors_every_printed_and_callout_control() -> None:
    printed = {name for names in spec.DRAWING_DIMENSIONS.values() for name in names}
    assert set(drawing.PRINTED_DIMENSIONS) == printed
    limits = {name: row for name, row in drawing.PRINTED_DIMENSIONS.items() if row[1]}
    # The builder's limits: the body Ø's, the head Ø's and the relief
    # chamfer's LIMIT bands, the plain length's single MIN, the full-thread
    # station's and the under-head corner's single MAX.
    assert limits == {
        "BodyDia": (geom.BODY_DIA, 3),
        "HeadDia": (11.50, 3),
        "HeadReliefChamfer": (1.45, 3),
        "PlainLength": (3.60, 5),
        "FullThread": (5.71, 6),
        "UnderHeadCornerR": (0.5, 6),
    }
    # The corner's radius lands on the side view's upper round, checked on
    # the rebuilt arrow tip.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "_dress_underhead_corner(adapter, side, side_annotations)" in source
    corner = inspect.getsource(drawing._dress_underhead_corner)
    for step in (
        "display.ArcExtensionLineOrOppositeSide = True",
        'rebuild_drawing(adapter, label="under-head corner radius leader")',
        "model_point_in_view(",
    ):
        assert step in corner
    assert "for name in sorted(REFERENCE_DIMENSIONS):" in source
    assert 'offset_dimension_text(adapter, side_annotations, {"BodyDia": ' in source
    assert drawing.PRINTED_DIMENSIONS["TipChamfer"] == (geom.TIP_CHAMFER, 0)
    assert drawing.PRINTED_DIMENSIONS["OverallLength"][0] == pytest.approx(26.10)
    # Unprinted controls: each chamfer's rise, held to its axial leg so the
    # "X 45 DEG" callouts are true.
    assert drawing.SOURCE_ONLY_DIMENSIONS == {
        "TipChamferRise@ShankProfile": (geom.TIP_CHAMFER, 0),
        "HeadReliefChamferRise@HeadProfile": (geom.HEAD_RELIEF_CHAMFER, 0),
    }
    # The part authors every callout on the dimension it marks; the drawing
    # writes none.  The full-thread limit alone carries its callout above
    # the value.
    callouts = spec.DIMENSION_CALLOUTS_BY_NAME
    assert set(callouts) == {
        "BodyDia",
        "HeadDia",
        "HeadReliefChamfer",
        "TipChamfer",
        "UnderHeadCornerR",
        "PlainLength",
    }
    assert spec.DIMENSION_CALLOUTS_ABOVE_BY_NAME == {"FullThread": "TO FULL THREAD"}
    assert callouts["UnderHeadCornerR"] == "MHA-SM-VN-51\nLOOP CLEARS"
    assert callouts["TipChamfer"] == spec.CHAMFER_CALLOUT
    for by_feature in (spec.DIMENSION_CALLOUTS, spec.DIMENSION_CALLOUTS_ABOVE):
        for feature, names in by_feature.items():
            assert set(names) <= spec.DRAWING_DIMENSIONS[feature]
    assert part.DIMENSION_CALLOUTS is spec.DIMENSION_CALLOUTS
    assert part.DIMENSION_CALLOUTS_ABOVE is spec.DIMENSION_CALLOUTS_ABOVE
    build = Path(part.__file__).read_text(encoding="utf-8")
    assert "((4, DIMENSION_CALLOUTS), (3, DIMENSION_CALLOUTS_ABOVE))" in build
    readback = inspect.getsource(drawing._verify_printed_dimensions)
    assert "(3, DIMENSION_CALLOUTS_ABOVE_BY_NAME)" in readback
    assert "set_dimension_callouts" not in source


def test_drawing_runs_the_readbacks_after_the_last_rebuild() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "_verify_source_dimensions(adapter.currentModel)" in source
    assert "settled_checks=(lambda: _verify_printed_dimensions(" in source
    # Every enforced-sheet view, the isometric included, renders with hidden
    # lines removed.
    assert "for view in (side, end, iso):\n        set_hidden_lines_removed(" in source
