---
title: Learning structured signals from limited observations.
hero_title: 'Learning structured signals from <em>limited observations.</em>'
subtitle: A paper-first layout for preprints, technical reports, and research notes — the same feynman engine, dressed as a journal article.
theme: light
style: article
authors: A. Researcher · Example Institute
date: 16 September 2026
version: '1.2'
abstract: The article theme prioritises the research claim over the narrative. It adds an author/date/version meta row, this dense abstract block, and automatically numbered sections in a narrower measure — while every feynman capability (mathematics, executed code, figures, cross-references) works exactly as it does elsewhere.
keywords: signal processing · statistical learning · reproducibility
source_url: https://github.com/anilyesilkaya/feynman/blob/main/examples/article.md
---

This page is built with `style: article`. It is a sibling of the
[main demo](demo.html), which uses the default `notebook` theme; a
[reference / specification](spec.html) page shows the third built-in theme.

## Introduction {#sec-intro}

Use this template for papers, preprints, research notes, technical reports, and
thesis-like chapters. The reading measure is intentionally narrower than the
notebook demo, so long-form prose feels closer to a printed journal article.
Sections are numbered automatically from the document order — this is section 1,
and the heading above needs no manual "1.".

## Method {#sec-method}

Introduce assumptions before notation. The equation panel is the same canonical
feynman treatment used across every theme, numbered so it can be referenced:

$$
y = Hx + n
$$ (eq-model)

We estimate $x$ from the noisy observation @eq-model. The panel carries a copy
button that returns the original LaTeX.

### Experimental protocol {#sec-protocol}

A subhead sits inside the numbered section without taking a number of its own.
The lab runs in a real kernel at build time, exactly as in the demo:

```{python}
trials, snr_lo, snr_hi = 1000, 0, 20
print(f"{trials} trials over {snr_hi - snr_lo} dB of SNR (seed 42)")
```

## Results {#sec-results}

The results section favours figures and compact interpretation over
step-by-step narration. A table states the protocol at a glance:

| Setting | Value | Purpose |
|---------|-------|---------|
| Trials  | 1,000 | Estimate uncertainty |
| SNR     | 0–20 dB | Stress the operating range |
| Seed    | 42    | Reproducibility |

::: box {type=info title="Contribution"}
Summarise the main contribution in one or two precise sentences. A research
document benefits from making its novelty easy to locate.
:::

## Discussion {#sec-discussion}

Separate interpretation from measurement. Discuss limitations, external
validity, and what additional evidence would change the conclusion.

> Good scientific documentation makes the boundary between observation and
> interpretation visible.

## References {#sec-refs}

Author, C. *A representative prior work.* Journal of Examples, 2025. See also
the [notebook demo](demo.html) and the [specification theme](spec.html) for the
other two built-in layouts.
