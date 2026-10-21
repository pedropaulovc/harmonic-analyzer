"""E04D diagnostic-only dirty Edit versus original Force+Edit for the oblique jig.

Pinned source: 862ec3315ce0449e85021b719b70ff0283be1698.
Pinned generated SDK: 1ec68e3d12e0518e9bb152eff3d91b4bebd2b229.
This recognizes a closed subset; unavailable/unknown content is inconclusive,
not permission to repair, activate configurations, evaluate equations or retry.
All returned evidence is plain data. No native handles belong in the report.
The real verifier owns both B-then-A trajectories and all original gates. This
module adds bounded eligibility/evidence only, never a production cutover.

Binding audit (sldworks_2026.py at the pinned SDK; G/P = get/put map):
  IAssemblyDoc.GetComponents: method, G-/P-, VT_VARIANT (12), bool input.
  IComponent2.FirstFeature/GetModelDoc2: methods, G-/P-, VT_DISPATCH (9).
  IComponent2.GetChildren: method, G-/P-, VT_VARIANT (12), null for parts.
  IComponent2.GetBodies3: method, G-/P-, VT_VARIANT (12) + out VARIANT;
    production decoding is (bodies, info); -1 selects all solids and sheets.
  IComponent2.GetPathName: method, G-/P-, VT_BSTR (8).
  IComponent2.GetSuppression2/ListExternalFileReferencesCount: methods,
    G-/P-, VT_I4 (3); resolved states are 2/3, mismatch error is 5.
  IComponent2.ListExternalFileReferences2: method, G-/P-, VT_VOID (24),
    seven out VARIANT arrays + out I4/BSTR, therefore nine fields, no bool.
  IComponent2.Name2/ReferencedConfiguration: properties, G+/P+, VT_BSTR (8).
  IBody2.GetType: method, G-/P-, VT_I4 (3).
  IBody2.Name: property, G+/P+, VT_BSTR (8), positive-control map member.
  IBody2.Check3: property, G+/P-, VT_DISPATCH (9), not callable.
  IFaultEntity.Count: property, G+/P-, VT_I4 (3).
  IModelDoc2.FirstFeature/GetEquationMgr/Parameter: methods, G-/P-,
    VT_DISPATCH (9); Parameter takes one local BSTR dimension name.
  IModelDoc2.GetType: method, G-/P-, VT_I4 (3).
  IModelDoc2.GetPathName: method, G-/P-, VT_BSTR (8).
  IModelDoc2.ConfigurationManager: property, G+/P-, VT_DISPATCH (9).
  IConfigurationManager.ActiveConfiguration: property, G+/P-, VT_DISPATCH (9).
  IConfiguration.Name: property, G+/P+, VT_BSTR (8).
  IFeature.GetFirstSubFeature/GetNextFeature/GetNextSubFeature/
    GetSpecificFeature2: methods, G-/P-, VT_DISPATCH (9).
  IFeature.GetID: method, G-/P-, VT_I4 (3), document-scoped identity.
  IFeature.GetTypeName2: method, G-/P-, VT_BSTR (8).
  IFeature.Name: property, G+/P+, VT_BSTR (8).
  IEquationMgr.GetCount: method, G-/P-, VT_I4 (3).
  IEquationMgr.Equation/GlobalVariable: indexed properties emitted as
    methods, G-/P-, VT_BSTR (8)/VT_BOOL (11), DISPATCH_PROPERTYGET.
  IEquationMgr.LinkToFile: property, G+/P+, VT_BOOL (11).
  IDimension.Name: property, G+/P+, VT_BSTR (8).
  IDimension.GetFeatureOwner: method, G-/P-, VT_DISPATCH (9).

  IDimension.FullName: property, G+/P-, VT_BSTR (8), leaf@feature@model.

Every property above is read without invocation; every method is invoked.
The IDimension identity channel is its exact Name/FullName and the resolved
model filename, plus GetFeatureOwner's Name/GetID/GetTypeName2 against this
part's scoped complete inventory. These extra APIs are documented individually
in IDimension.Name/FullName/GetFeatureOwner and IFeature.GetID. GetTitle is not
used: its extension depends on File Explorer settings; no alternate identity
spelling is tried if the supported FullName representation is unavailable.
Official per-member docs are in developing-solidworks v3.12.1; native tuple
availability is qualified here, not claimed from this static binding audit.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
import traceback
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

import _assembly
import _session
import _telemetry
import ch_rocker_arm_tl_oblique_jig_assembly_spec as jig_spec
from _com import _early_bound
from _paths import CAD_ROOT, OUT_SLDASM, OUT_SLDPRT


class Inconclusive(RuntimeError):
    """The restricted diagnostic could not establish an admission conjunct."""


def _require(condition: bool, message: str) -> None:
    if condition is not True:
        raise Inconclusive(message)


# Exactly the approved E04D vocabulary; administrative means traverse, not skip.
CHILD_SOLID_TYPES = frozenset(
    {
        "Boss",
        "BossThin",
        "Extrusion",
        "Cut",
        "CutThin",
        "Revolution",
        "RevolutionThin",
        "RevCut",
        "Fillet",
        "Chamfer",
        "HoleWzd",
        "CirPattern",
        "LPattern",
        "MirrorPattern",
        "MirrorSolid",
        "Sweep",
        "SweepCut",
        "Helix",
        "Imported",
        "CosmeticThread",
    }
)
CHILD_REFERENCE_TYPES = frozenset(
    {
        "OriginProfileFeature",
        "RefPlane",
        "RefAxis",
        "ProfileFeature",
        "3DProfileFeature",
    }
)
ADMIN_TYPES = frozenset(
    {
        "CommentsFolder",
        "FavoriteFolder",
        "HistoryFolder",
        "SelectionSetFolder",
        "SensorFolder",
        "DocsFolder",
        "DetailCabinet",
        "SurfaceBodyFolder",
        "SolidBodyFolder",
        "EnvFolder",
        "InkMarkupFolder",
        "EqnFolder",
        "FtrFolder",
        "ProfileFtrFolder",
        "RefPlaneFtrFolder",
        "RefAxisFtrFolder",
    }
)
ROOT_MATE_TYPES = frozenset({"MateCoincident", "MateDistanceDim", "MateLock"})
ROOT_PRESENTATION_TYPES = frozenset({"AsmExploder", "CompExplodeStep"})
ROOT_TYPES = (
    ADMIN_TYPES
    | ROOT_MATE_TYPES
    | ROOT_PRESENTATION_TYPES
    | frozenset(
        {
            "Reference",
            "MateGroup",
            "OriginProfileFeature",
            "RefPlane",
            "ProfileFeature",
        }
    )
)
FEATURE_OCCURRENCE_CAP = 5000
FEATURE_DEPTH_CAP = 32
_NAME_SEGMENT = re.compile(r"[A-Za-z0-9_ -]+\Z", re.ASCII)
_NUMBER = re.compile(r"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", re.ASCII)
_EXTERNAL_ARRAY_NAMES = (
    "ModelPathName",
    "ComponentPathName",
    "Feature",
    "DataType",
    "Status",
    "RefEntity",
    "FeatCom",
)


def _bound(value: Any, interface: str) -> Any:
    _require(value is not None, f"{interface}: native receiver is unavailable")
    return _early_bound(value, interface)


def _text(value: Any, label: str, *, empty: bool = False) -> str:
    _require(type(value) is str, f"{label}: expected literal BSTR")
    _require(empty or bool(value.strip()), f"{label}: empty native name")
    return value


def _integer(value: Any, label: str) -> int:
    _require(type(value) is int, f"{label}: expected literal native integer")
    return value


def _resolved_path(value: str, label: str) -> Path:
    path = Path(_text(value, label))
    _require(path.is_absolute(), f"{label}: native path is not absolute")
    path = path.resolve(strict=True)
    _require(path.is_file(), f"{label}: resolved path is not a file")
    return path


def _active_configuration(model: Any, budget: Any) -> str:
    budget.check("admission.active_configuration")
    manager = _bound(model.ConfigurationManager, "IConfigurationManager")
    configuration = _bound(manager.ActiveConfiguration, "IConfiguration")
    return _text(configuration.Name, "active configuration")


def _component_identity(component: Any, budget: Any) -> dict:
    budget.check("admission.component_identity")
    name = _text(component.Name2, "component Name2")
    configuration = _text(component.ReferencedConfiguration, f"{name} configuration")
    suppression = _integer(component.GetSuppression2(), f"{name} suppression")
    _require(
        suppression in (2, 3),
        f"{name}: unresolved/suppressed/error state {suppression}",
    )
    path = _resolved_path(component.GetPathName(), f"{name} path")
    _require(path.suffix.lower() == ".sldprt", f"{name}: not a native part path")
    return {
        "name": name,
        "path": str(path),
        "configuration": configuration,
        "suppression": suppression,
    }


def traverse_features(
    receiver: Any, scope: str, budget: Any, state: dict | None = None
) -> dict:
    """Completely walk an already early-bound model/component receiver.

    Callers bind IModelDoc2 for the root, IComponent2 for configured children.
    IDs are scoped by this result, never shared between inventories. ``state``
    shares only the occurrence budget across the entire independently opened
    model. Repeated appearances retain every edge and re-explore descendants.
    Both native chain termination and empty child chains are recorded explicitly.
    """
    if state is None:
        state = {"occurrences": 0}
    _require(type(state.get("occurrences")) is int, "invalid feature occurrence state")
    graph: dict = {"scope": scope, "nodes": {}, "occurrences": [], "terminations": []}

    def chain(
        raw: Any,
        parent: int | None,
        parent_occurrence: int | None,
        depth: int,
        ancestors: frozenset[int],
        kind: str,
    ) -> None:
        seen: set[int] = set()
        ordinal = 0
        while raw is not None:
            budget.check(f"admission.feature.{scope}.{depth}.{ordinal}")
            _require(depth < FEATURE_DEPTH_CAP, f"{scope}: feature depth cap reached")
            state["occurrences"] += 1
            _require(
                state["occurrences"] < FEATURE_OCCURRENCE_CAP,
                f"{scope}: global feature occurrence cap reached",
            )
            feature = _bound(raw, "IFeature")
            identity = _integer(feature.GetID(), f"{scope} feature GetID")
            _require(identity >= 0, f"{scope}: unresolved feature identity {identity}")
            _require(
                identity not in seen and identity not in ancestors,
                f"{scope}: feature chain/ancestry cycle at {identity}",
            )
            seen.add(identity)
            node = {
                "id": identity,
                "name": _text(feature.Name, f"{scope} feature Name"),
                "type": _text(feature.GetTypeName2(), f"{scope} feature type"),
            }
            if node["type"] == "Reference":
                component = _bound(feature.GetSpecificFeature2(), "IComponent2")
                node["instance"] = _component_identity(component, budget)
            key = str(identity)
            previous = graph["nodes"].get(key)
            _require(
                previous is None or previous == node,
                f"{scope}: inconsistent repeated feature identity {identity}",
            )
            graph["nodes"][key] = node
            occurrence = len(graph["occurrences"])
            graph["occurrences"].append(
                {
                    "id": identity,
                    "parent": parent,
                    "parent_occurrence": parent_occurrence,
                    "depth": depth,
                    "chain": kind,
                    "ordinal": ordinal,
                }
            )
            budget.check(f"admission.feature_children.{scope}.{identity}")
            chain(
                feature.GetFirstSubFeature(),
                identity,
                occurrence,
                depth + 1,
                ancestors | {identity},
                "sub",
            )
            budget.check(f"admission.feature_next.{scope}.{identity}")
            raw = (
                feature.GetNextFeature()
                if kind == "root"
                else feature.GetNextSubFeature()
            )
            ordinal += 1
        graph["terminations"].append(
            {
                "parent": parent,
                "parent_occurrence": parent_occurrence,
                "depth": depth,
                "chain": kind,
                "length": ordinal,
                "native_null": True,
            }
        )

    try:
        budget.check(f"admission.first_feature.{scope}")
        chain(receiver.FirstFeature(), None, None, 0, frozenset(), "root")
    except Exception as error:
        failure = (
            error
            if isinstance(error, Inconclusive)
            else Inconclusive(
                f"{scope}: feature traversal unavailable: {type(error).__name__}: {error}"
            )
        )
        failure.evidence = graph
        raise failure from error
    return graph


def _local_atom(atom: str) -> bool:
    """Validate finite name segments; return whether the atom is a dimension."""
    segments = atom.split("@")
    _require(len(segments) in (1, 2), f"unsupported equation qualification {atom!r}")
    first = segments[0]
    _require(
        bool(first.strip()) and _NAME_SEGMENT.fullmatch(first) is not None,
        f"unsupported equation atom {atom!r}",
    )
    if len(segments) == 2:
        second = segments[1]
        _require(
            bool(second.strip()) and _NAME_SEGMENT.fullmatch(second) is not None,
            f"unsupported equation atom {atom!r}",
        )
    return len(segments) == 2


class _AssignmentParser:
    """A consuming, non-evaluating recognizer, not a SOLIDWORKS evaluator."""

    def __init__(self, text: str, budget: Any):
        self.text = _text(text, "equation")
        self.budget = budget
        self.position = 0
        self.references: list[str] = []

    def whitespace(self) -> None:
        while self.position < len(self.text) and self.text[self.position] in " \t\r\n":
            self.budget.check("admission.equation.whitespace")
            self.position += 1

    def take(self, token: str) -> bool:
        self.whitespace()
        if self.text.startswith(token, self.position):
            self.position += len(token)
            return True
        return False

    def atom(self) -> str:
        self.whitespace()
        _require(self.take('"'), "expected a quoted local equation atom")
        end = self.text.find('"', self.position)
        _require(end >= self.position, "unterminated quoted equation atom")
        atom = self.text[self.position : end]
        _local_atom(atom)
        self.position = end + 1
        return atom

    def expression(self) -> None:
        self.product()
        while True:
            self.budget.check("admission.equation.additive")
            if not (self.take("+") or self.take("-")):
                return
            self.product()

    def product(self) -> None:
        self.primary()
        while True:
            self.budget.check("admission.equation.multiplicative")
            if not (self.take("*") or self.take("/")):
                return
            self.primary()

    def primary(self) -> None:
        self.budget.check("admission.equation.primary")
        while self.take("+") or self.take("-"):
            self.budget.check("admission.equation.unary")
        self.whitespace()
        if self.take("("):
            self.expression()
            _require(self.take(")"), "unbalanced equation parentheses")
        elif self.take("tan"):
            _require(
                self.take("("), "tan requires exactly one parenthesized expression"
            )
            self.expression()
            _require(self.take(")"), "unbalanced tan expression")
        elif self.position < len(self.text) and self.text[self.position] == '"':
            self.references.append(self.atom())
        else:
            match = _NUMBER.match(self.text, self.position)
            _require(
                match is not None, f"unsupported equation token at {self.position}"
            )
            literal = match.group()
            try:
                value = float(literal)
            except (OverflowError, ValueError) as error:
                raise Inconclusive("unsupported equation numeric literal") from error
            _require(math.isfinite(value), "nonfinite native-double equation literal")
            self.position = match.end()
            # Only an attached lowercase mm is permitted; whitespace is not skipped.
            if self.text.startswith("mm", self.position):
                self.position += 2

    def parse(self) -> tuple[str, list[str]]:
        lhs = self.atom()
        _require(self.take("="), "equation is not an assignment")
        self.expression()
        self.whitespace()
        _require(
            self.position == len(self.text),
            f"unconsumed equation syntax at {self.position}",
        )
        return lhs, self.references


def _parse_assignment(text: str, budget: Any) -> tuple[str, list[str]]:
    try:
        return _AssignmentParser(text, budget).parse()
    except RecursionError as error:
        raise Inconclusive(
            "equation nesting is unavailable to the finite recognizer"
        ) from error


def _resolve_dimension(model: Any, atom: str, features: dict, budget: Any) -> dict:
    budget.check(f"admission.equation.parameter.{atom}")
    _require(_local_atom(atom), f"not a local dimension: {atom!r}")
    leaf, feature_name = atom.split("@")
    candidates = []
    for node in features["nodes"].values():
        budget.check("admission.equation.owner_inventory")
        if node["name"].casefold() == feature_name.casefold():
            candidates.append(node)
    _require(
        len(candidates) == 1 and candidates[0]["name"] == feature_name,
        f"{atom}: missing/ambiguous local feature name",
    )
    dimension = _bound(model.Parameter(atom), "IDimension")
    dimension_name = _text(dimension.Name, f"{atom} dimension Name")
    _require(
        dimension_name == leaf, f"{atom}: Parameter returned a different dimension"
    )
    full_name = _text(dimension.FullName, f"{atom} dimension FullName")
    qualified = full_name.split("@")
    model_path = _resolved_path(model.GetPathName(), f"{atom} local model path")
    _require(
        len(qualified) == 3
        and "@".join(qualified[:2]) == atom
        and Path(qualified[2]) == Path(model_path.name),
        f"{atom}: Parameter FullName does not identify this exact local model/dimension",
    )
    owner = _bound(dimension.GetFeatureOwner(), "IFeature")
    identity = _integer(owner.GetID(), f"{atom} owner GetID")
    owner_name = _text(owner.Name, f"{atom} owner Name")
    owner_type = _text(owner.GetTypeName2(), f"{atom} owner type")
    expected = candidates[0]
    _require(
        identity == expected["id"]
        and owner_name == feature_name
        and owner_type == expected["type"],
        f"{atom}: Parameter owner does not match this scoped local feature",
    )
    return {
        "name": dimension_name,
        "full_name": full_name,
        "model_path": str(model_path),
        "feature_id": identity,
        "feature_name": owner_name,
        "feature_type": owner_type,
    }


def parse_equations(
    model: Any, budget: Any, *, referenced_configuration: str, features: dict
) -> dict:
    """Admit every row (disabled included) without evaluation or mutation.

    ``features`` is this matching-config child's complete traversal result.
    Parameter is invoked on this exact IModelDoc2 receiver, then its leaf and
    owner identity are checked; unresolved/ambiguous names never become globals.
    """
    evidence: dict = {"entries": [], "dimensions": {}, "dependencies": {}}
    try:
        model = _bound(model, "IModelDoc2")
        active = _active_configuration(model, budget)
        _require(
            active == referenced_configuration,
            "child active configuration differs from referenced configuration",
        )
        evidence["configuration"] = active
        budget.check("admission.equation.manager")
        manager = _bound(model.GetEquationMgr(), "IEquationMgr")
        linked = manager.LinkToFile
        evidence["link_to_file"] = linked if type(linked) is bool else None
        _require(
            linked is False, "equation manager has linked/unknown external file state"
        )
        count = _integer(manager.GetCount(), "equation count")
        _require(count >= 0, "negative equation count")
        evidence["count"] = count
        declarations: dict[str, dict] = {}
        folded: set[str] = set()
        for index in range(count):
            budget.check(f"admission.equation.row.{index}")
            text = _text(manager.Equation(index), f"equation {index}")
            row = {"index": index, "text": text}
            evidence["entries"].append(row)
            global_variable = manager.GlobalVariable(index)
            row["global"] = global_variable if type(global_variable) is bool else None
            _require(
                type(global_variable) is bool,
                f"equation {index}: unknown global classification",
            )
            lhs, references = _parse_assignment(text, budget)
            dimension = _local_atom(lhs)
            row.update(lhs=lhs, references=references)
            _require(
                global_variable is (not dimension),
                f"equation {index}: global/dimension LHS classification mismatch",
            )
            _require(
                lhs.casefold() not in folded,
                f"duplicate/ambiguous equation declaration {lhs!r}",
            )
            folded.add(lhs.casefold())
            declarations[lhs] = row
        for row in evidence["entries"]:
            budget.check(f"admission.equation.dependencies.{row['index']}")
            lhs = row["lhs"]
            if not row["global"]:
                evidence["dimensions"][lhs] = _resolve_dimension(
                    model, lhs, features, budget
                )
            dependencies = []
            for atom in row["references"]:
                budget.check("admission.equation.reference")
                if _local_atom(atom):
                    if atom not in evidence["dimensions"]:
                        evidence["dimensions"][atom] = _resolve_dimension(
                            model, atom, features, budget
                        )
                else:
                    declaration = declarations.get(atom)
                    _require(
                        declaration is not None and declaration["global"] is True,
                        f"undeclared/ambiguous local global {atom!r}",
                    )
                if atom in declarations:
                    dependencies.append(atom)
                else:
                    _require(
                        atom.casefold() not in folded,
                        f"case-ambiguous equation dependency {atom!r}",
                    )
            evidence["dependencies"][lhs] = dependencies
        # Iterative DFS avoids a Python recursion limit masquerading as a clean graph.
        colors: dict[str, int] = {}
        for start in declarations:
            budget.check("admission.equation.cycle_root")
            if colors.get(start) == 2:
                continue
            stack = [(start, False)]
            while stack:
                budget.check("admission.equation.cycle_step")
                atom, finishing = stack.pop()
                if finishing:
                    colors[atom] = 2
                    continue
                _require(
                    colors.get(atom) != 1, f"equation dependency cycle at {atom!r}"
                )
                if colors.get(atom) == 2:
                    continue
                colors[atom] = 1
                stack.append((atom, True))
                for dependency in reversed(evidence["dependencies"][atom]):
                    budget.check("admission.equation.cycle_edge")
                    stack.append((dependency, False))
        _require(
            _active_configuration(model, budget) == active,
            "child configuration changed during equation admission",
        )
    except Exception as error:
        failure = (
            error
            if isinstance(error, Inconclusive)
            else Inconclusive(
                f"equation admission unavailable: {type(error).__name__}: {error}"
            )
        )
        failure.evidence = evidence
        raise failure from error
    return evidence


def _plain_native(value: Any, budget: Any) -> Any:
    """Copy only already-returned plain values, never stringify/dereference COM."""
    if type(value) is float and not math.isfinite(value):
        return {"native_type": "float", "literal": repr(value)}
    if value is None or type(value) in (str, bool, int, float):
        return value
    if type(value) in (tuple, list):
        copied = []
        for item in value:
            budget.check("admission.plain_evidence")
            copied.append(_plain_native(item, budget))
        return copied  # JSON arrays; callers retain native container representations.
    return {"unavailable_native_type": type(value).__name__}


def _configured_bodies(
    component: Any, budget: Any, evidence: dict | None = None
) -> dict:
    if evidence is None:
        evidence = {}
    evidence.update(query=-1, bodies=[])
    budget.check("admission.configured_bodies")
    raw = component.GetBodies3(-1)  # swAllBodies: solids AND sheets, not wire/mesh.
    evidence["result_representation"] = type(raw).__name__
    _require(
        type(raw) is tuple and len(raw) == 2, "GetBodies3: expected (bodies, info)"
    )
    bodies, info = raw
    evidence.update(
        bodies_representation=type(bodies).__name__,
        info_representation=type(info).__name__,
        raw_info=_plain_native(info, budget),
    )
    _require(
        type(bodies) in (tuple, list) and type(info) in (tuple, list),
        "GetBodies3: missing/malformed body or info array",
    )
    evidence.update(count=len(bodies), info_count=len(info))
    _require(
        len(bodies) > 0 and len(bodies) == len(info),
        "GetBodies3: empty/mismatched configured body arrays",
    )
    for index, (raw_body, raw_info) in enumerate(zip(bodies, info, strict=True)):
        budget.check(f"admission.configured_body.{index}")
        row = {"ordinal": index, "info": _plain_native(raw_info, budget)}
        evidence["bodies"].append(row)
        body_info = _integer(raw_info, "configured body info")
        _require(body_info == 1, "configured body is not swNormalBody_e")
        body = _bound(raw_body, "IBody2")
        row["name"] = _plain_native(body.Name, budget)  # Property positive control.
        _text(row["name"], "body Name positive control", empty=True)
        row["type"] = _plain_native(body.GetType(), budget)
        body_type = _integer(row["type"], "body GetType")
        _require(body_type == 0, "configured body is not a solid")
        faults = body.Check3  # Generated get-only DISPATCH PROPERTY, never Check3().
        row["check3_representation"] = (
            "native_null" if faults is None else type(faults).__name__
        )
        fault_count = 0
        if faults is not None:
            faults = _bound(faults, "IFaultEntity")
            row["fault_count"] = _plain_native(faults.Count, budget)
            fault_count = _integer(row["fault_count"], "body fault Count")
            row["check3_representation"] = "IFaultEntity"
        row["fault_count"] = fault_count
        _require(fault_count == 0, "configured body has faults")
    return evidence


def _external_references(
    component: Any, budget: Any, evidence: dict | None = None
) -> dict:
    if evidence is None:
        evidence = {}
    budget.check("admission.external_reference_count")
    evidence["count"] = _plain_native(
        component.ListExternalFileReferencesCount(), budget
    )
    count = _integer(evidence["count"], "external reference count")
    _require(count == 0, "component has external references")
    budget.check("admission.external_reference_list")
    raw = component.ListExternalFileReferences2()
    evidence.update(
        representation=type(raw).__name__, raw=_plain_native(raw, budget), arrays={}
    )
    _require(
        type(raw) is tuple and len(raw) == 9,
        "ListExternalFileReferences2: expected seven arrays plus I4/BSTR, no bool retval",
    )
    arrays = evidence["arrays"]
    for index, name in enumerate(_EXTERNAL_ARRAY_NAMES):
        budget.check(f"admission.external_reference_array.{name}")
        values = raw[index]
        arrays[name] = {
            "representation": type(values).__name__,
            "raw": _plain_native(values, budget),
        }
        _require(
            values is None or type(values) in (tuple, list),
            f"external reference {name}: malformed array",
        )
        cardinality = 0 if values is None else len(values)
        arrays[name]["count"] = cardinality
        _require(
            cardinality == 0,
            f"external reference {name}: nonzero/mismatched row cardinality",
        )
    option = _integer(raw[7], "external reference ConfigOption")
    _require(option in (0, 1, 2), "unknown external-reference configuration option")
    configuration = _text(raw[8], "external reference ConfigName", empty=True)
    _require(
        option != 2 or bool(configuration.strip()),
        "named external-reference config is empty",
    )
    evidence.update(config_option=option, config_name=configuration)
    return evidence


def _root_inventory(
    graph: dict, instances: dict, prepared_mate: str, sweep: dict, budget: Any
) -> dict:
    """Exact categories/counts and stable known names, not guessed SW auto names."""
    counts: Counter = Counter()
    references = {}
    mates = {}
    groups = []
    planes = []
    profiles = []
    for node in graph["nodes"].values():
        budget.check("admission.root_category")
        kind = node["type"]
        _require(
            kind in ROOT_TYPES,
            f"unknown/ineligible root feature {node['name']!r}: {kind}",
        )
        counts[kind] += 1
        if kind == "Reference":
            instance = node["instance"]
            name = instance["name"]
            _require(
                name not in references, f"duplicate root Reference instance {name}"
            )
            _require(
                name in instances and instance == instances[name]["identity"],
                f"root Reference does not match admitted instance {name!r}",
            )
            references[name] = node["id"]
        elif kind == "MateGroup":
            groups.append(node["id"])
        elif kind in ROOT_MATE_TYPES:
            name = node["name"]
            _require(name not in mates, f"duplicate root mate name {name!r}")
            mates[name] = {"id": node["id"], "type": kind}
        elif kind == "RefPlane":
            planes.append(node["name"])
        elif kind == "ProfileFeature":
            profiles.append(node["name"])
    _require(
        set(references) == set(instances), "root Reference inventory differs from R1"
    )
    _require(len(groups) == 1, "root must contain exactly one MateGroup")
    _require(
        counts["OriginProfileFeature"] == 1,
        "root must contain exactly one template origin",
    )
    _require(
        len(planes) == 4
        and len(set(planes)) == 4
        and {"Front Plane", "Top Plane", "Right Plane"}.issubset(planes),
        "root must contain three default planes and one carrier-seat plane",
    )
    _require(
        profiles == [jig_spec.CL_TIP_FEATURE],
        "root must contain only the known CL-tip sketch",
    )
    # Source: builder _mate_carriages (two planes/carriage), _mate_carrier
    # (two inner pin axes and one scalar seat plane), _lock_families, and
    # author_dof_drives' one transient DRIVE_<key>. Other mate auto names vary.
    coincident_count = (
        2 * len(jig_spec.CARRIAGE_PLACEMENTS) + len(jig_spec.PIN_MATES["inner"]) + 1
    )
    lock_count = 0
    for stem in jig_spec.LOCKED_TO:
        budget.check("admission.root_lock_count")
        lock_count += jig_spec.QUANTITIES[stem]
    _require(
        counts["MateCoincident"] == coincident_count
        and counts["MateLock"] == lock_count
        and counts["MateDistanceDim"] == 1,
        "root mate type/count inventory differs from pinned builder",
    )
    _require(
        prepared_mate == f"DRIVE_{jig_spec.SLIDE_KEY}",
        "unexpected prepared drive mate name",
    )
    _require(
        mates.get(prepared_mate, {}).get("type") == "MateDistanceDim",
        "prepared distance-drive mate is missing",
    )
    inner_names = []
    outer_names = []
    for name, _hole, _pin in jig_spec.PIN_MATES["inner"]:
        budget.check("admission.root_inner_pin")
        _require(
            mates.get(name, {}).get("type") == "MateCoincident",
            f"missing inner pin mate {name}",
        )
        inner_names.append(name)
    for name, _hole, _pin in jig_spec.PIN_MATES["outer"]:
        budget.check("admission.root_outer_pin")
        _require(
            name not in mates, f"outer pin mate already exists before sweep: {name}"
        )
        outer_names.append(name)
    _require(
        sweep.get("assembly") == jig_spec.ASM_NAME
        and sweep.get("drive_key") == jig_spec.SLIDE_KEY,
        "sweep assembly/drive identity differs from pinned jig",
    )
    passes = sweep.get("passes")
    _require(
        type(passes) is list
        and len(passes) == 2
        and passes[0].get("pass") == "inner"
        and passes[0].get("remate") is None
        and passes[1].get("pass") == "outer",
        "unexpected jig sweep pass/remate order",
    )
    remate = passes[1].get("remate")
    expected_coaxial = []
    for name, hole, pin in jig_spec.PIN_MATES["outer"]:
        budget.check("admission.root_remate_contract")
        expected_coaxial.append(
            {
                "label": name,
                "hole": jig_spec.carrier_hole_axis(hole),
                "pin": jig_spec.pin_axis(pin),
            }
        )
    _require(
        type(remate) is dict
        and remate.get("suppress") == inner_names
        and remate.get("coaxial") == expected_coaxial,
        "sweep suppressions/named outer axes differ from pinned source",
    )
    group = groups[0]
    grouped_mates = set()
    for edge in graph["occurrences"]:
        budget.check("admission.root_mate_edge")
        node = graph["nodes"][str(edge["id"])]
        if edge["parent"] == group:
            _require(
                node["type"] in ROOT_MATE_TYPES, "MateGroup has a non-approved child"
            )
            grouped_mates.add(node["id"])
        if node["type"] in ROOT_MATE_TYPES:
            _require(
                edge["parent"] == group, "root mate occurs outside the single MateGroup"
            )
    _require(
        len(grouped_mates) == len(mates),
        "MateGroup does not contain the exact mate inventory",
    )
    return {
        "counts": dict(counts),
        "reference_ids": references,
        "mate_group": group,
        "mates": mates,
        "expected_coincident_count": coincident_count,
        "expected_lock_count": lock_count,
        "prepared_drive": prepared_mate,
        "inner_pin_mates": inner_names,
        "authorized_outer_pin_mates": outer_names,
    }


def admit(
    adapter: Any,
    expected: dict[str, Path],
    budget: Any,
    prepared_mate: str,
    sweep: dict,
) -> dict:
    """Establish R1--R4 once after unchanged static/prepare full rebuilds.

    ``expected`` is the orchestrator's already-hashed exact instance->part-file
    map. No hashing, opening, configuration activation, solve or close occurs
    here. A failure attaches partial plain ``evidence`` to Inconclusive; callers
    must serialize data, not retain exceptions/tracebacks across document close.
    """
    evidence: dict = {
        "admitted": False,
        "instances": {},
        "root_features": {},
        "child_inventories": {},
    }
    state = {"occurrences": 0}
    try:
        with budget.unit("admission"):
            budget.check("admission.start")
            root = _bound(adapter.currentModel, "IModelDoc2")
            assembly = _bound(adapter.currentModel, "IAssemblyDoc")
            _require(
                _integer(root.GetType(), "root document type") == 2,
                "root is not an assembly",
            )
            root_configuration = _active_configuration(root, budget)
            evidence["root_configuration"] = root_configuration
            expected_names = set()
            resolved_expected = {}
            for stem, placements in jig_spec.PLACEMENTS.items():
                budget.check("admission.expected_family")
                _require(
                    len(placements) == jig_spec.QUANTITIES[stem],
                    "pinned jig quantity/placement mismatch",
                )
                for index in range(len(placements)):
                    budget.check("admission.expected_instance")
                    name = jig_spec.instance_name(stem, index)
                    expected_names.add(name)
                    _require(
                        name in expected and isinstance(expected[name], Path),
                        f"expected file missing for {name}",
                    )
                    path = _resolved_path(str(expected[name]), f"expected {name}")
                    _require(
                        path.stem == stem and path.suffix.lower() == ".sldprt",
                        f"{name}: expected native file has wrong family identity",
                    )
                    resolved_expected[name] = path
            _require(
                set(expected) == expected_names,
                "expected closure differs from pinned jig instance inventory",
            )
            budget.check("admission.root_components")
            raw_components = assembly.GetComponents(True)
            _require(
                type(raw_components) in (tuple, list),
                "root component array is unavailable/malformed",
            )
            _require(
                len(raw_components) == len(expected_names),
                "root component count differs from pinned inventory",
            )
            for raw_component in raw_components:
                budget.check("admission.instance")
                component = _bound(raw_component, "IComponent2")
                identity = _component_identity(component, budget)
                name = identity["name"]
                _require(
                    name in expected_names and name not in evidence["instances"],
                    f"additional/duplicate/unexpected root component {name!r}",
                )
                _require(
                    Path(identity["path"]) == resolved_expected[name],
                    f"{name}: resolved file differs from hashed input",
                )
                row = {
                    "path": identity["path"],
                    "configuration": identity["configuration"],
                    "suppression": identity["suppression"],
                    "identity": identity,
                }
                evidence["instances"][name] = row
                child_model = _bound(component.GetModelDoc2(), "IModelDoc2")
                _require(
                    _integer(child_model.GetType(), f"{name} document type") == 1,
                    f"{name}: nested/non-part document is ineligible",
                )
                _require(
                    _resolved_path(
                        child_model.GetPathName(), f"{name} child document path"
                    )
                    == resolved_expected[name],
                    f"{name}: component/model document path mismatch",
                )
                children = component.GetChildren()
                _require(
                    children is None
                    or (type(children) in (tuple, list) and len(children) == 0),
                    f"{name}: nested/malformed child inventory",
                )
                row["children_representation"] = type(children).__name__
                row["configured_bodies"] = {}
                _configured_bodies(component, budget, row["configured_bodies"])
                row["external_references"] = {}
                _external_references(component, budget, row["external_references"])
                scope = json.dumps([identity["path"], identity["configuration"]])
                row["child_inventory"] = scope
                if scope not in evidence["child_inventories"]:
                    with budget.unit(f"admission.child.{name}"):
                        _require(
                            _active_configuration(child_model, budget)
                            == identity["configuration"],
                            f"{name}: active child configuration does not match referenced configuration",
                        )
                        child = {
                            "path": identity["path"],
                            "configuration": identity["configuration"],
                        }
                        evidence["child_inventories"][scope] = child
                        features = traverse_features(component, scope, budget, state)
                        child["features"] = features
                        for node in features["nodes"].values():
                            budget.check("admission.child_category")
                            _require(
                                node["type"]
                                in CHILD_SOLID_TYPES
                                | CHILD_REFERENCE_TYPES
                                | ADMIN_TYPES,
                                f"{name}: unknown/ineligible child feature {node['name']!r}: {node['type']}",
                            )
                        child["equations"] = parse_equations(
                            child_model,
                            budget,
                            referenced_configuration=identity["configuration"],
                            features=features,
                        )
            _require(
                set(evidence["instances"]) == expected_names,
                "missing root instance identities",
            )
            with budget.unit("admission.root_graph"):
                graph = traverse_features(root, "root", budget, state)
                evidence["root_features"] = graph
                evidence["root_inventory"] = _root_inventory(
                    graph,
                    evidence["instances"],
                    prepared_mate,
                    sweep,
                    budget,
                )
                equations = parse_equations(
                    root,
                    budget,
                    referenced_configuration=root_configuration,
                    features=graph,
                )
                evidence["root_equations"] = equations
                _require(equations["count"] == 0, "root contains equations")
            _require(
                _active_configuration(root, budget) == root_configuration,
                "root configuration changed during admission",
            )
            evidence["feature_occurrences"] = state["occurrences"]
            evidence["admitted"] = True
    except Exception as error:
        evidence["admitted"] = False
        evidence["feature_occurrences"] = state["occurrences"]
        if isinstance(error, Inconclusive) and hasattr(error, "evidence"):
            evidence["failed_step_evidence"] = error.evidence
        failure = (
            error
            if isinstance(error, Inconclusive)
            else Inconclusive(f"admission unavailable: {type(error).__name__}: {error}")
        )
        failure.evidence = evidence
        raise failure from error
    return evidence


BASELINE = "862ec3315ce0449e85021b719b70ff0283be1698"
SDK_REVISION = "1ec68e3d12e0518e9bb152eff3d91b4bebd2b229"
REPORT_PATH = CAD_ROOT / "out/reports/jig-dirty-edit.json"
BUDGET_PATH = CAD_ROOT / "out/reports/jig-dirty-edit-budget.json"
FAILURE_PATH = CAD_ROOT / "out/reports/failures/jig-dirty-edit.json"
_MAX_REPORT_BYTES = 64 * 1024 * 1024
_SETTINGS = {
    "TreatCoincidenceAsInterference": False,
    "TreatSubAssembliesAsComponents": True,
    "IncludeMultibodyPartInterferences": True,
    "MakeInterferingPartsTransparent": False,
    "CreateFastenersFolder": False,
    "UseTransform": False,
}


def _error(phase, exc):
    try:
        message = str(exc)
    except Exception as unavailable:
        return {
            "phase": phase,
            "type": type(exc).__name__,
            "message": None,
            "message_unavailable": type(unavailable).__name__,
        }
    return {"phase": phase, "type": type(exc).__name__, "message": message}


def _rejection_summary(evidence):
    """Bound the first concrete rejection for the correlated log/span only."""
    if evidence["status"] == "complete-parent-decision-required":
        return ""

    def describe(issue, prefix=""):
        message = issue.get("message")
        if message is None:
            message = json.dumps(issue, sort_keys=True)
        phase = issue.get("phase", "diagnostic")
        return f"{prefix}{phase}: {message}"[:512]

    for row in evidence["trajectories"]:
        prefix = f"{row['variant']}:"
        if row["errors"]:
            return describe(row["errors"][0], prefix)
        if row["gates"]["failed"]:
            label, reason = row["gates"]["failed"][0]
            return describe({"phase": label, "message": reason}, prefix)
        if row.get("validation_errors"):
            return describe(row["validation_errors"][0], prefix)
    if evidence["errors"]:
        return describe(evidence["errors"][0])
    comparison = evidence["comparison"]
    if comparison and comparison["unclassified_differences"]:
        return describe(
            {
                "phase": "comparison",
                "message": comparison["unclassified_differences"][0],
            }
        )
    return f"diagnostic status: {evidence['status']}"


def _write_json(path, value):
    payload = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    _require(
        len(payload.encode("utf-8")) <= _MAX_REPORT_BYTES,
        "structured evidence exceeds the preregistered 64 MiB bound",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(path)


class Budget:
    """One persisted nominal native-work allowance, never a process deadline."""

    def __init__(self, path, clock=None):
        self.path = Path(path)
        self.clock = clock or time.perf_counter
        _require(
            not self.path.exists(),
            "diagnostic budget already exists; no automatic resubmission",
        )
        # run_build connects before calling this module. Its existing process
        # anchor conservatively includes native setup and import wall overhead.
        self.started = _session._T0 if clock is None else self.clock()
        self.offline_s = 0.0
        self.checks = Counter()
        self.phases = {}
        self.stopped = None
        self.persistence_errors = []
        self.save()

    def snapshot(self):
        return {
            "submission": 1,
            "maximum_submissions": 2,
            "maximum_original_visits_including_separate_acceptance": 42,
            "nominal_limit_s": 3600,
            "cleanup_reserve_s": 600,
            "elapsed_conservative_seat_work_s": max(0.0, self.clock() - self.started),
            "offline_while_holding_seat_s": self.offline_s,
            "scheduled_checks": dict(self.checks),
            "phases": self.phases,
            "planning_stop": self.stopped,
            "persistence_errors": list(self.persistence_errors),
            "clock_basis": "conservative process/seat-work wall time since session import",
            "hard_deadline": False,
        }

    def save(self):
        _write_json(self.path, self.snapshot())

    def _persist(self):
        try:
            self.save()
        except BaseException as exc:
            self.persistence_errors.append(_error("budget.persist", exc))

    def check(self, label, cleanup=False):
        self.checks[label] += 1
        if not cleanup and self.snapshot()["elapsed_conservative_seat_work_s"] >= 3000:
            self.stopped = label
            self._persist()
            raise Inconclusive(f"native planning budget exhausted before {label}")

    @contextlib.contextmanager
    def unit(self, label, cleanup=False):
        self.check(label, cleanup=cleanup)
        started = time.perf_counter_ns()
        try:
            yield
        finally:
            phase = self.phases.setdefault(label, {"attempts": 0, "elapsed_ns": 0})
            phase["attempts"] += 1
            phase["elapsed_ns"] += time.perf_counter_ns() - started
            self._persist()

    @contextlib.contextmanager
    def offline(self):
        started = self.clock()
        try:
            yield
        finally:
            self.offline_s += self.clock() - started
            self._persist()


def _capture_errors(ledger):
    return [error for entry in ledger for error in entry["errors"]]


class Capture:
    """Forward one original native manager; strictly observe the SAME result."""

    def __init__(self, manager, budget, entry):
        self.manager = manager
        self.budget = budget
        self.entry = entry
        self.done = False
        entry.update(
            {
                "compute_calls": 0,
                "rows": [],
                "errors": [],
                "done": [],
                "settings": {},
                "canonical": [],
            }
        )

    def observe_settings(self):
        manager, budget, entry = self.manager, self.budget, self.entry
        try:
            with budget.unit("interference.observer_settings"):
                for name, expected in _SETTINGS.items():
                    budget.check("interference.setting")
                    actual = getattr(manager, name)
                    entry["settings"][name] = (
                        actual
                        if type(actual) is bool
                        else {"unavailable_type": type(actual).__name__}
                    )
                    _require(
                        actual is expected,
                        f"native manager setting {name} unavailable/changed",
                    )
        except BaseException as exc:
            entry["errors"].append(_error("settings", exc))
            if not isinstance(exc, Exception):
                raise

    def __getattr__(self, name):
        return getattr(self.manager, name)

    def GetInterferences(self):
        try:
            with self.budget.unit("interference.original_compute"):
                self.entry["compute_calls"] += 1
                result = self.manager.GetInterferences()
        except BaseException as exc:
            self.entry["errors"].append(_error("GetInterferences", exc))
            raise
        self.entry["raw_container"] = type(result).__name__
        try:
            with self.budget.unit("interference.duplicate_observer_decode"):
                _require(
                    type(result) in (tuple, list),
                    "interference result is not a reusable native array",
                )
                self.entry["row_count"] = len(result)
                _require(
                    len(result) <= 10000,
                    "interference row bound exceeded; incomplete evidence",
                )
                grouped = {}
                for ordinal, raw in enumerate(result):
                    self.budget.check("interference.row")
                    row = {"ordinal": ordinal}
                    self.entry["rows"].append(row)
                    try:
                        _require(raw is not None, "missing interference object")
                        native = _early_bound(raw, "IInterference")
                        components = native.Components
                        _require(
                            type(components) in (tuple, list) and len(components) > 0,
                            "missing/malformed interference component array",
                        )
                        _require(
                            len(components) <= 82,
                            "interference component multiplicity exceeds jig inventory",
                        )
                        identities = []
                        for raw_component in components:
                            self.budget.check("interference.component_metadata")
                            _require(
                                raw_component is not None,
                                "missing interference component",
                            )
                            component = _early_bound(raw_component, "IComponent2")
                            name = component.Name2
                            configuration = component.ReferencedConfiguration
                            _require(
                                type(name) is str and bool(name),
                                "missing native component name",
                            )
                            _require(
                                type(configuration) is str and bool(configuration),
                                "missing native component configuration",
                            )
                            identities.append([name, configuration])
                        row["components"] = identities
                        volume = native.Volume
                        row["raw_volume"] = _plain_native(volume, self.budget)
                        _require(
                            type(volume) in (int, float)
                            and math.isfinite(volume)
                            and volume >= 0,
                            "missing/nonfinite/negative native interference volume",
                        )
                        row["volume_m3"] = volume
                        key = tuple(sorted(tuple(identity) for identity in identities))
                        grouped.setdefault(key, []).append(volume)
                    except Exception as exc:
                        error = _error(f"row:{ordinal}", exc)
                        row["error"] = error
                        self.entry["errors"].append(error)
                self.entry["canonical"] = [
                    {
                        "components": [list(identity) for identity in key],
                        "multiplicity": len(volumes),
                        "volumes_m3": sorted(volumes),
                        "total_m3": sum(volumes),
                    }
                    for key, volumes in sorted(grouped.items())
                ]
        except Exception as exc:
            self.entry["errors"].append(_error("decode", exc))
        # Never replace/materialize the result, even when observation failed.
        return result

    def Done(self):
        try:
            with self.budget.unit("interference.release", cleanup=True):
                result = self.manager.Done()
            self.done = True  # A returned VT_VOID call released the native manager.
            self.entry["done"].append(
                {
                    "success": result is None,
                    "result": _plain_native(result, self.budget),
                }
            )
            if result is not None:
                self.entry["errors"].append(
                    {
                        "phase": "Done",
                        "type": "UnexpectedVoidResult",
                        "message": f"Done returned {type(result).__name__}, expected None",
                    }
                )
            return result
        except BaseException as exc:
            self.entry["done"].append({"success": False, "error": _error("Done", exc)})
            self.entry["errors"].append(_error("Done", exc))
            raise


@contextlib.contextmanager
def scoped_capture(adapter, budget, ledger, label):
    original = _assembly.configured_interference_manager
    captures = []

    def factory(actual_adapter):
        _require(actual_adapter is adapter, "scoped manager used by another adapter")
        entry = {"label": label}
        ledger.append(entry)
        try:
            manager = original(actual_adapter)
        except BaseException as exc:
            entry.update(
                {
                    "errors": [_error("manager_factory", exc)],
                    "compute_calls": 0,
                    "rows": [],
                    "done": [],
                    "settings": {},
                    "canonical": [],
                }
            )
            raise
        capture = Capture(manager, budget, entry)
        captures.append(capture)
        capture.observe_settings()
        return capture

    _assembly.configured_interference_manager = factory
    try:
        yield
    finally:
        _assembly.configured_interference_manager = original
        for capture in captures:
            if not capture.done:
                try:
                    capture.Done()
                except BaseException as exc:
                    capture.entry["errors"].append(
                        _error("secondary_scoped_release", exc)
                    )
            capture.manager = None
        captures.clear()


def _hash_inputs(paths):
    _require(len(paths) <= 10000, "input closure exceeds finite manifest bound")
    result = {}
    for path in sorted({Path(path).resolve() for path in paths}):
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                size += len(chunk)
                digest.update(chunk)
        result[str(path)] = {"bytes": size, "sha256": digest.hexdigest()}
    return result


def _input_paths(name):
    import ch_rocker_arm_tl_oblique_jig_assembly_spec as spec
    from _buildgraph import module_deps_of

    _require(name == spec.ASM_NAME, "diagnostic is restricted to the reviewed jig")
    expected = {}
    for stem, placements in spec.PLACEMENTS.items():
        _require(
            len(placements) == spec.QUANTITIES[stem], "spec placement/quantity mismatch"
        )
        for index in range(len(placements)):
            expected[spec.instance_name(stem, index)] = (
                OUT_SLDPRT / f"{stem}.SLDPRT"
            ).resolve()
    root = (OUT_SLDASM / f"{name}.SLDASM").resolve()
    native = {root, *expected.values()}
    paths = {
        *native,
        *(path.parent / f".{path.stem}.execution" for path in native),
        OUT_SLDASM / f".{name}.dof.json",
        OUT_SLDASM / f".{name}.sweep.json",
    }
    entry = Path(__file__).resolve()
    paths.update((entry, *map(Path, module_deps_of(entry))))
    paths.update(
        CAD_ROOT.parent / filename
        for filename in ("dodo.py", "pyproject.toml", "uv.lock")
    )
    paths.update(path for path in (CAD_ROOT / "config").rglob("*") if path.is_file())
    sdk = CAD_ROOT.parent / "SolidworksMCP-python/src"
    paths.update(path for path in sdk.rglob("*.py") if path.is_file())
    return expected, sorted(paths)


def _provenance():
    from opentelemetry import trace
    import solidworks_mcp

    root = CAD_ROOT.parent

    def revision(path):
        return subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    sdk_root = (root / "SolidworksMCP-python").resolve()
    sdk = revision(sdk_root)
    _require(
        sdk == SDK_REVISION, "SDK revision differs from the reviewed binding contract"
    )
    sdk_origin = Path(solidworks_mcp.__file__).resolve()
    _require(
        sdk_origin.is_relative_to(sdk_root / "src"),
        f"loaded SDK is outside the reviewed source closure: {sdk_origin}",
    )
    context = trace.get_current_span().get_span_context()
    _require(context.is_valid, "native execution trace context is unavailable")
    return {
        "reviewed_baseline": BASELINE,
        "source_commit": revision(root),
        "sdk_commit": sdk,
        "experiment_id": uuid.uuid4().hex,
        "loaded_sdk_origin": str(sdk_origin),
        "python": {
            "version": sys.version,
            "executable": sys.executable,
            "platform": sys.platform,
        },
        "trace_id": f"{context.trace_id:032x}",
        "span_id": f"{context.span_id:016x}",
        "environment": {
            key: os.environ.get(key)
            for key in (
                "TRACEPARENT",
                "HARMONIC_FARM_COMMIT",
                "HARMONIC_FARM_BUILD_ID",
                "HARMONIC_FARM_RUN",
                "OTEL_SERVICE_INSTANCE_ID",
                "HARMONIC_WORKER_ID",
            )
        },
        "order": ["B:dirty-Edit-only", "A:original-Force-False-plus-Edit"],
        "ordered_pair_is_unbiased_benchmark": False,
        "native_binding_availability": "established only by successful admission/observations",
    }


def _residents(adapter, budget, *, cleanup=False):
    """Strict all-resident enumeration, including hidden/outside-cad-out inputs."""
    budget.check("resident.enumeration", cleanup=cleanup)
    app = _early_bound(adapter.swApp, "ISldWorks")
    document = app.GetFirstDocument()
    rows = []
    seen = set()
    while document is not None:
        budget.check("resident.document", cleanup=cleanup)
        _require(
            len(rows) < 500,
            "resident enumeration cap reached before native termination",
        )
        document = _early_bound(document, "IModelDoc2")
        path, title = document.GetPathName(), document.GetTitle()
        _require(
            type(path) is str and type(title) is str and bool(title),
            "unreadable resident document identity",
        )
        identity = (str(Path(path).resolve()) if path else "", title)
        _require(identity not in seen, "resident document cycle/ambiguous identity")
        seen.add(identity)
        rows.append({"path": identity[0], "title": title})
        document = document.GetNext()
    return rows


def _cleanup(adapter, relevant, budget):
    import verify

    result = {"before": None, "after": None, "confirmed": False, "errors": []}
    with budget.unit("cleanup", cleanup=True):
        try:
            result["before"] = _residents(adapter, budget, cleanup=True)
        except BaseException as exc:
            result["errors"].append(_error("cleanup.enumerate_before", exc))
        try:
            # Preserve the existing consumer's unsaved close path and then prove
            # it, since its _attempt calls can swallow native failures.
            verify.discard_open_documents(adapter)
        except BaseException as exc:
            result["errors"].append(_error("cleanup.original_discard", exc))
        adapter.currentModel = None
        try:
            remaining = _residents(adapter, budget, cleanup=True)
            for row in remaining:
                budget.check("cleanup.hidden_document", cleanup=True)
                if row["path"] in relevant:
                    _early_bound(adapter.swApp, "ISldWorks").CloseDoc(row["title"])
            result["after"] = _residents(adapter, budget, cleanup=True)
            _require(
                not any(row["path"] in relevant for row in result["after"]),
                "relevant visible/hidden document remains resident after discard",
            )
            result["confirmed"] = not result["errors"]
        except BaseException as exc:
            result["errors"].append(_error("cleanup.verify", exc))
    return result


def _boundary_keys(sweep):
    keys = []
    for walk in sweep["passes"]:
        if walk["remate"]:
            keys.extend(
                (f"{walk['pass']}:0:pre-remate", f"{walk['pass']}:0:post-remate")
            )
        keys.extend(
            f"{walk['pass']}:{index}:visit" for index in range(len(walk["poses"]))
        )
    return keys


class _Diagnostic:
    def __init__(self, adapter, variant, expected, budget, row):
        self.adapter, self.variant, self.expected, self.budget = (
            adapter,
            variant,
            expected,
            budget,
        )
        self.row = row
        self.current_label = "initial/static"
        self.keys = []
        self.drive_started = None
        row.update(
            {
                "variant": variant,
                "admission": None,
                "boundaries": [],
                "counts": {
                    "writes": 0,
                    "visits": 0,
                    "reads": 0,
                    "suppressions": 0,
                    "coincidences": 0,
                },
                "native_outcomes": [],
                "prepare_attempts": [],
                "remate_attempts": [],
                "interferences": [],
                "errors": [],
                "gates": {"passed": [], "failed": []},
                "original_aggregate_timings": {},
            }
        )

    def check(self, label):
        self.budget.check(label)

    def native(self, label, fn):
        outcome = {"operation": label}
        self.row["native_outcomes"].append(outcome)
        try:
            with self.budget.unit(label):
                result = fn()
            outcome["result"] = _plain_native(result, self.budget)
            _require(
                type(result) in (bool, type(None)),
                f"unexpected native rebuild result for {label}",
            )
            if result is not True:
                self.row["errors"].append(
                    {
                        "phase": label,
                        "type": "UnsuccessfulRebuild",
                        "message": f"literal rebuild result {result!r}",
                    }
                )
            return result
        except BaseException as exc:
            outcome["error"] = _error(label, exc)
            self.row["errors"].append(outcome["error"])
            raise

    @contextlib.contextmanager
    def _attempts(self, phase):
        namespace = vars(self.adapter)
        had_instance_attribute = "_attempt" in namespace
        prior_instance_value = namespace.get("_attempt")
        original = self.adapter._attempt
        outcomes = self.row[f"{phase}_attempts"]
        helper_path = Path(__file__).parent / "_assembly_postbuild.py"
        sdk_path = (
            CAD_ROOT.parent
            / "SolidworksMCP-python/src/solidworks_mcp/adapters/solidworks/assembly.py"
        )
        # CPython 3.14 no longer seeds lambdas with an unused leading None.
        # Its optimizer removes the unreachable trailing None after literal False.
        force_constants = (False,) if sys.version_info >= (3, 14) else (None, False)

        def attempt(fn, *args, **kwargs):
            def observed():
                # Scoped runtime SDK-helper wrapping, ONLY around original
                # prepare/remate. The two pinned single-call lambda forms below
                # identify attempt envelopes; co_names membership alone does not.
                rebuilds = set()
                item = {
                    "rebuild_members": [],
                    "callsite": None,
                    "recognized_pinned_form": False,
                }
                try:
                    code = getattr(fn, "__code__", None)
                    names = set(code.co_names) if code is not None else set()
                    rebuilds = names & {"ForceRebuild3", "EditRebuild3"}
                    recognized = False
                    callsite = None
                    if code is not None:
                        path = Path(code.co_filename).resolve()
                        callsite = {"path": str(path), "line": code.co_firstlineno}
                        zero_argument_lambda = (
                            code.co_name == "<lambda>"
                            and code.co_argcount == 0
                            and code.co_kwonlyargcount == 0
                        )
                        if phase == "prepare" and path == helper_path.resolve():
                            recognized = (
                                zero_argument_lambda
                                and code.co_firstlineno == 102
                                and code.co_names == ("currentModel", "ForceRebuild3")
                                and code.co_freevars == ("adapter",)
                                and code.co_consts == force_constants
                                and code.co_consts[-1] is False
                            )
                        elif path == sdk_path.resolve():
                            recognized = (
                                zero_argument_lambda
                                and code.co_firstlineno == 2431
                                and code.co_names == ("EditRebuild3",)
                                and code.co_freevars == ("model",)
                                and code.co_consts == (None,)
                            )
                        if rebuilds and not recognized:
                            item["code_form"] = {
                                "name": code.co_name[:64],
                                "argument_count": code.co_argcount,
                                "keyword_only_argument_count": code.co_kwonlyargcount,
                                "names_repr": repr(code.co_names)[:256],
                                "freevars_repr": repr(code.co_freevars)[:256],
                                "constants_repr": repr(code.co_consts)[:256],
                            }
                    item.update(
                        rebuild_members=sorted(rebuilds),
                        callsite=callsite,
                        recognized_pinned_form=recognized,
                    )
                except Exception as exc:
                    # Metadata observation must not replace the original callback.
                    item["classification_error"] = _error(
                        f"{phase}.helper_classification", exc
                    )
                    self.row["errors"].append(item["classification_error"])
                if rebuilds and not item["recognized_pinned_form"]:
                    self.row["errors"].append(
                        {
                            "phase": phase,
                            "type": "UnrecognizedHelperRebuild",
                            "message": f"unavailable pinned helper capture: {item['callsite']}",
                        }
                    )
                started = time.perf_counter_ns()
                try:
                    value = fn()
                    if rebuilds or "classification_error" in item:
                        item["result"] = (
                            value
                            if type(value) in (bool, type(None))
                            else type(value).__name__
                        )
                        outcomes.append(item)
                        if value is not True:
                            self.row["errors"].append(
                                {
                                    "phase": phase,
                                    "type": "UnsuccessfulRebuild",
                                    "message": str(item),
                                }
                            )
                    return value
                except BaseException as exc:
                    if rebuilds or "classification_error" in item:
                        item["error"] = _error(phase, exc)
                        outcomes.append(item)
                        self.row["errors"].append(item["error"])
                    raise
                finally:
                    if rebuilds or "classification_error" in item:
                        item["elapsed_ns"] = time.perf_counter_ns() - started

            return original(observed, *args, **kwargs)

        self.adapter._attempt = attempt
        try:
            with self.budget.unit(phase):
                yield
        finally:
            if had_instance_attribute:
                self.adapter._attempt = prior_instance_value
            else:
                del self.adapter._attempt

    def preparing(self):
        return self._attempts("prepare")

    def prepare(self, sweep, mate):
        import ch_rocker_arm_tl_oblique_jig_assembly_spec as spec

        _require(
            sweep == spec.sweep_sidecar(),
            "recorded sweep differs from the pinned reviewed schedule",
        )
        _require(
            self.row["admission"] is None,
            "admission must run exactly once per reopened start",
        )
        self.keys = _boundary_keys(sweep)
        _require(
            len(self.keys) == 16,
            "reviewed schedule does not contain sixteen solve boundaries",
        )
        try:
            with self.budget.unit("diagnostic.admission"):
                self.row["admission"] = admit(
                    self.adapter, self.expected, self.budget, mate, sweep
                )
        except BaseException as exc:
            self.row["admission_failure"] = {
                "error": _error("admission", exc),
                "evidence": getattr(exc, "evidence", None),
            }
            raise

    def before_drive(self, key):
        self.check("pose.mutation+solve")
        self.row["counts"]["writes"] += 1
        self.drive_started = time.perf_counter_ns()

    def solve(self, key, timings):
        _require(
            self.row["admission"] is not None,
            "pose reached without successful admission",
        )
        _require(
            len(self.row["boundaries"]) < len(self.keys)
            and key == self.keys[len(self.row["boundaries"])],
            "boundary order/count changed",
        )
        if self.drive_started is not None:
            phase = self.budget.phases.setdefault(
                "original.drive_write", {"attempts": 0, "elapsed_ns": 0}
            )
            phase["attempts"] += 1
            phase["elapsed_ns"] += time.perf_counter_ns() - self.drive_started
            self.drive_started = None
        boundary = {"key": key, "rebuilds": [], "instances": {}}
        self.row["boundaries"].append(boundary)
        self.current_label = key
        operations = (["force"] if self.variant == "A" else []) + ["edit"]
        for operation in operations:
            timings[f"jig.{operation}_rebuild_attempts"] += 1
            started = time.perf_counter_ns()
            previous = len(self.row["native_outcomes"])
            try:
                model = _early_bound(self.adapter.currentModel, "IModelDoc2")
                callback = (
                    (lambda: model.ForceRebuild3(False))
                    if operation == "force"
                    else model.EditRebuild3
                )
                self.adapter._attempt(
                    lambda: self.native(f"explicit_{operation}", callback), default=None
                )
            finally:
                timings[f"jig.{operation}_rebuild_elapsed_ns"] += (
                    time.perf_counter_ns() - started
                )
                boundary["rebuilds"].extend(self.row["native_outcomes"][previous:])
        try:
            with self.budget.unit("diagnostic.full_instance_observation"):
                self._observe(boundary)
        except BaseException as exc:
            boundary["error"] = _error("boundary.observation", exc)
            self.row["errors"].append(boundary["error"])
            raise

    def _observe(self, boundary):
        app = _early_bound(self.adapter.swApp, "ISldWorks")
        active = app.ActiveDoc
        _require(active is not None, "no active document at explicit solve boundary")
        active = _early_bound(active, "IModelDoc2")
        path = active.GetPathName()
        _require(
            type(path) is str
            and Path(path).resolve()
            == (OUT_SLDASM / f"{self._name()}.SLDASM").resolve()
            and active.GetType() == 2,
            "active-root identity/type changed",
        )
        configuration = _early_bound(
            _early_bound(
                active.ConfigurationManager, "IConfigurationManager"
            ).ActiveConfiguration,
            "IConfiguration",
        ).Name
        _require(configuration == "Default", "active root configuration changed")
        boundary["active_root"] = {
            "path": str(Path(path).resolve()),
            "configuration": configuration,
        }
        assembly = _early_bound(self.adapter.currentModel, "IAssemblyDoc")
        components = assembly.GetComponents(True)
        _require(type(components) in (tuple, list), "boundary membership unavailable")
        _require(
            len(components) == len(self.expected),
            "boundary membership cardinality changed",
        )
        for raw in components:
            self.check("boundary.instance")
            _require(raw is not None, "missing live component")
            component = _early_bound(raw, "IComponent2")
            name = component.Name2
            _require(
                type(name) is str
                and name in self.expected
                and name not in boundary["instances"],
                "missing/extra/duplicate live instance identity",
            )
            path = component.GetPathName()
            config = component.ReferencedConfiguration
            suppression = component.GetSuppression2()
            frozen = self.row["admission"]["instances"][name]
            _require(
                type(path) is str
                and str(Path(path).resolve()) == str(self.expected[name].resolve()),
                f"resolved path changed: {name}",
            )
            _require(
                config == frozen["configuration"]
                and type(config) is str
                and bool(config),
                f"referenced configuration changed: {name}",
            )
            _require(
                type(suppression) is int and suppression == frozen["suppression"],
                f"suppression changed: {name}",
            )
            transform = component.Transform2
            _require(transform is not None, f"Transform2 unavailable: {name}")
            values = _early_bound(transform, "IMathTransform").ArrayData
            _require(
                type(values) in (tuple, list)
                and len(values) == 16
                and all(
                    type(value) in (int, float) and math.isfinite(value)
                    for value in values
                ),
                f"incomplete/nonfinite native transform: {name}",
            )
            boundary["instances"][name] = {
                "path": str(Path(path).resolve()),
                "configuration": config,
                "suppression": suppression,
                "array_data": list(values),
                "meaningful": list(values[:13]),
                "unused": list(values[13:]),
            }
        _require(
            set(boundary["instances"]) == set(self.expected),
            "incomplete keyed observation",
        )

    def _name(self):
        import verify

        return verify.SWEEP_OWNER

    def visit(self, key):
        self.check("consumer.visit")
        self.current_label = key
        self.row["counts"]["visits"] += 1

    def carriage_read(self, name, fn):
        self.row["counts"]["reads"] += 1
        with self.budget.unit("original.carriage_read"):
            return fn()

    def remate(self, label):
        self.check("root.remate")
        key = "suppressions" if label.startswith("suppress:") else "coincidences"
        self.row["counts"][key] += 1

    def remating(self, label):
        self.remate(label)
        return self._attempts("remate")


class _GateReport:
    """Keep Report's real gate semantics, with scheduled-unit accounting."""

    def __init__(self, actual, diagnostic):
        self.actual, self.diagnostic = actual, diagnostic

    def __getattr__(self, name):
        return getattr(self.actual, name)

    def gate(self, label, fn):
        with self.diagnostic.budget.unit(f"original.gate:{label.split(':')[-1]}"):
            self.actual.gate(label, fn)
        # Availability is checked AFTER the original gate/_attempt path; an
        # observer error never substitutes a different consumer outcome.
        for entry in self.diagnostic.row["interferences"]:
            entry["checked_outside_attempt"] = True


def _positive_controls(row, name):
    import ch_rocker_arm_tl_oblique_jig_assembly_spec as spec
    from _interference_contracts import allowed_interference_pairs

    pairs = allowed_interference_pairs(name)
    families = {
        frozenset((spec.HUB_PIN, spec.CARRIER)),
        frozenset((spec.HOLD_DOWN_STUD, spec.T_NUT)),
        frozenset((spec.LEADSCREW, spec.LEADSCREW_NUT)),
    }
    required = [
        tuple(sorted(pair))
        for pair in pairs
        if frozenset(instance.rsplit("-", 1)[0] for instance in pair) in families
    ]
    _require(bool(required), "positive-control allowed pairs unavailable")
    missing = []
    for entry in row["interferences"]:
        positive = {
            tuple(sorted(identity[0] for identity in item["components"]))
            for item in entry["canonical"]
            if item["total_m3"] > 0
        }
        absent = [list(pair) for pair in required if pair not in positive]
        entry["positive_controls_missing"] = absent
        missing.extend(absent)
    return missing


def _validate_trajectory(row, expected, name):
    issues = []
    import ch_rocker_arm_tl_oblique_jig_assembly_spec as spec

    wanted = {
        "writes": 15,
        "visits": 14,
        "reads": 28,
        "suppressions": 2,
        "coincidences": 2,
    }
    if row["counts"] != wanted:
        issues.append({"phase": "counts", "expected": wanted, "actual": row["counts"]})
    if len(row["boundaries"]) != 16 or any(
        set(item["instances"]) != set(expected) for item in row["boundaries"]
    ):
        issues.append(
            {
                "phase": "boundaries",
                "message": "not sixteen complete full-instance records",
            }
        )
    gates = row["gates"]
    suffixes = [
        "saved-rebuild-clean",
        "dof-free-necessity",
        "no-over-constrained",
        "model-healthy",
        "interference-free",
        "pass-sweep-interference-free",
    ]
    if gates["failed"] or gates["passed"] != [
        f"{name}:{suffix}" for suffix in suffixes
    ]:
        issues.append(
            {
                "phase": "gates",
                "message": "all six original gates must pass in their original order",
            }
        )
    entries = row["interferences"]
    expected_interferences = ["initial/static"] + [
        f"{walk['pass']}:{index}:visit"
        for walk in spec.sweep_sidecar()["passes"]
        for index, pose in enumerate(walk["poses"])
        if pose["check"]
    ]
    if [entry["label"] for entry in entries] != expected_interferences:
        issues.append(
            {
                "phase": "interference_counts",
                "message": "expected one initial and ten sweep calculations",
            }
        )
    if any(
        entry["compute_calls"] != 1
        or not entry["done"]
        or not entry["done"][-1]["success"]
        for entry in entries
    ):
        issues.append(
            {
                "phase": "interference_calls",
                "message": "same-call calculation/release invariant failed",
            }
        )
    outcomes = row["native_outcomes"]
    counts = Counter(item["operation"] for item in outcomes)
    if counts != Counter(
        {
            "initial_force": 1,
            "explicit_edit": 16,
            **({"explicit_force": 16} if row["variant"] == "A" else {}),
        }
    ):
        issues.append({"phase": "rebuild_counts", "actual": dict(counts)})
    aggregate = row["original_aggregate_timings"]
    expected_aggregate = {
        "jig.drive_write_attempts": 15,
        "jig.transform_readback_attempts": 28,
        "jig.force_rebuild_attempts": 16 if row["variant"] == "A" else 0,
        "jig.edit_rebuild_attempts": 16,
    }
    if any(aggregate.get(key) != value for key, value in expected_aggregate.items()):
        issues.append({"phase": "original_aggregate_counts", "actual": aggregate})
    preparation_forces = [
        item
        for item in row["prepare_attempts"]
        if item["recognized_pinned_form"]
        and item["rebuild_members"] == ["ForceRebuild3"]
    ]
    preparation_edits = [
        item
        for item in row["prepare_attempts"]
        if item["recognized_pinned_form"]
        and item["rebuild_members"] == ["EditRebuild3"]
    ]
    remate_edits = [
        item
        for item in row["remate_attempts"]
        if item["recognized_pinned_form"]
        and item["rebuild_members"] == ["EditRebuild3"]
    ]
    if (
        len(preparation_forces) != 1
        or len(preparation_edits) != 1
        or len(remate_edits) != 2
    ):
        issues.append(
            {
                "phase": "helper_rebuild_counts",
                "prepare_forces": len(preparation_forces),
                "prepare_edits": len(preparation_edits),
                "remate_edits": len(remate_edits),
            }
        )
    if (
        type(row["admission"]) is not dict
        or row["admission"].get("admitted") is not True
    ):
        issues.append(
            {"phase": "admission", "message": "required admission unavailable"}
        )
    issues.extend(row["errors"])
    issues.extend(_capture_errors(entries))
    if row["variant"] == "A" and _positive_controls(row, name):
        issues.append(
            {
                "phase": "positive_controls",
                "message": "fresh reference is missing expected real allowed positive contacts",
            }
        )
    row["validation_errors"] = issues
    return issues


def _admission_projection(evidence, budget):
    """Compare admitted facts, not body/feature order or a geometry digest."""
    root_inventory = evidence["root_inventory"]
    known_mates = set(root_inventory["inner_pin_mates"])
    known_mates.add(root_inventory["prepared_drive"])

    def count_rows(counter):
        rows = []
        for key, count in sorted(counter.items()):
            budget.check("comparison.admission.counter_row")
            rows.append([_plain_native(key, budget), count])
        return rows

    def features(graph, *, root=False):
        nodes = Counter()
        edges = Counter()
        terminations = Counter()

        def node_key(identity):
            if identity is None:
                return ("", "")
            node = graph["nodes"][str(identity)]
            name = node["name"]
            if root and node["type"] in ROOT_MATE_TYPES and name not in known_mates:
                name = "<automatic-mate-name>"
            return (node["type"], name)

        for node in graph["nodes"].values():
            budget.check("comparison.admission.feature_node")
            nodes[node_key(node["id"])] += 1
        for occurrence in graph["occurrences"]:
            budget.check("comparison.admission.feature_edge")
            edges[(node_key(occurrence["parent"]), node_key(occurrence["id"]))] += 1
        for termination in graph["terminations"]:
            budget.check("comparison.admission.feature_termination")
            terminations[
                (
                    node_key(termination["parent"]),
                    termination["chain"],
                    termination["length"],
                    termination["native_null"],
                )
            ] += 1
        return {
            "nodes": count_rows(nodes),
            "edges": count_rows(edges),
            "terminations": count_rows(terminations),
        }

    def equations(raw):
        entries = {}
        dimensions = {}
        for row in raw["entries"]:
            budget.check("comparison.admission.equation")
            entries[row["lhs"]] = {
                key: value for key, value in row.items() if key != "index"
            }
        for atom, identity in raw["dimensions"].items():
            budget.check("comparison.admission.dimension")
            dimensions[atom] = {
                key: value for key, value in identity.items() if key != "feature_id"
            }
        return {
            "configuration": raw["configuration"],
            "link_to_file": raw["link_to_file"],
            "count": raw["count"],
            "entries": entries,
            "dimensions": dimensions,
            "dependencies": raw["dependencies"],
        }

    instances = {}
    for name, row in evidence["instances"].items():
        budget.check("comparison.admission.instance")
        health = Counter()
        for body in row["configured_bodies"]["bodies"]:
            budget.check("comparison.admission.body_health")
            health[(body["info"], body["type"], body["fault_count"])] += 1
        references = row["external_references"]
        reference_counts = {}
        for field, values in references["arrays"].items():
            budget.check("comparison.admission.external_reference")
            reference_counts[field] = values["count"]
        instances[name] = {
            "identity": row["identity"],
            "child_inventory": row["child_inventory"],
            "body_health": count_rows(health),
            "configured_body_count": row["configured_bodies"]["count"],
            "configured_body_info_count": row["configured_bodies"]["info_count"],
            "external_references": {
                "count": references["count"],
                "arrays": reference_counts,
                "config_option": references["config_option"],
                "config_name": references["config_name"],
            },
        }
    children = {}
    for scope, child in evidence["child_inventories"].items():
        budget.check("comparison.admission.child")
        children[scope] = {
            "path": child["path"],
            "configuration": child["configuration"],
            "features": features(child["features"]),
            "equations": equations(child["equations"]),
        }
    return {
        "admitted": evidence["admitted"],
        "root_configuration": evidence["root_configuration"],
        "instances": instances,
        "child_inventories": children,
        "root_features": features(evidence["root_features"], root=True),
        "root_equations": equations(evidence["root_equations"]),
        "root_inventory": {
            key: root_inventory[key]
            for key in (
                "counts",
                "expected_coincident_count",
                "expected_lock_count",
                "prepared_drive",
                "inner_pin_mates",
                "authorized_outer_pin_mates",
            )
        },
    }


def _compare(b, a, budget):
    before_admission = _admission_projection(b["admission"], budget)
    reference_admission = _admission_projection(a["admission"], budget)
    result = {
        "alarms_are_acceptance_thresholds": False,
        "translation_alarm_m": 1e-9,
        "meaningful_entry_alarm": 1e-9,
        "parent_decision_required": True,
        "admission_equal": before_admission == reference_admission,
        "admission_raw_equal": b["admission"] == a["admission"],
        "admission_comparison_is_geometry_digest": False,
        "admission_semantic_projection": {
            "B": before_admission,
            "A": reference_admission,
        },
        "boundaries": [],
        "interferences": [],
        "unclassified_differences": [],
    }
    if not result["admission_equal"]:
        result["unclassified_differences"].append("admission inventories differ")
    for before, reference in zip(b["boundaries"], a["boundaries"], strict=True):
        budget.check("comparison.boundary")
        _require(before["key"] == reference["key"], "A/B boundary keys differ")
        item = {"key": before["key"], "instances": {}}
        result["boundaries"].append(item)
        for name, observed in before["instances"].items():
            budget.check("comparison.instance")
            expected = reference["instances"][name]
            x, y = observed["array_data"], expected["array_data"]
            deltas = [left - right for left, right in zip(x, y, strict=True)]
            translation = math.sqrt(sum(value * value for value in deltas[9:12]))
            relative = [
                [sum(x[3 * i + k] * y[3 * j + k] for k in range(3)) for j in range(3)]
                for i in range(3)
            ]
            cosine = max(
                -1.0, min(1.0, (sum(relative[i][i] for i in range(3)) - 1) / 2)
            )
            sine = (
                math.sqrt(
                    (relative[2][1] - relative[1][2]) ** 2
                    + (relative[0][2] - relative[2][0]) ** 2
                    + (relative[1][0] - relative[0][1]) ** 2
                )
                / 2
            )
            angle = math.atan2(sine, cosine)
            structural = {
                key: [observed[key], expected[key]]
                for key in ("path", "configuration", "suppression")
                if observed[key] != expected[key]
            }
            item["instances"][name] = {
                "meaningful_entry_deltas": deltas[:13],
                "unused_entry_deltas": deltas[13:],
                "translation_norm_m": translation,
                "translation_norm_mm": translation * 1000,
                "relative_rotation_rad": angle,
                "scale_delta": deltas[12],
                "structural_differences": structural,
                "translation_alarm": translation >= 1e-9,
                "meaningful_entry_alarm": any(
                    abs(value) >= 1e-9 for value in deltas[:13]
                ),
            }
            if structural or any(value != 0 for value in deltas[:13]):
                result["unclassified_differences"].append(f"{before['key']}:{name}")
    for candidate, reference in zip(
        b["interferences"], a["interferences"], strict=True
    ):
        budget.check("comparison.interference")
        equal = (
            candidate["label"] == reference["label"]
            and candidate["canonical"] == reference["canonical"]
        )
        result["interferences"].append(
            {"label": candidate["label"], "canonical_exact_equal": equal}
        )
        if not equal:
            result["unclassified_differences"].append(
                f"interference:{candidate['label']}"
            )
    return result


@_telemetry.traced("verify.jig_dirty_edit_experiment")
async def run(adapter, name, outer_report):
    import verify

    evidence = {
        "schema": "jig-dirty-edit-v2",
        "status": "inconclusive",
        "disposition": "parent decision required; no production cutover authorized",
        "provenance": None,
        "input_snapshots": [],
        "trajectories": [],
        "comparison": None,
        "errors": [],
        "cleanup": None,
    }
    budget = None
    paths = []
    relevant = set()
    primary = None
    original_interference = verify.check_no_interference
    original_annotate = _telemetry.annotate
    current = None
    rejection = ""
    try:
        _require(name == verify.SWEEP_OWNER, "dirty-Edit experiment is jig-local only")
        offline_started = time.perf_counter()
        evidence["provenance"] = _provenance()
        expected, paths = _input_paths(name)
        relevant = {
            str(path.resolve())
            for path in paths
            if path.suffix.upper() in (".SLDPRT", ".SLDASM")
        }
        initial = _hash_inputs(paths)
        evidence["input_snapshots"].append({"stage": "before-B", "files": initial})
        budget = Budget(BUDGET_PATH)
        budget.offline_s += time.perf_counter() - offline_started
        budget._persist()

        def interference(*args, **kwargs):
            budget.check("original.interference_gate")
            label = current.current_label
            first = len(current.row["interferences"])
            try:
                with scoped_capture(
                    adapter, budget, current.row["interferences"], label
                ):
                    with budget.unit("original.interference_gate"):
                        return original_interference(*args, **kwargs)
            finally:
                for entry in current.row["interferences"][first:]:
                    entry["checked_outside_attempt"] = True

        def annotate(**attributes):
            if current is not None and "jig.drive_write_attempts" in attributes:
                current.row["original_aggregate_timings"] = dict(attributes)
            return original_annotate(**attributes)

        verify.check_no_interference = interference
        _telemetry.annotate = annotate
        for variant in ("B", "A"):
            budget.check(f"start-{variant}")
            residents = _residents(adapter, budget)
            _require(
                not any(row["path"] in relevant for row in residents),
                "relevant visible/hidden input document is resident before independent open",
            )
            if variant == "A":
                with budget.offline():
                    snapshot = _hash_inputs(paths)
                evidence["input_snapshots"].append(
                    {"stage": "before-A", "files": snapshot}
                )
                _require(
                    snapshot == initial,
                    "input closure changed before independently reopened A",
                )
            row = {"residents_before": residents}
            evidence["trajectories"].append(row)
            current = _Diagnostic(adapter, variant, expected, budget, row)
            report = verify.Report()
            trajectory_error = None
            try:
                with budget.unit(f"original.trajectory_{variant}"):
                    await verify._verify_static_one(
                        adapter, name, _GateReport(report, current), diagnostic=current
                    )
            except BaseException as exc:
                trajectory_error = exc
                row["errors"].append(_error("trajectory.primary", exc))
                # Keep the original exception identity, but not observer native
                # receivers held in unwound traceback-frame locals across close.
                traceback.clear_frames(exc.__traceback__)
            finally:
                row["gates"] = {
                    "passed": list(report.passed),
                    "failed": [list(failure) for failure in report.failed],
                }
                for entry in row["interferences"]:
                    entry["checked_outside_attempt"] = True
                try:
                    row["cleanup"] = _cleanup(adapter, relevant, budget)
                except BaseException as exc:
                    row["cleanup"] = {
                        "confirmed": False,
                        "errors": [_error("trajectory.secondary_cleanup", exc)],
                    }
                try:
                    with budget.offline():
                        snapshot = _hash_inputs(paths)
                    evidence["input_snapshots"].append(
                        {"stage": f"after-{variant}-cleanup", "files": snapshot}
                    )
                except BaseException as exc:
                    row["errors"].append(_error("trajectory.secondary_hash", exc))
                    if trajectory_error is None:
                        trajectory_error = exc
            if trajectory_error is not None:
                raise trajectory_error
            _require(
                row["cleanup"]["confirmed"],
                "independent trajectory cleanup was not confirmed",
            )
            _require(
                snapshot == initial,
                "input closure bytes changed during unsaved trajectory",
            )
            issues = _validate_trajectory(row, expected, name)
            # Unsupported/incomplete admission is not a reason to widen, repair,
            # or launch a second trajectory. Actual completed gate failures remain
            # data and may be compared with the independently reopened reference.
            _require(
                row["admission"] is not None
                and len(row["boundaries"]) == 16
                and all(
                    set(item["instances"]) == set(expected)
                    for item in row["boundaries"]
                ),
                "incomplete/ineligible trajectory; no additional native work authorized",
            )
            row["complete"] = not issues
        b, a = evidence["trajectories"]
        evidence["comparison"] = _compare(b, a, budget)
        if any(row["gates"]["failed"] for row in (b, a)):
            evidence["status"] = "failed-consumer"
        elif (
            all(row["complete"] for row in (b, a))
            and not evidence["comparison"]["unclassified_differences"]
        ):
            evidence["status"] = "complete-parent-decision-required"
    except BaseException as exc:
        primary = exc
        evidence["errors"].append(_error("primary", exc))
    finally:
        verify.check_no_interference = original_interference
        _telemetry.annotate = original_annotate
        current = None
        if budget is not None:
            try:
                evidence["cleanup"] = _cleanup(adapter, relevant, budget)
                if not evidence["cleanup"]["confirmed"]:
                    evidence["status"] = "inconclusive"
                    evidence["errors"].extend(evidence["cleanup"]["errors"])
            except BaseException as exc:
                evidence["errors"].append(_error("secondary.final_cleanup", exc))
                evidence["status"] = "inconclusive"
            try:
                with budget.offline():
                    final = _hash_inputs(paths)
                evidence["input_snapshots"].append(
                    {"stage": "final-cleanup", "files": final}
                )
                if final != evidence["input_snapshots"][0]["files"]:
                    evidence["status"] = "inconclusive"
                    evidence["errors"].append(
                        {
                            "phase": "final_hash",
                            "type": "InputChanged",
                            "message": "input bytes changed",
                        }
                    )
            except BaseException as exc:
                evidence["errors"].append(_error("secondary.final_hash", exc))
                evidence["status"] = "inconclusive"
            budget._persist()
            evidence["budget"] = budget.snapshot()
            if budget.persistence_errors:
                evidence["errors"].extend(budget.persistence_errors)
                evidence["status"] = "inconclusive"
        else:
            evidence["budget"] = None
            evidence["cleanup"] = {
                "confirmed": False,
                "reason": "no diagnostic trajectory entered; enclosing run_build owns teardown",
            }
        try:
            rejection = _rejection_summary(evidence)
            _telemetry.annotate(
                **{
                    "jig.diagnostic.trajectories": len(evidence["trajectories"]),
                    "jig.diagnostic.boundaries": sum(
                        len(row["boundaries"]) for row in evidence["trajectories"]
                    ),
                    "jig.diagnostic.status": evidence["status"],
                    **({"jig.diagnostic.rejection": rejection} if rejection else {}),
                }
            )
            if rejection:
                _telemetry.error(
                    f"dirty-Edit diagnostic rejected [{name}]: {rejection}; "
                    "inspect jig-dirty-edit.json"
                )
        except BaseException as exc:
            evidence["errors"].append(_error("secondary.telemetry", exc))
            evidence["status"] = "inconclusive"
        # Failure evidence uses the established dodo FAILURES enumeration/upload
        # path as well as the declared success-cache output. Never invent a blob
        # prefix or claim an unobserved upload.
        try:
            _write_json(REPORT_PATH, evidence)
            if evidence["status"] != "complete-parent-decision-required":
                _write_json(FAILURE_PATH, evidence)
        except BaseException as exc:
            evidence["errors"].append(_error("secondary.report_write", exc))
            if primary is None:
                primary = exc
    for row in evidence["trajectories"]:
        outer_report.passed.extend(
            f"{row['variant']}:{label}" for label in row["gates"]["passed"]
        )
        outer_report.failed.extend(
            (f"{row['variant']}:{label}", reason)
            for label, reason in row["gates"]["failed"]
        )
    if evidence["status"] != "complete-parent-decision-required":
        outer_report.failed.append(
            (
                f"{name}:dirty-edit-diagnostic",
                f"{rejection or _rejection_summary(evidence)}; "
                "inspect jig-dirty-edit.json",
            )
        )
    if primary is not None:
        raise primary
    return evidence
