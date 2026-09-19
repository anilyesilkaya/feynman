"""Turn a parsed document into an HTML body.

This wires the pieces together by overriding a handful of markdown-it render
rules. ``RendererHTML`` auto-registers every public method as a rule, so we just
define the ones we want to customise:

- ``math_inline`` / ``math_inline_double`` / ``math_block`` -> native MathML,
- ``fence`` -> Pygments for static ``python`` blocks, and for executable
  ``{python}`` blocks the highlighted source followed by the captured output,
- ``container_viz_open`` / ``container_viz_close`` -> a ``<feynman-viz>`` figure
  wrapping the directive body as its caption.

Executable cells are run once, up front, by :mod:`feynman.execute`; this module
only stitches their captured output into the page in document order.
"""

from __future__ import annotations

from markdown_it.renderer import RendererHTML
from markdown_it.token import Token

from html import escape

from feynman import boxes, crossref, diagnostics, directives, figures
from feynman.collect import AssetCollector
from feynman.crossref import Target
from feynman.execute import CellResult, execute_cells
from feynman.highlight import highlight_code
from feynman.math import to_mathml
from feynman.parse import Document, make_md, split_front_matter

EXECUTABLE_INFO = "{python}"

# Inline SVG icons shared by the copy affordances, kept here so the renderers
# emit self-contained markup (the stylesheet sizes them via `.icon`).
_COPY_ICON = (
    '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">'
    '<rect x="8" y="8" width="12" height="12" rx="2"/>'
    '<path d="M16 8V4H4v12h4"/></svg>'
)
_CODE_ICON = (
    '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">'
    '<path d="m8 7-5 5 5 5m8-10 5 5-5 5m-3-13-2 16"/></svg>'
)
_OUTPUT_ICON = (
    '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">'
    '<path d="m5 12 4 4L19 6"/></svg>'
)


def _equation_panel(latex: str, target: Target | None = None) -> str:
    """Wrap a display equation in a panel with a copy-the-LaTeX button.

    The raw source rides along in ``data-latex`` (HTML-escaped) so the runtime
    can copy the exact LaTeX a reader would paste back into a document. A
    labelled equation additionally carries an ``id`` anchor and a parenthesised
    number (``(1)``) so cross-references can point at it.
    """
    mathml = to_mathml(latex, display=True)
    attr = escape(latex.strip(), quote=True)
    button = (
        f'<button type="button" class="equation-copy js-only" '
        f'data-latex="{attr}" aria-label="Copy LaTeX source">{_COPY_ICON}</button>'
    )
    id_attr = ""
    number = ""
    if target is not None:
        id_attr = f' id="{escape(target.label, quote=True)}"'
        number = f'<span class="equation-number">{escape(target.marker)}</span>'
    return f'<div class="equation-panel"{id_attr}>{mathml}{number}{button}</div>'


def _code_toolbar(label: str, sublabel: str) -> str:
    """A code-card toolbar: a language label plus a copy button."""
    return (
        '<figcaption class="code-toolbar">'
        f'<span class="code-label">{_CODE_ICON}{escape(label)}'
        f'<small>{escape(sublabel)}</small></span>'
        '<button type="button" class="copy-button js-only" '
        f'aria-label="Copy code">{_COPY_ICON}Copy</button>'
        "</figcaption>"
    )


def _is_executable(info: str) -> bool:
    return info.strip() == EXECUTABLE_INFO


# Author-facing table option classes (on the ``{...}`` block-attribute line)
# mapped to the internal class the stylesheet and runtime key off. Keeping the
# public names short (``sortable``) while namespacing what ships (``feynman-table
# -sortable``) avoids collisions with any generic class an author might reuse.
_TABLE_OPTION_CLASSES = {
    "sortable": "feynman-table-sortable",
    "striped": "feynman-table-striped",
    "compact": "feynman-table-compact",
}


def _table_open(token: Token, target: Target | None) -> str:
    """Open a table: a ``<figure>`` wrapper, optional caption, scroll container.

    A ``{#tbl-...}`` id (attached by ``attrs_block_plugin``) moves onto the
    ``<figure>`` as the anchor and produces a numbered ``Table N`` caption, just
    like ``:::viz`` and executed-cell figures. Recognised option classes
    (``sortable`` / ``striped`` / ``compact``) are namespaced onto the ``<table>``
    for the stylesheet and the sort enhancer; the default ``thead``/``tbody`` cell
    rendering (including alignment styles) is left untouched.
    """
    author_classes = (token.attrGet("class") or "").split()
    table_classes = ["feynman-table"] + [
        _TABLE_OPTION_CLASSES[c] for c in author_classes if c in _TABLE_OPTION_CLASSES
    ]
    class_attr = " ".join(dict.fromkeys(table_classes))

    id_attr = ""
    caption = ""
    if target is not None:
        id_attr = f' id="{escape(target.label, quote=True)}"'
        caption = (
            '<figcaption class="feynman-table-caption">'
            f'<span class="feynman-fig-label">{escape(target.marker)}</span>'
            "</figcaption>"
        )

    return (
        f'<figure class="feynman-table-figure"{id_attr}>'
        f"{caption}"
        '<div class="feynman-table-scroll">'
        f'<table class="{class_attr}">'
    )


def _table_close() -> str:
    return "</table></div></figure>"


def _collect_executable_sources(tokens: list[Token]) -> list[str]:
    return [t.content for t in tokens if t.type == "fence" and _is_executable(t.info)]


def _cell_options(source: str) -> tuple[dict, str]:
    """Split leading ``#| key: value`` option lines from a cell's source.

    Boolean options understood: ``echo`` (show the source, default true),
    ``output`` (show the captured output, default true), and ``allow-error``
    (default false) which marks a raising cell as intentional so ``--strict``
    does not fail on its traceback. ``label`` sets a stable ``id`` on the cell
    for linking. Unknown options are ignored but still stripped from the
    displayed source.
    """
    opts: dict = {}
    lines = source.splitlines()
    i = 0
    while i < len(lines) and lines[i].lstrip().startswith("#|"):
        directive = lines[i].split("#|", 1)[1].strip()
        if ":" in directive:
            key, _, value = directive.partition(":")
            key, value = key.strip(), value.strip()
            # Only fold case for the bool test, so a `label` keeps its casing.
            if value.lower() in ("true", "false"):
                opts[key] = value.lower() == "true"
            else:
                opts[key] = value
        i += 1
    return opts, "\n".join(lines[i:])


class FeynmanRenderer(RendererHTML):
    """RendererHTML with maths, executable fences and viz containers."""

    def __init__(
        self,
        cell_results: list[CellResult],
        collector: AssetCollector | None = None,
        targets: dict[str, Target] | None = None,
        current_url: str = "",
    ):
        super().__init__()
        self._cells = cell_results
        self._exec_cursor = 0
        self._collector = collector
        self._targets = targets or {}
        self._current_url = current_url
        # Per-viz scroll-mode state (set in container_viz_open); see there.
        self._viz_scroll = False
        self._viz_steps_opened = False

    # --- maths -------------------------------------------------------------
    def math_inline(self, tokens, idx, options, env):
        return to_mathml(tokens[idx].content, display=False)

    def math_inline_double(self, tokens, idx, options, env):
        # ``$$...$$`` used inline still reads best as a display equation.
        return to_mathml(tokens[idx].content, display=True)

    def math_block(self, tokens, idx, options, env):
        return _equation_panel(tokens[idx].content)

    def math_block_label(self, tokens, idx, options, env):
        # ``$$...$$ (eq-foo)`` -- the label rides in the token's info string.
        target = self._targets.get(tokens[idx].info.strip())
        return _equation_panel(tokens[idx].content, target)

    # --- cross-references --------------------------------------------------
    def xref(self, tokens, idx, options, env):
        label = tokens[idx].content
        return crossref.render_xref(
            self._targets.get(label), label, self._current_url
        )

    # --- code fences -------------------------------------------------------
    def fence(self, tokens, idx, options, env):
        token = tokens[idx]
        info = token.info.strip()
        if _is_executable(info):
            return self._render_executable(token.content)
        lang = info.split()[0] if info else "text"
        # A ``{#lst-...}`` id makes the block a numbered, linkable listing.
        target = self._targets.get(crossref.brace_id(info) or "")
        id_attr = ""
        sublabel = "static"
        if target is not None:
            id_attr = f' id="{escape(target.label, quote=True)}"'
            sublabel = target.marker  # "Listing N"
        return (
            f'<figure class="feynman-code" data-lang="{lang}"{id_attr}>'
            f"{_code_toolbar(lang, sublabel)}"
            f"{highlight_code(token.content, lang)}"
            f"</figure>"
        )

    def _render_executable(self, source: str) -> str:
        opts, code = _cell_options(source)
        result = (
            self._cells[self._exec_cursor]
            if self._exec_cursor < len(self._cells)
            else None
        )
        self._exec_cursor += 1

        show_code = opts.get("echo", True)
        show_output = opts.get("output", True)
        # `#| echo: false` + `#| output: false` runs the cell purely for its
        # side effects on later cells; render nothing rather than an empty card.
        if not show_code and not show_output:
            return ""

        label = opts.get("label")
        # A ``fig-`` label makes the cell's output a numbered, linkable figure;
        # the id anchors the whole cell so a reference lands on the card.
        target = self._targets.get(str(label)) if label else None
        attrs = ' class="feynman-cell" data-lang="python"'
        if label:
            attrs += f' id="{escape(str(label), quote=True)}"'
        parts: list[str] = [f"<figure{attrs}>"]
        if show_code:
            parts.append(_code_toolbar("python", "executed at build time"))
            parts.append(highlight_code(code, "python"))
        if show_output and result is not None and result.html:
            caption = (
                f'<span class="feynman-fig-label">{escape(target.marker)}</span>'
                if target is not None
                else "Output"
            )
            out_label = f'<div class="output-label">{_OUTPUT_ICON}{caption}</div>'
            parts.append(
                f'<div class="feynman-cell-output">{out_label}{result.html}</div>'
            )
        parts.append("</figure>")
        return "".join(parts)

    # --- viz container -----------------------------------------------------
    def container_viz_open(self, tokens, idx, options, env):
        info = tokens[idx].info
        spec = directives.parse_params(info)
        target = self._targets.get(spec.get("id") or "")
        marker = target.marker if target is not None else ""
        # Track scroll-mode state for this viz so the close (and the first
        # ``::: step``) can emit the matching structure. Viz blocks never nest,
        # so a pair of flags is enough. ``_viz_steps_opened`` flips at the first
        # waypoint, when the pinned header closes and the scrolling column opens.
        self._viz_scroll = bool(spec.get("scroll"))
        self._viz_steps_opened = False
        return directives.render_viz_open(info, marker=marker)

    def container_viz_close(self, tokens, idx, options, env):
        markup = directives.render_viz_close(
            scroll=self._viz_scroll, steps_opened=self._viz_steps_opened
        )
        self._viz_scroll = False
        self._viz_steps_opened = False
        return markup

    # --- scroll waypoints (nested inside a scroll-mode viz) ----------------
    def container_step_open(self, tokens, idx, options, env):
        prefix = ""
        # In scroll mode the first waypoint ends the pinned caption header and
        # opens the scrolling waypoint column; later waypoints just open.
        if self._viz_scroll and not self._viz_steps_opened:
            prefix = directives.render_scroll_steps_open()
            self._viz_steps_opened = True
        return prefix + directives.render_step_open(tokens[idx].info)

    def container_step_close(self, tokens, idx, options, env):
        return directives.render_step_close()

    # --- callout boxes -----------------------------------------------------
    def container_box_open(self, tokens, idx, options, env):
        return boxes.render_box_open(tokens[idx].info)

    def container_box_close(self, tokens, idx, options, env):
        return boxes.render_box_close()

    # --- embedded figures --------------------------------------------------
    def container_figure_open(self, tokens, idx, options, env):
        info = tokens[idx].info
        spec = figures.parse_figure_params(info)
        target = self._targets.get(spec.get("id") or "")
        marker = target.marker if target is not None else ""
        # Read the SVG at render time (the collector holds the filesystem); a
        # missing file / no collector yields None, which becomes a placeholder.
        src = spec.get("src")
        svg_text = (
            self._collector.read_text(src)
            if self._collector is not None and src
            else None
        )
        return figures.render_figure_open(info, svg_text, marker=marker)

    def container_figure_close(self, tokens, idx, options, env):
        return figures.render_figure_close()

    # --- images ------------------------------------------------------------
    def image(self, tokens, idx, options, env):
        # Route the src through the collector (copy locally / inline as a data
        # URI); remote and missing refs come back unchanged. Build-time figures
        # from executed cells are injected as raw HTML and never reach here.
        if self._collector is not None:
            src = tokens[idx].attrGet("src")
            if src is not None:
                tokens[idx].attrSet("src", self._collector.resolve(src))
        return super().image(tokens, idx, options, env)

    # --- tables ------------------------------------------------------------
    def table_open(self, tokens, idx, options, env):
        token = tokens[idx]
        target = self._targets.get(token.attrGet("id") or "")
        return _table_open(token, target)

    def table_close(self, tokens, idx, options, env):
        return _table_close()


def _collect_viz_infos(tokens: list[Token]) -> list[str]:
    return [t.info for t in tokens if t.type == "container_viz_open"]


def _collect_box_infos(tokens: list[Token]) -> list[str]:
    return [t.info for t in tokens if t.type == "container_box_open"]


def _collect_figure_infos(tokens: list[Token]) -> list[str]:
    return [t.info for t in tokens if t.type == "container_figure_open"]


def parse_document(text: str, *, source: str | None = None):
    """Split front matter and parse the body to a token stream.

    Returns ``(doc, md, tokens)``. Factored out so the book builder can run the
    cross-reference pre-pass over a chapter's tokens (to number targets before
    any page is rendered) without duplicating the parse setup. ``source`` is the
    document path, attached to a front-matter diagnostic if the YAML is invalid.
    """
    doc = split_front_matter(text, source=source)
    md = make_md()
    tokens = md.parse(doc.body)
    return doc, md, tokens


def render_document(
    text: str,
    *,
    collector: AssetCollector | None = None,
    targets: dict[str, Target] | None = None,
    current_url: str = "",
    source: str | None = None,
) -> tuple[Document, str]:
    """Parse and render a document; return metadata and HTML body.

    ``collector`` receives every local image reference; when ``None`` (the
    default) image refs are left untouched.

    ``targets`` overrides the per-document cross-reference numbering with a
    book-wide map (the book builder collects every chapter's targets up front so
    a reference can resolve into another chapter). When given, the local
    numbering pre-pass and its dangling-reference warnings are skipped: the book
    builder owns those, since a reference may legitimately resolve to a target in
    a different file. ``current_url`` is this page's URL, used to keep same-page
    references bare while cross-chapter ones gain a ``chapter.html`` prefix.

    ``source`` is the document's path, attached to any diagnostic emitted here so
    a reader can find the offending file.
    """
    doc, md, tokens = parse_document(text, source=source)

    # Warn once, at build time, about any viz directive naming an unknown type
    # (the reader would silently fall back to the grid renderer otherwise).
    for info in _collect_viz_infos(tokens):
        warning = directives.validate_viz(directives.parse_params(info))
        if warning:
            diagnostics.warn(warning, source=source)

    # Likewise warn about a callout box naming an unknown variant (the reader
    # would silently get the info style otherwise).
    for info in _collect_box_infos(tokens):
        warning = boxes.validate_box(boxes.parse_box_params(info))
        if warning:
            diagnostics.warn(warning, source=source)

    # Warn about a figure directive with no src or an unknown theme (a missing
    # file is caught later, at render time, where the filesystem is in reach).
    for info in _collect_figure_infos(tokens):
        warning = figures.validate_figure(figures.parse_figure_params(info))
        if warning:
            diagnostics.warn(warning, source=source)

    # Cross-reference pre-pass: number every labelled element before rendering
    # so a reference can point forward to a target not yet emitted. Warn about
    # unknown label prefixes, duplicates, and references that resolve to nothing.
    # A caller-supplied book-wide map (``targets``) short-circuits this: the book
    # builder already numbered every chapter and owns the dangling-ref check,
    # because a reference here may resolve to a target in a different file.
    if targets is None:
        targets, label_warnings = crossref.collect_targets(tokens)
        for warning in label_warnings + crossref.dangling_ref_warnings(tokens, targets):
            diagnostics.warn(warning, source=source)

    # Strip option lines before execution so ``#|`` directives never run.
    sources = _collect_executable_sources(tokens)
    cell_opts = [_cell_options(s)[0] for s in sources]
    exec_sources = [_cell_options(s)[1] for s in sources]
    cell_results = execute_cells(exec_sources)

    # A cell that raised is captured (its traceback is baked into the page), but
    # an *unexpected* traceback is a build problem: report it so ``--strict`` can
    # fail. A tutorial that means to demonstrate a failure opts in with
    # ``#| allow-error: true`` and is not reported.
    for opts, result in zip(cell_opts, cell_results):
        if result.error and not opts.get("allow-error", False):
            diagnostics.warn(
                f"cell raised {result.error} (add '#| allow-error: true' if intended)",
                source=source,
            )

    md.renderer = FeynmanRenderer(
        cell_results, collector=collector, targets=targets, current_url=current_url
    )
    body = md.renderer.render(tokens, md.options, {})
    return doc, body
