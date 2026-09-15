"""Build orchestration: document -> self-contained HTML page + assets.

``build_document`` runs the render pipeline, fills the page template, writes the
result, and copies the runtime assets (stylesheet, the one JS module, the
generated Pygments CSS) alongside it.
"""

from __future__ import annotations

import shutil
from importlib import resources
from pathlib import Path

from jinja2 import Environment

from feynman.highlight import get_style_css
from feynman.render import render_document

ASSET_FILES = ("theme.css", "feynman.js")
TEMPLATE_NAME = "base.html.j2"
PYGMENTS_CSS_NAME = "pygments.css"


def _asset_text(name: str) -> str:
    return resources.files("feynman.assets").joinpath(name).read_text(encoding="utf-8")


def build_document(source: Path, out_dir: Path) -> Path:
    """Build ``source`` into ``out_dir``; return the written HTML path."""
    source = Path(source)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    text = source.read_text(encoding="utf-8")
    doc, body = render_document(text)

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
        assets={"css": "theme.css", "pygments": PYGMENTS_CSS_NAME, "js": "feynman.js"},
    )

    out_html = out_dir / f"{source.stem}.html"
    out_html.write_text(html, encoding="utf-8")

    # Copy static runtime assets verbatim.
    for name in ASSET_FILES:
        (out_dir / name).write_text(_asset_text(name), encoding="utf-8")
    # Emit the generated dual-theme Pygments stylesheet.
    (out_dir / PYGMENTS_CSS_NAME).write_text(get_style_css(), encoding="utf-8")

    return out_html
