"""CI only: compare the installed toolchain with the pins in config/holon.json, read-only.

Prints one `PIN <name> PASS|FAIL <detail>` line per pin and exits 1 if any fails. It uses HOLON's own
fingerprint functions (holon.bend, holon.lean, holon.replay), so a PASS here is what GENV / G7 / replay
compare; it changes no pin and no checker. Run from the repository root: python .github/ci/verify_toolchain.py
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from holon import bend, lean, replay  # noqa: E402

cfg = json.loads((ROOT / "config" / "holon.json").read_text())
results = []


def pin(name, ok, detail):
    results.append(ok)
    print(f"PIN {name} {'PASS' if ok else 'FAIL'} {detail}", flush=True)


def guard(name, f):
    try:
        f()
    except Exception as e:  # noqa: BLE001
        pin(name, False, f"{type(e).__name__}: {e}")


def check_bend():
    fp = bend.fingerprint(bend.config(ROOT))
    want = cfg["bend"]["pinned_fingerprint"]
    pin("bend_fingerprint", fp["fingerprint"] == want,
        f"got {fp['fingerprint']} want {want} (head {fp['head']}, bun {fp['bun']} sha256 {fp['bun_sha256']})")
    v = subprocess.run(["bend", "version"], capture_output=True, text=True).stdout.strip()
    pin("bend_version", cfg["bend"]["pinned_version"] in v, f"`bend version` -> {v!r}")
    k = bend.verdict_kernel_path(Path(fp["checkout"]))
    got = bend.file_sha256(k) if k.is_file() else "missing"
    pin("bendtt_kernel", got == cfg["bend"]["pinned_kernel_sha256"],
        f"{k} got {got} want {cfg['bend']['pinned_kernel_sha256']}")


def check_lean():
    ok, detail = lean.toolchain_ok(lean.config(ROOT))
    pin("lean", ok, detail)


def check_replay():
    r = cfg["replay"]
    for key, path in (("forge_sha256", r["forge"]), ("solc_sha256", r["solc"])):
        got = replay.file_sha256(path) if Path(path).is_file() else "missing"
        pin(key, got == r[key], f"{path} got {got} want {r[key]}")
    nm = Path(r["sol_deps"]) / "node_modules"
    got = replay.tree_sha256(nm) if nm.is_dir() else "missing"
    pin("sol_deps_sha256", got == r["sol_deps_sha256"], f"{nm} got {got} want {r['sol_deps_sha256']}")
    got = replay.go_version()
    pin("go_version", got == r["go_version"], f"got {got!r} want {r['go_version']!r}")
    m = subprocess.run(["git", "-C", r["morph"], "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    pin("morph_commit", m.startswith("3e44e795586af3e11285b603ab642c67823add51"), f"{r['morph']} HEAD {m}")


def check_hevm():
    h = cfg["hevm"]
    for name, d in (("hevm", h), ("cvc5", h["solver"])):
        got = replay.file_sha256(d["path"]) if Path(d["path"]).is_file() else "missing"
        pin(f"{name}_sha256", got == d["sha256"], f"{d['path']} got {got} want {d['sha256']}")


for name, f in (("bend", check_bend), ("lean", check_lean), ("replay", check_replay), ("hevm", check_hevm)):
    guard(name, f)
print(f"PINS {'ALL PASS' if all(results) else 'FAILED'} ({sum(results)}/{len(results)})")
sys.exit(0 if all(results) else 1)
