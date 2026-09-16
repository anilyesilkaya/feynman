"""The ``:::figure`` directive: embed an external SVG as a numbered figure.

A directive such as::

    ::: figure {src=diagram.svg theme=auto #fig-shapes}
    A caption in **Markdown**, may reference @sec-viz.
    :::

is compiled at build time into a ``<figure>`` whose body is the *inlined* SVG
source read from ``src`` (a file beside the document), and whose ``<figcaption>``
is the directive body rendered as ordinary Markdown -- exactly like the caption
of a ``:::viz`` block. A ``#fig-...`` id joins the shared "Figure N" counter (see
:mod:`feynman.crossref`), so an embedded figure numbers continuously alongside
executed-cell charts and ``:::viz`` visualisations.

The SVG is *inlined* into the page body rather than referenced as an ``<img>``
(the path an ordinary Markdown image takes through :class:`~feynman.collect.AssetCollector`)
for one reason: inline SVG inherits the page's ``currentColor`` and CSS custom
properties, so the optional ``theme=auto`` recolouring can make a figure adapt to
light/dark. An ``<img>`` would freeze the authored colours.

This module is deliberately pure: it never touches the filesystem. The renderer
resolves ``src`` (via the collector) and passes the SVG *text* to
:func:`render_figure_open`; ``None`` yields a graceful placeholder rather than a
crash. That split keeps the string work here fully unit-testable.

Because the SVG is inlined verbatim (aside from the small normalisation below),
three constraints apply and are the author's responsibility:

- **Trust.** The markup is *not* sanitised -- it may carry ``<script>``, ``on*``
  handlers or ``<foreignObject>``. Feynman ships zero author-controlled script
  elsewhere; embed only SVG you trust (e.g. the sibling ``svg-canvas`` editor's
  clean export).
- **Internal id collisions.** Inlining the *same* file twice (or two files that
  reuse ``id="clip0"``-style ids) can make ``url(#...)`` paint references resolve
  to the wrong definition. Give repeated figures distinct source ids.
- **Embedded ``<style>``.** A ``<style>`` block inside the SVG is *not* scoped and
  leaks to the whole page. Clean exports carry none.
"""

from __future__ import annotations

import re
from html import escape

# The brace body after the ``:::figure`` marker, e.g. ``{src=diagram.svg #fig-x}``.
_PARAMS_RE = re.compile(r"\{([^}]*)\}")
# Quote-aware key=value (borrowed from :mod:`feynman.boxes`): a bare token, or a
# single/double-quoted string that may contain spaces -- so ``src="my art.svg"``
# survives the space that the viz parser's ``[^\s]+`` value would truncate.
_PAIR_RE = re.compile(
    r"""(\w[\w-]*)\s*=\s*(?:"([^"]*)"|'([^']*)'|(\S+))""",
)
# A bare ``#slug`` gives the figure a cross-reference id (same spelling as viz).
_ID_RE = re.compile(r"(?:^|\s)#([A-Za-z0-9_-]+)")

DEFAULT_THEME = "off"
_THEMES = frozenset({"off", "auto"})

# --- SVG normalisation for HTML-body inlining ------------------------------
# An exported ``.svg`` starts with ``<?xml ...?>`` (and may carry a DOCTYPE);
# both are invalid inside an HTML body, so we strip them. Everything else --
# ``xmlns`` (harmless in HTML5 inline SVG), ``viewBox``, comments, ``<title>`` --
# is kept, so the figure stays byte-for-byte reproducible. A real XML parse is
# avoided on purpose: ``xml.etree`` reorders attributes and mangles namespaces.
_XML_PROLOG_RE = re.compile(r"^\s*<\?xml.*?\?>", re.DOTALL)
_DOCTYPE_RE = re.compile(r"^\s*<!DOCTYPE[^>]*>", re.IGNORECASE)
_SVG_TAG_RE = re.compile(r"<svg\b[^>]*>", re.IGNORECASE | re.DOTALL)
_CLASS_RE = re.compile(r"""\bclass\s*=\s*(["'])(?P<val>.*?)\1""", re.IGNORECASE | re.DOTALL)

# --- theme=auto colour map -------------------------------------------------
# Map ink-toned marks to ``currentColor`` (the themed root sets
# ``color: var(--ink)``, so they follow the theme) and paper-toned fills to the
# paper token; leave chromatic colours (e.g. ``#88ccee``) untouched -- they read
# on both backgrounds. Anchored to a paint property so it never rewrites an
# ``id="..."``, an ``xlink:href="#..."`` or a ``url(#...)`` reference.
_THEME_MAP = {
    "#000000": "currentColor",
    "#222222": "currentColor",
    "#ffffff": "var(--paper)",
}
_COLOR_RE = re.compile(
    r"(?P<prop>\b(?:stop-color|flood-color|lighting-color|fill|stroke|color))"
    r"(?P<sep>\s*[:=]\s*[\"']?)"
    r"(?P<val>#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3})\b"
)


def parse_figure_params(info: str) -> dict:
    """Parse a ``:::figure`` info string into a spec dict.

    Returns ``{"theme": ...}`` always, plus ``"src"`` and ``"id"`` when present.
    ``theme`` defaults to :data:`DEFAULT_THEME`. Unknown keys are ignored
    (validation is separate).
    """
    match = _PARAMS_RE.search(info or "")
    body = match.group(1) if match else ""

    params: dict = {}
    for key, dq, sq, bare in _PAIR_RE.findall(body):
        params[key] = dq or sq or bare

    spec: dict = {"theme": params.get("theme", DEFAULT_THEME)}
    if "src" in params:
        spec["src"] = params["src"]

    id_match = _ID_RE.search(body)
    if id_match:
        spec["id"] = id_match.group(1)
    return spec


def validate_figure(spec: dict) -> str | None:
    """Return a warning if ``spec`` is malformed, else ``None``.

    A ``:::figure`` with no ``src`` has nothing to embed; an unknown ``theme``
    value would silently behave as verbatim. Both surface at build time so the
    author can fix a typo. (A ``src`` that names a *missing* file is caught later,
    at render time, where the filesystem is in reach.)
    """
    if not spec.get("src"):
        return "figure directive has no src=; nothing to embed."
    theme = spec.get("theme", DEFAULT_THEME)
    if theme not in _THEMES:
        known = ", ".join(sorted(_THEMES))
        return f"unknown figure theme {theme!r}; embedding verbatim. Known: {known}."
    return None


def normalize_svg(text: str) -> str:
    """Strip the XML prolog and DOCTYPE so the SVG is valid inside an HTML body."""
    text = text.lstrip("﻿")
    text = _XML_PROLOG_RE.sub("", text)
    text = text.lstrip()
    text = _DOCTYPE_RE.sub("", text)
    return text.strip()


def _expand_hex(hexval: str) -> str:
    """Lower-case a hex colour and expand ``#abc`` shorthand to ``#aabbcc``."""
    h = hexval.lower()
    if len(h) == 4:
        h = "#" + "".join(c * 2 for c in h[1:])
    return h


def theme_svg(text: str) -> str:
    """Recolour ink/paper-toned paints to theme tokens; leave the rest untouched."""

    def repl(match: re.Match) -> str:
        mapped = _THEME_MAP.get(_expand_hex(match.group("val")))
        if mapped is None:
            return match.group(0)
        return f"{match.group('prop')}{match.group('sep')}{mapped}"

    return _COLOR_RE.sub(repl, text)


def inject_root_attrs(text: str, *, themed: bool) -> str:
    """Add the figure CSS class(es) to the first ``<svg>`` tag.

    Merges into an existing ``class="..."`` rather than emitting a duplicate
    attribute (browsers honour only the first). Returns ``text`` unchanged if no
    ``<svg>`` tag is found.
    """
    classes = ["feynman-figure-svg"]
    if themed:
        classes.append("feynman-figure-themed")
    added = " ".join(classes)

    tag_match = _SVG_TAG_RE.search(text)
    if not tag_match:
        return text
    tag = tag_match.group(0)

    class_match = _CLASS_RE.search(tag)
    if class_match:
        merged = f"{class_match.group('val')} {added}".strip()
        new_tag = (
            tag[: class_match.start()]
            + f'class="{merged}"'
            + tag[class_match.end() :]
        )
    else:
        new_tag = tag[:4] + f' class="{added}"' + tag[4:]
    return text[: tag_match.start()] + new_tag + text[tag_match.end() :]


def _prepare_svg(svg_text: str | None, themed: bool) -> tuple[str, bool]:
    """Normalise, optionally recolour, and class the SVG; ``(markup, ok)``."""
    if svg_text is None:
        return "", False
    normalized = normalize_svg(svg_text)
    if not _SVG_TAG_RE.search(normalized):
        return "", False
    if themed:
        normalized = theme_svg(normalized)
    return inject_root_attrs(normalized, themed=themed), True


def render_figure_open(info: str, svg_text: str | None, marker: str = "") -> str:
    """Return the opening markup for a ``:::figure`` directive.

    ``svg_text`` is the resolved SVG source (or ``None`` when the file was not
    found); the renderer reads it via the collector and passes it in. ``marker``
    is a cross-reference caption such as ``Figure 5`` when the directive carries a
    ``#fig-...`` id. The directive body (rendered by the inner tokens) becomes the
    ``<figcaption>``; :func:`render_figure_close` emits the closers.

    A missing or non-SVG source degrades to a visible placeholder rather than
    crashing the build; the id still anchors the ``<figure>`` so references resolve.
    """
    spec = parse_figure_params(info)
    fig_id = spec.get("id")
    id_attr = f' id="{escape(fig_id, quote=True)}"' if fig_id else ""
    caption_marker = (
        f'<span class="feynman-fig-label">{escape(marker)}</span> ' if marker else ""
    )
    themed = spec.get("theme") == "auto"

    body, ok = _prepare_svg(svg_text, themed)
    if not ok:
        src = spec.get("src", "")
        reason = "not found" if svg_text is None else "is not valid SVG"
        body = (
            '<div class="feynman-figure-missing" role="img" '
            f'aria-label="Figure source {reason}">'
            f"Figure source {reason}: {escape(src)}</div>"
        )
    return f'<figure class="feynman-figure"{id_attr}>{body}<figcaption>{caption_marker}'


def render_figure_close() -> str:
    return "</figcaption></figure>"
