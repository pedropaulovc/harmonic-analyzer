"""Content-addressed YAML digests shared across dependency checks."""

from functools import lru_cache
import hashlib

import yaml


@lru_cache(maxsize=256)
def yaml_digest(raw: bytes) -> str | None:
    """Digest parsed YAML, or return ``None`` when loading raises ``YAMLError``.

    Cache only immutable input bytes and digest results, never paths or parsed
    objects. Callers still read the file on every check so even same-size edits
    within one filesystem timestamp tick get a new content key.
    """
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError:
        return None
    # Only load errors select the caller's raw-file fallback. Dump failures must
    # propagate, just as they did before canonicalization was cached.
    canon = yaml.safe_dump(
        data, default_flow_style=False, sort_keys=False, allow_unicode=True
    )
    return hashlib.md5(canon.encode("utf-8")).hexdigest()
