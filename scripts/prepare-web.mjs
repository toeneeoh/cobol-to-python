import assert from "node:assert/strict";
import { copyFile, mkdir, readdir } from "node:fs/promises";
import path from "node:path";

const distributionDirectory = path.resolve("dist");
const wheels = (await readdir(distributionDirectory)).filter(
  (name) => name.startsWith("cobol_to_python-") && name.endsWith("-py3-none-any.whl"),
);

assert.equal(
  wheels.length,
  1,
  `expected exactly one browser-compatible wheel in dist, found ${wheels.length}`,
);

const assetsDirectory = path.resolve("web", "assets");
await mkdir(assetsDirectory, { recursive: true });
await copyFile(
  path.join(distributionDirectory, wheels[0]),
  path.join(assetsDirectory, "cobol_to_python.whl"),
);

const pyodideDirectory = path.join(assetsDirectory, "pyodide");
await mkdir(pyodideDirectory, { recursive: true });
for (const name of [
  "pyodide-lock.json",
  "pyodide.asm.mjs",
  "pyodide.asm.wasm",
  "pyodide.mjs",
  "python_stdlib.zip",
]) {
  await copyFile(
    path.resolve("node_modules", "pyodide", name),
    path.join(pyodideDirectory, name),
  );
}

console.log(`Prepared browser wheel from ${wheels[0]} and the pinned Pyodide runtime.`);
