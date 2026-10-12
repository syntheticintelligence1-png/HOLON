package derivation

import (
	"fmt"
	"strings"
	"testing"

	"github.com/morph-l2/go-ethereum/common/hexutil"
	eth "github.com/morph-l2/go-ethereum/core/types"
	"github.com/morph-l2/go-ethereum/crypto/kzg4844"
	geth "github.com/morph-l2/go-ethereum/eth"

	commonbatch "morph-l2/common/batch"
	commonblob "morph-l2/common/blob"
)

func recoverValue(f func()) (out any) {
	defer func() { out = recover() }()
	f()
	return nil
}

func TestHolonF3RetrievePanic(t *testing.T) {
	const element = 3968
	var malformed kzg4844.Blob
	malformed[element*32] = 0x01
	if _, err := kzg4844.BlobToCommitment(&malformed); err != nil {
		t.Fatalf("malformed blob is not a valid EIP-4844 blob: %v", err)
	}
	fmt.Printf("HOLON f3 0 commitment ok\n")

	var data []byte
	var err error
	p := recoverValue(func() { data, err = commonbatch.RetrieveBlobBytes(&malformed) })
	if p == nil {
		t.Fatalf("common/batch returned (len=%d, err=%v), expected panic", len(data), err)
	}
	if !strings.Contains(fmt.Sprint(p), "index out of range") {
		t.Fatalf("unexpected panic: %v", p)
	}
	fmt.Printf("HOLON f3 1 common_batch panic %v\n", p)

	var previous kzg4844.Blob
	previous[3967*32] = 0x01
	data, err = commonbatch.RetrieveBlobBytes(&previous)
	if err == nil {
		t.Fatalf("common/batch element 3967 returned len=%d without error", len(data))
	}
	fmt.Printf("HOLON f3 2 common_batch control error %v\n", err)

	data, err = commonblob.RetrieveBlobBytes(&malformed)
	if err == nil {
		t.Fatalf("common/blob returned len=%d without error", len(data))
	}
	fmt.Printf("HOLON f3 3 common_blob control error %v\n", err)
}

func TestHolonF3ParseBatchPanic(t *testing.T) {
	const element = 3968
	var malformed kzg4844.Blob
	malformed[element*32] = 0x01
	header := commonbatch.BatchHeaderV1{
		BatchHeaderV0:   commonbatch.BatchHeaderV0{BatchIndex: 7},
		LastBlockNumber: 9,
	}.Bytes()
	batch := geth.RPCRollupBatch{
		Version:           1,
		ParentBatchHeader: hexutil.Bytes(header),
		LastBlockNumber:   10,
		Sidecar:           eth.BlobTxSidecar{Blobs: []kzg4844.Blob{malformed}},
	}
	p := recoverValue(func() {
		var bi BatchInfo
		_ = bi.ParseBatch(batch)
	})
	if p == nil {
		t.Fatal("ParseBatch did not panic")
	}
	if !strings.Contains(fmt.Sprint(p), "index out of range") {
		t.Fatalf("unexpected panic: %v", p)
	}
	fmt.Printf("HOLON f3 4 parse_batch panic %v\n", p)
}
