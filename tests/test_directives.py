"""Unit tests for the :::viz directive parser and its type registry."""

from __future__ import annotations

from feynman.directives import (
    VIZ_TYPES,
    parse_params,
    render_viz_open,
    validate_viz,
)


def test_grid_defaults_no_braces():
    spec = parse_params("viz")
    assert spec == {
        "type": "grid",
        "rows": 8,
        "cols": 8,
        "pattern": "causal",
        "steps": 8,
    }


def test_int_coercion_and_bad_value_skipped():
    spec = parse_params("viz {type=grid rows=10 cols=notanumber}")
    assert spec["rows"] == 10 and isinstance(spec["rows"], int)
    # A non-integer value for an int param is skipped, so the default remains.
    assert spec["cols"] == 8


def test_step_fallback_per_type():
    # grid -> rows, radial -> spokes, wave -> constant default.
    assert parse_params("viz {type=grid rows=12}")["steps"] == 12
    assert parse_params("viz {type=radial spokes=20}")["steps"] == 20
    assert parse_params("viz {type=wave}")["steps"] == 24


def test_explicit_steps_wins():
    assert parse_params("viz {type=grid rows=12 steps=5}")["steps"] == 5


def test_malformed_braces_fall_back_to_defaults():
    # No closing brace: nothing is parsed, defaults apply.
    spec = parse_params("viz {type=grid rows=4")
    assert spec["type"] == "grid" and spec["rows"] == 8


def test_validate_known_types_ok():
    for name in VIZ_TYPES:
        assert validate_viz(parse_params(f"viz {{type={name}}}")) is None


def test_validate_unknown_type_warns():
    msg = validate_viz(parse_params("viz {type=bogus}"))
    assert msg is not None
    assert "bogus" in msg
    # The message names the known types so the author can fix a typo.
    for name in VIZ_TYPES:
        assert name in msg


def test_render_viz_open_emits_spec_and_label():
    markup = render_viz_open("viz {type=radial spokes=20}")
    assert "<feynman-viz" in markup
    assert 'class="feynman-viz-spec"' in markup
    assert '"type":"radial"' in markup
    assert 'aria-label="radial visualisation, 20 steps"' in markup
