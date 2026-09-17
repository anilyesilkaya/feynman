"""End-to-end pipeline regression test.

Builds the demo document and asserts that every stage left its fingerprint in
the output HTML: MathML, highlighted static code, an executed cell's textual
output, an inline figure (SVG or a PNG data URI), and the viz component.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from feynman.build import build_document

REPO = Path(__file__).resolve().parents[1]
DEMO = REPO / "examples" / "demo.md"


@pytest.fixture(scope="module")
def built_html(tmp_path_factory) -> str:
    out = tmp_path_factory.mktemp("site")
    html_path = build_document(DEMO, out)
    assert html_path.exists()
    # The runtime assets must be copied alongside the page.
    assert (out / "theme.css").exists()
    assert (out / "feynman.js").exists()
    assert (out / "pygments.css").exists()
    return html_path.read_text(encoding="utf-8")


def test_math_is_mathml(built_html):
    assert "<math" in built_html
    assert 'display="block"' in built_html  # the display equation


def test_static_code_is_highlighted(built_html):
    assert 'class="highlight"' in built_html
    assert "feynman-code" in built_html


def test_executed_cell_output_present(built_html):
    # printed stdout from the first executable cell
    assert "this page exercises 4 capabilities" in built_html
    assert "feynman-cell-output" in built_html


def test_inline_figure_present(built_html):
    # matplotlib captured as inline SVG (preferred) or PNG data URI (fallback)
    assert ("<svg" in built_html) or ("data:image/png;base64" in built_html)


def test_echo_false_hides_source(built_html):
    # The plotting cell uses #| echo: false, so its source must be absent
    # even though its figure is present. Pygments would tokenise the source
    # into spans, so check for a token that only appears in the hidden cell.
    assert "invert_yaxis" not in built_html


def test_viz_component_present(built_html):
    assert "<feynman-viz" in built_html
    assert "feynman-viz-spec" in built_html
    assert '"pattern":"diagonal"' in built_html
    # The demo exercises every registered viz type, including the Fourier
    # synthesiser and the Galton board.
    assert '"type":"fourier"' in built_html
    assert '"type":"galton"' in built_html


def test_callout_boxes_present(built_html):
    # The demo ships one box of each variant; a titled box gets a header row
    # and a titleless one is still marked by its icon.
    assert 'class="feynman-box feynman-box-info"' in built_html
    assert 'class="feynman-box feynman-box-warning"' in built_html
    assert 'class="feynman-box feynman-box-error"' in built_html
    assert "feynman-box-title" in built_html  # the titled boxes
    assert "Don&#x27;t do that" in built_html  # error box title, escaped


def test_embedded_figure_present(built_html):
    # The demo embeds an external SVG via :::figure with theme=auto. The SVG is
    # inlined (not an <img>), the XML prolog is stripped, ink strokes are mapped
    # to currentColor and the chromatic fill is left untouched. Scope the checks
    # to this figure's markup -- a matplotlib cell figure carries its own prolog.
    assert 'class="feynman-figure"' in built_html
    start = built_html.index('class="feynman-figure"')
    figure = built_html[start : built_html.index("</figure>", start)]
    assert "feynman-figure-svg feynman-figure-themed" in figure
    assert "<?xml" not in figure  # the directive strips the prolog before inlining
    assert "currentColor" in figure  # ink stroke recoloured
    assert "#88ccee" in figure  # chromatic fill preserved


def test_equation_panel_has_copy_button(built_html):
    # Display equations render inside a panel with a copy-the-LaTeX button that
    # carries the raw source in data-latex.
    assert "equation-panel" in built_html
    assert "equation-copy" in built_html
    assert "data-latex" in built_html


def test_code_cards_have_copy_toolbar(built_html):
    # Both static and executed code cards get a toolbar with a copy button.
    assert "code-toolbar" in built_html
    assert "copy-button" in built_html


def test_cross_references_resolve(built_html):
    # References render as numbered links to their targets' anchors, and the
    # targets carry the matching ids. The demo labels an equation, a listing,
    # a figure cell, several viz blocks and its sections.
    assert 'class="feynman-xref"' in built_html
    assert 'href="#eq-fourier"' in built_html
    assert 'id="eq-fourier"' in built_html
    assert 'href="#lst-greet"' in built_html
    assert 'id="lst-greet"' in built_html
    # The shared figure counter spans the cell figure, the viz blocks and the
    # embedded :::figure.
    assert 'href="#fig-lengths"' in built_html
    assert 'href="#viz-grid"' in built_html
    assert 'id="viz-grid"' in built_html
    assert 'href="#fig-sets"' in built_html
    assert 'id="fig-sets"' in built_html
    assert "Equation 1" in built_html
    assert "Figure 1" in built_html


def test_no_broken_references_in_demo(built_html):
    # The demo must not ship any dangling references.
    assert "feynman-xref-broken" not in built_html


def test_single_doc_has_no_home_link(built_html):
    # The Home link is a collection-only feature; a standalone build omits it.
    assert 'class="home-link"' not in built_html
