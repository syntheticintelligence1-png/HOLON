// Differential evaluation for holon.gen.equivalence's counter class: the compiled pair module (old definitions
// renamed o__<name>, new ones as they are), executed as Bend compiled it. Python only generates the inputs and reads
// the answers; it never evaluates the model.
//
// argv[2]: the compiled module. stdin: one JSON request per line, {"old": name, "new": name, "args": [value..]};
// stdout: one JSON answer per line, {"same": bool, "a": value, "b": value, "path": [key..]} (path: the first key path
// where the two results differ) or {"error": msg}.
// Values (JSON): a number is a U32, {"$nat": "n"} a Nat, {"$bool": b} a Bool, {"$": ctor, field: value..} a
// constructor (lists are Con{head, tail} / Nil{}).
import { createInterface } from "node:readline";
import { pathToFileURL } from "node:url";

const M = (await import(pathToFileURL(process.argv[2]).href)).default;

function toJs(v) {
  if (typeof v === "number") return v >>> 0;
  if (Array.isArray(v)) throw new Error("arrays are not values");
  if (v && typeof v === "object") {
    if ("$nat" in v) return BigInt(v.$nat);
    if ("$bool" in v) return !!v.$bool;
    const o = {};
    for (const k of Object.keys(v)) o[k] = k === "$" ? v[k] : toJs(v[k]);
    return o;
  }
  throw new Error("unknown value " + JSON.stringify(v));
}

function fromJs(v) {
  if (typeof v === "number") return v >>> 0;
  if (typeof v === "bigint") return { $nat: v.toString() };
  if (typeof v === "boolean") return { $bool: v };
  if (v && typeof v === "object") {
    const o = {};
    for (const k of Object.keys(v)) o[k] = k === "$" ? v[k] : fromJs(v[k]);
    return o;
  }
  return { $other: String(v) };
}

function diff(a, b, path) {
  if (typeof a !== "object" || a === null || typeof b !== "object" || b === null) {
    return JSON.stringify(a) === JSON.stringify(b) ? null : path;
  }
  if (a.$ !== b.$) return path;
  for (const k of Object.keys(a)) {
    if (k === "$") continue;
    const d = diff(a[k], b[k], path.concat([k]));
    if (d) return d;
  }
  return null;
}

const rl = createInterface({ input: process.stdin, crlfDelay: Infinity });
for await (const line of rl) {
  if (!line.trim()) continue;
  let out;
  try {
    const r = JSON.parse(line);
    const fa = M[r.old], fb = M[r.new];
    if (typeof fa !== "function" || typeof fb !== "function") throw new Error("no function " + r.old + " / " + r.new);
    const a = fromJs(fa(...r.args.map(toJs)));
    const b = fromJs(fb(...r.args.map(toJs)));
    const p = diff(a, b, []);
    out = { same: p === null, a, b, path: p || [] };
  } catch (e) {
    out = { error: String(e && e.message || e) };
  }
  process.stdout.write(JSON.stringify(out) + "\n");
}
