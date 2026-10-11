// HOLON M2 S7: long-lived Node worker hosting a bend-emitted model library.
// Protocol: JSON lines on stdin; one JSON line on stdout per request.
//   {"call":"flat","op":N,"args":[u64,...]}   -> {"ok":true,"out":[u64,...]}
//   {"call":"trace","steps":[[u64,...],...]}  -> {"ok":true,"out":[u64,...]}
//   {"ping":true}                            -> {"ok":true,"pong":true}
// Usage: node worker.mjs <model.mjs> <flatName> <traceName>
// flatName/traceName are exported dispatcher names ("hcall"/"hcall2").
import { createInterface } from "node:readline";
import { pathToFileURL } from "node:url";
import process from "node:process";

const [modelPath, flatName = "hcall", traceName = "hcall2"] = process.argv.slice(2);
const lib = (await import(pathToFileURL(modelPath).href)).default;
const flat = lib[flatName];
const trace = lib[traceName];
if (typeof flat !== "function" || typeof trace !== "function") {
  process.stderr.write(`missing dispatchers ${flatName}/${traceName} in ${modelPath}\n`);
  process.exit(2);
}

const NIL = { $: "Nil" };
function natListOf(arr) {
  let r = NIL;
  for (let i = arr.length - 1; i >= 0; i--) r = { $: "Con", head: arr[i], tail: r };
  return r;
}
function natListListOf(arr) {
  let r = NIL;
  for (let i = arr.length - 1; i >= 0; i--) r = { $: "Con", head: natListOf(arr[i]), tail: r };
  return r;
}
function listToArray(v) {
  const out = [];
  while (v && v.$ === "Con") { out.push(Number(v.head)); v = v.tail; }
  return out;
}

const rl = createInterface({ input: process.stdin, terminal: false });
const out = (o) => process.stdout.write(JSON.stringify(o) + "\n");
out({ ok: true, ready: true });
rl.on("line", (line) => {
  if (!line.trim()) return;
  try {
    const req = JSON.parse(line);
    if (req.ping) return out({ ok: true, pong: true });
    if (req.call === "flat") return out({ ok: true, out: listToArray(flat(req.op, natListOf(req.args))) });
    if (req.call === "trace") return out({ ok: true, out: listToArray(trace(req.op || 0, natListListOf(req.steps))) });
    return out({ ok: false, error: "unknown call" });
  } catch (e) {
    return out({ ok: false, error: String(e && e.stack || e) });
  }
});
