---
title: Adaptive Wiener Estimator.
hero_title: 'Adaptive Wiener <em>Estimator.</em>'
subtitle: A dense, scannable layout for APIs, algorithms, standards clauses, and software documentation — the same feynman engine, dressed as a technical reference.
theme: light
style: spec
badges: [Stable, Signal Processing, Since 2.1, 'Updated 2026-09-16']
source_url: https://github.com/anilyesilkaya/feynman/blob/main/examples/spec.md
---

This page is built with `style: spec`. It is a sibling of the
[main demo](demo.html) (the default `notebook` theme) and the
[research article](article.html) (the `article` theme). The status chips above
come from the front-matter `badges:` list; the one reading **Stable** picks up
the success tint.

## Summary {#sec-summary}

Estimates a desired sequence from noisy observations using second-order
statistics. Put the one-paragraph contract first: what the thing does, its
scope, and the single most important constraint. The spec theme uses a wider
measure and rules each section head, so a reader can scan clauses quickly.

## Syntax {#sec-syntax}

A fenced block is highlighted at build time — a specimen to read, with a copy
button:

```python {#lst-call}
xhat = wiener_estimate(y, H, noise_variance)
xhat = wiener_estimate(y, H, noise_variance, regularization=1e-8)
```

## Parameters {#sec-params}

@tbl-params lists the call arguments. Click a column header to sort — the table
opts into that with a `{.sortable #tbl-params}` line above it.

{.sortable #tbl-params}
| Name | Type | Description |
|------|------|-------------|
| `y` | array_like | Observed samples. |
| `H` | matrix | Known linear system or channel matrix. |
| `noise_variance` | float | Nonnegative noise variance. |
| `regularization` | float | Optional numerical stabilisation term. |

## Algorithm {#sec-algorithm}

State the model, then give the governing expression without burying it in prose:

$$
\hat{x} = (H^{H} H + \sigma^{2} I)^{-1} H^{H} y
$$ (eq-wiener)

@eq-wiener is the minimum-mean-square-error estimate under a linear-Gaussian
model.

::: box {type=warning title="Numerical note"}
In implementations, solve the linear system directly rather than forming an
explicit matrix inverse.
:::

## Notes and limitations {#sec-notes}

- Document dimensional assumptions explicitly.
- Separate normative requirements from explanatory notes.
- Keep examples minimal and task-oriented.
- Cross-reference equations, listings and clauses — see @eq-wiener and
  @lst-call above.

For the other built-in layouts, see the [notebook demo](demo.html) and the
[research article](article.html).
