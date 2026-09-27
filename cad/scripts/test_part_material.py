"""SolidWorks-free contract for per-configuration part material.

MHA-135 (pinion-lever-pin) applied its material after the INSTALLED split, and
the adapter's apply_material set only the active configuration (Default).
_common.apply_material now sets every configuration by name, and the part-save
chokepoint refuses a part whose configurations disagree or carry none.
"""

from __future__ import annotations

import inspect

import pytest

import _common


class _Part:
    """IModelDoc2 + IPartDoc double holding one material per configuration."""

    def __init__(self, materials: dict[str, str]) -> None:
        self.materials = dict(materials)
        self.log: list[str] = []

    def GetConfigurationNames(self):  # noqa: N802
        return tuple(self.materials)

    def SetMaterialPropertyName2(self, config, database, name):  # noqa: N802
        self.log.append(f"set {config}")
        self.materials[config] = name

    def GetMaterialPropertyName2(self, config):  # noqa: N802
        name = self.materials[config]
        return name, ("SOLIDWORKS Materials" if name else "")

    def EditRebuild3(self) -> bool:  # noqa: N802
        self.log.append("EditRebuild3")
        return True


class _Adapter:
    def __init__(self, part: _Part) -> None:
        self.currentModel = part


@pytest.fixture
def seat(monkeypatch):
    monkeypatch.setattr(_common, "_early_bound", lambda obj, _iface: obj)

    def make(materials):
        part = _Part(materials)
        return _Adapter(part), part

    return make


@pytest.mark.asyncio
async def test_apply_material_sets_every_configuration_by_name(seat) -> None:
    adapter, part = seat({"Default": "", "INSTALLED": ""})
    await _common.apply_material(adapter, "Plain Carbon Steel")
    assert part.materials == {"Default": "Plain Carbon Steel", "INSTALLED": "Plain Carbon Steel"}
    assert part.log == ["set Default", "set INSTALLED", "EditRebuild3"]


@pytest.mark.asyncio
async def test_apply_material_raises_when_a_configuration_reads_back_wrong(
    seat, monkeypatch
) -> None:
    adapter, part = seat({"Default": "", "INSTALLED": ""})
    monkeypatch.setattr(part, "SetMaterialPropertyName2", lambda *_args: None)
    with pytest.raises(RuntimeError, match=r"configurations read \{'Default': '', 'INSTALLED': ''\}"):
        await _common.apply_material(adapter, "Brass")


def test_the_gate_passes_one_material_in_every_configuration(seat) -> None:
    adapter, _part = seat({"Default": "Brass", **{f"T{t:03d}": "Brass" for t in (6, 12)}})
    _common.require_one_material(adapter, "cone-gear")


@pytest.mark.parametrize(
    "materials",
    [
        {"Default": "Plain Carbon Steel", "INSTALLED": ""},
        {"Default": "Plain Carbon Steel", "INSTALLED": "Brass"},
        {"Default": ""},
    ],
)
def test_the_gate_names_the_part_and_every_configuration(seat, materials) -> None:
    adapter, _part = seat(materials)
    with pytest.raises(RuntimeError, match=r"pinion-lever-pin: every configuration"):
        _common.require_one_material(adapter, "pinion-lever-pin")


def test_the_save_chokepoint_gates_material_before_its_final_rebuild_and_save() -> None:
    source = inspect.getsource(_common.save_part_and_images)
    gate = source.index("require_one_material(adapter, part_name)")
    assert source.index("apply_summary_info(") < gate
    assert gate < source.index("rebuild_stale_configurations(adapter, part_name)")


# ---------------------------------------------------------------------------
# Colour: part level set on all configurations at once, body level per
# configuration under activation (IBody2 has no configuration-option setter).

UNSET = (-1.0,) * 9
STEEL = (0.65, 0.64, 0.63)


def _plain(value):
    return tuple(getattr(value, "value", value))


class _Body:
    def __init__(self) -> None:
        self._values = UNSET

    @property
    def MaterialPropertyValues2(self):  # noqa: N802
        return self._values

    @MaterialPropertyValues2.setter
    def MaterialPropertyValues2(self, values):  # noqa: N802
        self._values = _plain(values)


class _ColourExtension:
    def __init__(self, model: _ColourModel) -> None:
        self.model = model

    def SetMaterialPropertyValues(self, values, config_opt, _names):  # noqa: N802
        assert config_opt == _common._SW_ALL_CONFIGURATIONS
        for name in self.model.part_colour:
            self.model.part_colour[name] = _plain(values)

    def GetMaterialPropertyValues(self, config_opt, names):  # noqa: N802
        assert config_opt == _common._SW_SPECIFY_CONFIGURATION
        (name,) = _plain(names)
        return self.model.part_colour[name]


class _Configuration:
    def __init__(self, name: str) -> None:
        self.Name = name


class _Manager:
    def __init__(self, model: _ColourModel) -> None:
        self.model = model

    @property
    def ActiveConfiguration(self):  # noqa: N802
        return _Configuration(self.model.active)


class _ColourModel:
    """IModelDoc2 + IPartDoc double: a part colour and bodies per configuration."""

    def __init__(self, names, active, part_colour=None) -> None:
        self.part_colour = {name: (part_colour or {}).get(name, UNSET) for name in names}
        self.bodies = {name: [_Body(), _Body()] for name in names}
        self.active = active
        self.log: list[str] = []
        self.Extension = _ColourExtension(self)
        self.ConfigurationManager = _Manager(self)

    def GetConfigurationNames(self):  # noqa: N802
        return tuple(self.part_colour)

    def ShowConfiguration2(self, name) -> bool:  # noqa: N802
        self.log.append(f"show {name}")
        self.active = name
        return True

    @property
    def MaterialPropertyValues(self):  # noqa: N802
        return self.part_colour[self.active]

    def GetBodies2(self, _body_type, _visible_only):  # noqa: N802
        return self.bodies[self.active]


@pytest.fixture
def colour_seat(monkeypatch):
    monkeypatch.setattr(_common, "_early_bound", lambda obj, _iface: obj)

    def make(names, active, **kwargs):
        model = _ColourModel(names, active, **kwargs)
        return _Adapter(model), model

    return make


@pytest.mark.asyncio
async def test_apply_color_sets_every_configuration_and_restores_the_active_one(
    colour_seat,
) -> None:
    adapter, model = colour_seat(("Default", "INSTALLED"), active="Default")
    await _common.apply_color(adapter, STEEL)
    assert model.log == ["show INSTALLED", "show Default"]
    assert model.active == "Default"
    for name in ("Default", "INSTALLED"):
        assert model.part_colour[name][:3] == STEEL
        assert all(body.MaterialPropertyValues2[:3] == STEEL for body in model.bodies[name])


@pytest.mark.asyncio
async def test_apply_color_on_a_single_configuration_part_never_switches(colour_seat) -> None:
    adapter, model = colour_seat(("Default",), active="Default")
    await _common.apply_color(adapter, STEEL)
    assert model.log == []


@pytest.mark.asyncio
async def test_apply_color_raises_naming_a_body_that_reads_back_wrong(
    colour_seat,
) -> None:
    class _StuckBody(_Body):
        @property
        def MaterialPropertyValues2(self):  # noqa: N802
            return UNSET

        @MaterialPropertyValues2.setter
        def MaterialPropertyValues2(self, _values):  # noqa: N802
            pass

    adapter, model = colour_seat(("Default", "INSTALLED"), active="Default")
    model.bodies["INSTALLED"][1] = _StuckBody()
    with pytest.raises(RuntimeError, match=r"read back \{'INSTALLED \(body 1\)': '\(-1\.0"):
        await _common.apply_color(adapter, STEEL)
    assert model.active == "Default"


def test_the_colour_gate_passes_one_colour_or_none_everywhere(colour_seat) -> None:
    adapter, _model = colour_seat(("Default", "T006", "T012"), active="Default")
    _common.require_one_colour(adapter, "cone-gear")
    adapter, _model = colour_seat(
        ("Default", "INSTALLED"),
        active="Default",
        part_colour={"Default": (*STEEL, 1, 1, 0.3, 0.31, 0, 0), "INSTALLED": (*STEEL, 1, 1, 0.3, 0.31, 0, 0)},
    )
    _common.require_one_colour(adapter, "pinion-lever-pin")


def test_the_colour_gate_names_a_configuration_left_without_the_colour(colour_seat) -> None:
    adapter, _model = colour_seat(
        ("Default", "INSTALLED"),
        active="Default",
        part_colour={"Default": (*STEEL, 1, 1, 0.3, 0.31, 0, 0)},
    )
    with pytest.raises(RuntimeError, match=r"pinion-lever-pin: every configuration must carry one colour.*INSTALLED"):
        _common.require_one_colour(adapter, "pinion-lever-pin")


def test_the_save_chokepoint_gates_colour_before_its_final_rebuild_and_save() -> None:
    source = inspect.getsource(_common.save_part_and_images)
    gate = source.index("require_one_colour(adapter, part_name)")
    assert source.index("require_one_material(adapter, part_name)") < gate
    assert gate < source.index("rebuild_stale_configurations(adapter, part_name)")


@pytest.mark.asyncio
async def test_a_configuration_created_after_apply_color_fails_the_gate(colour_seat) -> None:
    adapter, model = colour_seat(("Default",), active="Default")
    await _common.apply_color(adapter, STEEL)
    assert adapter.colour_configurations == {"Default"}
    _common.require_one_colour(adapter, "pinion-lever-pin")
    # The split after the colour: part level reads the same (inherited or
    # all-configuration), but INSTALLED's bodies were never written and read.
    model.part_colour["INSTALLED"] = model.part_colour["Default"]
    model.bodies["INSTALLED"] = [_Body()]
    with pytest.raises(
        RuntimeError,
        match=r"pinion-lever-pin: configuration\(s\) \['INSTALLED'\] created after apply_color",
    ):
        _common.require_one_colour(adapter, "pinion-lever-pin")


def test_a_part_that_never_calls_apply_color_skips_the_walked_check(colour_seat) -> None:
    adapter, _model = colour_seat(("Default", "T006"), active="Default")
    assert not hasattr(adapter, "colour_configurations")
    _common.require_one_colour(adapter, "cone-gear")
