"""Unit tests for the :::figure directive: parsing, SVG normalisation and theming.

All pure -- the SVG text is passed in, so nothing here touches the filesystem.
"""

from __future__ import annotations

from feynman.figures import (
    DEFAULT_THEME,
    inject_root_attrs,
    normalize_svg,
    parse_figure_params,
    render_figure_close,
    render_figure_open,
    theme_svg,
    validate_figure,
)

_PROLOG = '<?xml version="1.0" encoding="UTF-8"?>'
_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
    '<circle cx="50" cy="50" r="40" fill="#88ccee" stroke="#222222"/></svg>'
)


# --- parse_figure_params ---------------------------------------------------
def test_default_theme_no_braces():
    assert parse_figure_params("figure") == {"theme": DEFAULT_THEME}


def test_src_only():
    assert parse_figure_params("figure {src=a.svg}") == {
        "theme": DEFAULT_THEME,
        "src": "a.svg",
    }


def test_src_id_and_theme():
    spec = parse_figure_params("figure {src=a.svg theme=auto #fig-x}")
    assert spec == {"theme": "auto", "src": "a.svg", "id": "fig-x"}


def test_quoted_src_with_spaces():
    # Like boxes, the value pattern keeps a quoted src intact past the space
    # (the viz parser's `[^\s]+` would truncate it to "my).
    spec = parse_figure_params('figure {src="my diagram.svg" #fig-y}')
    assert spec["src"] == "my diagram.svg"
    assert spec["id"] == "fig-y"


def test_unknown_keys_ignored():
    spec = parse_figure_params("figure {src=a.svg bogus=1}")
    assert "bogus" not in spec


# --- validate_figure -------------------------------------------------------
def test_validate_missing_src_warns():
    msg = validate_figure(parse_figure_params("figure"))
    assert msg is not None
    assert "src" in msg


def test_validate_with_src_ok():
    assert validate_figure(parse_figure_params("figure {src=a.svg}")) is None


def test_validate_unknown_theme_warns():
    msg = validate_figure(parse_figure_params("figure {src=a.svg theme=bogus}"))
    assert msg is not None
    assert "bogus" in msg


# --- normalize_svg ---------------------------------------------------------
def test_normalize_strips_xml_prolog():
    out = normalize_svg(f"{_PROLOG}\n{_SVG}")
    assert "<?xml" not in out
    assert out.startswith("<svg")


def test_normalize_strips_doctype_and_bom_keeps_svg_attrs():
    src = '﻿<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "x.dtd">\n' + _SVG
    out = normalize_svg(src)
    assert "DOCTYPE" not in out
    assert "﻿" not in out
    # xmlns and viewBox survive -- both are valid/harmless in inline SVG.
    assert 'xmlns="http://www.w3.org/2000/svg"' in out
    assert 'viewBox="0 0 100 100"' in out


# --- inject_root_attrs -----------------------------------------------------
def test_inject_adds_class_once():
    out = inject_root_attrs(_SVG, themed=False)
    assert out.count("feynman-figure-svg") == 1
    assert "feynman-figure-themed" not in out
    assert out.startswith('<svg class="feynman-figure-svg"')


def test_inject_themed_adds_both_classes():
    out = inject_root_attrs(_SVG, themed=True)
    assert "feynman-figure-svg" in out
    assert "feynman-figure-themed" in out


def test_inject_merges_existing_class():
    svg = '<svg class="custom" viewBox="0 0 10 10"></svg>'
    out = inject_root_attrs(svg, themed=False)
    # One class attribute, both names present -- no duplicate attribute.
    assert out.count("class=") == 1
    assert "custom" in out
    assert "feynman-figure-svg" in out


# --- theme_svg (colour map) ------------------------------------------------
def test_theme_maps_ink_to_currentcolor():
    out = theme_svg('<rect fill="#222222" stroke="#000000"/>')
    assert 'fill="currentColor"' in out
    assert 'stroke="currentColor"' in out


def test_theme_maps_white_to_paper():
    out = theme_svg('<rect fill="#ffffff"/>')
    assert 'fill="var(--paper)"' in out


def test_theme_handles_shorthand_and_case():
    out = theme_svg('<rect fill="#000" stroke="#FFF"/>')
    assert 'fill="currentColor"' in out
    assert 'stroke="var(--paper)"' in out
    assert theme_svg('<rect fill="#FfFfFf"/>') == '<rect fill="var(--paper)"/>'


def test_theme_leaves_chromatic_untouched():
    out = theme_svg('<circle fill="#88ccee"/>')
    assert '#88ccee' in out
    assert "currentColor" not in out


def test_theme_maps_inline_style_form():
    out = theme_svg('<rect style="fill:#222222;stroke:#88ccee"/>')
    assert "fill:currentColor" in out
    assert "#88ccee" in out  # chromatic stroke left as-is


def test_theme_does_not_touch_ids_or_url_refs():
    # A property-anchored map must never rewrite an id or a url(#...) reference,
    # even when the value looks like an ink hex.
    src = '<rect id="#000000" clip-path="url(#000000)"/>'
    assert theme_svg(src) == src


# --- render_figure_open / _close -------------------------------------------
def test_render_open_inlines_svg_with_figure_wrapper():
    out = render_figure_open(
        "figure {src=a.svg theme=auto #fig-x}", f"{_PROLOG}\n{_SVG}", marker="Figure 5"
    )
    assert out.startswith('<figure class="feynman-figure" id="fig-x">')
    assert "<svg" in out
    assert "<?xml" not in out  # prolog stripped before inlining
    assert '<span class="feynman-fig-label">Figure 5</span>' in out
    # The id anchors the <figure>, not the <svg>.
    assert 'id="fig-x">' in out.split("<svg")[0]


def test_render_open_verbatim_default_no_theme_class():
    out = render_figure_open("figure {src=a.svg}", _SVG)
    assert "feynman-figure-themed" not in out
    assert "#222222" in out  # colours untouched
    assert "currentColor" not in out


def test_render_open_missing_svg_placeholder():
    out = render_figure_open("figure {src=nope.svg #fig-z}", None, marker="Figure 6")
    assert "feynman-figure-missing" in out
    assert "nope.svg" in out
    assert 'id="fig-z"' in out  # id still anchors the figure
    assert "<figcaption>" in out  # still a valid figure/caption pair


def test_render_open_non_svg_text_placeholder():
    out = render_figure_open("figure {src=a.txt}", "not an svg at all")
    assert "feynman-figure-missing" in out


def test_render_open_reason_overrides_not_found():
    # A resolved-but-binary source must not be described as missing: the author
    # would go looking for a file that is sitting right there.
    out = render_figure_open(
        "figure {src=pic.png}", None, reason="is not text (a raster image cannot be inlined)"
    )
    assert "feynman-figure-missing" in out
    assert "not found" not in out
    assert "raster image" in out
    assert "pic.png" in out


def test_render_open_escapes_id():
    out = render_figure_open('figure {src=a.svg #fig-x}', _SVG)
    # Ids are constrained by the regex, but the attribute is still quote-escaped.
    assert 'id="fig-x"' in out


def test_render_close():
    assert render_figure_close() == "</figcaption></figure>"
