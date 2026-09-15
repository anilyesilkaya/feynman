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

from feynman import directives
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


def _equation_panel(latex: str) -> str:
    """Wrap a display equation in a panel with a copy-the-LaTeX button.

    The raw source rides along in ``data-latex`` (HTML-escaped) so the runtime
    can copy the exact LaTeX a reader would paste back into a document.
    """
    mathml = to_mathml(latex, display=True)
    attr = escape(latex.strip(), quote=True)
    button = (
        f'<button type="button" class="equation-copy js-only" '
        f'data-latex="{attr}" aria-label="Copy LaTeX source">{_COPY_ICON}</button>'
    )
    return f'<div class="equation-panel">{mathml}{button}</div>'


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


def _collect_executable_sources(tokens: list[Token]) -> list[str]:
    return [t.content for t in tokens if t.type == "fence" and _is_executable(t.info)]


def _cell_options(source: str) -> tuple[dict, str]:
    """Split leading ``#| key: value`` option lines from a cell's source.

    v1 understands one option, ``echo`` (bool). Unknown options are ignored but
    still stripped from the displayed source.
    """
    opts: dict = {}
    lines = source.splitlines()
    i = 0
    while i < len(lines) and lines[i].lstrip().startswith("#|"):
        directive = lines[i].split("#|", 1)[1].strip()
        if ":" in directive:
            key, _, value = directive.partition(":")
            key, value = key.strip(), value.strip().lower()
            if value in ("true", "false"):
                opts[key] = value == "true"
            else:
                opts[key] = value
        i += 1
    return opts, "\n".join(lines[i:])


class FeynmanRenderer(RendererHTML):
    """RendererHTML with maths, executable fences and viz containers."""

    def __init__(self, cell_results: list[CellResult]):
        super().__init__()
        self._cells = cell_results
        self._exec_cursor = 0

    # --- maths -------------------------------------------------------------
    def math_inline(self, tokens, idx, options, env):
        return to_mathml(tokens[idx].content, display=False)

    def math_inline_double(self, tokens, idx, options, env):
        # ``$$...$$`` used inline still reads best as a display equation.
        return to_mathml(tokens[idx].content, display=True)

    def math_block(self, tokens, idx, options, env):
        return _equation_panel(tokens[idx].content)

    def math_block_label(self, tokens, idx, options, env):
        return _equation_panel(tokens[idx].content)

    # --- code fences -------------------------------------------------------
    def fence(self, tokens, idx, options, env):
        token = tokens[idx]
        info = token.info.strip()
        if _is_executable(info):
            return self._render_executable(token.content)
        lang = info.split()[0] if info else "text"
        return (
            f'<figure class="feynman-code" data-lang="{lang}">'
            f"{_code_toolbar(lang, 'static')}"
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

        parts: list[str] = ['<figure class="feynman-cell" data-lang="python">']
        if opts.get("echo", True):
            parts.append(_code_toolbar("python", "executed at build time"))
            parts.append(highlight_code(code, "python"))
        if result is not None and result.html:
            label = (
                '<div class="output-label">'
                f"{_OUTPUT_ICON}Output</div>"
            )
            parts.append(
                f'<div class="feynman-cell-output">{label}{result.html}</div>'
            )
        parts.append("</figure>")
        return "".join(parts)

    # --- viz container -----------------------------------------------------
    def container_viz_open(self, tokens, idx, options, env):
        return directives.render_viz_open(tokens[idx].info)

    def container_viz_close(self, tokens, idx, options, env):
        return directives.render_viz_close()


def render_document(text: str) -> tuple[Document, str]:
    """Parse and render a document; return metadata and HTML body."""
    doc = split_front_matter(text)
    md = make_md()
    tokens = md.parse(doc.body)

    # Strip option lines before execution so ``#|`` directives never run.
    sources = _collect_executable_sources(tokens)
    exec_sources = [_cell_options(s)[1] for s in sources]
    cell_results = execute_cells(exec_sources)

    md.renderer = FeynmanRenderer(cell_results)
    body = md.renderer.render(tokens, md.options, {})
    return doc, body
