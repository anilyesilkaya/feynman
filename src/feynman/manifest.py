"""Track the files each build owns, so a rebuild can reclaim only its own stale output.

Feynman writes a small ``.feynman-manifest.json`` into the output directory recording
every file a build generated. On the next build we diff the *previous* set against the
*current* one and delete only what the same owner produced before but no longer does --
never a wholesale directory wipe, and never a file the manifest does not claim.

Ownership is bucketed so different builds sharing one output directory do not clobber
each other:

- a single-document build (``feynman build a.md -o site``) owns the bucket ``doc:a``:
  its page plus the media it references. Building ``b.md`` into the same directory
  reconciles only ``doc:b`` and leaves ``a.html`` and its images alone.
- a collection build (``build-all`` / ``book``) owns one bucket for the whole set, so a
  post deleted from the source folder has its stale page and media reclaimed on rebuild.

Every path is stored as an output-relative POSIX string and validated on load and before
deletion: an absolute path, a ``..`` escape, or anything resolving outside the output
directory is ignored rather than acted on. When ownership is uncertain we keep the file.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path, PurePosixPath

MANIFEST_NAME = ".feynman-manifest.json"
_VERSION = 1


def _relative(out_dir: Path, path: Path | str) -> str | None:
    """Return ``path`` as a safe ``out_dir``-relative POSIX string, or ``None``.

    ``None`` means the path is unsafe to record or delete: absolute where it should be
    relative, escaping ``out_dir`` via ``..`` or a symlink, or otherwise resolving
    outside the output directory. Callers treat ``None`` as "leave it alone".
    """
    out_root = Path(out_dir).resolve()
    p = Path(path)
    try:
        resolved = p.resolve() if p.is_absolute() else (out_root / p).resolve()
        rel = resolved.relative_to(out_root)
    except (ValueError, OSError):
        return None
    if not rel.parts or ".." in rel.parts:
        return None
    return PurePosixPath(rel).as_posix()


def _validate_stored(rel: str) -> str | None:
    """Re-validate a path string loaded from a manifest before trusting it."""
    if not rel or "\\" in rel:
        return None
    pure = PurePosixPath(rel)
    if pure.is_absolute() or ".." in pure.parts:
        return None
    return pure.as_posix()


def _load(out_dir: Path) -> dict[str, list[str]]:
    """Read the manifest's per-owner buckets, keeping only paths that still validate."""
    path = Path(out_dir) / MANIFEST_NAME
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    owners = data.get("owners") if isinstance(data, dict) else None
    if not isinstance(owners, dict):
        return {}
    clean: dict[str, list[str]] = {}
    for owner, files in owners.items():
        if not isinstance(owner, str) or not isinstance(files, list):
            continue
        safe = [v for f in files if isinstance(f, str) and (v := _validate_stored(f))]
        clean[owner] = safe
    return clean


def _write(out_dir: Path, owners: dict[str, list[str]]) -> None:
    payload = {
        "generator": "feynman",
        "version": _VERSION,
        # Sorted for a stable, diff-friendly file.
        "owners": {o: sorted(set(files)) for o, files in sorted(owners.items())},
    }
    (Path(out_dir) / MANIFEST_NAME).write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )


def _prune_empty_dirs(out_dir: Path, candidates: Iterable[Path]) -> None:
    """Remove now-empty directories left behind by deleted files (e.g. ``media/``).

    Walks each deleted file's parent chain upward, removing empty directories until a
    non-empty one (or ``out_dir`` itself) is reached. ``out_dir`` is never removed.
    """
    out_root = Path(out_dir).resolve()
    seen: set[Path] = set()
    for start in candidates:
        d = start.resolve()
        while d != out_root and d not in seen:
            seen.add(d)
            try:
                if d.is_dir() and not any(d.iterdir()):
                    d.rmdir()
                else:
                    break
            except OSError:
                break
            d = d.parent


def reconcile(out_dir: Path, owner: str, current: Iterable[Path | str]) -> None:
    """Record ``owner``'s ``current`` files and delete the ones it no longer produces.

    Only files previously recorded under ``owner`` that are absent from ``current`` are
    removed, and only after re-validating they sit inside ``out_dir``. Other owners'
    files, and any untracked author files, are never touched.
    """
    out_dir = Path(out_dir)
    owners = _load(out_dir)
    previous = set(owners.get(owner, []))

    current_rel: set[str] = set()
    for path in current:
        rel = _relative(out_dir, path)
        if rel is not None:
            current_rel.add(rel)

    removed_parents: list[Path] = []
    for rel in previous - current_rel:
        # Do not let another owner's still-current file be deleted out from under it.
        if any(rel in files for other, files in owners.items() if other != owner):
            continue
        target = out_dir / rel
        try:
            if target.is_file() or target.is_symlink():
                target.unlink()
                removed_parents.append(target.parent)
        except OSError:
            continue

    owners[owner] = sorted(current_rel)
    _prune_empty_dirs(out_dir, removed_parents)
    _write(out_dir, owners)
