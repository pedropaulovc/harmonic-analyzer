"""Current-only source observations; historical receipts have a separate loader.

The Node validator owns the shared authority/source boundary used by verify-sync.
The inventory is an exact-byte sealed exporter result, never a second approval.
Assembly metadata is compiled by the live TypeScript domain through Node, with
the same source-witness and finite/gauge checks as runtime consumption. Neither
this loader nor the physical change census certifies posed constraints from REST.
The two genuine renderer-created template instances are checked through the
executed, sealed source-assembly creation ledger; raw inventory rows stay intact.
The executed-input declaration includes the actual SSR Scene import closure,
including target shader feedback, but not unrelated CLI/report-only modules.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess

WEB = Path(__file__).resolve().parents[1]
FRESH_ROOT = WEB / "content/v39-source"
LOADER = Path(__file__).with_suffix(".mjs")
EXECUTED_INPUTS = (
    "web/scripts/fresh-source-observations.py", "web/scripts/fresh-source-observations.mjs",
    "web/scripts/fresh-source-observations.schema.json", "web/scripts/source-observations.schema.json",
    "web/scripts/verify-reference.mjs", "web/scripts/fetch-model.mjs",
    "web/scripts/native-identity-map.mjs", "web/scripts/released-models.json",
    "web/src/source-witness.ts", "web/src/image-plane-homography.ts", "web/src/video-catalog.ts",
    "web/src/native-primitive-snapshot.ts", "web/src/source-assembly.ts",
    "web/src/native-target-shader-feedback.ts",
)


def _validate(data=None, inventory=None, video_id=None, operation="validate", web_root=None):
    script = """
import { readFileSync } from 'node:fs';
const fresh = await import(process.argv[1]);
const payload = JSON.parse(readFileSync(0, 'utf8'));
let result;
const root = payload.webRoot;
if (payload.operation === 'inventory') result = (await fresh.loadCurrentAuthority(root)).inventory;
else if (payload.operation === 'load') result = await fresh.loadCurrentObservations(root, payload.videoId);
else if (payload.operation === 'assembly-change-times') result = await fresh.currentSourceAssemblyChangeTimes(payload.data, { webRoot: root });
else result = await fresh.validateCurrentObservations(payload.data, { webRoot: root, inventory: payload.inventory, videoId: payload.videoId ?? payload.data?.source?.videoId });
console.log(JSON.stringify(result));
"""
    try:
        result = subprocess.run(
            ["node", "--input-type=module", "--eval", script, LOADER.resolve().as_uri()],
            input=json.dumps({"operation": operation, "data": data, "inventory": inventory,
                              "videoId": video_id, "webRoot": str(web_root or WEB)}, allow_nan=False),
            capture_output=True, text=True, encoding="utf-8", check=False, cwd=WEB.parent,
        )
    except OSError as error:
        raise ValueError("Current source authority requires Node and the tracked fresh loader") from error
    if result.returncode:
        raise ValueError("Current source authority refused observations: " + result.stderr.strip())
    return json.loads(result.stdout)


def load_observations(video_id, *, web_root=None):
    """Load exactly the fresh namespace; missing files never borrow the archive."""
    return _validate(video_id=video_id, operation="load", web_root=web_root)


def load_inventory(*, web_root=None):
    return _validate(operation="inventory", web_root=web_root)


def validate_observations(data, inventory=None, *, video_id=None, web_root=None):
    return _validate(data, inventory, video_id, web_root=web_root)


def assembly_change_times(data, web_root=None):
    """Exact same-shot requested times where compiled physical state changes."""
    return _validate(data=data, operation="assembly-change-times", web_root=web_root)
