#!/usr/bin/env bash
# One-shot toolchain setup for HOLON in a fresh Linux container.
#   tools/setup_env.sh            Bend 2 (pinned) + Lean 4.34.0 for `bend --verdict`
#   tools/setup_env.sh --replay   also Foundry + solc 0.8.24 + a morph checkout for `holon replay`
# Only GitHub and package registries are used, because some sandboxes block
# bend-lang.com, release.lean-lang.org and binaries.soliditylang.org.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PREFIX="${HOLON_PREFIX:-$HOME/.holon}"
mkdir -p "$PREFIX"

# 1. Bend 2, pinned
"$HERE/install_bend.sh" "$PREFIX"
ln -sf "$PREFIX/bin/bend" /usr/local/bin/bend 2>/dev/null || echo "add $PREFIX/bin to PATH"

# 2. Lean 4.34.0 (BendTT kernel for --verdict), via elan + a GitHub release tarball
LEAN_V=4.34.0
if ! "$HOME/.elan/bin/lean" --version 2>/dev/null | grep -q "$LEAN_V"; then
  if [ ! -x "$HOME/.elan/bin/elan" ]; then
    curl -sSfL https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -o "$PREFIX/elan-init.sh"
    sh "$PREFIX/elan-init.sh" -y --default-toolchain none --no-modify-path
  fi
  curl -sSfL -o "$PREFIX/lean.tar.zst" \
    "https://github.com/leanprover/lean4/releases/download/v$LEAN_V/lean-$LEAN_V-linux.tar.zst"
  python3 -m pip install -q zstandard
  python3 - "$PREFIX" <<'PY'
import sys, tarfile, zstandard
prefix = sys.argv[1]
with open(f"{prefix}/lean.tar.zst", "rb") as f:
    tarfile.open(fileobj=zstandard.ZstdDecompressor().stream_reader(f), mode="r|").extractall(prefix)
PY
  rm -f "$PREFIX/lean.tar.zst"
  "$HOME/.elan/bin/elan" toolchain link "leanprover/lean4:v$LEAN_V" "$PREFIX/lean-$LEAN_V-linux"
  "$HOME/.elan/bin/elan" default "leanprover/lean4:v$LEAN_V"
fi
"$HOME/.elan/bin/lean" --version

if [ "${1:-}" = "--replay" ]; then
  # 3. Foundry + solc 0.8.24 + morph checkout at the facts' commit
  mkdir -p "$PREFIX/foundry"
  curl -sSfL "https://github.com/foundry-rs/foundry/releases/download/stable/foundry_stable_linux_amd64.tar.gz" \
    | tar -xz -C "$PREFIX/foundry"
  curl -sSfL -o "$PREFIX/solc-0.8.24" https://github.com/ethereum/solidity/releases/download/v0.8.24/solc-static-linux
  chmod +x "$PREFIX/solc-0.8.24"
  if [ ! -d "$PREFIX/morph/.git" ]; then
    git clone --filter=blob:none --no-checkout https://github.com/morph-l2/morph "$PREFIX/morph"
  fi
  git -C "$PREFIX/morph" checkout -q 3e44e795586af3e11285b603ab642c67823add51
  (cd "$PREFIX/morph/contracts" && npm ci)
  echo "run: PATH=$PREFIX/foundry:\$PATH python -m holon replay --morph $PREFIX/morph --solc $PREFIX/solc-0.8.24"
fi
