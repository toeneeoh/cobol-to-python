# cobol-to-python

A typed, staged transpiler for the documented COBOL v0.1 subset.

Browser packaging and the Pyodide compatibility smoke test are described in
[docs/browser-development.md](docs/browser-development.md).

The static browser interface can be previewed with `npm run serve:web` and then
opened at <http://localhost:8000>.

The Pages workflow deploys successful `main` builds as the isolated project
site at <https://toeneeoh.github.io/cobol-to-python/>. It does not modify the
existing `toeneeoh.github.io` repository or its root site.

See [docs/release.md](docs/release.md) for the verified v0.1 release status.
