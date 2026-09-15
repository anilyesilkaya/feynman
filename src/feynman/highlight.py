"""Build-time syntax highlighting with Pygments.

Code is tokenised once at build time and emitted as static HTML. Two Pygments
styles are baked into the stylesheet -- a light one under ``:root`` and a dark
one under ``[data-theme="dark"]``, both scoped to ``.highlight`` -- so switching
theme is pure CSS with no runtime highlighter, the same trick the reference site
achieves with Shiki's CSS variables (see ``docs/kvcache-teardown.md``).
"""

from __future__ import annotations

from functools import lru_cache

from pygments import highlight as _pyg_highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

LIGHT_STYLE = "default"
DARK_STYLE = "github-dark"
CSS_CLASS = "highlight"


@lru_cache(maxsize=None)
def _lexer(lang: str):
    try:
        return get_lexer_by_name(lang, stripnl=False)
    except ClassNotFound:
        return get_lexer_by_name("text", stripnl=False)


@lru_cache(maxsize=None)
def _formatter() -> HtmlFormatter:
    # nowrap=False gives us the <div class="highlight"><pre>...</pre></div> shell
    # that the stylesheet targets. We never emit inline styles.
    return HtmlFormatter(nowrap=False, cssclass=CSS_CLASS, style=LIGHT_STYLE)


def highlight_code(source: str, lang: str) -> str:
    """Return highlighted ``source`` as an HTML ``.highlight`` block."""
    return _pyg_highlight(source, _lexer(lang), _formatter())


def get_style_css() -> str:
    """Return the dual-theme Pygments CSS.

    The light theme is scoped under ``:root .highlight`` and the dark theme under
    ``[data-theme="dark"] .highlight`` so token colours follow the page theme
    with no JavaScript.
    """
    light = HtmlFormatter(style=LIGHT_STYLE).get_style_defs(f":root .{CSS_CLASS}")
    dark = HtmlFormatter(style=DARK_STYLE).get_style_defs(
        f'[data-theme="dark"] .{CSS_CLASS}'
    )
    return (
        f"/* light: {LIGHT_STYLE} */\n{light}\n\n"
        f"/* dark: {DARK_STYLE} */\n{dark}\n"
    )
