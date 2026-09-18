"""Built-in themes: layout template + CSS skin, chosen by the ``style`` key.

A *theme* is a visual treatment of a document. It bundles a Jinja page template
(the chrome: hero shape, sidebar placement, footer note) with zero or more CSS
layers stacked on top of the shared base ``theme.css`` (tokens + component
styling). The document body is theme-agnostic generated prose, so a theme only
restyles the frame around it and the prose's typography -- never the content.

Authors pick a theme with a front-matter ``style:`` key (distinct from the
light/dark ``theme:`` key). Unknown values fall back to :data:`DEFAULT_THEME`
with a build warning; the default reproduces feynman's original look exactly.

Adding a theme is one :class:`Theme` entry here plus its ``<name>.html.j2``
template (extending ``base.html.j2``) and any ``theme-<name>.css`` layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# The base stylesheet every page loads first: design tokens + component styling.
# Theme layers are stacked after it and only override what they need.
BASE_CSS = "theme.css"


@dataclass(frozen=True)
class Theme:
    """One built-in theme: its page template, CSS layers, and chrome defaults."""

    #: Front-matter ``style:`` value that selects this theme.
    name: str
    #: Jinja template filename (extends ``base.html.j2``).
    template: str
    #: Extra CSS assets layered *after* :data:`BASE_CSS`, in order.
    styles: tuple[str, ...] = ()
    #: Fallback chrome text used when the front matter omits it.
    defaults: dict = field(default_factory=dict)


THEMES: dict[str, Theme] = {
    "notebook": Theme(
        name="notebook",
        template="notebook.html.j2",
        defaults={"kicker": "A feynman notebook", "tagline": "Ideas, made understandable."},
    ),
    "article": Theme(
        name="article",
        template="article.html.j2",
        styles=("theme-article.css",),
        defaults={"kicker": "Scientific article", "tagline": "Research article"},
    ),
    "spec": Theme(
        name="spec",
        template="spec.html.j2",
        styles=("theme-spec.css",),
        defaults={"kicker": "Reference / specification", "tagline": "Technical reference"},
    ),
    "book": Theme(
        name="book",
        template="book.html.j2",
        styles=("theme-book.css",),
        defaults={"kicker": "A chapter", "tagline": "Read cover to cover."},
    ),
}

#: The theme used when ``style:`` is absent or unrecognised. Reproduces the
#: original feynman page exactly, so existing documents are unaffected.
DEFAULT_THEME = "notebook"


def resolve(style: object) -> tuple[Theme, str | None]:
    """Return the :class:`Theme` for ``style`` and an optional warning message.

    An unknown (or missing) style resolves to :data:`DEFAULT_THEME`. A *known*
    style yields no warning; an explicitly-set but unrecognised one does, so the
    author learns their choice was ignored.
    """
    name = str(style) if style else DEFAULT_THEME
    theme = THEMES.get(name)
    if theme is not None:
        return theme, None
    known = ", ".join(sorted(THEMES))
    warning = f"unknown style {name!r}; using {DEFAULT_THEME!r} (choose one of: {known})"
    return THEMES[DEFAULT_THEME], warning
