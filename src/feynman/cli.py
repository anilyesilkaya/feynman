"""Command-line interface: ``feynman build <doc.md> [-o out/]``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from feynman import __version__
from feynman.build import build_document
from feynman.editor import DEFAULT_PORT, EditorUnavailableError, serve_editor
from feynman.scaffold import init_document


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
        out_html = build_document(args.source, args.out, inline=args.inline)
        print(f"built {out_html}")
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
