"""Tests for ``feynman init`` — the starter-document scaffold.

Covers CLI parsing, the clobber guard, filename→title derivation, and — the
one that matters most — that a freshly scaffolded document builds end to end
with no edits.
"""

from __future__ import annotations

import pytest

from feynman import cli, scaffold
from feynman.build import build_document


# --- title derivation ------------------------------------------------------
@pytest.mark.parametrize(
    "stem, expected",
    [
        ("my-first-post", "My first post"),
        ("hello_world", "Hello world"),
        ("Notes", "Notes"),
        ("kv-cache", "Kv cache"),
        ("", "Untitled"),
    ],
)
def test_title_from_stem(stem, expected):
    assert scaffold._title_from_stem(stem) == expected


# --- writing ---------------------------------------------------------------
def test_init_writes_buildable_starter(tmp_path):
    dest = scaffold.init_document(tmp_path / "my-first-post.md")
    text = dest.read_text(encoding="utf-8")
    assert dest.name == "my-first-post.md"
    # Title is derived from the filename and substituted into the front matter.
    assert "title: My first post" in text
    # No sentinel leaks through.
    assert "{{title}}" not in text
    # Front matter and a live example of each core feature are present.
    assert text.startswith("---\n")
    assert "$$" in text  # a display equation
    assert "```{python}" in text  # an executable cell
    assert "```python" in text  # a static, highlighted block


def test_minimal_is_smaller_and_valid(tmp_path):
    dest = scaffold.init_document(tmp_path / "note.md", minimal=True)
    text = dest.read_text(encoding="utf-8")
    assert "title: Note" in text
    assert "```{python}" not in text  # the tour is omitted
    assert "{{title}}" not in text


def test_creates_missing_parent_dirs(tmp_path):
    dest = scaffold.init_document(tmp_path / "blog" / "post.md")
    assert dest.is_file()


def test_refuses_to_clobber(tmp_path):
    dest = tmp_path / "post.md"
    dest.write_text("original", encoding="utf-8")
    with pytest.raises(FileExistsError):
        scaffold.init_document(dest)
    assert dest.read_text(encoding="utf-8") == "original"  # untouched


def test_force_overwrites(tmp_path):
    dest = tmp_path / "post.md"
    dest.write_text("original", encoding="utf-8")
    scaffold.init_document(dest, force=True)
    assert "original" not in dest.read_text(encoding="utf-8")


# --- CLI --------------------------------------------------------------------
def test_cli_init_writes_and_reports(tmp_path, capsys):
    dest = tmp_path / "post.md"
    assert cli.main(["init", str(dest)]) == 0
    assert dest.is_file()
    out = capsys.readouterr().out
    assert "wrote" in out
    assert "feynman build" in out  # points the author at the next step


def test_cli_init_clobber_returns_2(tmp_path, capsys):
    dest = tmp_path / "post.md"
    dest.write_text("original", encoding="utf-8")
    assert cli.main(["init", str(dest)]) == 2
    assert "already exists" in capsys.readouterr().err
    assert dest.read_text(encoding="utf-8") == "original"


def test_cli_init_force(tmp_path):
    dest = tmp_path / "post.md"
    dest.write_text("original", encoding="utf-8")
    assert cli.main(["init", str(dest), "--force"]) == 0
    assert "original" not in dest.read_text(encoding="utf-8")


# --- integration: the scaffold actually builds ------------------------------
def test_scaffolded_document_builds(tmp_path):
    """The whole point: init → build with zero edits must succeed."""
    src = scaffold.init_document(tmp_path / "my-post.md")
    out = tmp_path / "_site"
    html_path = build_document(src, out)
    html = html_path.read_text(encoding="utf-8")
    assert html_path.name == "my-post.html"
    assert "My post" in html  # derived title reached the page
    assert "<math" in html  # the inline/display equation rendered to MathML
    assert "This ran at build time." in html  # the executable cell ran
    assert "feynman-xref" in html  # @eq-example / @lst-example resolved


def test_minimal_document_builds(tmp_path):
    src = scaffold.init_document(tmp_path / "note.md", minimal=True)
    html_path = build_document(src, tmp_path / "_site")
    assert "Note" in html_path.read_text(encoding="utf-8")
