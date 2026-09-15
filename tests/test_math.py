"""Unit tests for LaTeX -> MathML conversion, including the failure path."""

from __future__ import annotations

import feynman.math as math_mod
from feynman.math import to_mathml


def test_inline_math_is_mathml():
    out = to_mathml("x^2", display=False)
    assert "<math" in out
    assert 'display="block"' not in out


def test_display_math_forces_block():
    out = to_mathml("x^2", display=True)
    assert "<math" in out
    assert 'display="block"' in out


def test_conversion_failure_degrades_to_code(monkeypatch):
    # Force the converter to raise so we exercise the degradation path
    # deterministically, independent of latex2mathml's own quirks.
    def boom(*args, **kwargs):
        raise ValueError("nope")

    monkeypatch.setattr(math_mod, "_latex_to_mathml", boom)

    inline = to_mathml(r"\badcmd", display=False)
    assert 'class="math-error"' in inline
    assert "\\badcmd" in inline  # the escaped source rides along

    block = to_mathml(r"\badcmd", display=True)
    assert "math-error-block" in block
