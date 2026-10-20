"""Offline regressions for the two configured consumers of shared music wire."""

from types import SimpleNamespace

import pytest

import _com
import _component_references
import _drawing_tables
import draw_mg_magnifier_assembly as magnifier
import draw_pn_pen_assembly as pen
from sh_vn_music_wire_lever_spec import BOM_DESCRIPTION as LEVER_WIRE_DESCRIPTION
from sh_vn_music_wire_pen_spec import BOM_DESCRIPTION as PEN_WIRE_DESCRIPTION
from _assembly_contract import assembly_contract


CONSUMERS = ((magnifier, "LeverWire", "mg-magnifier"), (pen, "PenWire", "pn-pen"))
_IDENTITY = (
    1.0,
    0.0,
    0.0,
    0.0,
    1.0,
    0.0,
    0.0,
    0.0,
    1.0,
    0.0,
    0.0,
    0.0,
    1.0,
    0.0,
    0.0,
    0.0,
)


def _component(stem, configuration, reference="", native_index=73):
    return SimpleNamespace(
        Name2=f"{stem}--{configuration}-{native_index}",
        ReferencedConfiguration=configuration,
        ComponentReference=reference,
        GetPathName=lambda: f"C:/parts/{stem}.SLDPRT",
        GetTotalTransform=lambda _presentation: SimpleNamespace(ArrayData=_IDENTITY),
    )


def _source(drawing, member, *, reference=None):
    components = []
    wire = None
    for logical, (stem, configuration) in drawing.BOM_COMPONENT_IDENTITIES.items():
        for index in range(drawing.BOM_QUANTITIES[logical]):
            is_wire = logical == drawing.WIRE_ROW
            component = _component(
                stem,
                member if is_wire else (configuration or "Default"),
                (
                    reference
                    if reference is not None
                    else f"{member.removesuffix(' Simplified')}:1"
                )
                if is_wire
                else "",
                73 + len(components) + index,
            )
            components.append(component)
            if is_wire:
                wire = component
    model = SimpleNamespace(
        ConfigurationManager=SimpleNamespace(
            ActiveConfiguration=SimpleNamespace(Name="Default")
        ),
        GetExplodedViewNames2=lambda configuration: (
            drawing.EXPLODED_VIEW_NAMES[configuration],
        ),
        GetComponents=lambda _top_level: tuple(components),
    )
    return model, components, wire


def _unwrapped_com(monkeypatch, drawing):
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(_com, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(
        _component_references, "_early_bound", lambda value, _interface: value
    )
    monkeypatch.setattr(
        _drawing_tables._sw_type_info,
        "early_bound_or_flag",
        lambda value, *_args: value,
    )


@pytest.mark.parametrize("drawing,member,assembly", CONSUMERS)
@pytest.mark.parametrize("suffix", ("", " Simplified"))
def test_source_census_accepts_only_its_named_wire_member(
    monkeypatch, drawing, member, assembly, suffix
):
    _unwrapped_com(monkeypatch, drawing)
    model, _components, wire = _source(drawing, member + suffix)
    drawing._validate_source(model)
    # The semantic local ordinal is 1; SOLIDWORKS' allocator suffix is unrelated.
    assert not wire.Name2.endswith("-1")
    assert drawing.BOM_COMPONENT_IDENTITIES[drawing.WIRE_ROW] == (
        "sh-vn-music-wire",
        member,
    )
    assert drawing.BOM_QUANTITIES[drawing.WIRE_ROW] == 1
    assert drawing.BALLOON_ANCHORS[drawing.WIRE_ROW].instance == f"@{member}:1"
    contract = assembly_contract(assembly)
    assert "sh-vn-music-wire" in contract.allowed_free_stems
    assert "sh-vn-music-wire" in contract.required_free_stems


@pytest.mark.parametrize("drawing,member,_assembly", CONSUMERS)
@pytest.mark.parametrize(
    "wrong_member", ("", "Default", "other-member", "LeverWire extra")
)
def test_source_census_refuses_another_configuration_despite_the_shared_stem(
    monkeypatch, drawing, member, _assembly, wrong_member
):
    _unwrapped_com(monkeypatch, drawing)
    model, _components, _wire = _source(drawing, wrong_member, reference=f"{member}:1")
    with pytest.raises(RuntimeError, match="selects"):
        drawing._validate_source(model)


@pytest.mark.parametrize("drawing,member,_assembly", CONSUMERS)
def test_source_census_refuses_the_other_real_wire_member(
    monkeypatch, drawing, member, _assembly
):
    _unwrapped_com(monkeypatch, drawing)
    other = "PenWire" if member == "LeverWire" else "LeverWire"
    model, _components, _wire = _source(drawing, other, reference=f"{member}:1")
    with pytest.raises(RuntimeError, match="selects"):
        drawing._validate_source(model)


@pytest.mark.parametrize("drawing,member,_assembly", CONSUMERS)
def test_source_census_requires_the_persisted_reference(
    monkeypatch, drawing, member, _assembly
):
    _unwrapped_com(monkeypatch, drawing)
    model, _components, _wire = _source(drawing, member, reference="")
    with pytest.raises(RuntimeError, match="missing native component references"):
        drawing._validate_source(model)


@pytest.mark.parametrize("drawing,member,_assembly", CONSUMERS)
def test_source_census_refuses_an_extra_unreferenced_wire_member(
    monkeypatch, drawing, member, _assembly
):
    _unwrapped_com(monkeypatch, drawing)
    model, components, _wire = _source(drawing, member)
    other = "PenWire" if member == "LeverWire" else "LeverWire"
    components.append(_component("sh-vn-music-wire", other, native_index=211))
    with pytest.raises(RuntimeError, match="wire member"):
        drawing._validate_source(model)


@pytest.mark.parametrize("drawing,member,_assembly", CONSUMERS)
def test_source_reference_changes_fail_closed_until_restored(
    monkeypatch, drawing, member, _assembly
):
    _unwrapped_com(monkeypatch, drawing)
    model, components, wire = _source(drawing, member)
    drawing._validate_source(model)

    wire.ComponentReference = f"{member}:2"
    with pytest.raises(RuntimeError, match="missing native component references"):
        drawing._validate_source(model)
    wire.ComponentReference = f"{member}:1"
    drawing._validate_source(model)

    duplicate = _component("sh-vn-music-wire", member, f"{member}:1", native_index=211)
    components.append(duplicate)
    with pytest.raises(RuntimeError, match="duplicated"):
        drawing._validate_source(model)
    components.remove(duplicate)
    drawing._validate_source(model)


@pytest.mark.parametrize("drawing,member,_assembly", CONSUMERS)
def test_nested_wire_reference_cannot_satisfy_the_top_level_role(
    monkeypatch, drawing, member, _assembly
):
    _unwrapped_com(monkeypatch, drawing)
    model, _components, wire = _source(drawing, member)
    original_name = wire.Name2
    wire.Name2 = f"other-subassembly-9/{original_name}"
    with pytest.raises(RuntimeError, match="missing native component references"):
        drawing._validate_source(model)
    wire.Name2 = original_name
    drawing._validate_source(model)


@pytest.mark.parametrize("drawing,member,_assembly", CONSUMERS)
def test_source_census_rejects_missing_and_extra_physical_occurrences(
    monkeypatch, drawing, member, _assembly
):
    _unwrapped_com(monkeypatch, drawing)
    model, components, _wire = _source(drawing, member)
    first = components.pop(0)
    with pytest.raises(RuntimeError, match="families"):
        drawing._validate_source(model)
    components.insert(0, first)
    drawing._validate_source(model)
    components.append(first)
    with pytest.raises(RuntimeError, match="families"):
        drawing._validate_source(model)
    components.pop()
    drawing._validate_source(model)


@pytest.mark.parametrize("drawing,member,_assembly", CONSUMERS)
def test_source_census_requires_the_wire_presentation_to_be_collapsed(
    monkeypatch, drawing, member, _assembly
):
    _unwrapped_com(monkeypatch, drawing)
    model, _components, wire = _source(drawing, member)
    translated = list(_IDENTITY)
    translated[9] = 0.025
    wire.GetTotalTransform = lambda presentation: SimpleNamespace(
        ArrayData=tuple(translated) if presentation else _IDENTITY
    )
    with pytest.raises(RuntimeError, match="source must open collapsed"):
        drawing._validate_source(model)
    wire.GetTotalTransform = lambda _presentation: SimpleNamespace(ArrayData=_IDENTITY)
    drawing._validate_source(model)


class _Bom:
    def __init__(self, drawing, member):
        self.cells = [
            ["ITEM NO.", "PART NUMBER", "DESCRIPTION", "QTY.", "NATIVE PART NUMBER"]
        ]
        self.columns = [
            (202, None, False),
            (204, "Number", False),
            (204, "Description", False),
            (203, None, False),
            (201, False, True),
        ]
        self.components = {}
        self.writes = []
        for item, logical in enumerate(drawing.BOM_COMPONENTS, 1):
            stem, configuration = drawing.BOM_COMPONENT_IDENTITIES[logical]
            configuration = (
                member if logical == drawing.WIRE_ROW else (configuration or "Default")
            )
            self.components[item] = tuple(
                _component(stem, configuration, native_index=101 + index)
                for index in range(drawing.BOM_QUANTITIES[logical])
            )
            properties = {
                (configuration, "Number"): drawing.BOM_PART_NUMBERS[logical],
                ("", "Number"): drawing.BOM_PART_NUMBERS[logical],
            }
            native = SimpleNamespace(
                GetCustomInfoValue=lambda selected, name, properties=properties: (
                    properties.get((selected, name), "")
                )
            )
            for component in self.components[item]:
                component.GetModelDoc2 = lambda native=native: native
            self.cells.append(
                [
                    str(item),
                    drawing.BOM_PART_NUMBERS[logical],
                    (
                        {
                            "LeverWire": LEVER_WIRE_DESCRIPTION,
                            "PenWire": PEN_WIRE_DESCRIPTION,
                        }[member.removesuffix(" Simplified")]
                        if logical == drawing.WIRE_ROW
                        else drawing.BOM_DESCRIPTIONS[logical]
                    ),
                    str(drawing.BOM_QUANTITIES[logical]),
                    logical,
                ]
            )

    @property
    def RowCount(self):
        return len(self.cells)

    @property
    def ColumnCount(self):
        return sum(not hidden for _kind, _property, hidden in self.columns)

    @property
    def TotalColumnCount(self):
        return len(self.columns)

    def GetColumnType3(self, index, include_hidden):
        kind, property_data, _hidden = self.columns[index]
        return kind, property_data, 0

    def ColumnHidden(self, index):
        return self.columns[index][2]

    def GetColumnCustomProperty(self, index):
        return self.columns[index][1]

    def DisplayedText(self, row, column):
        return self.cells[row][column]

    def GetComponents2(self, row, configuration):
        return self.components[row] if configuration == "Default Simplified" else ()

    def IsCellTextEditable(self, _row, column):
        return column != 1

    def SetText2(self, row, column, _include_hidden, text):
        assert column != 1, "the associative Number column must never be overwritten"
        self.writes.append((row, column, text))
        self.cells[row][column] = text

    def InsertColumn2(self, position, column, title, _width):
        if position not in (2, 3):
            raise ValueError("this fixture supports native Before/After insertion")
        index = column + (position == 3)
        self.columns.insert(index, (0, None, False))
        for row_index, row in enumerate(self.cells):
            row.insert(index, title if row_index == 0 else "")
        return True

    def SetColumnTitle2(self, column, title, _include_hidden):
        self.cells[0][column] = title
        return True

    def SetColumnWidth(self, _column, width, _options):
        return width

    def SetRowHeight(self, _row, _height, _options):
        return None


@pytest.mark.parametrize("drawing,member,_assembly", CONSUMERS)
def test_bom_uses_native_member_identity_and_preserves_associative_numbers(
    monkeypatch, drawing, member, _assembly
):
    _unwrapped_com(monkeypatch, drawing)
    table = _Bom(drawing, member + " Simplified")
    adapter = SimpleNamespace(currentModel=SimpleNamespace(EditRebuild3=lambda: True))
    items = dict(drawing._validate_bom(adapter, table))
    assert items == {
        logical: str(item) for item, logical in enumerate(drawing.BOM_COMPONENTS, 1)
    }
    assert table.cells[int(items[drawing.WIRE_ROW])][1] == "MHA-SH-VN-56"
    assert all(column != 1 for _row, column, _text in table.writes)


@pytest.mark.parametrize("drawing,member,_assembly", CONSUMERS)
def test_bom_rejects_another_member_even_with_the_same_printed_number(
    monkeypatch, drawing, member, _assembly
):
    _unwrapped_com(monkeypatch, drawing)
    other = "PenWire" if member == "LeverWire" else "LeverWire"
    table = _Bom(drawing, other)
    adapter = SimpleNamespace(currentModel=SimpleNamespace(EditRebuild3=lambda: True))
    with pytest.raises(RuntimeError, match="expected one logical member"):
        drawing._validate_bom(adapter, table)


@pytest.mark.parametrize("drawing,member,_assembly", CONSUMERS)
def test_bom_refuses_a_blank_number_instead_of_repairing_the_cell(
    monkeypatch, drawing, member, _assembly
):
    _unwrapped_com(monkeypatch, drawing)
    table = _Bom(drawing, member)
    wire_row = drawing.BOM_COMPONENTS.index(drawing.WIRE_ROW) + 1
    table.cells[wire_row][1] = ""
    adapter = SimpleNamespace(currentModel=SimpleNamespace(EditRebuild3=lambda: True))
    with pytest.raises(RuntimeError, match="BOM Number"):
        drawing._validate_bom(adapter, table)
    assert not table.writes


@pytest.mark.parametrize("drawing,member,_assembly", CONSUMERS)
def test_bom_rejects_a_changed_physical_wire_quantity(
    monkeypatch, drawing, member, _assembly
):
    _unwrapped_com(monkeypatch, drawing)
    table = _Bom(drawing, member)
    wire_row = drawing.BOM_COMPONENTS.index(drawing.WIRE_ROW) + 1
    table.cells[wire_row][3] = "2"
    adapter = SimpleNamespace(currentModel=SimpleNamespace(EditRebuild3=lambda: True))
    with pytest.raises(RuntimeError, match="BOM quantity"):
        drawing._validate_bom(adapter, table)
    assert not table.writes


@pytest.mark.parametrize("drawing,member,_assembly", CONSUMERS)
def test_bom_rejects_a_row_without_a_native_member_association(
    monkeypatch, drawing, member, _assembly
):
    _unwrapped_com(monkeypatch, drawing)
    table = _Bom(drawing, member)
    wire_row = drawing.BOM_COMPONENTS.index(drawing.WIRE_ROW) + 1
    table.components[wire_row] = ()
    adapter = SimpleNamespace(currentModel=SimpleNamespace(EditRebuild3=lambda: True))
    with pytest.raises(RuntimeError, match="no native component association"):
        drawing._validate_bom(adapter, table)
    assert not table.writes


@pytest.mark.parametrize("drawing,member,_assembly", CONSUMERS)
def test_bom_rejects_an_unexpected_native_wire_description(
    monkeypatch, drawing, member, _assembly
):
    _unwrapped_com(monkeypatch, drawing)
    table = _Bom(drawing, member)
    wire_row = drawing.BOM_COMPONENTS.index(drawing.WIRE_ROW) + 1
    table.cells[wire_row][2] = "WRONG MEMBER DESCRIPTION"
    adapter = SimpleNamespace(currentModel=SimpleNamespace(EditRebuild3=lambda: True))
    with pytest.raises(RuntimeError, match="BOM description mismatch"):
        drawing._validate_bom(adapter, table)
    assert not table.writes


@pytest.mark.parametrize("drawing,member,_assembly", CONSUMERS)
@pytest.mark.parametrize("damage", ("quantity", "same-number-member", "multiplicity"))
def test_bom_does_not_accept_rebuild_damage_as_its_settled_baseline(
    monkeypatch, drawing, member, _assembly, damage
):
    _unwrapped_com(monkeypatch, drawing)
    table = _Bom(drawing, member + " Simplified")
    wire_row = drawing.BOM_COMPONENTS.index(drawing.WIRE_ROW) + 1
    original_number = table.cells[wire_row][1]

    def rebuild_with_damage():
        if damage == "quantity":
            quantity_column = table.cells[0].index("QTY.")
            table.cells[wire_row][quantity_column] = "2"
        elif damage == "same-number-member":
            component = table.components[wire_row][0]
            other = "PenWire" if member == "LeverWire" else "LeverWire"
            component.ReferencedConfiguration = other + " Simplified"
        else:
            component = table.components[wire_row][0]
            duplicate = _component(
                "sh-vn-music-wire", member + " Simplified", native_index=981
            )
            duplicate.GetModelDoc2 = component.GetModelDoc2
            table.components[wire_row] += (duplicate,)
        return True

    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(EditRebuild3=rebuild_with_damage)
    )
    message = (
        "membership.*quantities.*changed"
        if damage == "same-number-member"
        else "native occurrence count.*printed quantity"
    )
    with pytest.raises(RuntimeError, match=message):
        drawing._validate_bom(adapter, table)
    assert table.cells[wire_row][1] == original_number
    assert all(column != 1 for _row, column, _text in table.writes)


def test_wire_application_instructions_stay_with_the_assembly_consumers():
    magnifier_steps = " ".join(magnifier.notes.ASSEMBLY_STEPS)
    pen_steps = " ".join(pen.notes.ASSEMBLY_STEPS)
    assert (
        "HOOK THE MHA-SH-VN-56 LEVER WIRE IN THE MHA-MG-06 OUTPUT FIXTURE SPIGOT GROOVE"
        in magnifier_steps
    )
    assert "WRAP IT CLOCKWISE DOWN THE MHA-MG-10 DRUM" in magnifier_steps
    assert "THROUGH THE MHA-PN-07 ADJUSTER STUD EYE" in pen_steps
    assert "SEAT THE PEN WIRE IN THE MHA-MG-05 WHEEL RIM GROOVE" in pen_steps
