"""Execute ``{python}`` code cells at build time and capture their output.

All executable cells in a document run in one shared IPython kernel, in document
order, so later cells see earlier cells' state (ordinary notebook semantics). We
capture the kernel's display protocol -- ``text/plain``, ``text/html`` (e.g.
pandas), inline SVG/PNG images (e.g. matplotlib) and stream output -- and render
each to HTML that gets baked into the page.

Nothing here runs in the reader's browser; this is a build step.
"""

from __future__ import annotations

import re
import warnings
from dataclasses import dataclass, field
from html import escape

import nbformat
from nbclient import NotebookClient

# On Windows the Proactor event loop emits a benign zmq RuntimeWarning on kernel
# startup; it is noise for a build tool.
warnings.filterwarnings("ignore", message="Proactor event loop")

# Prepended to every document's notebook. Forces matplotlib (if the document
# uses it) to emit crisp, themeable inline SVG rather than raster PNG, matching
# the "SVG everywhere, no canvas" ethos of the reference teardown. Guarded so
# documents without matplotlib installed still run.
_SETUP_SOURCE = "\n".join(
    [
        # Pin the SVG timestamp so matplotlib figures are byte-for-byte
        # reproducible; without this it stamps the build date into every figure.
        "import os",
        "os.environ.setdefault('SOURCE_DATE_EPOCH', '315532800')",  # 1980-01-01
        "try:",
        "    import matplotlib",
        # The inline backend registers the display hook that turns plt.show()
        # into captured output. (Agg would render but never emit a figure.)
        "    matplotlib.use('module://matplotlib_inline.backend_inline')",
        # Fix the salt for SVG element ids so figures are byte-reproducible;
        # otherwise matplotlib generates random <defs> ids on every run.
        "    matplotlib.rcParams['svg.hashsalt'] = 'feynman'",
        "    from matplotlib_inline.backend_inline import set_matplotlib_formats",
        "    set_matplotlib_formats('svg')",
        "except Exception:",
        "    pass",
    ]
)


@dataclass
class CellResult:
    """Captured output for one executed cell, addressed by document order."""

    index: int
    outputs_html: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def html(self) -> str:
        return "\n".join(self.outputs_html)


def _svg_from_output(data: dict) -> str | None:
    svg = data.get("image/svg+xml")
    if svg is None:
        return None
    if isinstance(svg, list):  # nbformat may store multiline as a list of lines
        svg = "".join(svg)
    return f'<div class="feynman-output-figure">{svg}</div>'


def _html_from_output(data: dict) -> str | None:
    html = data.get("text/html")
    if html is None:
        return None
    if isinstance(html, list):
        html = "".join(html)
    return f'<div class="feynman-output-html">{html}</div>'


def _png_from_output(data: dict) -> str | None:
    png = data.get("image/png")
    if png is None:
        return None
    if isinstance(png, list):
        png = "".join(png)
    # png payloads arrive base64-encoded from the kernel; keep as a data URI.
    b64 = png.strip().replace("\n", "")
    return f'<div class="feynman-output-figure"><img alt="figure" src="data:image/png;base64,{b64}"></div>'


def _text_from_output(text: str) -> str:
    return f'<pre class="feynman-output-text">{escape(text)}</pre>'


def _render_mime_bundle(data: dict) -> str:
    """Pick the richest representation available, in priority order."""
    for producer in (_svg_from_output, _html_from_output, _png_from_output):
        rendered = producer(data)
        if rendered is not None:
            return rendered
    text = data.get("text/plain", "")
    if isinstance(text, list):
        text = "".join(text)
    return _text_from_output(text) if text else ""


def _render_output(output) -> str:
    """Render one nbformat output object to HTML."""
    otype = output.get("output_type")
    if otype == "stream":
        text = output.get("text", "")
        if isinstance(text, list):
            text = "".join(text)
        return _text_from_output(text)
    if otype in ("execute_result", "display_data"):
        return _render_mime_bundle(output.get("data", {}))
    if otype == "error":
        traceback = "\n".join(output.get("traceback", []))
        # Strip ANSI colour codes the kernel adds to tracebacks.
        clean = re.sub(r"\x1b\[[0-9;]*m", "", traceback)
        return f'<pre class="feynman-output-error">{escape(clean)}</pre>'
    return ""


def execute_cells(sources: list[str], *, timeout: int = 60) -> list[CellResult]:
    """Run ``sources`` (one string per ``{python}`` cell) in a shared kernel.

    Returns one :class:`CellResult` per input cell, in the same order. A hidden
    setup cell is prepended for matplotlib configuration and excluded from the
    results. If a cell raises, its error is captured (so the build still
    produces a page) and recorded on the result.
    """
    if not sources:
        return []

    nb = nbformat.v4.new_notebook()
    nb.cells.append(nbformat.v4.new_code_cell(_SETUP_SOURCE))
    for src in sources:
        nb.cells.append(nbformat.v4.new_code_cell(src))

    client = NotebookClient(
        nb,
        timeout=timeout,
        kernel_name="python3",
        allow_errors=True,  # capture tracebacks instead of aborting the build
        # Silence the kernel's plain-text-transport startup banner; a local
        # build kernel is not a security-relevant channel.
        extra_arguments=["--Application.log_level=CRITICAL"],
    )
    client.execute()

    results: list[CellResult] = []
    # Skip cell 0 (the setup cell); realign to caller indices.
    for i, cell in enumerate(nb.cells[1:]):
        result = CellResult(index=i)
        for output in cell.get("outputs", []):
            if output.get("output_type") == "error":
                result.error = "".join(output.get("ename", "")) or "error"
            html = _render_output(output)
            if html:
                result.outputs_html.append(html)
        results.append(result)
    return results
