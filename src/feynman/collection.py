"""Multi-document builder: a folder of posts -> a searchable site.

``feynman build`` turns one Markdown file into one HTML page. ``build_all``
walks a *folder* of posts, builds each one, and additionally emits the two
artefacts a collection needs that a single page cannot provide:

- ``search-index.json`` -- one compact record per post (title, subtitle, date,
  tags, author, url and the post's plain text), consumed client-side; and
- ``index.html`` -- a listing / search page (the ``search`` template) that lists
  every post and, with JavaScript, filters them live via the bundled MiniSearch.

Only portable output makes sense here: a cross-post index fetched at runtime is
fundamentally incompatible with ``--inline``'s single self-contained file, so
this builder always writes a portable folder with shared sidecar assets.

Search ranking (BM25, fuzzy matching) is built in the browser from the compact
index at load time rather than pre-serialised here: MiniSearch's on-disk format
is an internal detail, and building from a few hundred records is instant, so we
ship the smaller, stable JSON and let the client index it.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

from feynman import build
from feynman.parse import split_front_matter

# Front-matter key that keeps a post out of the build entirely.
DRAFT_KEY = "draft"
SEARCH_INDEX_NAME = "search-index.json"
LISTING_NAME = "index.html"
# Tags whose text content is machine data, not prose, and must not pollute the
# search index (viz payloads ride in <script type="application/json">).
_SKIP_TEXT_TAGS = {"script", "style"}


class _TextExtractor(HTMLParser):
    """Collect human-readable text from rendered body HTML, skipping data tags."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag in _SKIP_TEXT_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TEXT_TAGS and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._chunks.append(data)

    @property
    def text(self) -> str:
        # Collapse whitespace so the index is compact and word-based.
        return " ".join("".join(self._chunks).split())


def html_to_text(html: str) -> str:
    """Return the collapsed plain text of ``html`` (script/style stripped)."""
    parser = _TextExtractor()
    parser.feed(html)
    return parser.text


def _as_text(value: object) -> str:
    """Coerce a front-matter scalar (str/int/date) to a trimmed string."""
    return "" if value is None else str(value).strip()


@dataclass
class Post:
    """One built post's metadata, as it appears in the index and the listing."""

    url: str
    title: str
    subtitle: str = ""
    date: str = ""
    authors: str = ""
    keywords: str = ""
    text: str = ""

    def index_record(self) -> dict:
        """The (id-less) record shape stored in ``search-index.json``."""
        return {
            "url": self.url,
            "title": self.title,
            "subtitle": self.subtitle,
            "date": self.date,
            "authors": self.authors,
            "keywords": self.keywords,
            "text": self.text,
        }


@dataclass
class SiteResult:
    """What :func:`build_all` produced: the pages plus the two site artefacts."""

    pages: list[Path] = field(default_factory=list)
    index: Path | None = None
    listing: Path | None = None
    skipped: list[Path] = field(default_factory=list)  # drafts


def _is_draft(meta: dict) -> bool:
    value = meta.get(DRAFT_KEY, False)
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1"}
    return bool(value)


def build_all(
    source_dir: Path, out_dir: Path, *, title: str = "", tagline: str = ""
) -> SiteResult:
    """Build every ``*.md`` in ``source_dir`` into ``out_dir`` with search.

    Returns a :class:`SiteResult`. Posts with a truthy ``draft:`` front-matter
    key are skipped (built into neither the pages nor the index). Non-draft posts
    are listed newest-first on the ``index.html`` search page. ``title`` names the
    listing page (defaults to the folder name); ``tagline`` fills the header.
    """
    source_dir = Path(source_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    sources = sorted(p for p in source_dir.glob("*.md") if p.is_file())
    if not sources:
        print(f"warning: no .md files found in {source_dir}", file=sys.stderr)

    result = SiteResult()
    posts: list[Post] = []
    css_layers: set[str] = set()

    for source in sources:
        # Peek at front matter first so a draft never runs the pipeline.
        meta = split_front_matter(source.read_text(encoding="utf-8")).meta or {}
        if _is_draft(meta):
            result.skipped.append(source)
            continue

        # Each post's header gets a Home link back to the collection listing.
        page = build.render_page(
            source, out_dir, inline=False, home_url=LISTING_NAME
        )
        out_html = out_dir / f"{source.stem}.html"
        out_html.write_text(page.html, encoding="utf-8")
        result.pages.append(out_html)
        css_layers.update(page.css_files)

        posts.append(
            Post(
                url=out_html.name,
                title=_as_text(page.meta.get("title")) or source.stem,
                subtitle=_as_text(page.meta.get("subtitle")),
                date=_as_text(page.meta.get("date")),
                authors=_as_text(page.meta.get("authors")),
                keywords=_as_text(page.meta.get("keywords")),
                text=html_to_text(page.body),
            )
        )

    # List dated posts (newest first) before undated ones. Dates are free-form
    # front-matter strings (authors write "2026-09-16" or "16 September 2026"),
    # so this only truly orders ISO-style dates; mixed formats fall into a
    # stable, best-effort order rather than a guaranteed chronology. sorted() is
    # stable, so we sort undated-last first, then dated-descending on top of it.
    posts.sort(key=lambda p: p.date, reverse=True)
    posts.sort(key=lambda p: p.date == "")

    result.index = _write_index(out_dir, posts)
    result.listing = _write_listing(
        out_dir,
        posts,
        title=title or source_dir.resolve().name or "Posts",
        tagline=tagline or "Ideas, made understandable.",
    )

    # Shared sidecar assets, written once. Include every theme layer any post
    # used, plus the MiniSearch runtime the listing page loads.
    layers = tuple(dict.fromkeys([build.BASE_CSS, *sorted(css_layers - {build.BASE_CSS})]))
    build.write_shared_assets(out_dir, layers)
    (out_dir / build.SEARCH_JS).write_text(
        build._asset_text(build.SEARCH_JS), encoding="utf-8"
    )

    return result


def _write_index(out_dir: Path, posts: list[Post]) -> Path:
    """Write ``search-index.json``: the docs the client feeds to MiniSearch."""
    payload = {
        "generator": "feynman",
        # MiniSearch indexes these fields; the client stores the rest for display.
        "fields": ["title", "subtitle", "keywords", "authors", "text"],
        "storeFields": ["url", "title", "subtitle", "date", "authors", "keywords"],
        "docs": [{"id": i, **p.index_record()} for i, p in enumerate(posts)],
    }
    path = out_dir / SEARCH_INDEX_NAME
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _write_listing(out_dir: Path, posts: list[Post], *, title: str, tagline: str) -> Path:
    """Render the ``search`` template into ``index.html``."""
    template = build._ENV.get_template("search.html.j2")
    html = template.render(
        title=title,
        theme="light",
        style="notebook",
        subtitle="",
        tagline=tagline,
        kicker="",
        hero_title=title,
        source_url="",
        posts=[p.index_record() for p in posts],
        inline=False,
        # The listing is a plain notebook-themed page: base CSS + feynman.js only.
        assets={
            "css": [{"href": build.BASE_CSS}],
            "pygments": {"href": build.PYGMENTS_CSS_NAME},
            "js": {"href": "feynman.js"},
        },
    )
    path = out_dir / LISTING_NAME
    path.write_text(html, encoding="utf-8")
    return path
