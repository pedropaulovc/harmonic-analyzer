"""Current consumer identities over unchanged, sealed native archive inputs.

This is a naming projection, not a geometry/source derivative. Source resolution
composes these names with the separately pinned historical file-rename map.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
import re
from types import MappingProxyType

SOURCE_MAP_SHA256 = "1ee9084204cab7025783c5bf0fa98e040cfaa3e4e8200f0d61e58e8dd32c3bfd"
TABLE_PATH = Path(__file__).resolve().parents[1] / "content/current-native-identities.json"
CURRENT_NATIVE_IDENTITY_MAP_SHA256 = "79addb71fe2ae3ee60039f07577b6dc0e40b0104449f18096a0b7643ce4b73af"
CURRENT_NATIVE_OCCURRENCE_NAMESPACE = "archive-role-local"
CURRENT_NATIVE_IDENTITY_PROJECTION = MappingProxyType({
    "kind": "current-native-identity-projection",
    "mapSha256": CURRENT_NATIVE_IDENTITY_MAP_SHA256,
    "sourceMapSha256": SOURCE_MAP_SHA256,
    "occurrenceNamespace": CURRENT_NATIVE_OCCURRENCE_NAMESPACE,
})
_INSTANCE = re.compile(
    r"(?:__[A-Za-z][A-Za-z0-9]*)?(?:(?:--[A-Za-z][A-Za-z0-9_.]*)*-[1-9][0-9]*"
    r"|-stretch[0-9]{2}-[1-9][0-9]*)(?:@[A-Za-z][A-Za-z0-9_-]*)?")


def require_current_native_occurrence_namespace(namespace):
    """Refuse joining archive-local selectors to unchecked rebuilt-native names."""
    if namespace != CURRENT_NATIVE_OCCURRENCE_NAMESPACE:
        raise ValueError(f"Unsupported occurrence namespace {namespace}; native readback is required")


def _context(identity):
    return (identity.get("parent"), identity["stem"],
            identity.get("configuration"), identity.get("role"))


class CurrentNativeIdentity:
    def __init__(self, path=TABLE_PATH):
        mapping = json.loads(Path(path).read_text(encoding="utf-8"))
        if mapping.get("schemaVersion") != 1 or mapping.get("sourceMapSha256") != SOURCE_MAP_SHA256:
            raise ValueError("Current identity table must reference the sealed native source map")
        self.map_sha256 = hashlib.sha256(json.dumps(
            mapping, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
        if self.map_sha256 != CURRENT_NATIVE_IDENTITY_MAP_SHA256:
            raise ValueError("Current identity table SHA256 differs from pinned consumer map")
        require_current_native_occurrence_namespace(mapping.get("occurrenceNamespace"))
        self.provenance = CURRENT_NATIVE_IDENTITY_PROJECTION
        self.aliases = {row["sourceStem"]: row["stem"] for row in mapping["archivedAliases"]}
        self.archived_numbers = {row["sourceStem"]: row["sourceNumber"] for row in mapping["archivedNumbers"]}
        self.shared = {row["stem"]: row for row in mapping["sharedVendors"]}
        self.source_files = mapping["sourceFiles"]
        self.sources, self.targets, self.prior_targets = {}, {}, {}
        numbers = {}
        rows = [(row, row["identities"]) for row in
                [*mapping["machineVendors"], *mapping["nativeIdentities"]]]
        rows += [(row, [row]) for row in
                 [*mapping["toolingVendors"], *mapping["archiveOnlyVendors"]]]
        for row, identities in rows:
            source = row["sourceStem"]
            if not identities:
                raise ValueError(f"Empty current native mapping: {source}")
            previous = self.sources.setdefault(source, {
                "sourceNumber": row["sourceNumber"], "identities": []})
            if previous["sourceNumber"] != row["sourceNumber"]:
                raise ValueError(f"Conflicting historical number: {source}")
            for identity in identities:
                if any(_context(old) == _context(identity) for old in previous["identities"]):
                    raise ValueError(f"Colliding current native identity: {source}")
                stem = identity["stem"]
                if stem in numbers and numbers[stem] != identity.get("number"):
                    raise ValueError(f"Conflicting current Number: {stem}")
                numbers[stem] = identity.get("number")
                group = self.shared.get(stem)
                if group and (identity.get("number") != group["number"]
                              or identity.get("configuration") not in group["configurations"]
                              or len(group["configurations"]) > 1 and identity.get("role") != identity.get("configuration")
                              or not isinstance(identity.get("role"), str)
                              or re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", identity["role"]) is None):
                    raise ValueError(f"Conflicting shared identity: {stem}")
                previous["identities"].append(identity)
                record = (source, identity)
                self.targets.setdefault((identity.get("parent"), stem), []).append(record)
                if identity.get("priorStem"):
                    self.prior_targets.setdefault(identity["priorStem"], []).append(record)
        self.stems = sorted(set(self.sources) | set(self.aliases) | set(self.prior_targets)
                            | {stem for _, stem in self.targets}, key=len, reverse=True)

    def _token(self, name, allow_configuration=False):
        if not isinstance(name, str):
            return None
        return next(((stem, name[len(stem):]) for stem in self.stems
                     if name == stem or name.startswith(stem)
                     and (_INSTANCE.fullmatch(name[len(stem):]) or allow_configuration
                          and re.fullmatch(r"(?:__[A-Za-z][A-Za-z0-9]*(?:--[A-Za-z][A-Za-z0-9_.]*)*|(?:--[A-Za-z][A-Za-z0-9_.]*)+)",
                                           name[len(stem):]))), None)

    def _resolve(self, stem, parent, suffix=""):
        source = self.aliases.get(stem, stem)
        if source in self.sources:
            records = [(source, identity) for identity in self.sources[source]["identities"]]
            current = False
        elif stem in self.prior_targets:
            records, current = self.prior_targets[stem], False
        else:
            records = self.targets.get((parent, stem), self.targets.get((None, stem), []))
            current = True
        records = [(source, identity) for source, identity in records
                   if identity.get("parent") in (None, parent)]
        if current:
            role = re.match(r"__([A-Za-z][A-Za-z0-9]*)", suffix)
            configuration = re.match(r"--([A-Za-z][A-Za-z0-9_.]*)", suffix)
            if role:
                records = [(source, identity) for source, identity in records
                           if identity.get("role") == role[1]]
            if (configuration and stem in self.shared
                    and "Default" not in self.shared[stem]["configurations"]):
                records = [(source, identity) for source, identity in records
                           if identity.get("configuration") == configuration[1]]
        identities = {_context(identity): identity for _, identity in records}
        if len(identities) != 1:
            raise ValueError(f"No unique immediate parent/member for {stem}: {parent}")
        identity = next(iter(identities.values()))
        role = re.match(r"__([A-Za-z][A-Za-z0-9]*)", suffix)
        if role and role[1] != identity.get("role"):
            raise ValueError(f"Wrong role for {stem}")
        group = self.shared.get(identity["stem"])
        configuration = re.match(r"--([A-Za-z][A-Za-z0-9_.]*)", suffix)
        if (group and configuration and configuration[1] in group["configurations"]
                and configuration[1] != identity["configuration"]):
            raise ValueError(f"Wrong configuration for {stem}")
        return records, identity

    def _occurrence_suffix(self, identity, suffix):
        qualifier = ""
        if identity.get("configuration") not in (None, "Default"):
            qualifier = "--" + identity["configuration"]
        elif identity.get("role"):
            peers = self.targets.get((identity.get("parent"), identity["stem"]), [])
            if len({peer.get("role") for _, peer in peers}) > 1:
                qualifier = "__" + identity["role"]
        return qualifier + suffix if qualifier and not suffix.startswith(qualifier) else suffix

    def project_path(self, path, *, occurrence_namespace=CURRENT_NATIVE_OCCURRENCE_NAMESPACE):
        require_current_native_occurrence_namespace(occurrence_namespace)
        if not isinstance(path, str) or (path != "ha-harmonic-analyzer"
                                        and not path.startswith("ha-harmonic-analyzer/")):
            return path
        if "\\" in path or any(part in ("", ".", "..") for part in path.split("/")):
            raise ValueError(f"Unsafe current native path: {path}")
        parts, parent = [], None
        for name in path.split("/"):
            found = self._token(name)
            if found is None:
                if name.startswith(("vn-", "sh-vn-")):
                    raise ValueError(f"Unknown vendor component: {name}")
                parts.append(name)
                parent = name
                continue
            stem, suffix = found
            _, identity = self._resolve(stem, parent, suffix)
            parts.append(identity["stem"] + self._occurrence_suffix(identity, suffix))
            parent = identity["stem"]
        return "/".join(parts)

    def project_number(self, number, stem, parent=None):
        found = self._token(stem, allow_configuration=True)
        if found is None:
            raise ValueError(f"Unknown native identity: {stem}")
        records, identity = self._resolve(found[0], parent, found[1])
        match = re.fullmatch(r"(.*?)(-T[0-9]{3})?", number)
        accepted = {self.archived_numbers.get(found[0]), identity.get("number")}
        for source, candidate in records:
            accepted.update((self.sources[source]["sourceNumber"], candidate.get("priorNumber")))
        if match is None or match[1] not in accepted:
            raise ValueError(f"Number {number} does not identify {stem}")
        return None if identity.get("number") is None else identity["number"] + (match[2] or "")

    def source_aliases(self, sealed_paths, *, parent=None, configuration=None, role=None):
        """Return every declared source candidate, never a presence-based choice."""
        aliases = {
            "cad/scripts/ch_vn_channel_spring_stock_geom.py":
                {"cad/scripts/vn_channel_spring_stock_geom.py"},
            "cad/scripts/sm_vn_counter_spring_stock_geom.py":
                {"cad/scripts/vn_counter_spring_stock_geom.py"},
        }
        for records in self.targets.values():
            for source, identity in records:
                names = {source} | {old for old, new in self.aliases.items() if new == source}
                current_names = {identity["stem"]}
                if identity.get("priorStem"):
                    current_names.add(identity["priorStem"])
                for current in current_names:
                    for template in ("cad/config/parts/{}.yaml", "cad/scripts/build_{}.py",
                                     "cad/scripts/{}_geom.py", "cad/scripts/{}_spec.py"):
                        logical = template.format(current if template.endswith(".yaml") else current.replace("-", "_"))
                        # Keep known-but-unselected names so a mismatched selector
                        # cannot fall back to a same-named file elsewhere.
                        candidates = aliases.setdefault(logical, set())
                        if ((parent is not None and identity.get("parent") != parent)
                                or (configuration is not None and identity.get("configuration") != configuration)
                                or (role is not None and identity.get("role") != role)):
                            continue
                        for name in names:
                            old = template.format(name if template.endswith(".yaml") else name.replace("-", "_"))
                            if old in sealed_paths:
                                candidates.add(old)
        for row in self.source_files:
            candidates = aliases.setdefault(row["currentPath"], set())
            parent_matches = parent is None or any(
                identity.get("parent") == parent and identity.get("configuration") == row.get("configuration")
                and identity.get("role") == row.get("role")
                for records in self.targets.values() for _, identity in records)
            if (parent_matches and (configuration is None or row.get("configuration") == configuration)
                    and (role is None or row.get("role") == role)):
                candidates.add(row["sourcePath"])
        return {logical: tuple(sorted(candidates)) for logical, candidates in aliases.items()}


@lru_cache(maxsize=1)
def current_identity():
    return CurrentNativeIdentity()


def project_current_native_path(path, *, occurrence_namespace=CURRENT_NATIVE_OCCURRENCE_NAMESPACE):
    return current_identity().project_path(path, occurrence_namespace=occurrence_namespace)


def current_inventory_parts(inventory):
    """Index both archive/current names without changing rest matrices or hashes."""
    if "occurrenceNamespace" in inventory:
        require_current_native_occurrence_namespace(inventory["occurrenceNamespace"])
    parts = {}
    for row in inventory["inventory"]:
        for path in {row["path"], project_current_native_path(row["path"])}:
            if path in parts:
                raise ValueError(f"Colliding current native inventory path: {path}")
            parts[path] = row
    return parts


def project_current_anchor(anchor):
    """Copy only runtime selectors; keep source association and numeric values."""
    if "occurrenceNamespace" in anchor:
        require_current_native_occurrence_namespace(anchor["occurrenceNamespace"])
    return {key: project_current_native_path(value) if key in
            ("partPath", "runtimeTemplatePartPath") else value for key, value in anchor.items()}
