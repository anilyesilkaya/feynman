"""Collect local assets referenced from a document -- the asset-collector stage.

The renderer routes every Markdown image ``src`` through an
:class:`AssetCollector`, which decides what a reference becomes in the output:

- remote (``http(s)://``, protocol-relative ``//``, ``data:``) and site-absolute
  (``/img/x.png``, a deploy URL) refs pass through untouched;
- a local file is, in *portable* mode, copied into a ``media/`` subfolder of the
  output directory (with the ``src`` rewritten to point there) and, in *inline*
  mode, embedded directly as a ``data:`` URI;
- a reference that does not resolve to a file is left as-is and recorded in
  :attr:`missing` so the build can warn without aborting.

Only ``media/`` is ever written by the collector, so it never touches files the
author placed in the output directory.
"""

from __future__ import annotations

import base64
import hashlib
import mimetypes
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlsplit

MEDIA_DIR = "media"
# Prefixes we must never treat as local files: remote/inline URIs, and
# site-absolute paths (handled by the leading-slash check below).
_REMOTE_PREFIXES = ("http://", "https://", "//", "data:", "mailto:")


@dataclass
class AssetCollector:
    """Rewrite image references, copying or inlining local files as needed."""

    source_dir: Path  # directory of the source .md; refs resolve relative to it
    out_dir: Path
    inline: bool
    copied: list[Path] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    def resolve(self, ref: str) -> str:
        """Rewrite one image ``src`` for the output; see the module docstring."""
        if not ref or ref.startswith(_REMOTE_PREFIXES) or ref.startswith("/"):
            return ref
        # Split ?query / #fragment off before touching the filesystem, and
        # decode %20-style escapes so "my%20plot.png" finds "my plot.png".
        parts = urlsplit(ref)
        resolved = (self.source_dir / unquote(parts.path)).resolve()
        if not resolved.is_file():
            self.missing.append(ref)
            return ref
        if self.inline:
            return self._data_uri(resolved)
        return self._copy(resolved)

    def _data_uri(self, path: Path) -> str:
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{b64}"

    def _copy(self, path: Path) -> str:
        name = self._safe_name(path)
        dest = self.out_dir / MEDIA_DIR / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        self.copied.append(dest)
        return f"{MEDIA_DIR}/{name}"

    @staticmethod
    def _safe_name(path: Path) -> str:
        # Prefix a short hash of the absolute source path so two files sharing a
        # basename from different folders cannot collide. The same file resolves
        # to the same name, so a repeated reference is copied only once.
        digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:8]
        return f"{digest}-{path.name}"
