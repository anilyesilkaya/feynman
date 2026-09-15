"""Command-line interface: ``feynman build <doc.md> [-o out/]``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from feynman import __version__
from feynman.build import build_document


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

    args = parser.parse_args(argv)

    if args.command == "build":
        if not args.source.is_file():
            print(f"error: no such file: {args.source}", file=sys.stderr)
            return 2
        out_html = build_document(args.source, args.out, inline=args.inline)
        print(f"built {out_html}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
