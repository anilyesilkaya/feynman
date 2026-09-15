---
title: A feynman demo
subtitle: One page exercising every capability — prose and mathematics, highlighted code, Python executed at build time, and a step-driven visualisation. No lesson, just the features.
theme: light
kicker: A small notebook, four capabilities
tagline: Ideas, made understandable.
---

## Prose and mathematics

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
$$

Hover the panel and press copy — you get the exact source back, ready to paste
into another document.

## Static code

A plain fenced block is highlighted at build time and never executed. It is just
a specimen to read, with a copy button in its toolbar:

```python
def greet(name: str) -> str:
    """A static snippet: highlighted, copyable, never run."""
    return f"Hello, {name}!"
```

Syntax highlighting is baked in as static HTML — the same two-theme trick as the
prose, so switching light and dark recolours the tokens with no runtime
highlighter.

## Executed Python

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
recolours with the page theme. Its source is hidden with `#| echo: false`, so
only the figure appears:

```{python}
#| echo: false
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

The figure above was produced by Python at build time and embedded directly —
there is no image file to manage and no plotting code running for the reader.

## An interactive visualisation

The one bit of JavaScript feynman ships drives visualisations built on a single
idea: **every visualisation is a pure function of an integer step.** This grid
reveals itself one diagonal wavefront at a time. Press **play**, or scrub the
slider — the same frame is produced for the same step, every time.

::: viz {type=grid rows=10 cols=10 pattern=diagonal steps=19 fps=4}
Each step advances a diagonal wavefront across the grid. The picture is a pure function of the step number — deterministic, replayable, and driven entirely by the slider.
:::

That is the whole demo: prose and maths, code you can read, code that ran, and a
picture you can drive — one connected page, generated from plain Markdown.
