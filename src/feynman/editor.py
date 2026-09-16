"""Serve the bundled svg-canvas editor over a local HTTP server.

svg-canvas is a zero-dependency, vanilla-JS SVG editor vendored as a git
submodule under ``editor/`` (a data directory, not an importable package). It
must be served over HTTP -- its ES-module imports will not load from a
``file://`` URL. This module launches a throwaway localhost server, opens a
browser, and serves the static files unchanged. Nothing is written back: the
author uses the editor's own Copy/Download to save an ``.svg``, then embeds it
with the :mod:`feynman.figures` ``:::figure`` directive.

The design is deliberately decoupled -- feynman only pins the submodule and
serves its files; there is no preload, save-back, or message bridge.
"""

from __future__ import annotations

import functools
import http.server
import webbrowser
from importlib import resources

# Fixed, memorable, unlikely-to-collide default. Override with --port (0 picks
# an ephemeral free port).
DEFAULT_PORT = 8737


class EditorUnavailableError(RuntimeError):
    """The bundled editor could not be located or served."""


class _EditorRequestHandler(http.server.SimpleHTTPRequestHandler):
    """``SimpleHTTPRequestHandler`` with a pinned MIME map.

    Overriding ``extensions_map`` makes ``.js`` serve as ``text/javascript``
    regardless of the host's ``mimetypes`` registry. On Windows the registry can
    map ``.js`` to ``text/plain``, which makes browsers refuse to execute
    ``main.js`` as an ES module and silently breaks the editor.
    """

    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".html": "text/html",
        ".css": "text/css",
        ".js": "text/javascript",
        ".mjs": "text/javascript",
        ".svg": "image/svg+xml",
        ".json": "application/json",
    }

    def log_message(self, *args):  # noqa: D102 - keep the console quiet
        # We print our own URL line; suppress the per-request access log.
        pass


def _editor_traversable():
    """Return a ``Traversable`` for the bundled editor directory.

    Anchored on the ``feynman`` package and joined to ``editor`` -- never
    ``files("feynman.editor")``, because ``editor/`` is intentionally not an
    importable (sub)package.
    """
    return resources.files("feynman").joinpath("editor")


def _require_editor():
    """Return the editor traversable, or raise if its files are missing."""
    editor = _editor_traversable()
    if not editor.joinpath("index.html").is_file():
        raise EditorUnavailableError(
            "the bundled SVG editor was not found.\n"
            "If you are working from a git checkout, initialise the submodule:\n"
            "    git submodule update --init src/feynman/editor\n"
            "If you installed feynman from a package, please report this -- the "
            "wheel was built without the editor assets."
        )
    return editor


def _make_server(port: int, directory: str) -> http.server.ThreadingHTTPServer:
    """Build a threading HTTP server bound to 127.0.0.1 serving ``directory``.

    A small seam so tests can read ``server_address`` and drive
    ``serve_forever``/``shutdown`` on a thread without racing on the port.
    ``ThreadingHTTPServer`` so the page's many asset requests (html + css + the
    JS modules) do not serialise. Binding to loopback keeps it local and avoids
    the Windows public-network firewall prompt in most configurations.
    """
    handler = functools.partial(_EditorRequestHandler, directory=directory)
    try:
        return http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    except OSError as exc:
        raise EditorUnavailableError(
            f"could not bind 127.0.0.1:{port} ({exc.strerror or exc}). "
            "Try a different --port (or --port 0 for an automatic one)."
        ) from exc


def serve_editor(*, port: int = DEFAULT_PORT, open_browser: bool = True) -> None:
    """Serve the bundled editor on 127.0.0.1 until interrupted.

    ``port=0`` picks an ephemeral port. Opens the URL in a browser unless
    ``open_browser`` is false. Runs until Ctrl+C, then returns cleanly.
    """
    editor = _require_editor()
    # Wrap the whole serve loop: for editable installs and unpacked wheels
    # as_file yields the real directory directly; for a zipped import it would
    # extract to a temp dir for the lifetime of this block.
    with resources.as_file(editor) as editor_path:
        httpd = _make_server(port, str(editor_path))
        with httpd:
            actual_port = httpd.server_address[1]
            url = f"http://127.0.0.1:{actual_port}/"
            print(f"serving the SVG editor at {url}")
            print("draw, then use Copy or Download to save a .svg. Ctrl+C to stop.")
            if open_browser:
                webbrowser.open(url)
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\nstopped.")
