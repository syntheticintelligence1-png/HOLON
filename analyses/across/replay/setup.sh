#!/usr/bin/env bash
# Prepare the replay harness: pinned target checkout, its dependencies, Foundry 1.7.1, and the verbatim UMA
# SkinnyOptimisticOracle source used by T09. Everything lands under replay/.work (git-ignored).
set -euo pipefail
cd "$(dirname "$0")"
ACROSS_COMMIT=b1c4e86225420df5cb8d03042526622aca80fe61
FOUNDRY_VERSION=v1.7.1
UMA_SKINNY_OO=0xeE3Afe347D5C74317041E2618C49534dAf887c24
UMA_SRC_SHA256=$(cat uma.sha256)
mkdir -p .work
if [ ! -d .work/across/.git ]; then
  git clone --filter=blob:none https://github.com/across-protocol/contracts .work/across
fi
git -C .work/across fetch --depth 1 origin "$ACROSS_COMMIT"
git -C .work/across checkout -q "$ACROSS_COMMIT"
git -C .work/across submodule update --init --depth 1 lib/forge-std lib/murky lib/sp1-contracts
git -C .work/across/lib/sp1-contracts submodule update --init --depth 1 contracts/lib/openzeppelin-contracts
(cd .work/across && yarn install --frozen-lockfile --ignore-scripts)
if [ ! -x .work/foundry/forge ]; then
  mkdir -p .work/foundry
  curl -sSL "https://github.com/foundry-rs/foundry/releases/download/${FOUNDRY_VERSION}/foundry_${FOUNDRY_VERSION}_linux_amd64.tar.gz" \
    | tar -xz -C .work/foundry
fi
mkdir -p generated src/uma
cp .work/across/generated/constants.json generated/constants.json
if [ ! -f src/uma/SkinnyOO_mainnet.sol ]; then
  if [ -n "${ETHERSCAN_API_KEY:-}" ]; then
    curl -sS "https://api.etherscan.io/v2/api?chainid=1&module=contract&action=getsourcecode&address=${UMA_SKINNY_OO}&apikey=${ETHERSCAN_API_KEY}" \
      | python3 -c 'import json,sys; r=json.load(sys.stdin)["result"][0]; open("src/uma/main.sol","w").write(r["SourceCode"])'
    { echo "// SPDX-License-Identifier: AGPL-3.0-only"
      echo "// Verbatim flattened source of UMA SkinnyOptimisticOracle as verified on Etherscan for Ethereum mainnet"
      echo "// ${UMA_SKINNY_OO} (the address HubPool's Finder resolves for SkinnyOptimisticOracle)."
      echo "// Originally compiled with v0.8.9+commit.e5eed63a; recompiled here unmodified."
      cat src/uma/main.sol; } > src/uma/SkinnyOO_mainnet.sol
    rm src/uma/main.sol
    echo "${UMA_SRC_SHA256}  src/uma/SkinnyOO_mainnet.sol" | sha256sum -c -
  else
    echo "NOTE: ETHERSCAN_API_KEY unset; T09 (UMA SkinnyOptimisticOracle replay) will be reported as NOT RUN." >&2
  fi
fi
echo "setup complete"
