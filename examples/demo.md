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

Adding a new shape is adding one renderer to the registry — the play / scrub /
seek machinery never changes. Note that the three figures above — @viz-grid,
@viz-radial and @viz-wave — share one figure counter with @fig-lengths, so a
reader sees a single "Figure N" sequence across executed charts and driven
visualisations alike.

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

## Cross-references {#sec-xref}

Everything on this page is linkable. Give an element a typed label — `#eq-` for
an equation, `#fig-` for a figure, `#lst-` for a code listing, `#viz-` for a
visualisation, `#sec-` for a heading — and write `@label` in prose to get an
auto-numbered link to it. It works forwards and backwards: @eq-fourier sits in
@sec-maths near the top, @lst-greet is in @sec-code, and the pictures live in
@sec-viz. Numbers are assigned at build time in document order, so they stay
correct as the page grows.

That is the whole demo: prose and maths, code you can read, code that ran,
pictures you can drive, and a web of cross-references tying them together — one
connected page, generated from plain Markdown.
