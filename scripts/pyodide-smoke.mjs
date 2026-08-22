import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";

import { loadPyodide } from "pyodide";

const distributionDirectory = path.resolve("dist");
const wheels = (await readdir(distributionDirectory)).filter(
  (name) => name.startsWith("cobol_to_python-") && name.endsWith("-py3-none-any.whl"),
);

assert.equal(
  wheels.length,
  1,
  `expected exactly one browser-compatible wheel in dist, found ${wheels.length}`,
);

const pyodide = await loadPyodide();
const wheel = await readFile(path.join(distributionDirectory, wheels[0]));
pyodide.unpackArchive(Uint8Array.from(wheel), "zip");

const generated = pyodide.runPython(`
from cobol_to_python import transpile

transpile("""IDENTIFICATION DIVISION.
PROGRAM-ID. BROWSER-SMOKE.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 COUNT PIC 9(2) VALUE 2.
PROCEDURE DIVISION.
COMPUTE COUNT = COUNT + 3.
DISPLAY COUNT.
STOP RUN.""")
`);

assert.match(generated, /def main\(\) -> None:/);
assert.match(generated, /cobol_count = _cobol_assign_9\(\(cobol_count \+ 3\), 2\)/);
console.log("Pyodide smoke test passed: wheel imported and transpiled COBOL.");
