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
CURRENT_NATIVE_IDENTITY_MAP_SHA256 = "55483bab7ebd0de57d71839288628de50229f881172c83515512ff937df49af9"
CURRENT_NATIVE_IDENTITY_PROJECTION = MappingProxyType({
    "kind": "current-native-identity-projection",
    "mapSha256": CURRENT_NATIVE_IDENTITY_MAP_SHA256,
    "sourceMapSha256": SOURCE_MAP_SHA256,
})


class CurrentNativeIdentity:
    def __init__(self, path=TABLE_PATH):
        mapping = json.loads(Path(path).read_text(encoding="utf-8"))
        if mapping.get("schemaVersion") != 1 or mapping.get("sourceMapSha256") != SOURCE_MAP_SHA256:
            raise ValueError("Current identity table must reference the sealed native source map")
        self.map_sha256 = hashlib.sha256(json.dumps(
            mapping, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
        if self.map_sha256 != CURRENT_NATIVE_IDENTITY_MAP_SHA256:
            raise ValueError("Current identity table SHA256 differs from pinned consumer map")
        self.provenance = CURRENT_NATIVE_IDENTITY_PROJECTION
        self.aliases = {row["sourceStem"]: row["stem"] for row in mapping["archivedAliases"]}
        self.sources = {}
        self.targets = {}
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
            previous["identities"].extend(identities)
            for identity in identities:
                key = (identity.get("parent"), identity["stem"])
                if key in self.targets:
                    raise ValueError(f"Colliding current native identity: {key}")
                self.targets[key] = source
        self.stems = sorted(set(self.sources) | set(self.aliases)
                            | {stem for _, stem in self.targets}, key=len, reverse=True)

    def project_path(self, path):
        if not isinstance(path, str) or (path != "ha-harmonic-analyzer"
                                        and not path.startswith("ha-harmonic-analyzer/")):
            return path
        if "\\" in path or any(part in ("", ".", "..") for part in path.split("/")):
            raise ValueError(f"Unsafe current native path: {path}")
        parts, parent = [], None
        for name in path.split("/"):
            found = next((stem for stem in self.stems if name == stem or
                          name.startswith(stem) and re.fullmatch(
                              r"(?:(?:--[A-Za-z][A-Za-z0-9_.]*)?-[1-9][0-9]*|-stretch[0-9]{2}-[1-9][0-9]*)(?:@[A-Za-z][A-Za-z0-9_-]*)?",
                              name[len(stem):])), None)
            if found is None:
                if name.startswith("vn-"):
                    raise ValueError(f"Unknown vendor component: {name}")
                parts.append(name)
                parent = name
                continue
            source = self.aliases.get(found, found)
            if source in self.sources:
                candidates = [identity["stem"] for identity in
                              self.sources[source]["identities"]
                              if identity.get("parent") in (None, parent)]
                if len(candidates) != 1:
                    raise ValueError(f"No unique immediate parent for {name}: {parent}")
                target = candidates[0]
            elif (parent, found) in self.targets or (None, found) in self.targets:
                target = found
            else:
                raise ValueError(f"No unique immediate parent for {name}: {parent}")
            parts.append(target + name[len(found):])
            parent = target
        return "/".join(parts)

    def source_aliases(self, sealed_paths):
        """Resolve sealed bytes only, including historical-only lookup aliases.

        These logical aliases do not advertise live CAD registry or builder files.
        """
        aliases = {
            "cad/scripts/ch_vn_channel_spring_stock_geom.py":
                "cad/scripts/vn_channel_spring_stock_geom.py",
            "cad/scripts/sm_vn_counter_spring_stock_geom.py":
                "cad/scripts/vn_counter_spring_stock_geom.py",
        }
        for current in {stem for _, stem in self.targets}:
            sources = {source for (_, stem), source in self.targets.items() if stem == current}
            if len(sources) != 1:
                raise ValueError(f"Ambiguous composed current CAD source: {current}")
            source = sources.pop()
            source_names = {source} | {old for old, new in self.aliases.items() if new == source}
            for source_name in source_names:
                for template in ("cad/config/parts/{}.yaml", "cad/scripts/build_{}.py", "cad/scripts/{}_geom.py"):
                    old = template.format(source_name if template.endswith(".yaml") else source_name.replace("-", "_"))
                    if old not in sealed_paths:
                        continue
                    new = template.format(current if template.endswith(".yaml") else current.replace("-", "_"))
                    if new in aliases and aliases[new] != old:
                        raise ValueError(f"Ambiguous composed current CAD source: {new}")
                    aliases[new] = old
        return aliases


@lru_cache(maxsize=1)
def current_identity():
    return CurrentNativeIdentity()


def project_current_native_path(path):
    return current_identity().project_path(path)


def current_inventory_parts(inventory):
    """Index both archive/current names without changing rest matrices or hashes."""
    parts = {}
    for row in inventory["inventory"]:
        for path in {row["path"], project_current_native_path(row["path"])}:
            if path in parts:
                raise ValueError(f"Colliding current native inventory path: {path}")
            parts[path] = row
    return parts


def project_current_anchor(anchor):
    """Copy only runtime selectors; keep source association and numeric values."""
    return {key: project_current_native_path(value) if key in
            ("partPath", "runtimeTemplatePartPath") else value for key, value in anchor.items()}
