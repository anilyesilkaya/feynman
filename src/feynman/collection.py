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

from feynman import build, crossref, diagnostics, manifest, render
from feynman.parse import meta_text, split_front_matter

# Front-matter key that keeps a post out of the build entirely.
DRAFT_KEY = "draft"
# Front-matter key giving a chapter's position in a book (lower reads first).
# Chapters without it sort last, in a stable filename order.
ORDER_KEY = "order"
SEARCH_INDEX_NAME = "search-index.json"
LISTING_NAME = "index.html"
# The book's spanning table of contents / entry page.
CONTENTS_NAME = "contents.html"
# Source stems whose generated page would collide with a builder's own artefact.
# A source named e.g. ``index.md`` is reported and skipped, not silently clobbered.
_RESERVED_STEMS = {"index", "search-index", "contents"}
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


@dataclass
class Post:
    """One built post's metadata, as it appears in the index and the listing.

    The fields mirror the front-matter keys the page templates read, so a card on
    the listing shows the same credits and tags as the post it links to.
    """

    url: str
    title: str
    subtitle: str = ""
    date: str = ""
    authors: str = ""
    tags: list[str] = field(default_factory=list)
    text: str = ""

    def index_record(self) -> dict:
        """The (id-less) record shape stored in ``search-index.json``."""
        return {
            "url": self.url,
            "title": self.title,
            "subtitle": self.subtitle,
            "date": self.date,
            "authors": self.authors,
            "tags": self.tags,
            "text": self.text,
        }


@dataclass
class SiteResult:
    """What :func:`build_all` produced: the pages plus the two site artefacts."""

    pages: list[Path] = field(default_factory=list)
    index: Path | None = None
    listing: Path | None = None
    skipped: list[Path] = field(default_factory=list)  # drafts
    books: list[Path] = field(default_factory=list)  # contents pages of built books


def _is_draft(meta: dict) -> bool:
    value = meta.get(DRAFT_KEY, False)
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1"}
    return bool(value)


def _discover_sources(source_dir: Path, out_dir: Path) -> list[Path]:
    """Prepare ``out_dir`` and return the ``*.md`` files under ``source_dir``.

    Shared by both multi-document builders: coerces the paths, creates the
    output directory, and returns the (filename-sorted, non-recursive) sources,
    warning when the folder holds none.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    sources = sorted(p for p in source_dir.glob("*.md") if p.is_file())
    if not sources:
        diagnostics.warn(f"no .md files found in {source_dir}")
    return sources


def _discover_books(source_dir: Path) -> list[Path]:
    """Return sub-directories of ``source_dir`` that hold ``*.md`` chapters.

    A collection folder can contain *books*: a subfolder of chapter files that
    :func:`build_all` builds as an interconnected book (into ``out/<name>/``) and
    surfaces as one card on the listing. Any immediate subdirectory with at least
    one top-level ``*.md`` qualifies; asset folders (``media``, ``figures``, a
    nested ``_site``) hold no Markdown and are skipped naturally.
    """
    return sorted(
        d
        for d in source_dir.iterdir()
        if d.is_dir() and any(d.glob("*.md"))
    )


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
    sources = _discover_sources(source_dir, out_dir)

    result = SiteResult()
    posts: list[Post] = []
    css_layers: set[str] = set()
    owned: list[Path] = []  # every file this build produces, for manifest reconcile
    # (path, html) pairs held back until every page has rendered; see the strict
    # gate below the loop.
    pending_pages: list[tuple[Path, str]] = []

    for source in sources:
        # A source whose stem would overwrite a generated artefact (index.html,
        # search-index.json, contents.html) is reported and skipped, never
        # silently clobbered by the listing written after this loop.
        if source.stem in _RESERVED_STEMS:
            print(
                f"error: {source.name}: '{source.stem}' is a reserved name in a "
                f"collection (it would overwrite the generated {source.stem} page); "
                f"rename the file.",
                file=sys.stderr,
            )
            result.skipped.append(source)
            continue

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
        # Buffered, not written here: under ``--strict`` a diagnostic from *any*
        # page must stop the whole site from publishing, and a page rendered
        # before the offending one would otherwise already be on disk. The
        # deferred writes happen together at the end of the build.
        pending_pages.append((out_html, page.html))
        result.pages.append(out_html)
        owned.extend([out_html, *page.media])
        css_layers.update(page.css_files)

        posts.append(
            Post(
                url=out_html.name,
                title=meta_text(page.meta.get("title")) or source.stem,
                subtitle=meta_text(page.meta.get("subtitle")),
                date=meta_text(page.meta.get("date")),
                authors=meta_text(page.meta.get("authors")),
                # Same resolution the page templates use, so a post tagged with
                # either `tags` or the older `keywords` lists and searches alike.
                tags=build.doc_tags(page.meta),
                text=html_to_text(page.body),
            )
        )

    # Books: each subfolder of chapters becomes its own interconnected book under
    # out/<name>/ and one card on this listing linking to its contents page. A
    # book carries no date, so it lists among the undated entries. Its card text
    # is the chapter titles/subtitles, so a search for a chapter name finds it.
    for book_dir in _discover_books(source_dir):
        # The book sits one level down (out/<name>/), so its contents page links
        # Home up to this collection's listing at the site root.
        book = build_book(
            book_dir, out_dir / book_dir.name, home_url=f"../{LISTING_NAME}"
        )
        if not book.pages:
            continue  # empty subfolder: build_book already warned
        result.books.append(book.contents)
        chapter_text = " ".join(
            f"{c.title} {c.subtitle}".strip() for c in book.chapters
        )
        posts.append(
            Post(
                url=f"{book_dir.name}/{CONTENTS_NAME}",
                title=book.title,
                subtitle=f"A {len(book.chapters)}-chapter book.",
                tags=["book"],
                text=chapter_text,
            )
        )

    # List dated posts (newest first) before undated ones. Dates are free-form
    # front-matter strings (authors write "2026-09-16" or "16 September 2026"),
    # so this only truly orders ISO-style dates; mixed formats fall into a
    # stable, best-effort order rather than a guaranteed chronology. sorted() is
    # stable, so we sort undated-last first, then dated-descending on top of it.
    posts.sort(key=lambda p: p.date, reverse=True)
    posts.sort(key=lambda p: p.date == "")

    # Strict gate: every page (and every nested book) has now rendered, so this
    # is the last moment before the site lands on disk. Bail with the result so
    # far -- the CLI reports the diagnostics and exits nonzero -- rather than
    # publishing a site we have already diagnosed as broken.
    if diagnostics.should_abort():
        return result
    for path, html in pending_pages:
        path.write_text(html, encoding="utf-8")

    result.index = _write_index(out_dir, posts)
    result.listing = _write_listing(
        out_dir,
        posts,
        title=title or source_dir.resolve().name or "Posts",
        tagline=tagline or "Ideas, made understandable.",
    )
    owned.extend([result.index, result.listing])

    # Shared sidecar assets, written once. Include every theme layer any post
    # used, plus the MiniSearch runtime the listing page loads.
    layers = tuple(dict.fromkeys([build.BASE_CSS, *sorted(css_layers - {build.BASE_CSS})]))
    build.write_shared_assets(out_dir, layers)
    (out_dir / build.SEARCH_JS).write_text(
        build._asset_text(build.SEARCH_JS), encoding="utf-8"
    )

    # Reclaim stale pages/media/index from a prior build of this collection --
    # posts newly marked draft, deleted, or renamed. Shared sidecar assets are
    # overwritten in place and not tracked. Nested books own their own subfolder
    # manifests. This build owns the whole flat file set at the site root.
    manifest.reconcile(out_dir, "collection", owned)

    return result


def _write_index(out_dir: Path, posts: list[Post]) -> Path:
    """Write ``search-index.json``: the docs the client feeds to MiniSearch."""
    payload = {
        "generator": "feynman",
        # MiniSearch indexes these fields; the client stores the rest for display.
        # A list field indexes fine: MiniSearch stringifies it and then splits on
        # punctuation, so ``["signals", "dsp"]`` yields both terms.
        "fields": ["title", "subtitle", "tags", "authors", "text"],
        "storeFields": ["url", "title", "subtitle", "date", "authors", "tags"],
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
        nav={},
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


# ---------------------------------------------------------------------------
# Book: an ordered, interconnected collection.
#
# Where ``build_all`` produces a flat, search-first collection (posts sorted
# newest-first, no inherent order), a *book* is the opposite model over the same
# kind of folder: chapters read in an authored sequence, number per-chapter
# ("Figure 3.2"), cross-reference across files, and carry prev/next navigation
# plus a spanning contents page. The mechanism is a two-pass build -- collect
# every chapter's cross-reference targets into one book-wide map, then render
# each chapter against that map so a reference can resolve into another chapter.
# ---------------------------------------------------------------------------


@dataclass
class Chapter:
    """One book chapter: its source, its resolved order, and output URL."""

    source: Path
    number: int  # 1-based position in reading order
    url: str  # output filename, e.g. "intro.html"
    title: str = ""
    subtitle: str = ""


@dataclass
class BookResult:
    """What :func:`build_book` produced: the chapter pages and contents page."""

    pages: list[Path] = field(default_factory=list)
    contents: Path | None = None
    skipped: list[Path] = field(default_factory=list)  # drafts
    title: str = ""  # resolved book title (for a listing card)
    chapters: list["Chapter"] = field(default_factory=list)


def _title_from_dirname(source_dir: Path) -> str:
    """A human title from a folder name: ``signal-processing`` -> ``Signal Processing``."""
    return source_dir.resolve().name.replace("-", " ").replace("_", " ").title()


def _order_key(meta: dict, fallback: str) -> tuple[int, object, str]:
    """Sort key for a chapter: explicit ``order:`` first, then filename.

    Chapters with an ``order:`` come first (in ascending numeric order); those
    without sort after, in stable filename order. A non-integer ``order`` is
    treated as absent so a typo cannot crash the build.
    """
    raw = meta.get(ORDER_KEY)
    try:
        return (0, int(raw), fallback)
    except (TypeError, ValueError):
        return (1, 0, fallback)


def build_book(
    source_dir: Path,
    out_dir: Path,
    *,
    title: str = "",
    tagline: str = "",
    home_url: str | None = None,
) -> BookResult:
    """Build a folder of ``*.md`` chapters into an interconnected book.

    Chapters are ordered by their front-matter ``order:`` key (filename order as
    a tiebreak / fallback), numbered from 1, and rendered with the ``book``
    theme's chapter chrome. Cross-references resolve *across* chapters -- a
    ``@fig-bars`` pointing into chapter 3 renders "Figure 3.2" linking to
    ``chapter-3.html#fig-bars`` -- and each chapter gains prev/next navigation.
    A ``contents.html`` entry page lists every chapter in reading order.

    Drafts (truthy ``draft:``) are excluded. Like :func:`build_all`, this always
    writes a portable folder: cross-file references are incompatible with a
    single ``--inline`` file.

    ``home_url`` gives the contents page a Home button pointing up to a parent
    collection (e.g. ``../index.html`` when :func:`build_all` nests a book in a
    site). A standalone book leaves it ``None`` and shows no Home button.
    """
    source_dir = Path(source_dir)
    out_dir = Path(out_dir)
    sources = _discover_sources(source_dir, out_dir)

    result = BookResult()

    # Discover non-draft chapters and settle reading order before numbering. The
    # source text read here is kept and reused for pass-1 parsing (pass 2 reads
    # again inside render_page, which owns its own pipeline).
    ordered: list[tuple[Path, dict, str]] = []
    for source in sources:
        # A chapter named contents.md would overwrite the generated contents page.
        if source.stem in _RESERVED_STEMS:
            print(
                f"error: {source.name}: '{source.stem}' is a reserved name in a book "
                f"(it would overwrite the generated {source.stem} page); rename the file.",
                file=sys.stderr,
            )
            result.skipped.append(source)
            continue
        text = source.read_text(encoding="utf-8")
        meta = split_front_matter(text).meta or {}
        if _is_draft(meta):
            result.skipped.append(source)
            continue
        ordered.append((source, meta, text))
    ordered.sort(key=lambda sm: _order_key(sm[1], sm[0].stem))

    chapters = [
        Chapter(
            source=source,
            number=i + 1,
            url=f"{source.stem}.html",
            title=meta_text(meta.get("title")) or source.stem,
            subtitle=meta_text(meta.get("subtitle")),
        )
        for i, (source, meta, _text) in enumerate(ordered)
    ]

    # Pass 1: number every chapter's targets into one book-wide map, so a
    # reference in any chapter can resolve to a target owned by another. Keep
    # each chapter's tokens for the dangling-reference check, which can only run
    # once the whole book's targets are known (a ref may resolve cross-file).
    book_targets: dict[str, crossref.Target] = {}
    chapter_tokens: list[tuple[Chapter, list]] = []
    for chapter, (_src, _meta, text) in zip(chapters, ordered):
        _, _, tokens = render.parse_document(text, source=str(chapter.source))
        chapter_tokens.append((chapter, tokens))
        targets, warnings = crossref.collect_targets(
            tokens, chapter=chapter.number, chapter_url=chapter.url
        )
        for warning in warnings:
            diagnostics.warn(warning, source=str(chapter.source))
        for label, target in targets.items():
            if label in book_targets:
                owner = book_targets[label].chapter_url
                diagnostics.warn(
                    f"duplicate cross-reference label {label!r} in "
                    f"{chapter.url} (already defined in {owner}); first wins.",
                    source=str(chapter.source),
                )
                continue
            book_targets[label] = target

    # A reference resolving to no target anywhere in the book is dangling; warn
    # per chapter against the completed book-wide map (render_document skips its
    # own per-document check when a book map is supplied).
    for chapter, tokens in chapter_tokens:
        for warning in crossref.dangling_ref_warnings(tokens, book_targets):
            diagnostics.warn(warning, source=str(chapter.source))

    # Pass 2: render each chapter against the book-wide map, with prev/next nav.
    css_layers: set[str] = set()
    owned: list[Path] = []
    # Chapters are buffered so ``--strict`` can refuse to publish a half-book: a
    # diagnostic in chapter 4 must not leave chapters 1-3 on disk.
    pending_pages: list[tuple[Path, str]] = []
    for i, chapter in enumerate(chapters):
        nav = {}
        if i > 0:
            nav["prev"] = chapters[i - 1]
        if i < len(chapters) - 1:
            nav["next"] = chapters[i + 1]

        page = build.render_page(
            chapter.source,
            out_dir,
            inline=False,
            home_url=CONTENTS_NAME,
            targets=book_targets,
            current_url=chapter.url,
            nav=nav,
            chapter=chapter.number,
        )
        out_html = out_dir / chapter.url
        pending_pages.append((out_html, page.html))
        result.pages.append(out_html)
        owned.extend([out_html, *page.media])
        css_layers.update(page.css_files)

    # Strict gate: every chapter has rendered and emitted its diagnostics, so
    # stop here rather than publishing a book we know is broken. ``result.pages``
    # is already populated, so the CLI reports the diagnostics and exits nonzero
    # instead of "no chapters built".
    if diagnostics.should_abort():
        return result
    for path, html in pending_pages:
        path.write_text(html, encoding="utf-8")

    book_title = title or _title_from_dirname(source_dir) or "Contents"
    result.title = book_title
    result.chapters = chapters
    result.contents = _write_contents(
        out_dir,
        chapters,
        title=book_title,
        tagline=tagline or "Read cover to cover.",
        home_url=home_url,
    )
    owned.append(result.contents)

    # Shared sidecar assets: base CSS + every theme layer any chapter used. The
    # book theme lives in css_layers because chapters set ``style: book``.
    layers = tuple(dict.fromkeys([build.BASE_CSS, *sorted(css_layers - {build.BASE_CSS})]))
    build.write_shared_assets(out_dir, layers)

    # Reclaim stale chapter pages/media from a prior build (chapters deleted,
    # renamed, or newly drafted). Shared sidecar assets are not tracked.
    manifest.reconcile(out_dir, "book", owned)

    return result


def _write_contents(
    out_dir: Path,
    chapters: list[Chapter],
    *,
    title: str,
    tagline: str,
    home_url: str | None = None,
) -> Path:
    """Render the book's spanning contents page into ``contents.html``."""
    template = build._ENV.get_template("contents.html.j2")
    html = template.render(
        title=title,
        theme="light",
        style="book",
        subtitle="",
        tagline=tagline,
        kicker="Table of contents",
        hero_title=title,
        home_url=home_url,
        source_url="",
        # The template reads chapter.number/url/title/subtitle as attributes,
        # which resolve directly against the Chapter dataclass.
        chapters=chapters,
        nav={},
        inline=False,
        assets={
            "css": [
                {"href": build.BASE_CSS},
                {"href": "theme-book.css"},
            ],
            "pygments": {"href": build.PYGMENTS_CSS_NAME},
            "js": {"href": "feynman.js"},
        },
    )
    path = out_dir / CONTENTS_NAME
    path.write_text(html, encoding="utf-8")
    return path
