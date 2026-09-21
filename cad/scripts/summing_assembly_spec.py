"""Pure contract for the summing assembly and its drawing package."""

from __future__ import annotations


EXPLODED_VIEW_NAME = "SUMMING_EXPLODED"
SOURCE_CONFIGURATION = "Default"

BOM_QUANTITIES = {
    "knife-mount": 2,
    "knife-hanger-washer": 2,
    "knife-hanger-stud": 2,
    "summing-lever": 1,
    "boss-hook": 1,
    "counter-spring": 1,
    "gooseneck": 1,
}
if len(BOM_QUANTITIES) != 7 or sum(BOM_QUANTITIES.values()) != 10:
    raise AssertionError("the released summing assembly must contain seven BOM rows and ten instances")

BOM_COMPONENTS = tuple(BOM_QUANTITIES)
BOM_PART_NUMBERS = {
    "knife-mount": "MHA-037",
    "knife-hanger-washer": "MHA-131",
    "knife-hanger-stud": "MHA-119",
    "summing-lever": "MHA-073",
    "boss-hook": "MHA-005",
    "counter-spring": "MHA-019",
    "gooseneck": "MHA-032",
}
BOM_DESCRIPTIONS = {
    "knife-mount": "KNIFE-EDGE BEARING SUPPORT",
    "knife-hanger-washer": (
        "ZINC-PLATED STEEL SAE WASHER, MCMASTER 90126A211"
    ),
    "knife-hanger-stud": (
        "MODIFIED GRADE 5 ZINC-PLATED HEX-HEAD SCREW; "
        "MCMASTER 91247A720 STOCK"
    ),
    "summing-lever": "SUMMING LEVER",
    "boss-hook": (
        "TRIMMED #10-24 OPEN ROUTING EYEBOLT, MCMASTER 9490T1"
    ),
    "counter-spring": (
        "MUSIC-WIRE EXTENSION SPRING, MCMASTER 1330K524"
    ),
    "gooseneck": "COUNTER-SPRING GOOSENECK",
}
if set(BOM_PART_NUMBERS) != set(BOM_QUANTITIES):
    raise AssertionError("summing BOM part-number coverage is incomplete")
if set(BOM_DESCRIPTIONS) != set(BOM_QUANTITIES):
    raise AssertionError("summing BOM description coverage is incomplete")

BOM_IDENTITY_ALIASES = {
    number: stem for stem, number in BOM_PART_NUMBERS.items()
}
BOM_NORMALIZED_ALIASES = {
    alias.casefold(): stem for alias, stem in BOM_IDENTITY_ALIASES.items()
}

# These components meet the summing subassembly during final machine
# installation. Their owning frame/channel assemblies release and count them;
# they must be identified here without being duplicated in the summing BOM.
EXTERNAL_INTERFACES = {
    "top-frame": ("MHA-077", 1),
    "gooseneck-set-screw": ("MHA-118", 1),
    "spring-hook": ("MHA-090", 20),
    "channel-spring-installed": ("MHA-011", 20),
}
if set(EXTERNAL_INTERFACES) & set(BOM_QUANTITIES):
    raise AssertionError("external installation interfaces must not be summing BOM rows")

SAVED_SETUP = "neutral"
SAVED_FREE_DOF = "lever_rock"
DEFINED_ALTERNATE_CONFIGURATIONS: tuple[str, ...] = ()

