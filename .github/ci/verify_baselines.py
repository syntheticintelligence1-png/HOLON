"""I52 only (not part of CI's toolchain job): compare the installed baseline tools with config/holon.json "baselines".

Prints one `BASELINE <name> PASS|FAIL|MISSING <detail>` line per tool and exits 1 if any pinned tool fails. The 13
toolchain pins are .github/ci/verify_toolchain.py's and are not re-checked here."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
cfg = json.loads((ROOT / "config" / "holon.json").read_text())
tools = cfg["baselines"]["tools"]
bad = 0


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest() if Path(p).is_file() else "missing"


def out(name, ok, detail):
    global bad
    bad += not ok
    print(f"BASELINE {name} {'PASS' if ok else 'FAIL'} {detail}")


for name in ("echidna", "medusa"):
    t = tools[name]
    out(name, sha(t["path"]) == t["sha256"], f"{t['path']} {sha(t['path'])}")
lock = (ROOT / tools["slither"]["requirements"]).read_text()
venv = Path(tools["slither"]["venv"])
got = subprocess.run([str(venv / "bin" / "pip"), "freeze", "--all"], capture_output=True, text=True).stdout if venv.is_dir() else ""
same = "".join(sorted(got.splitlines(True))) == lock
for name in ("slither", "halmos"):
    out(name, same and hashlib.sha256(lock.encode()).hexdigest() == tools[name]["lock_sha256"], f"venv {venv} matches the lock: {same}")
out("hevm", sha(cfg["hevm"]["path"]) == tools["hevm"]["sha256"], "the toolchain's hevm pin")
gv = subprocess.run(["go", "version"], capture_output=True, text=True).stdout.strip()
out("go_fuzz", gv == tools["go_fuzz"]["go_version"], gv)
cv = subprocess.run(["claude", "--version"], capture_output=True, text=True).stdout.strip()
out("agent_review", cv.split()[0:1] == [tools["agent_review"]["version"].split()[-1]], cv)
print("BASELINES ALL PASS" if not bad else f"BASELINES {bad} FAIL")
sys.exit(1 if bad else 0)
