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
