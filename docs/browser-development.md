# Browser development

The browser build uses the normal pure-Python wheel. There is no second
transpiler implementation for JavaScript: Pyodide imports the same
`cobol_to_python` package used by CPython.

## Prerequisites

- Python 3.11 or newer with the project development dependencies installed
- Node.js 20 or newer
- npm

Install the JavaScript smoke-test dependency once:

```console
npm ci
```

## Build and verify

Build exactly one universal wheel in a clean `dist` directory:

```console
python -m build --wheel
```

Then unpack that wheel in Pyodide and call the public `transpile()` API:

```console
npm run test:pyodide
```

Prepare the wheel for the static application after building it:

```console
npm run prepare:web
```

The smoke test fails unless `dist` contains exactly one
`cobol_to_python-*-py3-none-any.whl` file. Removing stale files before a new
build keeps that condition deterministic.

The wheel has no third-party Python runtime dependencies, so the smoke test can
use Pyodide's local `unpackArchive()` API without loading `micropip` or accessing
a package index. The Pyodide npm package is development-only and exists solely
to verify WebAssembly/browser compatibility under Node. A later milestone will
load the same wheel from a static GitHub Pages application.

## Preview the static interface

Run the standard-library development server:

```console
npm run serve:web
```

Open <http://localhost:8000>. The preparation step stages both the transpiler
wheel and the version-pinned Pyodide runtime under the ignored `web/assets`
directory. The resulting site makes no runtime CDN requests. The engine runs in
a Web Worker so it does not block the interface.

The browser calls only the package's public `transpile(source)` API. COBOL
source is passed as a function argument, not interpolated into Python code, and
the generated Python is displayed as readonly text. The application does not
execute generated code. Lexer, parser, and semantic failures retain their
existing category and line/column message without exposing a Python traceback.

## GitHub Pages deployment

`.github/workflows/pages.yml` validates pull requests and pushes. After a
successful push to `main`, it builds the wheel, stages the wheel and pinned
Pyodide runtime, and deploys `web` as this repository's project site:

<https://toeneeoh.github.io/cobol-to-python/>

This project-site deployment shares the `toeneeoh.github.io` domain but does
not write to or replace the separate `toeneeoh/toeneeoh.github.io` repository.
In this repository's GitHub settings, **Pages → Build and deployment → Source**
must be set to **GitHub Actions** once. The workflow requires no PAT, deploy key,
or cross-repository write permission.
