const requiredElements = {
  copy: document.querySelector("#copy"),
  examples: document.querySelector("#examples"),
  exampleSelect: document.querySelector("#example"),
  output: document.querySelector("#output"),
  source: document.querySelector("#source"),
  status: document.querySelector("#status"),
  statusMessage: document.querySelector("#status-message"),
  transpile: document.querySelector("#transpile"),
};

if (Object.values(requiredElements).some((element) => !element)) {
  throw new Error("The transpiler workspace is incomplete.");
}

const {
  copy,
  examples: examplesElement,
  exampleSelect,
  output,
  source,
  status,
  statusMessage,
  transpile,
} = requiredElements;
const examples = JSON.parse(examplesElement.textContent);
const worker = new Worker("pyodide-worker.js", { type: "module" });
let requestId = 0;
let ready = false;
let busy = false;

function setStatus(state, message, busy = false) {
  status.dataset.state = state;
  status.setAttribute("aria-busy", String(busy));
  statusMessage.textContent = message;
}

function setBusy(value) {
  busy = value;
  transpile.disabled = value || !ready;
  exampleSelect.disabled = value;
  source.readOnly = value;
}

function selectExample(name) {
  const selectedSource = examples[name];
  if (typeof selectedSource !== "string") {
    throw new Error(`Unknown example: ${name}`);
  }
  source.value = selectedSource;
  output.value = "";
  copy.disabled = true;
  if (ready) {
    setStatus("ready", "Ready to transpile.");
  }
}

function requestTranspilation() {
  if (!ready || busy) {
    return;
  }

  requestId += 1;
  setBusy(true);
  copy.disabled = true;
  setStatus("loading", "Transpiling COBOL…", true);
  worker.postMessage({ type: "transpile", id: requestId, source: source.value });
}

worker.addEventListener("message", (event) => {
  const message = event.data;
  if (message.type === "status") {
    setStatus("loading", message.message, true);
    return;
  }
  if (message.type === "ready") {
    ready = true;
    setBusy(false);
    setStatus("ready", "Ready to transpile.");
    return;
  }
  if (message.type === "fatal") {
    ready = false;
    setBusy(false);
    setStatus("error", message.message);
    return;
  }
  if (message.id !== requestId) {
    return;
  }

  setBusy(false);
  if (message.type === "result") {
    output.value = message.python;
    copy.disabled = false;
    setStatus("success", "Python generated successfully.");
  } else if (message.type === "error") {
    output.value = "";
    copy.disabled = true;
    setStatus("error", `${message.category}: ${message.message}`);
  }
});

worker.addEventListener("error", () => {
  ready = false;
  setBusy(false);
  setStatus("error", "The browser engine could not be started.");
});

exampleSelect.addEventListener("change", () => {
  selectExample(exampleSelect.value);
});

transpile.addEventListener("click", requestTranspilation);

copy.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(output.value);
    setStatus("success", "Generated Python copied.");
  } catch {
    setStatus("error", "Copy failed. Select the Python output and copy it manually.");
  }
});

source.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    event.preventDefault();
    requestTranspilation();
    return;
  }
  if (event.key !== "Tab") {
    return;
  }

  event.preventDefault();
  const start = source.selectionStart;
  const end = source.selectionEnd;
  source.setRangeText("    ", start, end, "end");
});

source.addEventListener("input", () => {
  output.value = "";
  copy.disabled = true;
  if (ready) {
    setStatus("ready", "Source changed. Ready to transpile.");
  }
});

selectExample(exampleSelect.value);
