"""Offline contracts for the paper-drive assembly and its drawing (MHA-A06)."""

import ast
import inspect
import re
from itertools import product
from pathlib import Path

import pytest

import _assembly
import _config
import build_paper_drive_assembly as assembly
import draw_paper_drive_assembly as drawing
import drive_train_steps
import harmonic_base_spec as base
import nameplate_spec as nameplate
import paper_drive_assembly_steps as steps
import transgear_drive_collar_spec as collar
import transgear_removable_spec as sprocket
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME

STEP_HEAD = re.compile(r"^(\d+)\. ", re.MULTILINE)
STEP_POINTER = re.compile(r"(MHA-A\d{2})\s+STEP\s+(\d+)")
# Default-format note text, measured on r743-rocker-fix3's render (leaf
# 20260926T112244Z-1-a884759d), as test_channel_assembly_drawing uses them;
# #945 moves these into _drawing_common.
NOTE_CHAR_WIDTH = 0.00276
NOTE_LINE_PITCH = 0.0045
# Words no sheet of the package may print (drawing-simplicity policy).
FORBIDDEN_SHEET_WORDS = ("EXCEPTION", "ACCEPTED", "RULING", "POLICY", "BOOK FIDELITY")

# CONTRACT-paper-drive.md, the round-10 component set.
UNCHANGED_FAMILIES = {
    "support-bar",
    "column-clamp-front",
    "column-clamp-back",
    "clamp-screw",
    "platen",
    "platen-rack",
    "platen-guide",
    "guide-lock",
    "platen-clip",
    "platen-paper",
    "fillister-screw",
    "guide-lock-screw",  # R9-31: the eight lock screws leave MHA-030
    "chain-inner-link",
    "chain-outer-link",
    "transgear-removable",
}
CONTRACT_TRANSGEAR_QUANTITIES = {
    "transgear-arm": 1,
    "transgear-arm-plate": 1,
    "transgear-arm-plate-screw": 2,
    "transgear-pivot-spacer": 1,
    "transgear-pivot-screw": 1,
    "transgear-latch-pin": 1,
    "latch-hook-bracket": 1,
    "latch-hook-bracket-screw": 2,
    "latch-hook": 1,
    "latch-hook-rivet": 2,
    "transgear-stub": 1,
    "transgear-feed-pinion": 1,
    "transgear-disc-hub": 1,
    "transgear-hub-cap": 1,
    "rack-pinion": 1,
    "transgear-disc-screw": 3,
    "transgear-knob-shaft": 1,
    "transgear-drive-collar": 1,
    "transgear-collar-cross-pin": 1,
    "transgear-knob-drive-pin": 2,
    "transgear-removable": 3,
    "transgear-thumbnut": 1,
    "transgear-knob-thrust-ring": 1,
    "transgear-knob-cup": 1,
    "transgear-knob-retaining-screw": 1,
}
RETIRED_FAMILIES = {
    "transgear-latch",
    "transgear-pinion",
    "transgear-bracket",
    "bracket-screw",
}


def _step_body(key: str) -> str:
    """The printed text of one step, from its head to the next head."""
    text = drawing.FITUP_STEPS
    heads = list(STEP_HEAD.finditer(text))
    index = steps.step_number(key) - 1
    end = heads[index + 1].start() if index + 1 < len(heads) else len(text)
    return " ".join(text[heads[index].end() : end].split())


def _number(stem: str) -> str:
    return _config.parts(stem)["number"]


def _literal_number(script: str, key: str) -> str:
    """The drawing number a build script stamps into its Number property."""
    path = Path(drawing.__file__).with_name(script)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    values = {
        node.values[index].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Dict)
        for index, item in enumerate(node.keys)
        if isinstance(item, ast.Constant) and item.value == key
    }
    (value,) = values
    return value


def test_paper_drive_keeps_registry_outputs_and_names_its_sheets() -> None:
    spec = DRAWINGS_BY_NAME["paper_drive_assembly"]
    assert spec.source_kind == "assembly"
    assert spec.part == "paper_drive"
    assert drawing.SOURCE == spec.source
    assert drawing.OUTPUTS == drawing.OUTPUTS.__class__(
        spec.outputs["slddrw"], spec.outputs["pdf"], spec.outputs["png"]
    )
    assert set(drawing.SHEET_SCALES) == set(drawing.SHEET_NAMES)
    assert set(drawing.SHEET_LAYOUTS) == set(drawing.SHEET_NAMES)
    assert len(set(drawing.SHEET_NAMES)) == len(drawing.SHEET_NAMES)


def test_the_step_registry_names_this_sheet() -> None:
    assert steps.DRAWING_NUMBER == _literal_number(
        "build_paper_drive_assembly.py", "Number"
    )
    assert steps.step_ref(steps.SEQUENCE[3]) == f"{steps.DRAWING_NUMBER} STEP 4"
    with pytest.raises(KeyError):
        steps.step_number("no-such-step")


def test_the_printed_step_heads_are_the_registry_in_order() -> None:
    printed = [int(n) for n in STEP_HEAD.findall(drawing.FITUP_STEPS)]
    assert printed == list(range(1, len(steps.SEQUENCE) + 1))
    # The chain fit-up opens the second column.
    second = [int(n) for n in STEP_HEAD.findall(drawing.FITUP_COLUMNS[1])]
    assert second[0] == steps.step_number(drawing.FITUP_SECOND_COLUMN_KEY)


def test_the_crank_side_pointers_land_on_the_crank_fitup_steps() -> None:
    """§13.2 (1): the chain fit-up starts from the crank side's own fit-up."""
    pointers = STEP_POINTER.findall(drawing.FITUP_COLUMNS[1])
    assert pointers == [
        (drive_train_steps.DRAWING_NUMBER, str(drive_train_steps.step_number(key)))
        for key in ("crank-mesh-checked", "paper-drive-wheel")
    ]
    fitup_ref = STEP_HEAD.findall(drawing.FITUP_COLUMNS[1])[0]
    assert f"STEP {fitup_ref}" in _step_body("fitup-accepted")


def test_the_steps_fit_their_fields() -> None:
    template = DRAWING_TEMPLATES[drawing.SPEC.layout]
    for text, (left, top), (right_limit, bottom_limit) in zip(
        drawing.FITUP_NOTES,
        drawing.FITUP_NOTE_XY,
        drawing.FITUP_NOTE_LIMITS,
        strict=True,
    ):
        lines = text.splitlines()
        assert left + max(map(len, lines)) * NOTE_CHAR_WIDTH < right_limit
        assert top - len(lines) * NOTE_LINE_PITCH > bottom_limit
    (first_left, _), (second_left, _), (collar_left, collar_top) = drawing.FITUP_NOTE_XY
    first_limit, second_limit, collar_limit = drawing.FITUP_NOTE_LIMITS
    assert first_limit[0] < min(second_left, collar_left)
    # The collar note sits below the chain fit-up and above the title block.
    assert second_limit[1] > collar_top
    assert collar_limit[1] > template.title_block_top_m
    assert first_left > 0.0 and max(second_limit[0], collar_limit[0]) < template.width_m


def test_the_bom_fits_left_of_the_title_block_and_on_the_sheet() -> None:
    template = DRAWING_TEMPLATES[drawing.SPEC.layout]
    left, top = drawing.BOM_ANCHOR
    width = sum(drawing.BOM_COLUMN_WIDTHS.values())
    # A description past the measured one-line length wraps to a second line.
    wrapped = sum(
        len(text) > drawing.BOM_DESCRIPTION_MAX_CHARS
        for text in drawing.BOM_DESCRIPTIONS.values()
    )
    assert wrapped <= len(drawing.GROUPED_DESCRIPTION_STEMS)
    height = (len(drawing.BOM_PART_NUMBERS) + 1 + wrapped) * drawing.BOM_ROW_HEIGHT
    assert left + width < template.title_block_left_m
    assert top - height > 0.003
    assert top < template.height_m - 0.003


def test_bom_rows_are_exactly_the_round10_families() -> None:
    families = set(drawing.BOM_PART_NUMBERS)
    assert families == UNCHANGED_FAMILIES | set(CONTRACT_TRANSGEAR_QUANTITIES)
    assert not families & RETIRED_FAMILIES
    assert drawing.TRANSGEAR_QUANTITIES == CONTRACT_TRANSGEAR_QUANTITIES


def test_bom_numbers_and_purchased_skus_come_from_the_registry() -> None:
    for stem, number in drawing.BOM_PART_NUMBERS.items():
        assert number == _number(stem), stem
    for stem, description in drawing.BOM_DESCRIPTIONS.items():
        skus = _config.parts(stem).get("supplier_skus") or ()
        if skus:
            assert description.endswith(f"MCMASTER {skus[0]}"), stem
        else:
            assert "MCMASTER" not in description, stem
    # A number never repeats, so the alias map is total.
    assert len(drawing.BOM_NORMALIZED_ALIASES) == len(drawing.BOM_PART_NUMBERS)


def test_sheet_two_shows_and_balloons_exactly_the_transgear() -> None:
    expected = {
        f"{stem}-{index}"
        for stem, count in CONTRACT_TRANSGEAR_QUANTITIES.items()
        for index in range(1, count + 1)
        if stem != "transgear-removable"
    } | {"transgear-removable-1"}
    assert drawing.TRANSGEAR_INSTANCES == expected
    assert set(drawing.TRANSGEAR_BALLOON_ANCHORS) == set(CONTRACT_TRANSGEAR_QUANTITIES)
    # The knob's T24 is instance 1; the crank T12 and the spare T18 stay off.
    assert drawing.TRANSGEAR_BALLOON_ANCHORS["transgear-removable"].instance == (
        "transgear-removable-1"
    )


# The transgear families the sheet-2 isometric draws no reachable ink of (farm
# run 20261001T051043622Z failed on the sleeve): they balloon on the inner view.
HIDDEN_BY_THE_ISOMETRIC = {
    "transgear-feed-pinion",
    "transgear-knob-shaft",
    "transgear-drive-collar",
    "transgear-collar-cross-pin",
    "transgear-knob-drive-pin",
    "transgear-knob-retaining-screw",
    "transgear-arm-plate-screw",
    "transgear-latch-pin",
}


def test_each_transgear_family_balloons_once_on_the_view_that_shows_it() -> None:
    # Item numbers against the dict order, so the order must come from them.
    items = {
        stem: str(len(drawing.BOM_PART_NUMBERS) - index)
        for index, stem in enumerate(drawing.BOM_PART_NUMBERS)
    }
    iso, inner = drawing.transgear_balloon_items(items)
    iso_stems = {stem for stem, _item in iso}
    inner_stems = {stem for stem, _item in inner}
    assert inner_stems == HIDDEN_BY_THE_ISOMETRIC
    assert iso_stems == set(CONTRACT_TRANSGEAR_QUANTITIES) - HIDDEN_BY_THE_ISOMETRIC
    for balloons in (iso, inner):
        assert all(items[stem] == item for stem, item in balloons)
        numbers = [int(item) for _stem, item in balloons]
        assert numbers == sorted(numbers)
    # The inner view shows every instance of its families and nothing else,
    # so no outer part covers them there.
    assert drawing.INNER_INSTANCES == {
        f"{stem}-{index}"
        for stem in inner_stems
        for index in range(1, CONTRACT_TRANSGEAR_QUANTITIES[stem] + 1)
    }
    assert drawing.INNER_INSTANCES <= drawing.TRANSGEAR_INSTANCES


# Native run 20261001T062924323Z (024e240b3) read sheet 2's outlines in x: the
# isolated transgear at 2:3 centred at x 355 mm spans 295.3 to 404.8, the
# inner *Right view at 2:3 placed at x 240 spans 201.0 to 258.3. Their y
# extents are estimates from the builder's stations (the run reported no y).
ISO_OUTLINE_AT_355 = (0.2953, 0.1438, 0.4048, 0.2319)
INNER_OUTLINE_AT_2_3 = (0.2010, 0.1622, 0.2583, 0.2179)


def _iso_outline(center_x: float) -> tuple[float, float, float, float]:
    dx = center_x - 0.355
    x0, y0, x1, y1 = ISO_OUTLINE_AT_355
    return (x0 + dx, y0, x1 + dx, y1)


def _scaled(
    outline: tuple[float, float, float, float], scale: tuple[float, float]
) -> tuple[float, float, float, float]:
    """``outline`` (read at 2:3) at ``scale``, about its centre."""
    k = (scale[0] / scale[1]) / (2.0 / 3.0)
    x0, y0, x1, y1 = outline
    cx, cy, hw, hh = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2 * k, (y1 - y0) / 2 * k
    return (cx - hw, cy - hh, cx + hw, cy + hh)


def test_the_024e240b3_layout_is_refused_naming_each_overflow() -> None:
    """The native failure: both views at 2:3, the isometric centred at 355."""
    with pytest.raises(ValueError) as refused:
        drawing.inner_view_shift(_iso_outline(0.355), INNER_OUTLINE_AT_2_3)
    message = str(refused.value)
    assert "isometric ring right 421.8 mm past 415.0 mm" in message
    assert "inner view ring left 184.0 mm past 185.0 mm" in message
    assert (
        "inner view ring right 275.3 mm within 4 mm of the isometric ring (278.3 mm)"
        in message
    )
    with pytest.raises(ValueError, match="no inner-view scale fits.*1:2.*1:3"):
        drawing.inner_view_scale(_iso_outline(0.355), INNER_OUTLINE_AT_2_3, (2.0, 3.0))


def test_both_rings_fit_between_the_bom_and_the_sheet_edge_with_margin() -> None:
    iso = _iso_outline(drawing.TRANSGEAR_VIEW_CENTER[0])
    scale = drawing.inner_view_scale(iso, INNER_OUTLINE_AT_2_3, (2.0, 3.0))
    assert scale == (1.0, 2.0)
    inner = _scaled(INNER_OUTLINE_AT_2_3, scale)
    dx, dy = drawing.inner_view_shift(iso, inner)
    reach = drawing.BALLOON_RING_REACH
    iso_left, iso_right = iso[0] - reach, iso[2] + reach
    left, right = inner[0] + dx - reach, inner[2] + dx + reach
    assert drawing.BOM_RIGHT == pytest.approx(0.182)
    assert iso_right <= 0.415 - 0.002
    assert left >= drawing.BOM_RIGHT + 0.003 + 0.0015
    assert right <= iso_left - drawing.SHEET_TWO_RING_GAP - 0.0015
    # Level with the isometric.
    assert (inner[1] + inner[3]) / 2.0 + dy == pytest.approx((iso[1] + iso[3]) / 2.0)
    # Its caption stands under the ring, over the title block, left of the
    # isometric's ring.
    template = DRAWING_TEMPLATES[drawing.SPEC.layout]
    caption_top = inner[1] + dy - reach - drawing.INNER_CAPTION_GAP
    assert caption_top - NOTE_LINE_PITCH > template.title_block_top_m
    assert left + len(drawing.INNER_CAPTIONS[scale]) * NOTE_CHAR_WIDTH < iso_left


def test_an_inner_view_wider_than_measured_steps_down_to_1_3() -> None:
    """Ten per cent wider at 2:3 overflows at 1:2; 1:3 then fits."""
    x0, y0, x1, y1 = INNER_OUTLINE_AT_2_3
    wider = (x0 - (x1 - x0) * 0.05, y0, x1 + (x1 - x0) * 0.05, y1)
    iso = _iso_outline(drawing.TRANSGEAR_VIEW_CENTER[0])
    with pytest.raises(ValueError, match="inner view ring"):
        drawing.inner_view_shift(iso, _scaled(wider, (1.0, 2.0)))
    assert drawing.inner_view_scale(iso, wider, (2.0, 3.0)) == (1.0, 3.0)


def test_no_sheet_prints_a_forbidden_word() -> None:
    texts = (*drawing.SHEET_TEXTS, *drawing.BOM_DESCRIPTIONS.values())
    for text in texts:
        for word in FORBIDDEN_SHEET_WORDS:
            assert word not in text.upper(), (word, text)


def test_no_retired_part_is_named_on_the_sheet() -> None:
    retired = {"MHA-079", "MHA-080", "MHA-108", "MHA-109"}
    printed = set(re.findall(r"MHA-\d{3}", drawing.FITUP_STEPS))
    assert not printed & retired
    assert printed <= set(drawing.BOM_PART_NUMBERS.values())


def test_the_knob_stack_prints_front_to_rear() -> None:
    """Contract §1: thumbnut | T24 | collar | 12T | ring | plate hub | plate |
    rear boss | cup | screw."""
    body = _step_body("knob-stack-fitted")
    order = [
        "transgear-thumbnut",
        "transgear-removable",
        "transgear-drive-collar",
        "transgear-knob-shaft",
        "transgear-knob-thrust-ring",
        "transgear-arm-plate",
        "transgear-knob-cup",
        "transgear-knob-retaining-screw",
    ]
    assert [stem for stem, _label in drawing.KNOB_STACK if stem] == order
    positions = [body.index(_number(stem)) for stem in order]
    assert positions == sorted(positions)
    assert body.index("PLATE HUB") < body.index(_number("transgear-arm-plate"))
    assert body.index("REAR BOSS") < body.index(_number("transgear-knob-cup"))


def test_the_pivot_screw_is_threadlocked_and_the_spacer_fitted_as_made() -> None:
    """R9-7 adds threadlocker to MHA-168; R9-6 never faces MHA-167."""
    body = _step_body("hanger-pivoted")
    assert "LOW-STRENGTH THREADLOCKER" in body
    assert _number("transgear-pivot-screw") in body
    assert _number("transgear-pivot-spacer") in body
    assert "AS MADE" in body
    # No step shortens the spacer.
    assert not re.search(r"\bFACE (IT|THE SPACER|TO)\b", drawing.FITUP_STEPS)


def test_the_fitup_acceptance_prints_the_contract_bands() -> None:
    """§13.2 (8): offset 0.05 ±0.10, knob float 0.05..0.35, head play
    0.10..0.35, collar-disc air 0.10 min."""
    assert drawing.KNOB_END_FLOAT_RANGE == pytest.approx((0.05, 0.35), abs=1e-9)
    body = _step_body("fitup-accepted")
    for text in ("0.05 \u00b10.10 FORWARD", "0.05 TO 0.35", "0.10 TO 0.35", "0.10 MIN"):
        assert text in body, text


def test_the_collar_gap_stop_is_the_seat_limit_less_the_collar() -> None:
    """§13.2 (4): g past the collar's seat limit from the 12T front face less
    its length L stops the fit-up."""
    assert drawing.COLLAR_GAP_MAX == pytest.approx(
        collar.SEAT_MAX_FROM_F - collar.LENGTH, abs=1e-9
    )
    body = _step_body("collar-gap-measured")
    assert f"{drawing.COLLAR_GAP_MAX:.2f}" in body
    assert f"g = d + {collar.FIT_UP_OFFSET_TARGET:.2f}" in body


def test_the_fitup_steps_and_the_collar_note_print_one_setting_drill_and_cut() -> None:
    """R9-30: steps 14-16 and the MHA-177 fit-up note (which this sheet also
    prints) state the collar setting, the core drill and the stud cut in the
    same words, so the two instructions cannot drift apart."""
    note = " ".join(collar.FIT_UP_NOTE.split())
    for key, phrase in (
        ("collar-gap-measured", collar.FIT_UP_OFFSET_SET_TEXT),
        ("collar-pinned", collar.CROSS_PIN_DRILL_PHRASE),
        ("stud-end-cut", collar.STUD_CUT_PHRASE),
    ):
        assert phrase in _step_body(key), key
        assert phrase in note, key
    # The drill phrase carries the cross pin's functional hole band (R9-11).
    assert "\u00d81.6 +0.05/0 THROUGH THE CORE" in collar.CROSS_PIN_DRILL_PHRASE
    assert "0.3 TO 1.0 BELOW THE RIM" in collar.STUD_CUT_PHRASE


def test_the_collar_is_pinned_before_the_stud_is_cut_and_the_stack_accepted() -> None:
    order = [
        "hook-set-and-riveted",
        "fitup-pose-set",
        "collar-gap-measured",
        "collar-pinned",
        "stud-end-cut",
        "fitup-accepted",
    ]
    numbers = [steps.step_number(key) for key in order]
    assert numbers == sorted(numbers)
    assert steps.SEQUENCE[-1] == "fitup-accepted"
    # The drive pins are in the collar before the stack is built.
    assert steps.step_number("collar-pins-pressed") < steps.step_number(
        "knob-stack-fitted"
    )


def test_the_cluster_float_and_pin_bands_print_their_spec_ranges() -> None:
    assert "0.20 TO 0.40" in _step_body("disc-cluster-hung")
    assert "2.30 TO 2.50 PROUD" in _step_body("collar-pins-pressed")
    assert "12.49 TO 13.51 PROUD" in _step_body("latch-pin-pressed")


def _spare_world_point(monkeypatch, local):
    """Exercise the production row-vector transform without a COM connection."""
    transform = [value for row in assembly.ROT_X_NEG90 for value in row]
    transform += [value / 1000.0 for value in assembly.SPARE_GEAR_POS]
    transform += [1.0, 0.0, 0.0, 0.0]
    adapter = object()

    def component_transform(actual_adapter, name):
        assert actual_adapter is adapter
        assert name == "transgear-removable-3"
        return transform

    monkeypatch.setattr(_assembly, "component_transform", component_transform)
    return _assembly.world_point(adapter, "transgear-removable-3", local)


def test_spare_sprocket_transformed_underside_contacts_base_deck(monkeypatch):
    # The spec's plate is local Z=0..PLATE, identical in all tooth configs.
    underside = _spare_world_point(monkeypatch, [0.0, 0.0, 0.0])
    top = _spare_world_point(monkeypatch, [0.0, 0.0, sprocket.PLATE])
    assert underside[1] == pytest.approx(base.STACK_HEIGHT, rel=0, abs=1e-9)
    assert top[1] == pytest.approx(base.STACK_HEIGHT + sprocket.PLATE, rel=0, abs=1e-9)
    assert (underside[0], underside[2]) == (160.0, -75.0)
    assert (top[0], top[2]) == (160.0, -75.0)


def test_spare_t18_footprint_is_on_flat_deck_not_raised_rim(monkeypatch):
    radius = sprocket.outside_dia(sprocket.TEETH["T18"]) / 2.0
    for x, y, z in product((-radius, radius), (-radius, radius), (0.0, sprocket.PLATE)):
        world = _spare_world_point(monkeypatch, [x, y, z])
        assert abs(world[0]) < base.TOP_LENGTH / 2.0 - base.LIP_W
        assert abs(world[2]) < base.TOP_WIDTH / 2.0 - base.LIP_W


def test_spare_storage_clears_nameplate_envelope_by_five_mm(monkeypatch):
    # Native top gate rejected the first deck-seating candidate: retaining
    # X=160/Z=-15 intersected the brass nameplate by 605.55 mm^3.
    radius = sprocket.outside_dia(sprocket.TEETH["T18"]) / 2.0
    plate_corners = [
        nameplate.mount_point(point)
        for point in product(
            (0.0, nameplate.PLATE_WIDTH),
            (0.0, nameplate.PLATE_HEIGHT),
            (-nameplate.PLATE_THICKNESS, 0.0),
        )
    ]
    spare_max_z = max(
        _spare_world_point(monkeypatch, [x, y, z])[2]
        for x, y, z in product(
            (-radius, radius), (-radius, radius), (0.0, sprocket.PLATE)
        )
    )
    assert spare_max_z <= min(point[2] for point in plate_corners) - 5.0


def test_spare_remains_fixed_t18_sibling_with_original_rotation():
    tree = ast.parse(Path(assembly.__file__).read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "place_component"
        and any(
            keyword.arg == "label"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value == "transgear-removable (spare T18)"
            for keyword in node.keywords
        )
    ]
    assert len(calls) == 1
    call = calls[0]
    assert [ast.unparse(arg) for arg in call.args] == [
        "adapter",
        "'transgear-removable'",
        "list(SPARE_GEAR_POS)",
        "[-90.0, 0.0, 0.0]",
        "ROT_X_NEG90",
    ]
    assert {
        keyword.arg: ast.literal_eval(keyword.value) for keyword in call.keywords
    } == {
        "configuration": "T18",
        "label": "transgear-removable (spare T18)",
    }
    assert (
        inspect.signature(_assembly.place_component).parameters["ground"].default
        is True
    )
    assert assembly.ROT_X_NEG90 == [[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]]
