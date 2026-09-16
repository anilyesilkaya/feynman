"""Scaffold a starter document for ``feynman init``.

Feynman is a single-document generator: there is no project, no config, no site
tree -- just one Markdown file in, one HTML page out. So ``init`` does exactly
one thing: write a single, valid, buildable ``.md`` with front matter and a
small live example of each core feature (prose, mathematics, a static code
block, and an executed ``{python}`` cell). The intent is a warm start over a
blank file -- ``feynman init post.md && feynman build post.md`` must succeed
with no edits.

Deliberately thin: no directory scaffold, no interactive prompts, no build. The
writer just refuses to clobber an existing file unless ``force`` is set.
"""

from __future__ import annotations

from pathlib import Path

# Replaced (not ``str.format``-ed) into the templates below: their bodies are
# full of literal braces -- ``{python}`` cells, ``{#sec-x}`` ids, ``f"{name}"``
# -- so a distinctive sentinel is the only safe substitution.
_TITLE = "{{title}}"

STARTER_TEMPLATE = """\
---
title: {{title}}
subtitle: A one-line description of what this post is about.
theme: light
kicker: First post
tagline: Ideas, made understandable.
# Optional front matter (uncomment to use):
# style: notebook           # built-in theme: notebook (default), article, spec
# hero_title: '{{title}}'   # raw-HTML display heading; allows <br> and <em>
# source_url: https://…     # adds a "view source" link in the hero
---

## Introduction {#sec-intro}

Open here. Prose is ordinary **Markdown**: emphasis, `inline code`,
[links](https://example.com), and lists.

Mathematics is built in — inline like $a^2 + b^2 = c^2$, or as a numbered
display panel you can refer back to with @eq-example:

$$
\\int_0^1 x^2 \\, dx = \\frac{1}{3}
$$ (eq-example)

## Code {#sec-code}

A fenced block is highlighted at build time and never executed — a specimen to
read, with a copy button:

```python {#lst-example}
def greet(name: str) -> str:
    return f"Hello, {name}!"
```

A `{python}` cell, by contrast, runs in a real kernel during the build; its
output is baked into the page and nothing runs in the reader's browser:

```{python}
print("This ran at build time.")
```

## Next steps {#sec-next}

Build this page with `feynman build <this-file>`, then keep writing. See
@lst-example above, and the demo for every capability:
<https://feynman.yesilkaya.dev/>.

<!-- More building blocks (each shown in context in the demo):
     callout box:   ::: box {type=info title="Note"} … :::
     visualisation: ::: viz {type=grid rows=8 cols=8 steps=12 #viz-x} … :::
     embed an SVG:  ::: figure {src=figures/diagram.svg theme=auto #fig-x} … :::
     cell options:  #| echo: false   #| output: false   #| label: fig-x
     Draw a figure in the browser with:  feynman draw -->
"""

MINIMAL_TEMPLATE = """\
---
title: {{title}}
---

## {{title}}

Start writing here.
"""


def _title_from_stem(stem: str) -> str:
    """Turn a filename stem into a sentence-case title.

    ``my-first-post`` -> ``My first post``. Hyphens and underscores become
    spaces; only the first letter is capitalised (the demo's house style).
    """
    words = stem.replace("-", " ").replace("_", " ").split()
    if not words:
        return "Untitled"
    text = " ".join(words)
    return text[0].upper() + text[1:]


def init_document(dest: Path, *, force: bool = False, minimal: bool = False) -> Path:
    """Write a starter document at ``dest``; return the written path.

    The title is derived from ``dest``'s filename. Missing parent directories
    are created. Raises :class:`FileExistsError` if ``dest`` already exists and
    ``force`` is false -- so the default never clobbers an author's work.
    """
    dest = Path(dest)
    if dest.exists() and not force:
        raise FileExistsError(str(dest))
    template = MINIMAL_TEMPLATE if minimal else STARTER_TEMPLATE
    content = template.replace(_TITLE, _title_from_stem(dest.stem))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    return dest
