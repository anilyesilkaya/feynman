---
title: A Feynman demo.
hero_title: 'A Feynman<br><em>demo.</em>'
subtitle: One page exercising every capability — prose and mathematics, highlighted code, Python executed at build time, and a step-driven visualisation. No lesson, just the features.
theme: light
kicker: A small notebook, endless possibilities
tagline: Ideas, made understandable.
source_url: https://github.com/anilyesilkaya/feynman/blob/main/examples/demo.md
---

## Prose and mathematics {#sec-maths}

Feynman is for **explaining things**. You write in Markdown, and the words read
like an essay: emphasis, `inline code`, links, and lists all render into clean,
themeable prose.

Mathematics is a first-class citizen. Feynman converts LaTeX to **native
MathML** at build time, so an equation like $e^{i\pi} + 1 = 0$ sits inline with
the text and is readable by assistive technology — no maths library ships to the
browser. Display equations get their own panel, with a button to copy the
original LaTeX:

$$
f(x) = \int_{-\infty}^{\infty} \hat{f}(\xi)\, e^{2\pi i x \xi} \, d\xi
$$ (eq-fourier)

Hover the panel and press copy — you get the exact source back, ready to paste
into another document. That panel is numbered, so elsewhere on the page we can
simply refer to @eq-fourier and the link resolves to it.

## Static code {#sec-code}

A plain fenced block is highlighted at build time and never executed. It is just
a specimen to read, with a copy button in its toolbar:

```python {#lst-greet}
def greet(name: str) -> str:
    """A static snippet: highlighted, copyable, never run."""
    return f"Hello, {name}!"
```

Syntax highlighting is baked in as static HTML — the same two-theme trick as the
prose, so switching light and dark recolours the tokens with no runtime
highlighter. The block above is @lst-greet, referenced by its label.

## Executed Python {#sec-python}

An executable cell runs in a real kernel *during the build*; its output is baked
into the page. Nothing executes in the reader's browser. This one computes a
value and prints it:

```{python}
features = ["mathematics", "static code", "executed python", "visualisation"]
print(f"this page exercises {len(features)} capabilities:")
for i, name in enumerate(features, 1):
    print(f"  {i}. {name}")
```

State persists across cells, exactly like a notebook. The next cell reuses
`features` and draws a chart — captured as inline SVG, so it stays crisp and
recolours with the page theme. Its source is hidden with `#| echo: false`, and
`#| label: fig-lengths` numbers it as a figure so we can point back at it:

```{python}
#| echo: false
#| label: fig-lengths
import matplotlib.pyplot as plt

lengths = [len(name) for name in features]
fig, ax = plt.subplots(figsize=(6, 3))
ax.barh(features, lengths, color="#a64b35")
ax.invert_yaxis()
ax.set_xlabel("characters in the capability name")
ax.set_title("Four capabilities, one build")
for spine in ("top", "right"):
    ax.spines[spine].set_visible(False)
fig.tight_layout()
plt.show()
```

@fig-lengths above was produced by Python at build time and embedded directly —
there is no image file to manage and no plotting code running for the reader.

## Interactive visualisations {#sec-viz}

The one bit of JavaScript feynman ships drives visualisations built on a single
idea: **every visualisation is a pure function of an integer step.** A `type`
selects a renderer; the same machinery — play, prev, next, and a scrub slider —
drives them all. The same step always produces the same frame, so a
visualisation is deterministic and replayable.

Different shapes, one engine. Press **play** or drag a slider on any of them.

A **box grid** lights cells by a rule `(row, col, step) → on?`. This one reveals
a diagonal wavefront:

::: viz {type=grid rows=10 cols=10 pattern=diagonal steps=19 fps=5 #viz-grid}
`row + col < step` — a wavefront advancing along the diagonal. Swap the rule and the same grid becomes a fill, a causal mask, or a quarter circle.
:::

A **radial sweep** arranges points in rings and spokes and sweeps a line around
like radar, lighting each spoke as it passes:

::: viz {type=radial rings=5 spokes=20 fps=8 #viz-radial}
The sweep advances one spoke per step; a full turn lights the whole field. Polar, not rectangular — no boxes in sight.
:::

A **travelling wave** plots a sine curve whose phase advances each step, so the
whole waveform slides to the right:

::: viz {type=wave freq=2 amp=54 steps=32 fps=12 #viz-wave}
y = sin(2πfx − φ), with φ advancing per step. The dot tracks the wave's value at the centre line.
:::

A **Fourier synthesiser** sums sine waves toward a target waveform — here the
step is the number of harmonics, and the bold curve converges on the dashed
square wave, overshooting at each jump (the Gibbs phenomenon):

::: viz {type=fourier target=square terms=12 fps=3 #viz-fourier}
Each step adds the next odd harmonic of a square wave. The readout tracks the peak, which settles near 1.18 — a persistent ~9% overshoot at the discontinuities.
:::

A **Galton board** drops marbles through a lattice of pegs; each bounces left or
right at random, and enough of them pile up into the bell curve. Each step drops
one more marble — watch it deflect off the pegs on its way down before settling
into a bin:

::: viz {type=galton rows=12 balls=140 fps=4 #viz-galton}
Every marble takes a random walk, yet the pile converges on the binomial the dashed curve marks. Drag the slider to watch order emerge from independent coin flips.
:::

### Scroll to drive it {#sec-scroll}

The step need not come from a button. Add a bare `scroll` flag and nest
`::: step {to=N}` waypoints in the caption, and the figure sticks in view while
the prose scrolls past — each waypoint seeking the drawing to its step as it
reaches the reading line. It is the same pure-function-of-a-step engine; only
the *input* changes from a slider to your scroll position. With JavaScript off
the waypoints are ordinary paragraphs and the scrubber still works.

:::: viz {type=grid rows=10 cols=10 pattern=causal fps=5 scroll #viz-scroll}
A causal attention mask, revealed row by row as you read.

::: step {to=0}
Start at the top. Nothing attends yet — the mask is empty, every cell idle.
:::

::: step {to=3}
Scroll on and the first rows fill in. Token 3 can look back at tokens 0–3, but
no further: the upper triangle stays dark.
:::

::: step {to=7}
Two-thirds down the sequence, most of the lower triangle is lit. Each new row
adds exactly one more visible cell than the last.
:::

::: step {to=10}
The full causal mask. Every token attends to itself and all earlier tokens, and
to none that follow. You drove the whole animation without touching a control.
:::
::::

Adding a new shape is adding one renderer to the registry — the play / scrub /
seek machinery never changes. Note that the six figures above — @viz-grid,
@viz-radial, @viz-wave, @viz-fourier, @viz-galton and @viz-scroll — share one
figure counter with @fig-lengths, so a reader sees a single "Figure N" sequence
across executed charts and driven visualisations alike.

## Embedded figures {#sec-figure}

Not every figure is code. Run `feynman draw` to open the bundled SVG editor in
your browser, sketch a diagram, and use its Copy or Download button to save an
`.svg` beside your document. Embed it with a `:::figure` and feynman inlines the
SVG so it stays crisp, gives it a caption, and numbers it in the same "Figure N"
sequence as everything else. Add `theme=auto` and ink-toned strokes and fills
recolour with the page, so the figure reads correctly in light and dark; other
colours are left alone.

::: figure {src=figures/diagram.svg theme=auto #fig-sets}
Two sets and their intersection, drawn in the bundled editor (`feynman draw`) and
embedded as an external SVG — no plotting code, no image file to encode. Compare
with the driven pictures in @sec-viz.
:::

@fig-sets is a static drawing, yet it shares the counter with the executed chart
@fig-lengths and the visualisations in @sec-viz.

## Interactive tables {#sec-tables}

Tables stay plain Markdown — pipe-delimited rows, with column alignment coming
from the usual `:---:` markers. Add a `{...}` line *directly above* the table to
opt into more: `.sortable` makes every column click-to-sort, `.striped` bands the
rows, and a `#tbl-` id gives it a caption in the shared counter, so prose can
refer to @tbl-viz. Numeric columns (right-aligned) sort by value rather than as
text and are set in tabular figures so their digits line up.

{.sortable .striped #tbl-viz}
| Visualisation       | Default steps | Driven by |
|:--------------------|--------------:|:----------|
| Box grid            |             8 | rows      |
| Radial sweep        |            16 | spokes    |
| Travelling wave     |            24 | fixed     |
| Fourier synthesiser |             8 | terms     |
| Galton board        |           120 | balls     |

@tbl-viz gathers the five shapes from @sec-viz and the step count each defaults
to. Click **Default steps** to sort by number — the counts reorder numerically,
not lexically (so `8` sorts before `16`, and `120` lands last). Sorting is
progressive enhancement: with JavaScript off the table is still complete and
readable, just not reorderable, and wide tables scroll with the header staying
in view.

## Callout boxes {#sec-box}

Set a point apart with a `:::box`. One directive, three variants chosen by
`type` — `info`, `warning`, `error` — each with its own colour and icon drawn
from the theme, so a box recolours correctly in light and dark. The body is
ordinary Markdown, so a callout can hold formatting, lists, code and even a
cross-reference back to @sec-viz.

::: box {type=warning title="Please Note"}
A **warning** box highlights an important caveat or limitation — something worth
weighing before you go on.
:::

::: box {type=error title="Don't do that"}
An **error** box flags a mistake to avoid — a coloured rule, a matching icon,
and your prose inside.
:::

::: box {type=info}
An **info** box offers a supporting aside. This one has no title, so its icon
alone marks the variant; add a quoted `title=` and it gains a header row whose
text may contain spaces.
:::

## Themes {#sec-themes}

This page uses the default **notebook** theme. A theme sets the page layout and
typography — chosen with a `style:` key in the front matter — while sharing the
same tokens, so light/dark, code highlighting and every building block above
work identically across all of them. Three more ship built in:

- **[Research article](article.html)** (`style: article`) — paper-first, with an
  author/date/version meta row, an abstract, and numbered sections in a narrower
  measure. Built for preprints, reports, and research notes.
- **[Reference / specification](spec.html)** (`style: spec`) — dense and
  scannable, with status chips in the hero, a wider measure, and ruled section
  heads. Built for APIs, algorithms, and software documentation.
- **[Book](book/contents.html)** (`style: book`) — a reading-first, long-form
  treatment for ordered, interconnected chapters: a large chapter folio, a serif
  measure, prev/next pagers, and a spanning table of contents. It pairs with the
  `feynman book` builder (see [below](#sec-search)), which numbers *per chapter*
  ("Figure 3.2") and resolves cross-references across files.

Each links back here, so you can compare the same engine in four different
dressings. An unrecognised `style:` falls back to this notebook theme.

## Search across the collection {#sec-search}

`feynman build` compiles one document; `feynman build-all <folder>` compiles a
whole folder of them into a searchable site. Alongside each page it writes a
[**listing page**](index.html) that shows every post and — the point of this
section — filters them live as you type. This very demo is built that way: the
search page above sits beside `demo.html`, `article.html` and `spec.html`.

Search runs entirely in the reader's browser. The build emits a compact
`search-index.json` (title, subtitle, tags and full text per post); the page
builds a [MiniSearch](https://github.com/lucaong/minisearch) index from it on
first use, with prefix and typo-tolerant matching — so *mathmatics* still finds
this page. With JavaScript off the listing degrades to a plain set of links, so
the collection stays navigable either way. A post marked `draft: true` in its
front matter is left out of both the pages and the index.

Where `build-all` makes a *flat, search-first* collection, `feynman book
<folder>` builds the same kind of folder into an *ordered, interconnected* one:
chapters read in an authored sequence (set by an `order:` key), each carries
prev/next pagers, and — the part a single page cannot do — cross-references
resolve *across files* and number *per chapter*, so `@fig-bars` in chapter 3
renders "Figure 3.2" and links straight into `chapter-3.html`. A spanning
[table of contents](book/contents.html) is the entry point. The three-chapter
[example book](book/contents.html) beside this demo is built exactly that way.

## Cross-references {#sec-xref}

Everything on this page is linkable. Give an element a typed label — `#eq-` for
an equation, `#fig-` for a figure, `#lst-` for a code listing, `#viz-` for a
visualisation, `#tbl-` for a table, `#sec-` for a heading — and write `@label` in
prose to get an auto-numbered link to it. It works forwards and backwards:
@eq-fourier sits in @sec-maths near the top, @lst-greet is in @sec-code, @tbl-viz
is in @sec-tables, and the pictures live in @sec-viz. Numbers are assigned at
build time in document order, so they stay correct as the page grows.

That is the whole demo: prose and maths, code you can read, code that ran,
pictures you can drive, a web of cross-references tying them together, and a
[searchable collection](index.html) around it — one connected page, generated
from plain Markdown.
