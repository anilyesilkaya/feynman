"""Tests for ``feynman book`` — the ordered, interconnected book builder.

Covers reading order (``order:`` then filename fallback), per-chapter numbering
(Figure 3.2), cross-chapter reference resolution (a ``@`` into another chapter
links to ``that-chapter.html#anchor``), prev/next navigation and its endpoints,
the spanning contents page, draft exclusion, and a regression guard that a
single standalone document still numbers plainly (Figure 1, not 1.1).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from feynman import cli, collection
from feynman.build import build_document

REPO = Path(__file__).resolve().parents[1]
EXAMPLES = REPO / "examples"


def _chapter(title, *, order=None, body="Prose.", **meta):
    fm = {"title": title, "style": "book"}
    if order is not None:
        fm["order"] = order
    fm.update(meta)
    front = "\n".join(f"{k}: {v}" for k, v in fm.items())
    return f"---\n{front}\n---\n\n{body}\n"


@pytest.fixture
def book(tmp_path):
    src = tmp_path / "chapters"
    src.mkdir()
    # Files are named out of reading order on purpose: `order:` must win.
    (src / "zeta.md").write_text(
        _chapter(
            "Zeta",
            order=1,
            body="## Start {#sec-start}\n\n$$ a=b $$ (eq-one)\n\nSee @sec-mid.",
        ),
        encoding="utf-8",
    )
    (src / "alpha.md").write_text(
        _chapter(
            "Alpha",
            order=2,
            body="## Middle {#sec-mid}\n\nRecall @eq-one and @sec-start.",
        ),
        encoding="utf-8",
    )
    (src / "draft.md").write_text(
        _chapter("Draft", order=3, draft="true", body="Hidden."),
        encoding="utf-8",
    )
    out = tmp_path / "site"
    result = collection.build_book(src, out, title="My Book")
    return src, out, result


# --- ordering & numbering --------------------------------------------------
def test_orders_by_order_key_not_filename(book):
    _, _, result = book
    # zeta (order 1) is chapter 1 despite sorting last alphabetically.
    assert [p.name for p in result.pages] == ["zeta.html", "alpha.html"]


def test_drafts_excluded(book):
    _, out, result = book
    assert len(result.skipped) == 1
    assert not (out / "draft.html").exists()


def test_per_chapter_numbering(book):
    _, out, _ = book
    zeta = (out / "zeta.html").read_text(encoding="utf-8")
    # Equation in chapter 1 is numbered 1.1, not a flat 1.
    assert "(1.1)" in zeta


def test_chapter_folio_present(book):
    _, out, _ = book
    alpha = (out / "alpha.html").read_text(encoding="utf-8")
    assert "Chapter 2" in alpha
    assert 'data-style="book"' in alpha


# --- cross-chapter references ----------------------------------------------
def test_cross_chapter_reference_links_to_other_page(book):
    _, out, _ = book
    # alpha (ch2) references eq-one and sec-start, both owned by zeta (ch1).
    alpha = (out / "alpha.html").read_text(encoding="utf-8")
    assert 'href="zeta.html#eq-one">Equation 1.1' in alpha
    assert 'href="zeta.html#sec-start">Section 1.1' in alpha


def test_same_page_reference_stays_bare(book):
    _, out, _ = book
    # zeta (ch1) references sec-mid, owned by alpha (ch2) -> cross-page.
    zeta = (out / "zeta.html").read_text(encoding="utf-8")
    assert 'href="alpha.html#sec-mid">Section 2.1' in zeta
    # But nothing on zeta links to its own anchors with a filename prefix.
    assert 'href="zeta.html#' not in zeta


def test_no_broken_references(book):
    _, out, _ = book
    for name in ("zeta.html", "alpha.html"):
        assert "feynman-xref-broken" not in (out / name).read_text(encoding="utf-8")


def test_dangling_reference_warns_against_whole_book(tmp_path, capsys):
    # A reference resolving to no target *anywhere in the book* is dangling and
    # must warn, even though it might have resolved in another chapter.
    src = tmp_path / "chapters"
    src.mkdir()
    (src / "a.md").write_text(
        _chapter("A", order=1, body="See @fig-nowhere."), encoding="utf-8"
    )
    (src / "b.md").write_text(
        _chapter("B", order=2, body="## Real {#sec-real}\n"), encoding="utf-8"
    )
    collection.build_book(src, tmp_path / "site")
    err = capsys.readouterr().err
    assert "fig-nowhere" in err and "a.md" in err


# --- navigation ------------------------------------------------------------
def test_prev_next_endpoints(book):
    _, out, _ = book
    first = (out / "zeta.html").read_text(encoding="utf-8")
    last = (out / "alpha.html").read_text(encoding="utf-8")
    # First chapter has no previous; last has no next.
    assert "pager-prev" not in first
    assert "pager-next" not in last
    # First links forward to the second; second links back to the first.
    assert 'rel="next"' in first and "alpha.html" in first
    assert 'rel="prev"' in last and "zeta.html" in last


def test_chapters_link_home_to_contents(book):
    _, out, _ = book
    zeta = (out / "zeta.html").read_text(encoding="utf-8")
    assert f'href="{collection.CONTENTS_NAME}"' in zeta


# --- contents page ---------------------------------------------------------
def test_contents_lists_chapters_in_order(book):
    _, out, result = book
    assert result.contents == out / collection.CONTENTS_NAME
    html = (out / collection.CONTENTS_NAME).read_text(encoding="utf-8")
    assert html.index("Zeta") < html.index("Alpha")
    assert "My Book" in html


def test_shared_assets_written(book):
    _, out, _ = book
    for name in ("feynman.js", "theme.css", "theme-book.css", "pygments.css"):
        assert (out / name).exists(), name


# --- regression: standalone numbering unaffected ---------------------------
def test_standalone_document_numbers_flat(tmp_path):
    src = tmp_path / "solo.md"
    src.write_text(
        _chapter("Solo", body="$$ a=b $$ (eq-one)\n\nSee @eq-one."),
        encoding="utf-8",
    )
    html = build_document(src, tmp_path / "out").read_text(encoding="utf-8")
    # No chapter context: a plain "Equation 1" / "(1)", never "1.1".
    assert "(1)" in html and "(1.1)" not in html
    assert ">Equation 1<" in html


# --- CLI wiring ------------------------------------------------------------
def test_cli_book_reports(tmp_path, capsys):
    src = tmp_path / "chapters"
    src.mkdir()
    (src / "one.md").write_text(_chapter("One", order=1), encoding="utf-8")
    code = cli.main(["book", str(src), "-o", str(tmp_path / "site")])
    assert code == 0
    out = capsys.readouterr().out
    assert "built 1 chapter(s)" in out
    assert "contents page:" in out


def test_cli_book_missing_dir(tmp_path, capsys):
    code = cli.main(["book", str(tmp_path / "nope"), "-o", str(tmp_path / "s")])
    assert code == 2
    assert "no such directory" in capsys.readouterr().err


# --- example book builds & cross-links -------------------------------------
def test_example_book_builds_and_crosslinks(tmp_path):
    out = tmp_path / "site"
    result = collection.build_book(EXAMPLES / "book", out, title="Signals")
    assert len(result.pages) == 3
    freq = (out / "02-frequency.html").read_text(encoding="utf-8")
    # A reference reaching back into chapter 1 and forward into chapter 3.
    assert 'href="01-foundations.html#eq-euler">Equation 1.1' in freq
    assert 'href="03-synthesis.html#sec-synthesis"' in freq
    for name in result.pages:
        assert "feynman-xref-broken" not in name.read_text(encoding="utf-8")
