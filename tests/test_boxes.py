"""Unit tests for the :::box directive parser and its variant registry."""

from __future__ import annotations

from feynman.boxes import (
    BOX_VARIANTS,
    DEFAULT_TYPE,
    parse_box_params,
    render_box_open,
    validate_box,
)


def test_default_type_no_braces():
    assert parse_box_params("box") == {"type": DEFAULT_TYPE}


def test_each_variant_parsed():
    for name in BOX_VARIANTS:
        assert parse_box_params(f"box {{type={name}}}") == {"type": name}


def test_quoted_title_with_spaces():
    # The value pattern must keep a quoted title intact past the first space
    # (the viz parser's `[^\s]+` would truncate it to "Heads).
    spec = parse_box_params('box {type=warning title="Heads up"}')
    assert spec == {"type": "warning", "title": "Heads up"}


def test_single_quoted_title():
    spec = parse_box_params("box {type=info title='One two three'}")
    assert spec["title"] == "One two three"


def test_bare_title_single_word():
    spec = parse_box_params("box {type=info title=Note}")
    assert spec["title"] == "Note"


def test_unknown_type_still_parses():
    # Parsing keeps the author's value verbatim; validation flags it separately.
    assert parse_box_params("box {type=bogus}") == {"type": "bogus"}


def test_validate_known_types_ok():
    for name in BOX_VARIANTS:
        assert validate_box(parse_box_params(f"box {{type={name}}}")) is None


def test_validate_unknown_type_warns():
    msg = validate_box(parse_box_params("box {type=bogus}"))
    assert msg is not None
    assert "bogus" in msg
    # The message names the known variants so the author can fix a typo.
    for name in BOX_VARIANTS:
        assert name in msg


def test_render_variant_class_and_icon():
    markup = render_box_open("box {type=warning title=Heads}")
    assert '<div class="feynman-box feynman-box-warning" role="note">' in markup
    assert "feynman-box-title" in markup
    assert "<svg" in markup  # the variant icon


def test_render_title_present_only_when_given():
    with_title = render_box_open('box {type=error title="Stop now"}')
    assert "feynman-box-title" in with_title
    assert "Stop now" in with_title

    without_title = render_box_open("box {type=error}")
    assert "feynman-box-title" not in without_title
    # The icon still marks the variant, labelled for assistive tech.
    assert "<svg" in without_title
    assert 'aria-label="Error"' in without_title


def test_render_escapes_title():
    # The page template renders with autoescape off, so the title must be
    # escaped here or author markup would break out of the header.
    markup = render_box_open('box {type=info title="a <b> & c"}')
    assert "<b>" not in markup
    assert "&lt;b&gt;" in markup
    assert "&amp;" in markup


def test_render_unknown_type_falls_back_to_default():
    markup = render_box_open("box {type=bogus}")
    assert f"feynman-box-{DEFAULT_TYPE}" in markup
    assert "feynman-box-bogus" not in markup
