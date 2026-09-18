"""Tests for the optional execution backend (``feynman[exec]``).

The Jupyter stack (nbclient / nbformat / ipykernel) is an optional extra. These
tests confirm that:

- ``feynman.execute`` imports without it (no eager Jupyter import);
- a plain Markdown build (no ``{python}`` cells) works without it; and
- a document with ``{python}`` cells raises an actionable error when it is
  missing.

To simulate a minimal install we block the backend modules in ``sys.modules``
(setting an entry to ``None`` makes ``import`` raise ``ImportError``), so these
run whether or not the extra is actually installed.
"""

from __future__ import annotations

import builtins
import sys

import pytest

from feynman import execute
from feynman.build import build_document
from feynman.execute import ExecutionUnavailableError, execute_cells


@pytest.fixture
def backend_missing(monkeypatch):
    """Make ``import nbformat`` / ``import nbclient`` fail, as on a minimal install."""
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name in ("nbformat", "nbclient") or name.startswith(("nbformat.", "nbclient.")):
            raise ImportError(f"blocked {name} for test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    # Drop any cached backend modules so the blocked import path is exercised.
    for mod in list(sys.modules):
        if mod == "nbformat" or mod.startswith(("nbformat.", "nbclient")):
            monkeypatch.delitem(sys.modules, mod, raising=False)
    yield


def test_execute_module_imports_without_backend():
    # The module itself must import with no Jupyter dependency; the symbols the
    # renderer needs (CellResult, execute_cells) are importable regardless.
    assert hasattr(execute, "CellResult")
    assert callable(execute.execute_cells)


def test_no_cells_needs_no_backend(backend_missing):
    # An empty cell list must short-circuit before touching the backend.
    assert execute_cells([]) == []


def test_cells_without_backend_raise_actionable_error(backend_missing):
    with pytest.raises(ExecutionUnavailableError) as exc:
        execute_cells(["print('hi')"])
    msg = str(exc.value)
    assert "feynman[exec]" in msg
    assert "pip install" in msg


def test_plain_markdown_builds_without_backend(backend_missing, tmp_path):
    src = tmp_path / "plain.md"
    src.write_text(
        "---\ntitle: Plain\n---\n\nJust prose and $x^2$, no code cells.\n",
        encoding="utf-8",
    )
    out = tmp_path / "out"
    html_path = build_document(src, out)  # must not raise
    html = html_path.read_text(encoding="utf-8")
    assert "<math" in html  # math still builds without the exec backend


def test_doc_with_cell_without_backend_raises(backend_missing, tmp_path):
    src = tmp_path / "coded.md"
    src.write_text(
        "---\ntitle: Coded\n---\n\n```{python}\nprint('hi')\n```\n",
        encoding="utf-8",
    )
    with pytest.raises(ExecutionUnavailableError):
        build_document(src, tmp_path / "out")
