import json
import re
from html.parser import HTMLParser
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from cobol_to_python import parse_program

ROOT = Path(__file__).parents[1]
WEB = ROOT / "web"


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.labels: set[str] = set()
        self.scripts: list[dict[str, str | None]] = []
        self.textareas: dict[str, dict[str, str | None]] = {}
        self._script_text: list[str] | None = None
        self.example_json = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        element_id = attributes.get("id")
        if element_id is not None:
            self.ids.add(element_id)
        if tag == "label" and attributes.get("for") is not None:
            self.labels.add(attributes["for"] or "")
        if tag == "textarea" and element_id is not None:
            self.textareas[element_id] = attributes
        if tag == "script":
            self.scripts.append(attributes)
            if element_id == "examples":
                self._script_text = []

    def handle_data(self, data: str) -> None:
        if self._script_text is not None:
            self._script_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._script_text is not None:
            self.example_json = "".join(self._script_text)
            self._script_text = None


def page() -> tuple[str, PageParser]:
    markup = (WEB / "index.html").read_text(encoding="utf-8")
    parser = PageParser()
    parser.feed(markup)
    return markup, parser


def test_static_assets_are_local_and_present() -> None:
    markup, parser = page()

    assert (WEB / "styles.css").is_file()
    assert (WEB / "app.js").is_file()
    assert 'href="styles.css"' in markup
    assert any(script.get("src") == "app.js" for script in parser.scripts)
    assert not re.search(r'(?:src|href)="https?://', markup)


def test_preview_server_uses_javascript_mime_type_for_modules() -> None:
    spec = spec_from_file_location("serve_web", ROOT / "scripts" / "serve_web.py")
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.BrowserAssetHandler.extensions_map[".mjs"] == "text/javascript"


def test_workspace_has_accessible_controls_and_status() -> None:
    markup, parser = page()

    expected_ids = {"workspace", "example", "transpile", "source", "output", "status"}
    assert expected_ids <= parser.ids
    assert {"example", "source", "output"} <= parser.labels
    assert "readonly" in parser.textareas["output"]
    assert 'role="status"' in markup
    assert 'aria-live="polite"' in markup
    assert 'data-state="loading"' in markup


def test_browser_worker_preserves_the_non_execution_boundary() -> None:
    worker = (WEB / "pyodide-worker.js").read_text(encoding="utf-8")
    application = (WEB / "app.js").read_text(encoding="utf-8")
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    preparation = (ROOT / "scripts" / "prepare-web.mjs").read_text(encoding="utf-8")

    assert package["devDependencies"]["pyodide"]
    assert 'path.resolve("node_modules", "pyodide", name)' in preparation
    assert 'new URL("assets/pyodide/"' in worker
    assert "packageModule.transpile(source)" in worker
    assert "runPython" not in worker
    assert "eval(" not in worker
    assert "exec(" not in worker
    assert 'new Worker("pyodide-worker.js"' in application
    assert "message.python" in application


def test_browser_examples_match_documented_accepted_programs() -> None:
    _, parser = page()
    examples: dict[str, str] = json.loads(parser.example_json)
    documentation = (ROOT / "docs" / "supported-cobol.md").read_text(encoding="utf-8")
    accepted_section = documentation.split("## Complete accepted programs", 1)[1].split(
        "## Rejected examples", 1
    )[0]
    documented = re.findall(r"```cobol\n(.*?)\n```", accepted_section, flags=re.DOTALL)

    assert len(examples) == 4
    assert list(examples.values()) == documented
    for source in examples.values():
        parse_program(source)
