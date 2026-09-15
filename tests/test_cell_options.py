"""Unit tests for ``#| key: value`` cell-option parsing and rendering."""

from __future__ import annotations

from feynman.render import _cell_options, render_document


def test_bool_options_coerced():
    opts, code = _cell_options("#| echo: false\n#| output: true\nx = 1")
    assert opts == {"echo": False, "output": True}
    assert code == "x = 1"


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
