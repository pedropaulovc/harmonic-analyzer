"""Build one private immutable Vite harness; retain exact bundle/code provenance."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time

from ..video import sha256, write_json


def source_seal(web_root: Path) -> dict[str, str]:
    files = [path for path in (web_root/'src').rglob('*') if path.is_file()]
    files += list(web_root.glob('*.html'))
    files += [web_root/'vite.config.ts', web_root/'package.json', web_root/'package-lock.json',
              web_root/'sync'/'dev-middleware.ts', web_root/'public'/'models'/'ha-harmonic-analyzer.glb']
    return {str(path.relative_to(web_root)): sha256(path) for path in sorted(set(files)) if path.is_file()}


def build_snapshot(web_root: Path, root: Path) -> tuple[Path, dict]:
    """No dirty-tree guessing: record it, hash built files, refuse build-time drift."""
    folder = root/'fit-snapshots'
    folder.mkdir(parents=True, exist_ok=True)
    destination = Path(tempfile.mkdtemp(prefix='native-', dir=folder))
    commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=web_root, check=True, capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(['git', 'status', '--porcelain'], cwd=web_root, check=True, capture_output=True, text=True).stdout.splitlines()
    sources = source_seal(web_root)
    started = time.perf_counter()
    command = [str(web_root/'node_modules'/'.bin'/'vite'), 'build', '--outDir', str(destination), '--base', '/']
    result = subprocess.run(command, cwd=web_root, capture_output=True, text=True)
    (destination/'build.log').write_text(result.stdout+result.stderr)
    if result.returncode:
        raise RuntimeError(f'Private native harness build failed ({result.returncode}): {destination}/build.log\n{result.stderr}')
    if sources != source_seal(web_root):
        raise RuntimeError(f'Source changed during native snapshot build: {destination}')
    files = {str(path.relative_to(destination)): sha256(path) for path in sorted(destination.rglob('*')) if path.is_file()}
    if 'fit.html' not in files or 'models/ha-harmonic-analyzer.glb' not in files:
        raise ValueError(f'Native fit HTML/model missing from snapshot: {destination}')
    metadata = {'directory': str(destination), 'gitCommit': commit, 'gitDirty': bool(dirty), 'gitDirtyEntries': dirty,
                'sourceFilesSha256': sources, 'bundleFilesSha256': files,
                'bundleManifestSha256': hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(),
                'buildSeconds': time.perf_counter()-started, 'command': command}
    write_json(destination/'provenance.json', metadata)
    return destination, metadata
