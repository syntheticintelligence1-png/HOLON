// HOLON M1 consumer replay (Go side, library API) for L_tag_BVH. holon/consumers.py copies this
// file into a scratch copy of morph common/batch, writes holon_consumer.json beside it and runs
//
//	(cd common && GOTOOLCHAIN=local HOLON_CONSUMER=holon_consumer.json go test ./batch -run '^TestHolonTagBVH$' -v -count=1)
//
// The input holds the two headers the real Rollup committed at the same batch index: the version-1
// header whose commit stored the blob versioned hash ("v1_header") and the version-2 header that
// commitState committed after the revert ("header"), plus the stored hash ("stored_vh"). The test
// reads both with the real BatchHeaderBytes accessors (Version; BlobCommitHash, which is
// BlobVersionedHash for v1 and BlobHashesHash for v2, both header[57:89]) and computes, with the real
// aggregateBlobHashes, the aggregate a version-2 consumer expects over the stored hash. It logs one line:
//
//	HOLON L_tag_BVH version=<v> blob_commit_hash=0x.. v1_version=<v> v1_blob_commit_hash=0x.. aggregate=0x..
//	HOLON L_tag_BVH error <stage>: <json-quoted message>
//
// It asserts nothing about the outcome. holon/consumers.py and holon/evidence.py decide the side.
// The comparison aggregate != blob_commit_hash is HOLON's: no Morph consumer decision is exercised
// (common/batch validateLegacyTransitionRecord, the one place that compares a v2 header's field with
// an aggregate, runs only for locally sealed records).
package batch

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"testing"

	"github.com/morph-l2/go-ethereum/common"
	"github.com/morph-l2/go-ethereum/common/hexutil"
)

type holonTagBVHInput struct {
	Header   hexutil.Bytes `json:"header"`
	V1Header hexutil.Bytes `json:"v1_header"`
	StoredVH common.Hash   `json:"stored_vh"`
}

func holonTagBVHQuote(s string) string {
	q, _ := json.Marshal(s)
	return string(q)
}

func holonTagBVHError(t *testing.T, stage string, err error) {
	fmt.Printf("HOLON L_tag_BVH error %s: %s\n", stage, holonTagBVHQuote(err.Error()))
	t.Fatalf("%s: %v", stage, err)
}

func TestHolonTagBVH(t *testing.T) {
	raw, err := os.ReadFile(os.Getenv("HOLON_CONSUMER"))
	if err != nil {
		holonTagBVHError(t, "input", err)
	}
	var in holonTagBVHInput
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&in); err != nil {
		holonTagBVHError(t, "input", err)
	}
	h := BatchHeaderBytes(in.Header)
	version, err := h.Version()
	if err != nil {
		holonTagBVHError(t, "Version", err)
	}
	field, err := h.BlobCommitHash()
	if err != nil {
		holonTagBVHError(t, "BlobCommitHash", err)
	}
	h1 := BatchHeaderBytes(in.V1Header)
	v1Version, err := h1.Version()
	if err != nil {
		holonTagBVHError(t, "V1Version", err)
	}
	v1Field, err := h1.BlobCommitHash()
	if err != nil {
		holonTagBVHError(t, "V1BlobCommitHash", err)
	}
	aggregate := aggregateBlobHashes([]common.Hash{in.StoredVH})
	fmt.Printf("HOLON L_tag_BVH version=%d blob_commit_hash=%s v1_version=%d v1_blob_commit_hash=%s aggregate=%s\n",
		version, field.Hex(), v1Version, v1Field.Hex(), aggregate.Hex())
}
