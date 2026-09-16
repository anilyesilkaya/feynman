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
    # grid -> rows, radial -> spokes, wave -> constant default, fourier -> terms.
    assert parse_params("viz {type=grid rows=12}")["steps"] == 12
    assert parse_params("viz {type=radial spokes=20}")["steps"] == 20
    assert parse_params("viz {type=wave}")["steps"] == 24
    assert parse_params("viz {type=fourier terms=10}")["steps"] == 10


def test_explicit_steps_wins():
    assert parse_params("viz {type=grid rows=12 steps=5}")["steps"] == 5


def test_malformed_braces_fall_back_to_defaults():
    # No closing brace: nothing is parsed, defaults apply.
    spec = parse_params("viz {type=grid rows=4")
    assert spec["type"] == "grid" and spec["rows"] == 8


def test_fourier_defaults_and_step_source():
    spec = parse_params("viz {type=fourier}")
    assert spec["type"] == "fourier"
    assert spec["terms"] == 8 and isinstance(spec["terms"], int)
    assert spec["amp"] == 54 and spec["freq"] == 1
    assert spec["target"] == "square"  # a string default, not int-coerced
    assert spec["steps"] == 8  # step_source="terms"


def test_fourier_explicit_steps_wins_over_terms():
    assert parse_params("viz {type=fourier terms=12}")["steps"] == 12
    assert parse_params("viz {type=fourier terms=12 steps=6}")["steps"] == 6


def test_fourier_target_kept_as_string():
    assert parse_params("viz {type=fourier target=triangle}")["target"] == "triangle"


def test_galton_defaults_and_step_source():
    spec = parse_params("viz {type=galton}")
    assert spec["type"] == "galton"
    assert spec["rows"] == 12 and isinstance(spec["rows"], int)
    assert spec["balls"] == 120 and isinstance(spec["balls"], int)
    assert spec["steps"] == 120  # step_source="balls"


def test_galton_balls_drives_steps_and_explicit_steps_wins():
    assert parse_params("viz {type=galton balls=200}")["steps"] == 200
    assert parse_params("viz {type=galton balls=200 steps=50}")["steps"] == 50


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


def test_viz_id_parsed_from_hash_token():
    spec = parse_params("viz {type=radial spokes=20 #viz-sweep}")
    assert spec["id"] == "viz-sweep"
    assert spec["type"] == "radial" and spec["spokes"] == 20


def test_viz_id_on_figure_not_in_spec_json():
    # The id anchors the wrapping <figure>; it must not leak into the client
    # JSON spec, which stays a pure description of the drawing.
    markup = render_viz_open("viz {type=grid rows=6 #viz-demo}")
    assert '<figure class="feynman-viz-figure" id="viz-demo">' in markup
    assert '"id"' not in markup


def test_viz_marker_renders_in_caption():
    markup = render_viz_open("viz {type=grid #viz-demo}", marker="Figure 2")
    assert '<span class="feynman-fig-label">Figure 2</span>' in markup
