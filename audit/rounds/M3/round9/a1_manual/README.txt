Round 9, A1: the by-hand re-run of mutants s5 and s6 (the bundle documents), because `holon audit mutation` cannot
re-extract them (a1.json baseline: "holon extract solidity: refused: sidecar .../gen/M3/bundle/sidecars/<m>.json:
malformed: output is not a repo-relative path ending .extracted.json"; F-M3-43).

Steps, at the target da95f80f48aa04db53e439fe6cd5455a837768c8, in scratch copies only:
 1. git clone --shared --no-checkout /root/work/morph M; git -C M checkout 3e44e795586af3e11285b603ab642c67823add51
    apply s5_s6.diff in M (both mutants together: they touch two different bundle members), then
    git -C M update-index --assume-unchanged <the two files>
 2. git worktree add --detach T da95f80; in T set config/holon.json extract.sources["morph-l2/morph"] = M
 3. in T: holon bundle --milestone M3 extract     -> messenger.json and queue.json change (bundle_documents.diff)
          holon bundle --milestone M3 model; holon bundle --milestone M3 laws
          holon sorts|codecs|own|diagram|evidence|disch --milestone M3; holon derive --milestone M3
          (derive: 25 messenger/queue laws change in facts_sha256 only; one, L_sym_tau_..._getFirstUnfinalized
           MessageEnqueueTime, also changes its notes)
          holon bundle --milestone M3 refine    (holon run refuses until the deployment is re-made)
          holon run --milestone M3 --laws $(cat laws.txt)                    -> mutant_run.log
 4. a fresh worktree B at da95f80 (unmutated): holon run --milestone M3 --laws $(cat laws.txt)  -> baseline_run.log
Result: the 26 statuses (25 laws plus the contract law the run reports) are identical on both sides.
 s6 (sendMessage's duplicate guard made vacuous) moves nothing: filed as F-M3-44.
 s5 (getFirstUnfinalizedMessageEnqueueTime returns 0 when nothing is pending) moves nothing, but the two laws over that
 view are already REFUTED at the baseline (the sentinel_inv and tau laws), so no status can move: judged masked, not filed.
