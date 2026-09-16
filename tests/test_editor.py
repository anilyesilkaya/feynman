"""Tests for the ``feynman draw`` editor server.

Most tests run against a *fake* editor directory (a minimal ``index.html`` +
stub ``js/main.js``) so they need no submodule checkout; ``_editor_traversable``
is monkeypatched to point at it. One integration test uses the real vendored
editor and is skipped when the submodule is absent.
"""

from __future__ import annotations

import threading
import urllib.request
from importlib import resources

import pytest

from feynman import cli, editor


@pytest.fixture
def fake_editor(tmp_path, monkeypatch):
    """A minimal on-disk editor dir, wired in via ``_editor_traversable``."""
    (tmp_path / "index.html").write_text(
        '<!doctype html><html><body>'
        '<svg id="canvas"></svg>'
        '<script type="module" src="js/main.js"></script>'
        "</body></html>",
        encoding="utf-8",
    )
    (tmp_path / "js").mkdir()
    (tmp_path / "js" / "main.js").write_text("console.log('stub');\n", encoding="utf-8")
    monkeypatch.setattr(editor, "_editor_traversable", lambda: tmp_path)
    return tmp_path


def _serve_in_thread(server):
    """Run ``server.serve_forever`` on a daemon thread; return the thread."""
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread


# --- P0: parsing / errors (no server) --------------------------------------
def test_cli_parses_draw(monkeypatch):
    calls = {}
    monkeypatch.setattr(cli, "serve_editor", lambda **kw: calls.update(kw))
    assert cli.main(["draw", "--no-browser", "--port", "0"]) == 0
    assert calls == {"port": 0, "open_browser": False}


def test_draw_defaults(monkeypatch):
    calls = {}
    monkeypatch.setattr(cli, "serve_editor", lambda **kw: calls.update(kw))
    assert cli.main(["draw"]) == 0
    assert calls == {"port": editor.DEFAULT_PORT, "open_browser": True}


def test_missing_editor_dir_raises(tmp_path, monkeypatch):
    # Point at an empty dir: index.html is absent.
    monkeypatch.setattr(editor, "_editor_traversable", lambda: tmp_path)
    with pytest.raises(editor.EditorUnavailableError, match="git submodule update"):
        editor.serve_editor(open_browser=False)


def test_missing_editor_dir_cli_returns_2(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(editor, "_editor_traversable", lambda: tmp_path)
    assert cli.main(["draw", "--no-browser"]) == 2
    assert "error:" in capsys.readouterr().err


class _InstantServer:
    """A stand-in whose ``serve_forever`` returns at once, so ``serve_editor``
    runs to completion without blocking. Supports the ``with`` protocol."""

    server_address = ("127.0.0.1", 0)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def serve_forever(self):
        return None


@pytest.mark.parametrize("open_browser", [True, False])
def test_open_browser_flag_honoured(fake_editor, monkeypatch, open_browser):
    opened = []
    monkeypatch.setattr(editor.webbrowser, "open", lambda url: opened.append(url))
    monkeypatch.setattr(editor, "_make_server", lambda port, directory: _InstantServer())
    editor.serve_editor(open_browser=open_browser)
    assert bool(opened) is open_browser


# --- P1: functional serve (fake dir) ---------------------------------------
def _get(url):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.status, resp.headers.get("Content-Type", ""), resp.read()


def test_serves_index_200(fake_editor):
    server = editor._make_server(0, str(fake_editor))
    with server:
        _serve_in_thread(server)
        port = server.server_address[1]
        status, _ctype, body = _get(f"http://127.0.0.1:{port}/")
        server.shutdown()
    assert status == 200
    assert b'id="canvas"' in body


def test_js_served_as_javascript(fake_editor):
    # Regression guard: on Windows the mimetypes registry can map .js to
    # text/plain, which blocks ES-module execution. The handler pins it.
    server = editor._make_server(0, str(fake_editor))
    with server:
        _serve_in_thread(server)
        port = server.server_address[1]
        _status, ctype, _body = _get(f"http://127.0.0.1:{port}/js/main.js")
        server.shutdown()
    assert ctype.startswith("text/javascript")


# --- P2: real submodule (integration) --------------------------------------
def _real_editor_present() -> bool:
    return resources.files("feynman").joinpath("editor", "index.html").is_file()


@pytest.mark.skipif(
    not _real_editor_present(), reason="svg-canvas submodule not checked out"
)
def test_real_editor_dir_present():
    index = resources.files("feynman").joinpath("editor", "index.html").read_text(
        encoding="utf-8"
    )
    assert 'id="canvas"' in index
    assert '<script type="module" src="js/main.js">' in index
    assert resources.files("feynman").joinpath("editor", "js", "main.js").is_file()
