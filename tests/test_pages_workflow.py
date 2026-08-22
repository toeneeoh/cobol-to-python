from pathlib import Path

ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "pages.yml"


def workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_pages_workflow_runs_all_project_validation() -> None:
    configuration = workflow()

    for command in (
        "pytest",
        "ruff check .",
        "ruff format --check .",
        "mypy src",
        "python -m build --wheel",
        "npm run test:pyodide",
    ):
        assert command in configuration


def test_pages_deployment_is_limited_to_main_and_not_pull_requests() -> None:
    configuration = workflow()

    assert "branches: [main]" in configuration
    assert "github.event_name != 'pull_request'" in configuration
    assert "github.ref == 'refs/heads/main'" in configuration
    assert "needs: validate" in configuration


def test_pages_deploys_only_the_prepared_static_directory() -> None:
    configuration = workflow()

    assert "npm run prepare:web" in configuration
    assert "actions/upload-pages-artifact@v5" in configuration
    assert "path: web" in configuration
    assert "pages: write" in configuration
    assert "id-token: write" in configuration
