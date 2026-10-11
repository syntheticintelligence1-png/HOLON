# M0 replay on morph-l2/morph @ 3e44e795586af3e11285b603ab642c67823add51

Go (go1.24.6). Run from a scratch worktree of the morph repo:

    git -C morph worktree add --detach ../morph_scratch 3e44e79
    cp replay/M0/go/holon_replay_test.go ../morph_scratch/common/batch/
    cd ../morph_scratch/common && HOLON_RESULTS=<holon>/results/M0 go test ./batch/ -run HolonReplay -v -count=1

Solidity (forge 1.8.5, solc 0.8.24). Use a scratch copy of `contracts/` with
contracts/mock and contracts/test removed, `npm i --no-save
@openzeppelin/contracts@4.9.3 @openzeppelin/contracts-upgradeable@4.9.3
@rari-capital/solmate@6.4.0`, and forge-std v1.9.7 in lib/. Copy
solidity/Harness.t.sol into test/, then run:

    HOLON_DOM_WITNESS=$(python3 -c "import json;print(json.load(open('<holon>/results/M0/L_dom_hdr.json'))['witness']['b'])") \
      forge test --match-path test/Harness.t.sol -vv
