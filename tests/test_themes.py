"""Built-in theme selection: the ``style`` front-matter key.

Covers theme resolution (default, known, unknown-with-warning) and the
end-to-end build: the right template, the right stacked CSS layers as sidecars
or inlined, and the theme-specific chrome each front matter drives.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from feynman.build import build_document
from feynman.themes import DEFAULT_THEME, THEMES, resolve

REPO = Path(__file__).resolve().parents[1]
EXAMPLES = REPO / "examples"


def _write(tmp_path, front_matter: str, body: str = "\n## Section {#sec-a}\n\nText.\n"):
    src = tmp_path / "doc.md"
    src.write_text(f"---\n{front_matter}\n---\n{body}", encoding="utf-8")
    return src


# --- resolve() -------------------------------------------------------------


def test_missing_style_resolves_to_default():
    theme, warning = resolve(None)
    assert theme.name == DEFAULT_THEME
    assert warning is None


def test_known_style_resolves_without_warning():
    theme, warning = resolve("article")
    assert theme.name == "article"
    assert warning is None


def test_unknown_style_falls_back_with_warning():
    theme, warning = resolve("nope")
    assert theme.name == DEFAULT_THEME
    assert warning is not None and "nope" in warning


# --- build wiring ----------------------------------------------------------


def test_default_build_uses_notebook_and_base_css_only(tmp_path):
    src = _write(tmp_path, "title: T")
    out = tmp_path / "out"
    html = build_document(src, out).read_text(encoding="utf-8")
    assert 'data-style="notebook"' in html
    # Only the base stylesheet ships; no theme layer sidecar exists.
    assert (out / "theme.css").exists()
    assert not list(out.glob("theme-*.css"))


def test_unknown_style_warns_on_build(tmp_path, capsys):
    src = _write(tmp_path, "title: T\nstyle: bogus")
    build_document(src, tmp_path / "out")
    assert "bogus" in capsys.readouterr().err


@pytest.mark.parametrize("name", [n for n in THEMES if THEMES[n].styles])
def test_theme_layers_ship_as_sidecars(tmp_path, name):
    src = _write(tmp_path, f"title: T\nstyle: {name}")
    out = tmp_path / "out"
    html = build_document(src, out).read_text(encoding="utf-8")
    assert f'data-style="{name}"' in html
    # Base first, then each theme layer -- all present as sidecars and links.
    assert (out / "theme.css").exists()
    for layer in THEMES[name].styles:
        assert (out / layer).exists()
        assert f'href="{layer}"' in html


def test_article_chrome_from_front_matter(tmp_path):
    src = _write(
        tmp_path,
        "title: Paper\nstyle: article\n"
        "authors: A. Author\ndate: 2026-09-16\nversion: '2.0'\n"
        "abstract: A dense summary.\nkeywords: a · b",
    )
    html = build_document(src, tmp_path / "out").read_text(encoding="utf-8")
    assert 'class="abstract"' in html
    assert "A dense summary." in html
    assert "A. Author" in html
    assert "Version 2.0" in html
    # A paper labels its tags "Keywords"; same chips, relabelled.
    assert "Keywords:" in html
    assert '<li class="doc-tag">a</li>' in html


def test_article_omits_optional_chrome_when_absent(tmp_path):
    src = _write(tmp_path, "title: Paper\nstyle: article")
    html = build_document(src, tmp_path / "out").read_text(encoding="utf-8")
    # No abstract block and no meta row when the keys are absent.
    assert 'class="abstract"' not in html
    assert "doc-meta" not in html
    assert 'class="article-meta"' not in html


# --- the shared credits/tags unit ------------------------------------------
# `meta.html.j2` defines the credit row and the tag chips once, and every theme
# imports it. So front matter drives the same markup everywhere: a theme chooses
# where the unit goes and how it looks, never what it contains or whether a key
# is understood. These tests pin that a *new* theme gets it for free.
_CREDITED = (
    "title: T\nauthors: A. Author\ndate: 2026-09-16\nversion: '2.0'\n"
    "tags: [signals, dsp]"
)


@pytest.mark.parametrize("name", list(THEMES))
def test_credits_and_tags_render_in_every_theme(tmp_path, name):
    src = _write(tmp_path, f"{_CREDITED}\nstyle: {name}")
    html = build_document(src, tmp_path / "out").read_text(encoding="utf-8")
    assert "A. Author" in html
    assert "2026-09-16" in html
    assert '<li class="doc-tag">signals</li>' in html
    # Each theme tags the shared unit with its own variant class for styling.
    assert "doc-meta" in html


@pytest.mark.parametrize("name", list(THEMES))
def test_no_meta_markup_when_front_matter_is_bare(tmp_path, name):
    # The macros are called unconditionally, so they must emit nothing at all
    # rather than an empty row -- otherwise every untitled page grows a stray box.
    src = _write(tmp_path, f"title: T\nstyle: {name}")
    html = build_document(src, tmp_path / "out").read_text(encoding="utf-8")
    assert "doc-meta" not in html
    assert "doc-tag" not in html


@pytest.mark.parametrize(
    "front_matter",
    [
        "tags: [signals, dsp]",       # a YAML list
        "tags: signals, dsp",         # one comma-separated string
        "keywords: signals · dsp",    # the older middot spelling
    ],
)
def test_tag_spellings_all_produce_the_same_chips(tmp_path, front_matter):
    src = _write(tmp_path, f"title: T\n{front_matter}")
    html = build_document(src, tmp_path / "out").read_text(encoding="utf-8")
    assert '<li class="doc-tag">signals</li>' in html
    assert '<li class="doc-tag">dsp</li>' in html


def test_version_and_date_survive_yaml_typing(tmp_path):
    # Unquoted, YAML hands back `datetime.date` and `int`; both must print.
    src = _write(tmp_path, "title: T\ndate: 2026-09-16\nversion: 2")
    html = build_document(src, tmp_path / "out").read_text(encoding="utf-8")
    assert "2026-09-16" in html
    assert "Version 2" in html


def test_partial_credits_omit_only_the_missing_fields(tmp_path):
    src = _write(tmp_path, "title: T\ndate: 2026-09-16")
    html = build_document(src, tmp_path / "out").read_text(encoding="utf-8")
    assert "doc-meta-date" in html
    assert "doc-meta-authors" not in html
    assert "doc-meta-version" not in html


def test_book_style_resolves_and_builds(tmp_path):
    theme, warning = resolve("book")
    assert theme.name == "book" and warning is None
    src = _write(tmp_path, "title: Chapter\nstyle: book")
    out = tmp_path / "out"
    html = build_document(src, out).read_text(encoding="utf-8")
    assert 'data-style="book"' in html
    assert (out / "theme-book.css").exists()
    # A standalone book page has no chapter number, so no folio.
    assert "chapter-folio" not in html


def test_spec_badges_and_stable_tint(tmp_path):
    src = _write(
        tmp_path,
        "title: Ref\nstyle: spec\nbadges: [Stable, Beta]",
    )
    html = build_document(src, tmp_path / "out").read_text(encoding="utf-8")
    assert 'class="spec-badges"' in html
    assert 'class="badge stable"' in html  # "Stable" gets the success tint
    assert ">Stable<" in html and ">Beta<" in html


def test_theme_layers_inlined_in_single_file(tmp_path):
    src = _write(tmp_path, "title: T\nstyle: article")
    out = tmp_path / "out"
    html = build_document(src, out, inline=True).read_text(encoding="utf-8")
    # Single self-contained file: no sidecars, styles embedded.
    assert [p.name for p in out.iterdir()] == ["doc.html"]
    assert 'href="theme.css"' not in html
    # Both base and layer are present inline (a token from each).
    assert "--paper" in html  # from theme.css
    assert "article-layout" in html  # from theme-article.css


# --- section numbers: one authority, displayed in three places -------------
# The number on a heading, the number a `@sec-` reference renders and the number
# the sidebar contents shows have to be the same string. They are, because only
# one of them is *computed*: the build stamps `data-section-number` on the heading,
# the theme CSS prints that attribute with `content: attr(...)`, and feynman.js
# reads it for the sidebar. These tests guard that wiring; the numbering itself is
# covered in test_crossref.py.
_NESTED = (
    "\n## Intro {#sec-intro}\n\nSee @sec-detail and @sec-last.\n"
    "\n### Detail {#sec-detail}\n\nText.\n"
    "\n## Unlabelled neighbour\n\nText.\n"
    "\n## Last {#sec-last}\n\nText.\n"
)


@pytest.mark.parametrize("name", list(THEMES))
def test_headings_carry_their_number_in_every_theme(tmp_path, name):
    # The attribute ships regardless of theme: a theme decides whether to *print*
    # a number, never what it is. So the sidebar agrees with the prose everywhere,
    # even where no number appears on the heading itself.
    src = _write(tmp_path, f"title: T\nstyle: {name}", _NESTED)
    html = build_document(src, tmp_path / "out").read_text(encoding="utf-8")
    # The unlabelled h2 is section 2, so "Last" is 3 -- not 2, which is what a
    # counter over labelled sections only would have said.
    for label, number in (("sec-intro", "1"), ("sec-detail", "1.1"), ("sec-last", "3")):
        assert f'id="{label}" data-section-number="{number}"' in html
    # And the references in the prose quote those same numbers back.
    assert 'href="#sec-detail">Section 1.1</a>' in html
    assert 'href="#sec-last">Section 3</a>' in html


def test_article_prints_the_stamped_number_not_its_own_count(tmp_path):
    # The article theme is the one that shows numbers on headings. It must print
    # the attribute rather than run a CSS counter, which counted only the headings
    # it had rules for -- so a document with subsections showed "3." on a heading
    # the prose called "Section 5".
    src = _write(tmp_path, "title: Paper\nstyle: article", _NESTED)
    out = tmp_path / "out"
    build_document(src, out)
    css = (out / "theme-article.css").read_text(encoding="utf-8")
    assert "content: attr(data-section-number)" in css
    assert "counter-increment" not in css


def test_sidebar_reads_the_stamped_number(tmp_path):
    src = _write(tmp_path, "title: T", _NESTED)
    out = tmp_path / "out"
    build_document(src, out)
    js = (out / "feynman.js").read_text(encoding="utf-8")
    # The contents list is driven by the attribute, so it cannot drift from it.
    assert "[id][data-section-number]" in js
    assert "h.dataset.sectionNumber" in js


# --- example docs: the three themes build together and cross-link ----------


def test_example_theme_docs_build_and_crosslink(tmp_path):
    # demo (notebook), article and spec build into one folder, share the runtime
    # assets, and link to each other via relative <name>.html hrefs.
    out = tmp_path / "site"
    styles = {}
    for name in ("demo", "article", "spec"):
        html = build_document(EXAMPLES / f"{name}.md", out).read_text(encoding="utf-8")
        styles[name] = html
        assert "feynman-xref-broken" not in html  # no dangling references

    assert 'data-style="notebook"' in styles["demo"]
    assert 'data-style="article"' in styles["article"]
    assert 'data-style="spec"' in styles["spec"]

    # demo points at both sibling themes; each sibling points back at demo.
    assert 'href="article.html"' in styles["demo"]
    assert 'href="spec.html"' in styles["demo"]
    assert 'href="demo.html"' in styles["article"]
    assert 'href="demo.html"' in styles["spec"]

    # The shared and layered stylesheets all land in the one output folder.
    for asset in ("theme.css", "theme-article.css", "theme-spec.css", "feynman.js"):
        assert (out / asset).exists()
