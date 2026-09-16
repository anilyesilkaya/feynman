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
from mdit_py_plugins.attrs import attrs_plugin
from mdit_py_plugins.container import container_plugin
from mdit_py_plugins.dollarmath import dollarmath_plugin
from mdit_py_plugins.front_matter import front_matter_plugin

from feynman import crossref

VIZ_NAME = "viz"
BOX_NAME = "box"


def _viz_validate(params: str, *args) -> bool:
    """Match ``::: viz ...`` fences (the token becomes ``container_viz``)."""
    return params.strip().split(" ", 1)[0] == VIZ_NAME


def _box_validate(params: str, *args) -> bool:
    """Match ``::: box ...`` fences (the token becomes ``container_box``)."""
    return params.strip().split(" ", 1)[0] == BOX_NAME


def make_md() -> MarkdownIt:
    """Return the configured MarkdownIt instance used for all documents."""
    md = (
        MarkdownIt("commonmark", {"html": True, "linkify": True, "typographer": True})
        .enable("table")
        .use(front_matter_plugin)
        .use(dollarmath_plugin, double_inline=True)
        .use(attrs_plugin)
        .use(anchors_plugin, min_level=2, max_level=3, permalink=False)
        .use(container_plugin, VIZ_NAME, validate=_viz_validate)
        .use(container_plugin, BOX_NAME, validate=_box_validate)
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


def split_front_matter(text: str) -> Document:
    """Split leading ``---`` YAML front matter from the Markdown body.

    The ``front_matter`` plugin recognises the block during rendering, but we
    also need the metadata (title, theme, ...) as a dict up front, so we parse
    and strip it here.
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
            except yaml.YAMLError:
                meta = {}
            if isinstance(meta, dict):
                return Document(meta=meta, body=rest)
    return Document(meta={}, body=text)
