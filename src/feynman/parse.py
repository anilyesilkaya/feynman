"""Markdown parsing: MarkdownIt configuration and front-matter extraction.

We build one configured ``MarkdownIt`` instance with the plugins the authoring
format needs, and split YAML front matter off the top of a document. Rendering
of the resulting token stream lives in :mod:`feynman.render`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import yaml
from markdown_it import MarkdownIt
from mdit_py_plugins.anchors import anchors_plugin
from mdit_py_plugins.attrs import attrs_block_plugin, attrs_plugin
from mdit_py_plugins.container import container_plugin
from mdit_py_plugins.deflist import deflist_plugin
from mdit_py_plugins.dollarmath import dollarmath_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.front_matter import front_matter_plugin
from mdit_py_plugins.tasklists import tasklists_plugin

from feynman import crossref, diagnostics

VIZ_NAME = "viz"
BOX_NAME = "box"
FIGURE_NAME = "figure"
STEP_NAME = "step"


def _viz_validate(params: str, *args) -> bool:
    """Match ``::: viz ...`` fences (the token becomes ``container_viz``)."""
    return params.strip().split(" ", 1)[0] == VIZ_NAME


def _step_validate(params: str, *args) -> bool:
    """Match ``::: step ...`` fences (the token becomes ``container_step``).

    A ``::: step`` is a scroll waypoint nested inside a ``:::viz {... scroll}``
    block; the outer viz uses more colons (``::::``) so the two nest. See
    :mod:`feynman.directives` for how a step's ``to=`` drives the visualisation.
    """
    return params.strip().split(" ", 1)[0] == STEP_NAME


def _box_validate(params: str, *args) -> bool:
    """Match ``::: box ...`` fences (the token becomes ``container_box``)."""
    return params.strip().split(" ", 1)[0] == BOX_NAME


def _figure_validate(params: str, *args) -> bool:
    """Match ``::: figure ...`` fences (token becomes ``container_figure``)."""
    return params.strip().split(" ", 1)[0] == FIGURE_NAME


def make_md() -> MarkdownIt:
    """Return the configured MarkdownIt instance used for all documents.

    The dialect is CommonMark plus a deliberate set of extensions: pipe tables,
    footnotes, definition lists, task lists, strikethrough and typographic
    replacements, on top of this project's own directives. ``typographer: True``
    only *permits* the replacement rules -- the ``commonmark`` preset leaves
    ``replacements``/``smartquotes`` disabled -- so they are enabled explicitly
    below or an author's ``--`` and ``"quotes"`` reach the reader verbatim.

    ``linkify`` is deliberately *not* enabled: it needs the optional
    ``linkify-it-py`` package, and ``enable("linkify")`` raises at import when it
    is absent. Bare URLs stay unlinked; an author writes ``<https://x>`` or a
    normal Markdown link.
    """
    md = (
        MarkdownIt("commonmark", {"html": True, "typographer": True})
        .enable("table")
        # ``--`` -> en dash, ``...`` -> ellipsis, and curly quotes. Disabled by
        # the commonmark preset, so passing ``typographer`` alone is not enough.
        .enable(["replacements", "smartquotes"])
        .enable("strikethrough")
        .use(footnote_plugin)
        .use(deflist_plugin)
        .use(tasklists_plugin)
        .use(front_matter_plugin)
        .use(dollarmath_plugin, double_inline=True)
        .use(attrs_plugin)
        # ``attrs_plugin`` is inline-only; on a table its ``{...}`` line would be
        # swallowed as a row. ``attrs_block_plugin`` attaches a ``{.class #id}``
        # line written *above* a block onto that block's opening token -- this is
        # how a table opts into ``.sortable`` styling and a ``#tbl-`` id.
        .use(attrs_block_plugin)
        .use(anchors_plugin, min_level=2, max_level=3, permalink=False)
        .use(container_plugin, VIZ_NAME, validate=_viz_validate)
        .use(container_plugin, BOX_NAME, validate=_box_validate)
        .use(container_plugin, FIGURE_NAME, validate=_figure_validate)
        .use(container_plugin, STEP_NAME, validate=_step_validate)
    )
    # Cross-referencing: `@label` references (an inline rule, before emphasis so
    # it claims the `@`) and explicit `{#sec-...}` heading ids (a core rule after
    # `anchor`, so an author's section label overrides the auto-slug).
    md.inline.ruler.before("emphasis", "xref", crossref.xref_rule)
    md.core.ruler.after("anchor", "section_id", crossref.section_id_rule)
    # Section numbers, computed once here and stamped on each heading token. The
    # theme CSS and the sidebar contents display this number rather than counting
    # headings again, so the three can never disagree.
    md.core.ruler.after("section_id", "section_number", crossref.number_headings)
    return md


@dataclass
class Document:
    """A parsed document: front-matter metadata plus the raw Markdown body."""

    meta: dict
    body: str


def meta_text(value: object) -> str:
    """Coerce a front-matter scalar (str/int/date) to a trimmed string.

    YAML gives us ``date: 2026-09-16`` as a ``datetime.date`` and ``version: 2``
    as an ``int``; templates want text either way. ``None`` (a key written with no
    value) becomes ``""``, which every template treats as absent.
    """
    return "" if value is None else str(value).strip()


def meta_list(value: object) -> list[str]:
    """Coerce a front-matter value to a list of trimmed strings.

    Authors write a list (``tags: [signals, dsp]``) or an inline string
    (``tags: signals, dsp`` -- and, historically for ``keywords``, a
    ``·``-separated run). All three read the same way here, so a template never
    has to care which spelling a document used. Empty entries are dropped, so a
    trailing comma cannot produce a blank chip.
    """
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        items = [meta_text(v) for v in value]
    else:
        # Split on the separators authors actually use, including the middot that
        # the `keywords` examples in this repo are written with.
        items = re.split(r"[,;·]", meta_text(value))
    return [item.strip() for item in items if item.strip()]


def split_front_matter(text: str, *, source: str | None = None) -> Document:
    """Split leading ``---`` YAML front matter from the Markdown body.

    The ``front_matter`` plugin recognises the block during rendering, but we
    also need the metadata (title, theme, ...) as a dict up front, so we parse
    and strip it here. Invalid YAML, or front matter that is not a mapping, is
    reported as a diagnostic (rather than silently swallowed) and treated as
    empty metadata so the build still produces a page. ``source`` is the document
    path, attached to the diagnostic.
    """
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            raw = text[3:end].strip()
            rest = text[end + 4 :]
            if rest.startswith("\n"):
                rest = rest[1:]
            try:
                meta = yaml.safe_load(raw) or {}
            except yaml.YAMLError as exc:
                # Surface the YAML parser's own line/column if it carries one.
                mark = getattr(exc, "problem_mark", None)
                line = mark.line + 1 if mark is not None else None
                diagnostics.warn(
                    f"invalid YAML front matter: {getattr(exc, 'problem', exc)}",
                    source=source,
                    line=line,
                )
                meta = {}
            if isinstance(meta, dict):
                return Document(meta=meta, body=rest)
            diagnostics.warn(
                f"front matter must be a mapping, got {type(meta).__name__}; ignoring it.",
                source=source,
            )
            return Document(meta={}, body=rest)
    return Document(meta={}, body=text)
