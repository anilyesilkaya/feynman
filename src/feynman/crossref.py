"""Cross-referencing: typed labels and ``@``-references within one document.

An author labels an element with a *typed* id -- ``#eq-euler``, ``#fig-bars``,
``#sec-intro``, ``#lst-greet``, ``#viz-sweep`` -- and refers to it in prose as
``@fig-bars``. At build time the target is auto-numbered by its type and the
reference renders as a clickable "Figure 1" / "Equation 2" pointing at the
target's anchor. Everything is resolved at build time; no JavaScript ships.

The mechanism is a *pre-pass* over the parsed token stream
(:func:`collect_targets`), mirroring how :mod:`feynman.render` already pre-scans
tokens for viz directives and executable cells. Numbers must be known before
rendering because a reference can point *forward* to an element that has not been
emitted yet. The registry :data:`PREFIX_KINDS` maps each label prefix to a
counter and a display word; it is the single source of truth for numbering,
analogous to ``VIZ_TYPES`` in :mod:`feynman.directives`.

Two counters intentionally coincide: ``fig-`` (a figure from a ``{python}`` cell)
and ``viz-`` (a ``:::viz`` block) share the *figures* counter, so a reader sees
one continuous "Figure N" sequence across both kinds of picture.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from html import escape

from markdown_it.token import Token

from feynman import directives, figures

# A reference: ``@`` then a lowercase prefix, a hyphen, and a slug. The prefix is
# lowercase-only so a stray "@" in prose (or a bare "@handle") never matches; the
# hyphen requirement means "@2024" and "@foo" are ignored too.
REF_RE = re.compile(r"@([a-z]+-[A-Za-z0-9_-]+)")

# ``{#label}`` inside a fence info string or a viz directive's brace body.
_BRACE_ID_RE = re.compile(r"\{#([A-Za-z0-9_-]+)\}")

# A trailing ``{#sec-...}`` on a heading line (pandoc/Quarto spelling). Captured
# by :func:`section_id_rule` and stripped from the visible heading text.
_TRAILING_ID_RE = re.compile(r"\s*\{#([A-Za-z0-9_-]+)\}\s*$")

_EXECUTABLE_INFO = "{python}"


@dataclass(frozen=True)
class Kind:
    """A reference kind: which counter a prefix feeds and how it reads."""

    prefix: str
    word: str  # display word: "Figure", "Equation", "Section", "Listing"
    counter: str  # counter bucket; two prefixes may share one


# The registry. Prefix -> kind. ``fig`` and ``viz`` deliberately share the
# ``figures`` counter so pictures number continuously across both.
PREFIX_KINDS: dict[str, Kind] = {
    "sec": Kind("sec", "Section", "sections"),
    "eq": Kind("eq", "Equation", "equations"),
    "fig": Kind("fig", "Figure", "figures"),
    "viz": Kind("viz", "Figure", "figures"),
    "lst": Kind("lst", "Listing", "listings"),
}


@dataclass(frozen=True)
class Target:
    """A labelled, numbered element that references can point at."""

    label: str  # the full id, e.g. "fig-bars"; also the anchor
    kind: Kind
    number: int

    @property
    def reference_text(self) -> str:
        """How a reference to this target reads, e.g. ``Figure 1``."""
        return f"{self.kind.word} {self.number}"

    @property
    def marker(self) -> str:
        """The element's own caption/badge text.

        Equations get a bare parenthesised number ``(1)``; figures and listings
        repeat the word ("Figure 1"). Sections carry no badge -- the heading is
        its own label and the sidebar already numbers it.
        """
        if self.kind.prefix == "eq":
            return f"({self.number})"
        if self.kind.prefix == "sec":
            return ""
        return f"{self.kind.word} {self.number}"


def _prefix_of(label: str) -> str:
    return label.split("-", 1)[0]


def brace_id(info: str) -> str | None:
    """Return the ``{#id}`` embedded in a fence/viz info string, if any."""
    match = _BRACE_ID_RE.search(info or "")
    return match.group(1) if match else None


def parse_cell_label(source: str) -> str | None:
    """Return the ``#| label:`` value from a ``{python}`` cell's source.

    Mirrors the ``#|`` option convention parsed in :mod:`feynman.render`; here
    we only need the label, so this stays a small, focused reader.
    """
    for line in source.splitlines():
        stripped = line.lstrip()
        if not stripped.startswith("#|"):
            break  # options are a contiguous leading block
        directive = stripped.split("#|", 1)[1].strip()
        if directive.startswith("label:"):
            return directive.split(":", 1)[1].strip() or None
    return None


def collect_targets(tokens: list[Token]) -> tuple[dict[str, Target], list[str]]:
    """Number every labelled element in document order.

    Returns the label -> :class:`Target` map plus a list of human-readable
    warnings (unknown prefix, duplicate label) for the caller to surface. Runs
    *after* :func:`section_id_rule`, so ``heading_open`` tokens already carry
    their explicit ``sec-`` ids.
    """
    targets: dict[str, Target] = {}
    warnings: list[str] = []
    counters: dict[str, int] = {}

    def register(label: str | None) -> None:
        if not label:
            return
        # A label whose prefix is not a cross-reference kind is a plain anchor
        # id (e.g. `#| label: my-cell`), which predates cross-referencing -- skip
        # it silently. A genuine typo surfaces instead as a dangling-reference
        # warning from the `@ref` side, so nothing is lost.
        kind = PREFIX_KINDS.get(_prefix_of(label))
        if kind is None:
            return
        if label in targets:
            warnings.append(f"duplicate cross-reference label {label!r}; first wins.")
            return
        number = counters.get(kind.counter, 0) + 1
        counters[kind.counter] = number
        targets[label] = Target(label, kind, number)

    for tok in tokens:
        if tok.type == "math_block_label":
            register(tok.info.strip())
        elif tok.type == "heading_open":
            hid = tok.attrGet("id")
            if hid and _prefix_of(hid) == "sec":
                register(hid)
        elif tok.type == "fence":
            if tok.info.strip() == _EXECUTABLE_INFO:
                register(parse_cell_label(tok.content))
            else:
                register(brace_id(tok.info))
        elif tok.type == "container_viz_open":
            # The viz id (``#viz-...``) is parsed by the directive module, so
            # the label we register is exactly the id it puts on the <figure>.
            register(directives.parse_params(tok.info).get("id"))
        elif tok.type == "container_figure_open":
            # A ``:::figure`` with a ``#fig-...`` id joins the shared figures
            # counter, numbering continuously with cells and viz blocks.
            register(figures.parse_figure_params(tok.info).get("id"))

    return targets, warnings


def iter_ref_labels(tokens: list[Token]) -> Iterator[str]:
    """Yield the label of every ``@``-reference in the token stream.

    References are inline tokens, so we descend into each ``inline`` token's
    children. Used to warn about references with no matching target.
    """
    for tok in tokens:
        if tok.type == "inline" and tok.children:
            for child in tok.children:
                if child.type == "xref":
                    yield child.content


def dangling_ref_warnings(
    tokens: list[Token], targets: dict[str, Target]
) -> list[str]:
    """Warn once per reference whose label resolves to no target."""
    warnings: list[str] = []
    seen: set[str] = set()
    for label in iter_ref_labels(tokens):
        if label in targets or label in seen:
            continue
        seen.add(label)
        warnings.append(f"reference @{label} has no matching label in this document.")
    return warnings


# --- markdown-it hooks -----------------------------------------------------
def xref_rule(state, silent) -> bool:
    """Inline rule: tokenise ``@prefix-slug`` as an ``xref`` token.

    Guards against e-mail addresses and handles by refusing to start a match
    when the ``@`` is preceded by an alphanumeric, another ``@``, or a dot -- so
    ``me@x-y.com`` and ``list@fig.co`` are left untouched.
    """
    pos = state.pos
    if state.src[pos] != "@":
        return False
    if pos > 0 and (state.src[pos - 1].isalnum() or state.src[pos - 1] in "@."):
        return False
    match = REF_RE.match(state.src, pos)
    if not match:
        return False
    if not silent:
        token = state.push("xref", "", 0)
        token.content = match.group(1)
    state.pos = match.end()
    return True


def section_id_rule(state) -> None:
    """Core rule: honour a trailing ``{#sec-...}`` on a heading.

    The ``anchors`` plugin (a core-ruler pass we run before this) sets every
    heading's ``id`` from an auto-slug of its text. Registering this rule
    *after* ``anchor`` lets an explicit ``{#sec-...}`` win: we strip the marker
    from the visible heading text and set the id to the author's label.
    """
    tokens = state.tokens
    for idx, token in enumerate(tokens):
        if token.type != "heading_open":
            continue
        inline = tokens[idx + 1]
        match = _TRAILING_ID_RE.search(inline.content)
        if not match:
            continue
        inline.content = _TRAILING_ID_RE.sub("", inline.content)
        if inline.children:
            # Strip the marker from the last text child that still carries it.
            for child in reversed(inline.children):
                if child.type == "text" and _TRAILING_ID_RE.search(child.content):
                    child.content = _TRAILING_ID_RE.sub("", child.content)
                    break
        token.attrSet("id", match.group(1))


def render_xref(target: Target | None, label: str) -> str:
    """Render one reference: a link when resolved, marked raw text when not."""
    if target is None:
        return f'<span class="feynman-xref feynman-xref-broken">@{escape(label)}</span>'
    return (
        f'<a class="feynman-xref" href="#{escape(target.label, quote=True)}">'
        f"{escape(target.reference_text)}</a>"
    )
