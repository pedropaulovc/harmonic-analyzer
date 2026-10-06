"""Shared lexical shapes for frozen CAD identities; no registry reads."""

import re

CATEGORIES = frozenset({"ha", "ch", "dt", "fr", "mg", "pd", "pn", "sm", "vn", "sh"})
STEM = re.compile(r"[a-z]{2}-[a-z0-9]+(?:-[a-z0-9]+)*")
NUMBER = re.compile(r"MHA-([A-Z]{2})-([0-9]{3})")
