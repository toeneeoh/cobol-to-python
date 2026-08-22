import assert from "node:assert/strict";

const endpoint = process.argv[2] ?? "http://127.0.0.1:9223";
const siteUrl = process.argv[3] ?? "https://toeneeoh.github.io/cobol-to-python/";
const targets = await fetch(`${endpoint}/json/list`).then((response) => response.json());
const target = targets.find((candidate) => candidate.type === "page" && candidate.url === siteUrl);

assert.ok(target, `no browser tab found for ${siteUrl}`);

const socket = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  socket.addEventListener("open", resolve, { once: true });
  socket.addEventListener("error", reject, { once: true });
});

let commandId = 0;
const pending = new Map();

socket.addEventListener("message", (event) => {
  const message = JSON.parse(event.data);
  const handler = pending.get(message.id);
  if (handler) {
    pending.delete(message.id);
    handler(message);
  }
});

function send(method, params = {}) {
  commandId += 1;
  const id = commandId;
  return new Promise((resolve) => {
    pending.set(id, resolve);
    socket.send(JSON.stringify({ id, method, params }));
  });
}

async function evaluate(expression) {
  const response = await send("Runtime.evaluate", {
    expression,
    returnByValue: true,
  });
  assert.ok(!response.error, response.error?.message);
  assert.ok(!response.result.exceptionDetails, "browser evaluation raised an exception");
  return response.result.result.value;
}

async function waitFor(expression, description) {
  const deadline = Date.now() + 60_000;
  while (Date.now() < deadline) {
    if (await evaluate(expression)) {
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  assert.fail(`timed out waiting for ${description}`);
}

try {
  await waitFor(
    'document.querySelector("#transpile")?.disabled === false',
    "the browser transpiler",
  );
  await evaluate('document.querySelector("#transpile").click()');
  await waitFor(
    'document.querySelector("#output")?.value.includes("def main() -> None:")',
    "generated Python",
  );

  const status = await evaluate('document.querySelector("#status-message")?.textContent');
  const output = await evaluate('document.querySelector("#output")?.value');
  assert.equal(status, "Python generated successfully.");
  assert.match(output, /print\("Hello, world!"\)/);
  console.log(`Live browser smoke test passed: ${siteUrl}`);
} finally {
  socket.close();
}
