"""Feynman: an authoring system for interactive technical explanations.

A Python-native static-site generator. Markdown documents are turned into
self-contained HTML pages with:

- native MathML for equations (build-time, accessible, zero runtime JS),
- syntax-highlighted static code (Pygments, dual light/dark theme via CSS),
- executed ``{python}`` cells whose captured output is baked into the page, and
- declarative ``:::viz`` step-driven visualisations rendered by one small
  vanilla-JS web component.

The whole build is a pure function of the source; the only code shipped to the
reader is one ES module plus a stylesheet.
"""

__version__ = "0.3.0"

from feynman.build import build_document

__all__ = ["build_document", "__version__"]
