"""LaTeX -> native MathML conversion.

We render maths to MathML at build time. The browser draws it with no runtime
JavaScript or CSS, and assistive technology can read it -- unlike the reference
site (see ``docs/kvcache-teardown.md``), whose KaTeX HTML is ``aria-hidden``.
"""

from __future__ import annotations

from html import escape

from latex2mathml.converter import convert as _latex_to_mathml


def to_mathml(latex: str, *, display: bool) -> str:
    """Convert a LaTeX fragment to a MathML string.

    ``display`` selects block (``display="block"``) versus inline layout.
    latex2mathml emits a ``<math>`` element; we set ``display`` explicitly so a
    single converter serves both ``$...$`` and ``$$...$$``. On failure we degrade
    to the escaped source wrapped in ``<code>`` rather than aborting the build.
    """
    mode = "block" if display else "inline"
    try:
        mathml = _latex_to_mathml(latex, display=mode)
    except Exception:
        cls = "math-error math-error-block" if display else "math-error"
        return f'<code class="{cls}" title="math conversion failed">{escape(latex)}</code>'

    # latex2mathml defaults to display="inline"; force block when requested so
    # display equations centre and get their own line via the stylesheet.
    if display and 'display="block"' not in mathml:
        mathml = mathml.replace("<math", '<math display="block"', 1)
    return mathml
