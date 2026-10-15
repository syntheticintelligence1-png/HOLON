#!/usr/bin/env bash
# One-shot toolchain setup for HOLON in a fresh Linux container.
#   tools/setup_env.sh            Bend 2 (pinned) + Lean 4.34.0 for `bend --verdict`
#   tools/setup_env.sh --replay   also Foundry + solc 0.8.24 + a morph checkout for `holon replay`
#   tools/setup_env.sh --extract  only the pinned extraction tools (slither-analyzer, crytic-compile, z3-solver: the I17
#                                 key's thresholds.tool_pins) into a venv at $PREFIX/tools/extract, from the hash-pinned
#                                 tools/extract-requirements.txt (wheels only, --require-hashes). Never inside the repo;
#                                 holon's own extraction (`holon extract solidity`) imports none of them.
#   tools/setup_env.sh --solc     only the pinned solc 0.8.24 (the static Linux binary of GitHub release v0.8.24),
#                                 checked against config/holon.json replay.solc_sha256 and installed as
#                                 $PREFIX/solc-0.8.24 (I48: rule N1 (e) and the Solidity isomorphism check). Nothing
#                                 else; a download with another sha256 is refused and nothing is installed.
# Only GitHub and package registries are used, because some sandboxes block
# bend-lang.com, release.lean-lang.org and binaries.soliditylang.org.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PREFIX="${HOLON_PREFIX:-$HOME/.holon}"
mkdir -p "$PREFIX"

if [ "${1:-}" = "--extract" ]; then
  # Extraction tools (BUILD_PLAN I17): a venv outside the repo, every wheel hash-checked.
  VENV="${PREFIX}/tools/extract"
  case "$(cd "$PREFIX" && pwd)/" in
    "$(cd "$HERE/.." && pwd)/"*) echo "refusing: $VENV is inside the repo" >&2; exit 2 ;;
  esac
  python3 -m venv "$VENV"
  "$VENV/bin/python" -m pip install -q --disable-pip-version-check --no-deps --require-hashes --only-binary=:all: \
    -r "$HERE/extract-requirements.txt"
  "$VENV/bin/python" -m pip check
  "$VENV/bin/python" -I -c "import importlib.metadata as m; print({k: m.version(k) for k in ('slither-analyzer', 'crytic-compile', 'z3-solver')})"
  exit 0
fi

if [ "${1:-}" = "--solc" ]; then
  # The pinned solc 0.8.24 (I48), from the GitHub release only, its sha256 checked before it is installed.
  WANT="$(python3 -I -c 'import json,sys; print(json.load(open(sys.argv[1]))["replay"]["solc_sha256"])' \
    "$HERE/../config/holon.json")"
  if ! printf '%s' "$WANT" | grep -Eqx '[0-9a-f]{64}'; then
    echo "config/holon.json replay.solc_sha256 is not a sha256" >&2
    exit 2
  fi
  DEST="$PREFIX/solc-0.8.24"
  TMP="$(mktemp "$PREFIX/.solc-0.8.24.XXXXXX")"
  trap 'rm -f "$TMP"' EXIT
  curl -sSfL -o "$TMP" https://github.com/ethereum/solidity/releases/download/v0.8.24/solc-static-linux
  GOT="$(sha256sum "$TMP" | cut -d' ' -f1)"
  if [ "$GOT" != "$WANT" ]; then
    echo "refusing: the downloaded solc has sha256 $GOT, not the pinned $WANT; nothing installed" >&2
    exit 2
  fi
  chmod 0755 "$TMP"
  mv -f "$TMP" "$DEST"
  trap - EXIT
  "$DEST" --version | tail -n 1
  echo "installed $DEST (sha256 $GOT)"
  exit 0
fi

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
  echo "run: PATH=$PREFIX/foundry:\$PATH python -m holon replay --morph $PREFIX/morph --solc $PREFIX/solc-0.8.24"
fi
