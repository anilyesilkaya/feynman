"""The ``:::box`` directive: author-facing syntax for callout boxes.

A directive such as::

    ::: box {type=warning title="Heads up"}
    Don't do **that**. See @sec-code for the safe approach.
    :::

is compiled at build time into a styled ``<div>`` whose colour and icon come
from its *variant* (``type=``). The body between the fences is ordinary
Markdown, so a box can hold formatting, lists, code, maths and
cross-references -- it is rendered by the inner tokens, exactly like the
``:::viz`` caption.

Known variants live in one declarative registry, :data:`BOX_VARIANTS`, the
build-time source of truth for which ``type=`` values are valid (analogous to
``VIZ_TYPES`` in :mod:`feynman.directives`). Each variant names a CSS class
suffix, an inline icon and an accessible label; the colours themselves are
theme tokens (``--info``/``--warning``/``--error`` and their ``*-soft``
pairs) in ``assets/theme.css``, so light/dark stays a pure-CSS switch and an
author cannot pass an arbitrary colour that breaks contrast.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import escape

# Inline SVG icons, one per variant. Same shape as the icons in
# :mod:`feynman.render` (24x24 line icons, ``class="icon"``, stroked in
# ``currentColor``), so they inherit sizing and the variant's colour for free.
# The outer shapes are stroked outlines; the interior marks (the i's stem and
# dot, the ! bar and dot) are SOLID fills rather than thin round-capped strokes,
# which blur at small sizes. `stroke="none"` keeps the fills from picking up the
# icon's stroke.
_INFO_ICON = (
    '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">'
    '<circle cx="12" cy="12" r="9"/>'
    '<circle cx="12" cy="8" r="1.35" fill="currentColor" stroke="none"/>'
    '<rect x="11" y="11" width="2" height="6" rx="1" fill="currentColor" stroke="none"/>'
    "</svg>"
)
_WARNING_ICON = (
    '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">'
    '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>'
    '<rect x="11" y="9" width="2" height="5" rx="1" fill="currentColor" stroke="none"/>'
    '<circle cx="12" cy="17" r="1.35" fill="currentColor" stroke="none"/>'
    "</svg>"
)
_ERROR_ICON = (
    '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">'
    '<polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"/>'
    '<path d="m15 9-6 6"/><path d="m9 9 6 6"/></svg>'
)


@dataclass(frozen=True)
class BoxVariant:
    """A registered callout variant: its CSS suffix, icon and label.

    ``name`` is both the ``type=`` value and the CSS-class suffix
    (``feynman-box-<name>``). ``icon`` is the inline SVG shown in the header /
    marker. ``label`` is the accessible name announced for the icon and used
    as the fallback header text when the author gives no explicit title.
    """

    name: str
    icon: str
    label: str


# The registry. Each entry pairs with a set of theme tokens in theme.css.
BOX_VARIANTS: dict[str, BoxVariant] = {
    "info": BoxVariant("info", _INFO_ICON, "Info"),
    "warning": BoxVariant("warning", _WARNING_ICON, "Warning"),
    "error": BoxVariant("error", _ERROR_ICON, "Error"),
}

DEFAULT_TYPE = "info"

# The brace body after the ``:::box`` marker, e.g. ``{type=warning title="..."}``.
_PARAMS_RE = re.compile(r"\{([^}]*)\}")
# Quote-aware key=value: a bare token, or a single/double-quoted string that
# may contain spaces. (The viz parser's ``[^\s]+`` value would truncate a
# quoted ``title="Heads up"`` at the first space, so boxes parse their own.)
_PAIR_RE = re.compile(
    r"""(\w[\w-]*)\s*=\s*(?:"([^"]*)"|'([^']*)'|(\S+))""",
)


def parse_box_params(info: str) -> dict:
    """Parse a ``:::box`` info string into ``{"type": ..., "title": ...}``.

    ``type`` defaults to :data:`DEFAULT_TYPE`; ``title`` is absent when the
    author gives none. Unknown keys are ignored (validation is separate).
    """
    match = _PARAMS_RE.search(info or "")
    body = match.group(1) if match else ""

    params: dict = {}
    for key, dq, sq, bare in _PAIR_RE.findall(body):
        params[key] = dq or sq or bare

    spec: dict = {"type": params.get("type", DEFAULT_TYPE)}
    if "title" in params:
        spec["title"] = params["title"]
    return spec


def validate_box(spec: dict) -> str | None:
    """Return a warning if ``spec`` names an unregistered variant, else ``None``.

    A ``type=`` with no registry entry would silently fall back to the info
    variant; surfacing it at build time lets the author fix a typo instead of
    shipping the wrong colour and icon.
    """
    vtype = spec.get("type", DEFAULT_TYPE)
    if vtype not in BOX_VARIANTS:
        known = ", ".join(sorted(BOX_VARIANTS))
        return (
            f"unknown box type {vtype!r}; the reader will see the info style. "
            f"Known types: {known}."
        )
    return None


def render_box_open(info: str) -> str:
    """Return the opening markup for a ``:::box`` directive info string.

    The variant selects the CSS class, icon and accessible label; an unknown
    type falls back to the default so output is always coherent. With a
    ``title=`` the box gets a header row (icon + title); without one, the icon
    alone marks the box so the variant stays visible. Author text is escaped
    because the page template renders with autoescape off.
    """
    spec = parse_box_params(info)
    variant = BOX_VARIANTS.get(spec["type"], BOX_VARIANTS[DEFAULT_TYPE])
    title = spec.get("title")

    open_div = (
        f'<div class="feynman-box feynman-box-{variant.name}" role="note">'
    )
    if title:
        return (
            f"{open_div}"
            f'<div class="feynman-box-title">'
            f'<span class="feynman-box-icon" aria-hidden="true">{variant.icon}</span>'
            f"<span>{escape(title)}</span>"
            f"</div>"
        )
    # No title: a bare, labelled icon keeps the variant visible without a header.
    return (
        f"{open_div}"
        f'<span class="feynman-box-icon" role="img" '
        f'aria-label="{escape(variant.label, quote=True)}">{variant.icon}</span>'
    )


def render_box_close() -> str:
    return "</div>"
