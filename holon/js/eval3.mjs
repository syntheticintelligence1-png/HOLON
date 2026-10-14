// The step evaluator of the M3 model (holon.sorts.evaluate3): the compiled typed (or untyped) model, `bend <model>.bend
// -o <model>.mjs`, executed as Bend compiled it. Python only moves values in and out.
//
// argv[2]: the compiled module. stdin: one JSON request per line, {"fn": name, "args": [value..]}; stdout: one JSON
// answer per line, {"out": value, "keys": {"kh": [hex..], "sh": [hex..]}, "calls": [[to hex | null, data hex]..]} or
// {"error": msg}. "keys" are the byte strings the run looked up in its hash tables (the parameters keccak256 and
// sha256), "calls" the external calls it looked up in its environment (the receiver when the call names one): the
// caller adds their answers and asks again (a fixpoint), as a refuter or the refinement harness supplies them.
//
// A request may carry "native": <caller id> (look the hash tables up in the evaluator's maps of that caller, which
// "tsync" keeps equal to the caller's tables; the model's table arguments are then unused) and "tsync": {table:
// {"add", "del"}}.
//
// Values (JSON): {"$w": "0x.."} a word W{l0..l7}; {"$b": "0x.."} a byte string (List<U32>); [..] a list; {"$r": name,
// "f": {field: value}} a record; true/false a Bool; a number a U32. Outputs: words as "0x..", byte lists as
// {"$b": "0x.."} when every element is a byte, records as {"$r", "f"}, lists as arrays.
import { readFileSync, writeFileSync } from "node:fs";
import { createInterface } from "node:readline";
import { pathToFileURL } from "node:url";

const path = process.argv[2];
let text = readFileSync(path, "utf8");
const HOOK = { kh: new Set(), sh: new Set(), calls: new Map() };
globalThis.__holonHook = HOOK;
// observe the hash-table and call lookups (the functions keep their compiled bodies)
function hook(name, body) {
  const re = new RegExp("function \\$" + name + "\\$\\(");
  if (!re.test(text)) return;
  text = text.replace(re, "function $" + name + "$__holon(");
  text += "\n" + body + "\n";
}
const listHex = `function __holonHex(xs) { let s = ""; for (let c = xs; c.$ === "Con"; c = c.tail) { const b = c.head;
  s += (b < 16 ? "0" : "") + (b >>> 0).toString(16); } return "0x" + s; }
function __holonWord(w) { let s = ""; for (let i = 7; i >= 0; i--) s += (w["l" + i] >>> 0).toString(16).padStart(8, "0");
  return "0x" + s; }`;
text += "\n" + listHex + "\n";
// native tables (A30, holon.sorts.search3's refuter): the hash tables as JavaScript maps that the caller keeps equal to
// the tables it would pass (a lookup of a key outside them answers 0, as the model's h_get does), so an evaluation
// neither scans nor receives the whole table; a request without "native" runs the compiled h_get on the tables it passes
hook("h_get", "function $h_get$(xs, k) { const h = globalThis.__holonHook; const x = __holonHex(k); h.cur.add(x); " +
  "if (h.native) { const v = (h.cur === h.sh ? h.tabs.sh : h.tabs.kh).get(x); return v === undefined ? " +
  "{$: 'W', l0: 0, l1: 0, l2: 0, l3: 0, l4: 0, l5: 0, l6: 0, l7: 0} : v; } return $h_get$__holon(xs, k); }");
hook("hs_get", "function $hs_get$(xs, k) { const h = globalThis.__holonHook; h.sh.add(__holonHex(k)); h.cur = h.sh; " +
  "try { return $hs_get$__holon(xs, k); } finally { h.cur = h.kh; } }");
hook("c_find", "function $c_find$(xs, to, bt, d) { const k = (bt ? __holonWord(to) : '-') + ' ' + __holonHex(d); " +
  "globalThis.__holonHook.calls.set(k, 1); return $c_find$__holon(xs, to, bt, d); }");
const tmp = path.replace(/\.mjs$/, "") + ".hooked.mjs";
writeFileSync(tmp, text);
const M = (await import(pathToFileURL(tmp).href)).default;

const NIL = { $: "Nil" };
function list(xs) {
  let t = NIL;
  for (let i = xs.length - 1; i >= 0; i--) t = { $: "Con", head: xs[i], tail: t };
  return t;
}
function hexBytes(h) {
  const s = h.startsWith("0x") ? h.slice(2) : h;
  const out = [];
  for (let i = 0; i + 1 < s.length + 1 && i < s.length; i += 2) out.push(parseInt(s.slice(i, i + 2), 16));
  return out;
}
function word(h) {
  let s = (h.startsWith("0x") ? h.slice(2) : h).padStart(64, "0");
  if (s.length > 64) s = s.slice(s.length - 64);
  const w = { $: "W" };
  for (let i = 0; i < 8; i++) w["l" + i] = parseInt(s.slice(64 - 8 * (i + 1), 64 - 8 * i), 16) >>> 0;
  return w;
}
function enc(v) {
  if (Array.isArray(v)) return list(v.map(enc));
  if (typeof v === "number" || typeof v === "boolean") return v;
  if (v && typeof v === "object") {
    if ("$w" in v) return word(v.$w);
    if ("$b" in v) return list(hexBytes(v.$b));
    if ("$r" in v) {
      const o = { $: v.$r };
      for (const [k, x] of Object.entries(v.f || {})) o[k] = enc(x);
      return o;
    }
  }
  throw new Error("cannot encode " + JSON.stringify(v).slice(0, 200));
}
function dec(x) {
  if (typeof x === "number" || typeof x === "boolean") return x;
  if (typeof x === "bigint") return Number(x);
  if (x === null || x === undefined) return null;
  if (x.$ === "Nil" || x.$ === "Con") {
    const out = [];
    for (let c = x; c.$ === "Con"; c = c.tail) out.push(dec(c.head));
    if (out.length && out.every((b) => typeof b === "number" && b >= 0 && b <= 255)) {
      return { $b: "0x" + out.map((b) => b.toString(16).padStart(2, "0")).join("") };
    }
    if (!out.length) return [];
    return out;
  }
  if (x.$ === "W") return __word(x);
  if (x.$ === "True") return true;
  if (x.$ === "False") return false;
  const f = {};
  for (const [k, v] of Object.entries(x)) if (k !== "$") f[k] = dec(v);
  return { $r: x.$, f };
}
function __word(w) {
  let s = "";
  for (let i = 7; i >= 0; i--) s += (w["l" + i] >>> 0).toString(16).padStart(8, "0");
  return "0x" + s;
}

// Stored values: a request may "save" its raw result under a name, and arguments may be {"$ref": name} (a stored
// value) or {"$call": fn, "args": [..]} (a nested call); "quiet": true answers no decoded result; "drop": [names].
const STORE = new Map();
function arg(v) {
  if (v && typeof v === "object" && !Array.isArray(v)) {
    if ("$ref" in v) {
      if (!STORE.has(v.$ref)) throw new Error("no stored value " + v.$ref);
      return STORE.get(v.$ref);
    }
    if ("$call" in v) {
      const f = M[v.$call];
      if (typeof f !== "function") throw new Error("the model has no function " + v.$call);
      return f(...(v.args || []).map(arg));
    }
    if ("$r" in v) {
      const o = { $: v.$r };
      for (const [k, x] of Object.entries(v.f || {})) o[k] = arg(x);
      return o;
    }
  }
  if (Array.isArray(v)) return list(v.map(arg));
  return enc(v);
}

// the native tables of each caller ("native": its id), and {"tsync": {"kh": {"add": [[key hex, word hex]..], "del":
// [key hex..]}, "sh": ..}}: their changes since the caller's previous request
const NATIVE = new Map();
HOOK.tabs = null;
HOOK.native = false;
function tabsOf(id) {
  let t = NATIVE.get(id);
  if (!t) {
    t = { kh: new Map(), sh: new Map() };
    NATIVE.set(id, t);
  }
  return t;
}
function tsync(tabs, d) {
  for (const t of ["kh", "sh"]) {
    const x = (d || {})[t];
    if (!x) continue;
    for (const [k, v] of x.add || []) tabs[t].set(k, word(v));
    for (const k of x.del || []) tabs[t].delete(k);
  }
}

const rl = createInterface({ input: process.stdin, crlfDelay: Infinity });
for await (const line of rl) {
  if (!line.trim()) continue;
  let ans;
  try {
    const req = JSON.parse(line);
    for (const d of req.drop || []) STORE.delete(d);
    HOOK.kh = new Set();
    HOOK.sh = new Set();
    HOOK.calls = new Map();
    HOOK.cur = HOOK.kh;
    HOOK.native = !!req.native;
    if (HOOK.native) {
      HOOK.tabs = tabsOf(String(req.native));
      if (req.tsync) tsync(HOOK.tabs, req.tsync);
    }
    let out = null;
    if (req.show) {
      if (!STORE.has(req.show)) throw new Error("no stored value " + req.show);
      out = STORE.get(req.show);
    } else if (req.fn) {
      const f = M[req.fn];
      if (typeof f !== "function") throw new Error("the model has no function " + req.fn);
      out = f(...(req.args || []).map(arg));
      if (req.save) STORE.set(req.save, out);
    }
    ans = { out: req.quiet ? null : dec(out), keys: { kh: [...HOOK.kh].sort(), sh: [...HOOK.sh].sort() },
            calls: [...HOOK.calls.keys()].sort().map((k) => {
              const [to, d] = k.split(" ");
              return [to === "-" ? null : to, d];
            }) };
  } catch (e) {
    ans = { error: String((e && e.stack) || e).slice(0, 2000) };
  }
  process.stdout.write(JSON.stringify(ans) + "\n");
}
