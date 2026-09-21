"""Regression tests for safe output ownership (manifest-driven cleanup).

These lock in that a build reclaims only its *own* stale output and never
clobbers another document's files, author-placed files, or acts on an unsafe
manifest path. See :mod:`feynman.manifest`.
"""

from __future__ import annotations

import base64
import json

import pytest

from feynman import collection, manifest
from feynman.build import build_document

_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4"
    "2mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def _doc_with_image(dir_, stem, img_name):
    """Write ``<stem>.md`` referencing ``figures/<img_name>`` and return its path."""
    (dir_ / "figures").mkdir(exist_ok=True)
    (dir_ / "figures" / img_name).write_bytes(_PNG)
    src = dir_ / f"{stem}.md"
    src.write_text(
        f"---\ntitle: {stem}\n---\n\n![pic](figures/{img_name})\n", encoding="utf-8"
    )
    return src


# --- single-document builds sharing one output directory -------------------
def test_two_docs_one_dir_both_survive(tmp_path):
    out = tmp_path / "out"
    a = _doc_with_image(tmp_path, "alpha", "a.png")
    b = _doc_with_image(tmp_path, "beta", "b.png")

    build_document(a, out)
    build_document(b, out)

    # Both pages and both images survive: building beta must not wipe alpha's.
    assert (out / "alpha.html").exists()
    assert (out / "beta.html").exists()
    assert len(list((out / "media").glob("*.png"))) == 2


def test_rebuild_one_doc_leaves_the_other(tmp_path):
    out = tmp_path / "out"
    a = _doc_with_image(tmp_path, "alpha", "a.png")
    b = _doc_with_image(tmp_path, "beta", "b.png")
    build_document(a, out)
    build_document(b, out)

    # Rebuild alpha with its image removed. Its own image goes; beta's stays.
    a.write_text("---\ntitle: alpha\n---\n\nno image now\n", encoding="utf-8")
    build_document(a, out)

    imgs = {p.name for p in (out / "media").glob("*.png")}
    assert len(imgs) == 1  # only beta's image remains
    assert (out / "beta.html").exists()
    assert (out / "alpha.html").exists()


def test_own_stale_image_is_reclaimed(tmp_path):
    out = tmp_path / "out"
    a = _doc_with_image(tmp_path, "alpha", "a.png")
    build_document(a, out)
    assert list((out / "media").glob("*.png"))

    a.write_text("---\ntitle: alpha\n---\n\nno image\n", encoding="utf-8")
    build_document(a, out)
    # The doc's own orphaned image is gone, and the empty media dir is pruned.
    assert not (out / "media").exists()


def test_author_file_is_preserved(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    keep = out / "CNAME"
    keep.write_text("feynman.example.dev\n", encoding="utf-8")
    a = _doc_with_image(tmp_path, "alpha", "a.png")

    build_document(a, out)
    a.write_text("---\ntitle: alpha\n---\n\nno image\n", encoding="utf-8")
    build_document(a, out)

    # An untracked author file is never touched by reconciliation.
    assert keep.exists()
    assert keep.read_text(encoding="utf-8") == "feynman.example.dev\n"


# --- collection rebuilds ---------------------------------------------------
def _post(dir_, stem, body="Prose.", **meta):
    fm = "\n".join(f"{k}: {v}" for k, v in {"title": stem, **meta}.items())
    (dir_ / f"{stem}.md").write_text(f"---\n{fm}\n---\n\n{body}\n", encoding="utf-8")


def test_published_to_draft_removes_stale_page(tmp_path):
    src = tmp_path / "posts"
    src.mkdir()
    _post(src, "alpha")
    _post(src, "beta")
    out = tmp_path / "site"
    collection.build_all(src, out)
    assert (out / "beta.html").exists()

    # Mark beta a draft and rebuild: its stale page must be reclaimed.
    _post(src, "beta", draft="true")
    collection.build_all(src, out)
    assert not (out / "beta.html").exists()
    assert (out / "alpha.html").exists()


def test_deleted_doc_removes_stale_page(tmp_path):
    src = tmp_path / "posts"
    src.mkdir()
    _post(src, "alpha")
    _post(src, "beta")
    out = tmp_path / "site"
    collection.build_all(src, out)

    (src / "beta.md").unlink()
    collection.build_all(src, out)
    assert not (out / "beta.html").exists()
    assert (out / "alpha.html").exists()


def test_renamed_doc_removes_old_page(tmp_path):
    src = tmp_path / "posts"
    src.mkdir()
    _post(src, "alpha")
    out = tmp_path / "site"
    collection.build_all(src, out)
    assert (out / "alpha.html").exists()

    (src / "alpha.md").rename(src / "renamed.md")
    collection.build_all(src, out)
    assert not (out / "alpha.html").exists()
    assert (out / "renamed.html").exists()


# --- reserved-name collision -----------------------------------------------
def test_index_md_is_reported_not_overwritten(tmp_path, capsys):
    src = tmp_path / "posts"
    src.mkdir()
    _post(src, "index", body="My own index page.")
    _post(src, "alpha")
    out = tmp_path / "site"
    result = collection.build_all(src, out)

    err = capsys.readouterr().err
    assert "reserved name" in err
    assert "index" in err
    # index.md was skipped; the generated listing owns index.html.
    assert src / "index.md" in result.skipped
    assert (out / "index.html").exists()
    listing = (out / "index.html").read_text(encoding="utf-8")
    assert "My own index page." not in listing  # not the user's page
    assert "data-feynman-search" in listing  # it is the generated listing


def test_contents_md_reserved_in_book(tmp_path, capsys):
    src = tmp_path / "chapters"
    src.mkdir()
    _post(src, "contents", body="Not a real chapter.")
    _post(src, "01", body="Real chapter.")
    result = collection.build_book(src, tmp_path / "book")

    assert "reserved name" in capsys.readouterr().err
    assert src / "contents.md" in result.skipped


# --- manifest safety -------------------------------------------------------
def test_unsafe_manifest_paths_are_ignored(tmp_path):
    out = tmp_path / "out"
    a = _doc_with_image(tmp_path, "alpha", "a.png")
    build_document(a, out)

    # Poison the manifest with an absolute path and a traversal escape, plus a
    # backslash path. A rebuild must not attempt to delete any of them.
    outside = tmp_path / "outside.txt"
    outside.write_text("keep me", encoding="utf-8")
    data = json.loads((out / manifest.MANIFEST_NAME).read_text(encoding="utf-8"))
    data["owners"]["doc:alpha"] += [
        str(outside),
        "../outside.txt",
        "..\\outside.txt",
    ]
    (out / manifest.MANIFEST_NAME).write_text(json.dumps(data), encoding="utf-8")

    a.write_text("---\ntitle: alpha\n---\n\nno image\n", encoding="utf-8")
    build_document(a, out)  # must not raise, must not delete outside.txt
    assert outside.exists()
    assert outside.read_text(encoding="utf-8") == "keep me"


def test_corrupt_manifest_does_not_crash(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / manifest.MANIFEST_NAME).write_text("{not json", encoding="utf-8")
    a = _doc_with_image(tmp_path, "alpha", "a.png")
    # A corrupt manifest is treated as empty, not fatal.
    build_document(a, out)
    assert (out / "alpha.html").exists()


# --- relative output paths -------------------------------------------------
# A manifest entry must name a file the same way whichever spelling of ``-o`` the
# author used, or a rebuild reads its own past entries as files it no longer
# produces and deletes them. These pin that `-o out` and `-o /abs/out` are one
# output directory, since `feynman build` is normally run with the relative form.
def test_relative_out_dir_records_paths_relative_to_it(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _doc_with_image(tmp_path, "alpha", "a.png")
    build_document("alpha.md", "out")

    data = json.loads((tmp_path / "out" / manifest.MANIFEST_NAME).read_text("utf-8"))
    entries = data["owners"]["doc:alpha"]
    # Not "out/alpha.html": the prefix belongs to the output dir, not the entry.
    # (The image's name carries a hash of its absolute source path, so match its
    # folder rather than the generated basename.)
    assert "alpha.html" in entries
    assert [e for e in entries if e.startswith("media/") and e.endswith("-a.png")]
    assert not [e for e in entries if e.startswith("out/")]


def test_mixing_relative_and_absolute_out_keeps_the_page(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _doc_with_image(tmp_path, "alpha", "a.png")

    # The same document, the same output directory, spelled both ways.
    build_document("alpha.md", tmp_path / "out")
    build_document("alpha.md", "out")

    # The second build must not reclaim the page and image the first one wrote --
    # they are the very files it just rewrote.
    assert (tmp_path / "out" / "alpha.html").exists()
    assert list((tmp_path / "out" / "media").glob("*.png"))


def test_relative_out_dir_still_reclaims_its_own_stale_media(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    a = _doc_with_image(tmp_path, "alpha", "a.png")
    build_document("alpha.md", "out")
    assert list((tmp_path / "out" / "media").glob("*.png"))

    # Cleanup keeps working through a relative path: drop the reference and the
    # image goes, exactly as it does for an absolute one.
    a.write_text("---\ntitle: alpha\n---\n\nno image\n", encoding="utf-8")
    build_document("alpha.md", "out")
    assert not (tmp_path / "out" / "media").exists()
    assert (tmp_path / "out" / "alpha.html").exists()
