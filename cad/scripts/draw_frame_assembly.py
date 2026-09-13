r"""Create the native multi-sheet frame assembly drawing package.

The released ``frame.SLDASM`` stays authoritative and byte-for-byte unchanged.
This recipe creates a transient exploded state in the open assembly, uses that
state for one native drawing view, saves the drawing package, and then closes
the dirty source assembly without saving it.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path
from typing import Any, Callable, Sequence

import _telemetry
from _common import _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_component_bom_balloons,
    create_blank_drawing_sheets,
    finalize_drawing,
    insert_bom_table,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_visible,
    set_high_quality_shaded_with_edges,
)
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view


SPEC = DRAWINGS_BY_NAME["frame_assembly"]
ARTIFACT_STEM = SPEC.artifact_stem
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

if SPEC.layout is not DrawingLayout.LANDSCAPE:
    raise AssertionError("the frame package requires the landscape ASME B template")

SHEET_NAMES = ("WORKING VIEWS", "EXPLODED VIEW + BOM", "ASSEMBLY")
SHEET_SCALE = (1.0, 6.0)
WORKING_FRONT_CENTER = (0.065, 0.155)
WORKING_RIGHT_CENTER = (0.150, 0.155)
WORKING_ISO_CENTER = (0.305, 0.160)
EXPLODED_ISO_CENTER = (0.305, 0.170)
EXPLODED_ISO_SCALE = (1.0, 8.0)
ASSEMBLY_ISO_CENTER = (0.335, 0.185)
ASSEMBLY_ISO_SCALE = (1.0, 10.0)
BOM_ANCHOR = (0.018, 0.263)

BOM_QUANTITIES = {
    "harmonic-base": 1,
    "tube-frame": 4,
    "rocker-arm-support": 1,
    "lag-screw": 4,
    "top-frame": 1,
    "nameplate": 1,
    "fillister-screw": 4,
    "frame-side-screw": 4,
    "gooseneck-set-screw": 1,
}
BOM_COMPONENTS = tuple(BOM_QUANTITIES)
BOM_DESCRIPTIONS = {
    "harmonic-base": "TWO-PLATE FRAME BASE",
    "tube-frame": "CAPPED HOLLOW FRAME COLUMN",
    "rocker-arm-support": "ROCKER-ARM SUPPORT CASTING",
    "lag-screw": "1/4-20 X 5/8 HEX-HEAD SCREW, 18-8 SS",
    "top-frame": "TOP-FRAME CASTING",
    "nameplate": "ENGRAVED BRASS MAKER'S NAMEPLATE",
    "fillister-screw": "BRASS #4-40 X 1/4 FILLISTER-HEAD SLOTTED SCREW",
    "frame-side-screw": "STEEL #8-32 X 1/2 NARROW FILLISTER-HEAD SLOTTED SCREW",
    "gooseneck-set-screw": "STEEL 1/4-20 X 5/8 SQUARE-HEAD CUP-POINT SET SCREW",
}
BOM_PART_NUMBERS = {
    "harmonic-base": "MHA-035",
    "tube-frame": "MHA-083",
    "rocker-arm-support": "MHA-089",
    "lag-screw": "MHA-039",
    "top-frame": "MHA-077",
    "nameplate": "MHA-086",
    "fillister-screw": "MHA-030",
    "frame-side-screw": "MHA-117",
    "gooseneck-set-screw": "MHA-118",
}
BOM_IDENTITY_ALIASES = {
    number: stem for stem, number in BOM_PART_NUMBERS.items()
}
BOM_NORMALIZED_ALIASES = {
    alias.casefold(): stem for alias, stem in BOM_IDENTITY_ALIASES.items()
}

# Distances are drawing-only displacements, not assembly requirements. The
# sequence first moves a part and its fasteners together, then pulls each
# fastener along its actual installation axis so mating faces remain readable.
_EXPLODE_Y = 1
_EXPLODE_X = 0
_EXPLODE_Z = 2
EXPLODE_STEP_COUNT = 11

# Source-grounded instructions only. The frame's concealed column/base and
# top-frame/column retention design is being resolved before this block is
# released; the complete list is filled from that approved design.
ASSEMBLY_STEPS = "\n".join(
    (
        "ASSEMBLY SEQUENCE",
        "1. SET THE HARMONIC BASE WITH ITS DECK FACE UP.",
        "2. PLACE THE FOUR CAPPED COLUMNS IN THE BASE SEATS, DOMED ENDS UP.",
        "3. SEAT THE ROCKER-ARM SUPPORT FOOT ON THE DECK; TURN ITS WINDOWED",
        "   FACES TOWARD THE LONG SIDES OF THE BASE.",
        "4. INSTALL FOUR MHA-039 HOLD-DOWN SCREWS TOP-DOWN THROUGH THE SUPPORT",
        "   FOOT INTO THE BASE TAPS. DRAW THE HEADS DOWN EVENLY.",
        "5. LAY THE NAMEPLATE FLAT ON THE EAST DECK, DECORATED FACE UP AND",
        "   READABLE FROM THE EAST SIDE.",
        "6. INSTALL FOUR MHA-030 BRASS SCREWS THROUGH THE PLATE INTO THE BASE.",
        "7. LOWER THE TOP FRAME OVER ALL FOUR COLUMNS WITH ITS GOOSENECK HUB",
        "   ON THE EAST SIDE.",
        "8. START MHA-118 IN THE HUB TAP; LEAVE ITS CUP POINT CLEAR OF THE",
        "   GOOSENECK BORE FOR THE LATER GOOSENECK INSTALLATION.",
    )
)
ASSEMBLY_CHECKS = "\n".join(
    (
        "ASSEMBLY-ONLY CHECKS",
        "1. SUPPORT FOOT IS FULLY SEATED ON THE DECK AND DOES NOT ROCK.",
        "2. ALL FOUR SUPPORT HOLD-DOWN HEADS BEAR ON THE FOOT.",
        "3. NAMEPLATE LIES FLAT, DECORATED FACE UP; ALL FOUR HEADS ARE SEATED.",
        "4. TOP FRAME PASSES OVER ALL FOUR COLUMNS WITHOUT BINDING.",
        "5. GOOSENECK BORE IS UNOBSTRUCTED WITH MHA-118 BACKED CLEAR.",
    )
)


def _as_tuple(value: Any, *, label: str) -> tuple[Any, ...]:
    if value is None or isinstance(value, str):
        raise RuntimeError(f"{label}: SolidWorks returned no object array")
    try:
        return tuple(value)
    except TypeError:
        return (value,)


def _source_fingerprint(path: Path) -> tuple[int, int, str]:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns, digest.hexdigest()


def _activate_sheet(adapter: Any, name: str) -> None:
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not ddoc.ActivateSheet(name):
        raise RuntimeError(f"failed to activate drawing sheet {name!r}")
    current = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    if current is None:
        raise RuntimeError("drawing has no current sheet after activation")
    actual = str(current.GetName() or "")
    if actual != name:
        raise RuntimeError(f"active drawing sheet is {actual!r}, expected {name!r}")


def _add_note_block(adapter: Any, text: str, xy: tuple[float, float], *, label: str) -> Any:
    note = add_note(adapter, text, *xy)
    if note is None:
        raise RuntimeError(f"failed to add {label}")
    note = _early_bound(note, "INote")
    if str(note.GetText() or "") != text:
        raise RuntimeError(f"{label} text did not persist")
    return note


def _set_exploded_state(adapter: Any, view: Any, show: bool, *, label: str) -> None:
    bound = _early_bound(view, "IView")
    returned = bool(bound.ShowExploded(show))
    actual = bool(bound.IsExploded())
    if actual != show:
        raise RuntimeError(
            f"{label}: exploded-state readback is {actual}, expected {show}"
        )
    if show and not returned:
        raise RuntimeError(f"{label}: ShowExploded returned false")
    adapter.currentModel.EditRebuild3()


def _align_working_views(front: Any, right: Any) -> None:
    front = _early_bound(front, "IView")
    right = _early_bound(right, "IView")
    # swAlignViewHorizontalCenter = 2: preserve the ASME side-view row.
    if not right.AlignWithView(2, front):
        raise RuntimeError("failed to align the working right view to the front view")
    if int(right.GetAlignment()) not in {2, 3}:  # aligned / aligned + children
        raise RuntimeError("working right view alignment did not persist")
    if int(front.GetAlignment()) not in {1, 3}:  # has aligned child / both
        raise RuntimeError("working front view does not retain its aligned child")


def _component_stem(component: Any) -> str:
    component = _early_bound(component, "IComponent2")
    path = str(component.GetPathName() or "")
    if not path:
        raise RuntimeError(f"component {component.Name2!r} has no referenced path")
    return Path(path).stem.casefold()


def _component_origin(component: Any) -> tuple[float, float, float]:
    component = _early_bound(component, "IComponent2")
    transform = _early_bound(component.Transform2, "IMathTransform")
    if transform is None:
        raise RuntimeError(f"component {component.Name2!r} has no transform")
    values = tuple(float(value) for value in transform.ArrayData)
    if len(values) != 16:
        raise RuntimeError(
            f"component {component.Name2!r} transform has {len(values)} values"
        )
    return values[9], values[10], values[11]


def _top_level_component_groups(
    assembly: Any,
) -> dict[str, tuple[Any, ...]]:
    assembly = _early_bound(assembly, "IAssemblyDoc")
    expected_total = sum(BOM_QUANTITIES.values())
    count = int(assembly.GetComponentCount(True))
    components = _as_tuple(
        assembly.GetComponents(True), label="frame top-level components"
    )
    if count != expected_total or len(components) != expected_total:
        raise RuntimeError(
            "frame top-level component count mismatch: "
            f"API={count}, returned={len(components)}, expected={expected_total}"
        )
    grouped: dict[str, list[Any]] = {stem: [] for stem in BOM_COMPONENTS}
    unexpected: list[str] = []
    for component in components:
        stem = _component_stem(component)
        if stem not in grouped:
            unexpected.append(stem)
            continue
        grouped[stem].append(component)
    wrong = {
        stem: len(items)
        for stem, items in grouped.items()
        if len(items) != BOM_QUANTITIES[stem]
    }
    if unexpected or wrong:
        raise RuntimeError(
            f"frame component families mismatch: unexpected={unexpected}, counts={wrong}"
        )
    return {stem: tuple(items) for stem, items in grouped.items()}


def _select_explode_components(
    source_model: Any, components: Sequence[Any], *, label: str
) -> tuple[str, ...]:
    source_model.ClearSelection2(True)
    selection_manager = _early_bound(source_model.SelectionManager, "ISelectionMgr")
    selection_data = _early_bound(selection_manager.CreateSelectData(), "ISelectData")
    if selection_data is None:
        raise RuntimeError(f"{label}: failed to create component selection data")
    selection_data.Mark = 1
    if int(selection_data.Mark) != 1:
        raise RuntimeError(f"{label}: selection mark 1 did not persist")
    names: list[str] = []
    for raw_component in components:
        component = _early_bound(raw_component, "IComponent2")
        name = str(component.Name2 or "")
        if not name or not component.Select4(True, selection_data, False):
            raise RuntimeError(f"{label}: failed to select component {name!r}")
        names.append(name)
    if len(names) != len(set(names)):
        raise RuntimeError(f"{label}: duplicate component identities {names!r}")
    return tuple(names)


def _add_native_explode_step(
    source_model: Any,
    configuration: Any,
    *,
    components: Sequence[Any],
    axis: int,
    reverse: bool,
    distance_m: float,
    label: str,
) -> Any:
    if axis not in {_EXPLODE_X, _EXPLODE_Y, _EXPLODE_Z} or distance_m <= 0.0:
        raise ValueError(f"{label}: invalid explode direction or distance")
    expected_names = _select_explode_components(
        source_model, components, label=label
    )
    before = int(configuration.GetNumberOfExplodeSteps())
    # AddExplodeStep2's generated early-bound wrapper returns
    # (IExplodeStep, swCreateExplodeStepError_e). The final [out] argument is
    # omitted deliberately; passing a BYREF VARIANT is the wrong convention for
    # InvokeTypes and silently loses the error code.
    result = configuration.AddExplodeStep2(
        float(distance_m),
        int(axis),
        bool(reverse),
        0.0,
        -1,
        False,
        True,
        False,
    )
    source_model.ClearSelection2(True)
    if not isinstance(result, tuple) or len(result) != 2:
        raise RuntimeError(f"{label}: incomplete AddExplodeStep2 result {result!r}")
    raw_step, error = result
    if int(error) != 0 or raw_step is None:
        raise RuntimeError(f"{label}: explode step failed with error {error!r}")
    step = _early_bound(raw_step, "IExplodeStep")
    step.Name = f"FRAME {label.upper()}"
    if str(step.Name or "") != f"FRAME {label.upper()}":
        raise RuntimeError(f"{label}: explode-step name did not persist")
    if not bool(source_model.EditRebuild3()):
        raise RuntimeError(f"{label}: rebuild failed after explode-step creation")
    after = int(configuration.GetNumberOfExplodeSteps())
    if after != before + 1:
        raise RuntimeError(f"{label}: explode-step count {before} -> {after}")
    actual_components = _as_tuple(
        step.GetComponents(), label=f"{label} explode-step components"
    )
    actual_names = {
        str(_early_bound(component, "IComponent2").Name2 or "")
        for component in actual_components
    }
    if actual_names != set(expected_names):
        raise RuntimeError(
            f"{label}: explode components {sorted(actual_names)!r} != "
            f"{sorted(expected_names)!r}"
        )
    if abs(float(step.ExplodeDistance) - distance_m) > 1e-9:
        raise RuntimeError(f"{label}: explode distance did not persist")
    return step


def _create_temporary_native_explode(
    adapter: Any, source_model: Any
) -> tuple[Any, str]:
    assembly = _early_bound(source_model, "IAssemblyDoc")
    configuration_manager = _early_bound(
        source_model.ConfigurationManager, "IConfigurationManager"
    )
    configuration = _early_bound(
        configuration_manager.ActiveConfiguration, "IConfiguration"
    )
    configuration_name = str(configuration.Name or "")
    if not configuration_name:
        raise RuntimeError("frame assembly has no active configuration")
    existing = int(assembly.GetExplodedViewCount2(configuration_name))
    if existing:
        raise RuntimeError(
            f"frame source already carries {existing} exploded view(s); "
            "refusing to alter a released definition"
        )
    if not assembly.CreateExplodedView():
        raise RuntimeError("failed to create transient frame exploded view")
    names = _as_tuple(
        assembly.GetExplodedViewNames2(configuration_name),
        label="frame exploded-view names",
    )
    if len(names) != 1:
        raise RuntimeError(f"frame exploded-view count mismatch: {names!r}")
    explode_name = str(names[0] or "")
    if not explode_name or not assembly.ShowExploded2(True, explode_name):
        raise RuntimeError(f"failed to activate frame exploded view {explode_name!r}")

    # CreateExplodedView can seed heuristic steps. They are unsuitable for a
    # checked package, so remove them before adding the deterministic sequence.
    for index in range(int(configuration.GetNumberOfExplodeSteps()) - 1, -1, -1):
        seed = _early_bound(configuration.GetExplodeStep(index), "IExplodeStep")
        seed_name = str(seed.Name or "") if seed is not None else ""
        if not seed_name or not configuration.DeleteExplodeStep(seed_name):
            raise RuntimeError(f"failed to remove auto explode step {seed_name!r}")
    if int(configuration.GetNumberOfExplodeSteps()) != 0:
        raise RuntimeError("auto explode steps remain before authored sequence")

    groups = _top_level_component_groups(assembly)
    front_side_screws = tuple(
        component
        for component in groups["frame-side-screw"]
        if _component_origin(component)[2] < 0.0
    )
    rear_side_screws = tuple(
        component
        for component in groups["frame-side-screw"]
        if _component_origin(component)[2] > 0.0
    )
    if len(front_side_screws) != 2 or len(rear_side_screws) != 2:
        raise RuntimeError("frame side screws do not split into two front/two rear")

    plans = (
        (
            "top frame clears columns",
            (
                *groups["top-frame"],
                *groups["frame-side-screw"],
                *groups["gooseneck-set-screw"],
            ),
            _EXPLODE_Y,
            False,
            0.150,
        ),
        (
            "front side screws withdraw",
            front_side_screws,
            _EXPLODE_Z,
            True,
            0.050,
        ),
        (
            "rear side screws withdraw",
            rear_side_screws,
            _EXPLODE_Z,
            False,
            0.050,
        ),
        (
            "gooseneck screw withdraws",
            groups["gooseneck-set-screw"],
            _EXPLODE_X,
            True,
            0.050,
        ),
        ("columns clear base seats", groups["tube-frame"], _EXPLODE_Y, False, 0.060),
        (
            "support lifts from deck",
            (*groups["rocker-arm-support"], *groups["lag-screw"]),
            _EXPLODE_Y,
            False,
            0.035,
        ),
        (
            "support moves beside base",
            (*groups["rocker-arm-support"], *groups["lag-screw"]),
            _EXPLODE_X,
            True,
            0.320,
        ),
        ("support screws withdraw", groups["lag-screw"], _EXPLODE_Y, False, 0.050),
        (
            "nameplate lifts from deck",
            (*groups["nameplate"], *groups["fillister-screw"]),
            _EXPLODE_Y,
            False,
            0.025,
        ),
        (
            "nameplate moves beside base",
            (*groups["nameplate"], *groups["fillister-screw"]),
            _EXPLODE_X,
            False,
            0.080,
        ),
        (
            "nameplate screws withdraw",
            groups["fillister-screw"],
            _EXPLODE_Y,
            False,
            0.035,
        ),
    )
    for label, components, axis, reverse, distance_m in plans:
        _add_native_explode_step(
            source_model,
            configuration,
            components=components,
            axis=axis,
            reverse=reverse,
            distance_m=distance_m,
            label=label,
        )
    if int(configuration.GetNumberOfExplodeSteps()) != EXPLODE_STEP_COUNT:
        raise RuntimeError("frame explode sequence did not retain all authored steps")
    if int(assembly.GetExplodedViewCount2(configuration_name)) != 1:
        raise RuntimeError("frame transient exploded-view count changed")
    return assembly, explode_name


def _normalized_bom_identity(text: str) -> str:
    normalized = text.strip().casefold()
    return BOM_NORMALIZED_ALIASES.get(normalized, normalized)


def _validate_frame_bom(adapter: Any, table: Any) -> tuple[tuple[str, str], ...]:
    table = _early_bound(table, "ITableAnnotation")
    rows = int(table.RowCount)
    columns = int(table.ColumnCount)
    if rows != len(BOM_COMPONENTS) + 1 or columns < 4:
        raise RuntimeError(
            f"frame BOM is {rows}x{columns}; expected "
            f"{len(BOM_COMPONENTS) + 1} rows and at least four columns"
        )
    contents = tuple(
        tuple(
            str(table.DisplayedText(row, column) or "").strip()
            for column in range(columns)
        )
        for row in range(rows)
    )
    header = tuple(cell.upper() for cell in contents[0])

    def column_named(predicate: Callable[[str], bool], label: str) -> int:
        matches = [index for index, cell in enumerate(header) if predicate(cell)]
        if len(matches) != 1:
            raise RuntimeError(f"frame BOM has no unique {label} column: {header!r}")
        return matches[0]

    item_column = column_named(lambda cell: cell.startswith("ITEM NO"), "ITEM NO.")
    part_column = column_named(lambda cell: cell == "PART NUMBER", "PART NUMBER")
    description_column = column_named(
        lambda cell: cell == "DESCRIPTION", "DESCRIPTION"
    )
    quantity_column = column_named(lambda cell: cell.startswith("QTY"), "QTY.")

    actual: dict[str, tuple[int, str, str, str]] = {}
    for row_index, row in enumerate(contents[1:], start=1):
        stem = _normalized_bom_identity(row[part_column])
        if stem in actual:
            raise RuntimeError(f"frame BOM repeats component family {stem!r}")
        actual[stem] = (
            row_index,
            row[item_column],
            row[description_column],
            row[quantity_column],
        )
    if set(actual) != set(BOM_COMPONENTS):
        raise RuntimeError(
            f"frame BOM identities {sorted(actual)!r} != "
            f"{sorted(BOM_COMPONENTS)!r}"
        )
    expected_items = {str(item) for item in range(1, len(BOM_COMPONENTS) + 1)}
    actual_items = {values[1] for values in actual.values()}
    if actual_items != expected_items:
        raise RuntimeError(
            f"frame BOM item numbers {sorted(actual_items)!r} != "
            f"{sorted(expected_items)!r}"
        )

    for stem, (row_index, _item, description, quantity) in actual.items():
        expected_part_number = BOM_PART_NUMBERS[stem]
        if contents[row_index][part_column] != expected_part_number:
            if not table.IsCellTextEditable(row_index, part_column):
                raise RuntimeError(
                    f"frame BOM part-number cell for {stem!r} is not editable"
                )
            table.SetText2(row_index, part_column, False, expected_part_number)
            applied = str(
                table.DisplayedText2(row_index, part_column, False) or ""
            ).strip()
            if applied != expected_part_number:
                raise RuntimeError(
                    f"frame BOM part number for {stem!r} did not persist"
                )
        if description != BOM_DESCRIPTIONS[stem]:
            raise RuntimeError(f"frame BOM description mismatch for {stem!r}")
        if quantity != str(BOM_QUANTITIES[stem]):
            raise RuntimeError(
                f"frame BOM quantity for {stem!r} is {quantity!r}, "
                f"expected {BOM_QUANTITIES[stem]}"
            )
    adapter.currentModel.EditRebuild3()
    for stem, (row_index, _item, _description, _quantity) in actual.items():
        applied = str(table.DisplayedText(row_index, part_column) or "").strip()
        if applied != BOM_PART_NUMBERS[stem]:
            raise RuntimeError(
                f"frame BOM part number for {stem!r} reverted to {applied!r}"
            )
    return tuple((stem, actual[stem][1]) for stem in BOM_COMPONENTS)


def _place_package(adapter: Any) -> None:
    new_project_drawing(adapter, layout=SPEC.layout, scale=SHEET_SCALE)
    create_blank_drawing_sheets(
        adapter, SHEET_NAMES, label="frame assembly package"
    )

    _activate_sheet(adapter, SHEET_NAMES[0])
    front = place_view(
        adapter,
        str(SOURCE),
        "*Front",
        *WORKING_FRONT_CENTER,
        scale=SHEET_SCALE,
    )
    right = place_view(
        adapter,
        str(SOURCE),
        "*Right",
        *WORKING_RIGHT_CENTER,
        scale=SHEET_SCALE,
    )
    iso = place_view(
        adapter,
        str(SOURCE),
        "*Isometric",
        *WORKING_ISO_CENTER,
        scale=SHEET_SCALE,
    )
    for label, view in (("working front", front), ("working right", right)):
        _set_exploded_state(adapter, view, False, label=label)
        set_hidden_lines_visible(adapter, view)
    _align_working_views(front, right)
    _set_exploded_state(adapter, iso, False, label="working isometric")
    set_high_quality_shaded_with_edges(
        adapter, iso, label="working isometric"
    )
    _add_note_block(
        adapter,
        "FINISHED ASSEMBLY - WORKING POSITION",
        (0.018, 0.263),
        label="working-view heading",
    )

    _activate_sheet(adapter, SHEET_NAMES[1])
    exploded = place_view(
        adapter,
        str(SOURCE),
        "*Isometric",
        *EXPLODED_ISO_CENTER,
        scale=EXPLODED_ISO_SCALE,
    )
    _set_exploded_state(adapter, exploded, True, label="exploded isometric")
    set_high_quality_shaded_with_edges(
        adapter, exploded, label="exploded isometric"
    )
    table = insert_bom_table(
        adapter,
        exploded,
        anchor_xy=BOM_ANCHOR,
        expected_components=BOM_COMPONENTS,
        descriptions=BOM_DESCRIPTIONS,
        identity_aliases=BOM_IDENTITY_ALIASES,
        configuration_grouping="same-part",
        label="frame",
    )
    balloon_items = _validate_frame_bom(adapter, table)
    add_component_bom_balloons(
        adapter,
        exploded,
        items=balloon_items,
        label="frame exploded-view BOM coverage",
        margin=0.012,
    )
    _add_note_block(
        adapter,
        "EXPLODED VIEW 1:8 - SEE SHEET 3 FOR INSTALLATION ORDER",
        (0.245, 0.078),
        label="exploded-view caption",
    )

    _activate_sheet(adapter, SHEET_NAMES[2])
    instruction_iso = place_view(
        adapter,
        str(SOURCE),
        "*Isometric",
        *ASSEMBLY_ISO_CENTER,
        scale=ASSEMBLY_ISO_SCALE,
    )
    _set_exploded_state(
        adapter, instruction_iso, False, label="assembly instruction isometric"
    )
    set_high_quality_shaded_with_edges(
        adapter, instruction_iso, label="assembly instruction isometric"
    )
    _add_note_block(
        adapter, ASSEMBLY_STEPS, (0.018, 0.263), label="assembly sequence"
    )
    _add_note_block(
        adapter, ASSEMBLY_CHECKS, (0.018, 0.105), label="assembly checks"
    )
    _add_note_block(
        adapter,
        "FINISHED ASSEMBLY 1:10",
        (0.300, 0.118),
        label="assembly isometric caption",
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")
    fingerprint = _source_fingerprint(SOURCE)
    check("open frame drawing source", await adapter.open_model(str(SOURCE)))
    source_model = _early_bound(adapter.currentModel, "IModelDoc2")
    if bool(source_model.GetSaveFlag()):
        raise RuntimeError(
            "frame source assembly is already dirty; refusing to discard user changes"
        )
    read_required_properties(
        source_model,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
        required=(
            "Number",
            "Revision",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
    )
    source_title = str(source_model.GetTitle() or "")
    if not source_title:
        raise RuntimeError("frame source assembly has no document title")

    assembly: Any | None = None
    explode_name = ""
    artifacts: dict[str, str] | None = None
    try:
        assembly, explode_name = _create_temporary_native_explode(
            adapter, source_model
        )
        _place_package(adapter)
        artifacts = await finalize_drawing(
            adapter,
            OUTPUTS,
            layout=SPEC.layout,
            pdf_title="Frame Assembly Drawing Package",
            scale=SHEET_SCALE,
            expected_sheet_names=SHEET_NAMES,
        )
    finally:
        collapse_error = ""
        if assembly is not None and explode_name:
            try:
                if not assembly.ShowExploded2(False, explode_name):
                    collapse_error = (
                        f"failed to collapse transient exploded view {explode_name!r}"
                    )
            except Exception as exc:
                collapse_error = f"failed to collapse transient exploded view: {exc}"
        adapter.swApp.CloseDoc(source_title)
        if adapter.swApp.GetOpenDocumentByName(str(SOURCE.resolve())) is not None:
            raise RuntimeError(
                f"frame source {source_title!r} remained open after discard"
            )
        if _source_fingerprint(SOURCE) != fingerprint:
            raise RuntimeError(
                "frame drawing generation changed the released source assembly"
            )
        if collapse_error:
            raise RuntimeError(collapse_error)

    if artifacts is None:
        raise RuntimeError("frame drawing package returned no artifacts")
    return artifacts


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[ARTIFACT_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
