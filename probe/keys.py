"""Dump the remote-cache key of every cacheable COM task (no backend probe)."""
import json, os, sys
os.environ.setdefault("HARMONIC_REMOTE_CACHE_MODE", "off")
sys.path.insert(0, os.getcwd())
import dodo  # noqa: E402
out = {}
for label, deps in dodo._cache_rows():
    key, _inputs = dodo._cache.key_inputs(deps, dodo.ContentChecker._digest)
    out[label] = key
json.dump(out, open(sys.argv[1], "w"), indent=0, sort_keys=True)
print(len(out))
