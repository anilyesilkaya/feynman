# Feynman

An authoring system for interactive technical explanations — a Python-native
static-site generator that turns one Markdown document into a themeable HTML
page, either as a portable folder or a single self-contained file.

**[View the live demo →](https://feynman.yesilkaya.dev/)**

Feynman is for articles where the reader should be able to do more than read:
follow the mathematics, read the code, see the code's output, and drive a
visualisation — all from a single page, with almost no JavaScript shipped to the
browser.

## What it does

- **Prose + native MathML.** LaTeX (`$inline$` and `$$display$$`) is converted to
  MathML *at build time*, so no maths library ships to the reader. Display
  equations render in a panel with a button to copy the raw LaTeX.
- **Static code blocks.** Highlighted at build time with Pygments, using a
  dual-theme stylesheet so switching light/dark recolours tokens with no runtime
  highlighter. Every card has a copy button.
- **Executable Python cells.** ` ```{python} ` blocks run once in a shared kernel
  during the build; their stdout and inline SVG figures (e.g. matplotlib) are
  baked into the page. State persists across cells like a notebook, and per-cell
  options tune what shows: `#| echo: false` hides the source (keeping the
  output), `#| output: false` hides the output (keeping the source), and
  `#| label:` sets a linkable id.
- **Local images.** `![](figures/plot.png)` references are resolved relative to
  the document — copied into the output folder (portable) or embedded as data
  URIs (single-file). Remote and `data:` URIs are left untouched.
- **Step-driven visualisations.** A `:::viz` directive emits a `<feynman-viz>`
  custom element that renders an SVG figure which is a pure function of an
  integer step, driven by play / prev / next / scrub controls. Ships with
  `grid`, `radial` and `wave` types; the type registry validates directives at
  build time, warning on an unknown `type=`.

The look is a warm "printed notebook": paper/ink palette, serif display type,
mono labels, a sticky table of contents, a reading-progress bar, and a pure-CSS
light/dark theme toggle. The only JavaScript shipped drives the visualisation,
copy buttons, table of contents, and theme.

## Install

Requires Python 3.10+.

```bash
pip install .            # the generator
pip install ".[demo]"    # + matplotlib, for the example document
```

## Usage

```bash
feynman build examples/demo.md -o _site
```

By default this writes a **portable folder**: `_site/demo.html` alongside its
sidecar assets (`theme.css`, `pygments.css`, `feynman.js`) and any local images
under `_site/media/`. Open the HTML file in a browser and keep the folder
together.

For a **single self-contained file** — stylesheet, script and images all inlined
— pass `--inline` (alias `--single-file`):

```bash
feynman build examples/demo.md -o _site --inline
```

That writes just `_site/demo.html` with nothing beside it.

### Front matter

Documents start with a YAML block that drives the page chrome:

```yaml
---
title: A Feynman demo.            # <title> and table-of-contents text
hero_title: 'A Feynman<br><em>demo.</em>'   # optional raw-HTML display heading
subtitle: One page exercising every capability.
kicker: A small notebook, four capabilities
tagline: Ideas, made understandable.
theme: light                     # initial theme (light | dark)
source_url: https://…/demo.md    # optional "view source" link in the hero
---
```

All fields are optional; only `title` is really needed.

## Deployment

`.github/workflows/pages.yml` builds `examples/demo.md` in CI and publishes it to
GitHub Pages on every push to `main`. To enable it once:

1. **Settings → Pages → Build and deployment → Source → GitHub Actions.**
2. Push to `main` (or re-run the workflow).

The demo then goes live at `https://<user>.github.io/feynman/`, or at the
custom domain the workflow writes into the site's `CNAME`
(currently `https://feynman.yesilkaya.dev/`).

## Development

```bash
pip install ".[dev]"
pytest
```

The test suite builds the demo end to end and asserts that every stage left its
fingerprint in the output HTML — MathML, highlighted code, executed-cell output,
an inline figure, the copy affordances, and the viz component — plus unit tests
for the directive registry, math conversion, cell options, and the asset
collector (single-file output and local-image handling).

## License

MIT.
