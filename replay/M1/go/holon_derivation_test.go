// HOLON M1 consumer replay (Go side, library API) for L_fact_Z. holon/consumers.py copies this
// file into a scratch copy of morph node/derivation (in a go.work over bindings/, common/, node/),
// writes holon_consumer.json beside it and runs
//
//	(cd node && GOTOOLCHAIN=local HOLON_CONSUMER=holon_consumer.json go test ./derivation -run '^TestHolonFactZ$' -v -count=1)
//
// The input holds the parent batch header the chain replay committed on ("parent_header") and, per
// commit label, the commitBatch fields plus the number of all-zero blobs the commit carried
// ("blobs"). For each commit, in label order, the test builds the geth.RPCRollupBatch derivation
// consumes: ParentBatchHeader = parent header, the commit's roots / lastBlockNumber /
// numL1Messages, no calldata block contexts, and a version-0 blob sidecar with `blobs` all-zero
// blobs and their real KZG commitments and blob proofs (an empty sidecar for blobs = 0). It then
// calls the real (*BatchInfo).ParseBatch and logs its outcome ("ok", "error: <msg>", or
// "panic: <value>"). It also logs the KZG versioned hash of the all-zero blob it built:
//
//	HOLON L_fact_Z zero_blob_vh 0x..
//	HOLON L_fact_Z <label> sidecar_blobs=<n> outcome=<json-quoted outcome>
//	HOLON L_fact_Z error <stage>: <json-quoted message>      (the harness could not build its input)
//
// An error returned by ParseBatch is an outcome, not a test failure: the test asserts nothing
// about what ParseBatch does; holon/consumers.py decides the side's status.
package derivation

import (
	"bytes"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"testing"

	"github.com/morph-l2/go-ethereum/common"
	"github.com/morph-l2/go-ethereum/common/hexutil"
	eth "github.com/morph-l2/go-ethereum/core/types"
	"github.com/morph-l2/go-ethereum/crypto/kzg4844"
	geth "github.com/morph-l2/go-ethereum/eth"
)

type holonFactZCommit struct {
	Version         uint        `json:"version"`
	LastBlockNumber uint64      `json:"last_block_number"`
	NumL1Messages   uint16      `json:"num_l1_messages"`
	PrevStateRoot   common.Hash `json:"prev_state_root"`
	PostStateRoot   common.Hash `json:"post_state_root"`
	WithdrawRoot    common.Hash `json:"withdraw_root"`
	Blobs           int         `json:"blobs"`
}

type holonFactZInput struct {
	ParentHeader hexutil.Bytes               `json:"parent_header"`
	Commits      map[string]holonFactZCommit `json:"commits"`
}

func holonFactZQuote(s string) string {
	q, _ := json.Marshal(s)
	return string(q)
}

func holonFactZError(t *testing.T, stage string, err error) {
	fmt.Printf("HOLON L_fact_Z error %s: %s\n", stage, holonFactZQuote(err.Error()))
	t.Fatalf("%s: %v", stage, err)
}

// holonFactZParse runs the real ParseBatch; a returned error or a panic is the outcome.
func holonFactZParse(batch geth.RPCRollupBatch) (outcome string) {
	defer func() {
		if r := recover(); r != nil {
			outcome = fmt.Sprintf("panic: %v", r)
		}
	}()
	if err := new(BatchInfo).ParseBatch(batch); err != nil {
		return "error: " + err.Error()
	}
	return "ok"
}

func TestHolonFactZ(t *testing.T) {
	raw, err := os.ReadFile(os.Getenv("HOLON_CONSUMER"))
	if err != nil {
		holonFactZError(t, "input", err)
	}
	var in holonFactZInput
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&in); err != nil {
		holonFactZError(t, "input", err)
	}

	// The all-zero blob, its KZG commitment, blob proof and versioned hash.
	var zero kzg4844.Blob
	commit, err := kzg4844.BlobToCommitment(&zero)
	if err != nil {
		holonFactZError(t, "BlobToCommitment", err)
	}
	proof, err := kzg4844.ComputeBlobProof(&zero, commit)
	if err != nil {
		holonFactZError(t, "ComputeBlobProof", err)
	}
	vh := kzg4844.CalcBlobHashV1(sha256.New(), &commit)
	fmt.Printf("HOLON L_fact_Z zero_blob_vh %s\n", hexutil.Encode(vh[:]))

	labels := make([]string, 0, len(in.Commits))
	for l := range in.Commits {
		labels = append(labels, l)
	}
	sort.Strings(labels)
	for _, l := range labels {
		c := in.Commits[l]
		if c.Blobs < 0 {
			holonFactZError(t, "input", fmt.Errorf("commit %s: negative blob count %d", l, c.Blobs))
		}
		sidecar := eth.BlobTxSidecar{Version: eth.BlobSidecarVersion0}
		for i := 0; i < c.Blobs; i++ {
			sidecar.Blobs = append(sidecar.Blobs, zero)
			sidecar.Commitments = append(sidecar.Commitments, commit)
			sidecar.Proofs = append(sidecar.Proofs, proof)
		}
		batch := geth.RPCRollupBatch{
			Version:           c.Version,
			ParentBatchHeader: append(hexutil.Bytes(nil), in.ParentHeader...),
			PrevStateRoot:     c.PrevStateRoot,
			PostStateRoot:     c.PostStateRoot,
			WithdrawRoot:      c.WithdrawRoot,
			LastBlockNumber:   c.LastBlockNumber,
			NumL1Messages:     c.NumL1Messages,
			Sidecar:           sidecar,
		}
		fmt.Printf("HOLON L_fact_Z %s sidecar_blobs=%d outcome=%s\n", l, len(batch.Sidecar.Blobs),
			holonFactZQuote(holonFactZParse(batch)))
	}
}
