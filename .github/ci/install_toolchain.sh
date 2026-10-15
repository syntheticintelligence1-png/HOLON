#!/usr/bin/env bash
# CI only: install the pinned HOLON toolchain on a GitHub-hosted ubuntu-24.04 runner, into $HOME.
# Every download is checked against a sha256; the pins themselves live in config/holon.json and are
# never changed here (the gates' GENV / G7 / replay checks compare against them).
#   bun 1.4.2 (binary sha256 below)      -> ~/.bun/bin/bun
#   Bend 2.0.36 @ 2343aec (install_bend)  -> ~/.holon/bend, wrapper ~/.holon/bin/bend
#   Lean 4.34.0 release tarball (sha256) -> ~/.holon/lean-4.34.0-linux, linked as the toolchain
#     directory ~/.elan/toolchains/leanprover--lean4---v4.34.0 (no elan binary: HOLON and the kernel
#     build both resolve that directory directly)
#   BendTT kernel (built by bend --verdict from the pinned sources) -> ~/.bend/bendtt/<h>/bendtt
#   forge (foundry stable), solc 0.8.24, morph @ 3e44e79      -> ~/holon-work (linked as /root/work)
#   sol_deps (holon.replay.ensure_sol_deps), hevm 0.55.1, cvc5 1.2.0 -> ~/.holon/tools
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
BUN_VERSION=1.4.2
BUN_ZIP_SHA=36368faef7527875d5ffa52e53cd48021741f2a83eb6208a8dd64068d422a913
BUN_BIN_SHA=a83d263767d839e4d2649ca8e35d07159c7afc99afdc96d731ced29e056dda0c
LEAN_TAR_SHA=caaa98356098c85dc0fcbbd28e1ec66f39eb6551829972b752ff20e1286b646b  # lean-4.34.0-linux.tar.zst
MORPH_COMMIT=3e44e795586af3e11285b603ab642c67823add51
WORK="$HOME/holon-work"
TMP="$(mktemp -d)"

cfg() { python3 -c "import json,sys; d=json.load(open('$REPO/config/holon.json'))
for k in sys.argv[1].split('.'): d=d[k]
print(d)" "$1"; }
sha_ok() {  # sha_ok <file> <sha256>
  local got; got="$(sha256sum "$1" | cut -d' ' -f1)"
  if [ "$got" != "$2" ]; then echo "SHA MISMATCH $1: got $got want $2" >&2; exit 1; fi
  echo "sha256 ok $1 $got"
}
fetch() { curl -sSfL --retry 5 --retry-delay 5 -o "$1" "$2"; }

# 1. bun, the exact release asset (the plain x64 and the baseline zips carry the same binary)
mkdir -p "$HOME/.bun/bin"
fetch "$TMP/bun.zip" "https://github.com/oven-sh/bun/releases/download/bun-v$BUN_VERSION/bun-linux-x64.zip"
sha_ok "$TMP/bun.zip" "$BUN_ZIP_SHA"
unzip -q -o "$TMP/bun.zip" -d "$TMP"
install -m 0755 "$TMP/bun-linux-x64/bun" "$HOME/.bun/bin/bun"
sha_ok "$HOME/.bun/bin/bun" "$BUN_BIN_SHA"
[ "$("$HOME/.bun/bin/bun" --version)" = "$BUN_VERSION" ]

# 2. Bend at the pinned commit (finds ~/.bun/bin/bun, so it installs no other bun)
"$REPO/tools/install_bend.sh" "$HOME/.holon"

# 3. Lean, the exact release tarball (sha256-checked), extracted with the runner's zstd. elan is not
#    installed: holon/lean.py and the BendTT kernel build resolve ~/.elan/toolchains/<toolchain>/bin
#    directly, which is all `elan toolchain link` would have created.
LEAN_V="$(cfg lean.pinned_version)"
[ "$LEAN_V" = 4.34.0 ] || { echo "config lean.pinned_version is $LEAN_V; LEAN_TAR_SHA pins 4.34.0" >&2; exit 1; }
fetch "$TMP/lean.tar.zst" "https://github.com/leanprover/lean4/releases/download/v$LEAN_V/lean-$LEAN_V-linux.tar.zst"
sha_ok "$TMP/lean.tar.zst" "$LEAN_TAR_SHA"
tar --use-compress-program=unzstd -xf "$TMP/lean.tar.zst" -C "$HOME/.holon"
LEAN_TC="$HOME/.elan/toolchains/leanprover--lean4---v$LEAN_V"
mkdir -p "$HOME/.elan/toolchains"
ln -sfn "$HOME/.holon/lean-$LEAN_V-linux" "$LEAN_TC"
"$LEAN_TC/bin/lean" --version

# 4. the BendTT kernel: bend --verdict builds and caches it on first use
( cd "$REPO/bend/probes" && "$HOME/.holon/bin/bend" p01_law_refl.bend --verdict )

# 5. replay / extraction toolchain at the config's absolute paths (/root/work -> ~/holon-work, /root/.holon -> ~/.holon)
mkdir -p "$WORK/foundry"
fetch "$TMP/foundry.tgz" "https://github.com/foundry-rs/foundry/releases/download/stable/foundry_stable_linux_amd64.tar.gz"
tar -xzf "$TMP/foundry.tgz" -C "$WORK/foundry"
sha_ok "$WORK/foundry/forge" "$(cfg replay.forge_sha256)"
fetch "$WORK/solc-0.8.24" https://github.com/ethereum/solidity/releases/download/v0.8.24/solc-static-linux
chmod +x "$WORK/solc-0.8.24"
sha_ok "$WORK/solc-0.8.24" "$(cfg replay.solc_sha256)"
git clone -q --filter=blob:none --no-checkout https://github.com/morph-l2/morph "$WORK/morph"
git -C "$WORK/morph" checkout -q "$MORPH_COMMIT"
python3 - "$REPO" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from pathlib import Path
from holon import replay
nm = replay.ensure_sol_deps(Path.home() / ".holon" / "tools" / "sol_deps")
print("sol_deps tree", replay.tree_sha256(nm))
PY

# 6. hevm and its solver (optional in G1, installed so G1 regenerates results/<m>/hevm.json)
H="$HOME/.holon/tools/hevm-$(cfg hevm.version)"; C="$HOME/.holon/tools/cvc5-$(cfg hevm.solver.version)"
mkdir -p "$H" "$C"
fetch "$H/hevm" "$(cfg hevm.url)"; chmod +x "$H/hevm"; sha_ok "$H/hevm" "$(cfg hevm.sha256)"
fetch "$TMP/cvc5.zip" "$(cfg hevm.solver.url)"
unzip -q -o "$TMP/cvc5.zip" -d "$TMP/cvc5"
install -m 0755 "$(find "$TMP/cvc5" -type f -name cvc5 -path '*/bin/*' | head -1)" "$C/cvc5"
sha_ok "$C/cvc5" "$(cfg hevm.solver.sha256)"
rm -rf "$TMP"
