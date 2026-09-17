"""Unit tests for cross-referencing: labels, numbering and ``@`` references."""

from __future__ import annotations

from feynman.crossref import collect_targets, dangling_ref_warnings
from feynman.parse import make_md


def _parse(md_text: str):
    return make_md().parse(md_text)


def test_each_kind_numbers_independently():
    tokens = _parse(
        "## First {#sec-a}\n\n"
        "$$x$$ (eq-one)\n\n"
        "## Second {#sec-b}\n\n"
        "$$y$$ (eq-two)\n\n"
        "```python {#lst-a}\np\n```\n"
    )
    targets, warnings = collect_targets(tokens)
    assert warnings == []
    assert targets["sec-a"].number == 1
    assert targets["sec-b"].number == 2
    assert targets["eq-one"].number == 1
    assert targets["eq-two"].number == 2
    assert targets["lst-a"].number == 1
    # Words come from the registry.
    assert targets["eq-one"].reference_text == "Equation 1"
    assert targets["sec-b"].reference_text == "Section 2"


def test_figures_and_viz_share_one_counter():
    # A cell figure, a viz, then an embedded :::figure -> Figure 1, 2, 3, all on
    # the one shared counter and reading as "Figure".
    tokens = _parse(
        "```{python}\n#| label: fig-a\np\n```\n\n"
        "::: viz {type=grid #viz-b}\ncap\n:::\n\n"
        "::: figure {src=d.svg #fig-c}\ncap\n:::\n"
    )
    targets, warnings = collect_targets(tokens)
    assert warnings == []
    assert targets["fig-a"].number == 1
    assert targets["viz-b"].number == 2
    assert targets["fig-c"].number == 3
    # All kinds read as "Figure".
    assert targets["viz-b"].reference_text == "Figure 2"
    assert targets["fig-c"].reference_text == "Figure 3"


def test_table_id_numbers_on_its_own_counter():
    # A `{#tbl-..}` block-attribute line above a pipe table joins a standalone
    # Table counter, independent of the figures/equations counters.
    tokens = _parse(
        "$$e$$ (eq-x)\n\n"
        "{#tbl-a}\n| A | B |\n|---|---|\n| 1 | 2 |\n\n"
        "{#tbl-b}\n| C | D |\n|---|---|\n| 3 | 4 |\n"
    )
    targets, warnings = collect_targets(tokens)
    assert warnings == []
    assert targets["tbl-a"].number == 1
    assert targets["tbl-b"].number == 2
    assert targets["eq-x"].number == 1  # separate counter
    assert targets["tbl-a"].reference_text == "Table 1"


def test_document_order_is_source_order():
    # A viz declared before an equation still numbers by position in the doc.
    tokens = _parse("::: viz {type=grid #viz-first}\nc\n:::\n\n$$z$$ (eq-after)\n")
    targets, _ = collect_targets(tokens)
    assert targets["viz-first"].number == 1
    assert targets["eq-after"].number == 1  # separate counter


def test_ref_tokenizes_and_skips_emails():
    tokens = _parse("See @fig-plot but not me@example.com nor list@fig.co here.")
    inline = next(t for t in tokens if t.type == "inline")
    xrefs = [c.content for c in inline.children if c.type == "xref"]
    assert xrefs == ["fig-plot"]


def test_unknown_prefix_is_a_plain_anchor_not_a_target():
    # A label whose prefix is not a cross-reference kind is a plain anchor id
    # (the pre-crossref `#| label:` / `{#id}` behaviour) -- silently skipped,
    # not numbered, and not warned about from the target side.
    tokens = _parse("```python {#my-block}\np\n```\n")
    targets, warnings = collect_targets(tokens)
    assert "my-block" not in targets
    assert warnings == []


def test_duplicate_label_first_wins_and_warns():
    tokens = _parse("$$a$$ (eq-dup)\n\n$$b$$ (eq-dup)\n")
    targets, warnings = collect_targets(tokens)
    assert targets["eq-dup"].number == 1
    assert any("duplicate" in w and "eq-dup" in w for w in warnings)


def test_forward_reference_resolves():
    # The reference appears before its target; the pre-pass must still find it.
    tokens = _parse("Refer to @eq-late.\n\n$$c$$ (eq-late)\n")
    targets, _ = collect_targets(tokens)
    assert "eq-late" in targets
    assert dangling_ref_warnings(tokens, targets) == []


def test_dangling_reference_warns_once():
    tokens = _parse("Both @fig-missing and again @fig-missing.\n")
    targets, _ = collect_targets(tokens)
    warnings = dangling_ref_warnings(tokens, targets)
    assert len(warnings) == 1
    assert "fig-missing" in warnings[0]


def test_section_label_overrides_autoslug():
    # An explicit {#sec-..} wins over the anchors plugin's text auto-slug, and
    # the marker text is stripped from the heading.
    tokens = _parse("## A Long Heading {#sec-intro}\n")
    heading = next(t for t in tokens if t.type == "heading_open")
    assert heading.attrGet("id") == "sec-intro"
    inline = next(t for t in tokens if t.type == "inline")
    assert inline.content == "A Long Heading"
