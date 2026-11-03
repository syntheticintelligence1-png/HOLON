// Evaluate IR terms on a compiled Bend model (an ES module from `bend model.bend -o model.mjs`).
// stdin:  {"module": path, "jobs": [{"terms": [IRterm, ..], "env": {name: Value}}, ..]}
// stdout: {"results": [[Value | {"error": msg}, ..], ..]}
// Value (JSON): Header {"$hdr": {cell: n}} | Bytes [n, ..] | Bool true/false | Some {"$some": v} | None null
// Outputs are decoded generically: lists -> arrays, Maybe -> {"$some"}/null. Compiled Bool is a JS boolean.
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const req = JSON.parse(readFileSync(0, "utf8"));
const M = (await import(pathToFileURL(req.module).href)).default;

const toList = (xs) => xs.reduceRight((t, h) => ({ $: "Con", head: h, tail: t }), { $: "Nil" });

function encode(v) {
  if (Array.isArray(v)) return toList(v.map(encode));
  if (typeof v === "number") return v;
  if (typeof v === "boolean") return v; // compiled Bool is a JS boolean
  if (v === null) return { $: "None" };
  if (v.$hdr) return { $: "Hdr", ...v.$hdr };
  if ("$some" in v) return { $: "Some", value: encode(v.$some) };
  throw new Error("cannot encode " + JSON.stringify(v));
}

function decode(x) {
  if (typeof x === "number" || typeof x === "boolean") return x;
  if (typeof x === "bigint") return Number(x);
  if (x.$ === "Nil" || x.$ === "Con") {
    const out = [];
    for (let c = x; c.$ === "Con"; c = c.tail) out.push(decode(c.head));
    return out;
  }
  if (x.$ === "True") return true;
  if (x.$ === "False") return false;
  if (x.$ === "None") return null;
  if (x.$ === "Some") return { $some: decode(x.value) };
  throw new Error("cannot decode constructor " + x.$);
}

function fn(name) {
  const f = M[name];
  if (typeof f !== "function") throw new Error("model has no function " + name);
  return f;
}

function evalTerm(t, env) {
  if ("var" in t) return env[t.var];
  if ("bytes" in t) return toList([...Buffer.from(t.bytes.slice(2), "hex")]);
  if ("field" in t) return fn("get_" + t.field)(evalTerm(t.of, env));
  if ("call" in t) return fn(t.call)(...t.args.map((a) => evalTerm(a, env)));
  if ("some" in t) return { $: "Some", value: evalTerm(t.some, env) };
  if ("bool" in t) return t.bool; // holon-ir/0.3 codec terms (I24): a Bool literal, a JS boolean like compiled Bool
  throw new Error("unknown term " + JSON.stringify(t));
}

const results = req.jobs.map((job) => {
  const env = Object.fromEntries(Object.entries(job.env).map(([k, v]) => [k, encode(v)]));
  return job.terms.map((t) => {
    try { return decode(evalTerm(t, env)); } catch (e) { return { error: String(e.message || e) }; }
  });
});
process.stdout.write(JSON.stringify({ results }));
