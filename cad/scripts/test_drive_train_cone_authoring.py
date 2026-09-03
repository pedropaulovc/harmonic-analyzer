from __future__ import annotations

import ast
import asyncio
import inspect
from types import SimpleNamespace

import _assembly as assembly
import build_cone_gear as cone
import build_drive_train_assembly as drive


_SOURCE = inspect.getsource(drive)
_TREE = ast.parse(_SOURCE)
_CONE_TREE = ast.parse(inspect.getsource(cone))


def _function(name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    return next(
        node
        for node in _TREE.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    )


def _calls(node: ast.AST, name: str) -> bool:
    return any(
        isinstance(item, ast.Call)
        and (
            (isinstance(item.func, ast.Name) and item.func.id == name)
            or (isinstance(item.func, ast.Attribute) and item.func.attr == name)
        )
        for item in ast.walk(node)
    )


def _named_call(node: ast.AST, name: str) -> ast.Call:
    return next(
        item
        for item in ast.walk(node)
        if isinstance(item, ast.Call)
        and (
            (isinstance(item.func, ast.Name) and item.func.id == name)
            or (isinstance(item.func, ast.Attribute) and item.func.attr == name)
        )
    )


def _expression(source: str) -> ast.expr:
    return ast.parse(source, mode="eval").body


def test_every_cone_configuration_persists_rebuilt_data() -> None:
    build = next(
        node
        for node in _CONE_TREE.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "build"
    )
    persistence_sweeps = [
        node
        for node in build.body
        if isinstance(node, ast.For)
        and any(
            isinstance(item, ast.Assign)
            and any(
                isinstance(target, ast.Attribute)
                and target.attr == "AddRebuildSaveMark"
                for target in item.targets
            )
            for item in ast.walk(node)
        )
    ]
    assert len(persistence_sweeps) == 1
    sweep = persistence_sweeps[0]
    assert ast.dump(sweep.iter) == ast.dump(_expression("reversed(CONFIGS)"))
    assert _calls(sweep, "ShowConfiguration2")
    assert _calls(sweep, "ForceRebuild3")

    finalized = next(
        index
        for index, node in enumerate(build.body)
        if _calls(node, "save_part_and_images")
    )
    close = next(
        index
        for index, node in enumerate(build.body)
        if _calls(node, "CloseAllDocuments")
    )
    reopen = next(
        index for index, node in enumerate(build.body) if _calls(node, "open_model")
    )
    persistence = build.body.index(sweep)
    final_save = next(
        index for index, node in enumerate(build.body) if _calls(node, "Save3")
    )
    assert finalized < close < reopen < persistence < final_save


def test_all_twenty_cones_are_inserted_directly_in_configuration() -> None:
    build = _function("build")
    cone_list = next(
        node
        for node in ast.walk(build)
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "cone_gears"
    )
    assert isinstance(cone_list.value, ast.List) and not cone_list.value.elts

    author_loop = next(
        node
        for node in build.body
        if isinstance(node, ast.For) and _calls(node, "_place_on_shaft")
    )
    assert ast.dump(author_loop.iter) == ast.dump(_expression("range(20)"))

    placement = _named_call(author_loop, "_place_on_shaft")
    assert ast.dump(placement.args[2]) == ast.dump(
        _expression("SHAFT_T120_STATION + j * SEAT_PITCH + GEAR_AXIS_SHIFT")
    )
    configuration = next(
        keyword.value
        for keyword in placement.keywords
        if keyword.arg == "configuration"
    )
    assert ast.dump(configuration) == ast.dump(_expression("f'T{teeth:03d}'"))

    append = _named_call(author_loop, "append")
    assert isinstance(append.func, ast.Attribute)
    assert isinstance(append.func.value, ast.Name)
    assert append.func.value.id == "cone_gears"
    assert ast.dump(append.args[0]) == ast.dump(_expression("(teeth, cg)"))


def test_cones_never_use_copy_with_mates_or_configuration_switching() -> None:
    build = _function("build")
    assert not any(
        isinstance(node, ast.Attribute) and node.attr == "ReferencedConfiguration"
        for node in ast.walk(build)
    )
    assert not any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "_force_rebuild_after_cone_replication"
        for node in _TREE.body
    )

    copy_calls = [
        node
        for node in ast.walk(build)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "copy_with_mates"
    ]
    assert copy_calls, "the unchanged cylinder replication contract disappeared"
    assert all(
        len(call.args) > 1
        and ast.dump(call.args[1]) == ast.dump(_expression("[seed_cyl]"))
        for call in copy_calls
    )


def test_every_authored_cone_is_keyed_before_downstream_gear_coupling() -> None:
    build = _function("build")
    author_index = next(
        index
        for index, statement in enumerate(build.body)
        if isinstance(statement, ast.For) and _calls(statement, "_place_on_shaft")
    )
    key_index = next(
        index
        for index, statement in enumerate(build.body)
        if isinstance(statement, ast.For)
        and isinstance(statement.iter, ast.Name)
        and statement.iter.id == "cone_gears"
        and _calls(statement, "_key_to_shaft")
    )
    coupling_index = next(
        index
        for index, statement in enumerate(build.body)
        if index > key_index and _calls(statement, "gear_mate")
    )
    assert author_index < key_index < coupling_index

    key_loop = build.body[key_index]
    assert isinstance(key_loop, ast.For)
    assert isinstance(key_loop.target, ast.Tuple)
    assert [item.id for item in key_loop.target.elts if isinstance(item, ast.Name)] == [
        "teeth",
        "cg",
    ]
    key_call = _named_call(key_loop, "_key_to_shaft")
    assert isinstance(key_call.args[1], ast.Name) and key_call.args[1].id == "cg"

    key_helper = _function("_key_to_shaft")
    authored_mates = [
        name
        for statement in key_helper.body
        for name in ("coincident_mate", "distance_driver", "parallel_mate")
        if _calls(statement, name)
    ]
    assert authored_mates == [
        "coincident_mate",
        "distance_driver",
        "parallel_mate",
    ]


def test_cone_key_bank_is_force_rebuilt_before_cylinder_mesh_batch() -> None:
    build = _function("build")
    key_index = next(
        index
        for index, statement in enumerate(build.body)
        if isinstance(statement, ast.For)
        and isinstance(statement.iter, ast.Name)
        and statement.iter.id == "cone_gears"
        and _calls(statement, "_key_to_shaft")
    )

    rebuild_index = next(
        index
        for index, statement in enumerate(build.body)
        if index > key_index
        and isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Await)
        and isinstance(statement.value.value, ast.Call)
        and isinstance(statement.value.value.func, ast.Name)
        and statement.value.value.func.id == "force_rebuild"
    )
    crank_mesh_index = next(
        index
        for index, statement in enumerate(build.body)
        if index > rebuild_index
        and isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Await)
        and isinstance(statement.value.value, ast.Call)
        and isinstance(statement.value.value.func, ast.Name)
        and statement.value.value.func.id == "gear_mate"
    )
    cylinder_batch_index = next(
        index
        for index, statement in enumerate(build.body)
        if index > crank_mesh_index
        and isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Call)
        and isinstance(statement.value.func, ast.Name)
        and statement.value.func.id == "gear_mates_batch"
    )

    assert key_index < rebuild_index < crank_mesh_index < cylinder_batch_index
    batch = build.body[cylinder_batch_index]
    assert isinstance(batch, ast.Expr) and isinstance(batch.value, ast.Call)
    label = next(
        keyword.value for keyword in batch.value.keywords if keyword.arg == "label"
    )
    assert isinstance(label, ast.Constant) and label.value == "cylinder.mesh_bank"


def test_configured_insert_uses_activated_source_configuration(
    monkeypatch, tmp_path
) -> None:
    """The named insert must use an activated, loaded source configuration."""
    part_path = tmp_path / "cone-gear.SLDPRT"
    part_path.write_bytes(b"")
    active = SimpleNamespace(Name="T120")
    events: list[tuple] = []

    class SourcePart:
        ConfigurationManager = SimpleNamespace(ActiveConfiguration=active)

        def ShowConfiguration2(self, name):  # noqa: N802
            events.append(("activate", name))
            active.Name = name
            return -1  # COM VARIANT_BOOL true

    source = SourcePart()

    class Application:
        def DocumentVisible(self, visible, doc_type):  # noqa: N802
            events.append(("visible", visible, doc_type))

        def OpenDoc6(  # noqa: N802
            self, path, doc_type, options, configuration, errors, warnings
        ):
            events.append(
                ("open", path, doc_type, options, configuration, errors, warnings)
            )
            return source

        def GetOpenDocumentByName(self, path):  # noqa: N802
            return source

    class Adapter:
        currentModel = object()
        swApp = Application()

        @staticmethod
        def _attempt(operation, default=None):
            try:
                return operation()
            except Exception:
                return default

        async def insert_component(self, params):
            events.append(("insert", params.configuration, active.Name))
            return SimpleNamespace(
                is_success=True,
                error=None,
                data={
                    "name": "cone-gear-2",
                    "configuration": active.Name,
                    "fixed": False,
                },
            )

    monkeypatch.setattr(assembly, "OUT_SLDPRT", tmp_path)
    monkeypatch.setattr(assembly, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(assembly, "assert_component_placed", lambda *_args: None)
    monkeypatch.setattr(assembly, "_ledger_record", lambda *_args: None)

    name = asyncio.run(
        assembly.place_component(
            Adapter(),
            "cone-gear",
            [0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0],
            [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            ground=False,
            configuration="T114",
        )
    )

    assert name == "cone-gear-2"
    assert ("activate", "T114") in events
    assert ("insert", "T114", "T114") in events


def test_configured_insert_accepts_configuration_activated_by_open(
    monkeypatch, tmp_path
) -> None:
    """OpenDoc6 can satisfy the requested configuration without a second switch."""
    part_path = tmp_path / "cone-gear.SLDPRT"
    part_path.write_bytes(b"")
    active = SimpleNamespace(Name="T120")
    events: list[tuple] = []

    class SourcePart:
        ConfigurationManager = SimpleNamespace(ActiveConfiguration=active)

        def ShowConfiguration2(self, name):  # noqa: N802
            events.append(("activate", name))
            return False

    source = SourcePart()

    class Application:
        @staticmethod
        def DocumentVisible(_visible, _doc_type):  # noqa: N802
            return None

        @staticmethod
        def OpenDoc6(  # noqa: N802
            _path, _doc_type, _options, _configuration, _errors, _warnings
        ):
            return source

        @staticmethod
        def GetOpenDocumentByName(_path):  # noqa: N802
            return source

    class Adapter:
        currentModel = object()
        swApp = Application()

        @staticmethod
        def _attempt(operation, default=None):
            try:
                return operation()
            except Exception:
                return default

        async def insert_component(self, params):
            events.append(("insert", params.configuration, active.Name))
            return SimpleNamespace(
                is_success=True,
                error=None,
                data={
                    "name": "cone-gear-1",
                    "configuration": active.Name,
                    "fixed": False,
                },
            )

    monkeypatch.setattr(assembly, "OUT_SLDPRT", tmp_path)
    monkeypatch.setattr(assembly, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(assembly, "assert_component_placed", lambda *_args: None)
    monkeypatch.setattr(assembly, "_ledger_record", lambda *_args: None)

    name = asyncio.run(
        assembly.place_component(
            Adapter(),
            "cone-gear",
            [0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0],
            [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            ground=False,
            configuration="T120",
        )
    )

    assert name == "cone-gear-1"
    assert not any(event[0] == "activate" for event in events)
    assert ("insert", "T120", "T120") in events
