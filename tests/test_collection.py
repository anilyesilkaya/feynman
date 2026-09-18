"""Tests for ``feynman build-all`` — the multi-document / search builder.

Covers the folder walk, the emitted ``search-index.json`` and ``index.html``
listing, plain-text extraction (viz JSON must not leak into the index), draft
exclusion, date-descending ordering, and the shared sidecar assets.
"""

from __future__ import annotations

import json

import pytest

from feynman import cli, collection
from feynman.build import SEARCH_JS


# --- plain-text extraction -------------------------------------------------
def test_html_to_text_strips_tags_and_scripts():
    html = (
        "<h2>Title</h2><p>Hello <em>world</em>.</p>"
        '<script type="application/json">{"type":"fourier"}</script>'
        "<style>.x{color:red}</style>"
    )
    text = collection.html_to_text(html)
    assert "Hello world ." in text.replace("  ", " ") or "Hello world" in text
    assert "fourier" not in text  # viz payload excluded
    assert "color:red" not in text  # style excluded


def test_html_to_text_collapses_whitespace():
    assert collection.html_to_text("<p>a\n\n  b\t c</p>") == "a b c"


# --- draft detection -------------------------------------------------------
@pytest.mark.parametrize(
    "value, expected",
    [(True, True), ("true", True), ("yes", True), ("1", True),
     (False, False), ("false", False), ("", False), (None, False)],
)
def test_is_draft(value, expected):
    assert collection._is_draft({"draft": value} if value is not None else {}) is expected


# --- the build -------------------------------------------------------------
def _post(title, *, body="Some prose here.", **meta):
    fm = "\n".join(f"{k}: {v}" for k, v in {"title": title, **meta}.items())
    return f"---\n{fm}\n---\n\n{body}\n"


@pytest.fixture
def site(tmp_path):
    src = tmp_path / "posts"
    src.mkdir()
    (src / "alpha.md").write_text(
        _post("Alpha", date="2026-01-02", keywords="signals", body="Wiener filtering."),
        encoding="utf-8",
    )
    (src / "beta.md").write_text(
        _post("Beta", date="2026-05-09", body="Galton board and quincunx."),
        encoding="utf-8",
    )
    (src / "gamma.md").write_text(
        _post("Gamma", body="No date here."), encoding="utf-8"
    )
    (src / "secret.md").write_text(
        _post("Secret", draft="true", body="Hidden."), encoding="utf-8"
    )
    out = tmp_path / "site"
    result = collection.build_all(src, out, title="My Blog")
    return src, out, result


def test_builds_one_page_per_nondraft(site):
    _, out, result = site
    assert len(result.pages) == 3
    assert {p.name for p in result.pages} == {"alpha.html", "beta.html", "gamma.html"}
    assert len(result.skipped) == 1
    assert not (out / "secret.html").exists()


def test_emits_index_and_listing(site):
    _, out, result = site
    assert (out / collection.SEARCH_INDEX_NAME).exists()
    assert (out / collection.LISTING_NAME).exists()
    assert result.index == out / collection.SEARCH_INDEX_NAME
    assert result.listing == out / collection.LISTING_NAME


def test_search_index_shape_and_content(site):
    _, out, _ = site
    data = json.loads((out / collection.SEARCH_INDEX_NAME).read_text(encoding="utf-8"))
    assert data["generator"] == "feynman"
    assert "text" in data["fields"]
    docs = data["docs"]
    assert len(docs) == 3
    assert all("id" in d and "url" in d for d in docs)
    alpha = next(d for d in docs if d["url"] == "alpha.html")
    assert "Wiener" in alpha["text"]
    assert alpha["keywords"] == "signals"
    assert alpha["date"] == "2026-01-02"
    # The draft is absent from the index.
    assert all(d["title"] != "Secret" for d in docs)


def test_listing_orders_dated_desc_then_undated(site):
    _, out, _ = site
    html = (out / collection.LISTING_NAME).read_text(encoding="utf-8")
    # beta (2026-05) before alpha (2026-01) before gamma (no date).
    assert html.index("Beta") < html.index("Alpha") < html.index("Gamma")


def test_listing_lists_all_posts_without_js(site):
    _, out, _ = site
    html = (out / collection.LISTING_NAME).read_text(encoding="utf-8")
    for title in ("Alpha", "Beta", "Gamma"):
        assert f">{title}<" in html
    assert "data-feynman-search" in html
    assert 'href="alpha.html"' in html


def test_posts_have_home_link_to_listing(site):
    _, out, _ = site
    post = (out / "alpha.html").read_text(encoding="utf-8")
    assert 'class="home-link"' in post
    assert f'href="{collection.LISTING_NAME}"' in post


def test_listing_has_no_home_link(site):
    # The listing IS home, so it must not link to itself in the header.
    _, out, _ = site
    html = (out / collection.LISTING_NAME).read_text(encoding="utf-8")
    assert 'class="home-link"' not in html


def test_shared_assets_written_once(site):
    _, out, _ = site
    for name in ("feynman.js", "theme.css", "pygments.css", SEARCH_JS):
        assert (out / name).exists(), name


def test_empty_dir_builds_nothing(tmp_path):
    src = tmp_path / "empty"
    src.mkdir()
    result = collection.build_all(src, tmp_path / "out")
    assert result.pages == []
    # A listing still renders (an empty collection), so the page exists.
    assert result.listing.exists()


# --- book auto-detection ---------------------------------------------------
@pytest.fixture
def site_with_book(tmp_path):
    src = tmp_path / "posts"
    src.mkdir()
    (src / "alpha.md").write_text(_post("Alpha", date="2026-01-02"), encoding="utf-8")
    # A subfolder of chapters is auto-detected as a book.
    book = src / "my-book"
    book.mkdir()
    (book / "01.md").write_text(
        _post("Chapter One", body="## Start {#sec-start}\n\nProse."),
        encoding="utf-8",
    )
    (book / "02.md").write_text(
        _post("Chapter Two", body="Recall @sec-start."), encoding="utf-8"
    )
    out = tmp_path / "site"
    result = collection.build_all(src, out, title="Site")
    return src, out, result


def test_book_built_into_subfolder(site_with_book):
    _, out, result = site_with_book
    assert (out / "my-book" / collection.CONTENTS_NAME).exists()
    assert (out / "my-book" / "01.html").exists()
    assert result.books == [out / "my-book" / collection.CONTENTS_NAME]


def test_book_appears_as_listing_card(site_with_book):
    _, out, _ = site_with_book
    html = (out / collection.LISTING_NAME).read_text(encoding="utf-8")
    # A card linking to the book's contents page, titled from the folder name.
    assert 'data-post-url="my-book/contents.html"' in html
    assert ">My Book<" in html


def test_book_is_searchable(site_with_book):
    _, out, _ = site_with_book
    data = json.loads((out / collection.SEARCH_INDEX_NAME).read_text(encoding="utf-8"))
    book = next(d for d in data["docs"] if d["url"] == "my-book/contents.html")
    # Indexed so a search for a chapter title finds the book card.
    assert "Chapter Two" in book["text"]
    assert book["keywords"] == "book"


def test_asset_subfolders_are_not_books(tmp_path):
    src = tmp_path / "posts"
    src.mkdir()
    (src / "alpha.md").write_text(_post("Alpha"), encoding="utf-8")
    (src / "media").mkdir()  # an asset folder: no .md, so not a book
    (src / "media" / "logo.svg").write_text("<svg/>", encoding="utf-8")
    result = collection.build_all(src, tmp_path / "site")
    assert result.books == []


# --- CLI wiring ------------------------------------------------------------
def test_cli_build_all_reports(tmp_path, capsys):
    src = tmp_path / "posts"
    src.mkdir()
    (src / "one.md").write_text(_post("One"), encoding="utf-8")
    code = cli.main(["build-all", str(src), "-o", str(tmp_path / "site")])
    assert code == 0
    out = capsys.readouterr().out
    assert "built 1 page(s)" in out


def test_cli_build_all_missing_dir(tmp_path, capsys):
    code = cli.main(["build-all", str(tmp_path / "nope"), "-o", str(tmp_path / "site")])
    assert code == 2
    assert "no such directory" in capsys.readouterr().err
