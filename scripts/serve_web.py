"""Serve browser assets with a portable MIME type for JavaScript modules."""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).parents[1]
WEB_DIRECTORY = ROOT / "web"


class BrowserAssetHandler(SimpleHTTPRequestHandler):
    """Static handler that serves ``.mjs`` consistently across platforms."""

    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".mjs": "text/javascript",
    }


def main() -> None:
    """Serve the prepared browser application on localhost port 8000."""

    handler = partial(BrowserAssetHandler, directory=WEB_DIRECTORY)
    server = ThreadingHTTPServer(("127.0.0.1", 8000), handler)
    print("Serving browser application at http://127.0.0.1:8000")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
