"""Observable package contract for the frame assembly drawing."""

import draw_fr_frame_assembly as drawing
import fr_frame_assembly_sheet as notes


def test_frame_package_bom_identifies_all_29_released_components() -> None:
    assert drawing.BOM_QUANTITIES == {
        "fr-harmonic-base": 1,
        "fr-tube-frame": 4,
        "fr-vn-tube-frame-cap": 4,
        "fr-rocker-arm-support": 1,
        "fr-vn-lag-screw": 4,
        "fr-top-frame": 1,
        "fr-nameplate": 1,
        "sh-vn-brass-fillister-screw": 4,
        "fr-vn-frame-cross-screw": 8,
        "fr-vn-gooseneck-set-screw": 1,
    }
    assert drawing.BOM_PART_NUMBERS == {
        "fr-harmonic-base": "MHA-FR-01",
        "fr-tube-frame": "MHA-FR-03",
        "fr-vn-tube-frame-cap": "MHA-FR-VN-54",
        "fr-rocker-arm-support": "MHA-FR-05",
        "fr-vn-lag-screw": "MHA-FR-VN-51",
        "fr-top-frame": "MHA-FR-02",
        "fr-nameplate": "MHA-FR-04",
        "sh-vn-brass-fillister-screw": "MHA-SH-VN-51",
        "fr-vn-frame-cross-screw": "MHA-FR-VN-53",
        "fr-vn-gooseneck-set-screw": "MHA-FR-VN-52",
    }


# --- sheet projection of model points -------------------------------------
#
# The doubles below are raw dispatches: they answer ``InvokeTypes`` only and
# assert the whole (dispid, lcid, flags, return type, argument types) header
# the SolidWorks 2026 type library gives each member (flags 1 = method,
# 2 = property get; 9 = IDispatch, 12 = VARIANT).

import math  # noqa: E402
import re  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import pytest  # noqa: E402

import _drawing_projection  # noqa: E402
import _telemetry  # noqa: E402

GET_MATH_UTILITY = (132, 0, 1, (9, 0), ())
MODEL_TO_VIEW_TRANSFORM = (221, 0, 2, (9, 0), ())
CREATE_POINT = (5, 0, 1, (9, 0), ((12, 1),))
MULTIPLY_TRANSFORM = (1, 0, 1, (9, 0), ((9, 1),))
ARRAY_DATA = (3, 0, 2, (12, 0), ())


class RawDispatch:
    """A bare ``PyIDispatch`` stand-in keyed by dispid; any other header fails."""

    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def InvokeTypes(self, dispid, lcid, flags, ret_type, arg_types, *args):  # noqa: N802
        header = (dispid, lcid, flags, ret_type, arg_types)
        self.calls.append(header)
        assert dispid in self.answers, f"unexpected dispid {dispid}"
        expected, answer = self.answers[dispid]
        assert header == expected
        return answer(*args) if callable(answer) else answer


# Model-to-sheet: rotate +90 deg about Z, scale 1:5, then translate to the
# view centre (0.150, 0.100) m.  ArrayData layout: row-major rotation (row i
# is the image of axis i), translation, scale, three unused.
VIEW_TRANSFORM = (0, 1, 0, -1, 0, 0, 0, 0, 1, 0.150, 0.100, 0.0, 0.2, 0, 0, 0)


class Projection:
    """``adapter`` and ``view`` whose projection runs through raw dispatches."""

    def __init__(self, *, fail_at: int | None = None):
        # The raw headers come from the checked-in makepy wrapper.
        pytest.importorskip("win32com.client")
        self.created = 0
        self.fail_at = fail_at
        self.transform = RawDispatch({})
        self.transform.values = VIEW_TRANSFORM
        self.utility = RawDispatch({CREATE_POINT[0]: (CREATE_POINT, self._point)})
        self.adapter = SimpleNamespace(
            swApp=RawDispatch({GET_MATH_UTILITY[0]: (GET_MATH_UTILITY, self.utility)})
        )
        self.view = RawDispatch(
            {MODEL_TO_VIEW_TRANSFORM[0]: (MODEL_TO_VIEW_TRANSFORM, self.transform)}
        )

    def _point(self, array):
        assert array.varianttype == 8197  # VT_ARRAY | VT_R8
        index, self.created = self.created, self.created + 1
        xyz = tuple(array.value)

        def multiply(transform):
            assert transform is self.transform
            if index == self.fail_at:
                return None
            v = transform.values
            rotated = [sum(xyz[i] * v[3 * i + j] for i in range(3)) for j in range(3)]
            sheet = [v[12] * rotated[j] + v[9 + j] for j in range(3)]
            return RawDispatch({ARRAY_DATA[0]: (ARRAY_DATA, tuple(sheet))})

        return RawDispatch({MULTIPLY_TRANSFORM[0]: (MULTIPLY_TRANSFORM, multiply)})

    def reads(self, header):
        dispatches = {GET_MATH_UTILITY: self.adapter.swApp, MODEL_TO_VIEW_TRANSFORM: self.view}
        return dispatches[header].calls.count(header)


def test_checked_heights_print_their_model_values() -> None:
    """The overall reference prints the cap stack's .001 grid exactly. The top
    cross-bore axis (MHA-FR-02's taps, .72 under its rail top) sits on the
    .001 grid too, so it prints three places, with the rule-read band the
    setting needs (#2389) rather than the title block's .XXX. The dimension carries
    only its value and band; the setting step names it, from the model."""
    from _title_block_units import render_number

    cap_in = drawing.CAP_TOP_Y / 25.4
    assert cap_in == pytest.approx(round(cap_in, drawing.HEIGHT_PLACES), abs=1e-9)
    assert drawing.HEIGHT_PLACES == 3
    assert drawing.TOP_AXIS_HEIGHT_PLACES == 3
    axis_in = drawing.TOP_SCREW_Y / 25.4
    assert axis_in == pytest.approx(round(axis_in, 3), abs=1e-9)
    assert drawing.TOP_AXIS_HEIGHT_BAND_MM == pytest.approx(0.030 * 25.4)
    printed = render_number(axis_in, drawing.UNIT, drawing.TOP_AXIS_HEIGHT_PLACES)
    band = render_number(
        drawing.TOP_AXIS_HEIGHT_BAND_MM / 25.4, drawing.UNIT, drawing.TOP_AXIS_HEIGHT_PLACES
    )
    assert notes.TOP_AXIS_HEIGHT_TEXT == f"{printed} ±{band}"
    assert notes.TOP_AXIS_HEIGHT_TEXT in _step(notes.steps.TOP_AXIS_SET_KEY)
    assert not hasattr(drawing, "TOP_AXIS_HEIGHT_SUFFIX")


def test_top_frame_underside_is_the_knife_mount_seat_plane() -> None:
    from build_sm_knife_mount import CASTING_UNDERSIDE_Y, MOUNT_GAP
    from fr_frame_attachment_spec import TOP_FRAME_MID_Y, TOP_FRAME_RAIL_TOP_Y
    from fr_top_frame_spec import HALF_H

    # The knife mounts clamp to it and the hanger washers seat on the rail
    # top one band above it: exact contact, no overlap and no gap.
    assert MOUNT_GAP == 0.0
    assert TOP_FRAME_MID_Y - HALF_H == pytest.approx(CASTING_UNDERSIDE_Y, abs=1e-9)
    assert TOP_FRAME_MID_Y + HALF_H == pytest.approx(TOP_FRAME_RAIL_TOP_Y, abs=1e-9)


def test_a_batch_projects_every_point_through_one_transform_read() -> None:
    projection = Projection()
    points = [(0.010, 0.020, 0.030), (0.100, 0.0, 0.0), (-0.050, 0.050, 0.0)]
    sheet = _drawing_projection.model_points_in_view(
        projection.adapter, projection.view, points, label="batch"
    )
    flat = [value for xy in sheet for value in xy]
    assert flat == pytest.approx([0.146, 0.102, 0.150, 0.120, 0.140, 0.090])
    assert projection.reads(MODEL_TO_VIEW_TRANSFORM) == 1
    assert projection.reads(GET_MATH_UTILITY) == 1
    assert projection.created == 3


def test_one_point_projects_to_the_same_sheet_position_as_a_batch() -> None:
    projection = Projection()
    assert _drawing_projection.model_point_in_view(
        projection.adapter, projection.view, (0.010, 0.020, 0.030), label="one"
    ) == pytest.approx((0.146, 0.102))


def test_a_failed_point_names_its_index_identity_and_progress(monkeypatch) -> None:
    recorded = {}
    monkeypatch.setattr(
        _telemetry, "annotate", lambda **attrs: recorded.update(attrs)
    )
    projection = Projection(fail_at=2)
    with pytest.raises(RuntimeError) as failure:
        _drawing_projection.model_points_in_view(
            projection.adapter,
            projection.view,
            [(0.0, 0.0, 0.0), (0.001, 0.0, 0.0), (0.002, 0.0, 0.0)],
            label="ends",
            names=["a start", "a end", "b start"],
        )
    message = str(failure.value)
    assert "ends: b start (index 2 of 3) at model (0.002, 0.0, 0.0)" in message
    assert "failed after 2 projected" in message
    assert recorded == {
        "points": 3, "failed_index": 2, "failed_point": "b start", "projected": 2
    }


def _step(key: str) -> str:
    return notes.STEP_TEXT[key]


def test_step_numbers_follow_the_registry_and_unknown_keys_are_refused() -> None:
    steps = notes.steps
    assert tuple(notes.STEP_TEXT) == steps.SEQUENCE
    for index, key in enumerate(steps.SEQUENCE, start=1):
        assert steps.step_number(key) == index
        assert steps.step_ref(key) == f"MHA-FR-00 STEP {index}"
    with pytest.raises(KeyError):
        steps.step_number("no-such-step")
    printed = [step for _title, group in notes.STEP_SECTIONS for step in group]
    assert printed == [
        f"{index}. {notes.STEP_TEXT[key]}"
        for index, key in enumerate(steps.SEQUENCE, start=1)
    ]


def test_every_step_is_one_short_instruction() -> None:
    # Rule 22: at most six lines, wrapped at 100 characters as ASSEMBLY.md is read.
    import textwrap

    for _title, group in notes.STEP_SECTIONS:
        for step in group:
            assert len(textwrap.wrap(step, width=100, subsequent_indent="   ")) <= 6, step


def test_each_check_and_remedy_is_its_own_step() -> None:
    # A step that checks only checks; a remedy (IF ...) is its own step.
    for key, text in notes.STEP_TEXT.items():
        if text.startswith("CHECK"):
            assert " AND REPEAT" not in text and "IF " not in text, key
        if text.startswith("IF "):
            assert "CHECK " not in text, key


def test_each_push_on_cap_has_a_bench_retention_check_and_a_remedy() -> None:
    # R7 machinist review (rule 23): the cap's push-on grip is its only axial
    # retention, so it is accepted by hand right after seating, and a loose
    # cap is replaced and re-pushed until that check passes.
    steps = notes.steps
    order = [
        steps.step_number(key)
        for key in (
            "caps-pushed-on",
            "caps-checked",
            "caps-retained-checked",
            "caps-replaced",
        )
    ]
    assert order == list(range(order[0], order[0] + 4))
    check = _step("caps-retained-checked")
    assert check.startswith("CHECK") and "PULL OFF OR TURN BY HAND" in check
    remedy = _step("caps-replaced")
    assert remedy.startswith("IF ") and "REPLACE" in remedy
    assert f"STEP {steps.step_number('caps-pushed-on')}" in remedy
    assert f"STEP {steps.step_number('caps-retained-checked')} PASSES" in remedy


def test_no_view_label_repeats_its_sheet_scale() -> None:
    # Over-specification: the title block prints each sheet's scale.
    for caption in (drawing.EXPLODED_CAPTION, drawing.ASSEMBLY_ISO_CAPTION):
        assert not re.search(r"\d+\s*:\s*\d+", caption)
    assert "ASSEMBLY.MD" in drawing.EXPLODED_CAPTION
    assert set(drawing.SHEET_LAYOUTS) == set(drawing.SHEET_SCALES) == set(drawing.SHEET_NAMES)


def test_setting_rows_are_cited_by_their_steps_and_clear_the_title_block() -> None:
    # R5 machinist review (rule 22): the rough-cut length and the cross
    # screws' full-thread acceptance print in sheet 1's setting table; each
    # row's step cites it without repeating its value, every row is cited,
    # and the columns' budget clears the title block.
    from _general_table import table_column_widths
    from _drawing_types import DRAWING_TEMPLATES

    steps = notes.steps
    assert drawing.SETTING_TABLE_SHEET == drawing.SHEET_NAMES[0]
    assert notes.SETTING_TABLE_ROWS == (
        (
            "1",
            str(steps.step_number(steps.COLUMNS_ROUGH_CUT_KEY)),
            "ITEM 2 ROUGH-CUT LENGTH",
            notes.COLUMN_ROUGH_CUT_LENGTH_TEXT,
            "STEEL RULE",
        ),
        (
            "2",
            str(steps.step_number("cross-screws-measured")),
            "ITEM 9 FULL THREAD UNDER HEAD",
            notes.CROSS_SCREW_FULL_THREAD_LIMIT_TEXT,
            "CALIPER",
        ),
    )
    for row in notes.SETTING_TABLE_ROWS:
        key = steps.SEQUENCE[int(row[1]) - 1]
        text = notes.STEP_TEXT[key]
        assert f"SETTING TABLE ROW {row[0]} (SHEET 1)" in text, key
        assert row[3] not in text, key
    cited = re.findall(r"SETTING TABLE ROW (\d+)", " ".join(notes.STEP_TEXT.values()))
    assert sorted(cited) == [row[0] for row in notes.SETTING_TABLE_ROWS]
    # The columns' budget stays left of the title block.
    width = sum(
        table_column_widths(notes.SETTING_TABLE_HEADER, notes.SETTING_TABLE_ROWS)
    )
    template = DRAWING_TEMPLATES[drawing.SHEET_LAYOUTS[drawing.SETTING_TABLE_SHEET]]
    assert (
        drawing.SETTING_TABLE_XY[0] + width
        <= template.title_block_left_m - drawing.SETTING_TABLE_CLEARANCE_M
    )


def test_steps_name_parts_by_item_and_use_no_private_vocabulary() -> None:
    steps = " ".join(notes.STEP_TEXT.values())
    for word in (
        "GOOSENECK", "DECK", "NEAR-WALL", "FAR-WALL", "NEAR WALL", "FAR WALL",
        "LOWER AXIS", "TOP AXIS", "FRONT", "REAR", "DECORATED", "HUB", "DIA ",
    ):
        assert word not in steps, word
    # A BOM part number prints only as the drawing a callout lives on.
    for number in drawing.BOM_PART_NUMBERS.values():
        assert re.findall(rf"(?<!DRAWING ){re.escape(number)}\b", steps) == [], number
    cited = {int(n) for n in re.findall(r"\bITEM (\d+)", steps)}
    assert cited == set(notes.ITEM_NUMBERS.values())


def test_the_bom_items_the_steps_cite_are_the_native_tables() -> None:
    native_order = (
        "fr-harmonic-base", "fr-tube-frame", "fr-rocker-arm-support",
        "fr-vn-lag-screw", "fr-top-frame", "fr-vn-tube-frame-cap",
        "fr-nameplate", "sh-vn-brass-fillister-screw",
        "fr-vn-frame-cross-screw", "fr-vn-gooseneck-set-screw",
    )
    assert notes.ITEM_NUMBERS == {
        stem: index for index, stem in enumerate(native_order, start=1)
    }



def test_the_support_windows_face_the_short_ends_of_item_1() -> None:
    # The builder turns MHA-FR-05 so its window normal (local Z, row 2)
    # runs along machine X, the base's length: the windows face the ends.
    import build_fr_frame_assembly as frame
    from fr_harmonic_base_spec import DECK_LENGTH, DECK_WIDTH

    assert [abs(value) for value in frame.SUPPORT_ROWS[2]] == [1.0, 0.0, 0.0]
    assert DECK_LENGTH > DECK_WIDTH
    assert "SHORT ENDS" in _step("support-seated")
    assert not any("LONG SIDES" in text for text in notes.STEP_TEXT.values())


def _nameplate_keys() -> list[str]:
    steps = notes.steps
    return [
        steps.NAMEPLATE_SET_KEY,
        "nameplate-clamped",
        steps.NAMEPLATE_SPOTTED_KEY,
        "nameplate-lifted",
        steps.NAMEPLATE_SEATS_TAPPED_KEY,
        steps.NAMEPLATE_SCREWED_KEY,
    ]


def test_the_nameplate_is_set_then_its_base_seats_are_spotted_through_it() -> None:
    # #628: the base sheet prints the four nameplate seats as TRANSFER FROM
    # MHA-FR-04 AT ASSEMBLY, so the plate is located on the base first, then
    # spotted through, drilled and tapped before the screws go in.
    import build_fr_harmonic_base as base

    steps = notes.steps
    assert drawing.NAMEPLATE_END_INSET == pytest.approx(base.NAMEPLATE_DECK_CLEARANCE)
    numbers = [steps.step_number(key) for key in _nameplate_keys()]
    assert numbers == list(range(numbers[0], numbers[0] + len(numbers)))
    # The inset is section B-B's native dimension, never a number in the note.
    placed = _step(steps.NAMEPLATE_SET_KEY)
    assert "SECTION B-B" in placed
    assert not re.search(r"\d\.\d", placed)
    assert drawing.BOM_PART_NUMBERS[notes.BASE] in _step(steps.NAMEPLATE_SEATS_TAPPED_KEY)


def test_the_nameplate_seats_are_tapped_before_the_columns_go_in() -> None:
    # #2390: the bare base goes on the mill for its nameplate seats; once the
    # columns and top frame stand on it, it cannot.
    steps = notes.steps
    tapped = steps.step_number(steps.NAMEPLATE_SEATS_TAPPED_KEY)
    assert tapped < steps.step_number("base-sockets-fitted")
    assert notes.STEP_GROUPS[0][1] == steps.NAMEPLATE_SET_KEY


def test_tube_cross_holes_are_spotted_through_the_clearance_hole_not_drilled() -> None:
    # #2388: nothing is drilled through a casting's clearance hole toward the
    # tapped far wall; the spot is transferred and the tube drilled off the
    # frame. The punch enters the clearance hole with little play.
    from fr_frame_cross_screw import NEAR_WALL_CLEARANCE_DIAMETER

    play = NEAR_WALL_CLEARANCE_DIAMETER / 25.4 - notes.TRANSFER_PUNCH
    assert 0.0 < play <= 0.005
    steps = notes.steps
    marked = steps.step_number(steps.LOWER_HOLES_MARKED_KEY)
    lifted = steps.step_number("lower-columns-lifted")
    drilled = steps.step_number(steps.LOWER_HOLES_DRILLED_KEY)
    assert marked < lifted < drilled
    # The screw is tried in the seated column, where a hole off the
    # casting's screw line shows, and the remedy works the tube hole.
    reseated = steps.step_number(steps.COLUMNS_RESEATED_KEY)
    checked = steps.step_number(steps.LOWER_HOLES_CHECKED_KEY)
    assert drilled < reseated < checked
    assert steps.SEQUENCE[checked] == "lower-holes-reworked"
    reassembled = steps.step_number("frame-reassembled")
    upper_checked = steps.step_number(steps.UPPER_HOLES_CHECKED_KEY)
    assert steps.step_number("upper-holes-drilled") < reassembled < upper_checked
    assert notes.TRANSFER_PUNCH_TEXT == "13/64"
    assert notes.TRANSFER_PUNCH_TEXT in _step(steps.LOWER_HOLES_MARKED_KEY)
    assert "DRILL" not in _step(steps.LOWER_HOLES_MARKED_KEY)


def test_the_set_screw_step_points_to_the_drawing_step_that_tightens_it() -> None:
    # Rule 23 at the package boundary (machinist review blocker): the member
    # it grips is named and MHA-HA-00's levelling step tightens it there.
    import ha_harmonic_analyzer_assembly_steps as ha_steps

    steps = notes.steps
    started = _step(steps.GOOSENECK_STARTED_KEY)
    assert ha_steps.step_ref("summing-levelled") in started
    assert notes.GOOSENECK_POST_NUMBER in started
    following = steps.SEQUENCE[steps.step_number(steps.GOOSENECK_STARTED_KEY)]
    assert notes.STEP_TEXT[following].startswith("CHECK")
    assert notes.GOOSENECK_POST_NUMBER in notes.STEP_TEXT[following]


def test_the_nameplate_spot_through_is_declared_on_the_assembly() -> None:
    """The nameplate's spot-through fit-up is an owner-accepted rule-19
    departure: the nominal screw float cannot absorb independent plate/base
    stations."""
    import sh_vn_brass_fillister_screw_spec as screw
    import fr_harmonic_base_spec as base_spec
    import fr_nameplate_drawing_spec as plate
    import fr_nameplate_spec as nameplate
    from _assembly_contract import assembly_contract
    from _drawing_registry import DRAWINGS_BY_NAME
    from _paths import CAD_ROOT
    from _printed_tolerance import printed_band_mm
    from machinist_exceptions import load_exceptions

    name = "fr_frame_assembly"
    assert DRAWINGS_BY_NAME[name].source_kind == "assembly"
    entries = {
        entry.id: entry
        for entry in load_exceptions(CAD_ROOT / "config", name, "assembly")
    }
    entry = entries["RV-01"]
    assert not [id_ for id_ in entries if "1667" in id_]
    assert (entry.id, entry.kind) == ("RV-01", "accept")
    assert re.search(r"\brule 19\b", entry.finding)
    first, last = (notes.steps.step_number(key) for key in _nameplate_keys()[::5])
    assert re.search(rf"\bsteps {first}-{last}\b", entry.where)
    assert not re.search(r"\bstep 9\b", entry.where)
    # Without the spot-through, the plate's .XX station and the base's .XXX
    # tap station, each on both axes, demand far more diametral float than the
    # screw has.
    float_mm = plate.SCREW_HOLE_DIA - screw.SHANK_DIA
    station_band = printed_band_mm(
        plate.DRAWING_PRECISION["ScrewHoles"]["S0X"], unit=nameplate.UNIT
    )
    demand_mm = 2.0 * math.sqrt(2.0) * (
        station_band
        + printed_band_mm(base_spec.HOLE_TABLE_PRECISION, unit=base_spec.UNIT)
    )
    assert float_mm < demand_mm
    # The build reads the same file and ignores the declaration.
    assert assembly_contract("fr-frame").number == "MHA-FR-00"


def test_height_dimensions_stand_clear_of_the_cutting_plane_letters() -> None:
    # PR #1468 r4 machinist review: the (1044.8) line struck the right-hand
    # B-B letter, and the A-A arrow shared its corridor. Both height lines now
    # stand right of the letters and left of section A-A, each with clearance;
    # the sections stay apart and inside the border.
    from fr_harmonic_base_spec import BOTTOM_LENGTH

    front_half = BOTTOM_LENGTH / 2.0 / 8.0 / 1000.0  # the 1:8 view's flange
    section_half = BOTTOM_LENGTH / 2.0 / 3.0 / 1000.0  # both 1:3 sections
    letters_right = (
        drawing.WORKING_FRONT_CENTER[0] + front_half + drawing.CUTTING_LETTER_REACH_M
    )
    top_axis_x = drawing.TOP_AXIS_HEIGHT_TEXT_XY[0]
    overall_x = drawing.OVERALL_HEIGHT_TEXT_XY[0]
    base_left = drawing.BASE_SECTION_CENTER[0] - section_half
    clearance = drawing.HEIGHT_LINE_CLEARANCE_M
    assert letters_right + clearance <= top_axis_x
    assert top_axis_x + clearance <= overall_x
    # r6 review: a visible gap between the front view's dimensions and A-A.
    assert overall_x + drawing.VIEW_GAP_M <= base_left
    assert drawing.VIEW_GAP_M >= 0.006
    base_right = drawing.BASE_SECTION_CENTER[0] + section_half
    top_left = drawing.TOP_SECTION_CENTER[0] - section_half
    top_right = drawing.TOP_SECTION_CENTER[0] + section_half
    assert top_left - base_right >= 0.006
    assert top_right <= 0.4191 - 0.002  # B-size inner border, 17 in less 0.5 in


def _frame_balloon_clearance_fixture():
    # Sheet metres, matching the two adjacent lanes on the reviewed sheet 2.
    return {
        "bottom": 0.314,
        "circle": (0.127, 0.297, 0.005),
        "cap_circle": (0.114, 0.306, 0.005),
        "leader": (0.125, 0.2925, 0.0, 0.116, 0.277, 0.0),
        "cap_leader": (0.1135, 0.301, 0.0, 0.112, 0.280, 0.0),
    }


def test_lowered_set_screw_balloon_clears_bom_and_cap_leader() -> None:
    assert drawing._frame_bom_balloon_failures(**_frame_balloon_clearance_fixture()) == []


@pytest.mark.parametrize(
    ("change", "failure"),
    [
        ({"circle": (0.127, 0.315, 0.005)}, "bom_rule_clearance"),
        ({"bottom": 0.303}, "bom_rule_clearance"),
        ({"circle": (0.119, 0.306, 0.005)}, "cap_balloon_clearance"),
        ({"leader": (0.125, 0.2925, 0.0, 0.105, 0.280, 0.0)}, "cap_leader_collision"),
        ({"cap_leader": (0.127, 0.300, 0.0, 0.127, 0.280, 0.0)}, "cap_leader_collision"),
        ({"cap_leader": ()}, "missing_leader"),
    ],
)
def test_native_bom_or_neighbour_collision_refuses_set_screw_placement(change, failure) -> None:
    state = _frame_balloon_clearance_fixture()
    state.update(change)
    assert failure in drawing._frame_bom_balloon_failures(**state)


def _isometric_mm(point: tuple[float, float, float]) -> tuple[float, float]:
    """Model mm on a SolidWorks *Isometric, Y up: right (1, 0, -1)/sqrt 2,
    up (-1, 2, -1)/sqrt 6, in model mm at 1:1."""
    x, y, z = point
    return (x - z) / math.sqrt(2.0), (2.0 * y - x - z) / math.sqrt(6.0)


def _box_corners(x, y, z):
    return [(a, b, c) for a in x for b in y for c in z]


def _deck_detail_boxes():
    """Each detail's exploded parts, as model-mm boxes from their specs."""
    import fr_frame_explode_spec as explode
    import fr_nameplate_spec as plate
    from fr_harmonic_base_spec import STACK_HEIGHT
    from fr_rocker_arm_support_spec import SUPPORT_HOLD_DOWN_XZ
    from fr_vn_lag_screw_spec import HEAD_AF
    from sh_vn_brass_fillister_screw_spec import HEAD_DIA, HEAD_H

    head = HEAD_AF / math.sqrt(3.0)  # hex corner radius
    screw_x = [x for x, _z in SUPPORT_HOLD_DOWN_XZ]
    screw_z = [z for _x, z in SUPPORT_HOLD_DOWN_XZ]
    support = _box_corners(
        (
            min(screw_x) - head + explode.SUPPORT_ASIDE_X,
            max(screw_x) + head + explode.SUPPORT_ASIDE_X,
        ),
        (
            STACK_HEIGHT + explode.SUPPORT_LIFT,
            drawing._LAG_SCREW_UNDER_HEAD_Y
            + drawing.LAG_HEAD_H
            + explode.SUPPORT_LIFT
            + explode.SUPPORT_SCREW_WITHDRAW,
        ),
        (min(screw_z) - head, max(screw_z) + head),
    )
    lift = explode.NAMEPLATE_LIFT
    x0 = plate.MOUNT_POS[0] + explode.NAMEPLATE_ASIDE_X
    z0 = plate.MOUNT_POS[2]
    nameplate = _box_corners(
        (x0 - plate.PLATE_HEIGHT, x0),
        (
            plate.MOUNT_FRONT_Y - plate.PLATE_THICKNESS + lift,
            plate.MOUNT_FRONT_Y + HEAD_H + explode.NAMEPLATE_SCREW_WITHDRAW + lift,
        ),
        (z0 - plate.PLATE_WIDTH - HEAD_DIA / 2.0, z0 + HEAD_DIA / 2.0),
    )
    return {"C": support, "D": nameplate}


def test_each_deck_detail_circle_holds_its_exploded_hardware() -> None:
    boxes = _deck_detail_boxes()
    for detail in drawing.DECK_DETAILS:
        centre = _isometric_mm(detail.centre_xyz)
        reach = max(
            math.dist(_isometric_mm(corner), centre) for corner in boxes[detail.letter]
        )
        # The parts it enlarges, with at least 2 mm of model air to the crop.
        assert reach <= detail.crop_radius_mm - 2.0, (detail.letter, reach)
        # And no idle margin: the circle is no more than 20 % over its parts.
        assert reach >= detail.crop_radius_mm / 1.2, (detail.letter, reach)


def test_deck_details_stand_in_the_free_column_of_sheet_2() -> None:
    # Measured on sheet 2 of run 20261103T090647187Z: the exploded view's
    # balloons end 175 mm from the left, the inner border is at 267 mm, the
    # BOM's bottom rule at 314 mm and the title block's top at 66 mm.
    rows = []
    for detail in drawing.DECK_DETAILS:
        x, y = detail.centre
        r = detail.radius_m
        assert 0.185 <= x - r and x + r <= 0.267 - 0.002, detail.letter
        assert y + r <= 0.314 - 0.010, detail.letter
        label_bottom = detail.label_xy[1] - 3 * 0.005  # three note lines
        assert label_bottom >= 0.066 + 0.010, detail.letter
        rows.append((label_bottom, y + r))
    rows.sort()
    for (_, below_top), (above_label_bottom, _) in zip(rows, rows[1:]):
        assert below_top + 0.005 <= above_label_bottom
    assert {detail.letter for detail in drawing.DECK_DETAILS} == {"C", "D"}


def test_deck_detail_labels_name_their_bom_items() -> None:
    items = {stem: str(n) for n, stem in enumerate(drawing.BOM_COMPONENTS, 1)}
    assert drawing.SUPPORT_DETAIL.label_text(items) == (
        "DETAIL C\n"
        f"ITEMS {items['fr-rocker-arm-support']} AND {items['fr-vn-lag-screw']}\n"
        "SCALE 1:3"
    )
    assert drawing.NAMEPLATE_DETAIL.stems == (
        "fr-nameplate",
        "sh-vn-brass-fillister-screw",
    )


class _SourceModel:
    """The released source assembly as the drawing opens it: clean."""

    def __init__(self) -> None:
        self.dirty = False

    def GetSaveFlag(self) -> bool:
        return self.dirty

    def GetTitle(self) -> str:
        return "fr-frame-assembly.SLDASM"

    def GetType(self) -> int:
        return 2  # swDocASSEMBLY


def _frame_build(monkeypatch, tmp_path, *, dirty_at: str | None, entered=None):
    """Run ``drawing.build`` with every native step faked; the source goes
    dirty during ``dirty_at`` ("placement" or "finalize") if given.
    ``entered`` records each start of finalization."""
    source = tmp_path / "fr-frame-assembly.SLDASM"
    source.write_bytes(b"released")
    model = _SourceModel()
    finalized: list[bool] = []
    entered = [] if entered is None else entered

    def place_package(*_args):
        if dirty_at == "placement":
            model.dirty = True
        return lambda: None

    def finalize_drawing(_adapter, _outputs, *, settled_checks, **_kwargs):
        entered.append(True)
        if dirty_at == "finalize":
            model.dirty = True
        for settled in settled_checks:
            settled()
        finalized.append(True)
        return {"pdf": "fr-frame-assembly.pdf"}

    monkeypatch.setattr(drawing, "SOURCE", source)
    monkeypatch.setattr(drawing, "check", lambda *_args: None)
    monkeypatch.setattr(drawing, "read_required_properties", lambda *_args, **_kw: {})
    monkeypatch.setattr(drawing, "_validate_persisted_explode", lambda _model: None)
    monkeypatch.setattr(drawing, "_place_package", place_package)
    monkeypatch.setattr(drawing, "finalize_drawing", finalize_drawing)
    adapter = SimpleNamespace(
        currentModel=model,
        open_model=lambda _path: None,
        swApp=SimpleNamespace(
            CloseDoc=lambda _title: None, GetOpenDocumentByName=lambda _path: None
        ),
    )
    return drawing.build(adapter), finalized


def test_a_clean_source_lets_the_frame_drawing_finalize(monkeypatch, tmp_path) -> None:
    artifacts, finalized = _frame_build(monkeypatch, tmp_path, dirty_at=None)
    assert artifacts == {"pdf": "fr-frame-assembly.pdf"} and finalized == [True]


@pytest.mark.parametrize(
    ("dirty_at", "where", "finalizes"),
    [("placement", "package placement", False), ("finalize", "finalize rebuilds", True)],
)
def test_a_dirtied_source_fails_before_the_drawing_saves(
    monkeypatch, tmp_path, dirty_at, where, finalizes
) -> None:
    # #1364: a drawing step dirtied the writable released source and the
    # drawing's save rewrote it; the fingerprint only caught it afterwards.
    # As in drive-train's drawing, a dirty source now fails before the save:
    # a dirty placement never reaches finalization.
    entered: list[bool] = []
    with pytest.raises(RuntimeError, match=f"dirtied the released source assembly by {where}"):
        _frame_build(monkeypatch, tmp_path, dirty_at=dirty_at, entered=entered)
    assert entered == ([True] if finalizes else [])


def test_every_view_is_configured_before_the_bom(monkeypatch) -> None:
    # #1364, native trace on farm run 20261120T205805100Z-5f74...: DETAIL C's
    # exploded configuration, made after insert_bom_table, dirtied the
    # released source. Every view placement and configuration now precedes
    # the BOM; only the deck details' labels (they name BOM items) follow it.
    events: list[str] = []

    def record(name, result=None):
        def call(*_args, **_kwargs):
            events.append(name)
            return result

        return call

    sheet = SimpleNamespace(GetCurrentSheet=lambda: sheet, SetScale=lambda *_args: True)
    landing = SimpleNamespace(note=object())
    proof = SimpleNamespace(rebound=frozenset(), bound=(), short=())
    for name, result in {
        "_create_mixed_package_sheets": None,
        "_activate_sheet": None,
        "_early_bound": sheet,
        "place_view": object(),
        "set_hidden_lines_removed": None,
        "_configure_view": "Default",
        "_add_frame_height_dimensions": None,
        "_create_joint_sections": (object(), object()),
        "_add_nameplate_inset_dimension": object(),
        "_place_setting_table": None,
        "set_high_quality_shaded_with_edges": None,
        "_place_deck_detail": object(),
        "_place_finished_isometric": None,
        "insert_bom_table": object(),
        "_validate_frame_bom": [("fr-harmonic-base", "1")],
        "add_component_bom_balloons": [landing],
        "_reattach_frame_balloons": proof,
        "_place_frame_set_screw_balloon": object(),
        "_assert_frame_bom_balloon_clearance": None,
        "_add_note_block": None,
        "_mark_deck_details": None,
        "_label_deck_detail": None,
    }.items():
        monkeypatch.setattr(drawing, name, record(name, result))
    drawing._place_package(SimpleNamespace(currentModel=object()), lambda _name: None)
    bom = events.index("insert_bom_table")
    placing = {"place_view", "_configure_view", "_place_deck_detail", "_place_finished_isometric"}
    assert not placing & set(events[bom:])
    assert events.count("_place_deck_detail") == len(drawing.DECK_DETAILS)
    assert events.count("_label_deck_detail") == len(drawing.DECK_DETAILS)
    assert events.index("_label_deck_detail") > bom
