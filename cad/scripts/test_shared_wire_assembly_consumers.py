"""Offline regressions for the two configured consumers of shared music wire."""

from pathlib import Path
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
            if drawing is magnifier and not is_wire:
                component.Name2 = f"{stem}-{index + 1}"
            components.append(component)
            if is_wire:
                wire = component
    properties = {}
    if drawing is magnifier:
        instances = [
            magnifier.explode.Instance(
                str(component.Name2), Path(component.GetPathName()).stem
            )
            for component in components
        ]
        offsets = {item.name.casefold(): [0.0, 0.0, 0.0] for item in instances}
        for step, names in magnifier.explode.plan_explode(instances):
            for name in names:
                offsets[name.casefold()]["xyz".index(step.axis)] += (
                    step.distance_mm / 1000.0
                )
        properties = {
            ("", magnifier.explode.explode_offsets_property(owner)): (
                magnifier.explode.encode_explode_offsets(owner, offsets, instances)
            )
            for owner in drawing.EXPLODED_VIEW_NAMES
        }
    model = SimpleNamespace(
        ConfigurationManager=SimpleNamespace(
            ActiveConfiguration=SimpleNamespace(Name="Default")
        ),
        GetExplodedViewNames2=lambda configuration: (
            drawing.EXPLODED_VIEW_NAMES[configuration],
        ),
        GetComponents=lambda _top_level: tuple(components),
        GetCustomInfoValue=lambda configuration, name: properties.get(
            (configuration, name), ""
        ),
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
    def __init__(
        self,
        drawing,
        member,
        *,
        configurations=(("Default", "Default Simplified"), (False, True)),
    ):
        self.cells = [["ITEM NO.", "PART NUMBER", "DESCRIPTION", "QTY.", "PART NUMBER"]]
        self.configurations = configurations
        self.BomFeature = SimpleNamespace(
            GetConfigurations=lambda _only_visible, _unused: self.configurations
        )
        self.columns = [
            {"kind": 202, "property": None, "hidden": False, "width": 0.02},
            {
                "kind": 204,
                "property": '$PRP:"Number"',
                "binding": "Number",
                "hidden": False,
                "width": 0.02,
            },
            {"kind": 204, "property": "Description", "hidden": False, "width": 0.02},
            {"kind": 203, "property": None, "hidden": False, "width": 0.02},
            {"kind": 201, "property": False, "hidden": True, "width": 0.0},
        ]
        self.number_property_readback = "Number"
        self.hidden_rows = set()
        self.components = {}
        self.writes = []
        self.title_writes = []
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
    def TotalRowCount(self):
        return len(self.cells)

    def RowHidden(self, row):
        if not 0 <= row < len(self.cells):
            raise IndexError("invalid physical row")
        return row in self.hidden_rows

    @property
    def ColumnCount(self):
        return sum(not column["hidden"] for column in self.columns)

    @property
    def TotalColumnCount(self):
        return len(self.columns) + len(self.configurations[0]) - 1

    def _column_index(self, index, include_hidden):
        indices = [
            physical
            for physical, column in enumerate(self.columns)
            if include_hidden or not column["hidden"]
        ]
        return indices[index] if 0 <= index < len(indices) else None

    def GetColumnType3(self, index, include_hidden):
        physical = self._column_index(index, include_hidden)
        if physical is None:
            return -1, None, 0
        column = self.columns[physical]
        return column["kind"], column["property"], 0

    def _visibility_slots(self):
        # 0-based native visibility domain: deselected configurations' latent
        # Quantity columns precede the selected Qty (k of them) or trail.
        names, flags = self.configurations
        selected = flags.index(True)
        slots = list(range(len(self.columns)))
        quantity = next(
            index for index, column in enumerate(self.columns) if column["kind"] == 203
        )
        latent = len(names) - 1
        return (
            slots[:quantity]
            + [None] * selected
            + slots[quantity:]
            + [None] * (latent - selected)
        )

    def ColumnHidden(self, index):
        slots = self._visibility_slots()
        physical = slots[index] if 0 <= index < len(slots) else None
        return self.columns[physical]["hidden"] if physical is not None else False

    def SetColumnHidden(self, index, hidden):
        slots = self._visibility_slots()
        if not 0 <= index < len(slots):
            raise IndexError("invalid visibility property")
        physical = slots[index]
        if physical is None:
            raise AssertionError("latent Quantity column must not be written")
        self.columns[physical]["hidden"] = hidden

    def GetColumnWidth(self, index):
        physical = self._column_index(index, False)
        return self.columns[physical]["width"] if physical is not None else 0.0

    def GetColumnTitle2(self, index, include_hidden):
        return self.DisplayedText2(0, index, include_hidden)

    def GetColumnCustomProperty(self, index):
        physical = self._column_index(index, True)
        if physical is None or self.columns[physical]["kind"] != 204:
            return ""
        column = self.columns[physical]
        if column.get("binding") == "Number":
            return self.number_property_readback
        return column["property"]

    def DisplayedText(self, row, column):
        return self.DisplayedText2(row, column, False)

    def DisplayedText2(self, row, column, include_hidden):
        physical = self._column_index(column, include_hidden)
        return self.cells[row][physical] if physical is not None else ""

    def GetComponents2(self, row, configuration):
        names, flags = self.configurations
        selected = names[flags.index(True)]
        return self.components[row] if configuration == selected else ()

    def IsCellTextEditable(self, _row, column):
        physical = self._column_index(column, True)
        if physical is None:
            raise IndexError("invalid physical column")
        return self.columns[physical].get("binding") != "Number"

    def SetText2(self, row, column, include_hidden, text):
        physical = self._column_index(column, include_hidden)
        if physical is None:
            raise IndexError("invalid displayed column write")
        assert self.columns[physical].get("binding") != "Number", (
            "the associative Number column must never be overwritten"
        )
        self.writes.append((row, column, include_hidden, text))
        self.cells[row][physical] = text

    def InsertColumn2(self, position, column, title, _width):
        if position not in (2, 3):
            raise ValueError("this fixture supports native Before/After insertion")
        if self._column_index(column, True) is None:
            raise IndexError("invalid physical column insertion")
        index = column + (position == 3)
        self.columns.insert(
            index,
            {"kind": 0, "property": None, "hidden": False, "width": 0.02},
        )
        for row_index, row in enumerate(self.cells):
            row.insert(index, title if row_index == 0 else "")
        return True

    def SetColumnTitle2(self, column, title, include_hidden):
        physical = self._column_index(column, include_hidden)
        if physical is None:
            raise IndexError("invalid physical column title")
        self.title_writes.append((column, title, include_hidden))
        self.cells[0][physical] = title
        return True

    def SetColumnWidth(self, column, width, _options):
        physical = self._column_index(column, False)
        if physical is None:
            raise IndexError("invalid visible column width")
        self.columns[physical]["width"] = width
        return width

    def SetRowHeight(self, _row, _height, _options):
        return None


@pytest.mark.parametrize("drawing,member,_assembly", CONSUMERS)
@pytest.mark.parametrize(
    "configurations",
    [
        (("Default Simplified",), (True,)),
        (("Default Simplified", "Default"), (True, False)),
        (("Default", "Default Simplified"), (False, True)),
    ],
    ids=["single", "selected-first", "selected-second"],
)
def test_bom_uses_native_member_identity_and_preserves_associative_numbers(
    monkeypatch, drawing, member, _assembly, configurations
):
    _unwrapped_com(monkeypatch, drawing)
    table = _Bom(drawing, member + " Simplified", configurations=configurations)
    latent = len(configurations[0]) - 1
    latent_before = configurations[1].index(True)
    assert table.GetColumnType3(4, True)[0] == 201
    # Typed Qty3 / native201[4] sit after the k latents preceding the selected Qty.
    assert table.ColumnHidden(3 + latent_before) is False
    assert table.ColumnHidden(4 + latent_before) is True
    assert table.GetColumnType3(5, True) == (-1, None, 0)
    adapter = SimpleNamespace(currentModel=SimpleNamespace(EditRebuild3=lambda: True))
    items = dict(drawing._validate_bom(adapter, table))
    assert items == {
        logical: str(item) for item, logical in enumerate(drawing.BOM_COMPONENTS, 1)
    }
    assert table.cells[int(items[drawing.WIRE_ROW])][1] == "MHA-SH-VN-56"
    assert all(
        column != 1 and include_hidden is True
        for _row, column, include_hidden, _text in table.writes
    )
    assert len(table.columns) == table.ColumnCount + 1
    assert table.TotalColumnCount == len(table.columns) + latent
    native_column = len(table.columns) - 1
    assert table.GetColumnType3(native_column, True)[0] == 201
    assert native_column == 5
    assert _drawing_tables._bom_column_hidden(table, native_column, label="native")
    assert not _drawing_tables._bom_column_hidden(
        table, native_column - 1, label="native"
    )
    assert table.GetColumnWidth(native_column) == 0.0
    assert table.GetColumnType3(1, True) == (204, '$PRP:"Number"', 0)
    assert table.GetColumnCustomProperty(1) == "Number"
    quantity_column = table.cells[0].index("QTY.")
    sku_column = table.cells[0].index(drawing.BOM_SKU_TITLE)
    assert table.title_writes
    assert all(
        include_hidden is True for _column, _title, include_hidden in table.title_writes
    )
    assert table.GetColumnType3(quantity_column, True)[0] == 203
    assert table.GetColumnType3(quantity_column, False)[0] == 203
    assert table.DisplayedText2(0, quantity_column, True) == "QTY."
    assert table.DisplayedText2(0, quantity_column, False) == "QTY."
    assert table.DisplayedText(0, quantity_column) == "QTY."
    wire_row = int(items[drawing.WIRE_ROW])
    assert table.DisplayedText2(wire_row, quantity_column, False) == str(
        drawing.BOM_QUANTITIES[drawing.WIRE_ROW]
    )
    assert table.DisplayedText(wire_row, 1) == "MHA-SH-VN-56"
    snapshot = _drawing_tables.validate_bom_number_property(
        table,
        configuration="Default Simplified",
        label="physical shared wire quantities",
        expected_rows=1 + len(drawing.BOM_COMPONENTS),
        occurrence_quantities=True,
    )
    assert [
        (row, number, quantity) for row, _members, number, quantity in snapshot
    ] == [
        (item, drawing.BOM_PART_NUMBERS[logical], str(drawing.BOM_QUANTITIES[logical]))
        for item, logical in enumerate(drawing.BOM_COMPONENTS, 1)
    ]
    for item, logical in enumerate(drawing.BOM_COMPONENTS, 1):
        assert table.DisplayedText2(item, quantity_column, True) == str(
            drawing.BOM_QUANTITIES[logical]
        )
        assert table.DisplayedText2(item, quantity_column, False) == str(
            drawing.BOM_QUANTITIES[logical]
        )
        assert table.DisplayedText2(item, 1, False) == drawing.BOM_PART_NUMBERS[logical]
        assert table.cells[item][quantity_column] == str(
            drawing.BOM_QUANTITIES[logical]
        )
        assert table.DisplayedText2(item, sku_column, True) == drawing.BOM_SKUS[logical]
    table.cells[wire_row][native_column] = "999"
    assert table.DisplayedText(wire_row, quantity_column) == str(
        drawing.BOM_QUANTITIES[drawing.WIRE_ROW]
    )
    assert (
        _drawing_tables.validate_bom_number_property(
            table,
            configuration="Default Simplified",
            label="changed hidden native key",
            expected_rows=1 + len(drawing.BOM_COMPONENTS),
            occurrence_quantities=True,
        )
        == snapshot
    )
    for index in range(len(table.columns), table.TotalColumnCount + 2):
        for include_hidden in (False, True):
            assert table.GetColumnType3(index, include_hidden) == (-1, None, 0)
            assert table.GetColumnTitle2(index, include_hidden) == ""
            assert table.DisplayedText2(0, index, include_hidden) == ""
        assert table.GetColumnWidth(index) == 0.0
        # Past-the-end visibility index (shifted by the k preceding latents).
        assert table.ColumnHidden(index + latent_before) is False
        assert table.GetColumnCustomProperty(index) == ""


@pytest.mark.parametrize("drawing,member,_assembly", CONSUMERS)
@pytest.mark.parametrize(
    "fault", ("qty-hidden", "number-hidden", "qty-type", "qty-text", "number-text")
)
def test_bom_refuses_invisible_or_wrong_visible_projection_after_sku(
    monkeypatch, drawing, member, _assembly, fault
):
    _unwrapped_com(monkeypatch, drawing)
    table = _Bom(drawing, member + " Simplified")
    adapter = SimpleNamespace(currentModel=SimpleNamespace(EditRebuild3=lambda: True))
    drawing._validate_bom(adapter, table)
    quantity_column = table.cells[0].index("QTY.")
    native_column = len(table.columns) - 1
    physical_cells = tuple(tuple(row) for row in table.cells)
    native_members = dict(table.components)
    if fault in ("qty-hidden", "number-hidden"):
        # Model the real wrong-property mutation, not a fabricated False view.
        hidden_column = quantity_column if fault == "qty-hidden" else 1
        _drawing_tables._set_bom_column_hidden(table, hidden_column, True, label="f")
        _drawing_tables._set_bom_column_hidden(table, native_column, False, label="f")
        table.columns[native_column]["width"] = 0.02
        assert table.GetColumnType3(hidden_column, True)[0] in (203, 204)
        assert table.GetColumnTitle2(hidden_column, False) != (
            table.GetColumnTitle2(hidden_column, True)
        )
        reason = "BOM visible columns are not a contiguous prefix"
    elif fault == "qty-type":
        native_type = table.GetColumnType3

        def wrong_visible_type(column, include_hidden):
            if not include_hidden and column == quantity_column:
                return native_type(native_column, True)
            return native_type(column, include_hidden)

        monkeypatch.setattr(table, "GetColumnType3", wrong_visible_type)
        assert table.GetColumnType3(quantity_column, False) != (
            table.GetColumnType3(quantity_column, True)
        )
        reason = "BOM visible column projection disagrees"
    else:
        native_text = table.DisplayedText2
        damaged_column = quantity_column if fault == "qty-text" else 1

        def wrong_visible_text(row, column, include_hidden):
            if not include_hidden and row == 1 and column == damaged_column:
                return "999"
            return native_text(row, column, include_hidden)

        monkeypatch.setattr(table, "DisplayedText2", wrong_visible_text)
        assert table.DisplayedText2(1, damaged_column, False) != (
            table.DisplayedText2(1, damaged_column, True)
        )
        name = "quantity" if fault == "qty-text" else "Number"
        reason = rf"BOM row 1: visible {name} .*does not match physical {name}"
    with pytest.raises(RuntimeError, match=reason):
        _drawing_tables.validate_bom_number_property(
            table,
            configuration="Default Simplified",
            label="visible shared wire Number and Qty",
            expected_rows=1 + len(drawing.BOM_COMPONENTS),
            occurrence_quantities=True,
        )
    assert tuple(tuple(row) for row in table.cells) == physical_cells
    assert table.components == native_members


@pytest.mark.parametrize("drawing,member,_assembly", CONSUMERS)
@pytest.mark.parametrize("hidden", ["header", "wire"])
def test_bom_refuses_hidden_physical_rows_before_writing_vendor_skus(
    monkeypatch, drawing, member, _assembly, hidden
):
    _unwrapped_com(monkeypatch, drawing)
    table = _Bom(drawing, member)
    wire_row = drawing.BOM_COMPONENTS.index(drawing.WIRE_ROW) + 1
    table.hidden_rows.add(0 if hidden == "header" else wire_row)
    adapter = SimpleNamespace(currentModel=SimpleNamespace(EditRebuild3=lambda: True))
    with pytest.raises(RuntimeError):
        drawing._validate_bom(adapter, table)
    assert not table.writes
    assert not table.title_writes
    assert len(table.columns) == 5


@pytest.mark.parametrize("drawing,member,_assembly", CONSUMERS)
@pytest.mark.parametrize("raw_property_data", ["Number", '$PRP:"Number"'])
@pytest.mark.parametrize("fault", ["wrong", "blank", "unreadable"])
def test_bom_requires_native_number_getter_even_when_raw_metadata_looks_bound(
    monkeypatch, drawing, member, _assembly, raw_property_data, fault
):
    _unwrapped_com(monkeypatch, drawing)
    table = _Bom(drawing, member)
    table.columns[1]["property"] = raw_property_data
    if fault == "unreadable":
        native_getter = table.GetColumnCustomProperty

        def unreadable_property(column):
            physical = table._column_index(column, True)
            if (
                physical is not None
                and table.columns[physical].get("binding") == "Number"
            ):
                raise RuntimeError("native custom-property getter failed")
            return native_getter(column)

        monkeypatch.setattr(table, "GetColumnCustomProperty", unreadable_property)
    else:
        table.number_property_readback = "Description" if fault == "wrong" else ""
    adapter = SimpleNamespace(currentModel=SimpleNamespace(EditRebuild3=lambda: True))
    message = (
        "native custom-property getter failed"
        if fault == "unreadable"
        else "Number property binding did not persist"
    )
    with pytest.raises(RuntimeError, match=message):
        drawing._validate_bom(adapter, table)
    assert [row[1] for row in table.cells[1:]] == [
        drawing.BOM_PART_NUMBERS[logical] for logical in drawing.BOM_COMPONENTS
    ]
    assert all(column != 1 for _row, column, _include_hidden, _text in table.writes)


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
    assert all(column != 1 for _row, column, _include_hidden, _text in table.writes)


def test_wire_application_instructions_stay_with_the_assembly_consumers():
    magnifier_steps = " ".join(magnifier.notes.ASSEMBLY_STEPS)
    pen_steps = " ".join(pen.notes.ASSEMBLY_STEPS)
    assert (
        "HOOK THE MHA-SH-VN-56 LEVER WIRE IN THE MHA-MG-06 OUTPUT FIXTURE SPIGOT GROOVE"
        in magnifier_steps
    )
    assert "WRAP IT CLOCKWISE DOWN THE MHA-MG-10 DRUM" in magnifier_steps
    # The pen wire's step names both the wire and the stud whose eye takes it.
    notes = pen.notes
    (eye_step,) = [
        step for step in notes.ASSEMBLY_STEPS
        if f"(ITEM {notes.ITEM[notes.WIRE]})" in step and " EYE " in step
    ]
    assert f"(ITEM {notes.ITEM[notes.STUD]})" in eye_step
    assert "SEAT THE PEN WIRE IN THE MHA-MG-05 WHEEL RIM GROOVE" in pen_steps
