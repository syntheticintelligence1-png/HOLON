// Generic search policy (I6): candidate actions for a machine without target search hints.
// Every action in facts order, with every combination of input values from facts.search.domains
// (action -> input -> [values]). An input without a domain takes 0 and 1 (Nat), false and true (Bool),
// or the empty list. Untrusted like any policy: it only steers the explorer.
export function policyOf(s, facts) {
  const dom = (facts.search && facts.search.domains) || {};
  const def = (t) => (t === "Bool" ? [false, true] : t.startsWith("List<") ? [[]] : [0, 1]);
  const out = [];
  for (const a of facts.actions) {
    let combos = [{ op: a.name }];
    for (const [n, t] of a.inputs) {
      const vals = (dom[a.name] && dom[a.name][n]) || def(t);
      combos = combos.flatMap((c) => vals.map((v) => ({ ...c, [n]: v })));
    }
    out.push(...combos);
  }
  return out;
}
