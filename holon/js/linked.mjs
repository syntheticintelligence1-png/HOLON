// Evaluate calls on a compiled linked-component model (holon.gen.linked; `bend model.bend -o model.mjs`).
// stdin:  {"module": path, "calls": [Expr, ..]}
//   Expr = {"fn": name, "args": [Expr, ..]} | {"val": Value} | {"some": Expr}
//   Value (JSON) = number (a U32 byte) | [Value, ..] (a list) | {"$": Ctor, field: Value, ..} (a record)
//                | {"nat": "<decimal>"} (a Nat, as a BigInt; I90's count models)
// stdout: {"results": [Value | {"error": msg}, ..]}: lists as arrays, Some as {"$some": v}, None as null, Bool as
// true/false, records as {"$": Ctor, field: v, ..}. Untrusted: it only proposes; Bend decides every status.
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const req = JSON.parse(readFileSync(0, "utf8"));
const M = (await import(pathToFileURL(req.module).href)).default;

function encode(v) {
  if (typeof v === "number") return v;
  if (typeof v === "boolean") return v;
  if (Array.isArray(v)) return v.reduceRight((t, h) => ({ $: "Con", head: encode(h), tail: t }), { $: "Nil" });
  if (v && typeof v === "object" && "nat" in v && typeof v.nat === "string" && /^[0-9]+$/.test(v.nat)) return BigInt(v.nat);
  if (v && typeof v === "object" && "$" in v) {
    const o = { $: v.$ };
    for (const [k, x] of Object.entries(v)) if (k !== "$") o[k] = encode(x);
    return o;
  }
  throw new Error("cannot encode " + JSON.stringify(v));
}

function decode(x) {
  if (typeof x === "number" || typeof x === "boolean") return x;
  if (typeof x === "bigint") return Number(x);
  if (x && (x.$ === "Nil" || x.$ === "Con")) {
    const out = [];
    for (let c = x; c.$ === "Con"; c = c.tail) out.push(decode(c.head));
    return out;
  }
  if (x && x.$ === "True") return true;
  if (x && x.$ === "False") return false;
  if (x && x.$ === "None") return null;
  if (x && x.$ === "Some") return { $some: decode(x.value) };
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
    return f(...e.args.map(evalExpr));
  }
  if (e && typeof e === "object" && "some" in e) return { $: "Some", value: evalExpr(e.some) };
  if (e && typeof e === "object" && "val" in e) return encode(e.val);
  throw new Error("cannot evaluate " + JSON.stringify(e));
}

const results = req.calls.map((c) => {
  try { return decode(evalExpr(c)); } catch (err) { return { error: String(err.message || err) }; }
});
process.stdout.write(JSON.stringify({ results }));
