"""Unit tests for table rendering: the figure wrapper, options and numbering.

Tables stay ordinary GFM pipe tables; a ``{...}`` block-attribute line *above* a
table opts into a scroll wrapper, option classes and a ``Table N`` caption. These
exercise the render pipeline (:func:`feynman.render.render_document`) end to end,
since the behaviour spans the parser (``attrs_block_plugin``), the cross-reference
pre-pass and the renderer overrides.
"""

from __future__ import annotations

from feynman.render import render_document

_SORTABLE = (
    "{.sortable .striped #tbl-x}\n"
    "| Name | Count |\n"
    "|:-----|------:|\n"
    "| Bob | 30 |\n"
    "| Al | 5 |\n"
)

_PLAIN = "| plain | table |\n|-------|-------|\n| a | b |\n"


def _body(md_text: str) -> str:
    _doc, body = render_document(md_text)
    return body


def test_table_gets_figure_wrapper_and_scroll_container():
    body = _body(_PLAIN)
    assert '<figure class="feynman-table-figure"' in body
    assert '<div class="feynman-table-scroll">' in body
    # Wrapper closes cleanly around the table.
    assert body.count("<table") == body.count("</table>") == 1


def test_bare_table_has_no_option_classes_or_caption():
    body = _body(_PLAIN)
    assert '<table class="feynman-table">' in body
    assert "feynman-table-sortable" not in body
    assert "feynman-table-caption" not in body


def test_option_line_is_not_swallowed_as_a_row():
    # The inline attrs plugin would render the `{...}` line as a table row; the
    # block plugin must instead attach it to the table, leaving no stray cell.
    body = _body(_SORTABLE)
    assert ".sortable" not in body
    assert "#tbl-x" not in body


def test_option_classes_are_namespaced_onto_the_table():
    body = _body(_SORTABLE)
    assert "feynman-table-sortable" in body
    assert "feynman-table-striped" in body


def test_labelled_table_is_numbered_and_anchored():
    body = _body(_SORTABLE)
    assert 'id="tbl-x"' in body
    assert "feynman-table-caption" in body
    assert "Table 1" in body


def test_reference_resolves_to_a_link():
    body = _body(_SORTABLE + "\nSee @tbl-x for values.\n")
    assert '<a class="feynman-xref" href="#tbl-x">Table 1</a>' in body


def test_column_alignment_is_preserved():
    # Alignment comes from the `:---:` markers via markdown-it's default cell
    # rendering, which we deliberately leave untouched.
    body = _body(_SORTABLE)
    assert 'style="text-align:right"' in body
    assert 'style="text-align:left"' in body


# --- caption text ----------------------------------------------------------
# A table could be numbered ("Table 1") but not *described*. Every other figure
# kind takes caption prose from its directive body; a table cannot, because a line
# inside it parses as a row -- so the text rides in on `caption="..."`.
_CAPTIONED = (
    '{#tbl-c caption="Throughput by **batch size**, see @sec-setup"}\n'
    "| Batch | Rate |\n"
    "|------:|-----:|\n"
    "| 1 | 20 |\n"
    "\n## Setup {#sec-setup}\n"
)


def test_caption_text_is_rendered_with_the_number():
    body = _body(_CAPTIONED)
    assert "feynman-table-caption" in body
    assert "Table 1" in body
    assert "Throughput by" in body


def test_caption_text_is_markdown_not_literal():
    body = _body(_CAPTIONED)
    assert "<strong>batch size</strong>" in body
    assert "**batch size**" not in body


def test_caption_resolves_a_cross_reference():
    # The same `@ref` machinery as prose: a caption is where a "see Section N"
    # most often belongs.
    body = _body(_CAPTIONED)
    assert '<a class="feynman-xref" href="#sec-setup">Section 1</a>' in body


def test_caption_renders_math_and_code():
    body = _body(
        '{#tbl-m caption="Cost is $n^2$ per `head`"}\n| a |\n| - |\n| 1 |\n'
    )
    assert "<math" in body
    assert "<code>head</code>" in body


def test_caption_without_an_id_still_describes_the_table():
    # Describing a table and numbering it are separate choices; a caption alone
    # must not require inventing a `#tbl-` label nobody references.
    body = _body('{caption="Not numbered, just described"}\n| a |\n| - |\n| 1 |\n')
    assert "feynman-table-caption" in body
    assert "Not numbered, just described" in body
    assert "feynman-fig-label" not in body
    # No id was requested, so the figure stays unanchored.
    assert "<figure class=\"feynman-table-figure\">" in body


def test_number_only_caption_has_no_stray_separator():
    body = _body(_SORTABLE)
    assert "Table 1</span>." not in body


def test_empty_caption_is_ignored():
    body = _body('{#tbl-e caption=""}\n| a |\n| - |\n| 1 |\n')
    # Still numbered, but no dangling separator from an empty string.
    assert "Table 1" in body
    assert "Table 1</span>." not in body


def test_caption_is_not_swallowed_as_a_row():
    body = _body(_CAPTIONED)
    assert "caption=" not in body
    assert body.count("<tr") == 2  # header row + one body row
