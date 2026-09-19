"""Tests for the Markdown dialect: the extensions beyond CommonMark.

Everything here is a feature an author will reach for and reasonably expect to
work, because it works in every other Markdown tool they have used. Each one was
either passed to ``MarkdownIt`` as an option that did nothing (``typographer``)
or not enabled at all, so the source leaked to the reader verbatim -- silently,
since a build cannot tell prose from unsupported syntax.

The rendered class names are asserted on purpose: ``theme.css`` styles these
exact selectors, so a plugin that changed its markup would otherwise drop the
styling without failing a test.
"""

from __future__ import annotations

import pytest

from feynman.render import render_document

_FRONT = "---\ntitle: T\n---\n\n"


def _body(markdown: str) -> str:
    return render_document(_FRONT + markdown)[1]


# --- typographic replacements (the `typographer` option) -------------------
def test_dashes_and_ellipsis_are_replaced():
    body = _body("An em dash --- and an en dash -- and an ellipsis...\n")
    assert "—" in body
    assert "–" in body
    assert "…" in body
    # Nothing left for the reader to see as source.
    assert "--" not in body
    assert "..." not in body


def test_quotes_are_curled():
    body = _body('He said "hello" and it\'s fine.\n')
    assert "“hello”" in body
    assert "it’s" in body
    assert '"hello"' not in body


def test_typography_never_touches_code():
    # The reason `replacements` is risky at all: a shell flag or a quoted string
    # inside code must survive byte-for-byte or the example stops working.
    body = _body('Run `cmd --flag "x"` please.\n')
    assert "--flag" in body
    assert "–" not in body
    assert "&quot;x&quot;" in body


def test_typography_never_touches_a_fence():
    body = _body('```\ncmd --flag "x" ...\n```\n')
    assert "--flag" in body
    assert "–" not in body and "…" not in body


# --- strikethrough ---------------------------------------------------------
def test_strikethrough():
    body = _body("This is ~~gone~~ text.\n")
    assert "<s>gone</s>" in body
    assert "~~" not in body


# --- footnotes -------------------------------------------------------------
def test_footnote_renders_ref_and_note():
    body = _body("Claim.[^1]\n\n[^1]: The note.\n")
    assert 'class="footnote-ref"' in body
    assert 'href="#fn1"' in body
    assert 'class="footnotes"' in body
    assert "The note." in body
    assert "[^1]" not in body


def test_footnote_rules_survive_the_renderer_swap():
    """``footnote_plugin`` binds its render rules to ``md.renderer``.

    ``render_document`` installs its own renderer afterwards, which used to drop
    those rules: the footnote tokens then fell through to ``renderToken`` and
    emitted empty ``<>`` and ``< />`` tags -- valid-looking output that shows the
    reader nothing. Assert the markup is real, not just that a tag appeared.
    """
    body = _body("Claim.[^a]\n\n[^a]: A note.\n")
    assert "<>" not in body
    assert "< />" not in body
    assert "<sup" in body and "<section" in body


def test_footnote_body_is_markdown():
    body = _body("Claim.[^x]\n\n[^x]: A *note* with `code`.\n")
    assert "<em>note</em>" in body
    assert "<code>code</code>" in body


def test_footnote_backref_present():
    body = _body("Claim.[^1]\n\n[^1]: The note.\n")
    # The return arrow is what makes a footnote navigable rather than a dead end.
    assert 'class="footnote-backref"' in body


# --- definition lists ------------------------------------------------------
def test_definition_list():
    body = _body("Term\n:   The definition.\n")
    assert "<dl>" in body
    assert "<dt>Term</dt>" in body
    assert "<dd>" in body and "The definition." in body


# --- task lists ------------------------------------------------------------
def test_task_list_renders_checkboxes():
    body = _body("- [ ] todo\n- [x] done\n")
    assert 'class="contains-task-list"' in body
    assert body.count('type="checkbox"') == 2
    assert 'checked="checked"' in body
    # Read-only: a static page must not imply the boxes can be ticked.
    assert body.count('disabled="disabled"') == 2
    assert "[ ]" not in body and "[x]" not in body


# --- tables still work (the one extension that predates this set) ----------
def test_pipe_table_still_parses():
    body = _body("| a | b |\n| - | - |\n| 1 | 2 |\n")
    assert "<table" in body and "<td>1</td>" in body


# --- the theme must style everything the parser can now emit ---------------
@pytest.mark.parametrize(
    "selector",
    [
        ".footnotes",
        ".footnotes-sep",
        ".footnote-ref",
        ".footnote-backref",
        ".footnote-item",
        ".task-list-item",
        "dl",
        "dt",
        "dd",
    ],
)
def test_theme_styles_the_new_markup(selector):
    """Enabling a plugin without styling it ships unstyled markup.

    All four themes layer on ``theme.css``, so the selectors belong there once
    rather than in each theme.
    """
    from importlib import resources

    css = resources.files("feynman.assets").joinpath("theme.css").read_text(
        encoding="utf-8"
    )
    assert selector in css
