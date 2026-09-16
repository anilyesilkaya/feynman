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
    assert "Keywords:" in html


def test_article_omits_optional_chrome_when_absent(tmp_path):
    src = _write(tmp_path, "title: Paper\nstyle: article")
    html = build_document(src, tmp_path / "out").read_text(encoding="utf-8")
    # No abstract block and no meta row when the keys are absent.
    assert 'class="abstract"' not in html
    assert 'class="article-meta"' not in html


def test_spec_badges_and_stable_tint(tmp_path):
    src = _write(
        tmp_path,
        "title: Ref\nstyle: spec\nbadges: [Stable, Beta]",
    )
    html = build_document(src, tmp_path / "out").read_text(encoding="utf-8")
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
