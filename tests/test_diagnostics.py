"""Tests for the shared diagnostic mechanism and ``--strict`` mode.

Covers that build problems are reported (not silently swallowed), that the
diagnostic sink records them, and that ``--strict`` turns them into a nonzero
exit while non-strict builds still exit 0. Intentional cell failures opt out with
``#| allow-error: true``.
"""

from __future__ import annotations

import pytest

from feynman import cli, diagnostics
from feynman.parse import split_front_matter


# --- the sink itself -------------------------------------------------------
def test_session_collects_and_non_strict_never_fails():
    with diagnostics.session(strict=False) as diags:
        diagnostics.warn("something", source="a.md", line=3)
    assert len(diags.items) == 1
    assert diags.items[0].source == "a.md"
    assert diags.items[0].line == 3
    assert not diags.should_fail()


def test_strict_session_fails_after_a_diagnostic():
    with diagnostics.session(strict=True) as diags:
        diagnostics.warn("boom")
    assert diags.should_fail()


def test_diagnostic_format_includes_source_and_line():
    d = diagnostics.Diagnostic("warning", "bad", source="x.md", line=7)
    assert d.format() == "warning: x.md:7: bad"
    assert diagnostics.Diagnostic("warning", "bad").format() == "warning: bad"


def test_default_sink_is_restored_after_session():
    before = diagnostics.current()
    with diagnostics.session(strict=True):
        assert diagnostics.current() is not before
    assert diagnostics.current() is before


# --- invalid YAML front matter is no longer silent -------------------------
def test_invalid_yaml_is_reported():
    bad = "---\ntitle: [unclosed\n---\n\nBody.\n"
    with diagnostics.session() as diags:
        doc = split_front_matter(bad, source="bad.md")
    assert doc.meta == {}  # still degrades to empty meta
    assert diags.items
    assert "front matter" in diags.items[0].message.lower()


def test_non_mapping_front_matter_is_reported():
    scalar = "---\njust a string\n---\n\nBody.\n"
    with diagnostics.session() as diags:
        doc = split_front_matter(scalar, source="s.md")
    assert doc.meta == {}
    assert any("mapping" in d.message for d in diags.items)


# --- diagnostics surface through a real build ------------------------------
def _write(dir_, name, text):
    p = dir_ / name
    p.write_text(text, encoding="utf-8")
    return p


def test_dangling_reference_reported_and_strict_exit(tmp_path):
    src = _write(tmp_path, "doc.md", "---\ntitle: T\n---\n\nSee @fig-missing.\n")
    # Non-strict: build succeeds (exit 0) but the diagnostic is emitted.
    code = cli.main(["build", str(src), "-o", str(tmp_path / "a")])
    assert code == 0
    # Strict: the same dangling reference makes it exit nonzero.
    code = cli.main(["build", str(src), "-o", str(tmp_path / "b"), "--strict"])
    assert code == 1


def test_missing_asset_reported(tmp_path):
    src = _write(tmp_path, "doc.md", "---\ntitle: T\n---\n\n![x](nope.png)\n")
    with diagnostics.session() as diags:
        from feynman.build import build_document

        build_document(src, tmp_path / "out")
    assert any("nope.png" in d.message for d in diags.items)


def test_unknown_viz_type_reported(tmp_path):
    src = _write(
        tmp_path,
        "doc.md",
        "---\ntitle: T\n---\n\n::: viz {type=nonesuch}\ncap\n:::\n",
    )
    code = cli.main(["build", str(src), "-o", str(tmp_path / "out"), "--strict"])
    assert code == 1


def test_duplicate_label_reported(tmp_path):
    body = (
        "## One {#sec-dup}\n\nText.\n\n## Two {#sec-dup}\n\nMore.\n"
    )
    src = _write(tmp_path, "doc.md", f"---\ntitle: T\n---\n\n{body}")
    with diagnostics.session() as diags:
        from feynman.build import build_document

        build_document(src, tmp_path / "out")
    assert any("duplicate" in d.message.lower() for d in diags.items)


# --- cell error policy -----------------------------------------------------
def test_unexpected_cell_error_fails_strict(tmp_path):
    src = _write(
        tmp_path,
        "doc.md",
        "---\ntitle: T\n---\n\n```{python}\nraise ValueError('boom')\n```\n",
    )
    code = cli.main(["build", str(src), "-o", str(tmp_path / "out"), "--strict"])
    assert code == 1


def test_allowed_cell_error_passes_strict(tmp_path):
    src = _write(
        tmp_path,
        "doc.md",
        "---\ntitle: T\n---\n\n```{python}\n#| allow-error: true\n"
        "raise ValueError('intended')\n```\n",
    )
    code = cli.main(["build", str(src), "-o", str(tmp_path / "out"), "--strict"])
    assert code == 0
    # The traceback is still baked into the page (demonstrating the failure).
    html = (tmp_path / "out" / "doc.html").read_text(encoding="utf-8")
    assert "feynman-output-error" in html


def test_clean_doc_passes_strict(tmp_path):
    src = _write(tmp_path, "doc.md", "---\ntitle: T\n---\n\nJust prose, $x^2$.\n")
    code = cli.main(["build", str(src), "-o", str(tmp_path / "out"), "--strict"])
    assert code == 0


# --- boolean cell options ---------------------------------------------------
def test_allow_error_no_does_not_disarm_strict(tmp_path):
    # ``no`` used to be kept as the string "no" -- truthy -- so this spelling
    # silently switched *off* the very check it names.
    src = _write(
        tmp_path,
        "doc.md",
        "---\ntitle: T\n---\n\n```{python}\n#| allow-error: no\n"
        "raise ValueError('boom')\n```\n",
    )
    code = cli.main(["build", str(src), "-o", str(tmp_path / "out"), "--strict"])
    assert code == 1


def test_allow_error_yes_is_accepted(tmp_path):
    src = _write(
        tmp_path,
        "doc.md",
        "---\ntitle: T\n---\n\n```{python}\n#| allow-error: yes\n"
        "raise ValueError('intended')\n```\n",
    )
    code = cli.main(["build", str(src), "-o", str(tmp_path / "out"), "--strict"])
    assert code == 0


def test_unreadable_boolean_option_is_reported(tmp_path):
    src = _write(
        tmp_path,
        "doc.md",
        "---\ntitle: T\n---\n\n```{python}\n#| echo: sometimes\nx = 1\n```\n",
    )
    with diagnostics.session() as diags:
        from feynman.build import build_document

        build_document(src, tmp_path / "out")
    assert any("expects a boolean" in d.message for d in diags.items)
    # The default (echo on) applies, so the source is still shown.
    html = (tmp_path / "out" / "doc.html").read_text(encoding="utf-8")
    assert "feynman-cell" in html


# --- a :::figure pointed at a binary file ----------------------------------
def test_figure_on_a_png_reports_and_does_not_crash(tmp_path):
    import base64

    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4"
        "2mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    (tmp_path / "pic.png").write_bytes(png)
    src = _write(
        tmp_path,
        "doc.md",
        "---\ntitle: T\n---\n\n::: figure {src=pic.png #fig-p}\nA chart.\n:::\n",
    )
    with diagnostics.session() as diags:
        from feynman.build import build_document

        build_document(src, tmp_path / "out")
    # Reported as undecodable, not as missing -- the file is right there.
    assert any("not UTF-8 text" in d.message for d in diags.items)
    assert not any("asset not found" in d.message for d in diags.items)
    html = (tmp_path / "out" / "doc.html").read_text(encoding="utf-8")
    assert "feynman-figure-missing" in html
    assert "raster image" in html
    assert "not found" not in html


def test_figure_on_a_png_fails_strict_without_writing(tmp_path):
    import base64

    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4"
        "2mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    (tmp_path / "pic.png").write_bytes(png)
    src = _write(
        tmp_path,
        "doc.md",
        "---\ntitle: T\n---\n\n::: figure {src=pic.png}\nA chart.\n:::\n",
    )
    out = tmp_path / "out"
    assert cli.main(["build", str(src), "-o", str(out), "--strict"]) == 1
    assert list(out.rglob("*")) == []


# --- strict must not publish the page it just condemned --------------------
def test_strict_writes_nothing(tmp_path):
    src = _write(tmp_path, "doc.md", "---\ntitle: T\n---\n\nSee @fig-missing.\n")
    out = tmp_path / "out"
    assert cli.main(["build", str(src), "-o", str(out), "--strict"]) == 1
    # Not even the sidecar assets: a half-built directory reads as a good build.
    assert list(out.rglob("*")) == []
    # Without --strict the same document still publishes, warning and all.
    ok = tmp_path / "ok"
    assert cli.main(["build", str(src), "-o", str(ok)]) == 0
    assert (ok / "doc.html").exists()


def test_strict_build_all_writes_nothing(tmp_path):
    posts = tmp_path / "posts"
    posts.mkdir()
    _write(posts, "a.md", "---\ntitle: A\n---\n\nFine.\n")
    _write(posts, "b.md", "---\ntitle: B\n---\n\nSee @fig-nope.\n")
    out = tmp_path / "site"
    assert cli.main(["build-all", str(posts), "-o", str(out), "--strict"]) == 1
    assert list(out.rglob("*")) == []
    # The good page is withheld too: a site with one chapter silently absent is
    # worse than no site at all, and the whole point of --strict is to stop.
    assert cli.main(["build-all", str(posts), "-o", str(tmp_path / "s2")]) == 0
    assert (tmp_path / "s2" / "a.html").exists()


def test_strict_book_writes_nothing(tmp_path):
    chapters = tmp_path / "chapters"
    chapters.mkdir()
    _write(chapters, "01-one.md", "---\ntitle: One\n---\n\nFine.\n")
    _write(chapters, "02-two.md", "---\ntitle: Two\n---\n\nSee @fig-nope.\n")
    out = tmp_path / "book"
    assert cli.main(["book", str(chapters), "-o", str(out), "--strict"]) == 1
    assert list(out.rglob("*")) == []
