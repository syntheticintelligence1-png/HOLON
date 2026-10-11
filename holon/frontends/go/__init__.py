"""holon.frontends.go: the M2 go/ssa extraction frontend (unit S3).

Pipeline:

    morph checkout ──gossa tool (tool/)──▶ gossa-dump/0.1 JSON (value graph)
                       ──model.py──▶ per-function op streams and guard trees
              ┌──codecs.py──▶ spec/M2/extracted/go_codecs.json   (codecs + partiality)
              └──own.py─────▶ spec/M2/extracted/go_batchdata.json (slice/backing facts)

Rules honoured (docs/M2_SPEC.md §2):
  * the extractor never reads hand-written facts; the differ (differ.py) is the
    only component that touches the hand fact files, and only as the
    comparison target inside tests;
  * anything the frontend cannot translate is coverage debt
    (spec/M2/coverage/go.json), never approximated;
  * outputs are deterministic: sorted iteration, no timestamps, repo-relative
    paths only.
"""
