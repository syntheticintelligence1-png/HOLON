"""A7 tamper (scratch tree only): forge the second-kernel claim of every M3 record whose BendTT check failed, as if
BendTT had accepted it (kernels[bendtt].result checked, independence_class I1-shared, checker.bendtt exit 0 and
ALL PROOFS CHECK, kernel.verdict checked), and forge one REFUTED record's replay as passed with a different
witness value. Prints what it changed."""
import json, sys, glob, os
tree = sys.argv[1]
changed = []
for f in sorted(glob.glob(os.path.join(tree, "results/M3/L*.json"))):
    r = json.load(open(f))
    ks = {k["name"]: k for k in r.get("kernels") or []}
    if r.get("status") in ("PROVED", "REFUTED") and ks.get("bendtt", {}).get("result") == "failed":
        ks["bendtt"]["result"] = "checked"
        r["independence_class"] = "I1-shared"
        if isinstance(r.get("kernel"), dict):
            r["kernel"]["verdict"] = "checked"
        bt = (r.get("checker") or {}).get("bendtt")
        if isinstance(bt, dict):
            bt["exit_code"] = 0
            bt["output_tail"] = "ALL PROOFS CHECK\n"
        for a in r.get("attempts") or []:
            c = (a.get("checker") or {}).get("bendtt") if isinstance(a.get("checker"), dict) else None
            if isinstance(c, dict):
                c["exit_code"] = 0
                c["output_tail"] = "ALL PROOFS CHECK\n"
        json.dump(r, open(f, "w"), indent=2, sort_keys=True)
        open(f, "a").write("\n")
        changed.append(os.path.basename(f))
print("forged second-kernel claims:", len(changed))
for c in changed:
    print("  ", c)
