"""Owner-declared machinist-review exceptions, kept beside the drawing code.

Known, owner-accepted departures live in ``cad/scripts/draw_<name>.exceptions.yaml``
beside the ``draw_<name>.py`` that prints the excused item (an assembly drawing
keeps its ``_assembly`` suffix: ``draw_fr_frame_assembly.exceptions.yaml``).
The file is a flat list:

    - id: "RV-01"
      kind: "accept"
      anchor: "frame:ch_rocker_arm_spec.GEOMETRIC_TOLERANCES_MM[rod-pin hole position]"
      finding: "position frame over-specified on a channel part (rule 5)"
      reason: "rod-pin coordinates set the connecting-rod lever length ..."

``kind`` is an enum: ``accept`` (do not file the finding at all) or ``minor``
(file it at most under minor, never gating). ``anchor`` is one anchor or a list
of them; each names a symbol the drawing code owns, never quoted sheet text,
so it cannot drift from the sheet:

- ``step:<step-key>`` -- a key of ``SEQUENCE`` in the ``*_steps`` module the
  draw script imports (the assembly fit-up steps); renders the printed step.
- ``note:<module>.<NAME>[<key>]`` -- a top-level text constant (a string, or a
  sequence of printed lines; ``[<key>]`` indexes a dict); renders the text.
- ``frame:<module>.<NAME>[<key>]`` -- one feature-control frame: a tolerance
  table entry (``GEOMETRIC_TOLERANCES_MM[<key>]``) or a ``GeometricControl``
  selected by its ``key`` from a ``GEOMETRIC_CONTROLS`` sequence; renders the
  key and its current tolerance (with characteristic and datums when known).
- ``dim:<Dimension>@<Feature>`` -- a model dimension the draw script imports
  into a view, declared in a ``{feature: {dimension, ...}}`` table it reaches
  (``DRAWING_DIMENSIONS``); renders its name (the value lives in the model).
- ``sheet:<n>/<text>`` -- last resort, when no code symbol owns the item; the
  entry's ``reason`` must say why (it contains ``no code anchor``).

``<module>`` is the draw script or a module in its import closure.

The two-way link: the draw script carries ``# machinist-exception: <id>`` at
the excused site. Only draw scripts carry the tag, so declaring or retiring an
exception re-keys that drawing alone, never a part, assembly or gate.
``test_machinist_exceptions`` (check:recipe) resolves every anchor and matches
every declared id to a tag and every tag to a declaration.

Nothing but ``machinist_review`` and that test imports this module, and no
build or draw closure reaches it or the YAML files. The review prompt receives
every declared exception for its package, each anchor rendered to the current
code value; a would-be finding that matches one is not a finding.
"""

from __future__ import annotations

import ast
import enum
import importlib
import io
import re
import tokenize
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml

SCRIPTS_DIR = Path(__file__).resolve().parent
EXCEPTIONS_SUFFIX = ".exceptions.yaml"
ENTRY_KEYS = ("id", "kind", "anchor", "finding", "reason")
SHEET_JUSTIFICATION = "no code anchor"
ID_PATTERN = r"[A-Z]+-\d+"
_ID = re.compile(rf"{ID_PATTERN}")
TAG = "machinist-exception:"
_TAG = re.compile(rf"#\s*{re.escape(TAG)}\s*(?P<ids>.*)$")
_TAG_IDS = re.compile(rf"(?P<ids>{ID_PATTERN}(?:\s*,\s*{ID_PATTERN})*)(?:\s|$)")
_SYMBOL = re.compile(
    r"(?P<module>[A-Za-z_][A-Za-z0-9_]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?:\[(?P<key>[^\[\]]+)\])?"
)
_DIM = re.compile(
    r"(?P<dimension>[A-Za-z_][A-Za-z0-9_]*)@(?P<feature>[A-Za-z_][A-Za-z0-9_]*)"
)
_SHEET = re.compile(r"(?P<sheet>[1-9][0-9]*)/(?P<text>\S.*)")


class ExceptionKind(enum.Enum):
    ACCEPT = "accept"
    MINOR = "minor"


class AnchorKind(enum.Enum):
    STEP = "step"
    NOTE = "note"
    FRAME = "frame"
    DIM = "dim"
    SHEET = "sheet"


@dataclass(frozen=True)
class Anchor:
    kind: AnchorKind
    text: str
    module: str = ""
    name: str = ""
    key: str = ""

    def __str__(self) -> str:
        return f"{self.kind.value}:{self.text}"


@dataclass(frozen=True)
class MachinistException:
    id: str
    kind: ExceptionKind
    anchors: tuple[Anchor, ...]
    finding: str
    reason: str


def parse_anchor(value: str) -> Anchor:
    """One anchor string; ValueError on a malformed one."""
    prefix, sep, body = value.partition(":")
    try:
        kind = AnchorKind(prefix)
    except ValueError:
        raise ValueError(
            f"anchor {value!r}: kind must be one of {[k.value for k in AnchorKind]}"
        ) from None
    if not sep or not body.strip() or body != body.strip():
        raise ValueError(f"anchor {value!r}: empty or padded target")
    if kind is AnchorKind.STEP:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", body):
            raise ValueError(f"anchor {value!r}: a step key is lower-case-dashed")
        return Anchor(kind, body, key=body)
    if kind is AnchorKind.DIM:
        if not _DIM.fullmatch(body):
            raise ValueError(f"anchor {value!r}: expected dim:<Dimension>@<Feature>")
        return Anchor(kind, body)
    if kind is AnchorKind.SHEET:
        if not _SHEET.fullmatch(body):
            raise ValueError(f"anchor {value!r}: expected sheet:<n>/<text>")
        return Anchor(kind, body)
    match = _SYMBOL.fullmatch(body)
    if match is None:
        raise ValueError(f"anchor {value!r}: expected {prefix}:<module>.<NAME>[<key>]")
    if kind is AnchorKind.FRAME and match["key"] is None:
        raise ValueError(f"anchor {value!r}: a frame anchor names its [<key>]")
    return Anchor(kind, body, match["module"], match["name"], match["key"] or "")


def exceptions_path(name: str, directory: Path = SCRIPTS_DIR) -> Path:
    """The declarations file beside ``draw_<name>.py``."""
    return directory / f"draw_{name}{EXCEPTIONS_SUFFIX}"


def _text(value: object, where: str, key: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{where}: {key} must be a non-empty string")
    return value.strip()


def _entry(value: object, where: str) -> MachinistException:
    if not isinstance(value, dict):
        raise ValueError(f"{where}: must be a mapping")
    if set(value) != set(ENTRY_KEYS):
        raise ValueError(
            f"{where}: keys must be exactly {sorted(ENTRY_KEYS)}, got {sorted(value)}"
        )
    id_ = _text(value["id"], where, "id")
    if not _ID.fullmatch(id_):
        raise ValueError(f"{where}: id {id_!r} must match {ID_PATTERN}")
    where = f"{where} ({id_})"
    try:
        kind = ExceptionKind(value["kind"])
    except ValueError:
        raise ValueError(
            f"{where}: kind must be one of {[k.value for k in ExceptionKind]}, "
            f"got {value['kind']!r}"
        ) from None
    raw = value["anchor"]
    raw_anchors = [raw] if isinstance(raw, str) else raw
    if not isinstance(raw_anchors, list) or not raw_anchors:
        raise ValueError(f"{where}: anchor must be a string or a non-empty list")
    try:
        anchors = tuple(parse_anchor(_text(a, where, "anchor")) for a in raw_anchors)
    except ValueError as exc:
        raise ValueError(f"{where}: {exc}") from None
    if len(set(anchors)) != len(anchors):
        raise ValueError(f"{where}: anchor lists a target twice")
    reason = _text(value["reason"], where, "reason")
    if (
        any(a.kind is AnchorKind.SHEET for a in anchors)
        and SHEET_JUSTIFICATION not in reason
    ):
        raise ValueError(
            f"{where}: a sheet: anchor is a last resort; the reason must say "
            f"why ({SHEET_JUSTIFICATION!r})"
        )
    return MachinistException(
        id_, kind, anchors, _text(value["finding"], where, "finding"), reason
    )


def load_file(path: Path) -> tuple[MachinistException, ...]:
    """Parse and validate one declarations file (it must exist)."""
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(doc, list) or not doc:
        raise ValueError(f"{path}: must be a non-empty list of exceptions")
    entries = tuple(
        _entry(value, f"{path}[{index}]") for index, value in enumerate(doc)
    )
    ids = [entry.id for entry in entries]
    duplicates = sorted({id_ for id_ in ids if ids.count(id_) > 1})
    if duplicates:
        raise ValueError(f"{path}: duplicate id {', '.join(duplicates)}")
    return entries


def load_exceptions(
    name: str, directory: Path = SCRIPTS_DIR
) -> tuple[MachinistException, ...]:
    """The package's declared exceptions; () when the package declares none.

    A missing file is not an error: most packages declare nothing. A malformed
    declaration is an error -- a typo must never silently widen or narrow what
    the reviewer ignores.
    """
    path = exceptions_path(name, directory)
    if not path.is_file():
        return ()
    return load_file(path)


# --- the two-way link: tags in the draw script ---------------------------------


def tags(path: Path) -> dict[str, list[int]]:
    """``# machinist-exception: <id>[, <id>]`` comment tags: id -> line numbers.

    A comment that starts the tag but carries no well-formed id is an error.
    """
    found: dict[str, list[int]] = {}
    source = path.read_text(encoding="utf-8")
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type != tokenize.COMMENT:
            continue
        tag = _TAG.search(token.string)
        if tag is None:
            continue
        ids = _TAG_IDS.match(tag["ids"])
        if ids is None:
            raise ValueError(
                f"{path}:{token.start[0]}: malformed tag {token.string!r}; "
                f"expected '# {TAG} RV-01[, RV-02]'"
            )
        for id_ in re.split(r"\s*,\s*", ids["ids"]):
            found.setdefault(id_, []).append(token.start[0])
    return found


# --- static resolution (AST only: no import, no COM) ----------------------------


def _module_tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _assignments(tree: ast.Module) -> dict[str, ast.expr]:
    """Top-level ``NAME = value`` / ``NAME: T = value``; the last one wins."""
    values: dict[str, ast.expr] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    values[target.id] = node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            if isinstance(node.target, ast.Name):
                values[node.target.id] = node.value
    return values


def _string(node: ast.expr | None, names: Mapping[str, ast.expr]) -> str | None:
    """A literal string, or a module constant naming one."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name) and isinstance(names.get(node.id), ast.Constant):
        return _string(names[node.id], {})
    return None


def _static_keys(node: ast.expr, names: Mapping[str, ast.expr]) -> set[str] | None:
    """The keys a literal table offers, or None when only an import can tell.

    A dict literal offers its string keys; a tuple/list of calls (the
    ``GEOMETRIC_CONTROLS`` shape) offers each call's first argument or
    ``key=``. Any computed element makes the answer unknown.
    """
    if isinstance(node, ast.Dict):
        keys = {_string(key, names) for key in node.keys}
        return None if None in keys else keys  # type: ignore[return-value]
    if isinstance(node, (ast.Tuple, ast.List)):
        keys = set()
        for element in node.elts:
            if not isinstance(element, ast.Call):
                return None
            key = next((kw.value for kw in element.keywords if kw.arg == "key"), None)
            key = key or (element.args[0] if element.args else None)
            text = _string(key, names)
            if text is None:
                return None
            keys.add(text)
        return keys
    return None


def _resolve_symbol(anchor: Anchor, modules: Mapping[str, Path]) -> str | None:
    path = modules.get(anchor.module)
    if path is None:
        return f"module {anchor.module!r} is neither the draw script nor in its import closure"
    names = _assignments(_module_tree(path))
    value = names.get(anchor.name)
    if value is None:
        return f"{path.name} assigns no top-level {anchor.name}"
    if not anchor.key:
        return None
    keys = _static_keys(value, names)
    if keys is not None and anchor.key not in keys:
        return f"{path.name}:{value.lineno} {anchor.name} has no key {anchor.key!r}"
    return None


def _steps_modules(draw_script: Path, modules: Mapping[str, Path]) -> list[Path]:
    imported = set()
    for node in ast.walk(_module_tree(draw_script)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            imported.add(node.module)
    return [
        modules[name]
        for name in sorted(imported)
        if name.endswith("_steps") and name in modules
    ]


def _resolve_step(
    anchor: Anchor, draw_script: Path, modules: Mapping[str, Path]
) -> str | None:
    steps = _steps_modules(draw_script, modules)
    if not steps:
        return f"{draw_script.name} imports no *_steps module"
    for path in steps:
        names = _assignments(_module_tree(path))
        sequence = names.get("SEQUENCE")
        if isinstance(sequence, (ast.Tuple, ast.List)):
            if anchor.key in {_string(element, names) for element in sequence.elts}:
                return None
    return f"no SEQUENCE in {[p.name for p in steps]} lists step {anchor.key!r}"


def _resolve_dim(anchor: Anchor, modules: Mapping[str, Path]) -> str | None:
    dimension, _, feature = anchor.text.partition("@")
    for path in modules.values():
        names = _assignments(_module_tree(path))
        for value in names.values():
            if not isinstance(value, ast.Dict):
                continue
            for key, members in zip(value.keys, value.values, strict=True):
                if _string(key, names) != feature:
                    continue
                if isinstance(
                    members, (ast.Set, ast.Tuple, ast.List)
                ) and dimension in {_string(member, names) for member in members.elts}:
                    return None
    return f"no {{{feature!r}: {{{dimension!r}, ...}}}} dimension table in the draw closure"


def resolve_anchor(
    anchor: Anchor, draw_script: Path, closure: Sequence[Path]
) -> str | None:
    """None when ``anchor`` resolves statically; otherwise why it does not.

    ``closure`` is the draw script's local import closure
    (``_buildgraph.module_deps_of``); anchors may name only those modules.
    """
    modules = {path.stem: path for path in (draw_script, *closure)}
    if anchor.kind is AnchorKind.SHEET:
        return None
    if anchor.kind is AnchorKind.STEP:
        return _resolve_step(anchor, draw_script, modules)
    if anchor.kind is AnchorKind.DIM:
        return _resolve_dim(anchor, modules)
    return _resolve_symbol(anchor, modules)


# --- rendering for the review prompt (imports the drawing's own modules) -------


def _lookup(anchor: Anchor) -> object:
    value = getattr(importlib.import_module(anchor.module), anchor.name)
    if not anchor.key:
        return value
    if isinstance(value, Mapping):
        return value[anchor.key]
    matches = [item for item in value if getattr(item, "key", None) == anchor.key]
    if len(matches) != 1:
        raise KeyError(f"{anchor}: {len(matches)} entries carry key {anchor.key!r}")
    return matches[0]


def _printed(value: object, anchor: Anchor) -> str:
    if isinstance(value, str):
        lines = value.splitlines()
    elif isinstance(value, Sequence) and all(isinstance(line, str) for line in value):
        lines = list(value)
    else:
        raise TypeError(f"{anchor}: {type(value).__name__} is not printed text")
    return " / ".join(line.strip() for line in lines if line.strip())


def _step_text(anchor: Anchor, name: str) -> str:
    draw = importlib.import_module(f"draw_{name}")
    sequences = [
        module.SEQUENCE
        for module in vars(draw).values()
        if getattr(module, "__name__", "").endswith("_steps")
        and anchor.key in getattr(module, "SEQUENCE", ())
    ]
    if len(sequences) != 1:
        raise KeyError(f"{anchor}: {len(sequences)} imported step sequences list it")
    number = sequences[0].index(anchor.key) + 1
    head = f"{number}. "
    paragraphs = set()
    for value in vars(draw).values():
        blocks = (
            [value]
            if isinstance(value, str)
            else value
            if isinstance(value, tuple)
            else ()
        )
        for block in blocks:
            if not isinstance(block, str):
                continue
            lines = block.splitlines()
            for index, line in enumerate(lines):
                if not line.startswith(head):
                    continue
                body = [line]
                for follow in lines[index + 1 :]:
                    if not follow.startswith(" "):
                        break
                    body.append(follow)
                paragraphs.add(" ".join(part.strip() for part in body))
    if len(paragraphs) != 1:
        raise KeyError(
            f"{anchor}: draw_{name} prints {len(paragraphs)} texts for step {number}"
        )
    return f"fit-up step {paragraphs.pop()}"


def render_anchor(anchor: Anchor, name: str) -> str:
    """The anchor's CURRENT printed text or value, for the review prompt."""
    if anchor.kind is AnchorKind.SHEET:
        sheet, _, text = anchor.text.partition("/")
        return f"sheet {sheet}: {text}"
    if anchor.kind is AnchorKind.DIM:
        dimension, _, feature = anchor.text.partition("@")
        return f"model dimension {dimension} ({feature})"
    if anchor.kind is AnchorKind.STEP:
        return _step_text(anchor, name)
    value = _lookup(anchor)
    if anchor.kind is AnchorKind.NOTE:
        return f'note "{_printed(value, anchor)}"'
    characteristic = getattr(value, "characteristic", None)
    if characteristic is None:
        return f'frame "{anchor.key}" {value}'
    datums = "|".join(getattr(value, "datums", ()))
    zone = "dia " if getattr(value, "tolerance_zone", "") == "diametral" else ""
    return f'frame "{anchor.key}": {characteristic} {zone}{value.tolerance}' + (
        f" to {datums}" if datums else ""
    )


def render_exception(exception: MachinistException, name: str) -> str:
    """One prompt line: id, kind, the rendered anchors, finding and reason."""
    where = "; ".join(render_anchor(anchor, name) for anchor in exception.anchors)
    return (
        f"- {exception.id} [{exception.kind.value}] at {where}: "
        f"{exception.finding} — {exception.reason}"
    )
