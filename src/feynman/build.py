"""Build orchestration: document -> HTML page + assets.

``build_document`` runs the render pipeline, fills the page template, writes the
result, and handles the runtime assets. By default it emits a *portable folder*
(the page plus sidecar ``theme.css`` / ``pygments.css`` / ``feynman.js`` and any
collected images under ``media/``). With ``inline=True`` it emits a single
self-contained HTML file with the stylesheet, script and images embedded.

The render-and-fill core is factored into :func:`render_page` so the
multi-document builder (:mod:`feynman.collection`) can reuse it without
re-implementing the pipeline, and share the runtime assets across every page.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from jinja2 import Environment, FunctionLoader

from feynman import diagnostics, manifest
from feynman.collect import AssetCollector
from feynman.highlight import get_style_css
from feynman.render import render_document
from feynman.themes import BASE_CSS, resolve

# The runtime script and the base stylesheet ship with every page; theme CSS
# layers are added per document. ``minisearch.min.js`` (SEARCH_JS) is shipped
# only by the multi-document builder, since only its search page loads it.
ASSET_FILES = ("feynman.js",)
SEARCH_JS = "minisearch.min.js"
PYGMENTS_CSS_NAME = "pygments.css"


def _asset_text(name: str) -> str:
    return resources.files("feynman.assets").joinpath(name).read_text(encoding="utf-8")


# One Jinja environment whose loader reads templates from the package assets, so
# a theme template's ``{% extends "base.html.j2" %}`` resolves. autoescape stays
# off: the body is already-rendered trusted HTML, as it was for the flat page.
_ENV = Environment(loader=FunctionLoader(_asset_text), autoescape=False)


def _guard_inline(name: str, content: str) -> str:
    """Ensure inlined asset content cannot break out of its ``<style>``/script.

    Our first-party assets contain no closing tag, so this is a defensive check
    rather than an escape: if one ever did, fail the build loudly instead of
    emitting broken (and potentially unsafe) HTML.
    """
    if "</style>" in content or "</script>" in content:
        raise ValueError(f"cannot inline {name!r}: it contains a closing tag")
    return content


@dataclass
class RenderedPage:
    """A rendered document: its HTML, front matter, and the CSS layers it uses.

    ``body`` is the rendered prose HTML (before the page shell), kept separately
    so a caller (e.g. the search-index builder) can extract plain text from it.
    """

    html: str
    meta: dict
    body: str
    css_files: tuple[str, ...]
    media: tuple[Path, ...] = ()  # local images copied into out_dir/media/ (portable)


def render_page(
    source: Path,
    out_dir: Path,
    *,
    inline: bool = False,
    home_url: str | None = None,
    targets: dict | None = None,
    current_url: str = "",
    nav: dict | None = None,
    chapter: int | None = None,
) -> RenderedPage:
    """Run the pipeline for one ``source`` and return its :class:`RenderedPage`.

    This fills the page template but writes *nothing*; the caller decides what
    lands on disk (the single-file :func:`build_document`, or the multi-document
    builder in :mod:`feynman.collection`). Local images are still collected into
    ``out_dir`` because that rewriting happens during rendering.

    ``home_url`` adds a "Home" link to the header pointing at it; ``None`` (the
    default) omits the link, so a standalone page keeps its original chrome. The
    multi-document builder passes the listing page so each post can return to it.

    ``targets`` / ``current_url`` are forwarded to :func:`render_document` for a
    book build (a book-wide cross-reference map and this page's URL). ``nav`` is
    an optional ``{"prev": {...}, "next": {...}}`` mapping of adjacent chapters,
    each ``{"url", "title"}``; the page template renders prev/next links from it.
    """
    text = source.read_text(encoding="utf-8")
    collector = AssetCollector(source.parent, out_dir, inline=inline)
    doc, body = render_document(
        text,
        collector=collector,
        targets=targets,
        current_url=current_url,
        source=str(source),
        chapter=chapter,
    )

    meta = doc.meta or {}
    theme, style_warning = resolve(meta.get("style"))
    if style_warning:
        diagnostics.warn(style_warning, source=str(source))

    # The base stylesheet first, then any theme layers, so a layer only overrides
    # what it needs. Emitted in this order into the page.
    css_files = (BASE_CSS, *theme.styles)

    if inline:
        assets = {
            "css": [
                {"content": _guard_inline(name, _asset_text(name))} for name in css_files
            ],
            "pygments": {"content": _guard_inline("pygments.css", get_style_css())},
            "js": {"content": _guard_inline("feynman.js", _asset_text("feynman.js"))},
        }
    else:
        assets = {
            "css": [{"href": name} for name in css_files],
            "pygments": {"href": PYGMENTS_CSS_NAME},
            "js": {"href": "feynman.js"},
        }

    template = _ENV.get_template(theme.template)
    title = meta.get("title", source.stem)
    html = template.render(
        title=title,
        theme=meta.get("theme", "light"),
        style=theme.name,
        subtitle=meta.get("subtitle", ""),
        # Small bits of chrome, front-matter driven with per-theme defaults.
        tagline=meta.get("tagline", theme.defaults.get("tagline", "")),
        kicker=meta.get("kicker", theme.defaults.get("kicker", "")),
        # Optional hero overrides: `hero_title` is raw HTML for the display
        # heading (e.g. line breaks / emphasis); `source_url` links the source.
        hero_title=meta.get("hero_title", "") or title,
        source_url=meta.get("source_url", ""),
        # Extra front matter consumed by specific themes (ignored by others).
        authors=meta.get("authors", ""),
        date=meta.get("date", ""),
        version=meta.get("version", ""),
        abstract=meta.get("abstract", ""),
        keywords=meta.get("keywords", ""),
        badges=meta.get("badges") or [],
        body=body,
        inline=inline,
        assets=assets,
        home_url=home_url,
        nav=nav or {},
        chapter=chapter,
    )

    for ref in collector.missing:
        diagnostics.warn(f"asset not found: {ref}", source=str(source))
    for ref in collector.undecodable:
        diagnostics.warn(
            f"asset is not UTF-8 text, so it cannot be inlined: {ref}. "
            f":::figure embeds SVG source; use a Markdown image (![alt](...)) "
            f"for a raster file.",
            source=str(source),
        )

    return RenderedPage(
        html=html,
        meta=meta,
        body=body,
        css_files=css_files,
        media=tuple(collector.copied),
    )


def write_shared_assets(out_dir: Path, css_files: tuple[str, ...]) -> None:
    """Write the runtime scripts, theme CSS layers and Pygments CSS into ``out_dir``.

    Idempotent: writing the same files twice (once per page in a multi-document
    build) is harmless, so callers need not track which assets already landed.
    """
    for name in ASSET_FILES:
        (out_dir / name).write_text(_asset_text(name), encoding="utf-8")
    for name in css_files:
        (out_dir / name).write_text(_asset_text(name), encoding="utf-8")
    (out_dir / PYGMENTS_CSS_NAME).write_text(get_style_css(), encoding="utf-8")


def build_document(source: Path, out_dir: Path, *, inline: bool = False) -> Path:
    """Build ``source`` into ``out_dir``; return the written HTML path."""
    source = Path(source)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    page = render_page(source, out_dir, inline=inline)

    out_html = out_dir / f"{source.stem}.html"
    # Under ``--strict`` a diagnostic means this page must not ship. Rendering
    # above emitted every diagnostic the document can produce, so checking here
    # -- before the first write -- is what makes strict mode a real gate rather
    # than a report filed after the broken page is already on disk.
    if diagnostics.should_abort():
        return out_html
    out_html.write_text(page.html, encoding="utf-8")

    # In portable mode, drop the runtime assets alongside the page. In inline
    # mode they are already embedded, and collected images are data URIs, so
    # there is nothing further to write.
    # In inline mode nothing else lands on disk (images are data URIs), so there
    # is no sidecar state to track or reclaim; keep the output to the one file.
    if not inline:
        write_shared_assets(out_dir, page.css_files)
        # Reclaim only *this document's* stale output from a prior build (e.g.
        # an image it no longer references), leaving other documents built into
        # the same directory -- and any author files -- untouched. Shared
        # sidecar assets are not tracked: overwritten in place, shared by docs.
        owned = [out_html, *page.media]
        manifest.reconcile(out_dir, f"doc:{source.stem}", owned)

    return out_html
