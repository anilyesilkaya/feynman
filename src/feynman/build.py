"""Build orchestration: document -> HTML page + assets.

``build_document`` runs the render pipeline, fills the page template, writes the
result, and handles the runtime assets. By default it emits a *portable folder*
(the page plus sidecar ``theme.css`` / ``pygments.css`` / ``feynman.js`` and any
collected images under ``media/``). With ``inline=True`` it emits a single
self-contained HTML file with the stylesheet, script and images embedded.
"""

from __future__ import annotations

import shutil
import sys
from importlib import resources
from pathlib import Path

from jinja2 import Environment

from feynman.collect import MEDIA_DIR, AssetCollector
from feynman.highlight import get_style_css
from feynman.render import render_document

ASSET_FILES = ("theme.css", "feynman.js")
TEMPLATE_NAME = "base.html.j2"
PYGMENTS_CSS_NAME = "pygments.css"


def _asset_text(name: str) -> str:
    return resources.files("feynman.assets").joinpath(name).read_text(encoding="utf-8")


def _guard_inline(name: str, content: str) -> str:
    """Ensure inlined asset content cannot break out of its ``<style>``/script.

    Our first-party assets contain no closing tag, so this is a defensive check
    rather than an escape: if one ever did, fail the build loudly instead of
    emitting broken (and potentially unsafe) HTML.
    """
    if "</style>" in content or "</script>" in content:
        raise ValueError(f"cannot inline {name!r}: it contains a closing tag")
    return content


def build_document(source: Path, out_dir: Path, *, inline: bool = False) -> Path:
    """Build ``source`` into ``out_dir``; return the written HTML path."""
    source = Path(source)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Clear only feynman's own media dir so orphaned images from a prior build
    # do not accumulate; never touch other files the author put in out_dir.
    shutil.rmtree(out_dir / MEDIA_DIR, ignore_errors=True)

    text = source.read_text(encoding="utf-8")
    collector = AssetCollector(source.parent, out_dir, inline=inline)
    doc, body = render_document(text, collector=collector)

    if inline:
        assets = {
            "css": {"content": _guard_inline("theme.css", _asset_text("theme.css"))},
            "pygments": {"content": _guard_inline("pygments.css", get_style_css())},
            "js": {"content": _guard_inline("feynman.js", _asset_text("feynman.js"))},
        }
    else:
        assets = {
            "css": {"href": "theme.css"},
            "pygments": {"href": PYGMENTS_CSS_NAME},
            "js": {"href": "feynman.js"},
        }

    template = Environment(autoescape=False).from_string(_asset_text(TEMPLATE_NAME))
    meta = doc.meta or {}
    title = meta.get("title", source.stem)
    html = template.render(
        title=title,
        theme=meta.get("theme", "light"),
        subtitle=meta.get("subtitle", ""),
        # Small bits of chrome, front-matter driven with neutral defaults.
        tagline=meta.get("tagline", "Ideas, made understandable."),
        kicker=meta.get("kicker", "A feynman notebook"),
        # Optional hero overrides: `hero_title` is raw HTML for the display
        # heading (e.g. line breaks / emphasis); `source_url` links the source.
        hero_title=meta.get("hero_title", "") or title,
        source_url=meta.get("source_url", ""),
        body=body,
        inline=inline,
        assets=assets,
    )

    out_html = out_dir / f"{source.stem}.html"
    out_html.write_text(html, encoding="utf-8")

    # In portable mode, drop the runtime assets alongside the page. In inline
    # mode they are already embedded, and collected images are data URIs, so
    # there is nothing further to write.
    if not inline:
        for name in ASSET_FILES:
            (out_dir / name).write_text(_asset_text(name), encoding="utf-8")
        (out_dir / PYGMENTS_CSS_NAME).write_text(get_style_css(), encoding="utf-8")

    for ref in collector.missing:
        print(f"warning: asset not found: {ref}", file=sys.stderr)

    return out_html
