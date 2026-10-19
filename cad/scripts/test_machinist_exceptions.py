"""Owner-declared machinist-review exceptions stay bound to the drawing code.

Each ``draw_<name>.exceptions.yaml`` must belong to a registered drawing, parse
under the strict schema, anchor every entry on a symbol the drawing's own code
owns, and match its ids one-to-one with ``# machinist-exception: <id>`` tags
in ``draw_<name>.py``. Only draw scripts may carry tags, and no build or draw
closure may reach the declarations, so declaring or retiring an exception
re-keys nothing but the tagged drawing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import machinist_exceptions as me
from _buildgraph import module_deps_of
from _drawing_registry import DRAWINGS_BY_NAME

SCRIPTS = Path(__file__).resolve().parent
DECLARATIONS = sorted(SCRIPTS.glob(f"draw_*{me.EXCEPTIONS_SUFFIX}"))


def _name(path: Path) -> str:
    return path.name[len("draw_") : -len(me.EXCEPTIONS_SUFFIX)]


def test_declarations_exist() -> None:
    assert DECLARATIONS


@pytest.mark.parametrize("path", DECLARATIONS, ids=lambda path: path.name)
def test_declarations_belong_to_a_registered_drawing(path: Path) -> None:
    name = _name(path)
    assert name in DRAWINGS_BY_NAME, f"{path.name}: no registered drawing {name!r}"
    assert DRAWINGS_BY_NAME[name].script_name == f"draw_{name}.py", path.name
    assert (SCRIPTS / f"draw_{name}.py").is_file(), path.name


@pytest.mark.parametrize("path", DECLARATIONS, ids=lambda path: path.name)
def test_declarations_parse_and_anchors_resolve(path: Path) -> None:
    name = _name(path)
    draw = SCRIPTS / f"draw_{name}.py"
    closure = [Path(module) for module in module_deps_of(draw)]
    failures = []
    for entry in me.load_file(path):
        for anchor in entry.anchors:
            problem = me.resolve_anchor(anchor, draw, closure)
            if problem is None:
                # The review renders every anchor; one that resolves on paper
                # but cannot render would crash the review at run time.
                try:
                    me.render_anchor(anchor, name)
                except (
                    AttributeError,
                    KeyError,
                    TypeError,
                    ValueError,
                    ImportError,
                ) as exc:
                    problem = f"does not render: {exc!r}"
            if problem is not None:
                failures.append(
                    f"{path.name} {entry.id}: unresolvable anchor {anchor}: {problem}"
                )
    assert not failures, "\n".join(failures)


def _tag_failures(draw: Path, declared: set[str], declarations: str) -> list[str]:
    tagged = set(me.tags(draw))
    return [
        *(
            f"{declarations} {id_}: orphaned declared id (no '# {me.TAG} {id_}' in {draw.name})"
            for id_ in sorted(declared - tagged)
        ),
        *(
            f"{draw.name} {id_}: referenced but undeclared id (not in {declarations})"
            for id_ in sorted(tagged - declared)
        ),
    ]


def test_tags_and_declarations_match_one_to_one() -> None:
    failures = []
    for draw in sorted(SCRIPTS.glob("draw_*.py")):
        path = me.exceptions_path(draw.stem[len("draw_") :], SCRIPTS)
        declared = (
            {entry.id for entry in me.load_file(path)} if path.is_file() else set()
        )
        failures += _tag_failures(draw, declared, path.name)
    assert not failures, "\n".join(failures)


def test_only_draw_scripts_carry_tags() -> None:
    # A tag in a spec or build module would put the review link in a build
    # closure: retiring an exception would then re-key parts.
    failures = [
        f"{path.relative_to(SCRIPTS).as_posix()}:{lines[0]} {id_}: tag outside a draw script"
        for path in sorted(SCRIPTS.rglob("*.py"))
        if not path.name.startswith("draw_") or path.parent != SCRIPTS
        for id_, lines in me.tags(path).items()
    ]
    assert not failures, "\n".join(failures)


def test_no_build_or_draw_closure_reaches_the_declarations() -> None:
    reader = str((SCRIPTS / "machinist_exceptions.py").resolve())
    reached = [
        script.name
        for pattern in ("build_*.py", "draw_*.py")
        for script in sorted(SCRIPTS.glob(pattern))
        if reader in module_deps_of(script)
    ]
    assert not reached, reached


# --- the failure modes name the file and the id --------------------------------

_ENTRY = (
    "- id: RV-01\n"
    "  kind: accept\n"
    "  anchor: note:draw_xx_part.NOTE\n"
    "  finding: f\n"
    "  reason: r\n"
)


def _declare(tmp_path: Path, text: str) -> Path:
    path = tmp_path / f"draw_xx_part{me.EXCEPTIONS_SUFFIX}"
    path.write_text(text, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (_ENTRY + _ENTRY, "duplicate id RV-01"),
        (
            _ENTRY.replace("kind: accept", "kind: ignore"),
            r"\(RV-01\): kind must be one of",
        ),
        (_ENTRY.replace("anchor:", "where:"), r"keys must be exactly"),
        (_ENTRY.replace("note:", "notes:"), r"\(RV-01\): anchor 'notes:"),
        (
            _ENTRY.replace("note:draw_xx_part.NOTE", "frame:m.TABLE"),
            r"\(RV-01\): .*\[<key>\]",
        ),
        (
            _ENTRY.replace("note:draw_xx_part.NOTE", "sheet:1/the bore"),
            r"\(RV-01\): a sheet:",
        ),
        (_ENTRY.replace("reason: r", "reason: ''"), r"\(RV-01\): reason"),
    ],
)
def test_malformed_declarations_fail_naming_file_and_id(
    tmp_path: Path, text: str, message: str
) -> None:
    path = _declare(tmp_path, text)
    with pytest.raises(ValueError, match=message) as raised:
        me.load_file(path)
    assert path.name in str(raised.value)


def test_a_missing_file_declares_nothing(tmp_path: Path) -> None:
    assert me.load_exceptions("xx_part", tmp_path) == ()
    path = _declare(tmp_path, _ENTRY)
    (entry,) = me.load_exceptions("xx_part", tmp_path)
    assert (entry.id, entry.kind, str(entry.anchors[0])) == (
        "RV-01",
        me.ExceptionKind.ACCEPT,
        "note:draw_xx_part.NOTE",
    )
    assert path.is_file()


def test_unresolvable_anchors_say_why(tmp_path: Path) -> None:
    draw = tmp_path / "draw_xx_part.py"
    draw.write_text(
        "import xx_steps\n"
        'NOTE = "BORE"\n'
        'TABLE = {"bore position": "0.10"}\n'
        'DRAWING_DIMENSIONS = {"Holes": {"HoleX"}}\n',
        encoding="utf-8",
    )
    steps = tmp_path / "xx_steps.py"
    steps.write_text('SEQUENCE = ("seat", "clamp")\n', encoding="utf-8")
    resolved = {
        text: me.resolve_anchor(me.parse_anchor(text), draw, [steps])
        for text in (
            "note:draw_xx_part.NOTE",
            "frame:draw_xx_part.TABLE[bore position]",
            "step:clamp",
            "dim:HoleX@Holes",
            "note:draw_xx_part.GONE",
            "frame:draw_xx_part.TABLE[slot position]",
            "note:elsewhere.NOTE",
            "step:press",
            "dim:HoleY@Holes",
        )
    }
    assert [text for text, problem in resolved.items() if problem is None] == [
        "note:draw_xx_part.NOTE",
        "frame:draw_xx_part.TABLE[bore position]",
        "step:clamp",
        "dim:HoleX@Holes",
    ]
    assert "no top-level GONE" in resolved["note:draw_xx_part.GONE"]
    assert (
        "no key 'slot position'" in resolved["frame:draw_xx_part.TABLE[slot position]"]
    )
    assert "import closure" in resolved["note:elsewhere.NOTE"]
    assert "'press'" in resolved["step:press"]
    assert "'HoleY'" in resolved["dim:HoleY@Holes"]


def test_tags_pair_both_ways(tmp_path: Path) -> None:
    draw = tmp_path / "draw_xx_part.py"
    draw.write_text(
        "# machinist-exception: RV-01, RV-02 (the two frames)\nX = 1  # machinist-exception: RV-03\n",
        encoding="utf-8",
    )
    assert me.tags(draw) == {"RV-01": [1], "RV-02": [1], "RV-03": [2]}
    failures = _tag_failures(draw, {"RV-01", "RV-02", "RV-04"}, "decl.yaml")
    assert failures == [
        f"decl.yaml RV-04: orphaned declared id (no '# {me.TAG} RV-04' in draw_xx_part.py)",
        "draw_xx_part.py RV-03: referenced but undeclared id (not in decl.yaml)",
    ]
    draw.write_text("# machinist-exception: rv-1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="malformed tag"):
        me.tags(draw)
