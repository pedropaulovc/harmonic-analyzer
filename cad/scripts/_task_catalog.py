"""Pure metadata shared by the doit graph and the agent-readable CLI help.

Keep task names and their short descriptions here so adding a gate changes the
runtime graph and the cmdhelp inventory together. This module deliberately has
no SolidWorks, telemetry, network, or filesystem side effects.
"""

from __future__ import annotations


VERIFY_NAMES = ("soundness", "kinematics")

CHECK_NAMES = (
    "math",
    "config",
    "graph",
    "nameplate",
    "recipe",
    "cache",
    "telemetry",
    "watchdog",
    "freshness",
    "flagonly",
    "partiso",
    "cli",
)

OPTIONAL_CHECK_NAMES = ("verify_telemetry",)

VERIFY_SUMMARIES = {
    "soundness": "Reopen every assembly and prove model health, DOF, and interference soundness.",
    "kinematics": "Author transient DOF drives and verify the mechanism's motion contracts.",
}

CHECK_SUMMARIES = {
    "math": "Verify the Fourier and mechanism mathematics without SolidWorks.",
    "config": "Audit configuration coverage, provenance, and dimensional consistency.",
    "graph": "Test build-graph discovery and fine-grained dependency coverage.",
    "nameplate": "Verify the nameplate engraving geometry source.",
    "recipe": "Run the offline build, release, export, and drawing recipe contracts.",
    "cache": "Test remote-cache keys, provenance, and observability contracts.",
    "telemetry": "Test OpenTelemetry logs, spans, correlation, and release instrumentation.",
    "watchdog": "Test the SolidWorks COM crash and operation-timeout watchdog.",
    "freshness": "Test standalone verification against doit's exact freshness ledger.",
    "flagonly": "Test late-bound SolidWorks flag-only invocation helpers.",
    "partiso": "Enforce part, assembly, and drawing submodule-digest isolation.",
    "cli": "Validate the cmdhelp schema, command inventory, renderers, and examples.",
    "verify_telemetry": "Exercise the opt-in verification span-shape performance contract.",
}

