"""A shared diagnostic sink, with an optional ``--strict`` mode.

Build-time problems (invalid YAML, an unknown directive option, a missing asset,
a duplicate label, a dangling cross-reference, an unexpected cell traceback) were
reported as ad-hoc ``print(..., file=sys.stderr)`` strings scattered across the
pipeline, with no way to make them fatal. This module funnels them through one
sink so the wording stays consistent, a source path / line can ride along, and a
caller can choose to fail the build on any of them.

Call :func:`warn` from anywhere in the pipeline. By default it prints to stderr
exactly as before (``warning: ...``) and never changes the exit status, so an
ordinary build is unaffected. Wrap a build in a :func:`session` to collect the
diagnostics; a *strict* session treats every diagnostic as fatal, and the CLI
turns that into a nonzero exit. The active session is held in a
:class:`~contextvars.ContextVar`, so no pipeline function needs a new argument.
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Diagnostic:
    """One reported problem: its message, and where it came from if known."""

    level: str  # "warning" (today's only level; strict makes them all fatal)
    message: str
    source: str | None = None  # path of the offending document, if known
    line: int | None = None  # 1-based line within that source, if known

    def format(self) -> str:
        """Render as ``[level]: [source][:line]: message`` for stderr."""
        where = ""
        if self.source:
            where = self.source if self.line is None else f"{self.source}:{self.line}"
            where = f"{where}: "
        return f"{self.level}: {where}{self.message}"


@dataclass
class DiagnosticCollector:
    """Accumulates diagnostics, printing each as it arrives (unless silenced).

    ``strict`` does not change what is printed; it only means :meth:`should_fail`
    returns true once any diagnostic has been reported, so a caller can exit
    nonzero. A non-strict collector never asks the build to fail -- preserving the
    long-standing warn-and-continue behaviour.
    """

    strict: bool = False
    echo: bool = True  # print to stderr as diagnostics arrive
    items: list[Diagnostic] = field(default_factory=list)

    def add(self, diagnostic: Diagnostic) -> None:
        self.items.append(diagnostic)
        if self.echo:
            print(diagnostic.format(), file=sys.stderr)

    def should_fail(self) -> bool:
        """True if this (strict) run reported anything the caller should fail on."""
        return self.strict and bool(self.items)


# The sink used when no session is active: prints, records nothing, never fatal.
# This is what an ordinary ``build_document`` call outside the CLI hits, so
# library use is unchanged.
_DEFAULT = DiagnosticCollector(strict=False)
_active: ContextVar[DiagnosticCollector] = ContextVar("feynman_diagnostics", default=_DEFAULT)


def current() -> DiagnosticCollector:
    """Return the collector for the active session (or the default sink)."""
    return _active.get()


def warn(message: str, *, source: str | Path | None = None, line: int | None = None) -> None:
    """Report a build-time problem at ``warning`` level (fatal only under strict)."""
    src = str(source) if source is not None else None
    current().add(Diagnostic(level="warning", message=message, source=src, line=line))


@contextmanager
def session(*, strict: bool = False):
    """Install a fresh collector for the duration of a build; yield it.

    Use in the CLI so ``--strict`` can turn reported problems into a nonzero exit:

        with diagnostics.session(strict=args.strict) as diags:
            build_document(...)
        if diags.should_fail():
            return 1
    """
    collector = DiagnosticCollector(strict=strict)
    token = _active.set(collector)
    try:
        yield collector
    finally:
        _active.reset(token)
