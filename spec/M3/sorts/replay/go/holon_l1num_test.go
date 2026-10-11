package batch

import (
	"testing"

	"github.com/morph-l2/go-ethereum/common"
)

// HOLON M3 replay of L_sort3_width_l1num (O28): two appended blocks with 65535 + 1 L1 messages.
// Semantic count Σ len(l1TxHashes) = 65536; l1TxNum is a uint16 and wraps to 0.
func TestHolonL1NumWidth(t *testing.T) {
	bd := &BatchData{}
	hs := make([]common.Hash, 65535)
	bd.Append([]byte{}, []byte{}, hs)
	bd.Append([]byte{}, []byte{}, hs[:1])
	t.Logf("l1TxNum=%d hashes=%d", bd.l1TxNum, len(bd.l1TxHashes)/32)
	if bd.l1TxNum != 0 {
		t.Fatalf("expected the uint16 realization to wrap to 0, got %d", bd.l1TxNum)
	}
	if len(bd.l1TxHashes)/32 != 65536 {
		t.Fatalf("semantic count %d", len(bd.l1TxHashes))
	}
}
