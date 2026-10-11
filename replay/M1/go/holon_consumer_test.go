// HOLON M1 consumer replay (Go side, library API) for L_tag_BVH. holon/consumers.py copies this
// file into a scratch copy of morph common/batch, writes holon_consumer.json beside it and runs
//
//	(cd common && GOTOOLCHAIN=local HOLON_CONSUMER=holon_consumer.json go test ./batch -run '^TestHolonTagBVH$' -v -count=1)
//
// The input holds the 257-byte version-2 batch header the real Rollup committed ("header") and the
// v1 blob versioned hash stored for that batch index ("stored_vh"). The test reads the header with
// the real BatchHeaderBytes accessors (Version, BlobCommitHash; for version 2 BlobCommitHash is
// BlobHashesHash = header[57:89]) and recomputes, with the real aggregateBlobHashes, the value a
// version-2 consumer expects in that field: keccak256(blobhash(0) || ... || blobhash(N-1)) over the
// stored hashes. It logs exactly one line:
//
//	HOLON L_tag_BVH version=<v> blob_commit_hash=0x.. aggregate=0x.. differ=<bool>
//	HOLON L_tag_BVH error <stage>: <json-quoted message>     (stage: input | Version | BlobCommitHash)
//
// It measures and asserts nothing about the outcome; holon/consumers.py decides the side's status.
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
	aggregate := aggregateBlobHashes([]common.Hash{in.StoredVH})
	fmt.Printf("HOLON L_tag_BVH version=%d blob_commit_hash=%s aggregate=%s differ=%v\n",
		version, field.Hex(), aggregate.Hex(), aggregate != field)
}
