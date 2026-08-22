const PYODIDE_BASE_URL = new URL("assets/pyodide/", self.location.href).href;
const DIAGNOSTIC_PATTERN = /(LexerError|ParseError|SemanticError): (.+)/;

let transpile;

function diagnosticFrom(error) {
  const message = error instanceof Error ? error.message : String(error);
  const match = [...message.matchAll(new RegExp(DIAGNOSTIC_PATTERN, "g"))].at(-1);
  if (match) {
    return { category: match[1], message: match[2] };
  }
  return {
    category: "TranspilerError",
    message: "The browser transpiler encountered an unexpected error.",
  };
}

async function initialize() {
  self.postMessage({ type: "status", message: "Loading the Python engine…" });
  const { loadPyodide } = await import(`${PYODIDE_BASE_URL}pyodide.mjs`);
  const pyodide = await loadPyodide({ indexURL: PYODIDE_BASE_URL });

  self.postMessage({ type: "status", message: "Loading the transpiler…" });
  const response = await fetch(new URL("assets/cobol_to_python.whl", self.location.href));
  if (!response.ok) {
    throw new Error(`Unable to load transpiler package (${response.status}).`);
  }
  pyodide.unpackArchive(await response.arrayBuffer(), "zip");

  const packageModule = pyodide.pyimport("cobol_to_python");
  transpile = (source) => packageModule.transpile(source);
  self.postMessage({ type: "ready" });
}

self.addEventListener("message", (event) => {
  if (event.data?.type !== "transpile" || typeof event.data.source !== "string") {
    return;
  }

  const { id, source } = event.data;
  try {
    if (!transpile) {
      throw new Error("The browser transpiler is not ready.");
    }
    self.postMessage({ type: "result", id, python: transpile(source) });
  } catch (error) {
    self.postMessage({ type: "error", id, ...diagnosticFrom(error) });
  }
});

initialize().catch((error) => {
  self.postMessage({ type: "fatal", ...diagnosticFrom(error) });
});
