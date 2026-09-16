"""Build-level tests for inline (single-file) output and image handling.

These use a tiny document with no ``{python}`` cell so they avoid the cost of
spinning up a kernel; the executed-cell path is covered by ``test_build.py``.
"""

from __future__ import annotations

import base64

import pytest

from feynman.build import build_document

_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4"
    "2mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


@pytest.fixture
def doc_with_image(tmp_path):
    (tmp_path / "figures").mkdir()
    (tmp_path / "figures" / "plot.png").write_bytes(_PNG)
    src = tmp_path / "scratch.md"
    src.write_text(
        "---\ntitle: Scratch\n---\n\nText $x^2$ and a picture.\n\n"
        "![a plot](figures/plot.png)\n",
        encoding="utf-8",
    )
    return src


def test_inline_is_single_self_contained_file(doc_with_image, tmp_path):
    out = tmp_path / "out"
    html_path = build_document(doc_with_image, out, inline=True)
    # Only the HTML file is written -- no sidecar assets, no media dir.
    assert [p.name for p in out.iterdir()] == [html_path.name]

    html = html_path.read_text(encoding="utf-8")
    assert "<style>" in html
    assert '<script type="module">' in html
    assert 'href="theme.css"' not in html
    assert 'src="feynman.js"' not in html
    # The local image is embedded as a data URI.
    assert "data:image/png;base64," in html


def test_portable_writes_sidecars_and_copies_image(doc_with_image, tmp_path):
    out = tmp_path / "out"
    build_document(doc_with_image, out, inline=False)
    names = {p.name for p in out.iterdir()}
    assert {"scratch.html", "theme.css", "pygments.css", "feynman.js"} <= names

    html = (out / "scratch.html").read_text(encoding="utf-8")
    assert 'src="media/' in html
    assert len(list((out / "media").glob("*.png"))) == 1


def test_missing_image_warns_and_is_left(tmp_path, capsys):
    src = tmp_path / "scratch.md"
    src.write_text("---\ntitle: T\n---\n\n![x](nope.png)\n", encoding="utf-8")
    build_document(src, tmp_path / "out")
    html = (tmp_path / "out" / "scratch.html").read_text(encoding="utf-8")
    assert 'src="nope.png"' in html
    assert "nope.png" in capsys.readouterr().err


def test_stale_media_removed_on_rebuild(doc_with_image, tmp_path):
    out = tmp_path / "out"
    build_document(doc_with_image, out)
    assert list((out / "media").glob("*.png"))
    # Rebuild with the image reference gone -> the media dir is cleared.
    doc_with_image.write_text("---\ntitle: T\n---\n\nno image\n", encoding="utf-8")
    build_document(doc_with_image, out)
    assert not (out / "media").exists()


_SVG_FILE = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
    '<rect x="1" y="1" width="8" height="8" fill="#88ccee" stroke="#222222"/></svg>\n'
)


@pytest.fixture
def doc_with_figure(tmp_path):
    (tmp_path / "figures").mkdir()
    (tmp_path / "figures" / "d.svg").write_text(_SVG_FILE, encoding="utf-8")
    src = tmp_path / "scratch.md"
    src.write_text(
        "---\ntitle: Scratch\n---\n\n"
        "::: figure {src=figures/d.svg theme=auto #fig-d}\n"
        "A caption.\n"
        ":::\n",
        encoding="utf-8",
    )
    return src


@pytest.mark.parametrize("inline", [True, False])
def test_figure_svg_inlined_into_body(doc_with_figure, tmp_path, inline):
    out = tmp_path / "out"
    html_path = build_document(doc_with_figure, out, inline=inline)
    html = html_path.read_text(encoding="utf-8")
    # The SVG lands in the body, prolog stripped, id on the <figure>.
    assert 'class="feynman-figure"' in html
    assert "<rect" in html
    assert "<?xml" not in html
    assert 'id="fig-d"' in html
    assert "currentColor" in html  # theme=auto mapped the ink stroke
    # The SVG is inlined, never copied to media/ (even in portable mode).
    assert not list(out.glob("media/*.svg"))
    if not inline:
        assert not (out / "media").exists()


def test_missing_figure_src_warns_and_placeholder(tmp_path, capsys):
    src = tmp_path / "scratch.md"
    src.write_text(
        "---\ntitle: T\n---\n\n"
        "::: figure {src=nope.svg #fig-x}\ncap\n:::\n",
        encoding="utf-8",
    )
    build_document(src, tmp_path / "out")
    html = (tmp_path / "out" / "scratch.html").read_text(encoding="utf-8")
    assert "feynman-figure-missing" in html
    assert 'id="fig-x"' in html  # reference still resolves
    assert "nope.svg" in capsys.readouterr().err
