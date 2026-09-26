"""Title-block MATERIAL prints the part's Material Specification (#923 fleet).

The template's MATERIAL cell linked the registry's short ``material`` family
name ("Brass"), so conegear's 834b eye-pass found T006-T024 -- specified
C67500 -- telling a machinist to cut generic brass. finalize_drawing now
retargets the cell to the Material Specification on every sheet and reads
MATERIAL and FINISH back against the linked model.
"""

from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

import _common
import _config
import _drawing_common
import _purchased_fastener_drawing
from _drawing_registry import DRAWINGS

MATERIAL_LINK = '$PRPSHEET:"Material"'
SPEC_LINK = '$PRPSHEET:"Material Specification"'
FINISH_LINK = '$PRPSHEET:"Finish"'


# Landscape cells (registry); a value's default extent sits inside either.
CELLS = {
    "Material Specification": (0.2181, 0.0260, 0.3105, 0.0336),
    "Finish": (0.2181, 0.0336, 0.3105, 0.0445),
}
INSIDE = {
    "Material Specification": (0.2200, 0.0270, 0.0, 0.3000, 0.0330, 0.0),
    "Finish": (0.2200, 0.0350, 0.0, 0.3000, 0.0440, 0.0),
}


class _Note:
    def __init__(
        self, linked: str, printed: str | None = None, *, sticky: bool = True, extent: tuple | None = None
    ) -> None:
        self._linked = linked
        self._printed = printed
        self._sticky = sticky
        self._extent = extent

    def GetExtent(self) -> tuple:
        if self._extent is not None:
            return self._extent
        return INSIDE["Finish" if "Finish" in self._linked else "Material Specification"]

    @property
    def PropertyLinkedText(self) -> str:
        return self._linked

    @PropertyLinkedText.setter
    def PropertyLinkedText(self, value: str) -> None:
        if self._sticky:
            self._linked = value

    def GetText(self) -> str:
        return self._printed if self._printed is not None else self._linked


class _Annotation:
    def __init__(self, note: _Note, kind: int = 6) -> None:
        self._note = note
        self._kind = kind

    def GetType(self) -> int:
        return self._kind

    def GetSpecificAnnotation(self) -> _Note:
        return self._note


class _Drawing:
    def __init__(self, notes: list[_Note], properties: dict[str, str] | None = None) -> None:
        self.notes = notes
        self.properties = properties or {}

    def GetFirstView(self) -> SimpleNamespace:
        return SimpleNamespace(GetAnnotations=lambda: [_Annotation(note) for note in self.notes])

    def GetCustomInfoValue(self, configuration: str, name: str) -> str:
        assert configuration == ""
        return self.properties.get(name, "")


class _Model:
    def __init__(self, file_level: dict[str, str], by_config: dict[str, dict[str, str]] | None = None) -> None:
        self.file_level = file_level
        self.by_config = by_config or {}

    def GetCustomInfoValue(self, configuration: str, name: str) -> str:
        if configuration == "":
            return self.file_level.get(name, "")
        return self.by_config.get(configuration, {}).get(name, "")


@pytest.fixture(autouse=True)
def _late_bound(monkeypatch):
    monkeypatch.setattr(_drawing_common, "_early_bound", lambda value, _kind: value)


def _resolve(notes, model, configuration="Default", properties=None):
    return _drawing_common.assert_title_block_resolves(
        _Drawing(notes, properties), model, configuration, drawing="MHA-013", sheet="T006", cells=CELLS
    )


# -- registry: every drawn part has what the two cells print -----------------


def _drawn_parts() -> list[str]:
    return sorted({spec.source.stem for spec in DRAWINGS if spec.source_kind == "part"})


def test_every_drawn_part_specifies_its_material_and_finish():
    """A gap -- blank or a placeholder such as NONE -- is fixed in the part's
    registry row, never exempted here."""
    gaps = {
        stem: key
        for stem in _drawn_parts()
        for key in ("material_specification", "finish")
        if _drawing_common.TITLE_BLOCK_PLACEHOLDER.match(str(_config.parts(stem).get(key) or ""))
    }
    assert _drawn_parts(), "no part drawings registered"
    assert gaps == {}


def test_every_specified_part_stamps_its_material_specification(monkeypatch):
    """Purchased parts included: their build never called apply_drawing_properties."""
    monkeypatch.setattr(_common, "_git_sha", lambda: "0000000")
    monkeypatch.setattr(_common, "_git_commit_year", lambda: "2026")
    specified = [stem for stem, row in _config.parts().items() if row.get("material_specification")]
    assert set(_drawn_parts()) <= set(specified)
    for stem in specified:
        stamped = _common.part_properties(stem)["Material Specification"]
        assert stamped == str(_config.parts(stem)["material_specification"]), stem


# -- the retarget --------------------------------------------------------------


def test_retarget_rewrites_only_the_token_and_keeps_the_label():
    material = _Note(f"<FONT size=2>MATERIAL\n{MATERIAL_LINK}")
    finish = _Note(f"FINISH\n{FINISH_LINK}")
    rewritten = _drawing_common.retarget_title_block_links(
        _Drawing([material, finish]), {MATERIAL_LINK: SPEC_LINK}, label="sheet 'T006'"
    )
    assert material.PropertyLinkedText == f"<FONT size=2>MATERIAL\n{SPEC_LINK}"
    assert finish.PropertyLinkedText == f"FINISH\n{FINISH_LINK}"
    assert rewritten == [(material, material.PropertyLinkedText)]


@pytest.mark.parametrize("copies", [0, 2])
def test_retarget_needs_the_link_exactly_once(copies):
    notes = [_Note(MATERIAL_LINK) for _ in range(copies)] + [_Note(FINISH_LINK)]
    with pytest.raises(RuntimeError, match="exactly once"):
        _drawing_common.retarget_title_block_links(_Drawing(notes), {MATERIAL_LINK: SPEC_LINK}, label="s")


def test_retarget_fails_when_the_link_does_not_persist():
    with pytest.raises(RuntimeError, match="did not persist"):
        _drawing_common.retarget_title_block_links(
            _Drawing([_Note(MATERIAL_LINK, sticky=False)]), {MATERIAL_LINK: SPEC_LINK}, label="s"
        )


def test_finalize_retargets_and_reads_back_every_sheet():
    source = inspect.getsource(_drawing_common.finalize_drawing)
    assert "retarget_title_block_links(" in source
    assert "_TEMPLATE_MATERIAL_LINK: property_link(TITLE_BLOCK_MATERIAL_PROPERTY)" in source
    assert "assert_title_block_resolves(" in source
    assert "would save on sheet" in source


def test_no_sheet_links_the_short_material():
    """The purchased path used to retarget MATERIAL itself; finalize owns it now."""
    source = inspect.getsource(_purchased_fastener_drawing)
    assert 'property_link("Material")' not in source
    assert '"Material",' not in source


# -- the readback ----------------------------------------------------------------


def test_the_configuration_property_wins_over_the_file_one():
    model = _Model(
        {"Material Specification": "C36000 free-machining brass", "Finish": "AS MACHINED, UNCOATED"},
        {"T006": {"Material Specification": "C67500 manganese bronze"}},
    )
    notes = [
        _Note(f"MATERIAL\n{SPEC_LINK}", "MATERIAL\r\nC67500 manganese bronze"),
        _Note(f"FINISH\n{FINISH_LINK}", "FINISH\r\nAS MACHINED, UNCOATED"),
    ]
    assert _resolve(notes, model, "T006") == {"notes": 2, "drift": 0}


def test_a_cell_that_prints_the_file_value_under_a_config_override_fails():
    model = _Model(
        {"Material Specification": "C36000 free-machining brass", "Finish": "AS MACHINED, UNCOATED"},
        {"T006": {"Material Specification": "C67500 manganese bronze"}},
    )
    notes = [
        _Note(f"MATERIAL\n{SPEC_LINK}", "MATERIAL\nC36000 free-machining brass"),
        _Note(f"FINISH\n{FINISH_LINK}", "FINISH\nAS MACHINED, UNCOATED"),
    ]
    with pytest.raises(RuntimeError, match=r"MHA-013 sheet 'T006' \(config 'T006'\).*Material Specification"):
        _resolve(notes, model, "T006")


def test_a_blank_material_specification_fails_loud():
    model = _Model({"Material": "Brass", "Finish": "AS MACHINED, UNCOATED"})
    notes = [_Note(f"MATERIAL\n{SPEC_LINK}", "MATERIAL\n"), _Note(FINISH_LINK, "AS MACHINED, UNCOATED")]
    with pytest.raises(RuntimeError, match=r"config 'Default'.*\[\"Material Specification=''\"\] is blank"):
        _resolve(notes, model)


@pytest.mark.parametrize("placeholder", ["NONE", "none", "N/A", "NA", "TBD", "-", " -- "])
def test_a_placeholder_finish_fails_like_a_blank(placeholder):
    model = _Model({"Material Specification": "C36000 free-machining brass", "Finish": placeholder})
    notes = [_Note(SPEC_LINK, "C36000 free-machining brass"), _Note(FINISH_LINK, placeholder)]
    with pytest.raises(RuntimeError, match="blank or a placeholder"):
        _resolve(notes, model)


@pytest.mark.parametrize("value", ["NONE REQUIRED; deburr", "Nickel", "as machined, uncoated"])
def test_a_real_value_is_no_placeholder(value):
    assert not _drawing_common.TITLE_BLOCK_PLACEHOLDER.match(value)


def test_a_missing_finish_cell_fails():
    model = _Model({"Material Specification": "C36000 free-machining brass"})
    with pytest.raises(RuntimeError, match="exactly once"):
        _resolve([_Note(SPEC_LINK, "C36000 free-machining brass")], model)


def test_a_drawing_level_finish_resolves_on_the_drawing():
    model = _Model({"Material Specification": "Steel, McMaster-Carr 90280A194"})
    notes = [
        _Note(SPEC_LINK, "Steel, McMaster-Carr 90280A194"),
        _Note('$PRP:"Finish"', "zinc plated"),
    ]
    assert _resolve(notes, model, properties={"Finish": "zinc plated"})["drift"] == 0


def test_other_linked_cells_that_drift_warn_but_do_not_fail(monkeypatch):
    events = []
    monkeypatch.setattr(_drawing_common._telemetry, "event", lambda name, **attrs: events.append((name, attrs)))
    model = _Model({"Material Specification": "C36000", "Finish": "AS MACHINED, UNCOATED", "Title": "Cone Gear"})
    notes = [
        _Note(SPEC_LINK, "C36000"),
        _Note(FINISH_LINK, "AS MACHINED, UNCOATED"),
        _Note('PART\n$PRPSHEET:"Title"', "PART\ncone-gear"),
        _Note('(c) $PRPSHEET:"COPYRIGHT_YEAR" $PRPSHEET:"SW-Author(Author)"', "(c) 2026 Pedro"),
        _Note("DO NOT SCALE DRAWING"),
    ]
    assert _resolve(notes, model) == {"notes": 3, "drift": 1}
    [(name, attrs)] = events
    assert name == "drawing.title_block_drift"
    assert (attrs["expected"], attrs["printed"]) == ("PART Cone Gear", "PART cone-gear")


def test_a_specification_that_wraps_below_its_cell_fails():
    """knife-mount's 70-character O1 wording wraps to a second line (offline
    estimate); the line under the cell's rule is an overflow, not a shrink."""
    model = _Model(
        {
            "Material Specification": "AISI O1 tool steel, hardened and tempered to 58-60 HRC after machining",
            "Finish": "heat treated, unpainted",
        }
    )
    notes = [
        _Note(
            SPEC_LINK,
            "AISI O1 tool steel, hardened and tempered to 58-60 HRC after machining",
            extent=(0.2200, 0.0225, 0.0, 0.3080, 0.0330, 0.0),
        ),
        _Note(FINISH_LINK, "heat treated, unpainted"),
    ]
    with pytest.raises(RuntimeError, match="Material Specification .* overflows its cell"):
        _resolve(notes, model)


def test_both_templates_carry_both_cells_inside_the_title_block():
    from _drawing_registry import DRAWING_TEMPLATES

    for template in DRAWING_TEMPLATES.values():
        material, finish = template.material_cell_m, template.finish_cell_m
        assert material[0] >= template.title_block_left_m and material[3] <= template.title_block_top_m
        assert finish[1] == material[3] and finish[3] <= template.title_block_top_m
        assert material[2] - material[0] == pytest.approx(0.0924)


def test_the_forecast_never_fits_a_word_wider_than_the_cell():
    """Codex P2 on 2136fe470: an unbreakable token wider than the wrap was
    accepted as a first line and read as fitting one line."""
    PIL = pytest.importorskip("PIL.ImageFont")
    from diagnostics import title_block_fit

    if not title_block_fit.FONT.is_file():
        pytest.skip("Century Gothic is not installed")
    font = PIL.truetype(str(title_block_fit.FONT), 100)
    token = "X" * 80
    assert title_block_fit.lines(font, token) == 2
    assert title_block_fit.lines(font, f"steel {token}") == 3
    assert title_block_fit.lines(font, "AISI O1 tool steel") == 1
    assert title_block_fit.lines(font, "AISI O1 tool steel, hardened and tempered to 58-60 HRC after machining") == 2
