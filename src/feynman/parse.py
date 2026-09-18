"""Markdown parsing: MarkdownIt configuration and front-matter extraction.

We build one configured ``MarkdownIt`` instance with the plugins the authoring
format needs, and split YAML front matter off the top of a document. Rendering
of the resulting token stream lives in :mod:`feynman.render`.
"""

from __future__ import annotations

from dataclasses import dataclass

import yaml
from markdown_it import MarkdownIt
from mdit_py_plugins.anchors import anchors_plugin
from mdit_py_plugins.attrs import attrs_block_plugin, attrs_plugin
from mdit_py_plugins.container import container_plugin
from mdit_py_plugins.dollarmath import dollarmath_plugin
from mdit_py_plugins.front_matter import front_matter_plugin

from feynman import crossref, diagnostics

VIZ_NAME = "viz"
BOX_NAME = "box"
FIGURE_NAME = "figure"


def _viz_validate(params: str, *args) -> bool:
    """Match ``::: viz ...`` fences (the token becomes ``container_viz``)."""
    return params.strip().split(" ", 1)[0] == VIZ_NAME


def _box_validate(params: str, *args) -> bool:
    """Match ``::: box ...`` fences (the token becomes ``container_box``)."""
    return params.strip().split(" ", 1)[0] == BOX_NAME


def _figure_validate(params: str, *args) -> bool:
    """Match ``::: figure ...`` fences (token becomes ``container_figure``)."""
    return params.strip().split(" ", 1)[0] == FIGURE_NAME


def make_md() -> MarkdownIt:
    """Return the configured MarkdownIt instance used for all documents."""
    md = (
        MarkdownIt("commonmark", {"html": True, "linkify": True, "typographer": True})
        .enable("table")
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
    )
    # Cross-referencing: `@label` references (an inline rule, before emphasis so
    # it claims the `@`) and explicit `{#sec-...}` heading ids (a core rule after
    # `anchor`, so an author's section label overrides the auto-slug).
    md.inline.ruler.before("emphasis", "xref", crossref.xref_rule)
    md.core.ruler.after("anchor", "section_id", crossref.section_id_rule)
    return md


@dataclass
class Document:
    """A parsed document: front-matter metadata plus the raw Markdown body."""

    meta: dict
    body: str


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
