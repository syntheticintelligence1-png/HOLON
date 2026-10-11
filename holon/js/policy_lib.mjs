// Search policy for the Morph rollup machine: candidate actions from a decoded state.
// Untrusted heuristics (like a fuzzing dictionary): they only steer the search.
export function policyOf(s, facts) {

  const lci = s.lfi + s.win.length - 1;
  const last = s.win[s.win.length - 1] || {};
  const fresh = 100 + 10 * (lci + 1) + (s.log.length % 7);
  const blob = 7 + 10 * (lci + 1);
  const room = Math.max(0, s.qlen - (last.tot || 0));
  const ns = room > 0 ? [0, 1] : [0];
  const P = facts.params;
  const out = [];
  for (const ver of [1, 2, 0]) for (const n of ns) {
    const blobsList = ver === 2 ? [[blob]] : [[blob], [], [P.Z]];
    for (const blobs of blobsList)
      out.push({ op: "commitBatch", who: 2, ver, parent: lci, n, lbn: lci + 1, prev: last.csr || 0, post: fresh, blobs });
  }
  for (const ver of [1, 2]) out.push({ op: "commitState", who: 2, ver, parent: lci, n: 0, lbn: lci + 1, prev: last.csr || 0, post: fresh, blobs: [] });
  for (const n of ns) out.push({ op: "commitBatchWithProof", who: 5, ver: 1, parent: lci, n, lbn: lci + 1, prev: last.csr || 0, post: fresh, blobs: [blob], proof: 1 });
  if (lci > s.lfi) out.push({ op: "revertBatch", who: 1, idx: lci, count: 1 });
  if (lci > s.lfi + 1) out.push({ op: "revertBatch", who: 1, idx: s.lfi + 1, count: lci - s.lfi });
  for (const idx of [...new Set([lci, s.lfi + 1])]) if (idx > s.lfi && idx <= lci) out.push({ op: "challengeState", who: 4, idx, value: 1 });
  out.push({ op: "proveState", who: 2, idx: s.bc, proof: 1 });
  out.push({ op: "finalizeBatch", who: 5, idx: s.lfi + 1 });
  out.push({ op: "setPause", who: 1, status: !s.paused });
  out.push({ op: "sendMessage", who: 5 });
  // time abstraction: wait exactly until the next relevant deadline (finalization, proof window, delay guard)
  const dts = new Set([1, s.W, s.W + 1, s.F, s.D + 1]);
  for (const e of s.win) if (e.bdf >= s.t) { dts.add(e.bdf - s.t); dts.add(e.bdf - s.t + 1); }
  const ch = s.chs[s.bc]; if (ch && s.inch) for (const d of [ch.s + s.W - s.t, ch.s + s.W - s.t + 1]) if (d > 0) dts.add(d);
  if (s.qpend < s.qlen) { const d = s.enq[s.qpend] + s.D + 1 - s.t; if (d > 0) dts.add(d); }
  dts.delete(0);
  for (const dt of [...dts].sort((x, y) => x - y)) out.push({ op: "wait", dt });
  return out;
}

