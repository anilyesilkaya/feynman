"""Unit tests for the local-asset collector."""

from __future__ import annotations

import base64

from feynman.collect import MEDIA_DIR, AssetCollector

# A tiny valid 1x1 PNG.
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4"
    "2mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def _make_source(tmp_path):
    (tmp_path / "figures").mkdir()
    (tmp_path / "figures" / "plot.png").write_bytes(_PNG)


def test_remote_and_data_refs_pass_through(tmp_path):
    c = AssetCollector(tmp_path, tmp_path / "out", inline=False)
    for ref in (
        "https://example.com/x.png",
        "http://example.com/x.png",
        "//cdn/x.png",
        "data:image/png;base64,AAAA",
        "/site-absolute.png",
    ):
        assert c.resolve(ref) == ref
    assert c.copied == [] and c.missing == []


def test_missing_file_recorded_and_unchanged(tmp_path):
    c = AssetCollector(tmp_path, tmp_path / "out", inline=False)
    assert c.resolve("nope.png") == "nope.png"
    assert c.missing == ["nope.png"]


def test_portable_copies_into_media(tmp_path):
    _make_source(tmp_path)
    out = tmp_path / "out"
    c = AssetCollector(tmp_path, out, inline=False)
    rewritten = c.resolve("figures/plot.png")
    assert rewritten.startswith(f"{MEDIA_DIR}/")
    assert rewritten.endswith("-plot.png")
    copied = list((out / MEDIA_DIR).glob("*.png"))
    assert len(copied) == 1
    assert copied[0].read_bytes() == _PNG


def test_portable_dedupes_repeated_ref(tmp_path):
    _make_source(tmp_path)
    out = tmp_path / "out"
    c = AssetCollector(tmp_path, out, inline=False)
    first = c.resolve("figures/plot.png")
    second = c.resolve("figures/plot.png")
    assert first == second
    # Same file resolves to the same name; copied twice but to one destination.
    assert len(list((out / MEDIA_DIR).glob("*.png"))) == 1


def test_inline_embeds_data_uri(tmp_path):
    _make_source(tmp_path)
    c = AssetCollector(tmp_path, tmp_path / "out", inline=True)
    rewritten = c.resolve("figures/plot.png")
    assert rewritten.startswith("data:image/png;base64,")
    payload = rewritten.split(",", 1)[1]
    assert base64.b64decode(payload) == _PNG
    # Inline mode writes nothing to disk.
    assert not (tmp_path / "out" / MEDIA_DIR).exists()


def test_query_and_fragment_stripped(tmp_path):
    _make_source(tmp_path)
    c = AssetCollector(tmp_path, tmp_path / "out", inline=True)
    rewritten = c.resolve("figures/plot.png?v=2#frag")
    assert rewritten.startswith("data:image/png;base64,")
    assert c.missing == []
