// Evaluate calls on a compiled Bend state-machine model (`bend model.bend -o model.mjs`).
// stdin:  {"module": path, "calls": [Expr, ..]}
//   Expr = {"fn": name, "args": [Expr | Value, ..]} | {"val": Value}
//   Value (JSON) = number (Nat) | boolean | [Value..] (List) | {"$": Ctor, field: Value, ..} | {"$fn"...} n/a
// stdout: {"results": [Value | {"error": msg}, ..]}   (constructors decoded as {"$": name, ...fields})
import { readFileSync } from "node:fs";

const req = JSON.parse(readFileSync(0, "utf8"));
// req.oracles (M2+ models with oracle parameters, I12/I15): lookups answered by the sidecar instances
const { loadModel, tabsOf } = await import("./oracle_model.mjs");
const M = await loadModel(req.module, req.oracles || null);

export function encode(v) {
  if (typeof v === "number") return BigInt(v);
  if (typeof v === "boolean") return v;
  if (Array.isArray(v)) return v.reduceRight((t, h) => ({ $: "Con", head: encode(h), tail: t }), { $: "Nil" });
  if (v && typeof v === "object" && "$" in v) {
    const o = { $: v.$ };
    for (const [k, x] of Object.entries(v)) if (k !== "$") o[k] = encode(x);
    return o;
  }
  throw new Error("cannot encode " + JSON.stringify(v));
}

export function decode(x) {
  if (typeof x === "bigint") return Number(x);
  if (typeof x === "number" || typeof x === "boolean") return x;
  if (x && (x.$ === "Nil" || x.$ === "Con")) {
    const out = [];
    for (let c = x; c.$ === "Con"; c = c.tail) out.push(decode(c.head));
    return out;
  }
  if (x && typeof x === "object" && "$" in x) {
    const o = { $: x.$ };
    for (const [k, y] of Object.entries(x)) if (k !== "$") o[k] = decode(y);
    return o;
  }
  throw new Error("cannot decode " + String(x));
}

function evalExpr(e) {
  if (e && typeof e === "object" && "fn" in e) {
    const f = M[e.fn];
    if (typeof f !== "function") throw new Error("model has no function " + e.fn);
    return f(...e.args.map(evalExpr), ...tabsOf(req.oracles, e.fn));
  }
  if (e && typeof e === "object" && "val" in e) return encode(e.val);
  return encode(e);
}

const results = req.calls.map((c) => {
  try { return decode(evalExpr(c)); } catch (err) { return { error: String(err.message || err) }; }
});
process.stdout.write(JSON.stringify({ results }));
