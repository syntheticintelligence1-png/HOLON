// realhdr — drives the REAL morph common/batch header codecs. JSON lines.
// Runs inside a go.work with morph's common/ + bindings/ trees (see refine.py).
// Request: {"h":[257 bytes as uints]}            -> {"enc_go_v0":[...], "enc_go_v1":[...]}
//          {"b":[bytes as uints]}               -> {"ok_go":0|1, "dec":[fields or null]}
package main

import (
	"bufio"
	"encoding/json"
	"os"

	"morph-l2/common/batch"
	"github.com/morph-l2/go-ethereum/common"
)

type req struct {
	H []uint64 `json:"h"`
	B []uint64 `json:"b"`
}

func hdrOf(xs []uint64) (h batch.BatchHeaderV1) {
	get := func(off, n int) uint64 {
		var x uint64
		for i := 0; i < n; i++ {
			x = x<<8 | uint64(xs[off+i]&0xff)
		}
		return x
	}
	at := func(off int, dst []byte) {
		for i := 0; i < 32; i++ {
			dst[i] = byte(xs[off+i])
		}
	}
	h.BatchIndex = get(1, 8)
	h.L1MessagePopped = get(9, 8)
	h.TotalL1MessagePopped = get(17, 8)
	at(25, h.DataHash[:])
	at(57, h.BlobVersionedHash[:])
	at(89, h.PrevStateRoot[:])
	at(121, h.PostStateRoot[:])
	at(153, h.WithdrawalRoot[:])
	at(185, h.SequencerSetVerifyHash[:])
	at(217, h.ParentBatchHash[:])
	h.LastBlockNumber = get(249, 8)
	return h
}

func bytesOf(xs []uint64) []byte {
	b := make([]byte, len(xs))
	for i, x := range xs {
		b[i] = byte(x)
	}
	return b
}

func uintsOf(b []byte) []uint64 {
	out := make([]uint64, len(b))
	for i, x := range b {
		out[i] = uint64(x)
	}
	return out
}

func main() {
	enc := json.NewEncoder(os.Stdout)
	sc := bufio.NewScanner(os.Stdin)
	sc.Buffer(make([]byte, 16<<20), 16<<20)
	for sc.Scan() {
		var r req
		if err := json.Unmarshal(sc.Bytes(), &r); err != nil {
			enc.Encode(map[string]any{"error": err.Error()})
			continue
		}
		out := map[string]any{}
		if r.H != nil {
			h := hdrOf(r.H)
			v0 := batch.BatchHeaderV0{
				BatchIndex: h.BatchIndex, L1MessagePopped: h.L1MessagePopped,
				TotalL1MessagePopped: h.TotalL1MessagePopped, DataHash: h.DataHash,
				BlobVersionedHash: h.BlobVersionedHash, PrevStateRoot: h.PrevStateRoot,
				PostStateRoot: h.PostStateRoot, WithdrawalRoot: h.WithdrawalRoot,
				SequencerSetVerifyHash: h.SequencerSetVerifyHash, ParentBatchHash: h.ParentBatchHash,
			}
			out["enc_go_v0"] = uintsOf(v0.Bytes())
			out["enc_go_v1"] = uintsOf(h.Bytes())
		}
		if r.B != nil {
			b := batch.BatchHeaderBytes(bytesOf(r.B))
			_, herr := b.Hash()
			out["ok_go"] = 0
			if herr == nil {
				out["ok_go"] = 1
			}
			if herr != nil {
				out["dec"] = nil
			} else {
				fields := []any{}
				push := func(x any, err error) {
					if err != nil {
						fields = append(fields, "ERR")
					} else {
						fields = append(fields, x)
					}
				}
				ver, _ := b.Version()
				push(uint64(ver), nil)
				pushU := func(f func() (uint64, error)) { v, e := f(); push(v, e) }
				pushH := func(f func() (common.Hash, error)) {
					v, e := f()
					if e != nil {
						push(nil, e)
					} else {
						push(uintsOf(v[:]), nil)
					}
				}
				pushU(b.BatchIndex)
				pushU(b.L1MessagePopped)
				pushU(b.TotalL1MessagePopped)
				pushH(b.DataHash)
				pushH(b.BlobVersionedHash)
				pushH(b.PrevStateRoot)
				pushH(b.PostStateRoot)
				pushH(b.WithdrawalRoot)
				pushH(b.SequencerSetVerifyHash)
				pushH(b.ParentBatchHash)
				pushU(b.LastBlockNumber)
				out["dec"] = fields
			}
		}
		enc.Encode(out)
	}
}
