"""Offline contracts for the paper-drive assembly and its drawing (MHA-PD-00)."""

import itertools
from itertools import product
import math
import re
from types import SimpleNamespace
from unittest.mock import MagicMock, PropertyMock

import pytest

from _column_clamp_interface import BAR_DEPTH
import _assembly
from _assembly_contract import assembly_contract
import _chain as chain
import _com
import _config
import _component_references
import _drawing_balloons
import _drawing_tables
from _layout_geometry import LeaderSegment, find_leader_leader_crossings
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DRAWING_TEMPLATES
import build_pd_paper_drive_assembly as assembly
import draw_pd_paper_drive_assembly as drawing
import dt_drive_train_steps
import fr_harmonic_base_spec as base
import fr_nameplate_spec as nameplate
import paper_drive_geom as paper_geometry
import paper_drive_rack_setup as rack_setup
import pd_paper_drive_assembly_steps as steps
import pd_paper_drive_knob_setting_spec as knob_setting
import pd_transgear_arm_geometry as steps_arm
import _paper_drive_placement as placement
import pd_paper_drive_explode_spec as explode
import pd_feed_rack_spec as feed_rack
import pd_rack_pinion_spec as disc
import pd_transgear_drive_collar_spec as collar
import pd_transgear_feed_pinion_spec as feed_pinion
import pd_transgear_knob_bush_geometry as knob_bush
import pd_transgear_knob_shaft_spec as knob_shaft
import pd_transgear_pin_spec as cluster_pin
import pd_vn_transgear_arm_plate_locating_pin_spec as plate_locating_pin
import _transgear_arm_plate_locating_interface as plate_locating_interface
import pd_vn_transgear_knob_drive_pin_spec as drive_pin
import pd_transgear_removable_spec as sprocket
import _sprocket_seat_geometry as seat_geometry
import transgear_cluster_fit as cluster_fit
import transgear_hanger_joints as joints
import pd_vn_transgear_pivot_screw_spec as pivot_screw

STEP_HEAD = re.compile(r"^(\d+)([A-Z]?)\. ", re.MULTILINE)
# Default-format note text, measured on r743-rocker-fix3's render (leaf
# 20260926T112244Z-1-a884759d), as test_channel_assembly_drawing uses them;
# #945 moves these into _drawing_common.
NOTE_CHAR_WIDTH = 0.00276
NOTE_LINE_PITCH = 0.0045
# Dimension text runs larger: DETAIL K's "ALONG ARM" callout spanned 27.9 mm and
# its two rows 9.2 mm on run 20261028T000650671Z's sheet 5.
DIM_CHAR_WIDTH = 0.0031
DIM_LINE_PITCH = 0.0047
# The BOM table's rows: one per BOM entry under one header row.
BOM_ROWS = len(drawing.BOM_PART_NUMBERS) + 1


def _segment_distance(
    point: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / (dx * dx + dy * dy)
    t = min(1.0, max(0.0, t))
    return math.dist(point, (a[0] + t * dx, a[1] + t * dy))


# Words no sheet of the package may print (drawing-simplicity policy).
FORBIDDEN_SHEET_WORDS = ("EXCEPTION", "ACCEPTED", "RULING", "POLICY", "BOOK FIDELITY")

# CONTRACT-paper-drive.md, the round-10 component set.
UNCHANGED_FAMILIES = {
    "pd-support-bar",
    "sh-column-clamp-front",
    "sh-column-clamp-back",
    "sh-vn-clamp-screw",
    "pd-platen",
    "pd-feed-rack",  # #2410: the bare purchased strip replaces MHA-PD-05
    "pd-platen-bottom-guide",  # #2410: MHA-PD-27, the rack screwed under it
    "pd-platen-guide",
    "sh-vn-fillister-screw-91794a055--RackScrew",
    "pd-guide-lock",
    "pd-platen-clip",
    "pd-platen-paper",
    "sh-vn-brass-fillister-screw",
    "pd-vn-platen-clip-screw",  # the four #2-56 clip screws leave MHA-PD-VN-52
    "pd-vn-guide-lock-screw",  # R9-31: the eight lock screws leave MHA-PD-VN-52
    "sh-vn-chain-link--InnerLink",
    "sh-vn-chain-link--OuterLink",
    "pd-vn-chain-connecting-link",  # MHA-PD-VN-66 closes the loop as its last outer link
    "pd-transgear-removable",
}
CONTRACT_TRANSGEAR_QUANTITIES = {
    "pd-transgear-arm": 1,
    "pd-transgear-arm-plate": 1,
    "pd-vn-transgear-arm-plate-screw": 2,
    "pd-vn-transgear-arm-plate-locating-pin": plate_locating_pin.ASSEMBLY_QUANTITY,
    "pd-transgear-pivot-spacer": 1,
    "pd-vn-transgear-pivot-screw": 1,
    "pd-vn-transgear-pivot-spring": 1,
    "pd-vn-transgear-latch-pin": 1,
    "sh-vn-fillister-screw-90280a108": 2,
    "pd-latch-hook": 1,
    "pd-transgear-pin": 1,
    "pd-transgear-rear-bushing": 1,
    "pd-transgear-feed-pinion": 1,
    "pd-transgear-disc-hub": 1,
    "pd-vn-transgear-hub-key-pin": 1,
    "pd-transgear-front-bushing": 1,
    "pd-vn-transgear-retaining-ring": 1,
    "pd-vn-transgear-cluster-shim": cluster_fit.SHIM_COUNT_MAX,
    "pd-rack-pinion": 1,
    "sh-vn-fillister-screw-91794a055--DiscScrew": 3,
    "pd-transgear-knob-shaft": 1,
    "pd-transgear-drive-collar": 1,
    "pd-vn-transgear-knob-drive-pin": 2,
    "pd-vn-transgear-collar-flat-pin": 1,
    "pd-transgear-removable": 3,
    "pd-transgear-thumbnut": 1,
    "pd-transgear-knob-thrust-ring": 1,
    "pd-transgear-knob-bush": 1,
    "pd-transgear-knob-cup": 1,
    "pd-vn-transgear-knob-cup-screw": 1,
}
# The shared #0-80 fillister's native names: the builder places the four
# RackScrews first, then the three DiscScrews (it proves each name).
RACK_SCREW_INSTANCES = tuple(f"sh-vn-fillister-screw-91794a055-{i}" for i in (1, 2, 3, 4))
DISC_SCREW_INSTANCES = tuple(f"sh-vn-fillister-screw-91794a055-{i}" for i in (5, 6, 7))
RETIRED_FAMILIES = {
    "transgear-latch",
    "transgear-pinion",
    "transgear-bracket",
    "bracket-screw",
    "pd-latch-hook-bracket",
    "vn-latch-hook-rivet",
    "vn-transgear-collar-cross-pin",
}


def _unit_operating_domain() -> drawing.RackOperatingDomain:
    """The real engaged-feed window: closed-form, cheap and source-derived."""
    return rack_setup.feed_rack_operating_domain()


def _unit_step_notes() -> drawing.StepNotes:
    return drawing.format_step_notes(operating_domain=_unit_operating_domain())


def _step_body(key: str) -> str:
    """The printed text of one step, its sub-steps joined, heads dropped."""
    texts = drawing._step_text(operating_domain=_unit_operating_domain())[key]
    return " ".join(" ".join(texts).split())


def _number(stem: str) -> str:
    return _config.parts(drawing.BOM_COMPONENT_IDENTITIES.get(stem, (stem, None))[0])["number"]


def test_paper_drive_keeps_registry_outputs_and_names_its_sheets() -> None:
    spec = DRAWINGS_BY_NAME["pd_paper_drive_assembly"]
    assert spec.source_kind == "assembly"
    assert spec.part == "pd_paper_drive"
    assert drawing.SOURCE == spec.source
    assert drawing.OUTPUTS == drawing.OUTPUTS.__class__(
        spec.outputs["slddrw"], spec.outputs["pdf"], spec.outputs["png"]
    )
    assert set(drawing.SHEET_SCALES) == set(drawing.SHEET_NAMES)
    assert set(drawing.SHEET_LAYOUTS) == set(drawing.SHEET_NAMES)
    assert len(set(drawing.SHEET_NAMES)) == len(drawing.SHEET_NAMES)


def test_an_unknown_step_is_refused() -> None:
    with pytest.raises(KeyError):
        steps.step_number("no-such-step")


def test_every_steps_sheet_keeps_most_lines_matchable_by_the_layout_audit() -> None:
    """The layout audit fails a sheet when under MIN_MATCH_SHARE of its COM
    strings find their printed text, and an indented continuation line never
    finds its own (run 20261111T054024870Z: sheet 10 at 34 of 69). Each
    steps sheet's head lines, plus its reference caption, must stay the
    larger share."""
    import _layout_audit

    lines: dict[str, list[str]] = {}
    for column in drawing.pack_step_columns(
        drawing._step_text(operating_domain=_unit_operating_domain())
    ):
        lines.setdefault(column.sheet, []).extend(
            line for line in column.text.splitlines() if line.strip()
        )
    for sheet, printed in lines.items():
        continued = sum(line.startswith(" ") for line in printed)
        matchable = len(printed) + (sheet != drawing.SHEET_NAMES[3])
        assert matchable - continued >= _layout_audit.MIN_MATCH_SHARE * matchable, sheet


def test_the_printed_step_heads_are_the_registry_in_order() -> None:
    notes = _unit_step_notes()
    heads = STEP_HEAD.findall(notes.fitup_steps)
    numbers = list(dict.fromkeys(int(number) for number, _letter in heads))
    assert numbers == list(range(1, len(steps.SEQUENCE) + 1))
    for number in numbers:
        letters = [letter for n, letter in heads if int(n) == number]
        assert letters == [""] or letters == list(
            drawing.SUB_STEP_LETTERS[: len(letters)]
        )


def test_one_blank_line_separates_consecutive_steps_and_none_splits_a_sub_step() -> None:
    notes = _unit_step_notes()
    for column in notes.columns:
        lines = column.text.splitlines()
        heads = [
            (index, int(match[1]))
            for index, line in enumerate(lines)
            if (match := STEP_HEAD.match(line))
        ]
        assert lines[heads[0][0] - 1] != ""  # the heading runs straight into the first step
        for (previous, number), (head, next_number) in zip(heads, heads[1:]):
            blanks = lines[previous:head].count("")
            assert blanks == (0 if next_number == number else 1)


def test_the_crank_side_pointer_names_the_sheet_that_prints_those_steps() -> None:
    """§13.2 (1): the chain fit-up starts from the crank side's own fit-up,
    and the pointer names the MHA-DT-00 sheet whose note prints both steps."""
    import draw_dt_drive_train_assembly as drive_train
    notes = _unit_step_notes()

    text = notes.fitup_steps.replace("\n", " ")
    pointers = re.findall(r"(MHA-[A-Z]{2}-00)\b SHEET (\d+), STEPS (\d+) AND (\d+)", text)
    wanted = [str(dt_drive_train_steps.step_number(key)) for key in steps.CRANK_SIDE_KEYS]
    assert pointers == [
        (assembly_contract("dt-drive-train").number, str(drive_train.CRANK_SHEET), *wanted)
    ]
    assert steps.CRANK_SIDE_KEYS == ("crank-mesh-checked", "paper-drive-wheel")
    # The cone-and-crank steps are the note package_note_fields stacks from
    # SEQUENCE_SHEET; steps 4 and 5 print on CRANK_SHEET.
    printed = {number for number, _letter in STEP_HEAD.findall(drive_train.CONE_CRANK_STEPS)}
    assert set(wanted) <= printed
    fitup_ref = steps.step_number(drawing.FITUP_CHAIN_KEY)
    pose_ref = steps.step_number("fitup-pose-set")
    assert f"STEP {pose_ref}" in _step_body("fitup-accepted")
    heading = notes.fitup_steps.index("CHAIN FIT-UP, STEPS")
    assert notes.fitup_steps.index(f"\n{fitup_ref}A. ") > heading


def test_the_steps_fit_their_fields() -> None:
    notes = _unit_step_notes()
    template = DRAWING_TEMPLATES[drawing.SPEC.layout]
    assert len(notes.columns) == len(drawing.STEP_SLOTS)
    right_limits = {
        drawing.PLATEN_NOTE_XY: drawing.PLATEN_NOTE_RIGHT,
        drawing.FITUP_NOTE_XY[0]: drawing.FITUP_NOTE_LIMITS[0][0],
        drawing.FITUP_NOTE_XY[1]: drawing.FITUP_NOTE_LIMITS[1][0],
    }
    fields = (
        *(
            (column.text, column.xy, (right_limits[column.xy], slot.bottom))
            for column, slot in zip(notes.columns, drawing.STEP_SLOTS, strict=True)
        ),
        *(
            (
                text,
                drawing.ASSEMBLED_CAPTION_XY,
                (
                    drawing.ISO_RING_LIMITS[0] - 0.003,
                    drawing.SHEET_INNER_BORDER_BOTTOM,
                ),
            )
            for text in drawing.ASSEMBLED_CAPTIONS.values()
        ),
    )
    for text, (left, top), (right_limit, bottom_limit) in fields:
        lines = text.splitlines()
        assert left + max(map(len, lines)) * NOTE_CHAR_WIDTH < right_limit
        assert top - len(lines) * NOTE_LINE_PITCH > bottom_limit
    for column, slot in zip(notes.columns, drawing.STEP_SLOTS, strict=True):
        assert (column.sheet, column.xy) == (slot.sheet, slot.xy)
        assert slot.bottom >= template.title_block_top_m
    (first_left, _), (second_left, _) = drawing.FITUP_NOTE_XY
    first_limit, second_limit = drawing.FITUP_NOTE_LIMITS
    assert first_limit[0] < second_left
    assert second_limit[1] > template.title_block_top_m
    assert first_left > 0.0 and second_limit[0] < template.width_m
    # Sheet 4's caption sits under its steps.
    assert notes.exploded_caption_xy[1] < drawing.PLATEN_NOTE_XY[1] - (
        len(notes.platen_steps.splitlines()) * NOTE_LINE_PITCH
    )
    assert notes.exploded_caption_xy[1] - NOTE_LINE_PITCH > template.title_block_top_m
    # DETAIL K and DETAIL E stand under the columns that share their sheets.
    assert drawing.KNOB_SETTING_CENTER[1] + drawing.KNOB_SETTING_RADIUS < (
        drawing.KNOB_SETTING_FIELD_TOP
    )
    assert drawing.CLUSTER_FLOAT_CENTER[1] + drawing.CLUSTER_FLOAT_RADIUS < (
        drawing.CLUSTER_FLOAT_FIELD_TOP
    )


def test_no_sub_step_runs_past_six_lines() -> None:
    notes = _unit_step_notes()
    for column in notes.columns:
        lines = column.text.splitlines()
        heads = [i for i, line in enumerate(lines) if STEP_HEAD.match(line)]
        for head, end in zip(heads, [*heads[1:], len(lines)]):
            body = [line for line in lines[head:end] if line]
            assert len(body) <= 6, lines[head]


def test_a_bom_that_cannot_fit_all_rows_is_refused_not_truncated() -> None:
    # f353's native 437.2384 mm table cannot fit these two fields even split.
    heights = (0.0102, *(0.01016758 for _ in range(42)))
    with pytest.raises(RuntimeError, match="complete paper-drive BOM does not fit"):
        drawing.bom_split_row(heights, 1)


def test_native_bom_containment_keeps_the_reference_title_and_border_clear() -> None:
    template = DRAWING_TEMPLATES[drawing.SPEC.layout]
    width = sum(drawing.BOM_COLUMN_WIDTHS.values())
    left, top = drawing.BOM_ANCHOR
    ref_floor = drawing.BOM_REFERENCE_LIMITS[3] + drawing.BOM_BORDER_CLEARANCE
    assert drawing.bom_extent_violations((left, top), width, top - ref_floor) == []
    assert drawing.bom_extent_violations((left, top), width, top - ref_floor + 0.001)
    right, top = drawing.BOM_SECOND_ANCHOR
    title_floor = template.title_block_top_m + drawing.BOM_BORDER_CLEARANCE
    assert drawing.bom_extent_violations((right, top), width, top - title_floor) == []
    assert drawing.bom_extent_violations((right, top), width, top - title_floor + 0.001)
    border = drawing.SHEET_INNER_BORDER_BOTTOM + drawing.BOM_BORDER_CLEARANCE
    assert drawing.bom_extent_violations(
        (template.width_m - border - width + 0.001, top), width, 0.1
    )


def test_bom_rows_are_exactly_the_round10_families() -> None:
    families = set(drawing.BOM_PART_NUMBERS)
    assert families == UNCHANGED_FAMILIES | set(CONTRACT_TRANSGEAR_QUANTITIES)
    assert not families & RETIRED_FAMILIES
    assert drawing.TRANSGEAR_QUANTITIES == CONTRACT_TRANSGEAR_QUANTITIES
    assert drawing.PLATEN_QUANTITIES == {
        "sh-vn-fillister-screw-91794a055--RackScrew": len(feed_rack.TAP_X)
    }


def test_bom_numbers_and_purchased_skus_come_from_the_registry() -> None:
    for stem, number in drawing.BOM_PART_NUMBERS.items():
        assert number == _number(stem), stem
    # A shared member's BOM text is its model's own (the builder stamps it
    # on the configuration, and it wins over a written cell).
    members = {
        explode.RACK_SCREW: drawing.rack_screw.BOM_DESCRIPTION,
        explode.DISC_SCREW: drawing.disc_screw.BOM_DESCRIPTION,
    }
    for stem, description in drawing.BOM_DESCRIPTIONS.items():
        registry = _config.parts(drawing.BOM_COMPONENT_IDENTITIES[stem][0])
        skus = registry.get("supplier_skus") or ()
        if stem in members:
            assert description == members[stem], stem
        # A fabricated part from purchased stock (the SDP/SI feed rack) is
        # not itself a McMaster purchase line.
        elif skus and registry.get("supplier") == "McMaster-Carr":
            assert description.endswith(f"MCMASTER {skus[0]}"), stem
        else:
            assert "MCMASTER" not in description, stem
    # Distinct physical members deliberately share one canonical purchase Number.
    for first, second in (
        ("sh-vn-chain-link--InnerLink", "sh-vn-chain-link--OuterLink"),
        (explode.RACK_SCREW, explode.DISC_SCREW),
    ):
        assert drawing.BOM_PART_NUMBERS[first] == drawing.BOM_PART_NUMBERS[second]
        assert (
            drawing.BOM_COMPONENT_IDENTITIES[first]
            != drawing.BOM_COMPONENT_IDENTITIES[second]
        )


def test_bom_sheet_says_what_the_shared_chain_number_orders() -> None:
    """2026-10-27 ENFORCE review (r1-r3): the inner and outer link rows share
    one Number, so the BOM sheet states that Number is one supplier chain,
    the length to cut and how it splits, and what closes the loop."""
    inner, outer = "sh-vn-chain-link--InnerLink", "sh-vn-chain-link--OuterLink"
    note = drawing.BOM_CHAIN_ORDER_NOTE
    sku = _config.parts("sh-vn-chain-link")["supplier_skus"][0]
    pitches = drawing.CHAIN_QUANTITIES[inner] + drawing.CHAIN_QUANTITIES[outer]
    assert pitches + drawing.CHAIN_QUANTITIES["pd-vn-chain-connecting-link"] == (
        drawing.chain.LINK_COUNT
    )
    for text in (
        f"{drawing.BOM_PART_NUMBERS[inner]}, ITEMS {drawing.SHARED_NUMBER_ITEMS[inner]} "
        f"AND {drawing.SHARED_NUMBER_ITEMS[outer]}, IS ONE CHAIN",
        f"ORDER {drawing.CHAIN_ORDER_FEET} FT",
        f"MCMASTER {sku}",
        f"CUT {pitches} PITCHES",
        f"{drawing.CHAIN_QUANTITIES[inner]} INNER",
        f"{drawing.CHAIN_QUANTITIES[outer]} OUTER",
        drawing.BOM_PART_NUMBERS["pd-vn-chain-connecting-link"],
    ):
        assert text in note.replace("\n", " "), text
    assert f"\n{note}\n" in drawing.BOM_SHEET_CAPTION
    assert drawing.BOM_SHEET_CAPTION.startswith(drawing.BOM_REFERENCE_CAPTION)
    assert drawing.BOM_SHEET_CAPTION.endswith(drawing.BOM_EXPENDABLES_NOTE)
    # The caption hangs right of the reference view, above the border and
    # left of the title block (rows of at most 36 characters).
    rows = drawing.BOM_SHEET_CAPTION.split("\n")
    assert max(len(row) for row in rows) <= 36
    x, y = drawing.BOM_REFERENCE_CAPTION_XY
    assert x > drawing.BOM_REFERENCE_LIMITS[2]
    assert y - len(rows) * NOTE_LINE_PITCH > drawing.SHEET_INNER_BORDER_BOTTOM


def test_the_spare_sprocket_loops_close_and_the_order_covers_them() -> None:
    """Owner ruling 2026-11-20 (Pedro), #2429, option A: the spare 18-tooth
    sprocket takes its own loop, closed by its own connecting link, at the
    source centres with it on either shaft."""
    import paper_drive_chain_fit as chain_fit

    knob_centre, crank_centre = chain_fit.source_nominal_chain_centres_mm()
    for where, (knob_teeth, crank_teeth) in {
        "knob": (drawing.SPARE_TEETH, sprocket.CRANK_TEETH),
        "crank": (sprocket.KNOB_TEETH, drawing.SPARE_TEETH),
    }.items():
        fit = chain_fit.solve_chain_fit(
            knob_centre,
            crank_centre,
            knob_teeth=knob_teeth,
            crank_teeth=crank_teeth,
            link_count=drawing.SPARE_LOOP_PITCHES[where],
        )
        assert fit.sag_mm > 0.0 and fit.roller_air_mm > 0.0, where
    cut = chain.LINK_COUNT - 1 + max(drawing.SPARE_LOOP_PITCHES.values()) - 1
    feet = drawing.CHAIN_ORDER_FEET
    assert (feet - 1) * 304.8 < cut * chain.LINK_PITCH <= feet * 304.8
    note = drawing.BOM_CHAIN_ORDER_NOTE.replace("\n", " ")
    assert (
        f"CUT {drawing.SPARE_LOOP_PITCHES['knob'] - 1} PITCHES (IT ON THE KNOB) OR "
        f"{drawing.SPARE_LOOP_PITCHES['crank'] - 1} (ON THE CRANK)"
    ) in note
    expendables = drawing.BOM_EXPENDABLES_NOTE.replace("\n", " ")
    assert f"1 MORE {_number('pd-vn-chain-connecting-link')}" in expendables


def test_shared_numbers_print_the_item_the_native_bom_gives(monkeypatch) -> None:
    """#3106 (rule 22): MHA-SH-VN-59 and MHA-SH-VN-50 each number two rows,
    so the steps add the item, and the native fill refuses a different one."""
    texts = " ".join(
        " ".join(text)
        for text in drawing._step_text(
            operating_domain=_unit_operating_domain()
        ).values()
    )
    for stem in (explode.RACK_SCREW, explode.DISC_SCREW):
        assert f"{_number(stem)} (ITEM {drawing.SHARED_NUMBER_ITEMS[stem]})" in texts, (
            stem
        )
    model, _components, table, adapter, cells, keys = _pd_bom_fixture(monkeypatch)
    counts = drawing._source_family_counts(model)
    rack, disc_screw = (
        keys.index(stem) + 1 for stem in (explode.RACK_SCREW, explode.DISC_SCREW)
    )
    cells[rack][0], cells[disc_screw][0] = cells[disc_screw][0], cells[rack][0]
    with pytest.raises(RuntimeError, match="the steps print ITEM"):
        drawing._validate_bom(
            adapter, table, counts, configuration=drawing.SIMPLIFIED_VIEW_CONFIGURATION
        )


def test_a_dowel_that_slides_into_the_arm_is_bonded() -> None:
    """Owner ruling 2026-11-20 (Pedro), #2497: the arm's slipping dowel is
    bonded and read again once cured. Its re-pinning half lapsed with the
    knob cup's cross pin (#2425): a cup taken off is renewed with its screw,
    and only a faulty pinion renews the shaft."""
    texts = drawing._step_text(operating_domain=_unit_operating_domain())
    renewed = (
        f"REPEAT STEP {steps.step_number('knob-stack-fitted')} WITH A NEW "
        f"{_number('pd-transgear-knob-cup')} CUP AND "
        f"{_number('pd-vn-transgear-knob-cup-screw')} SCREW, THEN FROM STEP "
        f"{steps.step_number('fitup-pose-set')}."
    )
    for key in ("fitup-mesh-remedied", "fitup-accepted"):
        assert any(row.endswith(renewed) for row in texts[key]), key
        assert not any("90\u00b0" in row or "2 HOLES" in row for row in texts[key]), key
    assert not any("2 HOLES" in row for row in texts["knob-stack-fitted"])
    assert any(
        row.endswith(f"MAKE A NEW {_number('pd-transgear-knob-shaft')} SHAFT.")
        for row in texts["fitup-mesh-remedied"]
    )
    # The bond, its check and the check's remedy are separate sub-steps. The
    # bond's prep and where the compound goes are DETAIL H's bond note, so
    # 13G stays one action in step 13's 24 letters (machinist reviews of
    # 592b20079f and 70917f0316).
    bond, check, remedy = texts["arm-plate-fitted"][6:9]
    detail_sheet = drawing.SHEET_NAMES.index(drawing.SETTING_DETAIL_SHEET) + 1
    assert bond == (
        "IF A DOWEL SLIDES IN BY HAND, BOND IT PER THE BOND NOTE AT DETAIL H, "
        f"SHEET {detail_sheet}."
    )
    assert (
        drawing.detail_cite("arm-plate-fitted") == f"(DETAIL H, SHEET {detail_sheet})"
    )
    note = " ".join(drawing.SETTING_DETAIL_CAPTIONS["H"].split())
    # A collar dowel or pin that slides in renews the collar (step 20) and a
    # latch dowel the arm (step 10), so the note serves the plate dowels only.
    assert f"BOND NOTE ({drawing.sub_step('arm-plate-fitted', 6)}):" in note
    for words in (
        "PULL THE DOWEL.",
        "DEGREASE IT AND ITS HOLE.",
        "COAT THE DOWEL, NOT THE HOLE, WITH LOCTITE 638.",
        "PRESS IT BACK AT ONCE TO ITS STEP'S PROUD.",
        "CURE 24 H.",
    ):
        assert words in note, words
    assert all(
        len(row) <= drawing.SETTING_CAPTION_WIDTH
        for row in drawing.SETTING_DETAIL_CAPTIONS["H"].split("\n")
    )
    assert check == (
        "CHECK: A BONDED DOWEL, PUSHED, STILL READS AS "
        f"{drawing.sub_step('arm-plate-fitted', 5)}."
    )
    assert remedy.endswith(f"RENEW AS {drawing.sub_step('arm-plate-fitted', 22)}.")
    assert texts["arm-plate-fitted"][22].startswith(
        "IF A CHECK STILL FAILS, THE DOWELS HAVE NOT HELD"
    )


def test_a_feed_sleeve_found_outside_after_hanging_has_a_renewal_route() -> None:
    """#3106: 24 and 26 renew a faulty MHA-PD-10 from the stripped cluster,
    one action per sub-step (machinist review of 592b20079f)."""
    texts = drawing._step_text(operating_domain=_unit_operating_domain())
    meshed = texts["hanger-meshed"]
    sleeve = _number("pd-transgear-feed-pinion")
    route = next(
        index
        for index, text in enumerate(meshed)
        if text.startswith(f"FOR A {sleeve} FOUND OUTSIDE")
    )
    assert meshed[route : route + 4] == (
        f"FOR A {sleeve} FOUND OUTSIDE, SLIDE THE COLLAR OFF.",
        f"FOR IT, STRIP THE CLUSTER ({drawing.sub_step('disc-cluster-hung', 4)} BACK TO "
        f"{drawing.sub_step('disc-cluster-hung', 1)}), KEEPING ITS SHIMS.",
        f"FOR IT, DO THE SLIDE-OFF AND THE REPEATS IN "
        f"{drawing.sub_step('arm-plate-located', 21)} ON A NEW ONE.",
        f"FOR IT, REPEAT STEPS {steps.step_number('oil-hole-drilled')}-"
        f"{steps.step_number('disc-cluster-shimmed')} AND "
        f"{drawing.sub_step('knob-stack-fitted', 18)}, THEN FROM "
        f"{drawing.sub_step('hanger-meshed', 0)}.",
    )
    # The sub-step it names is the one that slides the sleeve off and on.
    assert texts["arm-plate-located"][21].startswith(
        f"REPLACE A {sleeve} FOUND OUTSIDE: SLIDE THE HUB AND DISC OFF IT AS ONE"
    )
    assert texts["knob-stack-fitted"][18].startswith(
        f"SLIDE THE {_number('pd-transgear-drive-collar')} COLLAR ON"
    )
    assert (
        f"OR {drawing.sub_step('hanger-meshed', route)}."
        in texts["loaded-rack-geometry-checked"][11]
    )


def test_the_engaged_feed_is_measured_from_a_named_rack_end() -> None:
    """#3106: the engaged feed names which rack end it starts from."""
    assert drawing.RACK_FEED_END_TEXT in " ".join(_step_body("hanger-meshed").split())


def test_bom_sheet_lists_what_the_steps_use_up() -> None:
    """Machinist review r3, r5 (rule 22): the four spare rack screws cut into
    transfer screws and the #4-40 transfer screws are named with their counts
    and steps on the BOM sheet."""
    note = drawing.BOM_EXPENDABLES_NOTE.replace("\n", " ")
    assert f"{drawing.RACK_SCREWS} MORE {_number(explode.RACK_SCREW)}" in note
    made = f"{drawing.sub_step('rack-screwed', 0)}-{drawing.sub_step('rack-screwed', 2)}"
    assert f"{made} MAKE THEM TRANSFER SCREWS" in note
    assert f"{drawing.sub_step('platen-hung', 0)} USES 8 #4-40 TRANSFER SCREWS" in note
    texts = drawing._step_text(operating_domain=_unit_operating_domain())
    rack = " ".join(texts["rack-screwed"][:3])
    assert f"SPARE {_number(explode.RACK_SCREW)}" in rack and "TRANSFER SCREWS" in rack
    hung = _step_body("platen-hung")
    assert "2ND, 4TH, 6TH AND 8TH OF EACH" in hung and "#4-40 TRANSFER SCREW" in hung
    # Codjiflo P2 on 19ef870: the pointed screws keep a pliers grip, are run
    # in by fingers short of bottoming, and the strip is pressed square on
    # its points (they lie on its centreline, the roll axis of any tilt).
    made_steps = texts["rack-screwed"]
    assert "BY FINGERS" in made_steps[0] and "NOT BOTTOMED" in made_steps[0]
    assert "PLIERS GRIP" in made_steps[1]
    assert f"PRESSED SQUARE ON ITS {drawing.RACK_SCREWS} POINTS" in made_steps[3]
    assert any(text == "UNSCREW THE TRANSFER SCREWS WITH PLIERS." for text in made_steps)
    assert all("PROUD" not in text or "GRIP" in text for text in made_steps)


def test_the_two_locating_dowels_are_not_the_two_knob_wheel_drive_dowels() -> None:
    locating = "pd-vn-transgear-arm-plate-locating-pin"
    driving = "pd-vn-transgear-knob-drive-pin"
    assert plate_locating_pin.ASSEMBLY_QUANTITY == 2
    assert drawing.TRANSGEAR_QUANTITIES[locating] == plate_locating_pin.ASSEMBLY_QUANTITY
    assert drawing.TRANSGEAR_QUANTITIES[driving] == len(seat_geometry.PIN_HOLE_ANGLES_DEG)
    assert _number(locating) != _number(driving)
    assert "PLATE LOCATING DOWEL" in drawing.BOM_DESCRIPTIONS[locating]
    assert "WHEEL DRIVE DOWEL" in drawing.BOM_DESCRIPTIONS[driving]
    assert locating in drawing.ISO_HIDDEN_STEMS
    assert {locating, driving} <= explode.TRANSGEAR_SHOWN_STEMS
    for stem in (locating, driving):
        assert len(drawing.BOM_DESCRIPTIONS[stem]) <= drawing.BOM_DESCRIPTION_MAX_CHARS


def test_the_critical_matched_dowels_locate_and_the_plate_screws_only_clamp() -> None:
    located = _step_body("arm-plate-located")
    fitted = _step_body("arm-plate-fitted")
    assert (
        f"PRESS {plate_locating_pin.ASSEMBLY_QUANTITY} "
        f"{_number('pd-vn-transgear-arm-plate-locating-pin')} DOWELS"
    ) in fitted
    # The setting's identities, in operation order: S (the pressed pin's
    # shank in its bore, the cluster's running axis), K set at DETAIL K's
    # model dimensions and the trial mesh; then (opening the next step, the
    # located step's letters being used up) the pilots, each part reamed to
    # its own drawing, then the dowels.
    order = [
        "PIN BORE S",
        drawing.KNOB_SETTING_VIEW_NAME,
        "TRIAL MESH",
    ]
    # The parts named in the opening clamp are skipped by searching after it.
    cursor = located.index(_number("pd-transgear-arm")) + 1
    for token in order:
        cursor = located.index(token, cursor)
    cursor = 0
    for token in (
        drawing.PLATE_DOWEL_PILOT_TEXT,
        f"REAM THE ARM'S 2 HOLES TO {_number('pd-transgear-arm')}",
        f"REAM THE PLATE'S 2 HOLES TO {_number('pd-transgear-arm-plate')}",
        _number("pd-vn-transgear-arm-plate-locating-pin"),
    ):
        cursor = fitted.index(token, cursor)
    assert fitted.startswith("MATCH-DRILL")
    # The step cites the view's model dimensions and types no value of its own.
    for value in (knob_setting.K_FROM_S_ALONG_MM, knob_setting.K_FROM_S_ACROSS_MM):
        assert disc.inch_text(value, knob_setting.PLACES) not in located
    # S is the pressed pin's shank, indicated from the front, not its head
    # (no drawing control holds the head to the shank): the pin goes in
    # before the plate is set, so the trial mesh can run the cluster on it.
    assert f"{_number('pd-transgear-pin')} PIN'S SHANK IN ITS PIN BORE S" in located
    assert "FRONT UP" in located
    assert steps.step_number("pin-pressed") < steps.step_number("arm-plate-located")
    assert steps.step_number("arm-plate-fitted") < steps.step_number("hanger-pivoted")
    # "True" is a stated null-reading acceptance, the budget's centring bound.
    assert drawing.KNOB_SETTING_TRUE in located


def test_view_k_carries_the_set_coordinates_as_assembly_model_dimensions() -> None:
    # The chain P-S-Q-K: Q along the arm's axis from S, K square to it.
    s, q, k, p = (
        knob_setting.S_XY, knob_setting.Q_XY, knob_setting.K_XY, knob_setting.P_XY,
    )
    assert math.dist(p, s) == pytest.approx(steps_arm.PIN_STATION)
    assert math.dist(s, q) == pytest.approx(knob_setting.K_FROM_S_ALONG_MM)
    assert math.dist(q, k) == pytest.approx(knob_setting.K_FROM_S_ACROSS_MM)
    sq = (q[0] - s[0], q[1] - s[1])
    qk = (k[0] - q[0], k[1] - q[1])
    ps = (s[0] - p[0], s[1] - p[1])
    assert sq[0] * qk[0] + sq[1] * qk[1] == pytest.approx(0.0, abs=1e-9)
    assert sq[0] * ps[1] - sq[1] * ps[0] == pytest.approx(0.0, abs=1e-9)
    # K is the DRO count nearest the middle of the set band, among the nine
    # counts about the mid-band point on the nominal S-K line: each
    # coordinate a whole count within a count and a half of that point.
    low, high = disc.CENTRE_DISTANCE_WINDOW
    count = knob_setting.DRO_COUNT_MM
    nominal = (
        placement.KNOB_SHAFT_XY[0] - s[0], placement.KNOB_SHAFT_XY[1] - s[1],
    )
    assert math.hypot(*nominal) == pytest.approx(low)
    setting = (knob_setting.K_FROM_S_ALONG_MM, knob_setting.K_FROM_S_ACROSS_MM)
    for value, aim in zip(setting, knob_setting.K_AIM_FROM_S_MM):
        assert value / count == pytest.approx(round(value / count), abs=1e-9)
        assert abs(value - aim) < 1.5 * count
    reach = 1.5 * count * math.sqrt(2.0)
    off_line = abs((k[0] - s[0]) * nominal[1] - (k[1] - s[1]) * nominal[0]) / low
    assert off_line < reach
    assert abs(math.dist(s, k) - (low + high) / 2.0) < reach
    # N, the nominal centre, is on S-K at the band's low end, beside the
    # model's knob axis by K's count off the nominal line; S to N carries the
    # set band itself, +x/-0.
    assert math.dist(knob_setting.N_XY, placement.KNOB_SHAFT_XY) < reach
    assert math.dist(s, knob_setting.N_XY) == pytest.approx(disc.CENTRE_DISTANCE)
    assert (k[0] - s[0]) * (knob_setting.N_XY[1] - s[1]) - (k[1] - s[1]) * (
        knob_setting.N_XY[0] - s[0]
    ) == pytest.approx(0.0, abs=1e-9)
    # The printed limits: the set band's top, within one .0001 count of the
    # mesh window, and the -.001 the trial may move the plate toward S
    # (owner ruling 2026-11-24, audit part 2 question C1).
    assert knob_setting.CENTRE_TOLERANCE_MM[0] == pytest.approx(-0.001 * 25.4)
    assert high - low - 0.00254 < knob_setting.CENTRE_TOLERANCE_MM[1] <= high - low
    # C1 ("Yes, the trial may move the plate within those limits."): every
    # setting the step reaches keeps N, indicated TRUE, inside the limits
    # and clear of a bind with both running fits pressed shut (Codjiflo r2 on
    # #3539: the old .001 away move let N reach about +.0027).
    lower = disc.CENTRE_DISTANCE + knob_setting.CENTRE_TOLERANCE_MM[0]
    upper = disc.CENTRE_DISTANCE + knob_setting.CENTRE_TOLERANCE_MM[1]
    error = knob_setting.TRUE_RADIAL_ERROR_MM
    assert error == pytest.approx(0.0199, abs=1e-4)
    aim = knob_setting.setting_radius(1, (0.0, 0.0))
    # From the mid-band aim the limit leaves .00028 away from S: under the
    # .0005 a hobby mill sets, so no away move prints.
    assert knob_setting.TRIAL_AWAY_ROOM_MM == pytest.approx(upper - error - aim)
    assert knob_setting.TRIAL_AWAY_ROOM_MM == pytest.approx(0.00028 * 25.4, abs=0.000005 * 25.4)
    assert knob_setting.TRIAL_AWAY_ROOM_MM < knob_setting.TRIAL_MOVE_MIN_IN * 25.4
    assert knob_setting.TRIAL_MOVE_AWAY_MM is None
    assert drawing.KNOB_TRIAL_AWAY_MOVE_TEXT is None
    # Toward S the limit leaves .00116, but the pressed-shut mesh binds with
    # N under -.00079: the derived move is .0006 each way (.00085 along S-K).
    toward = knob_setting.TRIAL_MOVE_TOWARD_MM
    assert toward == pytest.approx((0.0006 * 25.4, 0.0006 * 25.4))
    assert drawing.KNOB_TRIAL_MOVE_TEXT == ".0006 ALONG AND .0006 ACROSS"
    lowest = knob_setting.setting_radius(-1, toward) - error
    assert lowest == pytest.approx(knob_setting.TRIAL_LOWEST_CENTRE_MM)
    assert lower < lowest and not knob_setting.binds(lowest)
    # The .0008/.0006 pair the old rule printed would bind there.
    old = (0.0008 * 25.4, 0.0006 * 25.4)
    assert knob_setting.binds(knob_setting.setting_radius(-1, old) - error)
    highest = aim + error
    assert highest == pytest.approx(knob_setting.TRIAL_HIGHEST_CENTRE_MM) and highest < upper
    # C3's gate at the top, every gate at the bottom.
    assert round(knob_setting.TRIAL_HIGHEST_MESH.runout_contact_ratio_min, 3) >= 1.1
    assert not knob_setting.TRIAL_LOWEST_MESH.failures()
    # The view marks the band and the two settings, at the places the model
    # owns; only the settings are references.
    assert knob_setting.DRAWING_DIMENSIONS == {
        knob_setting.FEATURE: {
            knob_setting.ALONG_DIMENSION, knob_setting.ACROSS_DIMENSION,
            knob_setting.CENTRE_DIMENSION,
        }
    }
    assert knob_setting.REFERENCE_DIMENSIONS == {
        knob_setting.ALONG_DIMENSION, knob_setting.ACROSS_DIMENSION
    }
    assert knob_setting.CENTRE_DIMENSION not in knob_setting.SETTING_CALLOUTS
    for part, text in knob_setting.SETTING_CALLOUTS.values():
        assert part == 3 and "\n" not in text


def test_view_k_frames_the_chain_with_its_settings_outside_the_crop() -> None:
    scale = drawing.KNOB_SETTING_SCALE[0] / drawing.KNOB_SETTING_SCALE[1]
    centre = drawing.KNOB_SETTING_CENTER
    mid = (
        (knob_setting.S_XY[0] + knob_setting.K_XY[0]) / 2.0,
        (knob_setting.S_XY[1] + knob_setting.K_XY[1]) / 2.0,
    )
    # Project as the machine front shows it (x mirrored); the layout holds
    # either way, so check both.
    for mirror in (1.0, -1.0):
        def sheet(xy):
            return (
                centre[0] + mirror * (xy[0] - mid[0]) * scale / 1000.0,
                centre[1] + (xy[1] - mid[1]) * scale / 1000.0,
            )

        s, q, k, t, n = (
            sheet(xy)
            for xy in (
                knob_setting.S_XY, knob_setting.Q_XY, knob_setting.K_XY,
                drawing.KNOB_SETTING_TAP_XY, knob_setting.N_XY,
            )
        )
        for point in (s, q, k, t, n):
            assert math.dist(point, centre) < drawing.KNOB_SETTING_RADIUS
        keep = drawing.knob_setting_keep(s, q, k, n)
        assert set(keep) == {
            knob_setting.ALONG_DIMENSION, knob_setting.ACROSS_DIMENSION,
            knob_setting.CENTRE_DIMENSION,
        }
        # S to N: the value and its stacked +x/-0 on one text row pair, past
        # S along the line (outside its extension lines), clear of the crop.
        x, y = keep.pop(knob_setting.CENTRE_DIMENSION)
        half = len("43.794+0.050") * DIM_CHAR_WIDTH / 2.0
        box = (x - half, y - DIM_LINE_PITCH, x + half, y + DIM_LINE_PITCH)
        nearest = (min(max(centre[0], box[0]), box[2]), min(max(centre[1], box[1]), box[3]))
        assert math.dist(nearest, centre) > drawing.KNOB_SETTING_RADIUS
        assert drawing.FITUP_NOTE_XY[1][0] < box[0] and box[2] < drawing.FITUP_NOTE_LIMITS[1][0]
        assert drawing.FITUP_NOTE_LIMITS[1][1] < box[1] and box[3] < drawing.KNOB_SETTING_FIELD_TOP
        line = math.dist(s, n)
        along = ((x - n[0]) * (s[0] - n[0]) + (y - n[1]) * (s[1] - n[1])) / line
        assert along - half > line
        # The dimension line runs through the text, so each extension line
        # ends where S and N are carried square to the line to the text's
        # offset: inside the view's field, clear of the title block (run
        # 20261028T050655383Z: N's ran onto its top border).
        unit = ((s[0] - n[0]) / line, (s[1] - n[1]) / line)
        offset = -(x - n[0]) * unit[1] + (y - n[1]) * unit[0]
        for end in (s, n):
            tip = (end[0] - offset * unit[1], end[1] + offset * unit[0])
            assert drawing.FITUP_NOTE_LIMITS[1][1] < tip[1] < drawing.KNOB_SETTING_FIELD_TOP
            assert tip[1] - DRAWING_TEMPLATES[drawing.SPEC.layout].title_block_top_m > 0.005
        boxes = [box]
        legs = {
            knob_setting.ALONG_DIMENSION: (s, q),
            knob_setting.ACROSS_DIMENSION: (q, k),
        }
        for name, (x, y) in keep.items():
            # The value row centred on the text point, its callout row above;
            # the dimension line runs through the text, parallel to its leg.
            _, callout = knob_setting.SETTING_CALLOUTS[name]
            a, b = legs[name]
            leg = math.dist(a, b)
            unit = ((b[0] - a[0]) / leg, (b[1] - a[1]) / leg)
            rows = (
                ("(00.000)", -DIM_LINE_PITCH / 2.0, DIM_LINE_PITCH / 2.0),
                (callout, DIM_LINE_PITCH / 2.0, 1.5 * DIM_LINE_PITCH),
            )
            for text, low, high in rows:
                half = len(text) * DIM_CHAR_WIDTH / 2.0
                # Every corner stays between the leg's two extension lines.
                for dx in (-half, half):
                    for dy in (low, high):
                        assert abs(dx * unit[0] + dy * unit[1]) < leg / 2.0 - 0.0005
            half = max(len(text) for text, _, _ in rows) * DIM_CHAR_WIDTH / 2.0
            box = (x - half, y - DIM_LINE_PITCH / 2.0, x + half, y + 1.5 * DIM_LINE_PITCH)
            nearest = (
                min(max(centre[0], box[0]), box[2]),
                min(max(centre[1], box[1]), box[3]),
            )
            assert math.dist(nearest, centre) > drawing.KNOB_SETTING_RADIUS
            assert drawing.FITUP_NOTE_XY[1][0] < box[0] and box[2] < drawing.FITUP_NOTE_LIMITS[1][0]
            assert drawing.FITUP_NOTE_LIMITS[1][1] < box[1] and box[3] < drawing.KNOB_SETTING_FIELD_TOP
            # Each extension line runs past its dimension line by about
            # 1.6 mm (ANSI 1/16 in); the step text above must stay clear of
            # that overshoot (run 20261028T063820031Z: ALONG's struck the
            # continuation line's "ON").
            shift = (x - (a[0] + b[0]) / 2.0, y - (a[1] + b[1]) / 2.0)
            for end in (a, b):
                assert end[1] + shift[1] + 0.003 < drawing.KNOB_SETTING_FIELD_TOP
            boxes.append(box)
        # Each circle lettered on a leader to its centre: S and T inside the
        # crop, the knob bore just outside it past the boss, each clear of the
        # chain. The bore's letter is not the view's (round 7, rule 26).
        bore = drawing.KNOB_BORE_LETTER
        assert bore != "K" and bore not in {"S", "T"}
        letters = drawing.knob_setting_letters(s, q, k, t)
        assert letters.keys() == drawing.KNOB_SETTING_LEGEND.keys() == {"S", bore, "T"}
        half_w, half_h = drawing.KNOB_SETTING_LETTER_HALF
        diagonal = math.hypot(half_w, half_h)
        for letter, ((left, top), tip) in letters.items():
            assert tip == {"S": s, bore: k, "T": t}[letter]
            middle = (left + half_w, top - half_h)
            reach = math.dist(middle, centre)
            if letter == bore:
                assert reach - diagonal > drawing.KNOB_SETTING_RADIUS
            else:
                assert reach + diagonal < drawing.KNOB_SETTING_RADIUS
            for a, b in ((s, q), (q, k)):
                assert _segment_distance(middle, a, b) > diagonal + 0.0005
            for other in (s, q, k, t):
                if other != tip:
                    assert math.dist(middle, other) > diagonal + 0.002
            boxes.append((left, top - 2 * half_h, left + 2 * half_w, top))
        caption_lines = drawing.KNOB_SETTING_CAPTION.splitlines()
        left, top = drawing.KNOB_SETTING_CAPTION_XY
        caption = (
            left,
            top - len(caption_lines) * NOTE_LINE_PITCH,
            left + max(map(len, caption_lines)) * NOTE_CHAR_WIDTH,
            top,
        )
        assert caption[2] < centre[0] - drawing.KNOB_SETTING_RADIUS
        assert caption[0] > drawing.FITUP_NOTE_LIMITS[0][0]
        assert caption[1] > DRAWING_TEMPLATES[drawing.SPEC.layout].title_block_top_m
        boxes.append(caption)
        for index, one in enumerate(boxes):
            for other in boxes[index + 1:]:
                assert (
                    one[2] < other[0] or other[2] < one[0]
                    or one[3] < other[1] or other[3] < one[1]
                )
    # The legend names each lettered circle by its part number.
    for letter, stem in (
        ("S", "pd-transgear-arm"),
        (drawing.KNOB_BORE_LETTER, "pd-transgear-knob-bush"),
        ("T", "pd-vn-transgear-arm-plate-screw"),
    ):
        assert f"{letter}: {_number(stem)} " in drawing.KNOB_SETTING_CAPTION
    # ALONG is the DRO frame's pivot-S axis; the legend defines ALONG and
    # ACROSS.
    s, q = knob_setting.S_XY, knob_setting.Q_XY
    toward_p = (knob_setting.P_XY[0] - s[0], knob_setting.P_XY[1] - s[1])
    along = (q[0] - s[0], q[1] - s[1])
    assert abs(toward_p[0] * along[1] - toward_p[1] * along[0]) < 1e-9
    assert toward_p[0] * along[0] + toward_p[1] * along[1] > 0.0
    assert "ALONG:" in drawing.KNOB_SETTING_CAPTION
    assert "ACROSS:" in drawing.KNOB_SETTING_CAPTION
    assert drawing.KNOB_SETTING_CENTER[1] - drawing.KNOB_SETTING_RADIUS > (
        DRAWING_TEMPLATES[drawing.SPEC.layout].title_block_top_m
    )
    assert drawing.KNOB_SETTING_VIEW_NAME in drawing.KNOB_SETTING_CAPTION


def test_the_jig_bored_k_lands_in_the_set_band_with_margin_at_both_ends() -> None:
    import _process_plans
    import _shop_equipment
    import paper_drive_arm_registration as registration

    low, high = disc.CENTRE_DISTANCE_WINDOW
    ux, uy = registration.S_TO_K_UNIT
    shop = _process_plans.load_shop()
    equipment = _shop_equipment.load()
    dro_record = equipment["dro"]["pm-30mv"]
    # The installed DRO's vendor-stated accuracy, per axis (its cite).
    (stated,) = [
        float(match.group(1))
        for cite in dro_record["cite"]
        if cite.startswith("DRO accuracy")
        for match in [re.search(r"(\.\d+)” Accuracy", cite)]
        if match
    ]
    accuracy = stated * 25.4
    # Centring is a null reading against the step's stated acceptance, not a
    # measured size: a sweep (the TIR) under the printed value puts each
    # centre within half of it of the spindle (owner ruling 2026-11-08
    # (Pedro), #2144 item 5.3). The bound holds while the indicator repeats
    # to its stated sweep at null; the shop's test indicator must read it.
    sweep = drawing.KNOB_SETTING_SWEEP_IN * 25.4
    assert shop["gauges"]["dti"]["resolution_mm"] < sweep
    centring = sweep / 2.0
    # Signed worst case, every bound adding the same way: the DRO is zeroed
    # on S, so its two axes' errors enter once, on the S-to-K move, both
    # along any direction; the indicator centres S and K; the pivot-and-pin
    # tram turns K about S by its lever.
    dro = accuracy * (abs(ux) + abs(uy))
    radial_err = dro + 2.0 * centring
    lever = knob_setting.K_SET_CENTRE_DISTANCE_MM / steps_arm.PIN_STATION
    tangential_err = dro + 2.0 * centring + 2.0 * centring * lever
    assert centring == pytest.approx(0.0005 * 25.4 / 2.0)
    assert radial_err == pytest.approx(0.0199, abs=1e-4)
    # The spec charges the same budget against DETAIL K's limits for every
    # setting the trial reaches (C1; Codjiflo r2 on #3539).
    assert knob_setting.DRO_ACCURACY_MM == pytest.approx(accuracy)
    assert knob_setting.TRUE_SWEEP_IN == drawing.KNOB_SETTING_SWEEP_IN
    assert knob_setting.TRUE_RADIAL_ERROR_MM == pytest.approx(radial_err)
    # The printed values are the display's own counts: the operator dials
    # exactly what DETAIL K prints.
    # The 5 um scale's inch-mode count, .0002.
    count = round(shop["gauges"]["mill-x-dro"]["resolution_mm"] / 25.4, 4) * 25.4
    assert knob_setting.DRO_COUNT_MM == pytest.approx(count)
    x, y = knob_setting.K_FROM_S_ALONG_MM, knob_setting.K_FROM_S_ACROSS_MM
    for value in (x, y):
        printed = round(value / 25.4, knob_setting.PLACES) * 25.4
        assert round(printed / count) * count == pytest.approx(value)

    def margins(point):
        radial = math.hypot(*point) - low
        return radial - radial_err, (high - low) - (radial + radial_err)

    radial = math.hypot(x, y) - low
    tangential = abs(x * uy - y * ux)
    bottom_margin, top_margin = margins((x, y))
    # 1. Physically: the worst-case K lies inside the set band at both ends.
    assert low < low + radial - radial_err and low + radial + radial_err < high
    assert bottom_margin > 0.0 and top_margin > 0.0
    # 2. No count about the aim leaves a larger minimum margin.
    best = max(min(margins(point)) for point in knob_setting.dro_count_candidates())
    assert min(bottom_margin, top_margin) == pytest.approx(best, abs=1e-12)
    # 3. At least what the mid-band aim leaves after the error budget and the
    # count lattice: the nearest count is within half a count per axis.
    floor = (high - low) / 2.0 - radial_err - count / 2.0 * (abs(ux) + abs(uy))
    assert floor > 0.0
    assert min(bottom_margin, top_margin) > floor
    # And inside K's drawn setting circle about its nominal.
    radius = registration.REDUCER_AXIS_SETUP_RADIUS_MM
    assert math.hypot(radial + radial_err, tangential + tangential_err) < radius


def test_the_matched_plate_is_refitted_on_its_dowels_and_re_read() -> None:
    fitted = _step_body("arm-plate-fitted")
    assert steps.inch_window(plate_locating_interface.PROUD_LIMITS_MM, 3, " TO ") in fitted
    # The setting step's own coordinates fix K; the refit only checks shake.
    assert disc.inch_text(knob_setting.K_FROM_S_ALONG_MM, knob_setting.PLACES) not in fitted
    assert drawing.KNOB_SETTING_VIEW_NAME not in fitted
    for method in ("RFS", "UNCERTAINTY", "QUALIFIED", "ACTUAL"):
        assert method not in fitted
    assert steps.step_number("arm-plate-located") + 1 == steps.step_number("arm-plate-fitted")


def test_the_plate_recheck_names_its_bore_and_acceptance() -> None:
    """The re-check can print on the sheet after DETAIL K and the TRUE key, so it
    names the bore's part and points at the step and sheet that define TRUE
    (integration review, run 20261109T062834910Z)."""
    sheet = drawing.SHEET_NAMES.index(drawing.KNOB_SETTING_SHEET) + 1
    defined = drawing.sub_step("arm-plate-located", 2)
    assert drawing.KNOB_SETTING_TRUE in _step_body("arm-plate-located")
    assert (
        f"CHECK: RE-INDICATED, {_number('pd-transgear-knob-bush')} KNOB BORE "
        f"{drawing.KNOB_BORE_LETTER} IS STILL TRUE PER {defined} (SHEET {sheet})."
        in _step_body("arm-plate-located")
    )
    columns = drawing.pack_step_columns(
        drawing._step_text(operating_domain=_unit_operating_domain())
    )
    defining = [
        column
        for column in columns
        if any(line.startswith(f"{defined}. ") for line in column.text.splitlines())
    ]
    assert [column.sheet for column in defining] == [drawing.KNOB_SETTING_SHEET]


def test_bom_identifies_the_current_inch_mesh_parts_without_cutter_prose() -> None:
    for stem, spec in (
        ("pd-rack-pinion", disc),
        ("pd-transgear-knob-shaft", knob_shaft),
        ("pd-transgear-feed-pinion", feed_pinion),
    ):
        description = drawing.BOM_DESCRIPTIONS[stem]
        assert f"{spec.TEETH}T" in description
        assert f"{spec.DIAMETRAL_PITCH:g}DP" in description
        assert f"PA{spec.PRESSURE_ANGLE_DEG:g}" in description
        assert "STOCK" in description
        assert "SHIFTED" not in description
        assert len(description) <= drawing.BOM_DESCRIPTION_MAX_CHARS
    assert "REDUCER DISC" in drawing.BOM_DESCRIPTIONS["pd-rack-pinion"]
    # #2410: the bare purchased strip, no backer.
    rack = drawing.BOM_DESCRIPTIONS["pd-feed-rack"]
    assert "RACK" in rack and "BACKER" not in rack
    assert f"{feed_pinion.DIAMETRAL_PITCH:g}DP" in rack
    assert f"PA{feed_pinion.PRESSURE_ANGLE_DEG:g}" in rack
    for text in (*drawing.sheet_texts(_unit_step_notes()), *drawing.BOM_DESCRIPTIONS.values()):
        assert "CUTTER" not in text


def test_the_feed_setup_reference_uses_the_selected_ratios_and_reference_pitch() -> (
    None
):
    expected = (
        sprocket.CRANK_TEETH
        / sprocket.KNOB_TEETH
        * knob_shaft.TEETH
        / disc.TEETH
        * math.pi
        * feed_pinion.PITCH_DIA
    )
    assert paper_geometry.NET_RACK_TRAVEL_PER_CRANK_REV == pytest.approx(expected)
    text = drawing.PAPER_FEED_TEXT
    match = re.search(r"PLATEN TRAVEL (\d*\.\d+) PER CRANK REV \(REF\)", text)
    assert match
    places = steps.PAPER_FEED_REFERENCE_PLACES
    assert len(match[1].split(".")[1]) == places
    assert float(match[1]) * 25.4 == pytest.approx(expected, abs=0.5 * 10.0**-places * 25.4)
    assert f"{sprocket.CRANK_TEETH}-TOOTH CRANK" in text
    assert f"{sprocket.KNOB_TEETH}-TOOTH KNOB" in text
    for caption in drawing.ASSEMBLED_CAPTIONS.values():
        assert text in caption
    # The form-cutter setting changes the tooth boundary, not the rolling pitch.
    tip_based_travel = expected * feed_pinion.OUTSIDE_DIA / feed_pinion.PITCH_DIA
    assert float(match[1]) != pytest.approx(tip_based_travel)
    # The historical 30DP comparison is provenance, not a second setup value.
    assert "30DP" not in text and "%" not in text


def _transgear_drawn_count(stem: str) -> int:
    """The transgear views draw the stacked shims, not the kit's spares."""
    if stem == "pd-vn-transgear-cluster-shim":
        return cluster_fit.SHIM_COUNT_MODEL
    return CONTRACT_TRANSGEAR_QUANTITIES[stem]


def test_sheet_two_shows_and_balloons_exactly_the_transgear() -> None:
    expected = {
        f"{stem}-{index}"
        for stem in CONTRACT_TRANSGEAR_QUANTITIES
        for index in range(1, _transgear_drawn_count(stem) + 1)
        if stem not in ("pd-transgear-removable", explode.DISC_SCREW)
    } | {"pd-transgear-removable-1", *DISC_SCREW_INSTANCES}
    assert drawing.TRANSGEAR_INSTANCES == expected
    # The shared fillister's RackScrews are the platen's, never sheet 2's.
    assert not set(RACK_SCREW_INSTANCES) & drawing.TRANSGEAR_INSTANCES
    # Every transgear family has a batch anchor, on either sheet's view.
    assert set(drawing.TRANSGEAR_BALLOON_ANCHORS) == set(CONTRACT_TRANSGEAR_QUANTITIES)
    # The knob wheel is instance 1; crank wheel and spare T18 stay off.
    assert drawing.TRANSGEAR_BALLOON_ANCHORS["pd-transgear-removable"].instance == (
        "pd-transgear-removable-1"
    )
    # The hub lands on its flange's front rim, on the far side from the
    # knob stack; the knob shaft on a 15T tooth tip at F; every other family
    # walks its own body on the instance the view shows.
    hub_point = drawing.TRANSGEAR_BALLOON_ANCHORS["pd-transgear-disc-hub"].point_mm
    assert hub_point is not None
    assert math.hypot(hub_point[0], hub_point[1]) == pytest.approx(
        drawing.hub.FLANGE_DIA / 2.0, abs=1e-3
    )
    assert hub_point[2] == pytest.approx(-drawing.hub.FLANGE_THICK)
    assert hub_point[0] > 0.0 and hub_point[1] > 0.0
    shaft = drawing.knob_shaft
    x, y, z = drawing.TRANSGEAR_BALLOON_ANCHORS["pd-transgear-knob-shaft"].point_mm
    assert z == 0.0  # F, the pinion's front face
    assert math.hypot(x, y) == pytest.approx(shaft.OUTSIDE_DIA / 2.0, abs=1e-4)
    # A tooth centre: half a pitch from the gap centred on GAP_AZIMUTH_DEG.
    pitch = 360.0 / shaft.TEETH
    offset = (math.degrees(math.atan2(y, x)) - shaft.GAP_AZIMUTH_DEG) % pitch
    assert offset == pytest.approx(pitch / 2.0, abs=1e-3)
    # *Isometric: sheet right -0.707 x + 0.707 z, up 0.408 x + 0.816 y +
    # 0.408 z.  The tip stands lower right of the axis, more than the D-core
    # radius off the axis's projected line, so the forward neck cannot hide it.
    right, up = -0.7071 * x, 0.4082 * x + 0.8165 * y
    assert right > 0.0 and up < 0.0
    axis = (0.7071, 0.4082)
    along = (right * axis[0] + up * axis[1]) / math.hypot(*axis)
    assert math.sqrt(right**2 + up**2 - along**2) > shaft.CORE_DIA / 2.0
    # The feed sleeve lands on its 12T tip land, forward of the rear face that
    # draws against the exploded rear bushing (#2551 machinist review).
    sx, sy, sz = drawing.TRANSGEAR_BALLOON_ANCHORS["pd-transgear-feed-pinion"].point_mm
    assert math.hypot(sx, sy) == pytest.approx(
        drawing.feed_pinion.OUTSIDE_DIA / 2.0, abs=1e-3
    )
    assert 0.0 < sz < drawing.feed_pinion.FACE_WIDTH
    # The collar lands on its front face's outer circle at local -X, lower
    # right of its axis, never its lowest point beside the flat pin (#2831).
    cx, cy, cz = drawing.TRANSGEAR_BALLOON_ANCHORS["pd-transgear-drive-collar"].point_mm
    assert (cx, cy, cz) == (pytest.approx(-drawing.collar.OD / 2.0, abs=1e-4), 0.0, 0.0)
    assert -0.7071 * cx > 0.0 and 0.4082 * cx < 0.0
    pinned = {
        "pd-transgear-removable",
        "pd-transgear-disc-hub",
        "pd-transgear-knob-shaft",
        "pd-transgear-feed-pinion",
        "pd-transgear-drive-collar",
    }
    assert all(
        anchor == drawing.BalloonAnchor()
        for stem, anchor in drawing.TRANSGEAR_BALLOON_ANCHORS.items()
        if stem not in pinned
    )


# Farm run 20261002T180658288Z's inner-view ring (its drawing.balloon_ring
# event): BOM item and attachment (sheet m), in ring order. 17 is the
# arm-plate screw, 24 the rear bushing, 32 the collar.
INNER_RING_180658 = (
    ("34", (0.219889, 0.176708)),
    ("32", (0.220362, 0.174046)),
    ("18", (0.229903, 0.170997)),
    ("35", (0.234541, 0.176240)),
    ("39", (0.236058, 0.178096)),
    ("26", (0.226995, 0.178996)),
    ("24", (0.228995, 0.180840)),
    ("17", (0.233308, 0.188817)),
    ("33", (0.218228, 0.178923)),
)
# That run logged no outline: run 20261002T172458664Z's 1:2 inner outline,
# scaled to 1:3 about the collar's landing (218.520, 171.821 there; 220.362,
# 174.046 here). Its circles render r 5.232 mm.
INNER_OUTLINE_180658 = (0.209403, 0.162653, 0.239943, 0.192772)
BALLOON_RADIUS = 0.005232


def _ring_centres(
    outline: tuple[float, float, float, float],
) -> list[tuple[float, float]]:
    """_spread_balloons' circle centres for INNER_RING_180658, in its order."""
    cx, cy = (outline[0] + outline[2]) / 2.0, (outline[1] + outline[3]) / 2.0
    rx = (outline[2] - outline[0]) / 2.0 + drawing.BALLOON_MARGIN
    ry = (outline[3] - outline[1]) / 2.0 + drawing.BALLOON_MARGIN
    thetas = [math.atan2(y - cy, x - cx) for _item, (x, y) in INNER_RING_180658]
    order = sorted(range(len(thetas)), key=thetas.__getitem__)
    gap = _drawing_balloons._min_angular_gap(
        min(rx, ry), BALLOON_RADIUS, clearance=_drawing_balloons._BALLOON_CLEARANCE_M
    )
    angles = _drawing_balloons._push_apart_on_ring(
        [thetas[index] for index in order], min_gap=gap
    )
    centres = [(0.0, 0.0)] * len(thetas)
    for index, angle in zip(order, angles):
        centres[index] = (cx + rx * math.cos(angle), cy + ry * math.sin(angle))
    return centres


def _crossed_items(
    centres: list[tuple[float, float]], slots: list[int]
) -> set[frozenset[str]]:
    """The item pairs whose printed leaders, circle edge to attachment, cross."""
    segments = []
    for (item, (x, y)), slot in zip(INNER_RING_180658, slots):
        bx, by = centres[slot]
        length = math.hypot(x - bx, y - by)
        segments.append(
            LeaderSegment(
                label=item,
                kind="balloon",
                x0=bx + (x - bx) / length * BALLOON_RADIUS,
                y0=by + (y - by) / length * BALLOON_RADIUS,
                x1=x,
                y1=y,
            )
        )
    return {
        frozenset((crossing.a.label, crossing.b.label))
        for crossing in find_leader_leader_crossings(segments)
    }


def test_the_inner_ring_swaps_crossing_leaders_onto_each_others_slots() -> None:
    attachments = [attach for _item, attach in INNER_RING_180658]
    identity = list(range(len(INNER_RING_180658)))
    centres = _ring_centres(INNER_OUTLINE_180658)
    # The ring as run 20261002T180658288Z left it crosses 17 over 24.
    assert _crossed_items(centres, identity) == {frozenset({"17", "24"})}
    slots = drawing.uncrossed_ring_slots(centres, attachments)
    moved = {INNER_RING_180658[index][0] for index in identity if slots[index] != index}
    assert moved == {"17", "24"}
    assert _crossed_items(centres, slots) == set()
    # The outline is reconstructed: within 2 mm of it either way, whatever
    # the ring crosses, the slots it takes cross nothing, and no leader runs
    # through another balloon's circle.
    for dx, dy in product((-0.002, 0.0, 0.002), repeat=2):
        x0, y0, x1, y1 = INNER_OUTLINE_180658
        shifted = _ring_centres((x0 + dx, y0 + dy, x1 + dx, y1 + dy))
        slots = drawing.uncrossed_ring_slots(shifted, attachments)
        assert sorted(slots) == identity
        assert _crossed_items(shifted, slots) == set(), (dx, dy)
        for index, (x, y) in enumerate(attachments):
            bx, by = shifted[slots[index]]
            for other, (ox, oy) in enumerate(shifted):
                if other == slots[index]:
                    continue
                t = ((ox - bx) * (x - bx) + (oy - by) * (y - by)) / (
                    (x - bx) ** 2 + (y - by) ** 2
                )
                t = min(1.0, max(0.0, t))
                gap = math.hypot(bx + t * (x - bx) - ox, by + t * (y - by) - oy)
                assert gap > BALLOON_RADIUS, (dx, dy, index, other)


def test_an_uncrossed_ring_keeps_its_slots() -> None:
    centres = [(0.0, 1.0), (1.0, 0.0), (0.0, -1.0)]
    attachments = [(0.0, 0.1), (0.1, 0.0), (0.0, -0.1)]
    assert drawing.uncrossed_ring_slots(centres, attachments) == [0, 1, 2]
    # Two leaders swapped across each other go back.
    assert drawing.uncrossed_ring_slots(centres[:2], attachments[1::-1]) == [1, 0]


@pytest.mark.parametrize("offset_m", (-5e-5, 0.0, 5e-5, 1.15e-4))
def test_the_inner_ring_knob_pair_from_run_222629_swaps_when_touching(offset_m) -> None:
    """Run 20261023T222629630Z's audit: inner-view balloons 36 (knob shaft) and
    40 (cup pin) crossed 0.115 mm past 36's attachment after the final rebuild;
    within the 0.1 mm touch tolerance at uncross time no swap was made."""
    from _layout_geometry import LeaderSegment, find_leader_leader_crossings

    start_40, end_40 = (0.2453, 0.1719), (0.2317, 0.1763)
    dx, dy = end_40[0] - start_40[0], end_40[1] - start_40[1]
    norm = math.hypot(dx, dy)
    # 36's attachment on 40's leader, displaced normally by offset_m.
    t = 0.9
    attach_36 = (
        start_40[0] + t * dx - dy / norm * offset_m,
        start_40[1] + t * dy + dx / norm * offset_m,
    )
    centres = [(0.2414, 0.1586), (0.2462, 0.1716)]
    attachments = [attach_36, end_40]
    unswapped = [
        LeaderSegment("36", "balloon", *centres[0], *attach_36),
        LeaderSegment("40", "balloon", *centres[1], *end_40),
    ]
    if abs(offset_m) < 1e-4:
        assert not find_leader_leader_crossings(unswapped)  # The audit's touch.
    slots = drawing.uncrossed_ring_slots(centres, attachments)
    assert slots == [1, 0]
    swapped = [
        LeaderSegment("36", "balloon", *centres[1], *attach_36),
        LeaderSegment("40", "balloon", *centres[0], *end_40),
    ]
    assert not find_leader_leader_crossings(swapped, tol=0.0, shared_terminus=0.0)
    assert drawing._leader_clearance(
        (*centres[1], *attach_36), (*centres[0], *end_40)
    ) >= drawing._UNCROSS_CLEARANCE_M


def test_the_isometric_ring_pair_from_run_082822_swaps() -> None:
    """Run 20261015T082822796Z's audit: isometric balloons 14 and 16, leaders
    (circle edge -> attachment), crossed at (372.9, 178.4) mm. Their slots
    swap, and the swapped leaders cross nothing."""
    centres = [(0.4017, 0.1595), (0.4032, 0.1753)]
    attachments = [(0.3703, 0.1801), (0.3639, 0.1793)]

    def crossings(slots: list[int]) -> list:
        return find_leader_leader_crossings(
            [
                LeaderSegment(
                    label=str(index),
                    kind="balloon",
                    x0=centres[slot][0],
                    y0=centres[slot][1],
                    x1=attach[0],
                    y1=attach[1],
                )
                for index, (slot, attach) in enumerate(zip(slots, attachments))
            ]
        )

    assert crossings([0, 1])
    slots = drawing.uncrossed_ring_slots(centres, attachments)
    assert slots == [1, 0]
    assert not crossings(slots)


# The isometric never balloons these: farm run 20261001T051043622Z found no
# reachable isometric ink for the sleeve; the pin, front bushing and retaining
# ring meet on the pin nose; the knob bush stands under the ring and in the
# arm, the cup screw in the cup (#2425). Sheet 3's explode balloons them.
HIDDEN_BY_THE_ISOMETRIC = {
    "pd-transgear-feed-pinion",
    "pd-transgear-knob-shaft",
    "pd-transgear-drive-collar",
    "pd-vn-transgear-knob-drive-pin",
    "pd-transgear-knob-bush",
    "pd-vn-transgear-knob-cup-screw",
    "pd-vn-transgear-arm-plate-screw",
    "pd-vn-transgear-arm-plate-locating-pin",
    "pd-vn-transgear-latch-pin",
    "pd-transgear-rear-bushing",
    "pd-transgear-pin",
    "pd-transgear-front-bushing",
    "pd-vn-transgear-retaining-ring",
    "pd-vn-transgear-cluster-shim",
    # #2409: inside their hosts.
    "pd-vn-transgear-collar-flat-pin",
    "pd-vn-transgear-hub-key-pin",
}
# Hidden in the arm's counterbore from the isometric; Section A-A balloons it.
BALLOONED_BY_SECTION_A_A = {"pd-vn-transgear-pivot-spring"}


def test_each_transgear_family_balloons_once_on_the_view_that_shows_it() -> None:
    # Item numbers against the dict order, so the order must come from them.
    items = {
        stem: str(len(drawing.BOM_PART_NUMBERS) - index)
        for index, stem in enumerate(drawing.BOM_PART_NUMBERS)
    }
    iso, exploded = drawing.transgear_balloon_items(items)
    iso_stems = {stem for stem, _item in iso}
    exploded_stems = {stem for stem, _item in exploded}
    assert drawing.ISO_HIDDEN_STEMS == HIDDEN_BY_THE_ISOMETRIC
    assert drawing.ISO_SECTION_ONLY_STEMS == BALLOONED_BY_SECTION_A_A
    assert iso_stems == (
        set(CONTRACT_TRANSGEAR_QUANTITIES) - HIDDEN_BY_THE_ISOMETRIC - BALLOONED_BY_SECTION_A_A
    )
    assert exploded_stems == explode.TRANSGEAR_SHOWN_STEMS
    assert HIDDEN_BY_THE_ISOMETRIC < exploded_stems
    # Every transgear family is ballooned on sheet 2 (isometric or Section
    # A-A) or sheet 3.
    section = {stem for stem, *_ in drawing.PIVOT_BALLOON_TIPS}
    assert BALLOONED_BY_SECTION_A_A <= section
    assert iso_stems | exploded_stems | BALLOONED_BY_SECTION_A_A == set(
        CONTRACT_TRANSGEAR_QUANTITIES
    )
    for balloons in (iso, exploded):
        assert all(items[stem] == item for stem, item in balloons)
        numbers = [int(item) for _stem, item in balloons]
        assert numbers == sorted(numbers)
    # The explode shows every instance of its families, the mounted knob
    # wheel only of the removables, the shared fillister's DiscScrews only
    # (never the platen's RackScrews), and nothing else.
    assert drawing.TRANSGEAR_EXPLODED_INSTANCES == {
        f"{stem}-{index}"
        for stem in exploded_stems - {"pd-transgear-removable", explode.DISC_SCREW}
        for index in range(1, _transgear_drawn_count(stem) + 1)
    } | {explode.KNOB_WHEEL_INSTANCE, *DISC_SCREW_INSTANCES}
    assert drawing.TRANSGEAR_EXPLODED_INSTANCES <= drawing.TRANSGEAR_INSTANCES
    # The pivot stack is SECTION A-A's; the latch hook stays on the bar.
    for stem in (
        "pd-transgear-pivot-spacer",
        "pd-vn-transgear-pivot-screw",
        "pd-latch-hook",
    ):
        assert stem not in exploded_stems
    # Each family is drawn in exactly one of sheet 3's two views: the disc
    # cluster on its pin in one, the hanger and knob stack in the other.
    groups = drawing.TRANSGEAR_EXPLODED_GROUPS
    assert len(groups) == 2
    assert groups[0].stems | groups[1].stems == exploded_stems
    assert not groups[0].stems & groups[1].stems
    assert "pd-rack-pinion" in groups[1].stems and "pd-transgear-pin" in groups[1].stems
    assert {"pd-transgear-arm", "pd-transgear-knob-shaft"} <= groups[0].stems
    assert (
        drawing.exploded_group_instances(groups[0])
        | drawing.exploded_group_instances(groups[1])
    ) == drawing.TRANSGEAR_EXPLODED_INSTANCES


def test_the_transgear_explode_views_fit_their_fields_at_the_bom_configuration() -> None:
    template = DRAWING_TEMPLATES[drawing.SPEC.layout]
    knob, cluster = (group.ring_limits for group in drawing.TRANSGEAR_EXPLODED_GROUPS)
    # Both fields inside the border and clear of each other; the knob stack's
    # stops above the title block, the cluster's above the caption.
    for left, bottom, right, top in (knob, cluster):
        assert left > 0.0127 and bottom > drawing.SHEET_INNER_BORDER_BOTTOM
        assert right < 0.420 and top < 0.270
    assert knob[2] < cluster[0]
    assert knob[1] > template.title_block_top_m
    # Run 20261024T025815061Z's 1:1 knob-stack outline (its projected box,
    # 247.3 x 226.8 mm) and the cluster's width from the builder's stations
    # (137.6 mm), each grown by the pin's rearward throw along the
    # isometric's Z (1/sqrt(2) across, 1/sqrt(6) up: the pin's head is the
    # view's rearmost point).  The cluster's height is native: round 12 read
    # its ring 147.4 mm tall (to 0.1 mm) at a 12 mm throw, so the throw now
    # must leave the ring a millimetre short of its field.
    scale = drawing.TRANSGEAR_EXPLODED_SCALE[0] / drawing.TRANSGEAR_EXPLODED_SCALE[1]
    reach = 2 * drawing.BALLOON_RING_REACH
    pin_throw = sum(
        step.distance_mm for step in explode.TRANSGEAR_STEPS
        if "pd-transgear-pin" in step.stems
    ) / 1000.0
    cluster_height = (0.14745 - reach) / scale + (pin_throw - 0.012) / math.sqrt(6.0)
    for (width, height), (left, bottom, right, top), margin in (
        ((0.2473, 0.2268), knob, 0.0),
        ((0.1376 + pin_throw / math.sqrt(2.0), cluster_height), cluster, 0.001),
    ):
        assert width * scale + reach < right - left - margin
        assert height * scale + reach < top - bottom - margin
    for group in drawing.TRANSGEAR_EXPLODED_GROUPS:
        left, bottom, right, top = group.ring_limits
        assert left < group.center[0] < right and bottom < group.center[1] < top
    # The caption sits right of the knob stack's field, under the cluster's
    # and above the title block.
    x, y = drawing.TRANSGEAR_EXPLODED_CAPTION_XY
    lines = drawing.TRANSGEAR_EXPLODED_CAPTION.splitlines()
    assert lines[0].startswith("TRANSGEAR EXPLODED, ISOMETRIC:")
    assert x > knob[2] and y < cluster[1]
    assert x + max(map(len, lines)) * NOTE_CHAR_WIDTH < 0.420
    assert y - len(lines) * NOTE_LINE_PITCH > template.title_block_top_m
    assert drawing.TRANSGEAR_EXPLODED_ORIENTATION == "*Isometric"
    assert drawing.TRANSGEAR_EXPLODED_SCALE == drawing.TRANSGEAR_VIEW_SCALE
    assert drawing.SHEET_SCALES["TRANSGEAR EXPLODED"] == drawing.TRANSGEAR_EXPLODED_SCALE


# The v40 sheet 2 (the same layout code as 594749aec) printed the transgear
# isometric's outline at 2:3, read from the PDF's view image. The farm run of
# 9055bc155 refused the one-piece hook's isometric. That isometric's left
# edge and top come from its message (rings at 261.5 and 265.8). Its right
# edge and bottom are v40's, because the hook only grows the view up and left.
ISO_OUTLINE_V40 = (0.2853, 0.1112, 0.3966, 0.2448)
ISO_OUTLINE_ONE_PIECE_HOOK = (0.2785, 0.1112, 0.3966, 0.2488)


def _moved(
    outline: tuple[float, float, float, float], shift: tuple[float, float]
) -> tuple[float, float, float, float]:
    dx, dy = shift
    return (outline[0] + dx, outline[1] + dy, outline[2] + dx, outline[3] + dy)


@pytest.mark.parametrize(
    "iso_outline", [ISO_OUTLINE_ONE_PIECE_HOOK, ISO_OUTLINE_V40], ids=["one-piece-hook", "v40"]
)
def test_the_centred_isometric_ring_fits_sheet_two_field(
    iso_outline: tuple[float, float, float, float],
) -> None:
    """Centred vertically and unmoved along x, the isometric's ring fits the
    field, right of the pivot section's."""
    shift = drawing.transgear_view_shift(iso_outline)
    assert shift[0] == 0.0
    iso = _moved(iso_outline, shift)
    reach = drawing.BALLOON_RING_REACH
    left, bottom, right, top = drawing.SHEET_TWO_RING_LIMITS
    assert (iso[1] - reach - bottom) == pytest.approx(top - (iso[3] + reach))
    assert iso[1] - reach >= bottom and iso[3] + reach <= top
    assert left <= iso[0] - reach and iso[2] + reach <= right


def test_an_isometric_ring_leaving_the_field_sideways_is_refused() -> None:
    x0, y0, x1, y1 = ISO_OUTLINE_V40
    with pytest.raises(ValueError, match=r"sheet 2 isometric ring x .* leaves 185\.0 to 415\.0 mm"):
        drawing.transgear_view_shift((x0 + 0.020, y0, x1 + 0.020, y1))


def test_the_one_piece_hook_isometric_moves_down_4_0_mm() -> None:
    dx, dy = drawing.transgear_view_shift(ISO_OUTLINE_ONE_PIECE_HOOK)
    assert (dx, dy) == (0.0, pytest.approx(-0.0040))


def test_an_isometric_taller_than_the_field_is_refused() -> None:
    x0, y0, x1, _y1 = ISO_OUTLINE_ONE_PIECE_HOOK
    with pytest.raises(
        ValueError, match=r"isometric ring height 173\.0 mm > room 172\.0 mm"
    ):
        drawing.transgear_view_shift((x0, y0, x1, y0 + 0.139))


def test_no_sheet_prints_a_forbidden_word() -> None:
    texts = (*drawing.sheet_texts(_unit_step_notes()), *drawing.BOM_DESCRIPTIONS.values())
    for text in texts:
        for word in FORBIDDEN_SHEET_WORDS:
            assert word not in text.upper(), (word, text)


def test_no_retired_part_is_named_on_the_sheet() -> None:
    retired = {"MHA-079", "MHA-080", "MHA-108", "MHA-109"}
    text = _unit_step_notes().fitup_steps
    printed = set(re.findall(r"MHA-(?!VN-)[A-Z]{2}-(?:[0-9]{2}(?:-TL-(?:[0-9]{2}|VN-[5-9][0-9]))?|VN-[5-9][0-9])(?:-T[0-9]{3})?(?![A-Z0-9-])", text))
    assert not any(number in text for number in retired)
    # Off-BOM numbers: the drive-train package the crank side cites and its
    # crankshaft the fit-up pulls forward, and the frame parts (columns, base
    # deck) the bar is clamped to and set from.
    assert printed <= set(drawing.BOM_PART_NUMBERS.values()) | {
        assembly_contract("dt-drive-train").number,
        drawing.CRANKSHAFT,
        drawing.FRAME_COLUMN,
        drawing.FRAME_BASE,
    }


def test_the_knob_stack_goes_on_front_to_rear() -> None:
    """Contract §1: shaft through ring and bush, then the cup and its screw,
    then the collar (#2425)."""
    body = _step_body("knob-stack-fitted")
    order = [
        "pd-transgear-knob-shaft",
        "pd-transgear-knob-thrust-ring",
        "pd-transgear-knob-bush",
        "pd-transgear-knob-cup",
        "pd-vn-transgear-knob-cup-screw",
        "pd-transgear-drive-collar",
    ]
    positions = [body.index(_number(stem)) for stem in order]
    assert positions == sorted(positions)


def test_the_pivot_screw_is_unlocked_and_the_spacer_bonded_as_made() -> None:
    """MHA-PD-VN-57 runs through the bar, its tip faced below the front face,
    and carries no lock (owner ruling U-MHA-PD-VN-57-no-lock, #1194): no
    stake, no threadlocker. The seat is shown in the pivot view. R9-6 never
    faces MHA-PD-20.  Owner ruling 2026-11-24, fit audit question 6: the
    spacer is bonded on the shoulder flush with its end (rule 23: the grade,
    the degrease, how it is held square while it cures, the compound kept
    off the running fit, and the cure before load), and the MHA-PD-VN-63
    spring under the head holds the arm on it."""
    body = _step_body("hanger-pivoted")
    window = steps.inch_window(pivot_screw.TIP_RECESS, 3, " TO ")
    assert "THREADLOCKER" not in body
    assert "STAKE" not in body
    assert "BLIND" not in body
    assert f"{window} BELOW THE BAR'S FRONT FACE" in _step_body("arm-plate-screws-cut")
    assert "ANOTHER SCREW" not in body
    assert drawing.PIVOT_VIEW_REF in body
    assert _number("pd-vn-transgear-pivot-screw") in body
    assert _number("pd-transgear-pivot-spacer") in body
    assert _number("pd-vn-transgear-pivot-spring") in body
    assert "AS MADE" in body
    texts = drawing._step_text(operating_domain=_unit_operating_domain())["hanger-pivoted"]
    assert len(texts) == 24
    assert "PRESS THE" not in body and "REAMED" not in body
    assert "SLIDES ON BY HAND" not in body
    assert texts[1] == (
        "FIT THE ARM, ITS BORE AND FRONT FACE COATED WITH PASTE WAX, ON IT FROM THE REAR."
    )
    # The dry trial proves the bought screw's shoulder end and the spacer's
    # bore square enough before anything is bonded; its failure takes the
    # step's one renewal, then the inspection (Codjiflo r1 on #3487).
    assert texts[2].startswith("CHECK, DRY: ")
    assert texts[2].endswith(
        "THE SPACER SHOWS NO DAYLIGHT ON THE PLATE AND THE ARM SWINGS FREELY."
    )
    assert "FLAT PLATE COVERED WITH POLYETHYLENE FILM, WHOSE HOLE CLEARS" in texts[2]
    assert "WAXED" not in body
    assert texts[3] == (
        f"IF EITHER FAILS, DO {drawing.sub_step('hanger-pivoted', 20)}-"
        f"{drawing.sub_step('hanger-pivoted', 23)}."
    )
    assert texts[4] == "LIFT THE SPACER OFF THE SHOULDER."
    # One action per sub-step (machinist review 20261124T013305458Z, rule
    # 22): degrease, coat, push on, wipe, clamp; the screw is seated only
    # when the bond has cured.
    assert texts[5].startswith("DEGREASE THE SPACER'S BORE")
    bond = texts[drawing.PIVOT_SPACER_BOND_SUB_STEP]
    assert bond == "COAT THE SPACER'S BORE WITH LOCTITE 638, NOT THE SHOULDER."
    assert texts[7] == (
        "PUSH THE SPACER ON THE SHOULDER UNTIL ITS FRONT FACE IS FLUSH WITH THE SHOULDER'S END."
    )
    assert texts[8] == "WIPE THE SPACER'S FRONT FACE CLEAN."
    clamp = texts[9]
    assert clamp.startswith("AT ONCE, CLAMP THE SCREW DOWN")
    assert clamp.endswith(f"BOTH ON THE PLATE OF {drawing.sub_step('hanger-pivoted', 2)}.")
    assert texts[10].startswith(
        f"WHEN THE BOND HAS CURED {drawing.PIVOT_SPACER_BOND_CURE_H} H, SEAT THE SCREW"
    )
    assert not any(" AND LET THE BOND CURE" in text for text in texts)
    assert all(
        len(lines) <= 6 for lines in drawing._wrapped_sub_steps("hanger-pivoted", texts)
    )
    import pd_transgear_pivot_spacer_spec as spacer_spec

    assert spacer_spec.BOND_GAP[1] <= spacer_spec.LOCTITE_638_GAP_MAX
    # No step shortens the spacer.
    assert not re.search(r"\bFACE (IT|THE SPACER|TO)\b", _unit_step_notes().fitup_steps)


def test_the_fitup_acceptance_prints_the_contract_bands() -> None:
    """§13.2 (8): the seated chain offset, cup-set knob float and minimum
    collar-disc air use their owning specs; R9-71 leaves no head play."""
    expected_float = (
        knob_shaft.END_FLOAT - knob_shaft.END_FLOAT_SET_TOL,
        knob_shaft.END_FLOAT + knob_shaft.END_FLOAT_SET_TOL,
    )
    assert drawing.KNOB_END_FLOAT_RANGE == pytest.approx(expected_float, abs=1e-9)
    body = _step_body("fitup-accepted")
    for text in (
        f"{steps.OFFSET_ACCEPT_TEXT} FORWARD",
        steps.inch_window(expected_float, 3, " TO "),
        steps.COLLAR_DISC_AIR_TEXT,
    ):
        assert text in body, text
    assert "HEAD PLAY" not in body


def test_the_pivot_section_and_its_locator_keep_to_sheet_two_left_field() -> None:
    ring_left, _bottom, _right, ring_top = drawing.SHEET_TWO_RING_LIMITS
    field_right = ring_left
    # The section's balloon ring stays in the field.
    sx, sy = drawing.PIVOT_SECTION_CENTER
    reach = drawing.PIVOT_SECTION_RADIUS + drawing.BALLOON_RING_REACH
    assert sx - reach > 0.018
    assert sx + reach < field_right
    # The locator's circle sits above the ring, its cutting line inside the
    # circle and at least 1 mm past the stack each way along the axis.
    lx, ly = drawing.PIVOT_LOCATOR_CENTER
    lr = drawing.PIVOT_LOCATOR_RADIUS
    assert lx + lr < field_right
    assert ly + lr < ring_top
    assert sy + reach < ly - lr - 0.006
    scale = drawing.PIVOT_LOCATOR_SCALE[0] / drawing.PIVOT_LOCATOR_SCALE[1]
    stack_half = (pivot_screw.HEAD_H - drawing.PIVOT_FRONT_FACE_Y) / 2.0
    assert (stack_half + 1.0) * scale / 1000.0 <= drawing.PIVOT_CUT_HALF < lr
    # VIEW B's label left of the locator's circle, over the ring.
    cx, cy = drawing.PIVOT_LOCATOR_CAPTION_XY
    assert cx > 0.018
    assert cx + len(drawing.PIVOT_LOCATOR_CAPTION) * NOTE_CHAR_WIDTH < lx - lr
    assert cy <= ring_top
    assert cy - NOTE_LINE_PITCH > sy + reach
    # The native section caption under the ring, above the border.
    caption_y = drawing.PIVOT_SECTION_CAPTION_XY[1]
    assert caption_y < sy - reach
    assert caption_y - 2 * NOTE_LINE_PITCH > drawing.SHEET_INNER_BORDER_BOTTOM
    # Both circles frame the screw from its head to the bar's front face.
    assert drawing.PIVOT_FRONT_FACE_Y == pytest.approx(
        -(pivot_screw.SHOULDER_LEN + BAR_DEPTH)
    )
    assert drawing.PIVOT_SECTION_RADIUS == pytest.approx(
        drawing.PIVOT_FRAME_RADIUS_MM
        * drawing.PIVOT_SECTION_SCALE[0]
        / drawing.PIVOT_SECTION_SCALE[1]
        / 1000.0
    )
    assert drawing.PIVOT_VIEW_INSTANCES >= {
        "pd-support-bar-1",
        "pd-vn-transgear-pivot-screw-1",
        "pd-vn-transgear-pivot-spring-1",
    }


def test_each_pivot_section_balloon_points_into_its_own_cut_face() -> None:
    tips = {stem: (side, y, r) for stem, side, y, r in drawing.PIVOT_BALLOON_TIPS}
    assert set(tips) == {
        name.rsplit("-", 1)[0] for name in drawing.PIVOT_VIEW_INSTANCES
    }
    spring, spacer = joints.SPRING, joints.SPACER
    arm_geometry = joints.ARM
    floor = -spring.MODEL_HEIGHT
    arm_front = -(pivot_screw.SHOULDER_LEN - spacer.LENGTH)
    # (y span along the axis, r span off it) of each part's cut face, in the
    # screw's frame, head underside y 0.
    faces = {
        "pd-vn-transgear-pivot-screw": (
            (0.0, pivot_screw.HEAD_H),
            (pivot_screw.SOCKET_AF / math.sqrt(3.0), pivot_screw.HEAD_DIA / 2.0),
        ),
        "pd-vn-transgear-pivot-spring": (
            (floor, 0.0),
            (spring.ID / 2, spring.OD / 2),
        ),
        "pd-transgear-arm": (
            (arm_front, floor),
            (arm_geometry.PIVOT_BORE_DIA / 2, arm_geometry.SPOT_FACE_DIA / 2),
        ),
        "pd-transgear-pivot-spacer": (
            (-pivot_screw.SHOULDER_LEN, arm_front),
            (spacer.BORE_DIA / 2, spacer.OD / 2),
        ),
        "pd-support-bar": (
            (drawing.PIVOT_FRONT_FACE_Y, -pivot_screw.SHOULDER_LEN),
            (assembly.BAR.PIVOT_TAP_CSK_DIA / 2, drawing.PIVOT_FRAME_RADIUS_MM),
        ),
    }
    centre_y = drawing.PIVOT_VIEW_CENTRE_MM[1]
    for stem, (side, y, r) in tips.items():
        (y0, y1), (r0, r1) = faces[stem]
        assert y0 < y < y1, stem
        assert r0 < r < r1, stem
        # Inside the crop circle.
        assert math.hypot(r, y - centre_y) < drawing.PIVOT_FRAME_RADIUS_MM, stem
    # The spring's tip is on its cone's diagonal, inside its thin wall.
    _side, y, r = tips["pd-vn-transgear-pivot-spring"]
    assert y == pytest.approx(floor / 2.0)
    assert r == pytest.approx((spring.ID + spring.OD) / 4.0)
    # Down the stack the tips alternate sides.
    order = sorted(tips.values(), key=lambda tip: -tip[1])
    assert [side for side, _y, _r in order] == ["left", "right", "left", "right", "left"]


def test_pivot_section_balloon_columns_keep_order_and_pitch() -> None:
    pitch = drawing.PIVOT_BALLOON_PITCH
    assert drawing.spread_balloon_column([0.05, 0.0, -0.05], pitch) == [
        pytest.approx(v) for v in (0.05, 0.0, -0.05)
    ]
    spread = drawing.spread_balloon_column([0.010, 0.008, 0.007], pitch)
    assert all(a - b >= pitch - 1e-12 for a, b in zip(spread, spread[1:]))
    assert sum(spread) == pytest.approx(0.025)
    with pytest.raises(ValueError):
        drawing.spread_balloon_column([0.0, 0.01], pitch)
    # Every balloon of either column stays inside the section's ring reach.
    scale = drawing.PIVOT_SECTION_SCALE[0] / drawing.PIVOT_SECTION_SCALE[1] / 1000.0
    sx, sy = drawing.PIVOT_SECTION_CENTER
    centre_y = drawing.PIVOT_VIEW_CENTRE_MM[1]
    reach = drawing.PIVOT_SECTION_RADIUS + drawing.BALLOON_RING_REACH
    assert drawing.PIVOT_SECTION_RADIUS + drawing.PIVOT_BALLOON_GAP < reach
    for flip in (1.0, -1.0):
        for column in ("left", "right"):
            ys = sorted(
                (
                    sy + flip * (y - centre_y) * scale
                    for _stem, side, y, _r in drawing.PIVOT_BALLOON_TIPS
                    if side == column
                ),
                reverse=True,
            )
            for balloon_y in drawing.spread_balloon_column(ys, pitch):
                assert abs(balloon_y - sy) < reach - 0.005


def test_the_actual_collar_disc_overlap_is_checked_before_final_platen_installation() -> None:
    """A static F-to-disc setting cannot certify all loaded overlapping patches."""
    inspected = _step_body("collar-disc-air-inspected")
    assert (
        "WITH THE ARM LATCHED, REMOVE THE LOCKS AND LIFT OFF THE PLATEN." in inspected
    )
    assert "TRIAL PLATEN" not in inspected
    assert f"({disc.TEETH / knob_shaft.TEETH:g} KNOB TURNS)" in inspected
    assert f"CLEARANCE {steps.COLLAR_DISC_AIR_TEXT}" in inspected
    assert "REFIT THE PLATEN PER " in inspected
    # The feeler carries the MHA-PD-10 step face (Q1 C), the MHA-PD-17
    # spigot end ⊥ .001 (owner ruling 2026-11-08 (Pedro), #2144 item 3.2) and
    # the MHA-PD-18 pin bore S ⊥ Ø.001 A (owner ruling 2026-11-08 (Pedro),
    # #2144 item 4.1): the remedy re-faces only the step, setting hub and
    # disc back, which also recovers the air a tilted S closed.
    flat = " ".join(inspected.split())
    assert (
        f"THE {_number('pd-transgear-disc-hub')} SPIGOT END SEATS ON IT, SO HUB AND "
        "DISC SET BACK BY THAT AMOUNT." in flat
    )
    assert "RE-FACE THE " + _number("pd-transgear-disc-hub") not in flat
    # The feeler check only passes or fails, so the shortfall is read before
    # the stack comes off, and the re-face takes the minimum less that reading
    # (integration review, run 20261109T062834910Z).
    texts = drawing._step_text(operating_domain=_unit_operating_domain())[
        "collar-disc-air-inspected"
    ]
    feeler = steps.COLLAR_DISC_AIR_TEXT.split()[0]
    assert texts[2].startswith(f"CHECK: A {feeler} FEELER ENTERS ")
    # #2629: a pass exit to the platen's refit leads the re-face branch.
    assert texts[3] == (
        f"IF {drawing.sub_step('collar-disc-air-inspected', 2)} PASSES, SKIP "
        f"{drawing.sub_step('collar-disc-air-inspected', 4)}-"
        f"{drawing.sub_step('collar-disc-air-inspected', 15)}."
    )
    assert texts[4] == "READ THE THICKEST FEELER ENTERING ALL ROUND (NONE: READ 0)."
    assert texts[16].startswith("REFIT THE PLATEN PER ")
    read = drawing.sub_step("collar-disc-air-inspected", 4)
    assert (
        f"RE-FACE THE {_number('pd-transgear-feed-pinion')} STEP FACE SQUARE BY "
        f"{feeler} LESS THE {read} READING;" in flat
    )
    # #2418: the cut is driven by the sleeve's rear face on the stub's
    # shoulder, loaded by the tailstock, not by a Ø1/8 mandrel's friction.
    setup = [
        flat.index(word)
        for word in ("STUB MANDREL", "SHOULDER", "TAILSTOCK CENTRE", "RE-FACE THE ")
    ]
    assert setup == sorted(setup)
    assert "BETWEEN CENTRES" not in flat
    assert "READ SHORT" not in flat
    assert texts[-4] == (
        f"REPEAT {drawing.sub_step('collar-disc-air-inspected', 1)}-"
        f"{drawing.sub_step('collar-disc-air-inspected', 2)}."
    )
    # #3107: a still-short air is read and re-faced again, never refitted.
    assert texts[-3] == (
        f"IF {drawing.sub_step('collar-disc-air-inspected', 2)} STILL FAILS, REPEAT FROM "
        f"{read}."
    )
    assert texts[-1].startswith(
        f"IF {drawing.sub_step('collar-disc-air-inspected', 9)} RE-FACED THE STEP, REPEAT "
    )
    assert steps.COLLAR_DISC_AIR_MIN == collar.COLLAR_DISC_AIR_MIN
    assert steps.COLLAR_DISC_AIR_TEXT in _step_body("fitup-accepted")
    keys = (
        "hook-pin-hole-match-drilled",
        "collar-shoulder-seated",
        "collar-disc-air-inspected",
        "fitup-accepted",
        "chain-closed",
    )
    positions = [steps.step_number(key) for key in keys]
    assert positions == sorted(positions)


def test_one_disc_cycle_reference_travel_is_one_feed_revolution() -> None:
    """The disc and feed rotate together; reducer input turns are not feed turns."""
    knob_turns_per_disc = disc.TEETH / knob_shaft.TEETH
    crank_turns_per_disc = (
        knob_turns_per_disc * sprocket.KNOB_TEETH / sprocket.CRANK_TEETH
    )
    assert (
        crank_turns_per_disc * paper_geometry.NET_RACK_TRAVEL_PER_CRANK_REV
    ) == pytest.approx(math.pi * feed_pinion.PITCH_DIA)


def test_the_knob_bush_is_bonded_and_reamed_before_the_plate_is_set() -> None:
    """#2425 (owner ruling 2026-11-20): the MHA-PD-28 bush goes into
    MHA-PD-19 from face A to its shoulder, accepted on its own feeler, and
    is reamed through once fixed, before the plate goes on the arm; its
    bore is DETAIL K's knob bore N.  It is bonded with LOCTITE 638 (owner
    question Q8b, option B, held for the owner)."""
    texts = drawing._step_text(operating_domain=_unit_operating_domain())["pin-pressed"]
    bush = _number("pd-transgear-knob-bush")
    plate = _number("pd-transgear-arm-plate")
    # Owner ruling 2026-11-24, fit audit question 4: the pin is bonded
    # first, one action per sub-step, its check and remedy apart (rule 22).
    assert drawing.PIN_BOND_COMPOUND == cluster_pin.RETAINING_COMPOUND
    bond = drawing.PIN_BOND_SUB_STEP
    assert texts[bond].startswith(f"COAT THE SHANK UNDER THE HEAD, NOT THE HOLE, WITH {drawing.PIN_BOND_COMPOUND}")
    assert texts[2] == (
        "PUSH THE PIN THROUGH THE HOLE FROM THE REAR, TURNING IT, UNTIL ITS HEAD SEATS ON THE ARM."
    )
    assert texts[4] == "CLAMP THE HEAD ON THE ARM'S REAR FACE."
    assert texts[5] == (
        f"LET THE BOND CURE {drawing.PIN_BOND_CURE_H} H BEFORE ANYTHING IS FITTED ON "
        "THE PIN."
    )
    assert texts[6].startswith("CHECK: ") and texts[7] == "IF IT MOVES, PULL THE PIN."
    assert texts[8] == (
        "IF PULLED, CLEAN THE PIN AND THE HOLE AND REPEAT "
        f"{drawing.sub_step('pin-pressed', 0)}-{drawing.sub_step('pin-pressed', 6)}."
    )
    assert not any("PRESS THE" in text and "PIN" in text.split("BUSH")[0] for text in texts[:9])
    note = drawing.BOM_EXPENDABLES_NOTE.replace("\n", " ")
    # One consumables statement per compound names every step that uses it.
    assert (
        "LOCTITE 638 AT "
        + ", ".join(drawing.sub_step(key, index) for key, index in drawing.LOCTITE_638_SUB_STEPS)
        + f"; CURE {drawing.PIN_BOND_CURE_H} H."
    ) in note
    assert (drawing.sub_step("pin-pressed", bond), drawing.sub_step(
        "pin-pressed", drawing.BUSH_BOND_SUB_STEP
    ), drawing.sub_step(
        "hanger-pivoted", drawing.PIVOT_SPACER_BOND_SUB_STEP
    )) == ("11B", "11L", "15G")
    assert (
        drawing.PIN_BOND_CURE_H
        == drawing.PIVOT_SPACER_BOND_CURE_H
        == drawing.KNOB_CUP_BOND_CURE_H
    )
    all_steps = drawing._step_text(operating_domain=_unit_operating_domain())
    # Every step that names the compound, or sends a part to DETAIL H's bond
    # note, is in the consumables rows; nothing else is.
    assert {
        drawing.sub_step(key, index)
        for key, rows in all_steps.items()
        for index, row in enumerate(rows)
        if "LOCTITE" in row or "BOND IT PER THE BOND NOTE" in row
    } == set(re.findall(r"\b\d+[A-Z]\b", note[note.index("LOCTITE") :]))
    # The bush's bond: the pin's bullets (rule 23), one action a sub-step.
    assert texts[9] == (
        f"DEGREASE THE {bush} BUSH'S STUB AND THE {plate} PLATE'S REAMED HOLE."
    )
    assert texts[drawing.BUSH_BOND_SUB_STEP] == (
        f"COAT THE STUB, NOT THE HOLE, WITH {drawing.PIN_BOND_COMPOUND}."
    )
    assert texts[11] == (
        f"PUSH THE BUSH, STUB FIRST, INTO THE PLATE FROM ITS FRONT FACE (FACE A ON "
        f"{plate}), TURNING IT, UNTIL ITS SHOULDER SEATS."
    )
    assert texts[12] == (
        "WIPE ALL COMPOUND OFF FACE A AND OFF THE STUB AND THE PLATE BEHIND IT."
    )
    assert texts[13] == "CLAMP THE SHOULDER ON FACE A."
    # A leaf of the shop's set at three places, the coarsest that closes the
    # collar-to-disc air (machinist review 20261124T013305458Z, rule 4).
    feeler = disc.inch_text(knob_bush.SHOULDER_SEAT_GAP_MAX, 3)
    assert feeler == ".002"
    # Both acceptances cite their setting-table rows (machinist review r13).
    assert texts[14] == (
        f"CHECK: A {feeler} FEELER DOES NOT ENTER UNDER THE SHOULDER "
        f"{drawing.row_cite('bush-seated')}."
    )
    # A check and its remedy are separate sub-steps (rule 22).
    # A first failure is clamped home and checked again; a second renews the
    # pair (codjiflo review round 2).
    assert texts[15] == (
        f"IF IT ENTERS, CLAMP THE SHOULDER AGAIN AND REPEAT "
        f"{drawing.sub_step('pin-pressed', 14)}."
    )
    assert texts[16] == (
        f"IF IT STILL ENTERS, REPEAT FROM {drawing.sub_step('pin-pressed', 9)} WITH A "
        f"NEW {plate} PLATE AND {bush} BUSH."
    )
    assert texts[17] == (
        f"LET THE BOND CURE {drawing.PIN_BOND_CURE_H} H BEFORE THE BORE IS REAMED."
    )
    assert not any("PRESS" in text for text in texts[9:])
    # The in-place ream names its mate and fit; it prints the reamer's size
    # and no band, and the journal is turned to the bore (rule 4, fit audit
    # 2026-11-23).
    assert texts[18].endswith(
        f"THRU, A RUNNING FIT ON THE {_number('pd-transgear-knob-shaft')} JOURNAL, "
        f"WHICH IS TURNED TO IT {drawing.row_cite('bush-reamed')}."
    )
    ream = steps.inch_text(knob_bush.BORE_DIA, 4)
    assert ream == ".2490"
    assert texts[18].startswith(f"REAM THE BUSH'S BORE \u00d8{ream} THRU, ")
    assert len(texts) == 19
    assert steps.step_number("pin-pressed") < steps.step_number("arm-plate-located")
    located = _step_body("arm-plate-located")
    assert f"{bush} KNOB BORE {drawing.KNOB_BORE_LETTER} IS STILL TRUE" in located
    assert f"INTO THE {bush} BUSH FROM THE FRONT" in located
    assert drawing.KNOB_SETTING_LEGEND[drawing.KNOB_BORE_LETTER] == f"{bush} KNOB BORE"
    assert "pd-transgear-knob-bush-1" in drawing.KNOB_SETTING_INSTANCES
    # Every later renewal of the plate renews its bonded bush.
    for key in ("arm-plate-fitted", "hanger-pivoted", "fitup-mesh-remedied"):
        body = _step_body(key)
        assert body.count(f"{plate} PLATE,") == body.count(f"{plate} PLATE, {bush} BUSH,"), key


def test_the_rear_cup_is_faced_bonded_and_screwed_and_the_nut_seats_on_the_faced_pilot() -> None:
    """#2425 (owner ruling 2026-11-20): the cup's front is faced to the
    journal's stand-out less the end float, its pilot bonded on the journal
    end with LOCTITE 641 and the MHA-PD-VN-71 screw seated on the axis; the
    float is accepted on feelers at the bush's rear face. No pin, no
    match-drill. R9-70's wheel-float fit remains; the front drive is a true D."""
    texts = drawing._step_text(operating_domain=_unit_operating_domain())["knob-stack-fitted"]
    knob = _step_body("knob-stack-fitted")
    s = drawing.sub_step
    float_text = disc.inch_text(knob_shaft.END_FLOAT, 3)
    assert texts[1] == (
        f"PUSH THE SHAFT REARWARD, THE {drawing.KNOB_PINION} ON THE RING, THE RING ON "
        "THE BUSH'S HUB FACE."
    )
    assert texts[2].startswith("READ THE JOURNAL'S STAND-OUT BEHIND THE BUSH'S REAR FACE")
    assert (
        f"PILOT DEPTH READS {float_text} LESS THAN {s('knob-stack-fitted', 2)}'S STAND-OUT"
        in texts[3]
    )
    assert texts[4].startswith("IF THE PILOT ENDS SHALLOWER THAN THAT, MAKE A NEW")
    # Rule 23's bond bullet: grade by number, degrease, the compound on the
    # journal (the pin), not the blind pilot, kept off the running land, set
    # at once, the cure before load, and a bench acceptance.
    assert texts[5].startswith("DEGREASE ")
    bond = texts[drawing.KNOB_CUP_BOND_SUB_STEP]
    assert "LOCTITE 641" in bond and "NOT THE CUP'S BLIND PILOT" in bond
    assert "OFF THE JOURNAL IN THE BUSH" in bond
    assert texts[7].startswith("AT ONCE, ")
    assert texts[8].startswith(f"SEAT THE {_number('pd-vn-transgear-knob-cup-screw')} SCREW")
    assert f"CURE {drawing.KNOB_CUP_BOND_CURE_H} H BEFORE" in texts[10]
    assert texts[11].startswith(f"CHECK: SHAFT REARWARD AS {s('knob-stack-fitted', 1)}")
    assert (
        f"THE CUP'S FRONT AND THE BUSH'S REAR FACE READS {drawing.KNOB_END_FLOAT_WINDOW} "
        "ON FEELERS"
    ) in texts[11]
    assert drawing.KNOB_END_FLOAT_WINDOW == ".006 TO .010"
    assert texts[12] == "CHECK: SHAFT HELD, THE CUP DOES NOT TURN OR SLIDE ON THE JOURNAL BY HAND."
    assert texts[13] == (
        f"IF BOTH CHECKS PASS, SKIP {s('knob-stack-fitted', 14)}-{s('knob-stack-fitted', 17)}."
    )
    # The cured bond lets go only hot (rule 23); the heat is kept off the
    # bush's oil (codjiflo review, #2425).  The screw comes out in its own
    # sub-step, and the later strips cite the pair (machinist review r10).
    assert texts[14] == f"UNSCREW THE {_number('pd-vn-transgear-knob-cup-screw')} SCREW."
    assert texts[15] == (
        f"PULL THE {_number('pd-transgear-knob-cup')} CUP OFF THE JOURNAL HOT, ABOUT "
        f"250\u00b0C, THE HEAT KEPT OFF THE {_number('pd-transgear-knob-bush')} BUSH'S OIL."
    )
    cited = (
        f"TAKE THE {_number('pd-transgear-knob-cup')} CUP OFF AS "
        f"{s('knob-stack-fitted', 14)}-{s('knob-stack-fitted', 15)}."
    )
    every = drawing._step_text(operating_domain=_unit_operating_domain())
    # Steps 28 and 33, and the rear-faced collar's renewal (29).
    assert sum(cited in row for rows in every.values() for row in rows) == 3
    assert sum("250\u00b0C" in row for rows in every.values() for row in rows) == 1
    for word in ("MATCH-DRILL", "PIN (PRESS FIT)", "FEELER AT THE PLATE"):
        assert word not in knob, word
    assert "pd-vn-transgear-knob-cup-pin" not in drawing.BOM_PART_NUMBERS
    assert "cup-pin-hole" not in drawing.SETTING_ROW_KEYS
    note = drawing.BOM_EXPENDABLES_NOTE.replace("\n", " ")
    assert (
        f"LOCTITE 641 AT {s('knob-stack-fitted', drawing.KNOB_CUP_BOND_SUB_STEP)}; "
        f"CURE {drawing.KNOB_CUP_BOND_CURE_H} H."
    ) in note
    assert drawing.PIVOT_SPACER_BOND_CURE_H == drawing.KNOB_CUP_BOND_CURE_H
    # Each sub-step prints in at most six lines (rule 22).
    assert all(
        len(lines) <= 6 for lines in drawing._wrapped_sub_steps("knob-stack-fitted", texts)
    )
    seq = steps.SEQUENCE
    assert seq.index("pilot-faced-to-fit") < seq.index("knob-stack-fitted")
    assert seq.index("pilot-faced-to-fit") < seq.index("collar-shoulder-seated")
    assert f"{collar.PILOT_PROUD_TEXT} PROUD" in _step_body("pilot-faced-to-fit")
    seated = _step_body("collar-shoulder-seated")
    assert "COLLAR'S PILOT" in seated
    # The nut is a static clamp (the D-flat and dowels drive): rule 23's
    # U-MHA-PD-13-no-lock holds only while nobody turns it to drive.
    assert "NEVER TURN IT TO DRIVE" in seated


def test_the_knob_and_its_grip_are_defined_and_service_turns_the_crank() -> None:
    knob = _step_body("knob-stack-fitted")
    chain_step = steps.step_number("chain-closed")
    assert f"TURN THE KNOB ONLY BY THE COLLAR UNTIL STEP {chain_step}" in knob
    assert steps.SEQUENCE.index("knob-stack-fitted") < steps.SEQUENCE.index(
        "hanger-meshed"
    )
    assert _step_body("chain-run-accepted").startswith("TURN THE CRANK")
    for key in steps.SEQUENCE[chain_step - 1 :]:
        assert "TURN THE KNOB" not in _step_body(key), key


def test_the_fitted_collar_rear_face_reacts_on_the_actual_gear_shoulder() -> None:
    faced = _step_body("collar-rear-faced-to-fit")
    assert (
        f"IN {_number('pd-transgear-drive-collar')}'S FITTED LIMITS"
    ) in faced
    seated = _step_body("collar-shoulder-seated")
    assert "COLLAR ON THE SHAFT, ITS PIN ON THE D-FLAT" in seated
    assert f"{_number('pd-transgear-knob-shaft')} PINION'S FRONT FACE" in seated
    assert "ON THE DRIVE DOWELS" in seated
    assert collar.BODY_REAR_FACE_FROM_F == 0.0
    assert collar.LENGTH_FITTED_MIN <= collar.LENGTH <= collar.LENGTH_FITTED_MAX
    assert not {"collar-gap-measured", "collar-pinned"} & set(steps.SEQUENCE)


def test_the_fitup_steps_and_the_collar_note_share_facing_setting_and_stud_cut() -> None:
    """R9-30's shared fit phrases now describe shoulder seating, not core drilling."""
    note = " ".join(collar.FIT_UP_NOTE.split())
    phrase = collar.FIT_UP_OFFSET_SET_TEXT
    assert phrase in _step_body("collar-rear-faced-to-fit")
    assert phrase in note
    # The stud cut prints the collar spec's own window.
    low, high = (steps.inch_text(v, 3) for v in collar.STUD_CUT_BELOW_RIM)
    assert f"{low} TO {high} BELOW THE RIM" in _step_body("stud-end-cut")
    for text in drawing.sheet_texts(_unit_step_notes()):
        assert "THROUGH THE CORE" not in text
        assert "SPRING PIN IN THE SLOT" not in text
        assert "SLOTTED SHIM" not in text
    assert not hasattr(steps, "CLAMP_SLEEVE_OD")
    assert not hasattr(steps, "CLAMP_SLEEVE_ID")


def test_the_collar_is_faced_and_shoulder_seated_before_stud_cut_and_acceptance() -> None:
    order = [
        "hook-pin-hole-match-drilled",
        "fitup-pose-set",
        "collar-rear-faced-to-fit",
        "collar-shoulder-seated",
        "stud-end-cut",
        "collar-disc-air-inspected",
        "fitup-accepted",
    ]
    numbers = [steps.step_number(key) for key in order]
    assert numbers == sorted(numbers)
    assert steps.SEQUENCE.index("fitup-accepted") == len(steps.SEQUENCE) - 3
    assert steps.step_number("collar-pins-pressed") < steps.step_number(
        "knob-stack-fitted"
    )


def test_the_cluster_float_and_pin_bands_print_their_spec_ranges() -> None:
    accepted = _step_body("fitup-accepted")
    assert f"RING GAP READS {drawing.CLUSTER_FLOAT_VIEW_NAME}" in accepted
    assert "DISC TURNS FREE" in accepted
    # Each press step prints its setting detail's limits: the part specs'
    # window rounded inward to the .001 grid and no narrower, so no
    # conforming press-to-floor build is refused (Codjiflo, PR #3029).
    for key, band, bounds in (
        (
            "collar-pins-pressed",
            drawing.setting_details.DRIVE_PIN_PROUD_BAND,
            drive_pin.PROUD_RANGE,
        ),
        (
            "latch-pin-pressed",
            drawing.setting_details.LATCH_PROUD_BAND,
            joints.LATCH_PIN_PROUD_RANGE,
        ),
    ):
        assert bounds[0] - 1e-9 <= band[0] < band[1] <= bounds[1] + 1e-9
        assert band[0] - bounds[0] < 0.0254 and bounds[1] - band[1] < 0.0254
        assert f"{steps.inch_window(band, 3, ' TO ')} PROUD" in _step_body(key)


def test_an_over_pressed_or_slipping_latch_dowel_is_remade_with_its_arm() -> None:
    """#3124 / Codjiflo #3127: the dowel is pressed to height and the press
    is permanent (MHA-PD-18 RV-03), so a dowel set under the window stays in
    the arm it scraps; the remedy remakes both, as the later restarts do.
    A dowel that slides into the reamed hole by hand is a slip fit of
    unknown clearance in an arm that does not yet carry DETAIL K's
    jig-boring (#2497 allows compound only after it), so it remakes both
    too, as the arm's traveler rejects the arm (Codjiflo r2 on #3486).  The
    facts are asserted, not the wording (AGENTS.md, assembly data)."""
    texts = drawing._step_text(operating_domain=_unit_operating_domain())
    press, *remedies = (" ".join(row.split()) for row in texts["latch-pin-pressed"])
    low = steps.inch_text(drawing.setting_details.LATCH_PROUD_BAND[0], 3)
    assert drawing.detail_cite("latch-pin-pressed") in press
    remedy = " ".join(remedies)
    for fact in (
        "SLIDES IN BY HAND",
        f"UNDER {low}",
        f"NEW {_number('pd-transgear-arm')} ARM",
        f"{_number('pd-vn-transgear-latch-pin')} DOWEL",
        f"REPEAT FROM STEP {steps.step_number('latch-pin-pressed')}",
    ):
        assert fact in remedy, fact
    assert "BOND" not in remedy and "LOCTITE" not in remedy
    assert ("latch-pin-pressed", 1) not in drawing.BOND_NOTE_SUB_STEPS


def test_the_cluster_is_shimmed_to_view_e_after_it_is_hung() -> None:
    """#2124: the ring gap is set with shims under the rear bushing to VIEW
    E's model dimension; the step prints no value, and the window passes
    every shimmed cluster and holds the floor."""
    import pd_paper_drive_cluster_float_spec as cluster_float

    assert steps.step_number("disc-cluster-hung") + 1 == steps.step_number(
        "disc-cluster-shimmed"
    )
    shimmed = _step_body("disc-cluster-shimmed")
    assert drawing._N["pd-vn-transgear-cluster-shim"] in shimmed
    assert drawing._N["pd-transgear-rear-bushing"] in shimmed
    assert drawing.CLUSTER_FLOAT_VIEW_NAME in shimmed and "FEELER" in shimmed
    # Codjiflo (#2124): the gap is read with the ring on the groove's load
    # wall, where transgear_cluster_fit puts it, not loose in its play.
    assert "RING ON ITS GROOVE'S FRONT WALL" in " ".join(shimmed.split())
    # DETAIL E's window prints there only; the step's one value at its floor
    # is the bare gap's range below.
    assert f"{disc.inch_text(cluster_fit.END_FLOAT_MIN, 3)} +" not in shimmed
    # Codjiflo and machinist review (#2124): the step gives the fit-up's
    # most shims, and the BOM's QTY is the whole kit, the stack's nominal
    # shims plus the spares the model stores in the spare sprocket's bore.
    low_count, high_count = cluster_fit.SHIM_COUNT_RANGE
    assert f"UP TO {high_count} IN ALL" in " ".join(shimmed.split())
    # Rounds 9-10: the gap is corrected either way, one action a sub-step. The
    # bare stack is never under the window (transgear_cluster_fit), so an
    # under gap is an overshoot and one shim comes off; shims target the
    # window's middle. The check is the reading alone, and the sub-step after
    # it names the reading it passes on (integration review at 8fb7fb46f7).
    flat = " ".join(shimmed.split())
    view = drawing.CLUSTER_FLOAT_VIEW_NAME
    next_step = steps.step_number("disc-cluster-shimmed") + 1
    assert "NEVER READS UNDER" not in flat
    assert f"THE GAP READS {view} (SHEET " in flat
    assert f"IF THE GAP READS {view}, GO TO STEP {next_step}." in flat
    assert "IF IT DOES" not in flat
    assert "IF IT READ UNDER, TAKE ONE SHIM OFF." in flat
    middle = disc.inch_text(sum(cluster_fit.RING_FLOAT_RANGE) / 2.0, 3)
    shim = disc.inch_text(cluster_fit.SHIM.THICKNESS, 3)
    assert f"ONE PER {shim} OVER {middle} TO THE NEAREST" in flat
    assert cluster_fit.RING_FLOAT_RANGE[0] < sum(cluster_fit.RING_FLOAT_RANGE) / 2.0
    assert cluster_fit.UNSHIMMED_FLOAT_RANGE[0] >= cluster_fit.RING_FLOAT_RANGE[0]
    assert high_count <= cluster_fit.SHIM_COUNT_MAX
    # The sheet shows the loop closes (review of the DETAIL E rename): the
    # bare gap's printed range, the shim's thickness, and that range's floor
    # in the window while its top, less the most shims at their thinnest,
    # reaches the window.
    assert "(WITH NO SHIMS IT READS .009 TO .031)." in flat
    assert (
        f"ADD {disc.inch_text(cluster_fit.SHIM.THICKNESS, 3)} "
        f"{drawing._N['pd-vn-transgear-cluster-shim']} SHIMS" in flat
    )
    bare_low, bare_high = 0.009 * 25.4, 0.031 * 25.4
    assert bare_low <= cluster_fit.UNSHIMMED_FLOAT_RANGE[0]
    assert cluster_fit.UNSHIMMED_FLOAT_RANGE[1] <= bare_high
    assert bare_low >= cluster_fit.RING_FLOAT_RANGE[0] - 1e-9
    assert bare_high - high_count * cluster_fit.SHIM.THICKNESS_MIN <= cluster_fit.RING_FLOAT_RANGE[1]
    description = drawing.BOM_DESCRIPTIONS["pd-vn-transgear-cluster-shim"]
    assert "SUPPLY" not in description
    assert drawing.TRANSGEAR_QUANTITIES["pd-vn-transgear-cluster-shim"] == (
        cluster_fit.SHIM_COUNT_MAX
    )
    assert len(assembly.CLUSTER_SHIM_Z0S) == cluster_fit.SHIM_COUNT_MODEL
    spares = cluster_fit.SHIM_COUNT_MAX - cluster_fit.SHIM_COUNT_MODEL
    assert len(assembly.SPARE_SHIM_Y0S) == len(drawing.SPARE_SHIM_INSTANCES) == spares
    stacked = {
        name
        for name in drawing.TRANSGEAR_INSTANCES
        if name.startswith("pd-vn-transgear-cluster-shim-")
    }
    assert len(stacked) == cluster_fit.SHIM_COUNT_MODEL
    assert not stacked & drawing.SPARE_SHIM_INSTANCES
    # In the spare's bore, clear of its wall.
    import pd_transgear_removable_spec as removable
    import pd_vn_transgear_cluster_shim_spec as shim

    assert shim.OD < removable.BORE_DIA
    low = cluster_float.NOMINAL_MM
    high = low + cluster_float.TOLERANCE_MM[1]
    assert cluster_float.TOLERANCE_MM[0] == 0.0
    assert low == cluster_fit.END_FLOAT_MIN == cluster_fit.RING_FLOAT_RANGE[0]
    assert (
        cluster_fit.RING_FLOAT_RANGE[1] <= high < cluster_fit.RING_FLOAT_RANGE[1] + 0.0254
    )
    assert cluster_float.DRAWING_DIMENSIONS == {
        cluster_float.FEATURE: {cluster_float.DIMENSION}
    }


def test_view_e_text_stands_forward_of_the_ring_over_the_bare_pin() -> None:
    """The ring gap's text sits ahead of the ring (machine -Z), above the
    ring's rim, where only the pin's shank runs below it: no bushing outline,
    chamfer or extension line crosses it.  The circle still frames it."""
    import pd_paper_drive_cluster_float_spec as cluster_float
    import pd_vn_transgear_retaining_ring_spec as ring

    _, y, z = cluster_float.TEXT_POINT
    assert z < cluster_fit.RING_FRONT_Z - 2.0
    assert y - cluster_float.AXIS_XY[1] > ring.OD / 2.0 + 0.5
    reach = math.dist((y, z), drawing.CLUSTER_FLOAT_MODEL_CENTRE[1:])
    assert reach * drawing._CLUSTER_FLOAT_M_PER_MM < drawing.CLUSTER_FLOAT_RADIUS


def test_nothing_in_the_disc_cluster_is_faced_at_assembly() -> None:
    for key in (
        "hub-faced-to-nose",
        "front-bushing-faced-to-fit",
        "rear-bushing-faced-to-fit",
    ):
        assert key not in steps.SEQUENCE
    assert "pilot-faced-to-fit" in steps.SEQUENCE
    assert "collar-rear-faced-to-fit" in steps.SEQUENCE
    assert "collar-disc-air-inspected" in steps.SEQUENCE
    hub = drawing._N["pd-transgear-disc-hub"]
    bushings = (
        drawing._N["pd-transgear-front-bushing"],
        drawing._N["pd-transgear-rear-bushing"],
    )
    for key in steps.SEQUENCE:
        body = _step_body(key)
        assert "BLANK" not in body or not any(n in body for n in bushings), key
        if "FACE" not in body:
            continue
        for number in (hub, *bushings):
            assert f"FACE THE {number}" not in body, key
    hung = _step_body("disc-cluster-hung")
    assert "OIL THE PIN" in hung
    for number in bushings:
        assert number in hung
    assert f"TRAPPING THE {drawing._N['pd-transgear-disc-hub']} HUB" in hung
    accepted = _step_body("fitup-accepted")
    assert f"STEP {steps.step_number('collar-disc-air-inspected')}" in accepted
    assert steps.step_number("disc-cluster-assembled") + 1 == steps.step_number(
        "disc-taps-transferred"
    )


def test_the_disc_is_centred_to_its_running_bore_before_transfer_and_match_mark() -> None:
    """Pilot fit and a free span do not centre the assembled tooth spaces."""
    transferred = _step_body("disc-taps-transferred")
    # #2418: a stub fitted to the actual bore in the chuck, not a Ø1/8
    # mandrel between centres; the trued disc is clamped before the
    # off-axis spots are taken off the lathe and is read back on the stub.
    for word in ("STUB MANDREL", "LATHE CHUCK", "SLIDING FIT"):
        assert word in transferred
    assert f"{drawing._N['pd-transgear-feed-pinion']} BORE" in transferred
    assert "BETWEEN CENTRES" not in transferred
    # Owner ruling 2026-11-20 (Pedro), #2665: the disc is centred on its
    # O.D., then the pin samples 12 spaces about evenly round it.
    assert "TAP THE DISC CENTRAL UNTIL THE O.D. READS" in " ".join(transferred.split())
    strides = drawing.DISC_TIR_SAMPLE_STRIDES
    # The two strides go once round all the teeth.
    assert any(
        a * strides[0] + (drawing.DISC_TIR_SAMPLE_SPACES - a) * strides[1] == disc.TEETH
        for a in range(1, drawing.DISC_TIR_SAMPLE_SPACES)
    )
    assert (
        f"\u00d8{disc.inch_text(disc.TOOTH_SPACE_GAUGE_PIN_DIA_MM, 3)} GAUGE PIN IN "
        f"{drawing.DISC_TIR_SAMPLE_SPACES} SPACES, EVERY {strides[0]}TH OR {strides[1]}TH"
    ) in " ".join(transferred.split())
    tir = disc.inch_text(disc.inch_floor_mm(disc.TOOTH_SPACE_RUNOUT_TIR_MM, 3), 3)
    assert f"{tir} TIR MAX" in transferred
    for method in ("CERTIFIED", "RUNNING-BORE", "INDICATOR STATION", "INSPECTION"):
        assert method not in transferred
    # Codjiflo P3 on 353fd41a36: the sleeve, held between the stub's
    # shoulder and the tailstock, takes the truing taps, and the stub stays
    # chucked while the work is off it.
    ordered_actions = (
        "SHOULDER",
        "TAILSTOCK CENTRE",
        "TAP THE DISC CENTRAL",
        "CLAMP THE DISC TO THE HUB FLANGE",
        "OFF THE MANDREL",
        "IN THE CHUCK",
        "SPOT-DRILL THE DISC",
        "SCREWS.",
        "REMOVE THE CLAMPS",
        "REFIT THE SLEEVE",
        f"IN {drawing.DISC_TIR_SAMPLE_SPACES} SPACES",
        "MATCH-MARK DISC AND HUB",
    )
    locations = [transferred.index(action) for action in ordered_actions]
    assert locations == sorted(locations)
    assert "OD RUNOUT" not in transferred
    # threaded-joint-retention.md: pd-paper-drive/disc-screws is a static clamp, no lock.
    assert "LOCK" not in transferred


def test_the_plate_screws_are_cut_to_the_limit_the_lock_sweep_clears() -> None:
    """R9-44: cut off the mechanism, then refit the same screws before the
    hanger is pivoted."""
    order = ["arm-plate-fitted", "arm-plate-screws-cut", "hanger-pivoted"]
    fitted, cut, pivoted = (steps.step_number(key) for key in order)
    assert cut == fitted + 1 and cut < pivoted
    # The pin is pressed before the plate is set (#2417), so nothing goes in
    # between: the screws are back in before the hanger is pivoted.
    assert cut + 1 == pivoted
    body = _step_body("arm-plate-screws-cut")
    assert body.startswith(f"REMOVE BOTH {_number('pd-vn-transgear-arm-plate-screw')} SCREWS")
    assert "REFIT THE SAME SCREWS IN THE SAME HOLES" in body
    limit = f"FLUSH TO {disc.inch_text(joints.PLATE_SCREW_CUT_PROUD_MAX, 3)} PROUD"
    assert limit in body
    assert joints.PLATE_SCREW_TIP_PROUD_MAX == joints.PLATE_SCREW_CUT_PROUD_MAX
    # Positive control: the fit step itself does not mention the cut.
    assert "CUT" not in _step_body("arm-plate-fitted")


def _spare_world_point(monkeypatch, local):
    """Exercise the production row-vector transform without a COM connection."""
    transform = [value for row in assembly.ROT_X_NEG90 for value in row]
    transform += [value / 1000.0 for value in assembly.SPARE_GEAR_POS]
    transform += [1.0, 0.0, 0.0, 0.0]
    adapter = object()

    def component_transform(actual_adapter, name):
        assert actual_adapter is adapter
        assert name == "pd-transgear-removable-3"
        return transform

    monkeypatch.setattr(_assembly, "component_transform", component_transform)
    return _assembly.world_point(adapter, "pd-transgear-removable-3", local)


def test_spare_sprocket_transformed_underside_contacts_base_deck(monkeypatch):
    # The spec's plate is local Z=0..PLATE, identical in all tooth configs.
    underside = _spare_world_point(monkeypatch, [0.0, 0.0, 0.0])
    top = _spare_world_point(monkeypatch, [0.0, 0.0, seat_geometry.PLATE])
    assert underside[1] == pytest.approx(base.STACK_HEIGHT, rel=0, abs=1e-9)
    assert top[1] == pytest.approx(base.STACK_HEIGHT + seat_geometry.PLATE, rel=0, abs=1e-9)
    assert (underside[0], underside[2]) == (140.0, -75.1)
    assert (top[0], top[2]) == (140.0, -75.1)


def test_spare_t18_footprint_is_on_the_flat_deck(monkeypatch):
    # The deck's flat ends at its edge break (user ruling 2026-10-09: the
    # black deck x +-167.0, z +-130.25 stands DECK_RISE above the green land).
    radius = sprocket.outside_dia(sprocket.TEETH["T18"]) / 2.0
    for x, y, z in product((-radius, radius), (-radius, radius), (0.0, seat_geometry.PLATE)):
        world = _spare_world_point(monkeypatch, [x, y, z])
        assert abs(world[0]) < base.DECK_HALF_X - base.DECK_EDGE_BREAK
        assert abs(world[2]) < base.DECK_HALF_Z - base.DECK_EDGE_BREAK


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
            (-radius, radius), (-radius, radius), (0.0, seat_geometry.PLATE)
        )
    )
    assert spare_max_z <= min(point[2] for point in plate_corners) - 5.0


def _numbered_items() -> dict[str, str]:
    """Item numbers against the dict order, so plans must sort by them."""
    return {
        stem: str(len(drawing.BOM_PART_NUMBERS) - index)
        for index, stem in enumerate(drawing.BOM_PART_NUMBERS)
    }


@pytest.mark.parametrize(
    ("stem", "station", "role"),
    (
        ("sh-vn-chain-link--InnerLink", drawing.CHAIN_INNER_BALLOON_STATION, "InnerLink"),
        ("sh-vn-chain-link--OuterLink", drawing.CHAIN_OUTER_BALLOON_STATION, "OuterLink"),
    ),
)
def test_each_chain_link_balloon_lands_on_a_free_run_clear_of_both_wheels(
    stem, station, role
) -> None:
    """#1531: links in the knob wheel's wrap sat under the bar's and wheel's
    edges; the ballooned links stand on the runs between the wheels."""
    anchor = drawing.ASSEMBLED_BALLOON_ANCHORS[stem].instance
    assert anchor == f"@{role}:{station // 2 + 1}"
    assert station % 2 == (0 if role == "InnerLink" else 1)
    assert 0 < station < chain.LINK_COUNT - 1  # Not the connecting link.
    crank = (-chain.CRANK_CENTRE[0], chain.CRANK_CENTRE[1])
    for pin in (station, station + 1):
        x, y, _z = assembly._chain_station_point(pin)
        assert math.dist((x, y), assembly.KNOB_SHAFT_XY) - chain.KNOB_TIP_R > 20.0
        assert math.dist((x, y), crank) - chain.CRANK_TIP_R > 20.0


def test_the_inner_and_connecting_link_anchors_are_frozen() -> None:
    """Run 20261024T124144759Z: the walk's seat-dependent ray probe put
    balloon 43 on a covered point. Both anchors are the points main's walk
    proved drawn, whatever seat probes them."""
    anchors = drawing.ASSEMBLED_BALLOON_ANCHORS
    inner = anchors["sh-vn-chain-link--InnerLink"]
    assert inner.point_mm == drawing.CHAIN_INNER_BALLOON_POINT_MM
    assert inner.point_mm == (4.946, -0.867, 1.650)
    connecting = anchors["pd-vn-chain-connecting-link"]
    assert connecting.point_mm == drawing.CONNECTING_LINK_BALLOON_POINT_MM
    assert connecting.point_mm == (-2.042, -1.262, -3.550)
    assert connecting.instance is None  # The one connecting link.
    assert anchors["sh-vn-chain-link--OuterLink"].point_mm is None


def test_every_bom_item_is_ballooned_on_some_sheet() -> None:
    """Codex B1 (19e33c6c2): items 1-12 and the chain had no balloon."""
    items = _numbered_items()
    iso, exploded = drawing.transgear_balloon_items(items)
    plans = (
        drawing.assembled_balloon_items(items),
        drawing.platen_balloon_items(items),
        iso,
        exploded,
    )
    ballooned = [stem for plan in plans for stem, _item in plan]
    assert set(ballooned) | BALLOONED_BY_SECTION_A_A == set(drawing.BOM_PART_NUMBERS)
    for plan in plans:
        assert [int(item) for _stem, item in plan] == sorted(
            int(item) for _stem, item in plan
        )
    # The removable is ballooned on the mounted knob wheel (sheets 2 and 3)
    # and on the spare T18 on the deck (sheet 1), which the caption names.
    # The transgear families the isometric reaches are ballooned again on
    # sheet 3's explode, which shows them drawn apart.
    repeated = {stem for stem in ballooned if ballooned.count(stem) > 1}
    assert repeated == (
        set(CONTRACT_TRANSGEAR_QUANTITIES) - drawing.ISO_HIDDEN_STEMS
    ) & explode.TRANSGEAR_SHOWN_STEMS
    assert ballooned.count("pd-transgear-removable") == 3
    assert all(
        ballooned.count(stem) <= 2 for stem in ballooned if stem != "pd-transgear-removable"
    )
    spare = drawing.ASSEMBLED_BALLOON_ANCHORS["pd-transgear-removable"].instance
    assert spare == drawing.SPARE_INSTANCE == "pd-transgear-removable-3"
    # Edge-on in the front and right views the spare is a bare bar: hidden
    # there, shown and ballooned on the isometric only.
    for caption in drawing.ASSEMBLED_CAPTIONS.values():
        assert (
            f"{drawing.sprocket_name(drawing._SPARE_CONFIGS[0])} ON THE BASE DECK IS A "
            "SPARE, STORED LOOSE"
        ) in " ".join(caption.split())


def test_the_exploded_sheet_balloons_exactly_the_platen_group() -> None:
    platen_group = {
        "pd-support-bar",
        "sh-column-clamp-front",
        "sh-column-clamp-back",
        "sh-vn-clamp-screw",
        "pd-platen",
        "pd-feed-rack",
        "pd-platen-bottom-guide",
        "pd-platen-guide",
        "sh-vn-fillister-screw-91794a055--RackScrew",
        "pd-guide-lock",
        "pd-platen-clip",
        "pd-platen-paper",
        "sh-vn-brass-fillister-screw",
        "pd-vn-platen-clip-screw",
        "pd-vn-guide-lock-screw",
    }
    assert set(drawing.PLATEN_BALLOON_ANCHORS) == platen_group
    assert explode.SHOWN_STEMS == platen_group
    assert drawing.SHEET_NAMES[3] == "PLATEN AND SUPPORT"
    assert drawing.SHEET_NAMES[2] == "TRANSGEAR EXPLODED"
    assert not explode.SHOWN_STEMS & explode.TRANSGEAR_SHOWN_STEMS
    # Balloon 8 lands on a bottom lock plate, the one hanging free of the bar;
    # balloon 7 on the top guide, on its top edge, between a screw station
    # and a lock station; the rack-screw balloon on one rack screw.
    pinned = {
        stem: anchor.instance
        for stem, anchor in drawing.PLATEN_BALLOON_ANCHORS.items()
        if anchor.instance is not None
    }
    assert pinned == {
        "pd-guide-lock": "pd-guide-lock-2",
        "pd-platen-guide": "pd-platen-guide-1",
        explode.RACK_SCREW: drawing.PLATEN_RACK_SCREW_INSTANCE,
    }
    assert drawing.PLATEN_RACK_SCREW_INSTANCE in RACK_SCREW_INSTANCES
    x, y, z = drawing.PLATEN_GUIDE_BALLOON_POINT_MM
    from build_pd_platen_guide import HOLE_X, SCREW_STATION_X
    from pd_platen_guide_spec import GUIDE_HEIGHT

    assert (y, z) == (GUIDE_HEIGHT, 0.0)
    stations = sorted((*HOLE_X, *SCREW_STATION_X))
    assert any(a + 10.0 < x < b - 10.0 for a, b in zip(stations, stations[1:]))


def test_the_hanging_rack_group_balloons_on_its_drawn_edges_apart() -> None:
    """The bottom guide and the rack balloon on a top edge, mid-span between
    their rack-screw holes and clear of them; the guide, the pinned rack
    screw and the rack attach at distinct stations along the platen, and
    none at the platen's own balloon station."""
    import pd_platen_bottom_guide_spec as bottom_guide

    gx, gy, gz = drawing.BOTTOM_GUIDE_BALLOON_POINT_MM
    assert (gy, gz) == (bottom_guide.GUIDE_HEIGHT, 0.0)
    clear = bottom_guide.SCREW_CBORE_DIA / 2.0 + 10.0
    assert all(abs(gx - hole) > clear for hole in bottom_guide.SCREW_HOLE_X)
    assert 0.0 < gx < bottom_guide.GUIDE_LENGTH
    rx, ry, rz = drawing.FEED_RACK_BALLOON_POINT_MM
    assert (ry, rz) == (0.0, 0.0)  # the flat top's edge, in the strip's frame
    assert all(abs(rx - tap) > 10.0 for tap in feed_rack.TAP_X)
    # Machine x from the platen's crank-side edge: the guide is placed Ry180
    # (its x runs from the far end), the rack unturned about y.
    screw = RACK_SCREW_INSTANCES.index(drawing.PLATEN_RACK_SCREW_INSTANCE)
    stations = (
        bottom_guide.GUIDE_LENGTH - gx,
        feed_rack.TAP_X[screw],
        rx,
        drawing.PLATEN_BALLOON_POINT_MM[0],
    )
    assert all(abs(a - b) > 20.0 for a, b in itertools.combinations(stations, 2))


def _explode_instances() -> list[explode.Instance]:
    """The model's components as the builder's explode reads them: each
    keyed by its family, the shared fillister's by member, under the native
    names the builder gives them."""
    instances = [
        explode.Instance(f"{stem}-1", stem)
        for stem in explode.SHOWN_STEMS - {explode.RACK_SCREW}
    ]
    instances += [explode.Instance(name, explode.RACK_SCREW) for name in RACK_SCREW_INSTANCES]
    instances += [explode.Instance(name, explode.DISC_SCREW) for name in DISC_SCREW_INSTANCES]
    instances.append(explode.Instance("pd-rack-pinion-1", "pd-rack-pinion"))
    for stem, count in CONTRACT_TRANSGEAR_QUANTITIES.items():
        if stem not in ("pd-rack-pinion", explode.DISC_SCREW):
            instances += [
                explode.Instance(f"{stem}-{index}", stem) for index in range(1, count + 1)
            ]
    return instances


def _moved_families(plan) -> set[str]:
    family = {instance.name: instance.stem for instance in _explode_instances()}
    return {family[name] for _step, names in plan for name in names}


def test_the_shared_fillister_is_one_family_per_member() -> None:
    stem = "sh-vn-fillister-screw-91794a055"
    assert explode.member_family(stem, "RackScrew") == explode.RACK_SCREW
    assert explode.member_family(stem, "DiscScrew") == explode.DISC_SCREW
    assert explode.member_family("pd-feed-rack", "Default") == "pd-feed-rack"
    assert drawing.BOM_COMPONENT_IDENTITIES[explode.RACK_SCREW] == (stem, "RackScrew")
    assert drawing.BOM_COMPONENT_IDENTITIES[explode.DISC_SCREW] == (stem, "DiscScrew")


def test_each_fillister_member_moves_and_shows_only_on_its_own_sheet() -> None:
    """The RackScrews hang with the rack on the platen sheet; the DiscScrews
    go with the disc cluster on the transgear sheet. Neither member's
    instances move with the other's group or show on the other's sheet."""
    plan = explode.plan_explode(_explode_instances())
    platen = plan[: len(explode.PLATEN_STEPS)]
    transgear = plan[len(explode.PLATEN_STEPS) :]
    platen_moved = {name for _step, names in platen for name in names}
    transgear_moved = {name for _step, names in transgear for name in names}
    assert set(RACK_SCREW_INSTANCES) <= platen_moved
    assert not set(RACK_SCREW_INSTANCES) & transgear_moved
    assert set(DISC_SCREW_INSTANCES) <= transgear_moved
    assert not set(DISC_SCREW_INSTANCES) & platen_moved
    assert explode.RACK_SCREW in explode.SHOWN_STEMS
    assert explode.DISC_SCREW not in explode.SHOWN_STEMS
    assert explode.DISC_SCREW in explode.TRANSGEAR_SHOWN_STEMS
    assert explode.RACK_SCREW not in explode.TRANSGEAR_SHOWN_STEMS
    # Sheets 2 and 3 show instances by name: the DiscScrews only.
    shown = {name for name in drawing.TRANSGEAR_INSTANCES if "91794a055" in name}
    assert shown == set(DISC_SCREW_INSTANCES)
    exploded = {
        name for name in drawing.TRANSGEAR_EXPLODED_INSTANCES if "91794a055" in name
    }
    assert exploded == set(DISC_SCREW_INSTANCES)
    cluster = next(
        group for group in drawing.TRANSGEAR_EXPLODED_GROUPS
        if explode.DISC_SCREW in group.stems
    )
    assert set(DISC_SCREW_INSTANCES) <= drawing.exploded_group_instances(cluster)


def test_the_explode_moves_only_the_platen_group_and_keeps_the_platen() -> None:
    plan = explode.plan_explode(_explode_instances())[: len(explode.PLATEN_STEPS)]
    moved = {name for _step, names in plan for name in names}
    assert "pd-rack-pinion-1" not in moved
    assert "pd-platen-1" not in moved
    assert _moved_families(plan) == explode.SHOWN_STEMS - explode.STATIONARY_STEMS
    # The guide screws leave with the guides' step, the clip screws with the
    # clips': the two screw families never share a step.
    for _step, names in plan:
        assert not {"sh-vn-brass-fillister-screw-1", "pd-vn-platen-clip-screw-1"} <= set(names)


def test_the_platen_explode_hangs_the_rack_group_below_the_platen() -> None:
    """#2410: the bottom guide, the rack and its screws drop below the platen
    together; the rack then hangs clear under the guide and the screws stand
    above the guide's top, in sight under the platen's bottom edge; the top
    guide and every lock still rise."""
    import _mcmaster_91794a055 as fillister

    def throw(family: str) -> float:
        return sum(
            step.distance_mm
            for step in explode.PLATEN_STEPS
            if family in step.stems and step.axis == "y"
        )

    platen_bottom = assembly.PLATE_Y0
    guide_top = assembly.GUIDE_Y[0] + assembly.GUIDE_HEIGHTS[0] + throw(
        "pd-platen-bottom-guide"
    )
    guide_underside = assembly.GUIDE_Y[0] + throw("pd-platen-bottom-guide")
    rack_top = assembly.RACK_Y0 + throw("pd-feed-rack")
    under_head = assembly.RACK_SCREW_FLOOR_Y + throw(explode.RACK_SCREW)
    tip = under_head - drawing.rack_screw.LENGTH
    head_top = under_head + fillister.HEAD_H
    assert guide_top < platen_bottom
    assert rack_top < guide_underside
    assert guide_top < tip < head_top < platen_bottom
    # The isometric's line of sight rises as it comes forward: a head standing
    # behind the platen's front face shows only under the height it would
    # reach at that face.
    head_front_z = (
        assembly.RACK_TEETH_FRONT_Z + assembly.RACK_TAP_Z - fillister.HEAD_DIA / 2.0
    )
    sight = platen_bottom - (head_front_z - assembly.PLATE_FRONT_Z)
    assert head_top < sight
    for family in ("pd-platen-guide", "pd-guide-lock", "pd-vn-guide-lock-screw"):
        assert throw(family) > 0.0, family


def test_the_transgear_explode_moves_the_knob_wheel_but_not_the_crank_wheel() -> None:
    plan = explode.plan_explode(_explode_instances())
    assert [step for step, _names in plan] == list(explode.EXPLODE_STEPS)
    transgear = plan[len(explode.PLATEN_STEPS) :]
    moved = {name for _step, names in transgear for name in names}
    removables = {name for name in moved if name.startswith("pd-transgear-removable-")}
    assert removables == {explode.KNOB_WHEEL_INSTANCE}
    stems = _moved_families(transgear)
    assert stems == explode.TRANSGEAR_SHOWN_STEMS - explode.TRANSGEAR_STATIONARY_STEMS
    # Nothing outside the transgear moves on these steps; the arm stays put.
    assert stems <= set(CONTRACT_TRANSGEAR_QUANTITIES)
    assert "pd-transgear-arm-1" not in moved
    # Every part moves along one machine axis, so it stays on its own axis
    # seen from above; the cup pin leaves along X, out of its cross hole, and
    # the hub's key pin along X too, out of its chord ream (#2409). The
    # collar's flat pin, drawn out of its blind ream along Z, drops along Y
    # below the collar's outline so the isometric sees it.
    off_axis = {
        "cup pin out of the cup": "x",
        "hub key pin out": "x",
        "collar flat pin below the collar": "y",
    }
    for step, _names in transgear:
        assert step.axis == off_axis.get(step.label, "z")


def test_the_cluster_explode_spreads_pin_shims_bushing_and_sleeve_in_order() -> None:
    """Round 11: along the pin, rear to front, the pin's head, the shims,
    the rear bushing and the sleeve each stand a clear gap from the next."""

    def throw(stem: str) -> float:
        return sum(s.distance_mm for s in explode.TRANSGEAR_STEPS if stem in s.stems)

    head = cluster_fit.ARM_REAR_Z + throw("pd-transgear-pin")
    shims = throw("pd-vn-transgear-cluster-shim")
    shims_rear = cluster_fit.SHIM_REAR_Z + shims
    shims_front = cluster_fit.SHIM_REAR_Z - cluster_fit.SHIM_STACK_MODEL + shims
    bushing = throw("pd-transgear-rear-bushing")
    bushing_rear = cluster_fit.REAR_BUSHING_REAR_Z + bushing
    bushing_front = cluster_fit.SLEEVE_REAR_Z + bushing
    sleeve_rear = cluster_fit.SLEEVE_REAR_Z + throw("pd-transgear-feed-pinion")
    gaps = (head - shims_rear, shims_front - bushing_rear, bushing_front - sleeve_rear)
    assert all(gap >= 5.0 for gap in gaps), gaps
    # The disc and everything ahead of it keep their places off the sleeve.
    assert throw("pd-rack-pinion") == -26.0
    assert throw("pd-vn-transgear-retaining-ring") == -72.0


def test_the_explode_refuses_a_model_missing_a_shown_family() -> None:
    instances = [i for i in _explode_instances() if i.stem != "pd-vn-platen-clip-screw"]
    with pytest.raises(ValueError, match="pd-vn-platen-clip-screw"):
        explode.plan_explode(instances)
    instances = [i for i in _explode_instances() if i.stem != "pd-transgear-thumbnut"]
    with pytest.raises(ValueError, match="pd-transgear-thumbnut"):
        explode.plan_explode(instances)
    # A model whose fillisters all read as one member lacks the other.
    instances = [
        explode.Instance(i.name, explode.DISC_SCREW) if i.stem == explode.RACK_SCREW else i
        for i in _explode_instances()
    ]
    with pytest.raises(ValueError, match="RackScrew"):
        explode.plan_explode(instances)


def test_the_explode_refuses_a_model_missing_the_knob_wheel() -> None:
    instances = [
        i for i in _explode_instances() if i.name != explode.KNOB_WHEEL_INSTANCE
    ]
    instances.append(explode.Instance("pd-transgear-removable-9", "pd-transgear-removable"))
    with pytest.raises(ValueError, match="explode instances absent.*removable-1"):
        explode.plan_explode(instances)


def test_the_platen_group_is_built_and_hung_before_its_locks_are_set() -> None:
    """Codex B2: the steps started with the locks already on."""
    order = ["bar-clamped", "rack-screwed", "guides-screwed", "clips-fitted"]
    order += ["platen-hung", "guide-locks-set", "lock-seats-faced"]
    assert list(steps.SEQUENCE[: len(order)]) == order
    assert f"{steps.BAR_TOP_ABOVE_DECK_TEXT} ABOVE THE " in _step_body("bar-clamped")
    # The round pair locates the bar before the slotted pair is tightened;
    # the step names it by its holes, as no package sheet defines END A.
    bar_clamped = _step_body("bar-clamped")
    assert bar_clamped.index("ROUND-HOLE PAIR") < bar_clamped.index("SLOTTED PAIR")
    assert "END A" not in bar_clamped
    assert steps.BAR_TOP_ABOVE_DECK == pytest.approx(
        assembly.BAR_TOP_Y - assembly.BASE_DECK_Y, abs=5e-4
    )
    assert steps.RACK_CREST_DROP == pytest.approx(
        assembly.PLATE_Y0 - assembly.RACK_TIP_Y, abs=1e-9
    )
    # Every platen-group screw count the steps print is the model's.
    assert f"{drawing.GUIDE_SCREWS} " in _step_body("guides-screwed")
    assert drawing.GUIDE_SCREWS + drawing.CLIP_SCREWS == len(
        assembly.GUIDE_SCREW_XY
    ) + len(assembly.CLIP_SCREW_XY)
    assert f"{drawing.RACK_SCREWS} " in _step_body("rack-screwed")
    assert drawing.RACK_SCREWS == len(assembly.RACK_TAP_X)


def test_the_rack_is_screwed_to_its_guide_before_the_guide_is_set_by_its_crests() -> None:
    """#2410: the guide's rack-screw holes are struck from the strip's taps
    and the strip screwed on, its ends flush and its front face set behind
    the guide's, before the guide goes on the platen; the guide is then set
    by the rack's crests (the latched hook cannot take up a rack set off its
    band), its platen taps transferred at that set, and it is set at it
    again before it is screwed on. The top guide is tapped to its own print
    (owner ruling 2026-11-08, #2144 item 2.3): nothing is spotted through
    the platen for it."""
    texts = drawing._step_text(operating_domain=_unit_operating_domain())
    rack = texts["rack-screwed"]
    struck = next(i for i, text in enumerate(rack) if "STRIKE" in text)
    clamped = struck - 1
    assert rack[clamped].startswith("CLAMP THE RACK")
    screwed = next(
        i for i, text in enumerate(rack)
        if text.startswith("SCREW THE RACK ON") and _number(explode.RACK_SCREW) in text
    )
    assert struck < screwed
    for index in (clamped, screwed):
        assert "ENDS FLUSH" in rack[index]
        assert steps.RACK_FRONT_SET_TEXT in rack[index]
        assert "RULE" in rack[index]
    assert _number("pd-platen-bottom-guide") in rack[clamped]
    # The transfer screws are made from spare rack screws in the step.
    assert "FILE" in " ".join(rack[:clamped])
    # The guide is set by the crests before its taps are transferred and
    # again before it is screwed on.
    guides = texts["guides-screwed"]
    crest_set = next(
        i for i, text in enumerate(guides)
        if f"CRESTS {steps.RACK_CREST_TEXT} BELOW THE PLATEN'S BOTTOM EDGE" in text
    )
    assert "HEIGHT GAUGE" in guides[crest_set]
    assert _number("pd-platen-bottom-guide") in guides[crest_set]
    spotted = next(i for i, text in enumerate(guides) if "TRANSFER PUNCH" in text)
    screwed_on = next(i for i, text in enumerate(guides) if text.startswith("SCREW THE GUIDES"))
    again = next(
        i for i, text in enumerate(guides)
        if drawing.sub_step("guides-screwed", crest_set) in text and i > spotted
    )
    assert crest_set < spotted < again < screwed_on
    # The model places the rack's ends flush with the platen's.
    assert assembly.RACK_X0 == assembly.PLATE_X0
    for text in guides:
        if any(word in text for word in ("SPOT", "TRANSFER", "DRILL", "TAP EACH")):
            assert _number("pd-platen-guide") not in text
    # A new bottom guide takes the rack again from the rack's own step.
    rack_step = f"STEP {steps.step_number('rack-screwed')}"
    assert any(
        _number("pd-platen-bottom-guide") in text and rack_step in text for text in guides
    )
    assert any(
        _number("pd-platen-bottom-guide") in text and rack_step in text
        for text in texts["lock-seats-faced"]
    )


def test_no_step_solders_and_the_rack_rework_resets_its_guide() -> None:
    """Owner rulings 2026-11-13 (#2410): no solder, no backer. A loaded-rack
    check that finds every part inside its sheet sets the bottom guide again
    by the crests, rather than reworking a joint."""
    for text in drawing.sheet_texts(_unit_step_notes()):
        assert "SOLDER" not in text and "BACKER" not in text
    rework = _step_body("loaded-rack-geometry-checked")
    assert f"SLACKEN THE {_number('pd-platen-bottom-guide')} BOTTOM GUIDE" in rework
    # Machinist review r8: the re-set names its reference and band (3B's
    # crest drop) and the level the mesh gate assumes.
    assert f"SET THE GUIDE AGAIN PER {drawing.sub_step('guides-screwed', 1)}" in rework
    level = f"WITHIN {steps.inch_text(steps.LEVEL_RACK_CREST_DRIFT, 3)} OF EACH OTHER"
    assert level in rework


def test_every_screwed_setting_has_a_holding_check() -> None:
    """Machinist review r8 and a run of this sheet for #2824 (rule 23): the
    guide locks, the refitted plate screws, the seated pivot screw and the
    hook each get a bench check after they are tightened or seated, with a
    remedy, as 2M, 3N and 4C already had. The pivot screw is unlocked
    (U-MHA-PD-VN-57-no-lock): its checks are the shoulder's seat and the
    arm's free fall."""
    texts = drawing._step_text(operating_domain=_unit_operating_domain())
    locks = texts["guide-locks-set"]
    assert locks[3] == "CHECK: PUSHED FIRMLY BY HAND, NO LOCK MOVES ON ITS GUIDE."
    assert locks[4].startswith("IF ONE MOVES, FIT NEW ")
    plate = texts["arm-plate-screws-cut"]
    assert plate[4] == "CHECK: ROCKED BY HAND, THE PLATE HAS NO SHAKE AND NO DAYLIGHT."
    assert plate[5] == "IF IT SHAKES OR SHOWS DAYLIGHT, DO 13U AND REPEAT 14E."
    pivot = texts["hanger-pivoted"]
    assert pivot[10].endswith("SEAT THE SCREW, ITS SHOULDER TIGHT ON THE BAR'S BACK FACE "
                              f"({drawing.PIVOT_VIEW_REF}).")
    assert pivot[11] == "CHECK: NO DAYLIGHT BETWEEN THE SPACER AND THE BAR'S BACK FACE."
    assert pivot[12] == "CHECK: A HEX KEY BY HAND DOES NOT LOOSEN THE SCREW."
    assert pivot[13] == "CHECK: RAISED AND RELEASED, THE ARM FALLS FREELY."
    assert pivot[14] == "IF ALL THREE CHECKS PASS, SKIP 15R-15Z."
    # The remedy takes the screw out with the arm captive on it (the bonded
    # spacer keeps the arm on the shoulder) before anything is cleaned.
    assert pivot[15].startswith("UNSCREW ")
    assert pivot[16] == "LIFT IT OUT, THE ARM AND THE SPACER ON IT."
    assert pivot[17].startswith("FLUSH OIL INTO THE ARM'S BORE")
    assert "BAR BACK FACE" in pivot[18]
    # One repeat of the reseat, its checks, their skip and the strip: checks
    # that pass leave the step, checks that fail leave the arm off.
    assert pivot[19] == "REPEAT 15L-15S ONCE."
    # #3107: the screw and spacer are renewed once; a second failure sends
    # the bar and the arm to their sheets, and every outcome has a route: a
    # bar outside (with the arm if it is outside too), an arm outside or all
    # inside, one action a step (rule 22). The renewal frees the captive arm
    # on the arbor press (D10, owner question Q7a, option B).
    bar = _number("pd-support-bar")
    assert pivot[20:23] == (
        "IF NOT YET RENEWED, PUSH THE SCREW OUT OF THE SPACER, ARM REAR FACE "
        "DOWN ON THE ARBOR PRESS, AND REPEAT FROM 14G WITH A NEW "
        f"{_number('pd-vn-transgear-pivot-screw')} SCREW AND "
        f"{_number('pd-transgear-pivot-spacer')} SPACER.",
        f"IF ALREADY RENEWED, INSPECT THE {bar} BAR'S TAP AND BACK FACE AND THE "
        f"{_number('pd-transgear-arm')} ARM'S BORE TO THEIR SHEETS.",
        f"FOR A BAR FOUND OUTSIDE, MAKE A NEW {bar} BAR AND REBUILD FROM STEP "
        f"{steps.step_number('bar-clamped')}, WITH 15Z'S PARTS IF THE ARM IS ALSO OUTSIDE.",
    )
    assert pivot[23].startswith(
        "FOR AN ARM FOUND OUTSIDE, OR IF ALL ARE INSIDE, REPEAT FROM STEP "
        f"{steps.step_number('latch-pin-pressed')} WITH A NEW {_number('pd-transgear-arm')} ARM,"
    )
    # Only the parts fitted by step 15 are renewed (Codjiflo P3 on f92995b8e6).
    for later in ("pd-transgear-knob-shaft", "pd-transgear-knob-cup", "pd-latch-hook"):
        assert _number(later) not in pivot[23]
    assert len(pivot) == 24
    assert not any("STAKE" in line for line in pivot)
    accepted = texts["fitup-accepted"]
    # From 33 the reseat runs; a repeat failure takes the knob stack off
    # (28G) and rebuilds the arm as 28R-28V, whose step 15 carries the
    # renewal and the inspection (Codjiflo P2 on e8b4e199aa).
    assert "IF 33F FAILS, ARM UNLATCHED, DO 15R-15U AND 15L-15P." in accepted
    assert "IF A 15M-15P CHECK THEN FAILS, DO 28G AND 28R-28V." in accepted
    assert texts["fitup-mesh-remedied"][6].startswith("REMOVE THE ")
    assert texts["fitup-mesh-remedied"][15].startswith(
        "FOR A FAULT ALL ROUND (ARM SETTING)"
    )
    assert texts["fitup-mesh-remedied"][19].startswith("SKIP STEPS ")
    hook = texts["hook-pin-hole-match-drilled"]
    assert hook[4] == "TIGHTEN THE HOOK SCREWS."
    assert hook[5] == "CHECK: PUSHED FIRMLY BY HAND, THE HOOK DOES NOT MOVE ON THE BAR."


def test_no_bare_pinion_names_two_gears() -> None:
    """#3107 (Codjiflo P3 on 3e6318a026; rules 25 and 26): the MHA-PD-10
    sleeve is the Feed Pinion Sleeve, so the steps and the setting table never
    print a bare PINION: the knob shaft's gear is the KNOB PINION or the
    MHA-PD-08 PINION, the sleeve's the FEED PINION."""
    domain = _unit_operating_domain()
    rows = [row for rows in drawing._step_text(operating_domain=domain).values() for row in rows]
    rows += [" ".join(row) for row in drawing.setting_table_rows(operating_domain=domain)]
    qualified = re.compile(
        rf"\b(?:KNOB|FEED|{re.escape(_number('pd-transgear-knob-shaft'))}) PINION\b"
    )
    bare = [row for row in rows if re.search(r"\bPINION\b", qualified.sub("", row))]
    assert not bare
    assert drawing.KNOB_PINION == "KNOB PINION"
    assert drawing.FEED_PINION == "FEED PINION"


def test_every_failure_branch_has_a_pass_exit() -> None:
    """#2629 (machinist rule 22): a builder whose checks pass never reads on
    into a plain remedy command; each branch after the exit carries its
    condition."""
    texts = drawing._step_text(operating_domain=_unit_operating_domain())
    s = drawing.sub_step
    mesh = texts["fitup-mesh-remedied"]
    pose_checks = f"{s('fitup-pose-set', 7)}-{s('fitup-pose-set', 9)}"
    after = steps.step_number("collar-rear-faced-to-fit")
    assert mesh[0] == f"IF EVERY {pose_checks} CHECK PASSES, GO TO STEP {after}."
    assert mesh[4] == f"IF EVERY {pose_checks} CHECK NOW PASSES, GO TO STEP {after}."
    branches = mesh[mesh.index(next(r for r in mesh if r.startswith("FOR A FAULT ONCE"))):]
    assert all(
        row.startswith(("FOR ", "REFIT A LOOSE PLATE", "SKIP STEPS")) for row in branches
    )
    accepted = texts["fitup-accepted"]
    exit_row = f"IF EVERY CHECK PASSES, GO TO STEP {steps.step_number('chain-closed')}."
    remedies = accepted[accepted.index(exit_row) + 1:]
    assert remedies and all(row.startswith(("IF ", "FOR ")) for row in remedies)
    run = texts["chain-run-accepted"]
    # The remedy opens the link and lifts the chain off as two sub-steps
    # (machinist review of 70917f0316).
    assert run[3] == (
        f"IF BOTH CHECKS PASS, SKIP {s('chain-run-accepted', 4)}-"
        f"{s('chain-run-accepted', 7)}."
    )
    assert run[4].startswith("OPEN THE ") and run[4].endswith(" LINK.")
    assert run[5] == "LIFT THE CHAIN OFF."
    assert run[7].startswith("REPEAT STEPS ")
    located = texts["arm-plate-located"]
    assert located[16] == (
        f"IF {s('arm-plate-located', 11)} AND {s('arm-plate-located', 12)} PASSED, GO TO STEP "
        f"{steps.step_number('arm-plate-fitted')}."
    )
    # Owner ruling 2026-11-24, audit part 2 question C1: the trial's move
    # before a part is inspected, toward S only (no away move is left inside
    # the limits once TRUE's error is charged); a tight spot or no shake
    # takes the inspection (Codjiflo r2 on #3539). The move itself is the
    # setting table's row, cited, never typed into the step (rule 22;
    # codjiflo r2 on #3539).
    assert located[17] == (
        f"IF ONLY {s('arm-plate-located', 12)} FAILED, ON SHAKE OVER .008, AT "
        f"{drawing.KNOB_SETTING_VIEW_NAME}'S SETTING, MOVE THE TABLE TOWARD S BY THE "
        f"TRIAL MOVE {drawing.row_cite('trial-move')}, THEN FROM {s('arm-plate-located', 5)}."
    )
    assert "AWAY FROM S" not in located[17]
    assert drawing.KNOB_TRIAL_MOVE_TEXT not in located[17]
    rows = drawing.setting_table_rows(operating_domain=_unit_operating_domain())
    (move_row,) = [row for row in rows if row[1] == s("arm-plate-located", 17)]
    assert move_row[0] == str(drawing.SETTING_ROW["trial-move"])
    assert move_row[2] == (
        f"TABLE MOVED TOWARD S FROM {drawing.KNOB_SETTING_VIEW_NAME}'S SETTING"
    )
    assert move_row[3] == drawing.KNOB_TRIAL_MOVE_TEXT
    assert move_row[4] == "DRO"
    # The re-indication reads N at the table's setting, DETAIL K's or as
    # moved, so a moved plate reaches the pass exit (Codjiflo r2 on #3539).
    assert located[14].endswith(
        f"KNOB BORE {drawing.KNOB_BORE_LETTER} AT THE TABLE'S SETTING."
    )
    # Every return to the tap (12H's re-tap, the move, a part's retrial)
    # frees the plate first.
    assert located[5].startswith("SLACKEN THE CLAMPS AND TAP THE PLATE UNTIL KNOB BORE")
    assert located[18].startswith("IF NOT, INSPECT THE ")


def test_the_lock_taps_are_the_even_taps_counted_from_either_end() -> None:
    """The steps count the guide's lock taps in plain words (round 4, rule
    22): along the rail the platen-screw taps alternate with the lock taps,
    so the lock taps are the 2nd, 4th, 6th and 8th from either end."""
    import build_pd_platen_guide as guide

    stations = sorted(
        [(x, "screw") for x in guide.SCREW_STATION_X]
        + [(x, "lock") for x in guide.HOLE_X]
    )
    kinds = [kind for _, kind in stations]
    assert len(kinds) == drawing.GUIDE_TAPS_IN_ROW
    lock_positions = [i + 1 for i, kind in enumerate(kinds) if kind == "lock"]
    assert lock_positions == [2, 4, 6, 8]
    assert kinds == kinds[::-1]
    hung = _step_body("platen-hung")
    assert not re.search(r"\bA[1-9]\b", _step_body("guides-screwed") + hung)


def test_the_sprockets_are_named_plainly_never_by_configuration_code() -> None:
    """Round 8 (rules 22, 26): the steps and sheet 1 name each MHA-PD-09
    sprocket by its tooth count, never by the bare T12/T18/T24 code."""
    codes = re.compile(
        r"\b(?:" + "|".join(re.escape(name) for name, _teeth in sprocket.CONFIGS) + r")\b"
    )
    notes = _unit_step_notes()
    for text in drawing.sheet_texts(notes):
        assert not codes.search(text), text
    assert drawing.sprocket_name(sprocket.KNOB_CONFIG) == (
        f"{sprocket.KNOB_TEETH}-TOOTH {_number('pd-transgear-removable')} SPROCKET"
    )
    assert drawing.sprocket_name(drawing._SPARE_CONFIGS[0]) in drawing.ASSEMBLED_CAPTIONS[
        next(iter(drawing.ASSEMBLED_CAPTIONS))
    ].replace("\n", " ")


def test_the_chain_is_closed_and_run_after_the_collar_is_accepted() -> None:
    """Codex B3: routing, closure, adjustment and a functional run."""
    assert steps.SEQUENCE[-3:] == (
        "fitup-accepted",
        "chain-closed",
        "chain-run-accepted",
    )
    closed = _step_body("chain-closed")
    # The loose links are cut one pitch short; the connecting link closes it.
    # Cut, loop and join are one sub-step each (machinist review of
    # 592b20079f).
    cut, loop, join = drawing._step_text(operating_domain=_unit_operating_domain())[
        "chain-closed"
    ]
    assert cut.startswith(f"CUT {chain.LINK_COUNT - 1} PITCHES")
    assert cut.endswith("WITH A #25 CHAIN BREAKER.")
    assert loop.startswith("LOOP THEM OVER")
    assert join.startswith("JOIN THE ENDS")
    assert f"MAKES THE LOOP {chain.LINK_COUNT} PITCHES" in join
    assert "ANSI #25" in closed
    knob = drawing.sprocket_name(sprocket.KNOB_CONFIG, numbered=False)
    crank = drawing.sprocket_name(sprocket.CRANK_CONFIG, numbered=False)
    assert f"OVER THE {knob} AND THE {crank}" in " ".join(closed.split())
    assert chain.LINK_COUNT % 2 == 0
    assert chain.LINK_PITCH == sprocket.CHAIN_PITCH
    assert chain.CENTRELINE_LEN == pytest.approx(
        chain.LINK_COUNT * sprocket.CHAIN_PITCH
    )
    assert drawing.CHAIN_QUANTITIES == {
        "sh-vn-chain-link--InnerLink": chain.LINK_COUNT // 2,
        "sh-vn-chain-link--OuterLink": chain.LINK_COUNT // 2 - 1,
        "pd-vn-chain-connecting-link": 1,
    }
    assert sum(drawing.CHAIN_QUANTITIES.values()) == chain.LINK_COUNT
    # #3106: the two link rows share one Number, so the step names their items.
    assert (
        f"{chain.LINK_COUNT // 2} INNER, ITEM "
        f"{drawing.SHARED_NUMBER_ITEMS['sh-vn-chain-link--InnerLink']}, AND "
        f"{chain.LINK_COUNT // 2 - 1} OUTER LINKS, ITEM "
        f"{drawing.SHARED_NUMBER_ITEMS['sh-vn-chain-link--OuterLink']}"
    ) in " ".join(closed.split())
    assert f"THE {_number('pd-vn-chain-connecting-link')} #25 CONNECTING LINK" in closed
    for stem in drawing.CHAIN_QUANTITIES:
        assert "ANSI #25" in drawing.BOM_DESCRIPTIONS[stem]
    assert "CONNECTING LINK" in closed and "CLOSED END LEADING" in closed
    assert "NO TENSIONING" in closed
    run = _step_body("chain-run-accepted")
    assert "EVERY TOOTH" in run and "TOUCHES NOTHING" in run
    assert "LOOPED" not in _step_body("collar-shoulder-seated")


def test_the_setting_and_the_acceptance_offsets_are_told_apart() -> None:
    """Codex clarity: one band sets, a wider one accepts; the knob wheel
    behind the crank wheel within the acceptance passes."""
    setting = _step_body("collar-rear-faced-to-fit")
    accepted = _step_body("fitup-accepted")
    assert collar.FIT_UP_OFFSET_SET_TEXT in setting
    assert steps.OFFSET_ACCEPT_TEXT in accepted
    assert collar.FIT_UP_OFFSET_SET_TEXT != steps.OFFSET_ACCEPT_TEXT
    assert f"STEPS {steps.step_number('collar-rear-faced-to-fit')}-" in accepted
    behind = steps.OFFSET_ACCEPT_TOL - collar.FIT_UP_OFFSET_TARGET
    assert behind > 0.0


def test_the_chain_plane_bands_spend_the_offset_budget_not_the_fitter() -> None:
    """#2420: a straightedge across both wheels and feelers sets and reads
    the pair, and a miss costs a facing cut or a collar, so the re-check takes
    the widest .001 band the ±1 mm offset limit leaves in service and the
    setting the same band less the refit allowance it always kept."""
    inch = 0.0254
    budget = collar.CHAIN_OFFSET_LIMIT
    low, high = steps.ACCEPTED_CHAIN_OFFSET_IN_SERVICE
    assert max(abs(low), abs(high)) <= budget
    # One more thousandth of acceptance breaks the limit at the forward end.
    assert low - inch < -budget
    assert steps.OFFSET_ACCEPT_TOL - collar.FIT_UP_OFFSET_SET_TOL == pytest.approx(2 * inch)
    # Wide enough to read on feelers in .001 steps without a re-face per miss.
    assert collar.FIT_UP_OFFSET_SET_TOL >= 5 * inch
    # Whatever the setting passes, the re-check passes too.
    set_low, set_high = collar.CHAIN_OFFSET_IN_SERVICE
    assert low < set_low and set_high < high
    assert collar.CHAIN_OFFSET_MARGIN >= 0.0


def test_the_knob_wheel_is_read_held_back_on_its_seat() -> None:
    """Codex P2 on b2eb9a0e1: read the wheel held back on its seat, not
    floated forward under the nut. Its actual float is paid once in service."""
    pose = _step_body("fitup-pose-set")
    knob = drawing.sprocket_name(sprocket.KNOB_CONFIG)
    assert f"{knob}, HELD BACK ON ITS SEAT" in " ".join(pose.split())
    # Step 29 refits what is off as 27D-27F, the wheel held back there.
    pose_set = drawing._step_text(operating_domain=_unit_operating_domain())[
        "fitup-pose-set"
    ]
    assert "HELD BACK ON ITS SEAT" in pose_set[4]
    assert (
        f"AS {drawing.sub_step('fitup-pose-set', 3)}-{drawing.sub_step('fitup-pose-set', 5)}."
        in " ".join(_step_body("collar-rear-faced-to-fit").split())
    )
    accepted = _step_body("fitup-accepted")
    assert accepted.startswith(f"CHECK, IN STEP {steps.step_number('fitup-pose-set')}")
    low, high = steps.ACCEPTED_CHAIN_OFFSET_IN_SERVICE
    half_plate_spread = (max(seat_geometry.PLATE_BAND) - min(seat_geometry.PLATE_BAND)) / 2.0
    assert (low, high) == pytest.approx(
        (
            -(collar.FIT_UP_OFFSET_TARGET + steps.OFFSET_ACCEPT_TOL)
            - half_plate_spread
            - collar.CRANK_END_PLAY_MAX
            - collar.KNOB_END_FLOAT_MAX
            - max(collar.KNOB_FLOAT_RANGE),
            steps.OFFSET_ACCEPT_TOL
            - collar.FIT_UP_OFFSET_TARGET
            + half_plate_spread
            + collar.HANGER_AXIAL_PLAY_MAX,
        ),
        abs=1e-9,
    )
    # The float is in the budget, forward: the contract's set range and the
    # acceptance both lose it at their forward ends.
    assert collar.CHAIN_OFFSET_IN_SERVICE[0] == pytest.approx(
        collar.CHAIN_SET_RANGE[0]
        - collar.CRANK_END_PLAY_MAX
        - collar.KNOB_END_FLOAT_MAX
        - max(collar.KNOB_FLOAT_RANGE)
    )
    assert max(abs(low), abs(high)) <= collar.CHAIN_OFFSET_LIMIT


def test_a_balloon_ring_is_centred_in_its_room_or_refused() -> None:
    limits = (0.2, 0.1, 0.4, 0.3)
    outline = (0.0, 0.0, 0.1, 0.1)
    dx, dy = drawing.ring_fit_shift(outline, limits, name="t")
    ring = drawing._grown(
        (outline[0] + dx, outline[1] + dy, outline[2] + dx, outline[3] + dy),
        drawing.BALLOON_RING_REACH,
    )
    assert ring[0] - limits[0] == pytest.approx(limits[2] - ring[2])
    assert ring[1] - limits[1] == pytest.approx(limits[3] - ring[3])
    with pytest.raises(ValueError, match="width"):
        drawing.ring_fit_shift((0.0, 0.0, 0.19, 0.1), limits, name="t")


def test_the_knob_stack_ring_runs_below_its_field_only_clear_of_the_title_block() -> None:
    """Run 20261121T015111001Z (#2425) read the knob stack and hanger's ring
    199.3 mm tall in its 197.0 mm field: the cup screw thrown behind the cup
    lengthened the view along the isometric's Z. The ring hangs from the
    field's top and runs into the empty field left of the title block; its
    balloons, on an ellipse round the outline, stay off the block."""
    knob, cluster = drawing.TRANSGEAR_EXPLODED_GROUPS
    assert cluster.ring_floor is None
    assert drawing.SHEET_INNER_BORDER_BOTTOM < knob.ring_floor < knob.ring_limits[1]
    reach = drawing.BALLOON_RING_REACH
    # The run's height; its width passed (at most the field's 244 mm).
    for width in (0.150, knob.ring_limits[2] - knob.ring_limits[0] - 2 * reach):
        outline = (0.05, 0.05, 0.05 + width, 0.05 + 0.1993 - 2 * reach)
        with pytest.raises(ValueError, match=r"height 199\.3 mm > room 197\.0 mm"):
            drawing.ring_fit_shift(outline, knob.ring_limits, name=knob.label)
        dx, dy = drawing.exploded_ring_shift(outline, knob)
        ring = drawing._grown(
            (outline[0] + dx, outline[1] + dy, outline[2] + dx, outline[3] + dy), reach
        )
        assert ring[3] == pytest.approx(knob.ring_limits[3])
        assert ring[0] - knob.ring_limits[0] == pytest.approx(knob.ring_limits[2] - ring[2])
        assert ring[1] >= knob.ring_floor
        # Every balloon circle on the ellipse clears the title block.
        keep_x, keep_y = drawing.TITLE_BLOCK_KEEP_OUT
        circle = reach - drawing.BALLOON_MARGIN
        centre = ((ring[0] + ring[2]) / 2.0, (ring[1] + ring[3]) / 2.0)
        semi = ((ring[2] - ring[0]) / 2.0 - circle, (ring[3] - ring[1]) / 2.0 - circle)
        for k in range(720):
            angle = math.radians(k / 2.0)
            x = centre[0] + semi[0] * math.cos(angle)
            y = centre[1] + semi[1] * math.sin(angle)
            assert x + circle < keep_x or y - circle >= keep_y, (width, x, y)
    # A ring whose balloons would come down on the block is refused, and so
    # is one past the floor; a field without a floor refuses any overflow.
    with pytest.raises(ValueError, match="over the title block"):
        drawing.exploded_ring_shift((0.0, 0.0, 0.200, 0.200), knob)
    with pytest.raises(ValueError, match="height"):
        drawing.exploded_ring_shift((0.0, 0.0, 0.100, 0.230), knob)
    with pytest.raises(ValueError, match="height"):
        drawing.exploded_ring_shift((0.0, 0.0, 0.100, 0.150), cluster)


# Farm run 20261001T142942518Z (8689c2a0d) read sheet 1's isometric at 1:3:
# its outline 187.7 mm tall; its width passed, so at most 149 mm.
ISO_OUTLINE_AT_1_3 = (0.250, 0.075, 0.250 + 0.149, 0.075 + 0.1877)


class _PaddedView:
    """A view whose read-back outline is its content, which scales, plus a
    fixed sheet-space padding, which does not (SolidWorks' outline)."""

    def __init__(self, size_m, at_scale, padding_m):
        self.content = tuple(
            (side - padding_m) / (at_scale[0] / at_scale[1]) for side in size_m
        )
        self.padding = padding_m
        self.applied = []

    def outline_at(self, scale):
        self.applied.append(scale)
        ratio = scale[0] / scale[1]
        width, height = (side * ratio + self.padding for side in self.content)
        return (0.2, 0.1, 0.2 + width, 0.1 + height)


def test_the_sheet_one_isometric_ring_fits_at_the_sheet_scale() -> None:
    """The 1:3 isometric's ring overflowed natively (221.7 > 198.0 mm); at the
    sheet's scale the same view's ring fits, whatever its fixed padding."""
    with pytest.raises(ValueError, match=r"height 221\.7 mm > room 198\.0 mm"):
        drawing.ring_fit_shift(
            ISO_OUTLINE_AT_1_3, drawing.ISO_RING_LIMITS, name="sheet 1 isometric"
        )
    size = (
        ISO_OUTLINE_AT_1_3[2] - ISO_OUTLINE_AT_1_3[0],
        ISO_OUTLINE_AT_1_3[3] - ISO_OUTLINE_AT_1_3[1],
    )
    assert drawing.ISO_SCALE_LADDER[0] == drawing.ASSEMBLED_SCALE
    for padding in (0.0, 0.0127, 0.0254):
        view = _PaddedView(size, (1.0, 3.0), padding)
        scale, _outline = drawing.step_down_to_fit(
            view.outline_at, drawing.ISO_SCALE_LADDER, drawing.ISO_RING_LIMITS, name="t"
        )
        assert scale == drawing.ASSEMBLED_SCALE, padding
    # Every scale the isometric may take has its caption.
    assert set(drawing.ASSEMBLED_CAPTIONS) == set(drawing.ISO_SCALE_LADDER)


def test_the_exploded_view_steps_down_on_its_native_outline() -> None:
    """Codex P2 (aa9d3b681): a 211.9 mm wide outline at 1:3 with 12.7 mm of
    fixed padding, scaled whole, predicts a 192.9 mm ring at 1:4 in the 193.0
    room; natively it is 196.1, so the view must go on to 1:5 (166.2)."""
    ladder = drawing.EXPLODED_SCALE_LADDER
    limits = drawing.EXPLODED_RING_LIMITS
    assert limits[2] - limits[0] == pytest.approx(0.193)
    view = _PaddedView((0.2119, 0.100), (1.0, 3.0), 0.0127)
    scale, outline = drawing.step_down_to_fit(view.outline_at, ladder, limits, name="t")
    assert scale == (1.0, 5.0)
    assert view.applied == list(ladder)
    assert outline == view.outline_at(scale)
    # A view that fits as placed is not rescaled.
    view = _PaddedView((0.120, 0.120), (1.0, 3.0), 0.0127)
    assert (
        drawing.step_down_to_fit(view.outline_at, ladder, limits, name="t")[0]
        == (ladder[0])
    )
    assert view.applied == [ladder[0]]
    # Only when 1:5 still overflows does it refuse, naming every scale.
    view = _PaddedView((0.5, 0.5), (1.0, 3.0), 0.0127)
    with pytest.raises(ValueError, match=r"no t scale fits: .*1:3.*1:4.*1:5"):
        drawing.step_down_to_fit(view.outline_at, ladder, limits, name="t")
    assert set(drawing.EXPLODED_CAPTIONS) == set(ladder)


def test_the_hook_is_set_on_a_meshed_and_run_hanger() -> None:
    """Codex (8b5e1f354) / R9-62: the hook was match-drilled with the hanger
    "latched" but the pinion-in-rack mesh never set nor the platen run."""
    keys = ("latch-hook-fitted", "hanger-meshed", "hook-pin-hole-match-drilled")
    fitted, meshed, drilled = (steps.step_number(key) for key in keys)
    assert meshed == fitted + 1 and drilled == meshed + 1
    domain = _unit_operating_domain()
    mesh = _step_body("hanger-meshed")
    hook = _step_body("hook-pin-hole-match-drilled")
    # #2416 (owner direction 2026-11-11): the mesh is set by feel, so the step
    # prints no setting value; the engaged-feed window is its only number.
    assert not re.search(
        r"\.\d{3}", mesh.replace(drawing.engaged_feed_text(domain), "")
    )
    assert not hasattr(steps, "RACK_DATUM_BACKLASH_TEXT")
    # The window names its end by the crank, not by a machine axis no sheet
    # draws, and the title block already gives the unit.
    window = drawing.engaged_feed_text(domain)
    assert window in mesh
    for axis_word in ("-X", "+X", "MACHINE X", " MM"):
        assert axis_word not in mesh
    # Codex P1 on b2eb9a0e1: set clear of the pin, the unclamped arm fell
    # through the hole's clearance and opened the feed mesh.
    assert "LOWER EDGE ON THE PIN" in hook
    # Rule 24: the pin hole is the hook drawing's. The hook is used as
    # supplied, with no heat treatment (#2527, owner ruling 2026-11-20).
    assert f"PER {drawing._N['pd-latch-hook']}" in hook
    assert "HARDEN" not in hook and "TEMPER" not in hook


def test_the_feel_set_starts_at_the_worst_corners_first_bind() -> None:
    """#2416 (owner direction 2026-11-11; codjiflo P3s on 2f5bac993 and
    c4e3ec5b4): zero backlash passes the interference point, so the felt bind
    at the worst corner comes before the flanks wedge. The stack starts there:
    just short of it a corner still reaches past that point, and a feel set
    runs looser than the builder's design band."""
    import paper_drive_mesh_check as mesh_check

    bind = steps.FEED_FIRST_BIND_BACKLASH_MM
    short = mesh_check.feed_rack_mesh((bind - 1e-4,) * 2)
    assert short.interference_margin_min_mm < 0.0
    assert mesh_check.feed_rack_mesh((bind,) * 2).interference_margin_min_mm >= 0.0
    assert steps.FEED_LOOSEST_BACKLASH_MM > rack_setup.RACK_DATUM_BACKLASH_RANGE[1]


def test_the_loaded_rack_check_is_one_dial_run_over_the_engaged_window() -> None:
    texts = drawing._step_text(operating_domain=_unit_operating_domain())[
        "loaded-rack-geometry-checked"
    ]
    travel = next(text for text in texts if "RUN THE PLATEN" in text)
    assert "KNOB HELD" not in travel
    assert any(text.startswith("CHECK: KNOB HELD") for text in texts)
    body = _step_body("loaded-rack-geometry-checked")
    for method in ("UNCERTAINTY", "RE-ZERO", "DATUM", "REJECT"):
        assert method not in body
    assert steps.step_number("hook-pin-hole-match-drilled") < steps.step_number(
        "loaded-rack-geometry-checked"
    ) < steps.step_number("fitup-pose-set")
    assert drawing.FITUP_CHAIN_KEY == "loaded-rack-geometry-checked"


def test_the_reducer_is_clocked_once_with_an_ordinary_limit() -> None:
    body = _step_body("fitup-pose-set")
    assert "HELD BACK ON ITS SEAT" in " ".join(body.split())
    clock = steps.inch_floor_mm(drawing.quality.reducer_setup_clock_deviation_mm(), 3)
    assert f"WITHIN {disc.inch_text(clock, 3)} AT THE PITCH CIRCLE" in body
    assert "TEST INDICATOR" in body
    # The reducer is accepted on an indicator, not on feelers in the mesh.
    assert (
        f"THE DISC SHAKES {drawing.REDUCER_BACKLASH_DIAL_TEXT} AS "
        f"{drawing.sub_step('arm-plate-located', 12)}"
    ) in " ".join(body.split())
    assert drawing.reducer_dial_check("SHAFT") in _step_body("arm-plate-located")
    assert "FEELER ENTERS" not in body
    for method in ("UNCERTAINTY", "RE-ZERO", "RE-CLOCK", "ABSOLUTE", "REJECT"):
        assert method not in body
    assert steps.step_number("knob-stack-fitted") < steps.step_number("fitup-pose-set")
    assert steps.step_number("fitup-pose-set") < steps.step_number("chain-closed")


def test_the_reducer_dial_window_is_what_a_build_inside_its_drawings_reads() -> None:
    """Pressed together, the mesh stands closer than the axes by half of both
    running clearances; the ceiling takes the loosest reading, rounded
    outward one division at most, and the tightest mesh still shakes: no
    floor prints (owner ruling 2026-11-24, audit part 2 question C2)."""
    journal = (
        min(knob_bush.BORE_DIA_LIMITS) - max(knob_shaft.JOURNAL_DIA_BAND),
        max(knob_bush.BORE_DIA_LIMITS) - min(knob_shaft.JOURNAL_DIA_BAND),
    )
    sleeve = cluster_fit.BORE_DIAMETRAL_CLEARANCE
    assert 0.0 < journal[0] < journal[1] and 0.0 < sleeve[0] < sleeve[1]
    closures = [(journal[i] + sleeve[i]) / 2.0 for i in (0, 1)]
    tips = [profile.blank_radius_mm for profile in disc.manufactured_profiles()]
    pitch = disc.PITCH_DIA / 2.0
    readings = [
        backlash * tip / pitch
        # C1: the trial's one move toward S reaches below the set band.
        for centre in (drawing.knob_setting.TRIAL_LOWEST_CENTRE_MM, *disc.CENTRE_DISTANCE_WINDOW)
        for closure in closures
        for backlash in drawing.mesh_check.reducer_mesh(centre - closure).backlash_mm
        for tip in tips
    ]
    step = drawing.REDUCER_DIAL_STEP_MM
    high = drawing.REDUCER_SHAKE_MAX_MM
    assert high - step < max(readings) <= high
    assert high / step == pytest.approx(round(high / step))
    # No bind: the tightest shake is positive; the needle moving shows it.
    assert min(readings) > 0.0
    assert drawing.REDUCER_SHAKE_MIN_MM == pytest.approx(min(readings))
    assert drawing.REDUCER_BACKLASH_DIAL_TEXT == (
        f"(THE NEEDLE MOVES), {disc.inch_text(high, 3)} MAX"
    )


def test_every_step_naming_s_or_n_defines_them_or_points_to_their_key() -> None:
    """Machinist review on 0a4408f590 (rule 22): step 12R packed onto a sheet
    without the DETAIL K key and used S and N bare. Each sheet's step that
    reads S or N names the bore's part or points to the key's sheet."""
    key_sheet = drawing.SHEET_NAMES.index(drawing.KNOB_SETTING_SHEET) + 1
    bare = re.compile(rf"(?<![\w'])(S|{drawing.KNOB_BORE_LETTER})\b(?! TO )")
    for column in drawing.pack_step_columns(
        drawing._step_text(operating_domain=_unit_operating_domain())
    ):
        if column.sheet == drawing.KNOB_SETTING_SHEET:
            continue
        for step in re.split(r"\n(?=\d+[A-Z]?\. )", column.text):
            flat = " ".join(step.split())
            if "DRO" not in flat or not bare.search(flat):
                continue
            assert f"(SHEET {key_sheet})" in flat or (
                "PIN BORE S" in flat
                and f"KNOB BORE {drawing.KNOB_BORE_LETTER}" in flat
            ), flat


def test_the_reducer_mesh_is_tried_before_the_plate_is_doweled() -> None:
    """#2417: the mesh is read on its real seats while the plate is clamped,
    again once it is doweled, and only confirmed at the chain fit-up."""
    located = _step_body("arm-plate-located")
    trial = located.index("TRIAL MESH")
    check = drawing.reducer_dial_check("SHAFT")
    assert located.index(check) > trial
    lifted = located.index("LIFT OFF THE SHAFT", trial)
    # The pilots wait for the trial, opening the fitted step.
    assert _step_body("arm-plate-fitted").startswith(f"MATCH-DRILL 2 {drawing.PLATE_DOWEL_PILOT_TEXT}")
    # The cluster and the pin it runs on exist before the plate is set.
    for key in ("disc-cluster-assembled", "disc-taps-transferred", "pin-pressed"):
        assert steps.step_number(key) < steps.step_number("arm-plate-located")
    # A cluster or pin remedy that repeats from the latch pin never repeats
    # the disc's one-time tap transfer.
    assert steps.step_number("disc-taps-transferred") < steps.step_number(
        "latch-pin-pressed"
    )
    # The plate is tapped to its DETAIL K setting before the trial; the trial
    # may move it once, within DETAIL K's limits (owner ruling 2026-11-24,
    # audit part 2 question C1); S and N are proven unmoved before the pilots.
    assert located.rindex("TAP THE PLATE") < trial
    recheck = located[lifted:]
    assert "S READS TRUE AT THE DRO'S ZERO" in recheck
    assert f"KNOB BORE {drawing.KNOB_BORE_LETTER} AT THE TABLE'S SETTING" in recheck
    assert "CLAMP THE ARM FRONT UP ON PARALLELS ON THE MILL TABLE" in located
    # The setting is made where the mesh is: S is indicated at the disc's height.
    assert "PIN BORE S, AT THE HEIGHT THE DISC WILL RUN" in located
    # A failed trial inspects the gears and the two running fits the window
    # charges before it blames the arm.
    assert (
        f"{_number('pd-transgear-knob-shaft')} JOURNAL AND "
        f"{_number('pd-transgear-knob-bush')} AND "
        f"{_number('pd-transgear-feed-pinion')} BORES TO THEIR SHEETS."
        in located
    )
    # #2629: the trial's pass exit, then its one move, then the inspection.
    assert (
        f"IF {drawing.sub_step('arm-plate-located', 11)} AND "
        f"{drawing.sub_step('arm-plate-located', 12)} PASSED, GO TO STEP "
        f"{steps.step_number('arm-plate-fitted')}." in located
    )
    assert located.index("PASSED, GO TO STEP") < located.index(
        f"MOVE THE TABLE TOWARD S BY THE TRIAL MOVE {drawing.row_cite('trial-move')}"
    ) < located.index("IF NOT, INSPECT")
    # The restart follows the part, one sub-step each: a new plate is set
    # again from 12A, a new disc or sleeve is centred again; a new disc,
    # sleeve or shaft is tried with the table back at DETAIL K's setting,
    # never at a move made for the part it replaced (Codjiflo r2 on #3539).
    retrial = f"REPEAT FROM {drawing.sub_step('arm-plate-located', 4)}."
    located_texts = drawing._step_text(operating_domain=_unit_operating_domain())[
        "arm-plate-located"
    ]
    assert located_texts[4].startswith(
        f"SET THE TABLE TO {drawing.KNOB_SETTING_VIEW_NAME}'S "
    )
    for remedy in (
        f"REPLACE A {_number('pd-transgear-knob-bush')} BUSH FOUND OUTSIDE WITH A NEW BUSH AND "
        f"{_number('pd-transgear-arm-plate')} PLATE PER {drawing.sub_step('pin-pressed', 9)}-"
        f"{drawing.sub_step('pin-pressed', 18)} AND REPEAT FROM "
        f"{drawing.sub_step('arm-plate-located', 0)}.",
        "REPLACE A DISC FOUND OUTSIDE THROUGH "
        f"{drawing.sub_step('disc-cluster-assembled', 2)}-"
        f"{drawing.sub_step('disc-taps-transferred', 17)} ON THE SAME HUB, ITS "
        f"{_number('pd-vn-transgear-hub-key-pin')} PIN RIDING THE FLAT, AND {retrial}",
        f"REPLACE A {_number('pd-transgear-feed-pinion')} FOUND OUTSIDE: SLIDE THE HUB "
        "AND DISC OFF IT AS ONE, THE PIN RIDING THE FLAT, THE DISC SCREWS "
        "SLACKENED, REPEAT "
        f"{drawing.sub_step('disc-cluster-assembled', 3)}-"
        f"{drawing.sub_step('disc-cluster-assembled', 4)}, "
        f"{drawing.sub_step('disc-taps-transferred', 0)}-"
        f"{drawing.sub_step('disc-taps-transferred', 2)}, "
        f"{drawing.sub_step('disc-taps-transferred', 9)} AND "
        f"{drawing.sub_step('disc-taps-transferred', 12)}-"
        f"{drawing.sub_step('disc-taps-transferred', 17)} ON A NEW ONE, THEN FROM "
        f"{drawing.sub_step('arm-plate-located', 4)}.",
        f"REPLACE A {_number('pd-transgear-knob-shaft')} FOUND OUTSIDE AND {retrial}",
    ):
        assert remedy in located
    assert f"IF ALL ARE INSIDE, UNCLAMP AND REPEAT FROM STEP {steps.step_number('latch-pin-pressed')}" in located
    assert len(drawing._step_text(operating_domain=_unit_operating_domain())["arm-plate-located"]) <= len(
        drawing.SUB_STEP_LETTERS
    )
    fitted = _step_body("arm-plate-fitted")
    assert "AS 12M AND 12N" in fitted
    # Owner ruling 2026-11-20 (Pedro), #2497: the arm already carries the
    # DETAIL K jig-boring, so a dowel that slides in is bonded, not scrapped.
    assert "BOND IT PER THE BOND NOTE AT DETAIL H" in " ".join(fitted.split())
    assert "ARM CLAMPED FRONT UP ON THE SAME PARALLELS" in fitted
    # A failed doweled re-read is cleaned and read again before the set is
    # scrapped, each its own sub-step.
    assert fitted.index("CLEAN THE TEETH AND SEATS AND REPEAT") < fitted.index("IF A CHECK STILL FAILS")
    assert fitted.index("IF A CHECK STILL FAILS") < fitted.rindex(f"NEW {_number('pd-transgear-arm')} ARM")
    # The doweled re-read comes before anything irreversible on the arm.
    for key in ("hanger-pivoted", "knob-stack-fitted", "hook-pin-hole-match-drilled"):
        assert steps.step_number("arm-plate-fitted") < steps.step_number(key)
    # The final confirmation reads the same way. Its remedies try the plate's
    # seat, a clean, a knob stack and a disc first; the arm is rebuilt only
    # for a fault that is the same all round, the last branch.
    pose = _step_body("fitup-mesh-remedied")
    assert f"THE DISC SHAKES {drawing.REDUCER_BACKLASH_DIAL_TEXT} AS " in " ".join(
        _step_body("fitup-pose-set").split()
    )
    assert len(drawing._step_text(operating_domain=_unit_operating_domain())["fitup-pose-set"]) == 10
    rebuild = pose.index("FOR A FAULT ALL ROUND (ARM SETTING)")
    assert pose.index(f"NEW {_number('pd-transgear-arm')} ARM") > rebuild
    for part, name in (("pd-transgear-arm-plate", "PLATE"), ("pd-latch-hook", "HOOK")):
        assert f"{_number(part)} {name}," in pose[rebuild:]
    assert (
        pose.index("FOR A FAULT ONCE A DISC TURN (A DISC TOOTH)")
        < pose.index("FOR A LOOSE PLATE OR A FAULT EVERY KNOB TURN")
        < rebuild
    )
    # The turn only finds the period; nothing on the rebuild is staked.
    assert "TURN THE DISC ONE TURN BY THE COLLAR, NOTING WHERE IT FAULTS." in pose
    assert "STAKING" not in pose
    assert f"DO {drawing.sub_step('hanger-pivoted', 15)}-{drawing.sub_step('hanger-pivoted', 16)}." in pose[rebuild:]
    # A new disc takes new screws, cut again to its own rear face, on the
    # same hub, its key pin left in (#2409).
    assert (
        f"A NEW {_number('pd-rack-pinion')} DISC AND NEW "
        f"{drawing._N[explode.DISC_SCREW]} SCREWS ON THE SAME HUB, ITS PIN LEFT "
        f"IN AND RIDING THE FLAT, THEN STEPS {steps.step_number('disc-screws-cut')}, "
    ) in pose


def test_the_hub_key_pin_and_collar_flat_pin_are_fitted_and_kept() -> None:
    """#2409: the hub is keyed by a pin pressed along a chord of it to its
    stop before the hub is fitted, its side over the sleeve's flat; every
    remedy slides hub and disc off the nose and back with the pin riding the
    flat, the pin never out of the hub; the collar's flat pin is pressed with
    the drive dowels, one permanent unit with the collar, and its crest is
    broken with the collar's rear bore mouth after facing."""
    texts = drawing._step_text(operating_domain=_unit_operating_domain())
    key_pin = _number("pd-vn-transgear-hub-key-pin")
    assert key_pin == drawing.hub.KEY_PIN_NUMBER
    assembled = texts["disc-cluster-assembled"]
    press = next(
        i for i, row in enumerate(assembled) if row.startswith(f"PRESS THE {key_pin} PIN")
    )
    fit = next(
        i
        for i, row in enumerate(assembled)
        if f"BORE ON THE {_number('pd-transgear-feed-pinion')} BOSS" in row
    )
    assert press < fit
    assert "CROSS HOLE" in assembled[press] and assembled[press].endswith("UNTIL IT STOPS.")
    assert assembled[press + 1].startswith("IF THE PIN SLIDES IN BY HAND, MAKE A NEW")
    assert "FROM THE NOSE, THE PIN OVER THE FLAT" in assembled[fit]
    assert assembled[-1].startswith("CHECK:")
    assert "HUB DRIVES THE SLEEVE" in assembled[-1]
    # No step re-pins: the knob cup's cross pin is retired (#2425) and the
    # hub key pin is never renewed in place.
    assert not any(
        "DRIVEN INWARD" in row or "NEW PIN" in row
        for rows in texts.values()
        for row in rows
    )
    assert len(texts["oil-hole-drilled"]) == 1
    for key in ("fitup-mesh-remedied", "collar-disc-air-inspected"):
        rows = texts[key]
        slide = next(i for i, row in enumerate(rows) if "SLIDE THE HUB AND DISC" in row)
        assert "NOSE AS ONE" in rows[slide] and "PIN RIDING THE FLAT" in rows[slide], key
        assert not any("BACK THE" in row or "SET SCREW" in row for row in rows), key
        assert not any("STAKING FRESH METAL AS" in row for row in rows), key
    refit = texts["collar-disc-air-inspected"]
    assert any(
        row.startswith("SLIDE THE HUB'S BORE BACK ON THE BOSS") and "PIN RIDING THE FLAT" in row
        for row in refit
    )
    pressed = texts["collar-pins-pressed"]
    pin = _number("pd-vn-transgear-collar-flat-pin")
    assert pin == collar.FLAT_PIN_NUMBER
    # The pin is pressed on the collar's traveler (MHA-PD-08's D-flat is
    # milled to it before the shaft is first used); the step checks it.
    assert not any(row.startswith(f"PRESS THE {pin} PIN") for row in pressed)
    check = next(row for row in pressed if row.startswith(f"CHECK: THE {pin} PIN"))
    assert "DOES NOT MOVE BY HAND" in check
    assert check.endswith("COLLAR AND PIN ARE ONE PERMANENT UNIT.")
    assert pressed[pressed.index(check) + 1].startswith("IF THE PIN MOVES, ")
    from pathlib import Path

    plan = (
        Path(__file__).resolve().parent.parent
        / "process" / "pd_transgear_drive_collar" / "plan.toml"
    ).read_text(encoding="utf-8")
    assert f"Press the {pin} pin into the flat pin's hole" in plan
    assert len(pressed) <= len(drawing.SUB_STEP_LETTERS)
    # A dowel that slides in by hand is rule 23's slip fit: the collar is
    # renewed, never bonded (the reamed holes print no band, so no bonded
    # clearance could be stated: Codjiflo P2 on #3485).  The three
    # wheels are then tried on the dowels, the drive-pin offsets'
    # acceptance; a wheel that binds is renewed, no easing drill printed.
    loose = [row for row in pressed if "SLIDES IN BY HAND" in row]
    assert len(loose) == 1
    assert all("BOND" not in row for row in pressed)
    wheel = _number("pd-transgear-removable")
    trial = next(row for row in pressed if row.startswith("CHECK: EACH OF THE"))
    assert f"EACH OF THE 3 {wheel} WHEELS DROPS ON" in trial
    at = pressed.index(trial)
    assert pressed[at + 1] == "IF ONE WHEEL BINDS, RENEW IT."
    step = steps.step_number("collar-pins-pressed")
    assert pressed[at + 2] == f"IF NO WHEEL BINDS, GO TO STEP {step + 1}."
    # Every collar renewal re-fits or renews MHA-PD-08, whose core and
    # D-flat were made to the old collar (Codjiflo P2 on #3485): one block
    # of single actions, which the four remedies cite.
    shaft_no = _number("pd-transgear-knob-shaft")
    block = pressed[at + 3 :]
    assert len(block) == 5
    assert block[0].endswith(f"MAKE A NEW {_number('pd-transgear-drive-collar')} COLLAR.")
    assert block[1].startswith(f"CHECK: THE NEW COLLAR SLIDES ON THE {shaft_no} SHAFT'S CORE")
    assert "NO SHAKE" in block[1] and "PIN ON THE D-FLAT" in block[1]
    assert block[2].startswith("IF IT BINDS, CUT THE SHAFT'S CORE AND D-FLAT TO THE NEW COLLAR")
    assert block[3] == f"IF IT SHAKES, MAKE A NEW {shaft_no} SHAFT TO THE NEW COLLAR."
    assert block[4] == f"REPEAT FROM {step}A WITH THE NEW COLLAR."
    letters = drawing.SUB_STEP_LETTERS
    cite = f"RENEW THE COLLAR PER {step}{letters[at + 3]}-{step}{letters[len(pressed) - 1]}."
    assert loose[0].endswith(cite)
    assert pressed[pressed.index(check) + 1].endswith(cite)
    assert texts["pilot-faced-to-fit"][-1].endswith(cite)
    assert not any(
        "MAKE A NEW" in row and "COLLAR AND REPEAT" in row
        for rows in texts.values()
        for row in rows
    )
    rear = texts["collar-rear-faced-to-fit"]
    new = next(i for i, row in enumerate(rear) if row.endswith("MAKE A NEW " + block[0].split("MAKE A NEW ")[1]))
    assert rear[new + 1] == f"CHECK THE NEW COLLAR ON THE SHAFT AS {step}{letters[at + 4]}."
    assert all(row.startswith("IF IT BINDS OR SHAKES, ") for row in rear[new + 2 : new + 5])
    assert "CUP OFF AS" in rear[new + 2] and "SHAFT OUT FORWARD" in rear[new + 3]
    assert rear[new + 4].endswith(f"DO {step}{letters[at + 5]}-{step}{letters[at + 6]}.")
    assert rear[-1].startswith(f"REPEAT FROM STEP {step} WITH THE NEW COLLAR")
    assert all("RE-DRILL" not in row for row in pressed)
    # The pin rides the collar off the shaft, then (drawn apart only) leaves
    # its blind ream the way it went in, rearward out of the open end, before
    # any other move, so sheet 3's isometric can show it.
    pin_stem = "pd-vn-transgear-collar-flat-pin"
    own = [step for step in explode.TRANSGEAR_STEPS if step.stems == (pin_stem,)]
    riding = next(
        i for i, step in enumerate(explode.TRANSGEAR_STEPS)
        if pin_stem in step.stems and "pd-transgear-drive-collar" in step.stems
    )
    assert own and explode.TRANSGEAR_STEPS.index(own[0]) > riding
    assert own[0].axis == "z" and own[0].distance_mm > collar.FLAT_PIN_LENGTH
    faced = texts["collar-rear-faced-to-fit"]
    face = next(i for i, row in enumerate(faced) if row.startswith("FACE THE COLLAR'S REAR"))
    assert faced[face + 1].startswith("BREAK THE COLLAR'S REAR BORE MOUTH 45°")
    assert f"THROUGH THE {pin} PIN'S CREST" in faced[face + 1]
    bom = dict(drawing.BOM_PART_NUMBERS)
    assert bom["pd-vn-transgear-hub-key-pin"] == key_pin
    assert bom["pd-vn-transgear-collar-flat-pin"] == pin
    assert drawing.TRANSGEAR_QUANTITIES["pd-vn-transgear-hub-key-pin"] == 1
    assert drawing.TRANSGEAR_QUANTITIES["pd-vn-transgear-collar-flat-pin"] == 1


def test_the_trial_stack_goes_together_at_the_located_step() -> None:
    """The trial's parts as they stand at steps 12 and 13, from the specs:
    heights are forward of the arm's rear face, the arm front up."""
    plate = drawing.plate_geometry
    arm_front = steps_arm.THICKNESS
    # The cluster with no shims, on the rear bushing on the arm's face.
    sleeve_rear = arm_front + cluster_fit.REAR_BUSHING_LENGTH
    disc_front = sleeve_rear + feed_pinion.DISC_FRONT_STATION
    disc_rear = disc_front - disc.FACE_WIDTH
    # The knob shaft's 15T on the loose ring on the bush's hub face (#2425).
    pinion_rear = knob_bush.HUB_LENGTH + cluster_fit.KNOB_RING.LENGTH
    pinion_front = pinion_rear + knob_shaft.FACE_WIDTH
    slack = cluster_fit.F_BAND + cluster_fit.UNSHIMMED_FLOAT_BAND
    assert pinion_rear + slack < disc_rear and disc_front + slack < pinion_front
    # Nothing stands up into the disc: its own uncut screw tips over the
    # arm's face (they are cut at a later step), and at step 13 the uncut
    # plate screws, one of which lies inside the disc's tips.
    assert drawing.disc_screw.STOCK_TIP_PROUD_MAX + slack < disc_rear - arm_front
    screw_tip = drawing.plate_screw.STOCK_LENGTH - (
        plate.THICKNESS_OVER_ARM - plate.THICKNESS_OVER_ARM_BAND
    )
    tip_radius = max(profile.blank_radius_mm for profile in disc.manufactured_profiles())
    assert min(
        abs(steps_arm.PIN_STATION - station) for station in steps_arm.PLATE_TAP_STATIONS
    ) < tip_radius
    assert screw_tip + slack < disc_rear
    # The pin's head and the plate's rear end clear the plate and each
    # other; the shaft's rear end, the lowest point, hangs inside the shop's
    # 1 in parallels (archived parallels-lms-6745; shop-equipment: the set stops at 1 in).
    plate_edges = (
        steps_arm.KNOB_BORE_STATION + plate.EDGE_MINUS_X,
        steps_arm.KNOB_BORE_STATION + plate.EDGE_PLUS_X,
    )
    assert max(plate_edges) + cluster_fit.PIN.HEAD_DIA / 2.0 < steps_arm.PIN_STATION
    shaft_drop = knob_shaft.JOURNAL_LENGTH - cluster_fit.KNOB_RING.LENGTH - knob_bush.HUB_LENGTH
    assert knob_bush.STUB_LENGTH < shaft_drop < 25.4
    # The clamps: the plate's edge nearest the pivot bore lies over the arm
    # a clamp jaw's width (3/8 in) outside the disc's tips; the pilots lie
    # inside them, so the stack comes off before they are drilled.
    assert steps_arm.PIN_STATION - min(plate_edges) - tip_radius >= 0.375 * 25.4
    for site in steps_arm.LOCATOR_SITES_MM:
        assert math.dist(site, (steps_arm.PIN_STATION, 0.0)) < tip_radius
    # The knob bore stands off the arm, so its indicator and the shaft reach
    # it from the front.
    assert abs(steps_arm.KNOB_BORE_OFFSET) - knob_bush.HUB_DIA / 2.0 > steps_arm.edge_half_width(
        steps_arm.KNOB_BORE_STATION
    )


def test_the_feed_mesh_stays_on_the_hook_run_and_passes_its_closed_form_gates() -> None:
    assert assembly.RACK_MESH_EXT == pytest.approx(feed_pinion.RACK_MESH_EXTENSION)
    assert rack_setup.RACK_DATUM_BACKLASH_RANGE == feed_pinion.RACK_BACKLASH_RANGE
    height = assembly.RACK_PITCH_Y - assembly.STUD_XY[1]
    assert height == pytest.approx(feed_pinion.RACK_AXIS_DISTANCE)
    low, high = rack_setup.RACK_DATUM_MODEL_AXIS_DISTANCE_RANGE
    assert low < height < high
    # A mesh change at the stud turns the hanger about P: the pin crosses the
    # hook's straight run by the change over the stud's lever, and the
    # match-drilled hole with its wall must stay on that run.
    hook_geometry = assembly.HOOK
    lever = hook_geometry.HOLE_STATION / (
        assembly.ARM.PIN_STATION * math.cos(math.radians(assembly.ARM_ANGLE_DEG))
    )
    room = hook_geometry.PIN_HOLE_DIA / 2.0 + assembly.HOOK_SPEC.WALL_TARGET
    for end in (low, high):
        shift = abs(end - height) * lever
        assert shift + room < hook_geometry.RUN_ABOVE_HOLE
        assert shift + room < hook_geometry.RUN_BELOW_HOLE
    assert assembly._assert_rack_mesh() == rack_setup.feed_rack_operating_domain()


def test_the_native_feed_mesh_rejects_a_height_outside_its_actual_datum(monkeypatch) -> None:
    height = rack_setup.RACK_DATUM_MODEL_AXIS_DISTANCE_RANGE[1] + feed_pinion.MODULE_MM
    monkeypatch.setattr(assembly, "RACK_MESH_EXT", height - feed_pinion.PITCH_DIA / 2.0)
    monkeypatch.setattr(assembly, "RACK_PITCH_Y", assembly.STUD_XY[1] + height)
    with pytest.raises(ValueError):
        assembly._assert_rack_mesh()


def test_a_direct_datum_reader_cannot_widen_the_design_setup_band() -> None:
    low, high = rack_setup.RACK_DATUM_BACKLASH_RANGE
    span = high - low
    with pytest.raises(ValueError, match="datum setup band leaves"):
        rack_setup.require_feed_rack_datum_axis_distance(
            feed_pinion.RACK_AXIS_DISTANCE, (low - span, high + span)
        )


def test_note_formatting_is_explicit_about_its_supplied_window() -> None:
    domain = _unit_operating_domain()
    notes = drawing.format_step_notes(operating_domain=domain)
    window = steps.inch_window(domain.axis_from_left_end_limits_mm, 3, " TO ")
    assert window in drawing.engaged_feed_text(domain)
    assert drawing.engaged_feed_text(domain) in _step_body("hanger-meshed")
    assert notes.columns == drawing.pack_step_columns(
        drawing._step_text(operating_domain=domain)
    )
    assert drawing.sheet_texts(notes)[: len(notes.columns)] == tuple(
        column.text for column in notes.columns
    )


def test_drawing_notes_print_the_window_checked_against_the_paper_sweep() -> None:
    notes = drawing.require_step_notes()
    assert notes == drawing.format_step_notes(operating_domain=rack_setup.feed_rack_operating_domain())


@pytest.mark.parametrize(
    ("recording", "message"),
    (
        (
            {
                "paper_left_inset_band_mm": (10.0, 10.0),
                "paper_width_band_mm": (300.0, 300.0),
                "pen_x_from_running_axis_band_mm": (0.0, 0.0),
            },
            "required paper stroke",
        ),
        (
            {
                "paper_left_inset_band_mm": (255.0, 255.0),
                "paper_width_band_mm": (20.0, 20.0),
                "pen_x_from_running_axis_band_mm": (0.0, 0.0),
            },
            "cut-end overrun",
        ),
    ),
)
def test_the_notes_refuse_a_paper_sweep_the_finite_rack_cannot_carry(
    recording, message, monkeypatch,
) -> None:
    monkeypatch.setattr(paper_geometry, "recording_paper_sweep_bands_mm", lambda: recording)
    with pytest.raises(ValueError, match=message):
        drawing.require_step_notes()


def _native_pd_component(name, stem, configuration, *, origin=None):
    transform = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
    transform.extend(value / 1000.0 for value in (origin or (0.0, 0.0, 0.0)))
    return SimpleNamespace(
        Name2=name,
        GetPathName=lambda: f"C:/native/{stem}.SLDPRT",
        ReferencedConfiguration=configuration,
        ComponentReference="",
        Transform2=SimpleNamespace(ArrayData=transform),
    )


_PD_NATIVE_PART_WIDTH = 0.046824451973134076


def _pd_bom_fixture(monkeypatch, *, native_columns=False):
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, *_args: obj)
    monkeypatch.setattr(_com, "_early_bound", lambda obj, *_args: obj)
    monkeypatch.setattr(_component_references, "_early_bound", lambda obj, *_args: obj)
    monkeypatch.setattr(
        _drawing_tables._sw_type_info, "early_bound_or_flag", lambda obj, *_args: obj
    )
    quantities = {
        key: 1 for key in drawing.BOM_COMPONENT_IDENTITIES
    } | drawing.TRANSGEAR_QUANTITIES | drawing.CHAIN_QUANTITIES | drawing.PLATEN_QUANTITIES
    quantities["sh-vn-brass-fillister-screw"] = len(assembly.GUIDE_SCREW_XY)
    quantities["sh-vn-clamp-screw"] = len(assembly.CLAMP_HOLE_X)
    components_by_key = {}
    for key, (stem, member) in drawing.BOM_COMPONENT_IDENTITIES.items():
        configurations = (
            (sprocket.KNOB_CONFIG, sprocket.CRANK_CONFIG, "T18")
            if key == "pd-transgear-removable" else
            (member or "Default",) * quantities[key]
        )
        components_by_key[key] = [
            _native_pd_component(
                f"native-{key}-{index + 100}", stem, f"{configuration} Simplified"
            )
            for index, configuration in enumerate(configurations)
        ]
        number = drawing.BOM_PART_NUMBERS[key]
        properties = {
            (component.ReferencedConfiguration, "Number"): number
            for component in components_by_key[key]
        } | {("", "Number"): number}
        native_configurations = {
            component.ReferencedConfiguration: SimpleNamespace(
                BOMPartNoSource=8,
                AlternateName=member or stem,
                UseAlternateNameInBOM=True,
                Description=drawing.BOM_DESCRIPTIONS[key],
                UseDescriptionInBOM=key == "pd-transgear-removable",
            )
            for component in components_by_key[key]
        }
        # Both assembly configurations address real members of the same files.
        # Switching BOM membership must not mutate the source occurrences.
        for member_name, configuration_info in tuple(native_configurations.items()):
            native_configurations[member_name.removesuffix(" Simplified")] = configuration_info
            properties[(member_name.removesuffix(" Simplified"), "Number")] = number
        native = SimpleNamespace(
            properties=properties,
            configurations=native_configurations,
            GetCustomInfoValue=lambda selected, property_name, values=properties: (
                values.get((selected, property_name), "")
            ),
            GetConfigurationByName=native_configurations.get,
            # The drawing's views load the simplified members (native PD evidence).
            active_configuration=components_by_key[key][0].ReferencedConfiguration,
            written=[],
        )
        for component in components_by_key[key]:
            component.GetModelDoc2 = lambda native=native: native
            component.GetSuppression2 = lambda: 2
            exclusions = {
                (3, (configuration,)): False
                for configuration in ("Default", drawing.SIMPLIFIED_VIEW_CONFIGURATION)
            }
            component.exclusions = exclusions
            component.GetExcludeFromBOM2 = (
                lambda option, names, values=exclusions: (values[(option, tuple(names))],)
            )
    components = [
        component for group in components_by_key.values() for component in group
    ]
    model = SimpleNamespace(GetComponents=lambda _top_only: tuple(components))
    # Reversed, except that the four shared-Number rows sit at the items the
    # steps print (the native order puts them there).
    keys = [
        key
        for key in reversed(drawing.BOM_PART_NUMBERS)
        if key not in drawing.SHARED_NUMBER_ITEMS
    ]
    for key, item in sorted(
        drawing.SHARED_NUMBER_ITEMS.items(), key=lambda pair: pair[1]
    ):
        keys.insert(item - 1, key)
    keys = tuple(keys)
    cells = [["ITEM NO.", "PART NUMBER", "DESCRIPTION", "QTY."]]
    native_rows = [components_by_key[key] for key in keys]
    for row, key in enumerate(keys, 1):
        component = native_rows[row - 1][0]
        native = component.GetModelDoc2()
        cells.append([
            str(row),
            native.GetConfigurationByName(component.ReferencedConfiguration).AlternateName,
            drawing.BOM_DESCRIPTIONS[key],
            str(quantities[key]),
        ])
    columns = [
        SimpleNamespace(
            kind=202, property_name="", raw_property_data="", hidden=False, width=0.025
        ),
        SimpleNamespace(
            kind=201, property_name="", raw_property_data="", hidden=False,
            width=_PD_NATIVE_PART_WIDTH,
        ),
        SimpleNamespace(
            kind=204, property_name="Description", raw_property_data="Description",
            hidden=False, width=0.025,
        ),
        SimpleNamespace(
            kind=203, property_name="", raw_property_data="", hidden=False, width=0.045
        ),
    ]
    table = MagicMock()
    table.Type = 2
    available = ("Default", drawing.SIMPLIFIED_VIEW_CONFIGURATION)
    members_by_configuration = {
        drawing.SIMPLIFIED_VIEW_CONFIGURATION: tuple(native_rows),
        "Default": tuple([
            SimpleNamespace(**(vars(component) | {
                "ReferencedConfiguration": component.ReferencedConfiguration.removesuffix(" Simplified"),
            }))
            for component in group
        ] for group in native_rows),
    }
    state = SimpleNamespace(
        columns=columns, native_rows=native_rows, row_keys=list(keys), cells=cells,
        hidden_rows=set(), requested_heights={}, materialized=[], quantity=columns[3],
        configuration=drawing.SIMPLIFIED_VIEW_CONFIGURATION,
        members_by_configuration=members_by_configuration,
    )

    def set_configurations(only_visible, flags, names):
        flags, names = tuple(flags), tuple(names)
        if (
            type(only_visible) is not bool
            or len(flags) != len(names)
            or any(type(flag) is not bool for flag in flags)
            or sum(flags) != 1
        ):
            return False
        if only_visible:
            # Split fixtures may select a single visible configuration directly.
            if len(names) != 1 or names[0] not in available:
                return False
        elif len(names) != len(available) or set(names) != set(available):
            return False
        selected = next(name for name, visible in zip(names, flags, strict=True) if visible)
        native_rows[:] = members_by_configuration[selected]
        state.configuration = selected
        # Native quantities follow eligible occurrences, not a caller's cell writes.
        for index, column in enumerate(columns):
            if column.kind == 203:
                for row, group in enumerate(native_rows, 1):
                    cells[row][index] = str(len(group))
        return True

    table.BomFeature = SimpleNamespace(
        PartConfigurationGrouping=3, DisplayAsOneItem=False, TableType=2,
        SetConfigurations=set_configurations,
        GetConfigurationCount=lambda only_visible: 1 if only_visible else 2,
        GetConfigurations=lambda only_visible, _visibility: (
            ((state.configuration,), (True,)) if only_visible else
            (available, tuple(name == state.configuration for name in available))
        ),
    )
    table._pd_state = state
    type(table).RowCount = PropertyMock(side_effect=lambda: len(cells))
    type(table).TotalRowCount = PropertyMock(side_effect=lambda: len(cells))
    type(table).ColumnCount = PropertyMock(
        side_effect=lambda: sum(not column.hidden for column in columns)
    )
    type(table).TotalColumnCount = PropertyMock(side_effect=lambda: len(visibility_domain()))

    def visibility_domain():
        """Native 0-based ColumnHidden domain: one Quantity column per configuration.

        Deselected configurations' Quantity columns stay latent: earlier ones sit
        just before the selected Quantity, later ones after the last typed column.
        """
        selected = available.index(state.configuration)
        latent = [
            name for name in available
            if name != state.configuration and name not in state.materialized
        ]
        before = [("latent", name) for name in latent if available.index(name) < selected]
        after = [("latent", name) for name in latent if available.index(name) > selected]
        domain = []
        for column in columns:
            if column is state.quantity:
                domain.extend(before)
                before = []
            domain.append(("column", column))
        return domain + before + after

    def raw_index(index, include_hidden):
        indices = (
            list(range(len(columns))) if include_hidden else
            [i for i, column in enumerate(columns) if not column.hidden]
        )
        return indices[index] if 0 <= index < len(indices) else None

    def column_type(index, include_hidden):
        physical = raw_index(index, include_hidden)
        if physical is None:
            # Native PD 2291: identical empty signature at every invalid index.
            return -1, None, 0
        column = columns[physical]
        return column.kind, column.raw_property_data or None, 0

    def displayed_text(row, index, include_hidden):
        physical = raw_index(index, include_hidden)
        return "" if physical is None else cells[row][physical]

    def row_hidden(row):
        if type(row) is not int or not 0 <= row < len(cells):
            raise IndexError(row)
        return row in state.hidden_rows

    def custom_property(index):
        if not 0 <= index < len(columns) or columns[index].kind != 204:
            return ""
        return columns[index].property_name

    def linked_text(group, property_name):
        values = set()
        for component in group:
            native = component.GetModelDoc2()
            configuration = (
                native.GetConfigurationByName(component.ReferencedConfiguration)
                if property_name == "Description"
                else None
            )
            values.add(str(
                configuration.Description
                if configuration is not None and configuration.UseDescriptionInBOM
                else (
                    native.GetCustomInfoValue(
                        component.ReferencedConfiguration, property_name
                    )
                    or native.GetCustomInfoValue("", property_name)
                    or ""
                )
            ).strip())
        return "; ".join(sorted(values))

    def bind_property(index, property_name):
        for row, group in enumerate(native_rows, 1):
            cells[row][index] = linked_text(group, property_name)

    def set_custom_property(index, property_name):
        if not 0 <= index < len(columns) or columns[index].kind != 204:
            return False
        column = columns[index]
        column.property_name = property_name
        column.raw_property_data = f'$PRP:"{property_name}"' if property_name else ""
        cells[0][index] = property_name
        bind_property(index, property_name)
        return True

    def move_column(source, where, destination):
        if where not in (2, 3):
            return False
        if not (0 <= source < len(columns) and 0 <= destination < len(columns)):
            return False
        insertion = destination + (where == 3) - (source < destination)
        columns.insert(insertion, columns.pop(source))
        for row in cells:
            row.insert(insertion, row.pop(source))
        return True

    def insert_column(where, index, name, width_style):
        if width_style != 0 or where not in (2, 3):
            return False
        if not 0 <= index < len(columns):
            return False
        insertion = index + (where == 3)
        # Native 2352 inserts an already user-defined/custom-property column.
        columns.insert(
            insertion,
            SimpleNamespace(
                kind=204, property_name="", raw_property_data="", hidden=False,
                width=columns[index].width,
            ),
        )
        for row in cells:
            row.insert(insertion, name if row is cells[0] else "")
        return True

    def hide_column(index, hidden):
        if type(index) is not int:
            raise IndexError(index)
        if type(hidden) is not bool:
            raise TypeError(hidden)
        domain = visibility_domain()
        if not 0 <= index < len(domain):
            raise IndexError(index)
        role, target = domain[index]
        if role == "column":
            target.hidden = hidden
            # ITableAnnotation.SetColumnHidden is VOID, not a success flag.
            return None
        # Native v45 PD: writing a latent Quantity materializes it as a typed column.
        position = sum(entry_role == "column" for entry_role, _target in domain[:index])
        columns.insert(position, SimpleNamespace(
            kind=203, property_name="", raw_property_data="", hidden=hidden, width=0.0,
            latent_configuration=target,
        ))
        state.materialized.append(target)
        for row_index, row in enumerate(cells):
            row.insert(position, "QTY." if row_index == 0 else str(
                len(members_by_configuration[target][row_index - 1])
            ))
        return None

    def column_hidden(index):
        domain = visibility_domain()
        if type(index) is not int or not 0 <= index < len(domain):
            return False
        role, target = domain[index]
        return target.hidden if role == "column" else False

    def set_column_type(index, kind, include_hidden, property_name):
        index = raw_index(index, include_hidden)
        if index is None:
            return 1  # swColumnTypeStatus_InvalidIndex
        previous = columns[index].kind
        columns[index].kind = kind
        columns[index].property_name = property_name if kind == 204 else ""
        columns[index].raw_property_data = (
            f'$PRP:"{property_name}"' if kind == 204 and property_name else ""
        )
        if previous == 201 and not any(column.kind == 201 for column in columns):
            # Native seat evidence: destroying the final PartNumber column
            # immediately deletes this grouped row and its native associations.
            row = state.row_keys.index("pd-transgear-removable")
            cells.pop(row + 1)
            native_rows.pop(row)
            state.row_keys.pop(row)
        if kind == 204 and property_name:
            bind_property(index, property_name)
        return 0

    def set_column_title(index, title, include_hidden):
        physical = raw_index(index, include_hidden)
        if physical is None:
            return False
        cells[0][physical] = title
        return True

    def set_text(row, index, include_hidden, text):
        physical = raw_index(index, include_hidden)
        if physical is None:
            raise IndexError(index)
        column = columns[physical]
        if row and column.kind == 204 and column.property_name:
            # Native PD 2026-10-23: a property-bound cell edit (even a bogus
            # property) writes into each part's active configuration; the
            # cell then re-reads its member's configuration.
            group = native_rows[row - 1]
            for native in {id(c.GetModelDoc2()): c.GetModelDoc2() for c in group}.values():
                native.properties[(native.active_configuration, column.property_name)] = text
                native.written.append((native.active_configuration, column.property_name))
            cells[row][physical] = linked_text(group, column.property_name)
            return
        cells[row][physical] = text


    def get_width(index):
        physical = raw_index(index, False)
        return 0.0 if physical is None else columns[physical].width

    def set_width(index, width, _options):
        # Widths are a separate unversioned API, never the visibility domain.
        physical = raw_index(index, False)
        if physical is None:
            raise IndexError(index)
        columns[physical].width = width
        return columns[physical].width

    def row_height(row):
        if type(row) is not int or not 0 <= row < len(cells):
            raise IndexError(row)
        return max(drawing.BOM_ROW_HEIGHT, state.requested_heights.get(row, 0.0))

    def set_row_height(row, height, _options):
        row_height(row)
        state.requested_heights[row] = height
        return row_height(row)

    table.MoveColumn.side_effect = move_column
    table.InsertColumn2.side_effect = insert_column
    table.SetColumnHidden.side_effect = hide_column
    table.ColumnHidden.side_effect = column_hidden
    table.GetColumnWidth.side_effect = get_width
    table.GetColumnType3.side_effect = column_type
    table.SetColumnType3.side_effect = set_column_type
    table.GetColumnCustomProperty.side_effect = custom_property
    table.SetColumnCustomProperty.side_effect = set_custom_property
    table.SetColumnTitle2.side_effect = set_column_title
    table.GetColumnTitle2.side_effect = lambda index, include_hidden: displayed_text(
        0, index, include_hidden
    )
    table.DisplayedText.side_effect = lambda row, column: displayed_text(row, column, False)
    table.Text2.side_effect = displayed_text
    table.DisplayedText2.side_effect = displayed_text
    table.RowHidden.side_effect = row_hidden
    table.IsCellTextEditable.return_value = True
    table.SetText2.side_effect = set_text
    table.SetColumnWidth.side_effect = set_width
    table.GetHeaderCount.return_value = 1
    table.GetRowHeight.side_effect = row_height
    table.SetRowHeight.side_effect = set_row_height
    table.GetComponents2.side_effect = lambda row, configuration: (
        native_rows[row - 1]
        if configuration == state.configuration else ()
    )
    if not native_columns:
        # Most consumer tests begin with the valid, already-bound final table.
        columns[1] = SimpleNamespace(
            kind=204, property_name="Number", raw_property_data='$PRP:"Number"',
            hidden=False, width=0.025,
        )
        columns.append(
            SimpleNamespace(
                kind=201, property_name="", raw_property_data="", hidden=False,
                width=_PD_NATIVE_PART_WIDTH,
            )
        )
        for row in cells:
            row.append(row[1])
        bind_property(1, "Number")
        hide_column(next(
            index for index, (_role, target) in enumerate(visibility_domain())
            if target is columns[-1]
        ), True)
    adapter = SimpleNamespace(currentModel=SimpleNamespace(EditRebuild3=lambda: True))
    return model, components, table, adapter, cells, keys


def test_source_census_distinguishes_chain_members_and_preserves_transgear_aggregation(monkeypatch):
    model, _components, table, adapter, _cells, keys = _pd_bom_fixture(monkeypatch)
    counts = drawing._source_family_counts(model)
    assert counts["sh-vn-chain-link--InnerLink"] == 33
    assert counts["sh-vn-chain-link--OuterLink"] == 32
    assert counts["pd-vn-chain-connecting-link"] == 1
    assert counts["pd-transgear-removable"] == 3
    items = dict(
        drawing._validate_bom(
            adapter, table, counts, configuration=drawing.SIMPLIFIED_VIEW_CONFIGURATION
        )
    )
    for key in ("sh-vn-chain-link--InnerLink", "sh-vn-chain-link--OuterLink", "pd-transgear-removable"):
        assert items[key] == str(keys.index(key) + 1)
    assert items["sh-vn-chain-link--InnerLink"] != items["sh-vn-chain-link--OuterLink"]
    table.SetText2.assert_not_called()


@pytest.mark.parametrize("row", (-1, BOM_ROWS, BOM_ROWS + 1))
def test_pd_native_row_visibility_refuses_nonexistent_rows(monkeypatch, row):
    _model, _components, table, _adapter, _cells, _keys = _pd_bom_fixture(monkeypatch)
    with pytest.raises(IndexError):
        table.RowHidden(row)


@pytest.mark.parametrize("fault", ("merged-members", "wrong-quantity", "internal-number", "blank-number"))
def test_bom_refuses_merged_chain_rows_or_noncanonical_numbers(monkeypatch, fault):
    model, _components, table, adapter, cells, keys = _pd_bom_fixture(monkeypatch)
    counts = drawing._source_family_counts(model)
    inner_row = keys.index("sh-vn-chain-link--InnerLink") + 1
    outer_row = keys.index("sh-vn-chain-link--OuterLink") + 1
    if fault == "merged-members":
        original = table.GetComponents2.side_effect
        table.GetComponents2.side_effect = lambda row, configuration: (
            original(inner_row, configuration) + original(outer_row, configuration)
            if row == inner_row else original(row, configuration)
        )
    elif fault == "wrong-quantity":
        cells[inner_row][3] = "67"
    else:
        cells[inner_row][1] = "" if fault == "blank-number" else "sh-vn-chain-link--InnerLink"
    with pytest.raises(RuntimeError):
        drawing._validate_bom(
            adapter, table, counts, configuration=drawing.SIMPLIFIED_VIEW_CONFIGURATION
        )
    table.SetText2.assert_not_called()


def test_bom_canonical_numbers_are_read_again_after_the_last_rebuild(monkeypatch):
    model, _components, table, adapter, cells, keys = _pd_bom_fixture(monkeypatch)
    counts = drawing._source_family_counts(model)
    inner_row = keys.index("sh-vn-chain-link--InnerLink") + 1

    def rebuild_with_stale_number():
        cells[inner_row][1] = "sh-vn-chain-link--InnerLink"
        return True

    adapter.currentModel.EditRebuild3 = rebuild_with_stale_number
    with pytest.raises(RuntimeError, match="BOM part number"):
        drawing._validate_bom(
            adapter, table, counts, configuration=drawing.SIMPLIFIED_VIEW_CONFIGURATION
        )
    table.SetText2.assert_not_called()


@pytest.mark.parametrize(
    ("fault", "message"),
    (
        ("swapped-chain-associations", "native associations changed"),
        ("missing-transgear-association", "has no native component association"),
        ("missing-spare-quantity", "BOM row.*changed"),
        ("missing-transgear-row", "dimensions changed"),
        ("grouping", "configuration grouping changed"),
        ("column-property", None),
        ("native-number", "associative Number"),
        ("changed-retained-native", "unique trailing native column"),
        ("unhidden-retained-native", "dimensions changed"),
        ("moved-retained-native", None),
    ),
)
def test_bom_rechecks_members_and_quantities_after_the_last_rebuild(
    monkeypatch, fault, message
):
    model, _components, table, adapter, cells, keys = _pd_bom_fixture(monkeypatch)
    counts = drawing._source_family_counts(model)
    inner_row = keys.index("sh-vn-chain-link--InnerLink") + 1
    outer_row = keys.index("sh-vn-chain-link--OuterLink") + 1
    transgear_row = keys.index("pd-transgear-removable") + 1
    native_components = table.GetComponents2.side_effect

    def rebuild_with_changed_bom():
        if fault == "swapped-chain-associations":
            # Both rows still print the same canonical purchase Number. A
            # Number-only readback cannot notice the wrong native attachment.
            table.GetComponents2.side_effect = lambda row, configuration: native_components(
                {inner_row: outer_row, outer_row: inner_row}.get(row, row),
                configuration,
            )
        elif fault == "missing-transgear-association":
            table.GetComponents2.side_effect = lambda row, configuration: (
                () if row == transgear_row else native_components(row, configuration)
            )
        elif fault == "missing-spare-quantity":
            cells[transgear_row][3] = "2"
        elif fault == "grouping":
            table.BomFeature.PartConfigurationGrouping = 2
        elif fault == "column-property":
            table._pd_state.columns[1].property_name = "Description"
        elif fault == "changed-retained-native":
            table._pd_state.columns[-1].kind = 202
        elif fault == "unhidden-retained-native":
            table._pd_state.columns[-1].hidden = False
        elif fault == "moved-retained-native":
            columns = table._pd_state.columns
            columns[3], columns[4] = columns[4], columns[3]
            for row in cells:
                row[3], row[4] = row[4], row[3]
        elif fault == "native-number":
            native = native_components(
                inner_row, drawing.SIMPLIFIED_VIEW_CONFIGURATION
            )[0].GetModelDoc2()
            native.GetCustomInfoValue = lambda *_: "WRONG-NATIVE-NUMBER"
        else:
            cells.pop(transgear_row)
            table.GetComponents2.side_effect = lambda row, configuration: native_components(
                row + (row >= transgear_row), configuration
            )
        return True

    adapter.currentModel.EditRebuild3 = rebuild_with_changed_bom
    with pytest.raises(RuntimeError, match=message):
        drawing._validate_bom(
            adapter, table, counts, configuration=drawing.SIMPLIFIED_VIEW_CONFIGURATION
        )
    table.SetText2.assert_not_called()


def _pd_bom_insertion_fixture(monkeypatch, *, configuration=None):
    model, components, table, adapter, cells, keys = _pd_bom_fixture(
        monkeypatch, native_columns=True
    )
    monkeypatch.setattr(_drawing_tables._sw_type_info, "early_bound", lambda obj, *_: obj)
    monkeypatch.setattr(_drawing_tables._sw_type_info, "is_early_bound", lambda *_: True)
    monkeypatch.setattr(_drawing_tables, "_activate_and_select_view", lambda *_, **__: None)
    monkeypatch.setattr(_drawing_tables, "bom_table_template", lambda _: "native.sldbomtbt")
    monkeypatch.setattr(_drawing_tables, "bool_array", tuple)
    monkeypatch.setattr(_drawing_tables, "bstr_array", tuple)
    adapter._get_attr_or_call = lambda obj, name: getattr(obj, name)
    adapter._attempt = lambda action: action()
    adapter.currentModel.ClearSelection2 = lambda _: None
    adapter.currentModel.ForceRebuild3 = lambda _: True
    view = SimpleNamespace(
        ReferencedConfiguration=drawing.SIMPLIFIED_VIEW_CONFIGURATION,
        InsertBomTable6=lambda *_: table,
    )

    def insert():
        return _drawing_tables.insert_bom_table(
            adapter,
            view,
            anchor_xy=drawing.BOM_ANCHOR,
            expected_components=tuple(drawing.BOM_PART_NUMBERS),
            descriptions=drawing.BOM_DESCRIPTIONS,
            component_identities=drawing.BOM_COMPONENT_IDENTITIES,
            part_number_property="Number",
            configuration_grouping="same-name",
            configuration=configuration,
            label="paper-drive",
        )

    return SimpleNamespace(
        model=model, components=components, table=table, adapter=adapter,
        cells=cells, keys=keys, state=table._pd_state, insert=insert, view=view,
    )


def test_native_visibility_fixture_keeps_property_text_and_width_domains_distinct(monkeypatch):
    scene = _pd_bom_insertion_fixture(monkeypatch)
    table = scene.insert()
    native = scene.state.columns[-1]
    quantity = scene.state.columns[3]
    assert (native.kind, native.hidden, native.width) == (201, True, _PD_NATIVE_PART_WIDTH)
    assert (quantity.kind, quantity.hidden, quantity.width) == (203, False, 0.045)
    assert table.GetColumnWidth(3) == quantity.width
    assert table.GetColumnWidth(4) == 0.0
    assert table.ColumnHidden(4) is False
    assert table.ColumnHidden(5) is True

    assert table.SetColumnHidden(5, False) is None
    assert table.GetColumnWidth(3) == 0.045
    assert table.GetColumnWidth(4) == _PD_NATIVE_PART_WIDTH
    for index in range(5):
        assert table.GetColumnType3(index, True) == table.GetColumnType3(index, False)
        assert table.GetColumnTitle2(index, True) == table.GetColumnTitle2(index, False)
        assert table.DisplayedText2(0, index, True) == table.DisplayedText2(0, index, False)
    assert table.SetColumnHidden(5, True) is None
    assert native.width == _PD_NATIVE_PART_WIDTH
    assert quantity.width == 0.045

    # Insertions inherit their physical neighbour's stored width.
    assert table.InsertColumn2(3, 2, "PURCHASE SKU", 0) is True
    assert scene.state.columns[3].width == scene.state.columns[2].width
    assert scene.state.columns[4] is quantity
    assert scene.state.columns[5] is native
    assert table.GetColumnWidth(4) == quantity.width
    assert table.GetColumnWidth(5) == 0.0
    assert table.ColumnHidden(5) is False
    assert table.ColumnHidden(6) is True
    for index in (6, 7, 8):
        assert table.GetColumnWidth(index) == 0.0
        assert table.ColumnHidden(index + 1) is False
        assert table.GetColumnType3(index, True) == (-1, None, 0)


@pytest.mark.parametrize("with_sku", (False, True))
@pytest.mark.parametrize(
    "configuration",
    (drawing.SIMPLIFIED_VIEW_CONFIGURATION, drawing.BOM_CONFIGURATION),
    ids=("latent-before", "latent-after"),
)
def test_pd_hidden_native_property_collision_accepts_zero_width_without_losing_visible_qty(
    monkeypatch, with_sku, configuration
):
    scene = _pd_bom_insertion_fixture(monkeypatch, configuration=configuration)
    table = scene.insert()
    latent_before = ("Default", drawing.SIMPLIFIED_VIEW_CONFIGURATION).index(configuration)
    if with_sku:
        assert table.InsertColumn2(3, 2, "PURCHASE SKU", 0) is True
    before = _drawing_tables.validate_bom_number_property(
        table, configuration=configuration, label="paper-drive",
        expected_rows=BOM_ROWS, occurrence_quantities=True,
    )
    native_column = len(scene.state.columns) - 1
    scene.state.columns[native_column].width = 0.0
    assert table.GetColumnType3(native_column + 1, True) == (-1, None, 0)
    assert table.ColumnHidden(native_column + latent_before) is True
    assert table.ColumnHidden(native_column + latent_before + 1) is False
    assert _drawing_tables._bom_physical_columns(table, label="paper-drive")[-1] == (201, True)
    assert _drawing_tables.validate_bom_number_property(
        table, configuration=configuration, label="paper-drive",
        expected_rows=BOM_ROWS, occurrence_quantities=True,
    ) == before


def _pd_description_writes(scene):
    return {
        write
        for group in scene.state.native_rows
        for component in group
        for write in component.GetModelDoc2().written
    }


def test_default_bom_descriptions_do_not_write_back_to_simplified_members(monkeypatch):
    # Native run 20261023T190254133Z: the linked DESCRIPTION write landed in
    # sh-vn-clamp-screw's active "Default Simplified" while the Default row
    # re-read "Default": '' != 'FILLISTER SCREW, MCMASTER 90280A201'.
    configuration = drawing.BOM_CONFIGURATION
    scene = _pd_bom_insertion_fixture(monkeypatch, configuration=configuration)
    table = scene.insert()
    assert table.GetColumnCustomProperty(2) == ""
    assert table.GetColumnTitle2(2, False) == "DESCRIPTION"
    assert _drawing_tables._bom_physical_columns(table, label="paper-drive") == (
        (202, False), (204, False), (204, False), (203, False), (201, True)
    )
    assert _pd_description_writes(scene) == set()
    assert {
        key: scene.cells[row][2] for row, key in enumerate(scene.state.row_keys, 1)
    } == drawing.BOM_DESCRIPTIONS


def _rebind_to_bogus_property(_adapter, table, column, *, label):
    # Native run 20261023T192129678Z: rebinding to a nonexistent property kept
    # the write-back ($PRP:"HARMONIC BOM DESCRIPTION TEXT").
    assert table.SetColumnCustomProperty(column, "HARMONIC BOM DESCRIPTION TEXT")
    assert table.SetColumnTitle2(column, "DESCRIPTION", True)


@pytest.mark.parametrize(
    "replacement",
    (lambda *_, **__: None, _rebind_to_bogus_property),
    ids=("linked", "rebound"),
)
@pytest.mark.parametrize("recheck", (True, False), ids=("rechecked", "control"))
def test_default_bom_refuses_property_bound_description_write_back(
    monkeypatch, replacement, recheck,
):
    # Any property-bound column writes back; the pre-authoring recheck refuses
    # it before SetText2, and without the recheck the write-back is observed.
    scene = _pd_bom_insertion_fixture(monkeypatch, configuration=drawing.BOM_CONFIGURATION)
    monkeypatch.setattr(
        _drawing_tables, "_unlink_bom_description_column", replacement
    )
    if recheck:
        with pytest.raises(RuntimeError, match="still reads property .* before authoring"):
            scene.insert()
        assert _pd_description_writes(scene) == set()
        return
    monkeypatch.setattr(_drawing_tables, "_require_unlinked_bom_column", lambda *_, **__: None)
    with pytest.raises(RuntimeError, match="BOM description did not persist: ''"):
        scene.insert()
    writes = _pd_description_writes(scene)
    assert writes
    assert all(name.endswith(" Simplified") for name, _prop in writes)


def test_description_unlink_refuses_binding_restored_by_rebuild(monkeypatch):
    scene = _pd_bom_insertion_fixture(monkeypatch, configuration=drawing.BOM_CONFIGURATION)
    native_rebuild = _drawing_tables.rebuild_drawing

    def rebuild(adapter, *, label):
        if label == "unlink_bom_description_column":
            assert scene.table.SetColumnCustomProperty(2, "Description") is True
        return native_rebuild(adapter, label=label)

    monkeypatch.setattr(_drawing_tables, "rebuild_drawing", rebuild)
    with pytest.raises(RuntimeError, match="still reads property 'Description'.* after rebuild"):
        scene.insert()
    assert _pd_description_writes(scene) == set()


def test_view_configuration_bom_unlinks_description_column(monkeypatch):
    # Codjiflo P1 on #1895: view-derived callers' writes also landed in the
    # component models' active configurations; the drawing now owns the text.
    scene = _pd_bom_insertion_fixture(monkeypatch)
    table = scene.insert()
    assert table.GetColumnCustomProperty(2) == ""
    assert scene.state.configuration == drawing.SIMPLIFIED_VIEW_CONFIGURATION
    assert _pd_description_writes(scene) == set()
    assert {
        key: scene.cells[row][2] for row, key in enumerate(scene.state.row_keys, 1)
    } == drawing.BOM_DESCRIPTIONS


@pytest.mark.parametrize("configuration", (None, "Default"))
def test_bom_refuses_plain_description_without_row_text(monkeypatch, configuration):
    scene = _pd_bom_insertion_fixture(monkeypatch, configuration=configuration)
    descriptions = {
        key: text for key, text in drawing.BOM_DESCRIPTIONS.items() if key != "pd-platen"
    }
    with pytest.raises(
        RuntimeError, match=f"DESCRIPTION column left 1 of {BOM_ROWS - 1} rows blank"
    ):
        _drawing_tables.insert_bom_table(
            scene.adapter, scene.view, anchor_xy=drawing.BOM_ANCHOR,
            expected_components=tuple(drawing.BOM_PART_NUMBERS),
            descriptions=descriptions,
            component_identities=drawing.BOM_COMPONENT_IDENTITIES,
            part_number_property="Number", configuration_grouping="same-name",
            configuration=configuration, label="paper-drive",
        )


@pytest.mark.parametrize("blank", ("", "   ", None))
def test_bom_refuses_blank_descriptions_before_any_mutation(monkeypatch, blank):
    scene = _pd_bom_insertion_fixture(monkeypatch, configuration=drawing.BOM_CONFIGURATION)
    descriptions = dict(drawing.BOM_DESCRIPTIONS) | {"pd-platen": blank}
    before = [vars(column).copy() for column in scene.state.columns]
    with pytest.raises(ValueError, match=r"descriptions are blank for \['pd-platen'\]"):
        _drawing_tables.insert_bom_table(
            scene.adapter, scene.view, anchor_xy=drawing.BOM_ANCHOR,
            expected_components=tuple(drawing.BOM_PART_NUMBERS),
            descriptions=descriptions,
            component_identities=drawing.BOM_COMPONENT_IDENTITIES,
            part_number_property="Number", configuration_grouping="same-name",
            configuration=drawing.BOM_CONFIGURATION, label="paper-drive",
        )
    assert [vars(column) for column in scene.state.columns] == before


@pytest.mark.parametrize("configuration", ("Default", "Default Simplified"))
def test_visibility_mutation_refuses_beyond_typed_prefix(monkeypatch, configuration):
    # Codjiflo P2 on #1895: with Default selected, physical len(typed) maps onto
    # the latent Quantity, which SetColumnHidden would materialize.
    scene = _pd_bom_insertion_fixture(monkeypatch, configuration=configuration)
    table = scene.insert()
    typed = len(scene.state.columns)
    # Diagnostic reads still map the beyond-prefix index.
    _drawing_tables._bom_visibility_index(table, typed, label="pd")
    with pytest.raises(ValueError, match=f"physical column {typed} is not one of its {typed}"):
        _drawing_tables._set_bom_column_hidden(table, typed, True, label="pd")
    assert scene.state.materialized == []
    assert len(scene.state.columns) == typed


@pytest.mark.parametrize("fault", ("status", "readback"))
def test_default_bom_refuses_linked_description_column_left_bound(monkeypatch, fault):
    scene = _pd_bom_insertion_fixture(monkeypatch, configuration=drawing.BOM_CONFIGURATION)
    native = scene.table.SetColumnCustomProperty.side_effect

    def set_custom_property(index, property_name):
        if property_name:
            return native(index, property_name)
        return False if fault == "status" else True  # Readback keeps Description.

    scene.table.SetColumnCustomProperty.side_effect = set_custom_property
    with pytest.raises(RuntimeError, match="DESCRIPTION (unlink failed|column still reads)"):
        scene.insert()
    assert scene.table.GetColumnCustomProperty(2) == "Description"
    assert _pd_description_writes(scene) == set()


def test_default_bom_hides_native_column_without_materializing_latent_quantity(monkeypatch):
    # v45 run 20261023T163903809Z: Default selected, so the Default Simplified
    # Quantity is latent AFTER the native column. Typed+1 wrote that latent.
    configuration = drawing.BOM_CONFIGURATION
    assert configuration == "Default"
    scene = _pd_bom_insertion_fixture(monkeypatch, configuration=configuration)
    table = scene.insert()
    native_column = len(scene.state.columns) - 1
    assert _drawing_tables._bom_visibility_index(table, native_column, label="pd") == native_column
    assert table.ColumnCount == native_column
    assert table.TotalColumnCount == native_column + 2
    assert scene.state.materialized == []
    assert _drawing_tables._bom_physical_columns(table, label="paper-drive") == (
        (202, False), (204, False), (204, False), (203, False), (201, True)
    )
    assert [table.GetColumnTitle2(index, False) for index in range(table.ColumnCount)] == [
        "ITEM NO.", "PART NUMBER", "DESCRIPTION", "QTY."
    ]
    _drawing_tables.validate_bom_number_property(
        table, configuration=configuration, label="paper-drive",
        expected_rows=BOM_ROWS, occurrence_quantities=True,
    )

    # The former index materializes the latent Quantity; the census refuses it.
    assert table.SetColumnHidden(native_column + 1, True) is None
    assert scene.state.materialized == [drawing.SIMPLIFIED_VIEW_CONFIGURATION]
    assert table.TotalColumnCount == native_column + 2
    with pytest.raises(RuntimeError, match="Quantity columns do not match its configurations"):
        _drawing_tables._bom_physical_columns(table, label="paper-drive")


@pytest.mark.parametrize("hidden_row", (0, 1), ids=("header", "data"))
def test_bom_insertion_refuses_hidden_physical_rows_before_number_binding(monkeypatch, hidden_row):
    scene = _pd_bom_insertion_fixture(monkeypatch)
    scene.state.hidden_rows.add(hidden_row)
    before_columns = [vars(column).copy() for column in scene.state.columns]
    before_cells = tuple(tuple(row) for row in scene.cells)
    with pytest.raises(RuntimeError):
        scene.insert()
    assert [vars(column) for column in scene.state.columns] == before_columns
    assert tuple(tuple(row) for row in scene.cells) == before_cells
    assert scene.table.RowHidden(hidden_row) is True


@pytest.mark.parametrize(
    "failure",
    (
        "move", "move-noop", "insert", "insert-noop", "hide-readback",
        "number-property-status", "number-property-readback", "initial-inconsistent-counts",
    ),
)
def test_bom_insertion_refuses_failed_native_column_retention(monkeypatch, failure):
    scene = _pd_bom_insertion_fixture(monkeypatch)
    if failure == "move":
        scene.table.MoveColumn.side_effect = lambda *_: False
    elif failure == "move-noop":
        scene.table.MoveColumn.side_effect = lambda *_: True
    elif failure == "insert":
        scene.table.InsertColumn2.side_effect = lambda *_: False
    elif failure == "insert-noop":
        scene.table.InsertColumn2.side_effect = lambda *_: True
    elif failure == "number-property-status":
        scene.table.SetColumnCustomProperty.side_effect = lambda *_: False
    elif failure == "number-property-readback":
        native_property = scene.table.GetColumnCustomProperty.side_effect
        scene.table.GetColumnCustomProperty.side_effect = lambda index: (
            "Description" if index == 1 else native_property(index)
        )
    elif failure == "initial-inconsistent-counts":
        type(scene.table).ColumnCount = PropertyMock(return_value=3)
    else:
        # A VOID call returning None is valid, but a no-op must fail readback.
        scene.table.SetColumnHidden.side_effect = lambda *_: None
    with pytest.raises(RuntimeError):
        scene.insert()


@pytest.mark.parametrize("kind", (0, 201, 202, 203))
def test_bom_insertion_refuses_noncustom_inserted_column(monkeypatch, kind):
    scene = _pd_bom_insertion_fixture(monkeypatch)
    native_insert = scene.table.InsertColumn2.side_effect
    before_members = tuple(tuple(group) for group in scene.state.native_rows)
    before_quantities = tuple(row[3] for row in scene.cells)

    def insert_column(where, index, name, width_style):
        result = native_insert(where, index, name, width_style)
        scene.state.columns[index + (where == 3)].kind = kind
        return result

    scene.table.InsertColumn2.side_effect = insert_column
    with pytest.raises(RuntimeError):
        scene.insert()
    assert scene.state.columns[1].kind == kind
    assert scene.table.GetColumnCustomProperty(1) == ""
    assert scene.table.RowCount == scene.table.TotalRowCount == BOM_ROWS
    assert tuple(tuple(group) for group in scene.state.native_rows) == before_members
    assert tuple(row[3] for row in scene.cells) == before_quantities


@pytest.mark.parametrize("result", (None, 0, 1, "True"), ids=("none", "zero", "one", "string"))
def test_bom_insertion_refuses_nonbool_property_setter_success(monkeypatch, result):
    scene = _pd_bom_insertion_fixture(monkeypatch)
    native_set = scene.table.SetColumnCustomProperty.side_effect
    before_members = tuple(tuple(group) for group in scene.state.native_rows)
    before_quantities = tuple(row[3] for row in scene.cells)

    def set_custom_property(index, property_name):
        assert native_set(index, property_name) is True
        # The DESCRIPTION unlink ("") keeps its native status; Number gets ``result``.
        return result if property_name == "Number" else True

    scene.table.SetColumnCustomProperty.side_effect = set_custom_property
    with pytest.raises(RuntimeError):
        scene.insert()
    assert scene.table.GetColumnCustomProperty(1) == "Number"
    assert scene.table.RowCount == scene.table.TotalRowCount == BOM_ROWS
    assert tuple(tuple(group) for group in scene.state.native_rows) == before_members
    assert tuple(row[3] for row in scene.cells) == before_quantities

@pytest.mark.parametrize(
    "fault",
    (
        "missing-native", "changed-native", "unhidden-native", "duplicate-native",
        "native-not-last", "hidden-visible-gap", "bad-native-status",
        "bad-number-kind", "bad-number-status",
        "bad-property-readback", "short-total-count", "short-visible-count",
    ),
)
def test_bom_number_proof_refuses_invalid_retained_column_state(monkeypatch, fault):
    _model, _components, table, _adapter, cells, _keys = _pd_bom_fixture(monkeypatch)
    columns = table._pd_state.columns
    if fault == "missing-native":
        columns.pop()
        for row in cells:
            row.pop()
    elif fault == "changed-native":
        columns[-1].kind = 202
    elif fault == "unhidden-native":
        columns[-1].hidden = False
    elif fault == "duplicate-native":
        columns[2].kind = 201
    elif fault == "native-not-last":
        columns[3], columns[4] = columns[4], columns[3]
        for row in cells:
            row[3], row[4] = row[4], row[3]
    elif fault == "hidden-visible-gap":
        columns[2].hidden = True
    elif fault == "bad-number-kind":
        columns[1].kind = 202
    elif fault == "bad-property-readback":
        native_property = table.GetColumnCustomProperty.side_effect
        table.GetColumnCustomProperty.side_effect = lambda index: (
            "Description" if index == 1 else native_property(index)
        )
    elif fault in ("bad-native-status", "bad-number-status"):
        original_type = table.GetColumnType3.side_effect
        bad_index = 4 if fault == "bad-native-status" else 1
        table.GetColumnType3.side_effect = lambda index, hidden: (
            (*original_type(index, hidden)[:2], 1)
            if index == bad_index else original_type(index, hidden)
        )
    elif fault == "short-total-count":
        type(table).TotalColumnCount = PropertyMock(return_value=4)
    else:
        type(table).ColumnCount = PropertyMock(return_value=3)
    with pytest.raises(RuntimeError):
        _drawing_tables.validate_bom_number_property(
            table, configuration=drawing.SIMPLIFIED_VIEW_CONFIGURATION,
            label="paper-drive", expected_rows=len(drawing.BOM_PART_NUMBERS) + 1,
        )


def test_bom_number_proof_uses_binding_getter_not_raw_property_data(monkeypatch):
    _model, _components, table, _adapter, _cells, _keys = _pd_bom_fixture(monkeypatch)
    configuration = drawing.SIMPLIFIED_VIEW_CONFIGURATION
    before = _drawing_tables.validate_bom_number_property(
        table, configuration=configuration, label="paper-drive",
        occurrence_quantities=True,
    )
    column = table._pd_state.columns[1]
    assert column.raw_property_data == '$PRP:"Number"'
    for raw_metadata in ("Number", '$PRP:"Number"'):
        column.raw_property_data = raw_metadata
        assert _drawing_tables.validate_bom_number_property(
            table, configuration=configuration, label="paper-drive",
            occurrence_quantities=True,
        ) == before
    column.property_name = "Description"
    with pytest.raises(RuntimeError):
        _drawing_tables.validate_bom_number_property(
            table, configuration=configuration, label="paper-drive",
            occurrence_quantities=True,
        )


@pytest.mark.parametrize(
    ("index", "member", "mode", "value"),
    (
        (4, "GetColumnType3", True, (-1, None)),
        (4, "GetColumnType3", True, (999, None, 0)),
        (4, "GetColumnType3", True, ("-1", None, 0)),
        (4, "GetColumnType3", True, (-1, None, "0")),
        (4, "GetColumnType3", True, (-1, None, 2)),
        (4, "GetColumnType3", True, (-1, "", 0)),
        (4, "GetColumnType3", False, (-1, "Number", 0)),
        (4, "GetColumnTitle2", True, "UNEXPECTED"),
        (4, "GetColumnTitle2", False, "UNEXPECTED"),
        (4, "DisplayedText2", True, "UNEXPECTED"),
        (4, "DisplayedText2", False, "UNEXPECTED"),
        (4, "GetColumnWidth", None, 0.025),
        (4, "GetColumnWidth", None, -0.001),
        (4, "GetColumnWidth", None, float("nan")),
        (4, "GetColumnWidth", None, float("inf")),
        (5, "ColumnHidden", None, True),
        (5, "ColumnHidden", None, 1),
        (5, "ColumnHidden", None, None),
        (4, "GetColumnCustomProperty", None, "Audit"),
        (4, "GetColumnType3", True, (-1, None, 1)),
        (5, "GetColumnType3", True, (-1, None, 1)),
        (6, "GetColumnType3", True, (-1, None, 1)),
        (5, "GetColumnType3", True, (204, None, 0)),
        (6, "GetColumnTitle2", False, "UNEXPECTED"),
    ),
    ids=(
        "malformed-type", "unknown-kind", "string-kind", "string-status",
        "invalid-property-status", "nonempty-property-data", "visible-property-data",
        "physical-title", "visible-title", "physical-header", "visible-header",
        "nonzero-width", "negative-width", "nan-width", "infinite-width",
        "hidden-invalid", "nonboolean-hidden", "missing-hidden", "custom-property",
        "tail-control-status-mismatch", "first-control-status-mismatch",
        "second-control-status-mismatch", "typed-control", "nonempty-control",
    ),
)
def test_bom_column_census_refuses_invalid_native_slot_without_mutating(
    monkeypatch, index, member, mode, value
):
    scene = _pd_bom_insertion_fixture(monkeypatch)
    accessor = getattr(scene.table, member)
    original = accessor.side_effect

    if member == "DisplayedText2":
        def read(row, column, include_hidden):
            if column == index and include_hidden is mode:
                return value
            return original(row, column, include_hidden)
    elif mode is None:
        def read(column):
            return value if column == index else original(column)
    else:
        def read(column, include_hidden):
            if column == index and include_hidden is mode:
                return value
            return original(column, include_hidden)

    accessor.side_effect = read
    before_columns = [vars(column).copy() for column in scene.state.columns]
    before_members = tuple(tuple(row) for row in scene.state.native_rows)
    before_cells = tuple(tuple(row) for row in scene.cells)
    with pytest.raises(RuntimeError):
        scene.insert()
    assert [vars(column) for column in scene.state.columns] == before_columns
    assert tuple(tuple(row) for row in scene.state.native_rows) == before_members
    assert tuple(tuple(row) for row in scene.cells) == before_cells


@pytest.mark.parametrize("statuses", ((1, 0, 0), (0, 1, 0), (0, 0, 1), (0, 1, 1)))
def test_bom_column_census_does_not_normalize_distinct_invalid_statuses(
    monkeypatch, statuses
):
    scene = _pd_bom_insertion_fixture(monkeypatch)
    original_type = scene.table.GetColumnType3.side_effect

    def column_type(index, include_hidden):
        if index in (4, 5, 6):
            return -1, None, statuses[index - 4]
        return original_type(index, include_hidden)

    scene.table.GetColumnType3.side_effect = column_type
    before_columns = [vars(column).copy() for column in scene.state.columns]
    before_members = tuple(tuple(row) for row in scene.state.native_rows)
    before_cells = tuple(tuple(row) for row in scene.cells)
    with pytest.raises(RuntimeError):
        scene.insert()
    assert [vars(column) for column in scene.state.columns] == before_columns
    assert tuple(tuple(row) for row in scene.state.native_rows) == before_members
    assert tuple(tuple(row) for row in scene.cells) == before_cells


def test_bom_column_census_refuses_empty_interior_before_later_typed_column(monkeypatch):
    scene = _pd_bom_insertion_fixture(monkeypatch)
    original_type = scene.table.GetColumnType3.side_effect
    original_title = scene.table.GetColumnTitle2.side_effect
    original_text = scene.table.DisplayedText2.side_effect
    original_width = scene.table.GetColumnWidth.side_effect
    original_property = scene.table.GetColumnCustomProperty.side_effect
    scene.table.GetColumnType3.side_effect = lambda index, mode: (
        (-1, None, 0) if index == 2 else original_type(index, mode)
    )
    scene.table.GetColumnTitle2.side_effect = lambda index, mode: (
        "" if index == 2 else original_title(index, mode)
    )
    scene.table.DisplayedText2.side_effect = lambda row, index, mode: (
        "" if index == 2 else original_text(row, index, mode)
    )
    scene.table.GetColumnWidth.side_effect = lambda index: (
        0.0 if index == 2 else original_width(index)
    )
    scene.table.GetColumnCustomProperty.side_effect = lambda index: (
        "" if index == 2 else original_property(index)
    )
    before = tuple(tuple(row) for row in scene.cells)
    with pytest.raises(RuntimeError):
        scene.insert()
    assert tuple(tuple(row) for row in scene.cells) == before
    assert scene.table.GetColumnType3(3, True) == (203, None, 0)
    assert len(scene.state.columns) == 4


@pytest.mark.parametrize("kind", (201, 204), ids=("native-part-number", "custom-property"))
def test_bom_insertion_refuses_actual_preexisting_hidden_zero_width_column(
    monkeypatch, kind
):
    scene = _pd_bom_insertion_fixture(monkeypatch)
    scene.state.columns.append(SimpleNamespace(
        kind=kind, property_name="Audit" if kind == 204 else "",
        raw_property_data="Audit" if kind == 204 else "", hidden=True, width=0.0,
    ))
    for row in scene.cells:
        row.append("")
    assert scene.table.ColumnCount == 4
    assert scene.table.TotalColumnCount == 6
    physical = _drawing_tables._bom_physical_columns(scene.table, label="paper-drive")
    assert len(physical) == 5
    assert physical[-1] == (kind, True)
    before_columns = [vars(column).copy() for column in scene.state.columns]
    before_members = tuple(tuple(row) for row in scene.state.native_rows)
    before_cells = tuple(tuple(row) for row in scene.cells)
    with pytest.raises(RuntimeError):
        scene.insert()
    assert [vars(column) for column in scene.state.columns] == before_columns
    assert tuple(tuple(row) for row in scene.state.native_rows) == before_members
    assert tuple(tuple(row) for row in scene.cells) == before_cells


def test_bom_column_census_refuses_advertised_cap_overflow_without_truncation(monkeypatch):
    scene = _pd_bom_insertion_fixture(monkeypatch)
    type(scene.table).TotalColumnCount = PropertyMock(return_value=99)
    before_columns = [vars(column).copy() for column in scene.state.columns]
    before_members = tuple(tuple(row) for row in scene.state.native_rows)
    before_cells = tuple(tuple(row) for row in scene.cells)
    with pytest.raises(RuntimeError):
        scene.insert()
    assert [vars(column) for column in scene.state.columns] == before_columns
    assert tuple(tuple(row) for row in scene.state.native_rows) == before_members
    assert tuple(tuple(row) for row in scene.cells) == before_cells


@pytest.mark.parametrize("index", (15, 16, 17), ids=("last-declared", "first-control", "second-control"))
def test_bom_column_census_refuses_bad_metadata_beyond_diagnostic_display_cap(
    monkeypatch, index
):
    scene = _pd_bom_insertion_fixture(monkeypatch)
    type(scene.table).TotalColumnCount = PropertyMock(return_value=16)
    # 4 typed + 12 latent columns: 13 configurations, the selected one second,
    # so the latent guard holds and the census reaches the advertised tail.
    names = ("Default", drawing.SIMPLIFIED_VIEW_CONFIGURATION) + tuple(
        f"Extra {number}" for number in range(11)
    )
    scene.table.BomFeature.GetConfigurations = lambda only_visible, _visibility: (
        names, tuple(name == drawing.SIMPLIFIED_VIEW_CONFIGURATION for name in names)
    )
    assert _drawing_tables._bom_physical_columns(scene.table, label="paper-drive") == (
        (202, False), (201, False), (204, False), (203, False)
    )
    original_property = scene.table.GetColumnCustomProperty.side_effect
    scene.table.GetColumnCustomProperty.side_effect = lambda column: (
        "Audit" if column == index else original_property(column)
    )
    before_columns = [vars(column).copy() for column in scene.state.columns]
    before_cells = tuple(tuple(row) for row in scene.cells)
    with pytest.raises(
        RuntimeError, match=f"nonempty unsupported column at physical index {index}$"
    ):
        _drawing_tables._bom_physical_columns(scene.table, label="paper-drive")
    assert [vars(column) for column in scene.state.columns] == before_columns
    assert tuple(tuple(row) for row in scene.cells) == before_cells


def test_native_column_fixture_keeps_visible_and_physical_indices_distinct(monkeypatch):
    scene = _pd_bom_insertion_fixture(monkeypatch)
    # Typed columns before the selected Quantity share the visibility index.
    assert scene.table.SetColumnHidden(1, True) is None
    assert scene.table.ColumnCount == 3
    assert scene.table.TotalColumnCount == 5
    assert scene.table.GetColumnType3(1, True) == (201, None, 0)
    assert scene.table.GetColumnType3(1, False) == (204, "Description", 0)
    assert scene.table.GetColumnTitle2(1, True) == "PART NUMBER"
    assert scene.table.GetColumnTitle2(1, False) == "DESCRIPTION"
    assert scene.table.DisplayedText2(0, 1, False) == "DESCRIPTION"
    assert scene.table.GetColumnType3(3, False) == (-1, None, 0)
    assert _drawing_tables._bom_physical_columns(scene.table, label="paper-drive") == (
        (202, False), (201, True), (204, False), (203, False)
    )


@pytest.mark.parametrize("index", (-1, 4, 5, 6))
def test_native_column_fixture_refuses_nonaddressable_mutation_destinations(
    monkeypatch, index
):
    scene = _pd_bom_insertion_fixture(monkeypatch)
    before_columns = [vars(column).copy() for column in scene.state.columns]
    before_members = tuple(tuple(row) for row in scene.state.native_rows)
    before_cells = tuple(tuple(row) for row in scene.cells)
    assert scene.table.MoveColumn(1, 3, index) is False
    assert scene.table.MoveColumn(index, 3, 0) is False
    assert scene.table.InsertColumn2(2, index, "PART NUMBER", 0) is False
    assert scene.table.SetColumnType3(index, 204, True, "Number") == 1
    assert scene.table.SetColumnCustomProperty(index, "Number") is False
    assert scene.table.SetColumnTitle2(index, "PART NUMBER", True) is False
    with pytest.raises(IndexError):
        # Typed index -1 or past the end: below/above the visibility domain.
        scene.table.SetColumnHidden(index if index < 0 else index + 1, True)
    with pytest.raises(IndexError):
        scene.table.SetColumnWidth(index, 0.025, 0)
    with pytest.raises(IndexError):
        scene.table.SetText2(0, index, True, "PART NUMBER")
    assert [vars(column) for column in scene.state.columns] == before_columns
    assert tuple(tuple(row) for row in scene.state.native_rows) == before_members
    assert tuple(tuple(row) for row in scene.cells) == before_cells


@pytest.mark.parametrize(
    ("failure", "member", "mode"),
    (
        ("type_all", "GetColumnType3", True),
        ("type_visible", "GetColumnType3", False),
        ("title_all", "GetColumnTitle2", True),
        ("title_visible", "GetColumnTitle2", False),
        ("header_all", "DisplayedText2", True),
        ("header_visible", "DisplayedText2", False),
        ("width", "GetColumnWidth", None),
        ("hidden", "ColumnHidden", None),
        ("custom_property", "GetColumnCustomProperty", None),
    ),
)
def test_bom_column_census_refuses_accessor_errors_without_mutating(
    monkeypatch, failure, member, mode
):
    scene = _pd_bom_insertion_fixture(monkeypatch)
    accessor = getattr(scene.table, member)
    original = accessor.side_effect

    def fail():
        raise RuntimeError("native-column-read-failure")

    if member == "DisplayedText2":
        def read(row, column, include_hidden):
            if column == 4 and include_hidden is mode:
                fail()
            return original(row, column, include_hidden)
    elif mode is None:
        def read(column):
            if column == (5 if member == "ColumnHidden" else 4):
                fail()
            return original(column)
    else:
        def read(column, include_hidden):
            if column == 4 and include_hidden is mode:
                fail()
            return original(column, include_hidden)

    accessor.side_effect = read
    before_columns = [vars(column).copy() for column in scene.state.columns]
    before_members = tuple(tuple(row) for row in scene.state.native_rows)
    before_cells = tuple(tuple(row) for row in scene.cells)
    with pytest.raises(RuntimeError):
        scene.insert()
    assert [vars(column) for column in scene.state.columns] == before_columns
    assert tuple(tuple(row) for row in scene.state.native_rows) == before_members
    assert tuple(tuple(row) for row in scene.cells) == before_cells


@pytest.mark.parametrize("effect", ("omitted", "merged", "excluded", "hidden"))
def test_number_binding_consumer_refuses_changed_native_bom_state(monkeypatch, effect):
    scene = _pd_bom_insertion_fixture(monkeypatch)
    configuration = drawing.SIMPLIFIED_VIEW_CONFIGURATION
    native_rows = scene.state.native_rows
    gear_row = scene.keys.index("pd-transgear-removable") + 1
    gear_components = tuple(native_rows[gear_row - 1])
    gear_ids = {id(component) for component in gear_components}
    original_rows = scene.table.RowCount
    original_native_rows = tuple(
        tuple(id(component) for component in group) for group in native_rows
    )
    changed = False

    def rebuild():
        nonlocal changed
        if scene.state.columns[1].property_name != "Number" or changed:
            return True
        if effect == "hidden":
            scene.state.hidden_rows.add(gear_row)
        else:
            scene.cells.pop(gear_row)
            native_rows.pop(gear_row - 1)
            if effect == "merged":
                native_rows[0].extend(gear_components)
                quantity_column = next(
                    index for index, column in enumerate(scene.state.columns)
                    if column.kind == 203
                )
                scene.cells[1][quantity_column] = str(len(native_rows[0]))
            elif effect == "excluded":
                for component in gear_components:
                    component.exclusions[(3, (configuration,))] = True
        changed = True
        return True

    scene.adapter.currentModel.EditRebuild3 = rebuild
    if effect == "merged":
        message = "associative Number.*does not match native component Numbers"
    elif effect == "hidden":
        message = rf"BOM row {gear_row} is not proven visible"
    else:
        message = rf"BOM table is .*expected {original_rows} rows"
    with pytest.raises(RuntimeError, match=message):
        scene.insert()
    assert changed
    associated_rows = {
        row
        for row in range(1, scene.table.RowCount)
        for component in scene.table.GetComponents2(row, configuration)
        if id(component) in gear_ids
    }
    actual_native_rows = tuple(
        tuple(id(component) for component in scene.table.GetComponents2(row, configuration))
        for row in range(1, scene.table.RowCount)
    )
    if effect == "hidden":
        assert scene.table.RowCount == scene.table.TotalRowCount == original_rows
        assert scene.table.RowHidden(gear_row) is True
        assert associated_rows == {gear_row}
        assert actual_native_rows == original_native_rows
    else:
        assert scene.table.RowCount == scene.table.TotalRowCount == original_rows - 1
        assert associated_rows == ({1} if effect == "merged" else set())
        expected_native_rows = list(original_native_rows)
        removed = expected_native_rows.pop(gear_row - 1)
        if effect == "merged":
            expected_native_rows[0] += removed
        assert actual_native_rows == tuple(expected_native_rows)
        if effect == "excluded":
            assert all(
                component.GetExcludeFromBOM2(3, (configuration,)) == (True,)
                for component in gear_components
            )


@pytest.mark.parametrize("failure", ("row-association", "component-path"))
def test_number_binding_refuses_bad_native_rows_and_components(monkeypatch, failure):
    scene = _pd_bom_insertion_fixture(monkeypatch)
    native_components = scene.table.GetComponents2.side_effect
    if failure == "row-association":
        def components(row, configuration):
            if row == 1:
                raise RuntimeError("native-row-association-failure")
            return native_components(row, configuration)

        scene.table.GetComponents2.side_effect = components
        message = "native-row-association-failure"
    else:
        component = native_components(1, drawing.SIMPLIFIED_VIEW_CONFIGURATION)[0]
        component.GetPathName = lambda: ""
        message = "component has no native file path"
    with pytest.raises(RuntimeError, match=message):
        scene.insert()


@pytest.mark.parametrize(
    ("fault", "message"),
    (
        ("native-associations", "native associations changed during finalization"),
        ("grouping", "configuration grouping changed during finalization"),
        ("column-property", "Number property binding did not persist"),
        ("native-number", "associative Number"),
    ),
)
def test_bom_insertion_refuses_changes_from_the_description_rebuild(
    monkeypatch, fault, message
):
    scene = _pd_bom_insertion_fixture(monkeypatch)
    inner_row = scene.keys.index("sh-vn-chain-link--InnerLink") + 1
    outer_row = scene.keys.index("sh-vn-chain-link--OuterLink") + 1
    native_components = scene.table.GetComponents2.side_effect
    native_property = scene.table.GetColumnCustomProperty.side_effect

    def rebuild():
        if scene.table.SetText2.called:
            if fault == "grouping":
                scene.table.BomFeature.PartConfigurationGrouping = 2
            elif fault == "column-property":
                scene.table.GetColumnCustomProperty.side_effect = lambda index: (
                    "Description" if index == 1 else native_property(index)
                )
            elif fault == "native-number":
                native = native_components(
                    inner_row, drawing.SIMPLIFIED_VIEW_CONFIGURATION
                )[0].GetModelDoc2()
                native.GetCustomInfoValue = lambda *_: "WRONG-NATIVE-NUMBER"
            else:
                scene.table.GetComponents2.side_effect = lambda row, configuration: native_components(
                    {inner_row: outer_row, outer_row: inner_row}.get(row, row),
                    configuration,
                )
        return True

    scene.adapter.currentModel.EditRebuild3 = rebuild
    with pytest.raises(RuntimeError, match=message):
        scene.insert()


@pytest.mark.parametrize("fault", ("different-selected-number", "missing-number"))
def test_number_binding_refuses_invalid_native_selected_config_properties(monkeypatch, fault):
    scene = _pd_bom_insertion_fixture(monkeypatch)
    gear_row = scene.keys.index("pd-transgear-removable") + 1
    members = scene.state.native_rows[gear_row - 1]
    native = members[0].GetModelDoc2()
    if fault == "different-selected-number":
        native.properties[("T18 Simplified", "Number")] = "WRONG-T18"
        message = "associative Number"
    else:
        for component in members:
            native.properties[(component.ReferencedConfiguration, "Number")] = ""
        native.properties[("", "Number")] = ""
        message = "has no Number property"
    with pytest.raises(RuntimeError, match=message):
        scene.insert()


def _sub_step_texts() -> dict[str, str]:
    """Every printed sub-step head (``9C``, or ``16`` for a one-line step)
    with its text."""
    texts = drawing._step_text(operating_domain=_unit_operating_domain())
    heads: dict[str, str] = {}
    for key in steps.SEQUENCE:
        for index, text in enumerate(texts[key]):
            heads[drawing.sub_step(key, index)] = text
        if len(texts[key]) == 1:
            heads[str(steps.step_number(key))] = texts[key][0]
    return heads


def test_every_setting_row_is_cited_by_the_steps_its_step_column_names() -> None:
    """Rule 22 (R5 machinist review): each setting-table row's STEP cell names
    the sub-steps that set or check it, and each of them cites that row, or
    repeats a sub-step that does ("AS 12N")."""
    heads = _sub_step_texts()
    rows = drawing.setting_table_rows(operating_domain=_unit_operating_domain())
    assert len(rows) == len(drawing.SETTING_ROW_KEYS)
    sheet = drawing.SHEET_NAMES.index(drawing.SETTING_TABLE_SHEET) + 1
    cite = re.compile(rf"\bROWS? (\d+)(?:-(\d+))?, SHEET {sheet}\)")

    def cites(text: str, number: int) -> bool:
        return any(
            int(low) <= number <= int(high or low) for low, high in cite.findall(text)
        )

    for number, row in enumerate(rows, start=1):
        assert len(row) == len(drawing.SETTING_TABLE_HEADER)
        assert row[0] == str(number)
        for head in row[1].split(", "):
            text = heads[head]
            repeated = re.findall(r"\bAS (?:\d+[A-Z] AND )?(\d+[A-Z])\b", text)
            repeated += re.findall(r"\bAS (\d+[A-Z]) AND \d+[A-Z]\b", text)
            assert cites(text, number) or any(
                cites(heads[other], number) for other in repeated
            ), (head, number)


def test_every_setting_detail_is_cited_by_its_steps() -> None:
    """Each lettered setting detail is cited, with its sheet, by every step it
    dimensions."""
    texts = drawing._step_text(operating_domain=_unit_operating_domain())
    sheet = drawing.SHEET_NAMES.index(drawing.SETTING_DETAIL_SHEET) + 1
    for detail in drawing.setting_details.DETAILS:
        for key in detail.step_keys:
            body = " ".join(texts[key])
            assert f"({detail.view_name}, SHEET {sheet})" in body, (detail.letter, key)


def test_setting_reference_views_are_lettered_details_of_sheet_1() -> None:
    """#3110 (rule 9): each SETTING DETAILS reference view is a lettered
    DETAIL whose boundary sits on sheet 1's view in its orientation, with a
    letter that no other view or point on the package uses."""
    taken = {
        "A", drawing.PIVOT_LOCATOR_LETTER,
        drawing.KNOB_SETTING_VIEW_NAME[-1], drawing.CLUSTER_FLOAT_VIEW_NAME[-1],
        *drawing.KNOB_SETTING_LETTER_GAPS,  # DETAIL K's points S, T and N
        *drawing.SETTING_DETAILS_BY_LETTER,
    }
    letters = [parent.letter for parent in drawing.SETTING_PARENTS]
    assert len(set(letters)) == len(letters)
    assert not taken & set(letters)
    assert not {"I", "O", "Q"} & set(letters)
    for parent in drawing.SETTING_PARENTS:
        caption = drawing.SETTING_PARENT_CAPTIONS[parent.name]
        assert caption.startswith(f"DETAIL {parent.letter} "), caption


def test_sheet_1_boundary_letters_stand_clear_of_every_boundary() -> None:
    """#3110 (rule 14; Codjiflo P2/P3 on 608e0de509): on each sheet-1 view
    every boundary's letter and leader tip stands outside every other
    boundary circle, and its letter outside its own.

    Sheet x runs along machine -x on the front view and machine +z on the
    right view. Run 20261118T121458665Z-76e060f0f3284d3793c99307368ab0ea
    shows this: VIEW B's pivot (x -58) prints right of DETAIL K (x -21), and
    DETAIL M (z -136) prints right of DETAIL E (z -163)."""
    m_per_mm = drawing._ASSEMBLED_M_PER_MM

    def on_sheet(orientation: str, point: tuple[float, float, float]) -> tuple[float, float]:
        across = -point[0] if orientation == "*Front" else point[2]
        return (across * m_per_mm, point[1] * m_per_mm)

    boundaries = [
        (
            drawing.KNOB_SETTING_VIEW_NAME[-1], "*Front",
            drawing.KNOB_SETTING_MODEL_CENTRE, drawing.KNOB_SETTING_PARENT_RADIUS,
            drawing.KNOB_SETTING_LETTER_OFFSET,
        ),
        (
            drawing.CLUSTER_FLOAT_VIEW_NAME[-1], "*Right",
            drawing.CLUSTER_FLOAT_MODEL_CENTRE, drawing.CLUSTER_FLOAT_PARENT_RADIUS,
            drawing.CLUSTER_FLOAT_LETTER_OFFSET,
        ),
        *(
            (
                parent.letter, parent.orientation, parent.model_centre,
                drawing.setting_parent_sheet1_radius(parent), parent.sheet1_letter_offset,
            )
            for parent in drawing.SETTING_PARENTS
        ),
    ]
    glyph = math.hypot(*drawing.KNOB_SETTING_LETTER_HALF) * 2.0
    for letter, orientation, model_mm, radius, offset in boundaries:
        centre = on_sheet(orientation, model_mm)
        text, tip = drawing.detail_letter_pointer(centre, radius, offset)
        assert math.dist(text, centre) > radius + glyph, letter
        for other, other_orientation, other_mm, other_radius, _ in boundaries:
            if other == letter or other_orientation != orientation:
                continue
            other_centre = on_sheet(other_orientation, other_mm)
            assert math.dist(text, other_centre) > other_radius + glyph, (letter, other)
            assert math.dist(tip, other_centre) > other_radius, (letter, other)


def test_detail_h_text_stands_clear_of_its_extension_lines() -> None:
    """#3110 (rule 14): DETAIL H's .067 stands past the dowel's end, so
    neither the arm's rear-face line nor the dowel-end line runs through it
    (half an .067 at 5:1 is under 5 mm on the sheet, 1 mm of model)."""
    line = drawing.SETTING_DETAILS_BY_LETTER["H"].lines[0]
    assert line.end[2] > line.start[2]
    assert line.text[2] - line.end[2] >= 1.0 + 1.0
