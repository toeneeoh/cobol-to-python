# Release status

COBOL to Python v0.1 is deployed as a GitHub Pages project site:

<https://toeneeoh.github.io/cobol-to-python/>

The initial release commit is `1a98596`. GitHub Actions run `32582903783`
completed both the validation and deployment jobs successfully on 2026-08-22.

Release verification covered:

- all Python tests, Ruff checks, and mypy;
- universal wheel construction;
- wheel import and transpilation under Pyodide;
- HTTP 200 responses for the page, application module, worker, wheel, and
  Pyodide runtime;
- correct JavaScript and `.mjs` MIME types; and
- a live Edge session reaching engine readiness and generating Python from the
  default documented COBOL example.

The project site is independent of the root `toeneeoh.github.io` repository.
Generated Python is displayed as readonly text and is not executed in the
browser.
