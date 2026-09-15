"""The ``:::viz`` directive: author-facing syntax for step-driven visualisations.

A directive such as::

    ::: viz {type=grid rows=8 cols=8 pattern=causal}
    Each row is one decode step.
    :::

is compiled at build time into a ``<feynman-viz>`` custom element carrying a
JSON spec. The element is defined once in ``assets/feynman.js`` and renders the
visualisation from the spec, driving it by an integer step -- the single
architectural idea carried over from the reference teardown: *every
visualisation is a pure function of an integer step*.

Only ``type=grid`` ships in v1. The parser is deliberately small and the spec
shape is forward-compatible with explicit per-step frames (and, later, frames
computed by a ``{python}`` cell).
"""

from __future__ import annotations

import json
import re
from html import escape

# Matches the info string after the ``:::`` marker, e.g.
# " viz {type=grid rows=8 cols=8 pattern=causal}". The container plugin gives us
# everything after the marker; the leading name ("viz") is stripped by the
# validate matcher, but we tolerate it here too.
_PARAMS_RE = re.compile(r"\{([^}]*)\}")
_PAIR_RE = re.compile(r"(\w[\w-]*)\s*=\s*([^\s]+)")

# Any numeric parameter across the renderer types (grid / radial / wave).
INT_PARAMS = {"rows", "cols", "steps", "rings", "spokes", "amp", "freq"}
DEFAULTS = {"type": "grid", "rows": 8, "cols": 8, "pattern": "causal"}
# Per-type fallback for the step count when the author omits ``steps``.
_STEP_FALLBACK = {"grid": "rows", "radial": "spokes", "wave": None}


def parse_params(info: str) -> dict:
    """Parse a directive info string into a spec dict, applying defaults."""
    spec = dict(DEFAULTS)
    match = _PARAMS_RE.search(info or "")
    body = match.group(1) if match else ""
    for key, value in _PAIR_RE.findall(body):
        if key in INT_PARAMS:
            try:
                spec[key] = int(value)
            except ValueError:
                continue
        else:
            spec[key] = value
    # Number of animation steps defaults per type: rows for grids, spokes for
    # radial sweeps, and a sensible constant for the (dimensionless) wave.
    key = _STEP_FALLBACK.get(spec.get("type"), "rows")
    spec.setdefault("steps", spec.get(key, 8) if key else 24)
    return spec


def render_viz_open(info: str) -> str:
    """Return the opening markup for a ``:::viz`` directive.

    The spec travels in a ``type="application/json"`` script so it survives
    static hosting untouched. The directive body (rendered by the inner tokens)
    becomes the ``<figcaption>``; :func:`render_viz_close` emits the closers.
    """
    spec = parse_params(info)
    spec_json = json.dumps(spec, separators=(",", ":"))
    label = escape(f"{spec['type']} visualisation, {spec['steps']} steps")
    return (
        f'<figure class="feynman-viz-figure">'
        f'<feynman-viz aria-label="{label}">'
        f'<script type="application/json" class="feynman-viz-spec">{spec_json}</script>'
        f"</feynman-viz>"
        f"<figcaption>"
    )


def render_viz_close() -> str:
    return "</figcaption></figure>"
