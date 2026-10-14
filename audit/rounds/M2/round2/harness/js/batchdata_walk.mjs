// HOLON I21 (audit round M2/2, auditor A2), surface batchdata_act: the batch-data model's side of the append
// sequences, on its compiled Bend model (`bend model.bend -o model.mjs`, holon.mpipeline.CompiledMachine). It walks
// the same sequences, in the same order, as the Go harness (every sequence of at most depth appends over the argument
// lists, shortest first, then lexicographic), and writes what the model says; it compares nothing.
//
// stdin: {"module": path, "append": [[list, ..], ..]  the append action's inputs (lists of Nat) per argument set,
//         "depth": n, "appendStep": "step_<append action>", "viewStep": "step_<view action>",
//         "slices": [state field, ..]  the state fields of slice type, "view": the field the view step writes,
//         "read": compiled reader def (heap, slice) -> List<Nat>, "heap": its heap field,
//         "bound": n}  a sequence is evaluated only while every slice the model would hold stays at or below bound
//                      bytes (the largest entry of the size-class table the append builtin is given: the model's
//                      stated scope); others are written as out of scope
// stdout: one JSON array per sequence, in order: [k, true, [[len, cap] per slice field, per append],
//         [viewLen, viewCap, sha256 of the view's bytes]] or [k, false].
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";

const req = JSON.parse(readFileSync(0, "utf8"));
const M = (await import(req.module)).default;

const toList = (xs) => xs.reduceRight((t, h) => ({ $: "Con", head: BigInt(h), tail: t }), { $: "Nil" });
const fromList = (l) => {
  const out = [];
  for (let c = l; c.$ === "Con"; c = c.tail) out.push(Number(c.head));
  return out;
};
const args = req.append.map((a) => a.map(toList));
const lens = req.append.map((a) => a.map((x) => x.length));
const s0 = M.s0();
const out = [];

function view(st) {
  const v = M[req.viewStep](st);
  const sl = v[req.view];
  const bytes = fromList(M[req.read](v[req.heap], sl));
  const h = createHash("sha256").update(Buffer.from(bytes)).digest("hex");
  return [Number(sl.len), Number(sl.cap), h];
}

function slicesOf(st) {
  return req.slices.map((f) => [Number(st[f].len), Number(st[f].cap)]);
}

let k = 0;
for (let d = 0; d <= req.depth; d++) {
  const seq = [];
  const walk = (st, inScope, after, total) => {
    if (seq.length === d) {
      const vw = inScope ? view(st) : null;
      if (vw && vw[1] <= req.bound) {
        out.push(JSON.stringify([k, true, after, vw]));
      } else {
        out.push(JSON.stringify([k, false]));
      }
      k++;
      return;
    }
    for (let i = 0; i < args.length; i++) {
      seq.push(i);
      const t = total + lens[i].reduce((x, y) => x + y, 0);
      if (inScope && t <= req.bound) {
        const st2 = M[req.appendStep](st, ...args[i]);
        const sl = slicesOf(st2);
        walk(st2, sl.every(([, c]) => c <= req.bound), after.concat([sl]), t);
      } else {
        walk(st, false, after, t);
      }
      seq.pop();
    }
  };
  walk(s0, true, [], 0);
}
process.stdout.write(out.join("\n") + "\n");
