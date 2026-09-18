"""Command-line interface: ``feynman build <doc.md> [-o out/]``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from feynman import __version__, diagnostics
from feynman.build import build_document
from feynman.collection import build_all, build_book
from feynman.editor import DEFAULT_PORT, EditorUnavailableError, serve_editor
from feynman.scaffold import init_document


def _strict_flag(parser: argparse.ArgumentParser) -> None:
    """Add the shared ``--strict`` flag to a build sub-command."""
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat build diagnostics (invalid front matter, missing assets, "
        "dangling references, unexpected cell errors, ...) as errors: exit "
        "nonzero instead of warning and continuing.",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="feynman",
        description="Build interactive technical documents to static HTML.",
    )
    parser.add_argument("--version", action="version", version=f"feynman {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="Build a Markdown document to HTML.")
    build.add_argument("source", type=Path, help="Path to the .md document.")
    build.add_argument(
        "-o",
        "--out",
        type=Path,
        default=Path("_site"),
        help="Output directory (default: ./_site).",
    )
    build.add_argument(
        "--inline",
        "--single-file",
        dest="inline",
        action="store_true",
        help="Emit one self-contained HTML file (CSS, JS and images inlined) "
        "instead of a portable folder with sidecar assets.",
    )
    _strict_flag(build)

    build_all_parser = sub.add_parser(
        "build-all",
        help="Build a folder of .md documents into a searchable site.",
    )
    build_all_parser.add_argument(
        "source_dir",
        type=Path,
        help="Directory of .md documents to build (non-recursive).",
    )
    build_all_parser.add_argument(
        "-o",
        "--out",
        type=Path,
        default=Path("_site"),
        help="Output directory (default: ./_site).",
    )
    build_all_parser.add_argument(
        "--title",
        default="",
        help="Title of the search/listing page (default: the folder name).",
    )
    build_all_parser.add_argument(
        "--tagline",
        default="",
        help="Header tagline for the listing page.",
    )
    _strict_flag(build_all_parser)

    book_parser = sub.add_parser(
        "book",
        help="Build a folder of .md chapters into an ordered, interconnected book.",
    )
    book_parser.add_argument(
        "source_dir",
        type=Path,
        help="Directory of .md chapters to build (non-recursive).",
    )
    book_parser.add_argument(
        "-o",
        "--out",
        type=Path,
        default=Path("_site"),
        help="Output directory (default: ./_site).",
    )
    book_parser.add_argument(
        "--title",
        default="",
        help="Title of the contents page (default: the folder name).",
    )
    book_parser.add_argument(
        "--tagline",
        default="",
        help="Header tagline for the book.",
    )
    _strict_flag(book_parser)

    init = sub.add_parser(
        "init",
        help="Write a starter document to begin a new post.",
    )
    init.add_argument(
        "dest",
        type=Path,
        help="Path for the new .md document (its filename becomes the title).",
    )
    init.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Overwrite dest if it already exists.",
    )
    init.add_argument(
        "--minimal",
        action="store_true",
        help="Write only front matter and a heading, not the feature tour.",
    )

    draw = sub.add_parser(
        "draw",
        help="Open the bundled SVG editor in a browser to draw a figure.",
    )
    draw.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Local port to serve on (default: {DEFAULT_PORT}; 0 picks a free one).",
    )
    draw.add_argument(
        "--no-browser",
        dest="open_browser",
        action="store_false",
        help="Do not open a browser; print the URL only (useful in headless/CI).",
    )

    args = parser.parse_args(argv)

    if args.command == "build":
        if not args.source.is_file():
            print(f"error: no such file: {args.source}", file=sys.stderr)
            return 2
        with diagnostics.session(strict=args.strict) as diags:
            out_html = build_document(args.source, args.out, inline=args.inline)
        if diags.should_fail():
            print(
                f"error: build failed with {len(diags.items)} diagnostic(s) "
                f"under --strict",
                file=sys.stderr,
            )
            return 1
        print(f"built {out_html}")
        return 0

    if args.command == "build-all":
        if not args.source_dir.is_dir():
            print(f"error: no such directory: {args.source_dir}", file=sys.stderr)
            return 2
        with diagnostics.session(strict=args.strict) as diags:
            result = build_all(
                args.source_dir, args.out, title=args.title, tagline=args.tagline
            )
        if not result.pages and not result.books:
            print(f"error: no documents built from {args.source_dir}", file=sys.stderr)
            return 2
        if diags.should_fail():
            print(
                f"error: build failed with {len(diags.items)} diagnostic(s) "
                f"under --strict",
                file=sys.stderr,
            )
            return 1
        print(f"built {len(result.pages)} page(s) -> {args.out}")
        if result.books:
            print(f"built {len(result.books)} book(s)")
        if result.skipped:
            print(f"skipped {len(result.skipped)} draft(s)")
        print(f"search page: {result.listing}")
        return 0

    if args.command == "book":
        if not args.source_dir.is_dir():
            print(f"error: no such directory: {args.source_dir}", file=sys.stderr)
            return 2
        with diagnostics.session(strict=args.strict) as diags:
            result = build_book(
                args.source_dir, args.out, title=args.title, tagline=args.tagline
            )
        if not result.pages:
            print(f"error: no chapters built from {args.source_dir}", file=sys.stderr)
            return 2
        if diags.should_fail():
            print(
                f"error: build failed with {len(diags.items)} diagnostic(s) "
                f"under --strict",
                file=sys.stderr,
            )
            return 1
        print(f"built {len(result.pages)} chapter(s) -> {args.out}")
        if result.skipped:
            print(f"skipped {len(result.skipped)} draft(s)")
        print(f"contents page: {result.contents}")
        return 0

    if args.command == "init":
        try:
            dest = init_document(args.dest, force=args.force, minimal=args.minimal)
        except FileExistsError as exc:
            print(
                f"error: {exc} already exists (use --force to overwrite)",
                file=sys.stderr,
            )
            return 2
        print(f"wrote {dest}")
        print(f"next: feynman build {dest}")
        return 0

    if args.command == "draw":
        try:
            serve_editor(port=args.port, open_browser=args.open_browser)
        except EditorUnavailableError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
