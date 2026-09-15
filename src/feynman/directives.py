"""The ``:::viz`` directive: author-facing syntax for step-driven visualisations.

A directive such as::

    ::: viz {type=grid rows=8 cols=8 pattern=causal}
    Each row is one decode step.
    :::

is compiled at build time into a ``<feynman-viz>`` custom element carrying a
JSON spec. The element is defined once in ``assets/feynman.js`` and renders the
visualisation from the spec, driving it by an integer step -- the single
architectural idea carried over from the reference site (kvcache.cobanov.dev):
*every visualisation is a pure function of an integer step*.

Known visualisation types live in one declarative registry, :data:`VIZ_TYPES`.
That registry is the build-time source of truth for which ``type=`` values are
valid and which numeric parameters each accepts; the matching client-side
renderers live in ``assets/feynman.js`` (its ``RENDERERS`` map). Adding a shape
is one entry here plus one renderer there, and a ``type=`` with no registry
entry surfaces as a build-time warning (see :func:`validate_viz`) rather than a
silent fallback to the grid renderer.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from html import escape

# Matches the info string after the ``:::`` marker, e.g.
# " viz {type=grid rows=8 cols=8 pattern=causal}". The container plugin gives us
# everything after the marker; the leading name ("viz") is stripped by the
# validate matcher, but we tolerate it here too.
_PARAMS_RE = re.compile(r"\{([^}]*)\}")
_PAIR_RE = re.compile(r"(\w[\w-]*)\s*=\s*([^\s]+)")
# A bare ``#slug`` token among the params gives the figure a cross-reference id,
# e.g. ``{type=radial spokes=20 #viz-sweep}``. Matches the ``#id`` spelling used
# for equations, listings and sections; resolved by :mod:`feynman.crossref`.
_ID_RE = re.compile(r"(?:^|\s)#([A-Za-z0-9_-]+)")


@dataclass(frozen=True)
class VizType:
    """A registered visualisation type: its params, defaults and step source.

    ``int_params`` are the numeric parameters this type accepts (coerced to
    ``int`` at parse time). ``defaults`` are the non-step defaults applied when
    the author omits them. ``step_source`` names the parameter whose value
    supplies the default animation step count; when ``None``, ``default_steps``
    is used instead (for types whose step count is dimensionless, like a wave).
    """

    name: str
    int_params: frozenset[str]
    defaults: dict = field(default_factory=dict)
    step_source: str | None = None
    default_steps: int = 24


# The registry. Each entry mirrors a renderer in ``assets/feynman.js``.
VIZ_TYPES: dict[str, VizType] = {
    "grid": VizType(
        "grid",
        frozenset({"rows", "cols", "steps"}),
        {"rows": 8, "cols": 8, "pattern": "causal"},
        step_source="rows",
    ),
    "radial": VizType(
        "radial",
        frozenset({"rings", "spokes", "steps"}),
        {"rings": 5, "spokes": 16},
        step_source="spokes",
    ),
    "wave": VizType(
        "wave",
        frozenset({"amp", "freq", "steps"}),
        {"amp": 54, "freq": 2},
        step_source=None,
        default_steps=24,
    ),
}

DEFAULT_TYPE = "grid"

# Union of every type's numeric params. ``parse_params`` coerces ints before it
# knows the concrete type (``type`` is itself a parsed param), so it needs the
# full set; an unknown type still gets its numbers coerced sensibly.
ALL_INT_PARAMS: frozenset[str] = frozenset().union(
    *(t.int_params for t in VIZ_TYPES.values())
)


def parse_params(info: str) -> dict:
    """Parse a directive info string into a spec dict, applying defaults."""
    match = _PARAMS_RE.search(info or "")
    body = match.group(1) if match else ""

    # Read explicit params first so we know the type before applying defaults.
    parsed: dict = {}
    for key, value in _PAIR_RE.findall(body):
        if key in ALL_INT_PARAMS:
            try:
                parsed[key] = int(value)
            except ValueError:
                continue
        else:
            parsed[key] = value

    # A bare ``#slug`` gives the figure a cross-reference id. It rides in the
    # spec under ``id`` but is stripped before the client JSON (see render_spec).
    id_match = _ID_RE.search(body)
    if id_match:
        parsed["id"] = id_match.group(1)

    vtype = parsed.get("type", DEFAULT_TYPE)
    # Unknown types fall back to the grid shape for defaults so the client's
    # grid fallback still gets a coherent spec; validate_viz warns separately.
    entry = VIZ_TYPES.get(vtype, VIZ_TYPES[DEFAULT_TYPE])

    spec = {"type": vtype, **entry.defaults}
    spec.update(parsed)

    # Number of animation steps defaults per type: rows for grids, spokes for
    # radial sweeps, and a sensible constant for the (dimensionless) wave.
    if entry.step_source is not None:
        spec.setdefault("steps", spec.get(entry.step_source, entry.default_steps))
    else:
        spec.setdefault("steps", entry.default_steps)
    return spec


def validate_viz(spec: dict) -> str | None:
    """Return a warning if ``spec`` names an unregistered type, else ``None``.

    A ``type=`` with no registry entry would silently fall back to the grid
    renderer in the browser; surfacing it at build time lets the author fix a
    typo (or notice a missing JS renderer) instead of shipping a wrong picture.
    """
    vtype = spec.get("type", DEFAULT_TYPE)
    if vtype not in VIZ_TYPES:
        known = ", ".join(sorted(VIZ_TYPES))
        return (
            f"unknown viz type {vtype!r}; the reader will fall back to the grid "
            f"renderer. Known types: {known}."
        )
    return None


def render_viz_open(info: str, marker: str = "") -> str:
    """Return the opening markup for a ``:::viz`` directive info string.

    ``marker`` is a cross-reference caption such as ``Figure 1``, supplied by the
    renderer when the directive carries a ``#viz-...`` id (see
    :mod:`feynman.crossref`); it is empty for an unlabelled figure.
    """
    return render_spec(parse_params(info), marker=marker)


def render_spec(spec: dict, marker: str = "") -> str:
    """Return the opening markup for an already-parsed viz spec.

    The spec travels in a ``type="application/json"`` script so it survives
    static hosting untouched. The directive body (rendered by the inner tokens)
    becomes the ``<figcaption>``; :func:`render_viz_close` emits the closers.

    A ``#viz-...`` id (parsed into ``spec['id']``) is placed on the wrapping
    ``<figure>`` as the anchor and stripped from the client JSON, so the runtime
    spec stays a pure description of the drawing.
    """
    fig_id = spec.pop("id", None)
    spec_json = json.dumps(spec, separators=(",", ":"))
    label = escape(f"{spec['type']} visualisation, {spec['steps']} steps")
    id_attr = f' id="{escape(fig_id, quote=True)}"' if fig_id else ""
    caption_marker = (
        f'<span class="feynman-fig-label">{escape(marker)}</span> ' if marker else ""
    )
    return (
        f'<figure class="feynman-viz-figure"{id_attr}>'
        f'<feynman-viz aria-label="{label}">'
        f'<script type="application/json" class="feynman-viz-spec">{spec_json}</script>'
        f"</feynman-viz>"
        f"<figcaption>{caption_marker}"
    )


def render_viz_close() -> str:
    return "</figcaption></figure>"
