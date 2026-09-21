"""Unit tests for cross-referencing: labels, numbering and ``@`` references."""

from __future__ import annotations

from feynman.crossref import (
    SECTION_NUMBER_ATTR,
    collect_targets,
    dangling_ref_warnings,
    render_xref,
)
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


# --- section numbering follows the heading hierarchy -----------------------
# A section number is the one number in the system a reader can *check*: the
# theme prints it on the heading and the sidebar contents repeats it. So it has to
# mean position in the hierarchy, not "the Nth labelled section", which is what a
# flat counter gives and which drifts from the page the moment a document has a
# subsection or an unlabelled heading.
def test_heading_carries_its_number_for_the_page_to_display():
    # The number lives on the heading token, so the theme CSS and the sidebar
    # display it rather than counting headings for themselves. This attribute is
    # the contract between the three; everything else here follows from it.
    tokens = _parse("## A {#sec-a}\n### B {#sec-b}\n## C\n")
    numbers = [
        t.attrGet(SECTION_NUMBER_ATTR) for t in tokens if t.type == "heading_open"
    ]
    assert numbers == ["1", "1.1", "2"]


def test_reference_number_is_the_number_on_the_heading():
    # The assertion T7 is really about: a reference cannot say "Section 5" while
    # the heading it points at is printed "3.".
    tokens = _parse(
        "## Intro {#sec-intro}\n### Detail {#sec-detail}\n"
        "## Unlabelled-neighbour\n## Results {#sec-results}\n"
    )
    targets, _ = collect_targets(tokens)
    on_heading = {
        t.attrGet("id"): t.attrGet(SECTION_NUMBER_ATTR)
        for t in tokens
        if t.type == "heading_open"
    }
    for label, target in targets.items():
        # `reference_text` is "Section <n>"; the heading carries the bare "<n>".
        assert target.reference_text == f"Section {on_heading[label]}"


def test_subsections_number_hierarchically():
    tokens = _parse(
        "## Intro {#sec-intro}\n### Background {#sec-bg}\n"
        "### Prior {#sec-prior}\n## Method {#sec-method}\n"
    )
    targets, _ = collect_targets(tokens)
    assert targets["sec-intro"].reference_text == "Section 1"
    assert targets["sec-bg"].reference_text == "Section 1.1"
    assert targets["sec-prior"].reference_text == "Section 1.2"
    # The h2 after two h3s is the *second* section, not the fourth.
    assert targets["sec-method"].reference_text == "Section 2"


def test_unlabelled_headings_still_count():
    # A flat counter over labelled sections only called this "Section 1", while
    # every theme and the sidebar called it the third heading.
    tokens = _parse("## One\n\n## Two\n\n## Third {#sec-c}\n")
    targets, _ = collect_targets(tokens)
    assert targets["sec-c"].reference_text == "Section 3"


def test_deeper_levels_extend_the_path():
    tokens = _parse("## A {#sec-a}\n### B {#sec-b}\n#### C {#sec-c}\n")
    targets, _ = collect_targets(tokens)
    assert targets["sec-c"].reference_text == "Section 1.1.1"


def test_a_skipped_level_still_numbers():
    # An h4 directly under an h2 is bad structure, not a build error; it has to
    # land on a well-formed path rather than crash or collide.
    tokens = _parse("## A {#sec-a}\n#### D {#sec-d}\n")
    targets, _ = collect_targets(tokens)
    assert targets["sec-a"].reference_text == "Section 1"
    assert targets["sec-d"].reference_text == "Section 1.1.1"


def test_returning_to_a_shallower_level_resets_the_deeper_one():
    tokens = _parse(
        "## A {#sec-a}\n### A1 {#sec-a1}\n## B {#sec-b}\n### B1 {#sec-b1}\n"
    )
    targets, _ = collect_targets(tokens)
    assert targets["sec-b"].reference_text == "Section 2"
    assert targets["sec-b1"].reference_text == "Section 2.1"


def test_flat_document_numbering_is_unchanged():
    # The common case must read exactly as before: no dotted paths appear just
    # because the mechanism can produce them.
    tokens = _parse("## A {#sec-a}\n## B {#sec-b}\n## C {#sec-c}\n")
    targets, _ = collect_targets(tokens)
    assert [targets[k].reference_text for k in ("sec-a", "sec-b", "sec-c")] == [
        "Section 1",
        "Section 2",
        "Section 3",
    ]


def test_other_kinds_keep_flat_counters():
    # Only sections are hierarchical; a figure is "Figure 3" wherever it sits.
    tokens = _parse(
        "## A {#sec-a}\n\n::: viz {type=grid #viz-a}\nc\n:::\n\n"
        "### B {#sec-b}\n\n::: viz {type=grid #viz-b}\nc\n:::\n"
    )
    targets, _ = collect_targets(tokens)
    assert targets["viz-a"].reference_text == "Figure 1"
    assert targets["viz-b"].reference_text == "Figure 2"
    assert targets["viz-b"].path is None


def test_section_number_matches_the_hierarchy_in_a_book():
    # Chapter prefix composes with the path: chapter 3, section 1, subsection 1.
    tokens = _parse("## A {#sec-a}\n### B {#sec-b}\n## C {#sec-c}\n")
    targets, _ = collect_targets(tokens, chapter=3, chapter_url="ch3.html")
    assert targets["sec-a"].reference_text == "Section 3.1"
    assert targets["sec-b"].reference_text == "Section 3.1.1"
    assert targets["sec-c"].reference_text == "Section 3.2"


# --- book (chapter-aware) numbering ----------------------------------------
def test_chapter_numbering_reads_per_chapter():
    # With a chapter, numbering is "3.2": chapter number, then the local count.
    tokens = _parse("$$a$$ (eq-one)\n\n$$b$$ (eq-two)\n")
    targets, _ = collect_targets(tokens, chapter=3, chapter_url="ch3.html")
    assert targets["eq-two"].number == 2
    assert targets["eq-two"].reference_text == "Equation 3.2"
    assert targets["eq-two"].marker == "(3.2)"
    assert targets["eq-two"].chapter == 3
    assert targets["eq-two"].chapter_url == "ch3.html"


def test_no_chapter_is_flat_numbering():
    # The default (standalone) path is unchanged: a bare "Equation 1" / "(1)".
    tokens = _parse("$$a$$ (eq-one)\n")
    targets, _ = collect_targets(tokens)
    assert targets["eq-one"].reference_text == "Equation 1"
    assert targets["eq-one"].marker == "(1)"


def test_render_xref_cross_file_gets_url_prefix():
    tokens = _parse("$$a$$ (eq-one)\n")
    targets, _ = collect_targets(tokens, chapter=1, chapter_url="ch1.html")
    target = targets["eq-one"]
    # Rendered from a *different* page -> href carries the owning page's URL.
    from_other = render_xref(target, "eq-one", current_url="ch2.html")
    assert 'href="ch1.html#eq-one"' in from_other
    # Rendered from the *same* page -> bare anchor, no filename prefix.
    from_same = render_xref(target, "eq-one", current_url="ch1.html")
    assert 'href="#eq-one"' in from_same
