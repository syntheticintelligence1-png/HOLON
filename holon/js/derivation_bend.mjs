// Evaluate the compiled consumer model (holon.derivation.bendgen; `bend consumer.bend -o consumer.mjs`) on cases
// (holon.derivation.bendrun). Untrusted: it only evaluates; the checker decides every law.
// stdin: {"module": path, "layouts": {type: layout}, "batch_type", "recv_type", "nglobals",
//         "dt": {sha256 hex of the argument: answer},
//         "cases": [{"id", "batch": JSON by Go field names (a null element is an opaque placeholder), "pl": answer}]}
//   pl answer: {"kind": "PlOk", "nil", "bytes"} | {"kind": "PlDErr"|"PlRet", "error"} | {"kind": "PlPanic", "panic"}
//   dt answer: {"nil", "items": [hex]} | {"error"} | {"panic"}
// stdout: {"results": {id: {"out": "ORet"|"OPan"|"OFuel", "v": value, "recv": dump, "dt_args": [sha256], "unanswered"}}}
//   value: {"$": ctor, field: value} with lists as arrays, numbers as strings; dump: the receiver by field names
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { pathToFileURL } from "node:url";

const req = JSON.parse(readFileSync(0, "utf8"));
const M = (await import(pathToFileURL(req.module).href)).default;
const LAY = req.layouts;
const G = req.nglobals;
const MASK = (1n << 64n) - 1n;

const L = (xs) => xs.reduceRight((t, h) => ({ $: "Con", head: h, tail: t }), { $: "Nil" });
function A(l) {
  const out = [];
  for (let c = l; c && c.$ === "Con"; c = c.tail) out.push(c.head);
  return out;
}
const B = (b) => !!b;   // compiled Bend represents Bool as a JS boolean
const hexBytes = (s) => (s.startsWith("0x") ? Array.from(Buffer.from(s.slice(2), "hex")) : null);
const textBytes = (s) => Array.from(Buffer.from(String(s), "utf8"));
function vi(x) {
  const v = BigInt(x) & MASK;
  return { $: "VI", h: Number(v >> 32n), l: Number(v & 0xffffffffn) };
}

function build(t, j, cells) {
  const lay = LAY[t];
  if (!lay) throw new Error("no layout for " + t);
  switch (lay.kind) {
    case "struct":
      return { $: "VR", fs: L(lay.fields.map(([n, ft]) => build(ft, j == null ? null : j[n], cells))) };
    case "int":
      return vi(j == null ? 0 : j);
    case "bool":
      return { $: "VB", b: B(!!j) };
    case "string":
      return { $: "VStr", bs: L(j == null ? [] : textBytes(j)) };
    case "array": {
      if (lay.byte) {
        const bs = j == null ? new Array(lay.len).fill(0) : hexBytes(j);
        if (bs == null || bs.length !== lay.len) throw new Error("bad array for " + t);
        return { $: "VY", bs: L(bs) };
      }
      const xs = j == null ? new Array(lay.len).fill(null) : j;
      return { $: "VR", fs: L(xs.map((x) => (x === null ? { $: "VNil" } : build(lay.elem, x, cells)))) };
    }
    case "slice": {
      if (j == null) return { $: "VNil" };
      let arr, n;
      if (lay.byte) {
        const bs = hexBytes(j);
        if (bs == null) throw new Error("bad bytes for " + t);
        arr = { $: "VY", bs: L(bs) };
        n = bs.length;
      } else {
        arr = { $: "VR", fs: L(j.map((x) => (x === null ? { $: "VNil" } : build(lay.elem, x, cells)))) };
        n = j.length;
      }
      cells.push(arr);
      return { $: "VS", c: BigInt(G + cells.length - 1), p: { $: "Nil" }, o: 0, n, k: n };
    }
    default:
      if (j != null) throw new Error("cannot build a " + lay.kind + " value for " + t);
      return { $: "VNil" };
  }
}

function enc(v) {
  if (typeof v === "boolean") return v;
  if (typeof v === "bigint") return String(v);
  if (typeof v === "number") return String(v);
  if (v && (v.$ === "Nil" || v.$ === "Con")) return A(v).map(enc);
  if (v && (v.$ === "True" || v.$ === "False")) return v.$ === "True";
  if (v && typeof v === "object" && "$" in v) {
    const o = { $: v.$ };
    for (const [k, x] of Object.entries(v)) if (k !== "$") o[k] = enc(x);
    return o;
  }
  return null;
}

// the heap and values, read back
function vget(path, x) {
  for (const i of path) {
    if (x.$ === "VR") x = A(x.fs)[Number(i)];
    else if (x.$ === "VY") return { $: "VI", h: 0, l: A(x.bs)[Number(i)] };
    else return { $: "VNil" };
    if (x === undefined) return { $: "VNil" };
  }
  return x;
}
const ival = (x, info) => {
  let v = (BigInt(x.h) << 32n) | BigInt(x.l);
  if (info && !info[1] && v >> 63n) v -= 1n << 64n;
  return String(v);
};
function arrElems(a) {
  if (a.$ === "VR") return A(a.fs);
  if (a.$ === "VY") return A(a.bs).map((b) => ({ $: "VI", h: 0, l: b }));
  return [];
}

function dump(t, x, heap, depth) {
  const lay = LAY[t];
  if (!lay || depth > 10) return null;
  switch (lay.kind) {
    case "struct": {
      if (x.$ !== "VR") return null;
      const fs = A(x.fs);
      const o = {};
      lay.fields.forEach(([n, ft], i) => (o[n] = dump(ft, fs[i] || { $: "VNil" }, heap, depth + 1)));
      return o;
    }
    case "int":
      return x.$ === "VI" ? ival(x, lay.int) : null;
    case "bool":
      return x.$ === "VB" ? x.b === true : null;
    case "string":
      return x.$ === "VStr" ? Buffer.from(A(x.bs)).toString("utf8") : null;
    case "big":
      if (x.$ !== "VBig") return null;
      return { big: A(x.bs).reduce((acc, b) => acc * 256n + BigInt(b), 0n).toString() };
    case "array":
      if (lay.byte) return "0x" + Buffer.from(x.$ === "VY" ? A(x.bs) : arrElems(x).map((e) => e.l)).toString("hex");
      return arrElems(x).map((e) => dump(lay.elem, e, heap, depth + 1));
    case "slice": {
      if (x.$ !== "VS") return null;
      const arr = vget(A(x.p), heap[Number(x.c)]);
      const es = arrElems(arr).slice(x.o, x.o + x.n);
      if (lay.byte) return "0x" + Buffer.from(es.map((e) => e.l & 255)).toString("hex");
      return es.map((e) => dump(lay.elem, e, heap, depth + 1));
    }
    case "pointer": {
      if (x.$ !== "VP") return null;
      return dump(lay.elem, vget(A(x.p), heap[Number(x.c)]), heap, depth + 1);
    }
    default:
      return x.$ === "VNil" ? null : "<" + lay.kind + ">";
  }
}

function plAnswer(a) {
  if (a.kind === "PlOk") return { $: "PlOk", n: B(!!a.nil), bs: L(hexBytes(a.bytes) || []) };
  if (a.kind === "PlPanic") return { $: "PlPanic", e: { $: "VEs", s: L(textBytes(a.panic)) } };
  return { $: a.kind, e: { $: "VEs", s: L(textBytes(a.error)) } };
}

// trace mode (holon.derivation.bendproof): {"module", "aliases": {module stem: alias}, "runs": {name: {"init": def,
// "step": def}}, "values": [def]}: each run's states from its initial state, one step of the entry's trampoline at a
// time, each as Bend literal text (the trampoline's continuation, heap and registers; the final result); each value
// def's result as a literal. stdout: {"runs": {name: {"states": [{"k", "h", "r"}], "res"}}, "values": {def: literal}}
if (req.runs) {
  const AL = req.aliases || {};
  const q = (name) => {
    const i = name.lastIndexOf(".");
    if (i < 0) return name;
    const a = AL[name.slice(0, i)];
    if (a === undefined) throw new Error("no alias for " + name);
    return a + "." + name.slice(i + 1);
  };
  const lit = (v) => {
    if (typeof v === "boolean") return v ? "True{}" : "False{}";
    if (typeof v === "number") return String(v);
    if (typeof v === "bigint") return v.toString() + "n";
    if (typeof v === "function") throw new Error("a closure in a literal");
    if (v.$ === "Nil") return "Nil{}";
    if (v.$ === "Con") {
      const xs = [];
      for (let c = v; c.$ === "Con"; c = c.tail) xs.push(lit(c.head));
      return "[" + xs.join(", ") + "]";
    }
    const fs = Object.keys(v).filter((k) => k !== "$").map((k) => lit(v[k]));
    return q(v.$) + "{" + fs.join(", ") + "}";
  };
  // a state's closure: the run's own (null) or the model's spent placeholder (req.spent: {"pl", "dt"} def names),
  // told apart by their answers on an empty argument (compiled closures are rewrapped at every step)
  const NIL = { $: "Nil" };
  const probe = (f) => lit(f(NIL));
  const fn = (f, which) => {
    if (typeof f !== "function") throw new Error("a state's closure is not a function");
    const sp = (req.spent || {})[which];
    if (!sp) return null;
    const a = probe(f), s = probe(M[sp]), o = probe(r0[which]);
    if (a === o && a !== s) return null;
    if (a === s && a !== o) return q(sp);
    throw new Error("a state's " + which + " closure is neither the run's nor the spent one");
  };
  let r0 = null;
  const out = { runs: {}, values: {} };
  for (const [name, r] of Object.entries(req.runs)) {
    let t = M[r.init]();
    r0 = { pl: t.pl, dt: t.dt };
    const step = M[r.step];
    const states = [];
    // the machine's states (holon.derivation.bendgen's MT): MGo{fr, st, h, pl, dt}, MRet{x, st, pl, dt}, MEnd{x}
    for (let i = 0; i < (r.max || 1000000); i++) {
      if (t.$.endsWith("MGo")) {
        states.push({ kind: "go", fr: lit(t.fr), st: lit(t.st), h: lit(t.h), pl: fn(t.pl, "pl"), dt: fn(t.dt, "dt") });
      } else if (t.$.endsWith("MRet")) {
        states.push({ kind: "ret", x: lit(t.x), st: lit(t.st), pl: fn(t.pl, "pl"), dt: fn(t.dt, "dt") });
      } else {
        break;
      }
      t = step(t);
    }
    if (!t.$.endsWith("MEnd")) throw new Error(name + ": no end within the bound");
    out.runs[name] = { states, res: lit(t.x) };
  }
  for (const d of req.values || []) out.values[d] = lit(M[d]());
  process.stdout.write(JSON.stringify(out));
} else {
const results = {};
for (const c of req.cases) {
  const cells = [M.zero_recv()];
  const recv = { $: "VP", c: BigInt(G), p: { $: "Nil" } };
  let r;
  const seen = [];
  let unanswered = false;
  try {
    const batch = build(req.batch_type, c.batch, cells);
    const pl = (_xs) => plAnswer(c.pl);
    const dt = (bytes) => {
      const sha = createHash("sha256").update(Buffer.from(A(bytes))).digest("hex");
      seen.push(sha);
      const a = (c.dt || req.dt || {})[sha];
      if (!a) {
        unanswered = true;
        return { $: "DtErr", e: { $: "VEs", s: L(textBytes("holon: no recorded answer")) } };
      }
      if ("panic" in a) return { $: "DtPanic", e: { $: "VEs", s: L(textBytes(a.panic)) } };
      if ("error" in a) return { $: "DtErr", e: { $: "VEs", s: L(textBytes(a.error)) } };
      return { $: "DtOk", n: B(!!a.nil), txs: L((a.items || []).map((h) => L(hexBytes(h)))) };
    };
    const res = M.consumer_run(pl, dt, L(cells), recv, batch);
    const heap = A(res.h);
    r = { out: res.o.$, v: enc(res.o.v ?? res.o.e ?? null), recv: dump(req.recv_type, heap[G], heap, 0),
          dt_args: seen, unanswered };
  } catch (err) {
    r = { out: "error", v: String((err && err.message) || err), recv: null, dt_args: seen, unanswered };
  }
  results[c.id] = r;
}
process.stdout.write(JSON.stringify({ results }));
}
