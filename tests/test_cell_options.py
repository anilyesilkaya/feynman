"""Unit tests for ``#| key: value`` cell-option parsing and rendering."""

from __future__ import annotations

import pytest

from feynman.render import _cell_option_warnings, _cell_options, render_document


def test_bool_options_coerced():
    opts, code = _cell_options("#| echo: false\n#| output: true\nx = 1")
    assert opts == {"echo": False, "output": True}
    assert code == "x = 1"


@pytest.mark.parametrize("value", ["true", "TRUE", "yes", "On", "1"])
def test_truthy_spellings(value):
    assert _cell_options(f"#| allow-error: {value}\nx = 1")[0] == {"allow-error": True}


@pytest.mark.parametrize("value", ["false", "FALSE", "no", "Off", "0"])
def test_falsey_spellings(value):
    # ``no`` and ``off`` are the ones that used to be kept as truthy strings.
    assert _cell_options(f"#| allow-error: {value}\nx = 1")[0] == {"allow-error": False}


def test_unreadable_bool_left_unset_and_warned():
    opts, code = _cell_options("#| echo: sometimes\nx = 1")
    # Unset rather than a truthy string, so the documented default applies.
    assert "echo" not in opts
    assert code == "x = 1"
    warnings = _cell_option_warnings("#| echo: sometimes\nx = 1")
    assert len(warnings) == 1
    assert "'echo'" in warnings[0] and "'sometimes'" in warnings[0]


def test_unknown_key_is_not_boolean_checked():
    # `label`/`fig-cap` carry text; "no" is a legitimate value for them.
    assert _cell_options("#| label: no\nx = 1")[0] == {"label": "no"}
    assert _cell_option_warnings("#| label: no\nx = 1") == []


def test_label_keeps_case():
    opts, code = _cell_options("#| label: My-Cell\nx = 1")
    assert opts["label"] == "My-Cell"
    assert code == "x = 1"


def test_unknown_option_stripped_but_kept():
    opts, code = _cell_options("#| fig-cap: A caption\nx = 1")
    assert opts["fig-cap"] == "A caption"
    assert code == "x = 1"


def test_output_false_hides_output_block():
    text = "---\ntitle: T\n---\n\n```{python}\n#| output: false\nprint('X')\n```\n"
    _, body = render_document(text)
    # The echoed source stays, but there is no captured-output block.
    assert "feynman-cell" in body
    assert "feynman-cell-output" not in body


def test_echo_and_output_false_renders_nothing():
    text = (
        "---\ntitle: T\n---\n\n"
        "```{python}\n#| echo: false\n#| output: false\nz = 1\n```\n"
    )
    _, body = render_document(text)
    assert "feynman-cell" not in body
