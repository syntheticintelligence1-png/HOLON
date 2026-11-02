// Load a compiled Bend model whose oracle parameters (I12) are answered by their concrete instances: every lookup
// ap_<p> of a parameter with an instance calls the instance (compiled in oracles.instModule: the model plus one
// inst_<entry> def per sidecar instance); a parameter without one keeps its (empty) table. The tables a model
// function threads are passed empty (tabs). Used by machine.mjs and policy.mjs when a request carries "oracles"
// (holon.mpipeline.CompiledMachine.oracle_runtime), e.g. the M2 trace corpus of `holon replay --milestone M2` (I15).
// Untrusted like every evaluator here: replay compares its outputs with the real code.
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

export async function loadModel(module, oracles) {
  if (!oracles) return (await import(pathToFileURL(module).href)).default;
  const INST = oracles.instModule ? (await import(pathToFileURL(oracles.instModule).href)).default : null;
  let src = readFileSync(module, "utf8");
  const answer = {};
  for (const i of oracles.instances || []) {
    if (answer[i.param]) continue;   // the first instance of a parameter, in sidecar order
    const head = `function $ap_${i.param}$(`;
    if (src.split(head).length !== 2) throw new Error(`the compiled model has no single lookup ${head}`);
    if (!INST || typeof INST[i.fn] !== "function") throw new Error(`the instance module has no ${i.fn}`);
    src = src.replace(head, `function $ap_${i.param}$__holon(`)
      + `\nfunction $ap_${i.param}$(t, x) { return globalThis.__HOLON_INSTANCE["${i.param}"](x); }\n`;
    answer[i.param] = (x) => INST[i.fn](x);
  }
  globalThis.__HOLON_INSTANCE = answer;
  return (await import("data:text/javascript;base64," + Buffer.from(src).toString("base64"))).default;
}

// the (empty) tables model function `fn` takes as trailing arguments
export const tabsOf = (oracles, fn) => ((oracles && oracles.fnTabs && oracles.fnTabs[fn]) || []).map(() => ({ $: "Nil" }));
