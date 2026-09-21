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
- **CommonMark, plus the usual extras.** Pipe tables, footnotes (`[^1]`),
  definition lists, task lists (`- [x]`), strikethrough (`~~gone~~`), and
  typographic replacement (`--` → –, `...` → …, straight quotes → curly). Code
  spans and fences are never retyped, so a `--flag` in an example stays literal.
  Bare URLs are *not* auto-linked — write `<https://example.com>` or a normal
  Markdown link.
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
  `grid`, `radial`, `wave`, `fourier` and `galton` types; the type registry
  validates directives at build time, warning on an unknown `type=`.
- **Scroll-driven visualisations.** Add a bare `scroll` flag to a `:::viz` and
  nest `::: step {to=N}` waypoints inside the block: the opening line pins as a
  caption with the figure while the waypoints scroll past in their own column.
  The figure sticks in view and the drawing eases toward each waypoint's step,
  one step at a time, as the reading line crosses between them — the reader
  drives the animation by reading. Same pure-function-of-a-step engine; only the
  input changes from a slider to the scroll position. It is progressive
  enhancement: with JavaScript off the waypoints are ordinary paragraphs and the
  scrubber still works.
- **Embedded SVG figures.** A `:::figure {src=diagram.svg}` directive inlines an
  external SVG into the page as a captioned, numbered figure — sharing the same
  "Figure N" counter as executed charts and `:::viz` blocks via a `#fig-` id.
  Inlining (rather than an `<img>`) lets an optional `theme=auto` recolour
  ink/paper-toned strokes and fills to follow the light/dark theme.
- **Interactive tables.** Ordinary Markdown pipe tables. A `{...}` line *above* a
  table opts into extras: `.sortable` makes columns click-to-sort (numeric
  columns sort by value, others by text), `.striped` / `.compact` restyle it,
  `caption="..."` describes it in Markdown (emphasis, code spans, maths and
  `@refs` all work), and a `#tbl-` id gives it a "Table N" caption you reference
  with `@tbl-`. Caption and id are independent — either alone works. Column
  alignment follows the usual `:---:` markers, with numeric columns set in
  tabular figures; wide tables scroll with a sticky header. Sorting is
  progressive enhancement — the static table is fully readable with no JS.
- **Callout boxes.** A `:::box {type=warning title="Heads up"}` sets an aside
  apart. Three variants — `info` (default), `warning`, `error` — each get their
  own theme colour and icon; the `title=` is optional. The body is ordinary
  Markdown, so a box can hold formatting, lists, code and cross-references.
- **Cross-references.** Give any element a *typed* id — `#eq-` (equation),
  `#fig-` (figure), `#viz-` (visualisation), `#lst-` (code listing), `#tbl-`
  (table), `#sec-` (heading) — and write `@label` in prose to get an
  auto-numbered link ("Figure 3", "Equation 1"). Numbers are assigned at build
  time in document order, so forward and backward references both resolve and
  stay correct as the page grows. `fig-` and `viz-` share one "Figure N" counter.
  Sections number by their position in the heading hierarchy — the second `###`
  under the second `##` is "Section 2.2" — counting every heading, labelled or
  not. That number is computed once and is the same one the `article` theme
  prints on the heading and the sidebar contents shows, so a reference and the
  page can't disagree. In a book it carries the chapter: "Section 3.1".
- **Draw figures in-browser.** `feynman draw` launches the bundled
  [svg-canvas](https://github.com/anilyesilkaya/svg-canvas) editor — a
  zero-dependency SVG drawing tool — on localhost. Draw, export the SVG, and
  embed it with `:::figure`. The editor is decoupled: it never touches your
  documents, and nothing is shipped to the reader.

The look is a warm "printed notebook": paper/ink palette, serif display type,
mono labels, a sticky table of contents, a reading-progress bar, and a pure-CSS
light/dark theme toggle. The only JavaScript shipped drives the visualisation,
copy buttons, sortable tables, table of contents, and theme.

## Install

Requires Python 3.10+.

```bash
pip install .            # the generator (Markdown, math, highlighting, viz)
pip install ".[exec]"    # + the Jupyter backend, to run {python} code cells
pip install ".[demo]"    # + exec and matplotlib, for the example document
```

Executing `{python}` cells needs the optional `exec` backend; an ordinary
Markdown build (prose, math, figures, viz) does not. A document with code cells
built without it fails with an actionable install hint rather than silently
skipping the code.

`feynman draw` also needs the bundled editor submodule — see
[Development](#development).

## Usage

Start a new document with `init`, then `build` it:

```bash
feynman init my-first-post.md   # writes a starter document
feynman build my-first-post.md  # compiles it to _site/my-first-post.html
```

`feynman init` writes a single, ready-to-build Markdown file: front matter (its
`title` derived from the filename) plus a short live example of each core
feature — prose, mathematics, a static code block, and an executed `{python}`
cell. It never overwrites an existing file unless you pass `--force`, and
`--minimal` writes just front matter and a heading instead of the feature tour.
Feynman is a single-document generator, so `init` creates *one file*, not a
project tree.

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

### Strict builds

By default a build warns about problems (invalid front matter, a missing asset, a
duplicate label, a dangling `@ref`, an unexpected cell traceback) and continues.
Pass `--strict` — on `build`, `build-all` or `book` — to make any such diagnostic
fatal, so CI fails instead of publishing a broken page:

```bash
feynman build my-post.md --strict
```

Under `--strict` nothing is written: the build stops before publishing the page it
just diagnosed, so a failed run never leaves a half-built output directory that
looks like a good one.

A cell that raises on purpose (a tutorial demonstrating an error) opts out with a
cell option so `--strict` does not fail on it:

````markdown
```{python}
#| allow-error: true
1 / 0
```
````

The boolean cell options — `echo`, `output` and `allow-error` — accept
`true`/`yes`/`on`/`1` or `false`/`no`/`off`/`0`, in any case. A value that is
none of those is reported as a diagnostic and the documented default applies,
rather than being read as "on" because a non-empty string is truthy.

### Building a searchable collection

`build` compiles one document; `build-all` compiles a *folder* of them into a
searchable site:

```bash
feynman build-all examples -o _site --title "Feynman Posts"
```

This builds every `*.md` in the folder into its own portable page (sharing one
set of sidecar assets) and additionally writes:

- `search-index.json` — a compact record per post (title, subtitle, date, tags,
  author and full text); and
- `index.html` — a listing page that shows every post newest-first and, with
  JavaScript, filters them live as you type. Search runs entirely in the browser
  (a bundled [MiniSearch](https://github.com/lucaong/minisearch) index with
  prefix and typo-tolerant matching) — there is no server. With JavaScript off,
  the page still lists every post as links.

A post with a truthy `draft:` front-matter key is skipped — built into neither
the pages nor the index. Because the search page fetches `search-index.json` at
runtime, `build-all` always emits a portable folder; `--inline` (a single
self-contained file) applies only to per-document `build`.

Any *subfolder* of chapters is auto-detected as a [book](#building-a-book): it is
built into `_site/<name>/` and listed as a single card on `index.html` (titled
from the folder name, searchable by its chapter titles). So a mixed `examples/`
folder of loose posts plus a `book/` subfolder builds into one site in a single
command.

### Building a book

Where `build-all` makes a flat, search-first collection, `book` builds the same
kind of folder as an *ordered, interconnected* one — chapters read in sequence,
each with prev/next navigation and a shared contents page:

```bash
feynman book examples/book -o _site --title "Signals"
```

Chapters are ordered by an `order:` front-matter key (integer; filename order is
the fallback), numbered from 1, and rendered with the `book` theme's chapter
chrome. Two things set a book apart from a plain collection:

- **Per-chapter numbering** — figures, equations, listings and tables number as
  `Figure 3.2` ("2nd figure of chapter 3"), each chapter restarting at 1.
- **Cross-chapter references** — a `@fig-bars` in one chapter that points at a
  label defined in another resolves across files, rendering `Figure 3.2` linking
  to `that-chapter.html#fig-bars`. Same-page references stay bare anchors.

`book` writes a `contents.html` entry page (the "Home" each chapter links back
to) listing every chapter in reading order. Like `build-all`, it always emits a
portable folder and excludes truthy `draft:` chapters.

You can also let `build-all` build the book for you: a chapter subfolder inside a
collection is auto-detected (see above), so `feynman book` is the standalone way
to build a book on its own, while `build-all` folds one (or several) into a
larger searchable site.

### Front matter

Documents start with a YAML block that drives the page chrome:

```yaml
---
title: A Feynman demo.            # <title> and table-of-contents text
hero_title: 'A Feynman<br><em>demo.</em>'   # optional raw-HTML display heading
subtitle: One page exercising every capability.
kicker: A small notebook, four capabilities
tagline: Ideas, made understandable.
theme: light                     # initial colour mode (light | dark)
style: notebook                  # built-in theme (notebook | article | spec | book)
source_url: https://…/demo.md    # optional "view source" link in the hero
---
```

All fields are optional; only `title` is really needed.

### Built-in themes

`style:` selects a built-in theme — the page layout and typography, distinct
from the `theme:` light/dark colour mode. Every theme shares the same tokens,
so light/dark, code highlighting and all the building blocks work identically.

- **`notebook`** (default) — hero, sticky table of contents, and prose. The
  original feynman look; the choice when you omit `style`.
- **`article`** — paper-first, for preprints and technical reports. Adds an
  author/date/version meta row, an optional `abstract`, and numbered sections
  in a narrower measure. Reads `authors`, `date`, `version`, `abstract`,
  `keywords` from the front matter.
- **`spec`** — dense reference, for APIs, algorithms, and specifications. Status
  chips in the hero (from a `badges:` list; one reading `Stable` gets a success
  tint), a wider measure, and ruled section heads for fast lookup.
- **`book`** — reading-first, for one chapter of an interconnected book. A large
  chapter folio, a serif long-form measure, and prev/next pagers. Comes into its
  own built as a collection with `feynman book` (ordered chapters, per-chapter
  numbering, cross-chapter references); usable on a standalone page too.

An unrecognised `style:` falls back to `notebook` with a build warning.

### Visualisations

A `:::viz` directive compiles to a step-driven figure. Pick a `type=`, set its
parameters, and give it a `#viz-` id to make it a numbered, referenceable
figure; the text between the fences becomes the caption:

```
::: viz {type=grid rows=10 cols=10 pattern=diagonal steps=19 fps=5 #viz-grid}
A wavefront advancing along the diagonal.
:::
```

The five built-in types and their main parameters:

| `type=`   | Parameters                        | Step count defaults to |
|-----------|-----------------------------------|------------------------|
| `grid`    | `rows` `cols` `pattern` `steps`   | `rows`                 |
| `radial`  | `rings` `spokes` `steps`          | `spokes`               |
| `wave`    | `amp` `freq` `steps`              | 24 (fixed)             |
| `fourier` | `terms` `amp` `freq` `target` `steps` | `terms`            |
| `galton`  | `rows` `balls` `steps`            | `balls`                |

`fps` sets the autoplay rate; `steps` overrides the per-type default; `grid`
takes a `pattern` (`causal`, `fill`, `diagonal`, `circle`) and `fourier` a
`target` (`square`, `sawtooth`, `triangle`). An unknown `type=` warns at build
time and falls back to the grid renderer.

**Deep-linkable steps.** A figure with a `#viz-` id reflects its current step
into the URL as `…/page.html#viz-grid@4`, so a reader can bookmark or share the
figure *at an exact frame*. Opening such a link scrolls that figure into view
and seeks it to the step; other figures on the page keep their own defaults. It
uses `history.replaceState`, so scrubbing never floods the back button.

**Scroll-driven mode.** Add a bare `scroll` flag and nest `::: step {to=N}`
waypoints inside the block. The opening line pins as a caption with the figure;
the waypoints scroll past in their own column, and the drawing eases toward each
one's step as the reading line reaches it — the reader drives the animation by
scrolling. (Note the nesting: the outer fence uses more colons than the inner
`::: step` fences.)

```
:::: viz {type=grid rows=10 cols=10 pattern=causal scroll #viz-mask}
A causal attention mask, revealed row by row as you read.

::: step {to=0}
Nothing attends yet — the mask is empty.
:::

::: step {to=10}
The full mask: every token attends to itself and all earlier tokens.
:::
::::
```

With JavaScript off, the waypoints are ordinary paragraphs and the scrubber
still works — so a scroll-driven figure degrades to a normal one.

### Drawing figures

Diagrams are drawn in a bundled copy of
[svg-canvas](https://github.com/anilyesilkaya/svg-canvas), a small
zero-dependency in-browser SVG editor. Launch it from feynman:

```bash
feynman draw                 # serves on http://127.0.0.1:8737 and opens a browser
feynman draw --port 9000     # use a specific port (0 picks a free one)
feynman draw --no-browser    # print the URL only (headless / CI)
```

Draw your figure, then use the editor's **Download** (saves `canvas.svg`) or
**Copy** button. Save the file next to your document — e.g.
`figures/diagram.svg` — and embed it:

```
::: figure {src=figures/diagram.svg theme=auto #fig-diagram}
A caption in **Markdown**.
:::
```

The editor is a *launch-only* extension — feynman just serves it. There is no
save-back into your document, so the draw → export → `:::figure` step is
explicit. Press Ctrl+C in the terminal to stop the server.

## Deployment

`.github/workflows/pages.yml` builds `examples/demo.md` in CI and publishes it to
GitHub Pages on every push to `main`. To enable it once:

1. **Settings → Pages → Build and deployment → Source → GitHub Actions.**
2. Push to `main` (or re-run the workflow).

The demo then goes live at `https://<user>.github.io/feynman/`, or at the
custom domain the workflow writes into the site's `CNAME`.

## Development

The SVG editor ships as a git submodule. After cloning, initialise it (or clone
with `--recurse-submodules`) so `feynman draw` has files to serve:

```bash
git submodule update --init src/feynman/editor
pip install ".[dev]"
pytest
```

The test suite builds the demo end to end and asserts that every stage left its
fingerprint in the output HTML — MathML, highlighted code, executed-cell output,
an inline figure, the copy affordances, and the viz component — plus unit tests
for the directive registry, math conversion, cell options, and the asset
collector (single-file output and local-image handling).

## License

MIT. Bundles [svg-canvas](https://github.com/anilyesilkaya/svg-canvas) (also
MIT) as a submodule under `src/feynman/editor/`; see its `LICENSE`.
